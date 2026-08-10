"""ETF版CTAの回帰テスト。

最重要: 2026-07-18に暗号資産側で発覚した「未確定バーの永久固定」バグと
同じ轍を踏まないことをコードで保証する（cta/etf_data.py）。
ネットワークは使わない（yfinanceはモック）。
"""
import datetime as dt
import sqlite3

import numpy as np
import pandas as pd
import pytest

from cta import etf_data
from cta import strategy as st


# --- 未確定バー除外（最重要の回帰テスト） -----------------------------

def test_is_settled_rejects_todays_bar_during_market_hours():
    """まだ取引時間中のバーは確定扱いにしない。"""
    # 2026-08-10 の 12:00 UTC = 米国市場はまだ開いていない/取引中
    now = dt.datetime(2026, 8, 10, 12, 0, tzinfo=dt.timezone.utc)
    assert etf_data.is_settled('2026-08-07', now) is True   # 3日前は確定済み
    assert etf_data.is_settled('2026-08-10', now) is False  # 当日は未確定


def test_is_settled_accepts_bar_after_close():
    now = dt.datetime(2026, 8, 10, 23, 30, tzinfo=dt.timezone.utc)
    assert etf_data.is_settled('2026-08-10', now) is True


def _fake_yf(monkeypatch, frame):
    import types, sys
    mod = types.ModuleType('yfinance')
    mod.download = lambda *a, **kw: frame
    monkeypatch.setitem(sys.modules, 'yfinance', mod)


def test_unsettled_bar_is_not_cached(tmp_path, monkeypatch):
    """形成中バーがキャッシュに書き込まれないこと（永久固定バグの防止）。"""
    db = str(tmp_path / 'etf.db')
    idx = pd.to_datetime(['2026-08-06', '2026-08-07', '2026-08-10'])
    frame = pd.DataFrame({'Open': [10., 11., 12.], 'High': [10., 11., 12.],
                          'Low': [10., 11., 12.], 'Close': [10.5, 11.5, 99.9],
                          'Volume': [1, 1, 1]}, index=idx)
    _fake_yf(monkeypatch, frame)
    now = dt.datetime(2026, 8, 10, 12, 0, tzinfo=dt.timezone.utc)  # 8/10は取引中
    etf_data.fetch_and_cache(db, ['SPY'], now_utc=now)

    con = sqlite3.connect(db)
    rows = con.execute("SELECT bar_date, close_price FROM etf_bars ORDER BY bar_date").fetchall()
    con.close()
    assert [r[0] for r in rows] == ['2026-08-06', '2026-08-07']
    assert all(r[1] != 99.9 for r in rows)   # 未確定の99.9は入っていない


def test_provisional_value_gets_corrected_on_rerun(tmp_path, monkeypatch):
    """INSERT OR REPLACEなので、万一暫定値が入っても次回実行で修正される。

    cta/data.py（暗号資産側）の INSERT...WHERE NOT EXISTS はこれができず、
    誤った値が永久固定される設計上の弱点があった。"""
    db = str(tmp_path / 'etf.db')
    idx = pd.to_datetime(['2026-08-07'])
    _fake_yf(monkeypatch, pd.DataFrame(
        {'Open': [10.], 'High': [10.], 'Low': [10.], 'Close': [50.0], 'Volume': [1]},
        index=idx))
    now = dt.datetime(2026, 8, 10, 12, 0, tzinfo=dt.timezone.utc)
    etf_data.fetch_and_cache(db, ['SPY'], now_utc=now)

    # 同じ日付が別の(正しい)値で再取得された状況
    _fake_yf(monkeypatch, pd.DataFrame(
        {'Open': [10.], 'High': [10.], 'Low': [10.], 'Close': [77.7], 'Volume': [1]},
        index=idx))
    etf_data.fetch_and_cache(db, ['SPY'], now_utc=now)

    con = sqlite3.connect(db)
    rows = con.execute("SELECT close_price FROM etf_bars").fetchall()
    con.close()
    assert len(rows) == 1 and rows[0][0] == pytest.approx(77.7)  # 上書きされている


def test_load_universe_aligns_symbols(tmp_path, monkeypatch):
    db = str(tmp_path / 'etf.db')
    now = dt.datetime(2026, 8, 10, 23, 30, tzinfo=dt.timezone.utc)
    for sym, closes in [('SPY', [10., 11., 12.]), ('GLD', [20., 21., 22.])]:
        idx = pd.to_datetime(['2026-08-05', '2026-08-06', '2026-08-07'])
        _fake_yf(monkeypatch, pd.DataFrame(
            {'Open': closes, 'High': closes, 'Low': closes,
             'Close': closes, 'Volume': [1, 1, 1]}, index=idx))
        etf_data.fetch_and_cache(db, [sym], now_utc=now)
    times, opens, closes_df = etf_data.load_universe(db, ['SPY', 'GLD'])
    assert len(times) == 3
    assert list(closes_df.columns) == ['SPY', 'GLD']
    assert closes_df['GLD'].iloc[-1] == pytest.approx(22.0)


# --- long_only ------------------------------------------------------

def _weights(sig, long_only):
    rng = np.random.default_rng(0)
    N = len(sig)
    rets = rng.normal(0, 0.01, (400, N))
    vol = np.full(N, 0.16)
    return st.target_weights(np.array(sig), vol, rets, 0.15, 5.0, 252,
                             long_only=long_only)


def test_long_only_removes_short_positions():
    w = _weights([1.0, -1.0, 1.0, -1.0], long_only=True)
    assert (w >= 0).all()
    assert w[0] > 0 and w[2] > 0        # 上昇トレンドは保有
    assert w[1] == 0.0 and w[3] == 0.0  # 下降トレンドは現金化（ショートしない）


def test_long_short_keeps_shorts_by_default():
    w = _weights([1.0, -1.0, 1.0, -1.0], long_only=False)
    assert w[1] < 0 and w[3] < 0


def test_long_only_all_downtrend_is_flat():
    w = _weights([-1.0, -1.0, -1.0], long_only=True)
    assert (w == 0).all()   # 全銘柄が下降 → 全額現金


# --- config ---------------------------------------------------------

def test_etf_config_uses_trading_days_per_year(tmp_path):
    from cta.config import load_config
    cfg = load_config('config/etf.ini')
    assert cfg.market == 'etf'
    assert cfg.is_etf is True
    assert cfg.long_only is True
    # ETFは営業日ベース252日。暦日365日だとvol推定が約20%過大になる
    assert cfg.bars_per_year == 252


def test_crypto_config_unchanged(tmp_path):
    from cta.config import load_config
    cfg = load_config('config/default.ini')
    assert cfg.market == 'crypto'
    assert cfg.is_etf is False
    assert cfg.long_only is False          # 既存の暗号資産版は挙動不変
    assert cfg.bars_per_year == 6 * 365
