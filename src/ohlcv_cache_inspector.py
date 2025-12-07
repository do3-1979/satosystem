#!/usr/bin/env python3
"""
OHLCVキャッシュ検査ツール

ohlcv_cache.db の内容を確認・管理するツール
- 取得しているデータ数
- 取得データ範囲（途中断絶がある場合は、断絶ごとの期間）
- キャッシュの詳細分析
"""

import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from tabulate import tabulate

try:
    from logger import Logger
    HAS_LOGGER = True
except ImportError:
    HAS_LOGGER = False


class OHLCVCacheInspector:
    """OHLCVキャッシュを検査・分析するクラス"""

    def __init__(self, cache_path: str = "ohlcv_data/ohlcv_cache.db"):
        """
        OHLCVCacheInspectorの初期化

        Args:
            cache_path: SQLiteデータベースのパス
        """
        self.cache_path = cache_path
        if HAS_LOGGER:
            self.logger = Logger()
        else:
            self.logger = None
        
        if not os.path.exists(cache_path):
            print(f"❌ キャッシュファイルが見つかりません: {cache_path}")
            raise FileNotFoundError(f"Cache file not found: {cache_path}")

    def _get_connection(self) -> sqlite3.Connection:
        """データベース接続を取得"""
        conn = sqlite3.connect(self.cache_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_total_records(self) -> int:
        """
        キャッシュ内の総レコード数を取得

        Returns:
            総レコード数
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as total FROM candles")
        total = cursor.fetchone()["total"]
        conn.close()
        return total

    def get_cache_parameters(self) -> List[Dict]:
        """
        キャッシュされているパラメータ（start_epoch, end_epoch, time_frame）の一覧を取得

        Returns:
            パラメータの辞書リスト
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            """
            SELECT DISTINCT start_epoch, end_epoch, time_frame, COUNT(*) as record_count
            FROM candles
            GROUP BY start_epoch, end_epoch, time_frame
            ORDER BY start_epoch DESC
            """
        )
        
        rows = cursor.fetchall()
        conn.close()
        
        params = []
        for row in rows:
            params.append({
                "start_epoch": row["start_epoch"],
                "end_epoch": row["end_epoch"],
                "time_frame": row["time_frame"],
                "record_count": row["record_count"],
                "start_dt": datetime.fromtimestamp(row["start_epoch"]).strftime('%Y-%m-%d %H:%M'),
                "end_dt": datetime.fromtimestamp(row["end_epoch"]).strftime('%Y-%m-%d %H:%M')
            })
        
        return params

    def get_data_coverage(self, start_epoch: int, end_epoch: int, time_frame: int) -> Dict:
        """
        指定されたパラメータでのデータ範囲とギャップ（断絶）を分析

        Args:
            start_epoch: 開始時刻（エポック秒）
            end_epoch: 終了時刻（エポック秒）
            time_frame: タイムフレーム（分）

        Returns:
            データ範囲と断絶情報の辞書
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 指定パラメータでのデータ取得
        cursor.execute(
            """
            SELECT close_time, close_time_dt
            FROM candles
            WHERE start_epoch = ? AND end_epoch = ? AND time_frame = ?
            ORDER BY close_time ASC
            """,
            (start_epoch, end_epoch, time_frame)
        )
        
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return {
                "record_count": 0,
                "segments": []
            }
        
        # データをセグメント（連続したデータ）に分割
        segments = []
        current_segment = {
            "start_time": rows[0]["close_time"],
            "start_dt": rows[0]["close_time_dt"],
            "end_time": rows[0]["close_time"],
            "end_dt": rows[0]["close_time_dt"],
            "count": 1
        }
        
        time_frame_seconds = time_frame * 60  # タイムフレームを秒に変換
        expected_gap = time_frame_seconds  # 期待される時間間隔
        
        for i in range(1, len(rows)):
            current_time = rows[i]["close_time"]
            prev_time = rows[i-1]["close_time"]
            time_gap = current_time - prev_time
            
            # ギャップが期待値より大きい場合、新しいセグメントを開始
            if time_gap > expected_gap * 1.5:  # 1.5倍のマージン
                # 現在のセグメントを終了
                current_segment["end_time"] = prev_time
                current_segment["end_dt"] = rows[i-1]["close_time_dt"]
                segments.append(current_segment)
                
                # 新しいセグメントを開始
                current_segment = {
                    "start_time": current_time,
                    "start_dt": rows[i]["close_time_dt"],
                    "end_time": current_time,
                    "end_dt": rows[i]["close_time_dt"],
                    "count": 1
                }
            else:
                current_segment["end_time"] = current_time
                current_segment["end_dt"] = rows[i]["close_time_dt"]
                current_segment["count"] += 1
        
        # 最後のセグメントを追加
        segments.append(current_segment)
        
        return {
            "record_count": len(rows),
            "segments": segments
        }

    def print_summary(self):
        """キャッシュの概要を表示"""
        total = self.get_total_records()
        params = self.get_cache_parameters()
        
        print("\n" + "="*80)
        print("🗄️  OHLCV キャッシュ検査ツール")
        print("="*80)
        print(f"\n📊 総レコード数: {total:,} 件")
        print(f"📁 キャッシュファイル: {self.cache_path}")
        
        if os.path.exists(self.cache_path):
            cache_size = os.path.getsize(self.cache_path) / (1024 * 1024)  # MB
            print(f"💾 ファイルサイズ: {cache_size:.2f} MB")
        
        print(f"\n📋 キャッシュされているパラメータ数: {len(params)}")
        
        if params:
            print("\n参数一覧:")
            print("-" * 80)
            
            table_data = []
            for p in params:
                table_data.append([
                    p["time_frame"],
                    p["record_count"],
                    p["start_dt"],
                    p["end_dt"]
                ])
            
            headers = ["タイムフレーム\n(分)", "レコード数", "取得開始", "取得終了"]
            print(tabulate(table_data, headers=headers, tablefmt="grid"))

    def print_data_coverage(self, start_epoch: int = None, end_epoch: int = None, time_frame: int = None):
        """
        データ範囲と断絶を表示

        Args:
            start_epoch: 開始時刻（エポック秒）。Noneの場合は最初のパラメータを使用
            end_epoch: 終了時刻（エポック秒）。Noneの場合は最初のパラメータを使用
            time_frame: タイムフレーム（分）。Noneの場合は最初のパラメータを使用
        """
        params = self.get_cache_parameters()
        
        if not params:
            print("\n❌ キャッシュにデータがありません")
            return
        
        # パラメータが指定されていない場合は、最初のパラメータを使用
        if start_epoch is None or end_epoch is None or time_frame is None:
            p = params[0]
            start_epoch = p["start_epoch"]
            end_epoch = p["end_epoch"]
            time_frame = p["time_frame"]
        
        coverage = self.get_data_coverage(start_epoch, end_epoch, time_frame)
        
        print("\n" + "="*80)
        print(f"📈 データ範囲分析")
        print("="*80)
        print(f"\n🔍 パラメータ:")
        print(f"   - start_epoch: {start_epoch} ({datetime.fromtimestamp(start_epoch).strftime('%Y-%m-%d %H:%M')})")
        print(f"   - end_epoch: {end_epoch} ({datetime.fromtimestamp(end_epoch).strftime('%Y-%m-%d %H:%M')})")
        print(f"   - time_frame: {time_frame} 分")
        
        print(f"\n📊 データセグメント数: {len(coverage['segments'])} 個")
        print(f"📝 総レコード数: {coverage['record_count']:,} 件")
        
        if coverage["segments"]:
            print("\n📍 セグメント詳細:")
            print("-" * 80)
            
            table_data = []
            for i, seg in enumerate(coverage["segments"], 1):
                duration_seconds = seg["end_time"] - seg["start_time"]
                duration_hours = duration_seconds / 3600
                
                table_data.append([
                    i,
                    seg["start_dt"],
                    seg["end_dt"],
                    seg["count"],
                    f"{duration_hours:.1f}h"
                ])
            
            headers = ["No.", "開始時刻", "終了時刻", "レコード数", "期間"]
            print(tabulate(table_data, headers=headers, tablefmt="grid"))
            
            # ギャップがある場合は表示
            if len(coverage["segments"]) > 1:
                print("\n⚠️  データギャップ:")
                print("-" * 80)
                
                gap_data = []
                for i in range(1, len(coverage["segments"])):
                    prev_end = coverage["segments"][i-1]["end_time"]
                    curr_start = coverage["segments"][i]["start_time"]
                    gap_seconds = curr_start - prev_end
                    gap_hours = gap_seconds / 3600
                    gap_days = gap_seconds / (3600 * 24)
                    
                    gap_data.append([
                        i,
                        datetime.fromtimestamp(prev_end).strftime('%Y-%m-%d %H:%M'),
                        datetime.fromtimestamp(curr_start).strftime('%Y-%m-%d %H:%M'),
                        f"{gap_hours:.1f}h" if gap_days < 1 else f"{gap_days:.1f}日"
                    ])
                
                gap_headers = ["No.", "ギャップ前", "ギャップ後", "ギャップ期間"]
                print(tabulate(gap_data, headers=gap_headers, tablefmt="grid"))

    def print_detailed_analysis(self):
        """すべてのパラメータについて詳細分析を表示"""
        params = self.get_cache_parameters()
        
        print("\n" + "="*80)
        print("🔬 詳細分析: すべてのパラメータ")
        print("="*80)
        
        for p in params:
            print(f"\n【 タイムフレーム: {p['time_frame']} 分 】")
            self.print_data_coverage(p["start_epoch"], p["end_epoch"], p["time_frame"])


def main():
    """メイン処理"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="OHLCVキャッシュ検査ツール",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
例:
  python ohlcv_cache_inspector.py --summary
  python ohlcv_cache_inspector.py --coverage
  python ohlcv_cache_inspector.py --all
  python ohlcv_cache_inspector.py --coverage --start 1234567890 --end 1234567990 --timeframe 1
        """
    )
    
    parser.add_argument(
        "--summary",
        action="store_true",
        help="キャッシュの概要を表示"
    )
    
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="データ範囲と断絶を表示（最初のパラメータに対して）"
    )
    
    parser.add_argument(
        "--all",
        action="store_true",
        help="すべてのパラメータについて詳細分析を表示"
    )
    
    parser.add_argument(
        "--start",
        type=int,
        help="開始時刻（エポック秒）"
    )
    
    parser.add_argument(
        "--end",
        type=int,
        help="終了時刻（エポック秒）"
    )
    
    parser.add_argument(
        "--timeframe",
        type=int,
        help="タイムフレーム（分）"
    )
    
    parser.add_argument(
        "--cache",
        default="ohlcv_data/ohlcv_cache.db",
        help="キャッシュファイルのパス (デフォルト: ohlcv_data/ohlcv_cache.db)"
    )
    
    args = parser.parse_args()
    
    try:
        inspector = OHLCVCacheInspector(args.cache)
        
        # デフォルト動作: サマリーを表示
        if not (args.summary or args.coverage or args.all):
            inspector.print_summary()
        else:
            if args.summary:
                inspector.print_summary()
            if args.coverage:
                inspector.print_data_coverage(args.start, args.end, args.timeframe)
            if args.all:
                inspector.print_detailed_analysis()
    
    except FileNotFoundError as e:
        print(f"❌ エラー: {e}")
        exit(1)
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        exit(1)


if __name__ == "__main__":
    main()
