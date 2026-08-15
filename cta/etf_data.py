"""ETF（米国上場）の日足データ層。yfinance経由でSQLiteにキャッシュする。

cta/data.py（暗号資産・4H足・ccxt）と同じインターフェース（load_universe）を
提供し、strategy/engine をそのまま共有できるようにする。

【最重要】2026-07-18に発覚した重大バグと同じ轍を踏まないための原則:
  - yfinanceは「当日まだ取引時間中のバー」も返す。これを確定値として
    キャッシュすると、後から真の終値で上書きされず永久に誤った値が固定される。
  - よって「最終取引日が終了していることが確実な日」までしか書き込まない。
  - 書き込みは INSERT OR REPLACE（上書き可能）にして、万一暫定値が入っても
    次回実行で正しい値に修正されるようにする（cta/data.pyの
    INSERT...WHERE NOT EXISTS はこの点が弱かった）。
"""
import datetime as dt
import os
import sqlite3
import time

import numpy as np
import pandas as pd

from . import jp_repair

SCHEMA = """
CREATE TABLE IF NOT EXISTS etf_bars (
    symbol TEXT NOT NULL,
    bar_date TEXT NOT NULL,          -- YYYY-MM-DD（取引日）
    open_price REAL, high_price REAL, low_price REAL, close_price REAL,
    volume REAL,
    updated_at TEXT,
    PRIMARY KEY (symbol, bar_date)
)
"""

# 米国東部時間で16:00に引け。UTCで概ね20:00〜21:00（夏時間で変動）。
# 安全側に倒し「UTCで当日23:00を過ぎた取引日」のみ確定とみなす。
SETTLED_HOUR_UTC = 23

# 東証は15:00 JST（06:00 UTC）に引ける。09:00 UTC（18:00 JST）を確定時刻とする。
#
# 【重要】米国用の23:00 UTCを東証にも使ってはいけない。
#   23:00 UTCは翌日08:00 JSTにあたるため、月曜の終値で判定できるのが
#   火曜の朝08:00になり、寄成注文（寄付板は08:00頃から受付）にほとんど
#   間に合わない。09:00 UTC（当日18:00 JST）にすれば、引け後2〜3時間で
#   判定し、翌朝の寄成注文を余裕をもって出せる。
#   これはバックテストの「判定=バー終値 / 約定=次足始値」とも整合する。
SETTLED_HOUR_UTC_JP = 9


def _connect(db_path):
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    con = sqlite3.connect(db_path)
    con.execute(SCHEMA)
    return con


def settled_hour_utc(symbol=None):
    """その銘柄の属する市場の「確定とみなす時刻」(UTC)。"""
    return SETTLED_HOUR_UTC_JP if jp_repair.is_jp_symbol(symbol) else SETTLED_HOUR_UTC


def is_settled(bar_date, now_utc=None, symbol=None):
    """その取引日のバーが確定済みか。当日中・未確定のバーを弾く唯一の判定。

    市場ごとに引け時刻が違うため symbol で切り替える。東証銘柄に米国用の
    23:00 UTC を適用すると判定が翌朝08:00 JSTまでずれ込み、寄成注文に
    間に合わなくなる（symbol未指定なら従来どおり米国基準）。
    """
    now = now_utc or dt.datetime.now(dt.timezone.utc)
    d = pd.Timestamp(bar_date).date()
    settled_at = dt.datetime(d.year, d.month, d.day, settled_hour_utc(symbol),
                             tzinfo=dt.timezone.utc)
    return now >= settled_at


def _repair_jp_frame(d, sym, log=None):
    """東証銘柄のOHLCを修復する（終値の修復係数をOHLC全体へ適用）。

    Yahooは日本銘柄の分割を記録し損ねるため、そのまま使うと偽の暴落になる。
    詳細と根拠は cta/jp_repair.py を参照。
    """
    fixed, notes = jp_repair.repair_close_series(d['Close'])
    if log is not None and notes:
        log.setdefault(sym, []).extend(notes)
    if len(fixed) == 0:
        return d.iloc[0:0]
    scale = (fixed / d['Close'].reindex(fixed.index)).replace(
        [np.inf, -np.inf], np.nan).fillna(1.0)
    out = d.loc[fixed.index].copy()
    for col in ('Open', 'High', 'Low', 'Close'):
        if col in out.columns:
            out[col] = out[col] * scale
    return out


def fetch_and_cache(db_path, symbols, start='2006-01-01', now_utc=None,
                    repair_log=None):
    """yfinanceから取得し、確定済みバーのみキャッシュへ書き込む。

    東証銘柄('.T')は書き込み前に必ず jp_repair を通す。分割調整漏れを
    そのまま保存すると、後から真値で上書きされず誤りが固定される。
    repair_log に dict を渡すと、適用した修復内容を symbol 別に受け取れる。
    """
    import yfinance as yf
    con = _connect(db_path)
    cur = con.cursor()
    inserted = 0
    for sym in symbols:
        try:
            d = yf.download(sym, start=start, progress=False,
                            auto_adjust=True, threads=False)
        except Exception:
            continue
        if d is None or len(d) == 0:
            continue
        if isinstance(d.columns, pd.MultiIndex):
            d.columns = d.columns.get_level_values(0)
        if jp_repair.is_jp_symbol(sym):
            d = _repair_jp_frame(d, sym, log=repair_log)
        for ts, row in d.iterrows():
            bar_date = pd.Timestamp(ts).strftime('%Y-%m-%d')
            if not is_settled(bar_date, now_utc, symbol=sym):
                # まだ確定していないバーは書き込まない（永久固定バグの防止）
                continue
            if pd.isna(row.get('Close')):
                continue
            cur.execute(
                """INSERT OR REPLACE INTO etf_bars
                   (symbol, bar_date, open_price, high_price, low_price,
                    close_price, volume, updated_at)
                   VALUES (?,?,?,?,?,?,?,datetime('now'))""",
                (sym, bar_date,
                 float(row.get('Open', np.nan)), float(row.get('High', np.nan)),
                 float(row.get('Low', np.nan)), float(row['Close']),
                 float(row.get('Volume', 0) or 0)))
            inserted += 1
        con.commit()
    con.close()
    return inserted


def load_universe(db_path, symbols):
    """キャッシュから読み出す。cta/data.load_universe と同じ戻り値の形。

    Returns: (times[T] epoch秒, opens DataFrame, closes DataFrame)
    """
    con = _connect(db_path)
    frames = {}
    for sym in symbols:
        df = pd.read_sql_query(
            """SELECT bar_date, open_price AS open, close_price AS close
               FROM etf_bars WHERE symbol=? ORDER BY bar_date""",
            con, params=(sym,))
        if df.empty:
            continue
        df['bar_date'] = pd.to_datetime(df['bar_date'])
        frames[sym] = df.set_index('bar_date')
    con.close()
    if not frames:
        raise ValueError("ETFキャッシュが空です。先に fetch_and_cache を実行してください")

    idx = None
    for df in frames.values():
        idx = df.index if idx is None else idx.union(df.index)
    idx = idx.sort_values()
    opens = pd.DataFrame({s: frames[s]['open'].reindex(idx) for s in frames})
    closes = pd.DataFrame({s: frames[s]['close'].reindex(idx) for s in frames})
    # pandasのバージョンで内部解像度が異なる（2.x=ns / 3.x=us）ため、
    # astype('int64')//10**9 では環境によって1000倍ずれる。
    # datetime64[s] に明示変換してから整数化することでバージョン非依存にする。
    # （2026-08-11のRPiデプロイ時に実際に発生したバグ）
    times = idx.to_numpy(dtype='datetime64[s]').astype('int64').astype(float)
    return times, opens, closes


def coverage(db_path):
    """キャッシュの状況を返す（運用時の健全性チェック用）。"""
    con = _connect(db_path)
    df = pd.read_sql_query(
        """SELECT symbol, COUNT(*) AS bars, MIN(bar_date) AS first,
                  MAX(bar_date) AS last FROM etf_bars GROUP BY symbol
           ORDER BY symbol""", con)
    con.close()
    return df
