"""
CTA / Managed-Futures プロトタイプ（分散トレンド + ボラティリティ・ターゲティング）

設計原則（旧戦略の失敗を踏まえた）:
- 複数資産でトレンドを取り、単一相場(2024Q4)依存を構造的に排除
- 各資産を逆ボラでサイズ配分し、ポートフォリオ全体のボラを一定目標に制御 → DD抑制
- 低頻度リバランスでコストを抑制（旧戦略は slip 0.12% で破綻）
- 最小パラメータ・経済的合理性のあるトレンド信号（複数ホライズンのMA交差の平均）
- 最初から現実コスト + 2023年=真OOS を分離報告

これは独立した vectorized バックテスト（本体bot.pyとは別）。研究用。
"""
import sqlite3, numpy as np, datetime as dt, sys

BARS_PER_YEAR = 6 * 365   # 4H足
DB = '/home/satoshi/work/satosystem/ohlcv_data/ohlcv_cache.db'

def load(sym):
    con = sqlite3.connect(DB); cur = con.cursor()
    cur.execute("""SELECT close_time, close_price FROM candles
                   WHERE symbol=? AND time_frame=240 ORDER BY close_time""", (sym,))
    r = cur.fetchall(); con.close()
    t = np.array([x[0] for x in r]); c = np.array([x[1] for x in r], float)
    return t, c

def align(series):
    """list of (t,c) -> common timestamps, matrix of closes [T x N]"""
    common = None
    for t, c in series:
        common = t if common is None else np.intersect1d(common, t)
    closes = []
    for t, c in series:
        idx = {tt: i for i, tt in enumerate(t)}
        closes.append(np.array([c[idx[x]] for x in common]))
    return common, np.column_stack(closes)

def ewma(x, span):
    a = 2.0 / (span + 1.0); out = np.empty_like(x); out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = a * x[i] + (1 - a) * out[i-1]
    return out

def trend_signal(close, horizons_bars):
    """複数ホライズンのEWMA交差の符号を平均 → [-1,1]。経済的根拠: time-series momentum."""
    sig = np.zeros(len(close))
    for (f, s) in horizons_bars:
        ef = ewma(close, f); es = ewma(close, s)
        sig += np.sign(ef - es)
    return sig / len(horizons_bars)

def realized_vol(rets, window):
    """trailing 年率ボラ（各時点、過去window本）"""
    T = len(rets); vol = np.full(T, np.nan)
    for i in range(window, T):
        vol[i] = rets[i-window:i].std() * np.sqrt(BARS_PER_YEAR)
    return vol

def backtest(symbols, start=None, end=None,
             horizons_days=((10, 40), (30, 120), (60, 240)),
             vol_window_days=30, target_vol=0.20, max_gross=3.0,
             rebalance_days=1, cost_rate=0.0011, init_capital=100.0,
             funding_annual=0.0, verbose=True):
    series = [load(s) for s in symbols]
    times, closes = align(series)   # times[T], closes[T,N]
    T, N = closes.shape
    logc = np.log(closes)
    rets = np.vstack([np.zeros((1, N)), np.diff(logc, axis=0)])  # [T,N] simple log returns per bar

    # signals & vols per asset
    bpd = 6  # bars/day
    horizons = [(int(f*bpd), int(s*bpd)) for (f, s) in horizons_days]
    sig = np.column_stack([trend_signal(logc[:, j], horizons) for j in range(N)])
    vol = np.column_stack([realized_vol(rets[:, j], vol_window_days*bpd) for j in range(N)])

    reb = max(1, rebalance_days*bpd)
    w = np.zeros((T, N)); cur_w = np.zeros(N)
    warmup = max(max(h) for h in horizons) + vol_window_days*bpd + 2

    for t in range(T):
        if t >= warmup and (t % reb == 0):
            v = np.where(np.isfinite(vol[t]) & (vol[t] > 1e-6), vol[t], np.nan)
            raw = sig[t] / v                      # inverse-vol scaled signal
            raw = np.nan_to_num(raw, nan=0.0)
            # ex-ante portfolio vol scaling (assume diagonal cov; low corr asset set)
            port_var = np.sum((raw * v)**2)
            scale = (target_vol / np.sqrt(port_var)) if port_var > 1e-12 else 0.0
            tw = raw * scale
            gross = np.sum(np.abs(tw))
            if gross > max_gross:
                tw *= max_gross / gross
            cur_w = tw
        w[t] = cur_w

    # PnL: prior-bar weights applied to this-bar returns (no look-ahead)
    wprev = np.vstack([np.zeros((1, N)), w[:-1]])
    gross_ret = np.sum(wprev * rets, axis=1)
    turnover = np.sum(np.abs(w - wprev), axis=1)
    cost = turnover * cost_rate
    # funding/holding cost: gross notional exposure pays funding per bar (conservative: all legs pay)
    gross_expo = np.sum(np.abs(wprev), axis=1)
    funding_cost = gross_expo * (funding_annual / BARS_PER_YEAR)
    net = gross_ret - cost - funding_cost

    # date mask
    def epoch(dstr):
        return int(dt.datetime.strptime(dstr, "%Y-%m-%d").timestamp())
    mask = np.ones(T, bool)
    if start: mask &= (times >= epoch(start))
    if end:   mask &= (times <= epoch(end))
    # ensure warmup before masked region is used for signals (signals already computed on full history)
    idx = np.where(mask)[0]
    idx = idx[idx >= warmup]
    if len(idx) == 0:
        print("no data in range"); return None

    eq = init_capital * np.cumprod(1 + net[idx])
    total_pnl = eq[-1] - init_capital
    # metrics
    nr = net[idx]
    ann_ret = (eq[-1]/init_capital) ** (BARS_PER_YEAR/len(nr)) - 1
    sharpe = (nr.mean()/nr.std()*np.sqrt(BARS_PER_YEAR)) if nr.std() > 0 else 0
    peak = np.maximum.accumulate(eq); dd = (peak - eq)/peak
    maxdd = dd.max()*100
    avg_gross = np.mean(np.sum(np.abs(w[idx]), axis=1))
    yrs = len(nr)/BARS_PER_YEAR
    n_trades = int((turnover[idx] > 1e-6).sum())

    if verbose:
        def f(ts): return dt.datetime.utcfromtimestamp(ts).strftime('%Y-%m-%d')
        print(f"  期間 {f(times[idx[0]])}..{f(times[idx[-1]])} ({yrs:.2f}y)  assets={symbols}")
        print(f"  PnL=${total_pnl:.0f}  ann={ann_ret*100:.1f}%  Sharpe={sharpe:.2f}  MaxDD={maxdd:.1f}%  "
              f"avgGross={avg_gross:.2f}x  rebTurns={n_trades}")
    return dict(total_pnl=total_pnl, ann_ret=ann_ret, sharpe=sharpe, maxdd=maxdd,
                eq=eq, idx=idx, times=times)

if __name__ == "__main__":
    syms = ['BTC/USDT:USDT', 'XAUT/USDT:USDT']
    print("=== FULL 2023-02-01 .. 2026-06-28 (BTC+XAUT, vol-target 20%, reb daily, cost 0.11%) ===")
    backtest(syms, '2023-02-01', '2026-06-28')
    print("=== 2023 (true OOS) ===");      backtest(syms, '2023-02-01', '2023-12-31')
    print("=== 2024 ===");                 backtest(syms, '2024-01-01', '2024-12-31')
    print("=== 2025 ===");                 backtest(syms, '2025-01-01', '2025-12-31')
    print("=== 2026 H1 (recent) ===");     backtest(syms, '2026-01-01', '2026-06-28')
    print("\n=== BTC-only (no diversification, same engine) ===")
    backtest(['BTC/USDT:USDT'], '2023-02-01', '2026-06-28')
    print("=== XAUT-only ===")
    backtest(['XAUT/USDT:USDT'], '2023-02-01', '2026-06-28')
