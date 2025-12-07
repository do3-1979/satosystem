"""
OHLCVデータのSQLiteキャッシュ管理モジュール

このモジュールはOHLCVデータをSQLiteデータベースに保存・読み込みします。
従来のJSONファイルベースのキャッシュをSQLiteで置き換えます。

Features:
    - SQLiteデータベースへの読み書き
    - キャッシュの初期化と確認
    - 時系列データの効率的なクエリ
"""

import sqlite3
import os
import json
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from logger import Logger


class OHLCVCache:
    """OHLCVデータをSQLiteで管理するクラス"""

    def __init__(self, cache_path: str = "ohlcv_data/ohlcv_cache.db"):
        """
        OHLCVCacheの初期化

        Args:
            cache_path: SQLiteデータベースのパス
        """
        self.cache_path = cache_path
        self.logger = Logger()
        
        # キャッシュディレクトリが存在しない場合は作成
        cache_dir = os.path.dirname(cache_path)
        if cache_dir and not os.path.exists(cache_dir):
            os.makedirs(cache_dir, exist_ok=True)
            self.logger.log(f"キャッシュディレクトリを作成: {cache_dir}")
        
        # データベース接続とテーブル初期化
        self._initialize_database()

    def _get_connection(self) -> sqlite3.Connection:
        """データベース接続を取得"""
        conn = sqlite3.connect(self.cache_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize_database(self) -> None:
        """データベースとテーブルを初期化"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # キャッシュテーブルを作成
        # 複合キー: (start_epoch, end_epoch, time_frame, close_time)でユニークにする
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS candles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_epoch INTEGER NOT NULL,
                end_epoch INTEGER NOT NULL,
                time_frame INTEGER NOT NULL,
                close_time REAL UNIQUE NOT NULL,
                close_time_dt TEXT NOT NULL,
                open_price REAL NOT NULL,
                high_price REAL NOT NULL,
                low_price REAL NOT NULL,
                close_price REAL NOT NULL,
                volume REAL NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # インデックスを作成
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_params 
            ON candles (start_epoch, end_epoch, time_frame)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_time 
            ON candles (close_time)
        """)
        
        conn.commit()
        conn.close()
        self.logger.log("OHLCVキャッシュテーブルを確認/初期化しました")

    def get_ohlcv_data(
        self,
        start_epoch: int,
        end_epoch: int,
        time_frame: int
    ) -> Optional[List[Dict]]:
        """
        指定されたパラメータでOHLCVデータをキャッシュから取得

        Args:
            start_epoch: 開始時刻（エポック秒）
            end_epoch: 終了時刻（エポック秒）
            time_frame: タイムフレーム（分）

        Returns:
            キャッシュされたOHLCVデータのリスト、またはNone（キャッシュなし）
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            """
            SELECT close_time, close_time_dt, open_price, high_price, 
                   low_price, close_price, volume 
            FROM candles 
            WHERE start_epoch = ? AND end_epoch = ? AND time_frame = ?
            ORDER BY close_time ASC
            """,
            (start_epoch, end_epoch, time_frame)
        )
        
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return None
        
        # Row オブジェクトを辞書に変換
        data = []
        for row in rows:
            data.append({
                "close_time": row["close_time"],
                "close_time_dt": row["close_time_dt"],
                "open_price": row["open_price"],
                "high_price": row["high_price"],
                "low_price": row["low_price"],
                "close_price": row["close_price"],
                "Volume": row["volume"]
            })
        
        self.logger.log(
            f"キャッシュから {len(data)} 件のOHLCVデータを取得 "
            f"(start_epoch={start_epoch}, end_epoch={end_epoch}, time_frame={time_frame})"
        )
        return data

    def save_ohlcv_data(
        self,
        ohlcv_list: List[Dict],
        start_epoch: int,
        end_epoch: int,
        time_frame: int
    ) -> bool:
        """
        OHLCVデータをキャッシュに保存

        Args:
            ohlcv_list: OHLCVデータのリスト
            start_epoch: 開始時刻（エポック秒）
            end_epoch: 終了時刻（エポック秒）
            time_frame: タイムフレーム（分）

        Returns:
            保存成功の可否
        """
        if not ohlcv_list:
            self.logger.log("保存するOHLCVデータが空です")
            return False
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # 既存データを削除
            cursor.execute(
                """
                DELETE FROM candles 
                WHERE start_epoch = ? AND end_epoch = ? AND time_frame = ?
                """,
                (start_epoch, end_epoch, time_frame)
            )
            
            # 新しいデータを挿入
            for candle in ohlcv_list:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO candles 
                    (start_epoch, end_epoch, time_frame, close_time, close_time_dt, 
                     open_price, high_price, low_price, close_price, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        start_epoch,
                        end_epoch,
                        time_frame,
                        candle["close_time"],
                        candle["close_time_dt"],
                        candle["open_price"],
                        candle["high_price"],
                        candle["low_price"],
                        candle["close_price"],
                        candle["Volume"]
                    )
                )
            
            conn.commit()
            self.logger.log(
                f"キャッシュに {len(ohlcv_list)} 件のOHLCVデータを保存 "
                f"(start_epoch={start_epoch}, end_epoch={end_epoch}, time_frame={time_frame})"
            )
            return True
        except Exception as e:
            self.logger.log_error(f"OHLCVデータ保存エラー: {str(e)}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def clear_cache(self) -> bool:
        """
        キャッシュを全削除

        Returns:
            削除成功の可否
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM candles")
            conn.commit()
            conn.close()
            self.logger.log("OHLCVキャッシュを全削除しました")
            return True
        except Exception as e:
            self.logger.log_error(f"キャッシュ削除エラー: {str(e)}")
            return False

    def get_cache_stats(self) -> Dict:
        """
        キャッシュ統計情報を取得

        Returns:
            キャッシュ統計情報の辞書
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) as total FROM candles")
        total = cursor.fetchone()["total"]
        
        cursor.execute(
            """
            SELECT DISTINCT start_epoch, end_epoch, time_frame 
            FROM candles 
            ORDER BY start_epoch DESC
            """
        )
        params = cursor.fetchall()
        
        conn.close()
        
        stats = {
            "total_records": total,
            "cached_params": [
                {
                    "start_epoch": p["start_epoch"],
                    "end_epoch": p["end_epoch"],
                    "time_frame": p["time_frame"]
                }
                for p in params
            ]
        }
        
        return stats

    def migrate_from_json(self, json_cache_dir: str = "ohlcv_data") -> bool:
        """
        JSONキャッシュファイルからSQLiteに移行

        Args:
            json_cache_dir: JSONキャッシュファイルのディレクトリ

        Returns:
            移行成功の可否
        """
        if not os.path.exists(json_cache_dir):
            self.logger.log(f"JSONキャッシュディレクトリが見つかりません: {json_cache_dir}")
            return False
        
        import glob
        
        # JSONファイルを探す（パターン: ohlcv_data_*.json）
        json_files = glob.glob(os.path.join(json_cache_dir, "ohlcv_data_*.json"))
        
        if not json_files:
            self.logger.log("移行するJSONキャッシュファイルが見つかりません")
            return False
        
        migrated_count = 0
        
        for json_file in json_files:
            try:
                # ファイル名からパラメータを抽出
                # パターン: ohlcv_data_{start_epoch}_{end_epoch}_{time_frame}.json
                filename = os.path.basename(json_file)
                parts = filename.replace("ohlcv_data_", "").replace(".json", "").split("_")
                
                if len(parts) != 3:
                    self.logger.log_error(f"ファイル名の形式が不正です: {filename}")
                    continue
                
                start_epoch = int(parts[0])
                end_epoch = int(parts[1])
                time_frame = int(parts[2])
                
                # JSONファイルを読み込み
                with open(json_file, "r") as f:
                    ohlcv_list = json.load(f)
                
                # SQLiteに保存
                if self.save_ohlcv_data(ohlcv_list, start_epoch, end_epoch, time_frame):
                    migrated_count += 1
                    self.logger.log(f"移行完了: {filename}")
            except Exception as e:
                self.logger.log_error(f"ファイル移行エラー ({json_file}): {str(e)}")
        
        self.logger.log(f"JSONからSQLiteへの移行が完了しました ({migrated_count}個のファイル)")
        return migrated_count > 0

    def dump_to_json(self, output_file: str) -> bool:
        """
        SQLiteキャッシュをJSONにダンプ（デバッグ用）

        Args:
            output_file: 出力JSONファイルパス

        Returns:
            ダンプ成功の可否
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                """
                SELECT start_epoch, end_epoch, time_frame, close_time, close_time_dt,
                       open_price, high_price, low_price, close_price, volume
                FROM candles
                ORDER BY start_epoch, end_epoch, time_frame, close_time
                """
            )
            
            rows = cursor.fetchall()
            conn.close()
            
            data = [
                {
                    "start_epoch": r["start_epoch"],
                    "end_epoch": r["end_epoch"],
                    "time_frame": r["time_frame"],
                    "close_time": r["close_time"],
                    "close_time_dt": r["close_time_dt"],
                    "open_price": r["open_price"],
                    "high_price": r["high_price"],
                    "low_price": r["low_price"],
                    "close_price": r["close_price"],
                    "volume": r["volume"]
                }
                for r in rows
            ]
            
            with open(output_file, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            self.logger.log(f"SQLiteキャッシュを {output_file} にダンプしました ({len(data)} 件)")
            return True
        except Exception as e:
            self.logger.log_error(f"ダンプエラー: {str(e)}")
            return False
