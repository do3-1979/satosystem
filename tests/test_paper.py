"""ペーパートレーダーの回帰テスト。

執行コードパスがバックテストと共有されていること（独自の約定式が無いこと）を
前提に、状態永続化・冪等性・killswitchを検証する。ネットワークは使わない。"""
import numpy as np
import pytest

from cta.paper import PaperTrader
from tests.test_engine import make_db, make_cfg, trending_market, T0, STEP


def _mk_trader(tmp_path, db, **kw):
    cfg = make_cfg(db, ["A"], **kw)
    return PaperTrader(cfg, base_dir=str(tmp_path)), cfg


def test_run_once_trades_uptrend_and_logs(tmp_path):
    db, opens, closes = trending_market(tmp_path, drift=0.004, noise=0.005)
    trader, cfg = _mk_trader(tmp_path, db)
    n = len(closes)
    now = T0 + n * STEP + 60  # 最終バー確定直後
    live_px = closes[-1] * 1.001
    r = trader.run_once(refresh=False, price_fn=lambda s: live_px, now=now)
    assert r["n_fills"] >= 1
    assert r["positions"]["A"] > 0  # 上昇トレンド → ロング
    # 取引ログにsignal/ref/fillの3価格が記録される
    lines = open(tmp_path / "state/paper_trades.csv").read().splitlines()
    assert "signal_price" in lines[0] and "signal_deviation_usd" in lines[0]
    row = lines[1].split(",")
    assert float(row[3]) != float(row[4])  # signal(バー終値) ≠ ref(live mid)


def test_run_once_idempotent_per_bar(tmp_path):
    db, _, closes = trending_market(tmp_path, drift=0.004, noise=0.005)
    trader, cfg = _mk_trader(tmp_path, db)
    now = T0 + len(closes) * STEP + 60
    trader.run_once(refresh=False, price_fn=lambda s: closes[-1], now=now)
    # 同じバーで再実行 → 二重執行しない（cron重複起動への耐性）
    trader2 = PaperTrader(cfg, base_dir=str(tmp_path))
    r2 = trader2.run_once(refresh=False, price_fn=lambda s: closes[-1], now=now)
    assert "skipped" in r2


def test_state_persists_across_instances(tmp_path):
    db, _, closes = trending_market(tmp_path, drift=0.004, noise=0.005)
    trader, cfg = _mk_trader(tmp_path, db)
    now = T0 + (len(closes) - 6) * STEP + 60
    r1 = trader.run_once(refresh=False, price_fn=lambda s: closes[-7], now=now)
    trader2 = PaperTrader(cfg, base_dir=str(tmp_path))
    assert trader2.pf.positions == r1["positions"]
    assert trader2.pf.cash_usd == trader.pf.cash_usd


def test_funding_is_charged_on_new_bar_for_held_position(tmp_path):
    """2026-07-18判明の重大な欠落の回帰テスト: paper.pyにはfunding計上が
    一切無く、backtest(cta/engine.py)で最大のコスト要因(funding>fee>slip)と
    されていたものが常にゼロ扱いになっていた。

    前バーから持ち越したポジションに対し、新バー検出時に必ず1回だけ
    fundingが課金されることを検証する（cta/execution.funding_cost_usdと
    同じ計算式・makeCfgのconservative年率5%を使用）。"""
    db, _, closes = trending_market(tmp_path, drift=0.004, noise=0.005)
    trader, cfg = _mk_trader(tmp_path, db)
    now1 = T0 + (len(closes) - 2) * STEP + 60
    r1 = trader.run_once(refresh=False, price_fn=lambda s: closes[-3], now=now1)
    assert r1["positions"]["A"] != 0.0  # ポジションを持った状態を作る
    cash_before = trader.pf.cash_usd
    held_qty = trader.pf.positions["A"]

    now2 = now1 + STEP  # 次のバー
    r2 = trader.run_once(refresh=False, price_fn=lambda s: closes[-3], now=now2)

    assert r2["funding_paid_usd"] > 0  # conservativeモードなので符号に関わらずコスト
    # 期待値: |held_qty| * price * annual_rate(0.05) / bars_per_year
    from cta import execution as ex
    price = closes[-2]
    expected = ex.funding_cost_usd(held_qty, price, 0.05 / cfg.bars_per_year,
                                   conservative=True)
    assert r2["funding_paid_usd"] == pytest.approx(expected, rel=1e-6)


def test_funding_not_double_charged_on_duplicate_cron_call(tmp_path):
    db, _, closes = trending_market(tmp_path, drift=0.004, noise=0.005)
    trader, cfg = _mk_trader(tmp_path, db)
    now = T0 + len(closes) * STEP + 60
    trader.run_once(refresh=False, price_fn=lambda s: closes[-1], now=now)
    cash_after_first = trader.pf.cash_usd

    trader2 = PaperTrader(cfg, base_dir=str(tmp_path))
    r2 = trader2.run_once(refresh=False, price_fn=lambda s: closes[-1], now=now)
    assert "skipped" in r2
    assert trader2.pf.cash_usd == cash_after_first  # funding再課金されていない


def test_killswitch_closes_all_and_stays_halted(tmp_path):
    db, _, closes = trending_market(tmp_path, drift=0.004, noise=0.005)
    trader, cfg = _mk_trader(tmp_path, db)
    now = T0 + len(closes) * STEP + 60
    trader.run_once(refresh=False, price_fn=lambda s: closes[-1], now=now)
    assert trader.pf.positions["A"] > 0
    # 大暴落でequityがhard DDを割る → 全クローズ + halt
    crash_px = closes[-1] * 0.01
    r = trader.run_once(refresh=False, price_fn=lambda s: crash_px,
                        now=now + STEP)
    assert r["halted"]
    assert all(q == 0 for q in trader.pf.positions.values())
    # halt状態は永続化され、回復しても再開しない
    trader3 = PaperTrader(cfg, base_dir=str(tmp_path))
    r3 = trader3.run_once(refresh=False, price_fn=lambda s: closes[-1],
                          now=now + 2 * STEP)
    assert r3["halted"] and r3["n_fills"] == 0
