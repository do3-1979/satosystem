#!/usr/bin/env python3
"""
Bybit vs Bitget 価格比較テスト

8日間分の4時間足BTC/USDTデータを両取引所から取得し、価格差を分析します。
"""

import os
import sys
from datetime import datetime, timedelta
import time

# src/ ディレクトリを sys.path に追加
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from bybit_exchange import BybitExchange
from bitget_exchange import BitgetExchange
from config import Config


def format_timestamp(epoch):
    """エポックタイムを読みやすい形式に変換"""
    return datetime.fromtimestamp(epoch).strftime('%Y-%m-%d %H:%M:%S')


def calculate_statistics(bybit_data, bitget_data):
    """価格差の統計情報を計算"""
    if not bybit_data or not bitget_data:
        return None
    
    # 共通の時刻でマッチング
    bybit_dict = {d['real_time']: d for d in bybit_data}
    bitget_dict = {d['real_time']: d for d in bitget_data}
    
    common_times = sorted(set(bybit_dict.keys()) & set(bitget_dict.keys()))
    
    if not common_times:
        print("⚠️  共通する時刻のデータが見つかりません")
        return None
    
    differences = {
        'open': [],
        'high': [],
        'low': [],
        'close': [],
        'timestamps': []
    }
    
    for t in common_times:
        bybit = bybit_dict[t]
        bitget = bitget_dict[t]
        
        differences['open'].append(bybit['open_price'] - bitget['open_price'])
        differences['high'].append(bybit['high_price'] - bitget['high_price'])
        differences['low'].append(bybit['low_price'] - bitget['low_price'])
        differences['close'].append(bybit['close_price'] - bitget['close_price'])
        differences['timestamps'].append(t)
    
    stats = {}
    for price_type in ['open', 'high', 'low', 'close']:
        diffs = differences[price_type]
        stats[price_type] = {
            'mean': sum(diffs) / len(diffs),
            'max': max(diffs),
            'min': min(diffs),
            'abs_mean': sum(abs(d) for d in diffs) / len(diffs),
            'abs_max': max(abs(d) for d in diffs)
        }
    
    return stats, differences, common_times


def main():
    print("=" * 80)
    print("🔍 Bybit vs Bitget 価格比較テスト (BTC/USDT 4時間足)")
    print("=" * 80)
    print()
    
    # 設定読み込み
    try:
        bybit_key = Config.get_bybit_api_key()
        bybit_secret = Config.get_bybit_api_secret()
        bitget_key = Config.get_bitget_api_key()
        bitget_secret = Config.get_bitget_api_secret()
        bitget_passphrase = Config.get_bitget_api_passphrase()
    except Exception as e:
        print(f"❌ 設定読み込みエラー: {e}")
        return
    
    # 取引所インスタンス作成
    print("📡 取引所に接続中...")
    print("   (初回は市場情報のロードに30秒程度かかる場合があります)")
    bybit = BybitExchange(bybit_key, bybit_secret)
    bitget = BitgetExchange(bitget_key, bitget_secret, bitget_passphrase)
    print("✅ 接続完了\n")
    
    # 期間設定（現在から5日前まで、4時間足）
    # Bitgetは約8日分のデータを提供するが、安全のため5日分に設定
    end_time = int(time.time())
    start_time = end_time - (5 * 24 * 60 * 60)  # 5日前
    time_frame = 240  # 4時間 = 240分
    
    print(f"📅 取得期間:")
    print(f"   開始: {format_timestamp(start_time)}")
    print(f"   終了: {format_timestamp(end_time)}")
    print(f"   時間足: 4時間 (240分)")
    print()
    
    # Bybitからデータ取得
    print("📊 Bybitから最新データ取得中...")
    try:
        bybit_data = bybit.fetch_latest_ohlcv(time_frame)
        print(f"✅ Bybit: {len(bybit_data)} 件のデータを取得")
    except Exception as e:
        print(f"❌ Bybitデータ取得エラー: {e}")
        bybit_data = []
    
    # Bitgetからデータ取得
    print("📊 Bitgetから最新データ取得中...")
    try:
        bitget_data = bitget.fetch_latest_ohlcv(time_frame)
        print(f"✅ Bitget: {len(bitget_data)} 件のデータを取得")
    except Exception as e:
        print(f"❌ Bitgetデータ取得エラー: {e}")
        bitget_data = []
    
    print()
    
    if not bybit_data or not bitget_data:
        print("❌ データが取得できませんでした")
        return
    
    # データサンプル表示
    print("=" * 80)
    print("📋 データサンプル比較 (最初の3件)")
    print("=" * 80)
    print()
    
    for i in range(min(3, len(bybit_data), len(bitget_data))):
        bybit_item = bybit_data[i]
        bitget_item = bitget_data[i]
        
        print(f"【{i+1}件目】")
        print(f"  時刻: {format_timestamp(bybit_item['real_time'])}")
        print(f"  Bybit  - Open: {bybit_item['open_price']:>8.2f}, High: {bybit_item['high_price']:>8.2f}, Low: {bybit_item['low_price']:>8.2f}, Close: {bybit_item['close_price']:>8.2f}")
        print(f"  Bitget - Open: {bitget_item['open_price']:>8.2f}, High: {bitget_item['high_price']:>8.2f}, Low: {bitget_item['low_price']:>8.2f}, Close: {bitget_item['close_price']:>8.2f}")
        print(f"  差分   - Open: {bybit_item['open_price'] - bitget_item['open_price']:>8.2f}, High: {bybit_item['high_price'] - bitget_item['high_price']:>8.2f}, Low: {bybit_item['low_price'] - bitget_item['low_price']:>8.2f}, Close: {bybit_item['close_price'] - bitget_item['close_price']:>8.2f}")
        print()
    
    # 統計情報計算
    print("=" * 80)
    print("📈 価格差の統計情報")
    print("=" * 80)
    print()
    
    result = calculate_statistics(bybit_data, bitget_data)
    
    if result is None:
        print("❌ 統計情報を計算できませんでした")
        return
    
    stats, differences, common_times = result
    
    print(f"分析対象: {len(common_times)} 件のデータ")
    print()
    
    print("価格差 (Bybit - Bitget):")
    print("-" * 80)
    
    for price_type in ['open', 'high', 'low', 'close']:
        s = stats[price_type]
        print(f"\n{price_type.upper()}価格:")
        print(f"  平均差:         {s['mean']:>8.2f} USD")
        print(f"  最大差:         {s['max']:>8.2f} USD")
        print(f"  最小差:         {s['min']:>8.2f} USD")
        print(f"  絶対値平均差:   {s['abs_mean']:>8.2f} USD")
        print(f"  絶対値最大差:   {s['abs_max']:>8.2f} USD")
    
    # 価格差の割合計算（CLOSE価格ベース）
    print("\n" + "=" * 80)
    print("📊 価格差の割合 (CLOSE価格ベース)")
    print("=" * 80)
    print()
    
    bybit_dict = {d['real_time']: d for d in bybit_data}
    bitget_dict = {d['real_time']: d for d in bitget_data}
    
    percentage_diffs = []
    for t in common_times:
        bybit_close = bybit_dict[t]['close_price']
        bitget_close = bitget_dict[t]['close_price']
        pct_diff = ((bybit_close - bitget_close) / bitget_close) * 100
        percentage_diffs.append(pct_diff)
    
    avg_pct = sum(percentage_diffs) / len(percentage_diffs)
    max_pct = max(percentage_diffs)
    min_pct = min(percentage_diffs)
    abs_avg_pct = sum(abs(p) for p in percentage_diffs) / len(percentage_diffs)
    
    print(f"平均差:       {avg_pct:>8.4f} %")
    print(f"最大差:       {max_pct:>8.4f} %")
    print(f"最小差:       {min_pct:>8.4f} %")
    print(f"絶対値平均差: {abs_avg_pct:>8.4f} %")
    
    # 最大価格差の時刻を表示
    print("\n" + "=" * 80)
    print("🔎 最大価格差が発生した時刻")
    print("=" * 80)
    print()
    
    max_diff_idx = differences['close'].index(max(differences['close'], key=abs))
    max_diff_time = common_times[max_diff_idx]
    
    bybit_at_max = bybit_dict[max_diff_time]
    bitget_at_max = bitget_dict[max_diff_time]
    
    print(f"時刻: {format_timestamp(max_diff_time)}")
    print(f"Bybit  Close: {bybit_at_max['close_price']:.2f} USD")
    print(f"Bitget Close: {bitget_at_max['close_price']:.2f} USD")
    print(f"差分:         {bybit_at_max['close_price'] - bitget_at_max['close_price']:.2f} USD ({((bybit_at_max['close_price'] - bitget_at_max['close_price']) / bitget_at_max['close_price'] * 100):.4f}%)")
    
    print("\n" + "=" * 80)
    print("✅ 分析完了")
    print("=" * 80)


if __name__ == "__main__":
    main()
