"""実発注トレーダーの回帰テスト。実際のAPI呼び出しは一切行わない（モック）。

最重要:
  - 判断ロジックがペーパーと共有されていること（cta/decision.py経由）
  - 緊急クローズ時は照合不一致があっても**取引所の実数量で決済を断行**すること
    （通常時の停止と挙動を分けないと、ブレーカーが損失を垂れ流す）
"""
import json
import sqlite3

import numpy as np
import pytest

from cta import decision
from cta import execution as ex
from cta.config import Config
from cta.live_trader import LiveTrader, LiveGuardError
from tests.test_engine import make_db, make_cfg, trending_market, T0, STEP


class FakeExecutor:
    """BitgetLiveExecutorの差し替え。発注は記録するだけ。"""

    def __init__(self, positions=None, equity=1000.0, available=1000.0):
        self.positions = positions or {}
        self.equity = equity
        self.available = available
        self.placed = []
        self.raise_on_place = None

    def reconcile_positions(self, symbols, internal):
        real = {s: self.positions.get(s, 0.0) for s in symbols}
        mism = {s: {"exchange": real[s], "internal": internal.get(s, 0.0)}
                for s in symbols if abs(real[s] - internal.get(s, 0.0)) > 1e-9}
        return {"exchange_positions": real, "mismatches": mism}

    def fetch_equity_usd(self):
        return self.equity

    def fetch_available_usd(self):
        return self.available

    def place_order(self, order, bar_epoch, min_notional_usd=5.0):
        if self.raise_on_place:
            raise self.raise_on_place
        self.placed.append(order)
        px = order.signal_price or 100.0
        return ex.Fill(symbol=order.symbol, qty=order.qty,
                       signal_price=px, ref_price=px, fill_price=px,
                       fee_usd=0.0, reason=order.reason, ts=bar_epoch)


def _mk(tmp_path, executor, **kw):
    db, _, closes = trending_market(tmp_path, drift=0.004, noise=0.005)
    cfg = make_cfg(db, ["A"])
    now = T0 + len(closes) * STEP + 60
    tr = LiveTrader(cfg, executor, base_dir=str(tmp_path), **kw)
    return tr, now, closes


# --- 判断ロジックの共有 ------------------------------------------------

def test_decision_layer_is_shared_with_paper(tmp_path):
    """同じ入力なら plan_orders は同一のOrderを返す（ペーパーもライブも同じ関数）。"""
    db, _, closes = trending_market(tmp_path, drift=0.004, noise=0.005)
    cfg = make_cfg(db, ["A"])
    from cta import data as dm
    _, _, cdf = dm.load_universe(cfg.db_path, cfg.symbols, cfg.timeframe_min)
    arr = cdf.to_numpy(float)
    t = len(arr) - 1
    cm = ex.CostModel(cfg.fee_rate, cfg.slip_rate, cfg.min_notional_usd)
    a = decision.plan_orders(cfg, arr, t, {"A": 0.0}, 1000.0, 1.0, cm)
    b = decision.plan_orders(cfg, arr, t, {"A": 0.0}, 1000.0, 1.0, cm)
    assert [(o.symbol, o.qty) for o in a] == [(o.symbol, o.qty) for o in b]
    assert len(a) >= 1


# --- ガード⑤⑥: 実発注しない既定 ----------------------------------------

def test_dry_run_never_places_orders(tmp_path):
    fx = FakeExecutor()
    tr, now, _ = _mk(tmp_path, fx, enable_live=False)
    r = tr.run_once(refresh=False, now=now)
    assert fx.placed == []
    assert r["mode"] == "dry_run"
    assert r["n_planned"] >= 1        # 注文は計画されるが発注されない


def test_live_places_orders(tmp_path):
    # テスト用ユニバースは1銘柄・max_gross=3.0なので単一注文が3倍相当になる。
    # 実運用(7銘柄・逆vol配分)では起きない構成なのでガード④を緩めて検証する。
    fx = FakeExecutor()
    tr, now, _ = _mk(tmp_path, fx, enable_live=True, max_order_pct_of_equity=5.0)
    r = tr.run_once(refresh=False, now=now)
    assert len(fx.placed) >= 1
    assert r["mode"] == "live"


# --- ガード②: 通常時の不一致は停止 --------------------------------------

def test_mismatch_halts_new_orders(tmp_path):
    fx = FakeExecutor(positions={"A": 5.0})       # 取引所には5.0ある
    tr, now, _ = _mk(tmp_path, fx, enable_live=True)
    # 内部帳簿には0.0と記録された状態を作る
    json.dump({"peak": 1000.0, "halted": False, "last_bar": 0,
               "mismatch_halt": False, "positions": {"A": 0.0}},
              open(tr.state_path, "w"))
    tr._load_state()
    r = tr.run_once(refresh=False, now=now)
    assert r["note"] == "mismatch_halt"
    assert fx.placed == []                        # 新規発注していない
    assert "A" in r["mismatch"]


# --- ★最重要★ 緊急クローズは不一致でも断行 -------------------------------

def test_emergency_close_proceeds_despite_mismatch(tmp_path):
    """ブレーカー作動時は照合不一致があっても取引所の実数量で決済する。

    ここで停止してしまうと『損失を止めるためのブレーカーが、止まったせいで
    損失を垂れ流す』本末転倒になる（2026-08-13のユーザー指摘で設計変更）。"""
    fx = FakeExecutor(positions={"A": 7.0}, equity=100.0)  # 実際は7.0保有
    tr, now, _ = _mk(tmp_path, fx, enable_live=True)
    # 内部帳簿はズレており(0.0)、かつブレーカー作動済みの状態
    json.dump({"peak": 1000.0, "halted": True, "last_bar": 0,
               "mismatch_halt": False, "positions": {"A": 0.0}},
              open(tr.state_path, "w"))
    tr._load_state()
    r = tr.run_once(refresh=False, now=now)

    assert r["halted"] is True
    assert r["note"] == "circuit_breaker_flatten"
    assert len(fx.placed) == 1
    # 内部帳簿の0ではなく、取引所の実数量7.0を打ち消す注文が出ている
    assert fx.placed[0].qty == pytest.approx(-7.0)
    assert fx.placed[0].reason == "circuit_breaker"


def test_emergency_close_alerts_on_failure(tmp_path, monkeypatch):
    sent = {}
    monkeypatch.setattr("cta.live_trader.send_alert",
                        lambda s, b: sent.update(subject=s, body=b) or True)
    fx = FakeExecutor(positions={"A": 3.0})
    fx.raise_on_place = RuntimeError("exchange down")
    tr, now, _ = _mk(tmp_path, fx, enable_live=True)
    json.dump({"peak": 1000.0, "halted": True, "last_bar": 0,
               "mismatch_halt": False, "positions": {"A": 3.0}},
              open(tr.state_path, "w"))
    tr._load_state()
    r = tr.run_once(refresh=False, now=now)
    assert r["errors"]
    assert "緊急クローズ" in sent.get("subject", "")


# --- ガード①④: 資金上限・単発上限 ---------------------------------------

def test_capital_guard_blocks_absurd_equity(tmp_path):
    fx = FakeExecutor(equity=100_000.0)          # 想定の何倍もある
    tr, now, _ = _mk(tmp_path, fx, enable_live=True, max_live_capital_usd=1000.0)
    with pytest.raises(Exception):
        tr.run_once(refresh=False, now=now)
    assert fx.placed == []


def test_order_size_guard(tmp_path):
    """単位バグ等で桁が外れた注文を弾く（既定は equity の1.5倍超で拒否）。"""
    fx = FakeExecutor()
    tr, now, _ = _mk(tmp_path, fx, enable_live=True)
    ok = ex.Order("A", qty=10.0, signal_price=100.0)    # $1,000 = equity 1.0倍
    tr._check_order(ok, 100.0, equity=1000.0)           # 通る
    bad = ex.Order("A", qty=1000.0, signal_price=100.0)  # $100,000 = 100倍
    with pytest.raises(LiveGuardError):
        tr._check_order(bad, 100.0, equity=1000.0)


# --- ガード③: 余力不足 --------------------------------------------------

def test_no_margin_skips_orders(tmp_path, monkeypatch):
    monkeypatch.setattr("cta.live_trader.send_alert", lambda s, b: True)
    fx = FakeExecutor(available=0.0)
    tr, now, _ = _mk(tmp_path, fx, enable_live=True)
    r = tr.run_once(refresh=False, now=now)
    assert r.get("note") == "no_margin"
    assert fx.placed == []


# --- 冪等性 -------------------------------------------------------------

def test_dry_run_does_not_block_subsequent_live_run(tmp_path):
    """ドライランは状態を書き換えず、直後の実発注を妨げないこと。

    【2026-08-15、実発注開始の直前に発覚】ドライランが last_bar を進めて
    しまい、続けて実行した実発注が「処理済みバー」としてスキップされた。
    検証のための実行が本番の発注を止めてしまう設計上の不具合だった。"""
    db, _, closes = trending_market(tmp_path, drift=0.004, noise=0.005)
    cfg = make_cfg(db, ["A"])
    now = T0 + len(closes) * STEP + 60

    fx_dry = FakeExecutor()
    dry = LiveTrader(cfg, fx_dry, base_dir=str(tmp_path), enable_live=False,
                     max_order_pct_of_equity=5.0)
    r_dry = dry.run_once(refresh=False, now=now)
    assert fx_dry.placed == []
    assert r_dry["mode"] == "dry_run"

    # 同じバーで実発注 → スキップされず発注されること
    fx_live = FakeExecutor()
    live = LiveTrader(cfg, fx_live, base_dir=str(tmp_path), enable_live=True,
                      max_order_pct_of_equity=5.0)
    r_live = live.run_once(refresh=False, now=now)
    assert "skipped" not in r_live, "ドライランが実発注を妨げている"
    assert len(fx_live.placed) >= 1


def test_same_bar_not_reprocessed(tmp_path):
    fx = FakeExecutor()
    tr, now, _ = _mk(tmp_path, fx, enable_live=True)
    tr.run_once(refresh=False, now=now)
    n1 = len(fx.placed)
    tr2 = LiveTrader(tr.cfg, fx, base_dir=str(tmp_path), enable_live=True)
    r2 = tr2.run_once(refresh=False, now=now)
    assert "skipped" in r2
    assert len(fx.placed) == n1                  # 二重発注していない
