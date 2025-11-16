import os
import sqlite3
from typing import List, Dict, Tuple
from datetime import datetime


class OHLCVCache:
    """
    シンボル・タイムフレーム単位でローソク足を永続化し、
    任意期間のデータ抽出と不足分のみの取得を可能にする軽量キャッシュ。

    - ストレージ: SQLite (標準ライブラリのみ使用)
    - 一意制約: (symbol, timeframe, close_time)
    - 時刻は epoch 秒（close_time）。timeframe は分
    """

    def __init__(self, db_path: str = "ohlcv_data/ohlcv_cache.db") -> None:
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=NORMAL;")
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        cur = self._conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS candles (
                symbol TEXT NOT NULL,
                timeframe INTEGER NOT NULL,
                close_time INTEGER NOT NULL,
                open_price REAL NOT NULL,
                high_price REAL NOT NULL,
                low_price REAL NOT NULL,
                close_price REAL NOT NULL,
                volume REAL NOT NULL,
                PRIMARY KEY (symbol, timeframe, close_time)
            )
            """
        )
        self._conn.commit()

    def upsert_candles(self, symbol: str, timeframe: int, candles: List[Dict]) -> None:
        if not candles:
            return
        rows = [
            (
                symbol,
                timeframe,
                int(c["close_time"]),
                float(c["open_price"]),
                float(c["high_price"]),
                float(c["low_price"]),
                float(c["close_price"]),
                float(c["Volume"]),
            )
            for c in candles
        ]
        cur = self._conn.cursor()
        cur.executemany(
            """
            INSERT INTO candles
            (symbol, timeframe, close_time, open_price, high_price, low_price, close_price, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol, timeframe, close_time) DO UPDATE SET
                open_price=excluded.open_price,
                high_price=excluded.high_price,
                low_price=excluded.low_price,
                close_price=excluded.close_price,
                volume=excluded.volume
            """,
            rows,
        )
        self._conn.commit()

    def get_range(self, symbol: str, timeframe: int, start_epoch: int, end_epoch: int) -> List[Dict]:
        cur = self._conn.cursor()
        cur.execute(
            """
            SELECT close_time, open_price, high_price, low_price, close_price, volume
              FROM candles
             WHERE symbol = ? AND timeframe = ?
               AND close_time >= ? AND close_time < ?
             ORDER BY close_time ASC
            """,
            (symbol, timeframe, int(start_epoch), int(end_epoch)),
        )
        rows = cur.fetchall()
        result = []
        for ct, op, hp, lp, cp, vol in rows:
            result.append(
                {
                    "close_time": int(ct),
                    "close_time_dt": datetime.fromtimestamp(int(ct)).strftime("%Y/%m/%d %H:%M"),
                    "open_price": float(op),
                    "high_price": float(hp),
                    "low_price": float(lp),
                    "close_price": float(cp),
                    "Volume": float(vol),
                }
            )
        return result

    def range_stats(self, symbol: str, timeframe: int, start_epoch: int, end_epoch: int) -> Tuple[int, int, int]:
        """範囲内の件数と最小/最大のclose_timeを返す。該当が無ければ (0, -1, -1)。"""
        cur = self._conn.cursor()
        cur.execute(
            """
            SELECT COUNT(*), MIN(close_time), MAX(close_time)
              FROM candles
             WHERE symbol = ? AND timeframe = ?
               AND close_time >= ? AND close_time < ?
            """,
            (symbol, timeframe, int(start_epoch), int(end_epoch)),
        )
        cnt, mn, mx = cur.fetchone()
        if cnt is None:
            return 0, -1, -1
        return int(cnt), (int(mn) if mn is not None else -1), (int(mx) if mx is not None else -1)

    def has_sufficient_cache(self, symbol: str, timeframe: int, start_epoch: int, end_epoch: int) -> bool:
        count, mn, mx = self.range_stats(symbol, timeframe, start_epoch, end_epoch)
        if count <= 0:
            return False
        step = timeframe * 60
        expected = max(0, int((end_epoch - start_epoch) // step))
        # 許容誤差: 2 本まで（端数やAPIの切上げ/切下げ差異を吸収）
        return count >= max(0, expected - 2)

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass
