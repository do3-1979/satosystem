"""戦略ロジックの回帰テスト。シグナル成熟度・volターゲティング・ブレーカーの仕様を固定する。"""
import numpy as np
import pytest

from cta import strategy as st

BPY = 6 * 365


def test_trend_signal_uptrend_is_long():
    x = np.linspace(0, 1.0, 500)  # 単調上昇のlog価格
    sig = st.trend_signal(x, [(5, 20), (10, 40)])
    assert sig[-1] == pytest.approx(1.0)


def test_trend_signal_immature_history_is_nan():
    # 有効データがslowスパン(40本)未満の間はNaN（上場直後に取引しない）
    x = np.concatenate([np.full(100, np.nan), np.linspace(0, 1.0, 200)])
    sig = st.trend_signal(x, [(5, 20), (10, 40)])
    assert np.isnan(sig[100 + 10])          # 上場10本後: まだ未成熟
    assert not np.isnan(sig[100 + 150])     # 150本後: 有効
    assert sig[100 + 150] == pytest.approx(1.0)


def test_trailing_vol_scale():
    rng = np.random.default_rng(0)
    daily_sigma = 0.02 / np.sqrt(6)  # 年率 ~2%*sqrt(365) ≈ 38%
    rets = rng.normal(0, daily_sigma, 5000)
    v = st.trailing_vol(rets, 500, BPY)
    expected = daily_sigma * np.sqrt(BPY)
    assert v[-1] == pytest.approx(expected, rel=0.15)


def test_target_weights_hits_target_vol():
    rng = np.random.default_rng(1)
    T, N = 1000, 3
    sigmas = np.array([0.01, 0.02, 0.005])
    rets = rng.normal(0, sigmas, (T, N))
    vol_t = sigmas * np.sqrt(BPY)
    sig_t = np.array([1.0, -1.0, 1.0])
    w = st.target_weights(sig_t, vol_t, rets, target_vol=0.20,
                          max_gross=10.0, bars_per_year=BPY)
    pvol = st.portfolio_vol(w, rets, BPY)
    assert pvol == pytest.approx(0.20, rel=0.05)
    assert w[0] > 0 and w[1] < 0 and w[2] > 0  # シグナル方向を維持


def test_target_weights_gross_cap():
    rng = np.random.default_rng(2)
    rets = rng.normal(0, 0.0001, (1000, 2))  # 超低vol → レバ要求が爆発
    vol_t = np.array([0.01, 0.01])
    w = st.target_weights(np.array([1.0, 1.0]), vol_t, rets,
                          target_vol=0.30, max_gross=3.0, bars_per_year=BPY)
    assert np.abs(w).sum() == pytest.approx(3.0)


def test_target_weights_no_signal_is_flat():
    rets = np.zeros((100, 2))
    w = st.target_weights(np.array([np.nan, 0.0]), np.array([0.5, 0.5]),
                          rets, 0.2, 3.0, BPY)
    assert (w == 0).all()


def test_circuit_breaker_soft_and_hard():
    cb = st.CircuitBreaker(dd_soft=0.35, dd_hard=0.40)
    assert cb.update(1000.0) == 1.0
    assert cb.update(700.0) == 1.0    # DD30%: 通常運転
    assert cb.update(640.0) == 0.5    # DD36%: デレバレッジ
    assert cb.update(590.0) == 0.0    # DD41%: 停止
    assert cb.halted
    assert cb.update(2000.0) == 0.0   # 回復してもhaltedは人手解除まで維持
