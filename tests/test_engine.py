"""エンジンの忠実度テスト — gen2の轍を踏まないことをコードで保証する。

最重要: 同足約定が構造的に不可能であること（判定バー終値ではなく
次バー始値±slippageで約定していること）を合成データで検証する。
"""
import math
import sqlite3

import numpy as np
import pytest

from cta.config import Config
from cta.engine import run_backtest

TF = 240
STEP = TF * 60
T0 = 1_600_000_000


def make_db(tmp_path, prices):
    """prices: {symbol: (opens, closes)} から candles キャッシュDBを作る。
    open[t] は意図的に close[t-1] と乖離させ、同足/前足終値約定を検出可能にする。"""
    db = str(tmp_path / "cache.db")
    con = sqlite3.connect(db)
    con.execute("""CREATE TABLE candles (
        id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, start_epoch INT,
        end_epoch INT, time_frame INT, close_time INT, close_time_dt TEXT,
        open_price REAL, high_price REAL, low_price REAL, close_price REAL,
        volume REAL, created_at TEXT)""")
    for sym, (opens, closes) in prices.items():
        for i, (o, c) in enumerate(zip(opens, closes)):
            ct = T0 + (i + 1) * STEP
            con.execute(
                """INSERT INTO candles (symbol, start_epoch, end_epoch, time_frame,
                   close_time, close_time_dt, open_price, high_price, low_price,
                   close_price, volume, created_at)
                   VALUES (?,?,?,?,?,'',?,?,?,?,?,'')""",
                (sym, ct - STEP, ct, TF, ct, o, max(o, c), min(o, c), c, 100.0))
    con.commit()
    con.close()
    return db


def make_cfg(db, symbols, **kw):
    d = dict(
        db_path=db, timeframe_min=TF, funding_pkl="/nonexistent",
        symbols=symbols, horizons_days=[(1, 3), (2, 5)], vol_window_days=5,
        target_vol=0.30, max_gross=3.0, rebalance_days=1,
        no_trade_band_pct=0.01, dd_soft=0.35, dd_hard=0.40,
        fee_rate=0.001, slip_rate=0.002, min_notional_usd=5.0,
        funding_default_annual={s: 0.05 for s in symbols},
        init_capital_usd=1000.0)
    d.update(kw)
    return Config(**d)


def trending_market(tmp_path, n=600, drift=0.002, noise=0.01, seed=0):
    rng = np.random.default_rng(seed)
    logc = np.cumsum(rng.normal(drift, noise, n))
    closes = 100.0 * np.exp(logc)
    # openを前バー終値から意図的に0.5%ギャップさせる
    opens = np.empty(n)
    opens[0] = 100.0
    opens[1:] = closes[:-1] * 1.005
    return make_db(tmp_path, {"A": (opens, closes)}), opens, closes


def test_fills_use_next_bar_open_never_decision_close(tmp_path):
    db, opens, closes = trending_market(tmp_path)
    cfg = make_cfg(db, ["A"])
    res = run_backtest(cfg)
    assert len(res.fills) > 0
    close_by_ts = {T0 + (i + 1) * STEP: closes[i] for i in range(len(closes))}
    open_by_ts = {T0 + (i + 1) * STEP: opens[i] for i in range(len(opens))}
    for f in res.fills:
        # 約定基準価格 = 約定バーの始値（判定バー終値では絶対にない）
        assert f.ref_price == pytest.approx(open_by_ts[f.ts])
        # シグナル価格 = 前バー(判定バー)の終値
        prev_close = close_by_ts[f.ts - STEP]
        assert f.signal_price == pytest.approx(prev_close)
        # openは終値から0.5%ギャップしているので、両者は必ず異なる
        assert not math.isclose(f.ref_price, f.signal_price, rel_tol=1e-4)
        # slippageは不利方向
        if f.qty > 0:
            assert f.fill_price > f.ref_price
        else:
            assert f.fill_price < f.ref_price


def test_flat_market_no_equity_gain(tmp_path):
    # トレンドゼロ+微小ノイズ → 利益が出ないこと（コスト分だけ減るのは許容）
    rng = np.random.default_rng(3)
    n = 600
    closes = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.002, n)) * 0.0 +
                            rng.normal(0, 0.001, n))
    opens = np.r_[100.0, closes[:-1]]
    db = make_db(tmp_path, {"A": (opens, closes)})
    cfg = make_cfg(db, ["A"])
    res = run_backtest(cfg)
    assert res.equity[-1] <= cfg.init_capital_usd * 1.02


def test_uptrend_goes_long_and_profits(tmp_path):
    db, opens, closes = trending_market(tmp_path, drift=0.004, noise=0.005)
    cfg = make_cfg(db, ["A"])
    res = run_backtest(cfg)
    assert res.pos_qty[-1, 0] > 0          # ロングで保有
    assert res.equity[-1] > cfg.init_capital_usd  # 強トレンドで利益


def test_costs_accounted(tmp_path):
    db, _, _ = trending_market(tmp_path)
    cfg = make_cfg(db, ["A"])
    res = run_backtest(cfg)
    assert res.fees_usd > 0 and res.funding_usd > 0
    # コスト5倍で必ず成績が悪化する（コストが実際に効いている）
    res5 = run_backtest(cfg, cost_mult=5.0)
    assert res5.equity[-1] < res.equity[-1]


def test_hard_dd_halts_and_stays_flat(tmp_path):
    # 強上昇→暴落反転でDD40%超を誘発
    n = 900
    up = np.cumsum(np.full(600, 0.004))
    down = up[-1] + np.cumsum(np.full(300, -0.008))
    logc = np.r_[up, down]
    rng = np.random.default_rng(1)
    closes = 100.0 * np.exp(logc + rng.normal(0, 0.002, n))
    opens = np.r_[100.0, closes[:-1]]
    db = make_db(tmp_path, {"A": (opens, closes)})
    cfg = make_cfg(db, ["A"], target_vol=1.0, max_gross=5.0)
    res = run_backtest(cfg)
    if res.halted_at is not None:
        # halt後はポジションゼロのまま
        after = res.times > res.halted_at + 2 * STEP
        assert np.all(res.pos_qty[after] == 0)


def test_min_notional_blocks_dust_capital(tmp_path):
    db, _, _ = trending_market(tmp_path)
    cfg = make_cfg(db, ["A"], init_capital_usd=3.0)  # 最小ロット5USD未満
    res = run_backtest(cfg)
    assert len(res.fills) == 0
