"""OHLCVキャッシュ・funding履歴へのアクセス層。

原則: バックテストは必ずローカルキャッシュ経由（APIレート制限に触れない）。
追加取得はバックオフ付きでキャッシュへ追記する。
"""
import os
import pickle
import sqlite3
import time

import numpy as np
import pandas as pd


def load_ohlcv(db_path, symbol, timeframe_min):
    """キャッシュからOHLCVを読み、close_time(UTC epoch秒)インデックスのDataFrameで返す。"""
    con = sqlite3.connect(db_path)
    df = pd.read_sql_query(
        """SELECT close_time, open_price AS open, high_price AS high,
                  low_price AS low, close_price AS close, volume
           FROM candles WHERE symbol=? AND time_frame=?
           ORDER BY close_time""",
        con, params=(symbol, timeframe_min))
    con.close()
    df = df.drop_duplicates(subset="close_time").set_index("close_time")
    return df


def load_universe(db_path, symbols, timeframe_min):
    """全銘柄を共通の時間グリッド（union）に整列。上場前はNaN（weight 0扱い）。

    intersection でなく union を使うのは、後発上場資産（XAUT等）を含めつつ
    先発資産の弱気相場履歴（2021-2022）を捨てないため。"""
    frames = {}
    for s in symbols:
        df = load_ohlcv(db_path, s, timeframe_min)
        if df.empty:
            raise ValueError(f"no cached data for {s}")
        frames[s] = df
    idx = None
    for df in frames.values():
        idx = df.index if idx is None else idx.union(df.index)
    step = timeframe_min * 60
    # 欠損バーの多いグリッド穴は許容（NaNのまま扱う）
    out = {s: df.reindex(idx) for s, df in frames.items()}
    opens = pd.DataFrame({s: out[s]["open"] for s in symbols})
    closes = pd.DataFrame({s: out[s]["close"] for s in symbols})
    return idx.to_numpy(dtype=float), opens, closes


def load_funding(pkl_path, symbols, times, timeframe_min, default_annual):
    """バーごとのfundingレート行列 [T,N] を返す。

    実履歴（8h毎の(epoch, rate)）がある銘柄はバー区間 (t-tf, t] のレートを合算。
    無い銘柄はデフォルト年率をバーあたりに按分し、conservativeフラグを立てる。"""
    T, N = len(times), len(symbols)
    rates = np.zeros((T, N))
    conservative = np.zeros(N, dtype=bool)
    hist = {}
    if pkl_path and os.path.exists(pkl_path):
        with open(pkl_path, "rb") as f:
            hist = pickle.load(f)
    step = timeframe_min * 60
    bars_per_year = 365 * 24 * 60 // timeframe_min
    for j, sym in enumerate(symbols):
        h = hist.get(sym) or []
        if len(h) > 0:
            ep = np.array([x[0] for x in h])
            rt = np.array([x[1] for x in h])
            # 各バーに、そのバー区間で発生したfundingを割り当て
            pos = np.searchsorted(times, ep, side="left")
            for k, p in enumerate(pos):
                if 0 <= p < T and times[p] - step < ep[k] <= times[p]:
                    rates[p, j] += rt[k]
        else:
            rates[:, j] = default_annual.get(sym, 0.05) / bars_per_year
            conservative[j] = True
    return rates, conservative


def fetch_and_cache(db_path, symbol, timeframe_min, since_epoch, until_epoch,
                    exchange_id="bybit", max_retries=5):
    """バックオフ付きで取引所からOHLCVを取得しキャッシュへ追記する（追加銘柄/期間用）。"""
    import ccxt
    ex = getattr(ccxt, exchange_id)({"enableRateLimit": True})
    tf = {240: "4h", 60: "1h", 1440: "1d"}[timeframe_min]
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    since_ms = int(since_epoch * 1000)
    step_ms = timeframe_min * 60 * 1000
    inserted = 0
    while since_ms < until_epoch * 1000:
        for attempt in range(max_retries):
            try:
                batch = ex.fetch_ohlcv(symbol, tf, since=since_ms, limit=200)
                break
            except Exception:
                if attempt == max_retries - 1:
                    raise
                time.sleep(2 ** attempt)
        if not batch:
            break
        for o in batch:
            open_ms = o[0]
            close_time = open_ms // 1000 + timeframe_min * 60
            cur.execute(
                """INSERT INTO candles (symbol, start_epoch, end_epoch, time_frame,
                       close_time, close_time_dt, open_price, high_price, low_price,
                       close_price, volume, created_at)
                   SELECT ?,?,?,?,?,datetime(?, 'unixepoch'),?,?,?,?,?,datetime('now')
                   WHERE NOT EXISTS (SELECT 1 FROM candles
                       WHERE symbol=? AND time_frame=? AND close_time=?)""",
                (symbol, open_ms // 1000, close_time, timeframe_min, close_time,
                 close_time, o[1], o[2], o[3], o[4], o[5],
                 symbol, timeframe_min, close_time))
            inserted += cur.rowcount
        con.commit()
        since_ms = batch[-1][0] + step_ms
        if len(batch) < 2:
            break
    con.close()
    return inserted
