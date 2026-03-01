#!/usr/bin/env python3
"""
Bybit vs Bitget 価格比較テスト (簡易版)

最新データを直接APIから取得して価格差を分析します。
"""

import os
import sys
import ccxt
import time
from datetime import datetime

# src/ ディレクトリを sys.path に追加
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from config import Config


def format_timestamp(ts_ms):
    """ミリ秒タイムスタンプを読みやすい形式に変換"""
    return datetime.fromtimestamp(ts_ms / 1000).strftime('%Y-%m-%d %H:%M:%S')


def main():
    print("=" * 80)
    print("🔍 Bybit vs Bitget 価格比較テスト (BTC/USDT 4時間足)")
    print("=" * 80)
    print()
    
    # ccxt取引所インスタンス作成（APIキー不要、公開APIのみ使用）
    print("📡 取引所に接続中...")
    
    bybit = ccxt.bybit({
        'enableRateLimit': True,
    })
    
    bitget = ccxt.bitget({
        'enableRateLimit': True,
    })
    
    print("✅ 接続完了\n")
    
    # 最新50本の4時間足データを取得
    symbol = 'BTC/USDT:USDT'  # Bybit無期限先物
    symbol_bitget = 'BTC/USDT'  # Bitget現物
    timeframe = '4h'
    limit = 50
    
    print(f"📊 取得設定:")
    print(f"   シンボル: {symbol} (Bybit), {symbol_bitget} (Bitget)")
    print(f"   時間足: 4時間")
    print(f"   取得数: 最新{limit}本")
    print()
    
    # Bybitからデータ取得
    print("📊 Bybitからデータ取得中...")
    try:
        bybit_ohlcv = bybit.fetch_ohlcv(symbol, timeframe, limit=limit)
        print(f"✅ Bybit: {len(bybit_ohlcv)} 件のデータを取得")
    except Exception as e:
        print(f"❌ Bybitデータ取得エラー: {e}")
        return
    
    # Bitgetからデータ取得
    print("📊 Bitgetからデータ取得中...")
    try:
        bitget_ohlcv = bitget.fetch_ohlcv(symbol_bitget, timeframe, limit=limit)
        print(f"✅ Bitget: {len(bitget_ohlcv)} 件のデータを取得")
    except Exception as e:
        print(f"❌ Bitgetデータ取得エラー: {e}")
        return
    
    print()
    
    # データを辞書に変換（タイムスタンプをキーに）
    bybit_dict = {ohlcv[0]: ohlcv for ohlcv in bybit_ohlcv}
    bitget_dict = {ohlcv[0]: ohlcv for ohlcv in bitget_ohlcv}
    
    # 共通の時刻を抽出
    common_times = sorted(set(bybit_dict.keys()) & set(bitget_dict.keys()))
    
    if not common_times:
        print("❌ 共通する時刻のデータが見つかりませんでした")
        return
    
    print(f"📈 分析対象: {len(common_times)} 件の共通データ")
    print()
    
    # サンプルデータ表示
    print("=" * 80)
    print("📋 データサンプル比較 (最新3件)")
    print("=" * 80)
    print()
    
    for i, ts in enumerate(sorted(common_times, reverse=True)[:3]):
        bybit_data = bybit_dict[ts]
        bitget_data = bitget_dict[ts]
        
        # [timestamp, open, high, low, close, volume]
        print(f"【{i+1}件目】")
        print(f"  時刻: {format_timestamp(ts)}")
        print(f"  Bybit  - Open: {bybit_data[1]:>9.2f}, High: {bybit_data[2]:>9.2f}, Low: {bybit_data[3]:>9.2f}, Close: {bybit_data[4]:>9.2f}")
        print(f"  Bitget - Open: {bitget_data[1]:>9.2f}, High: {bitget_data[2]:>9.2f}, Low: {bitget_data[3]:>9.2f}, Close: {bitget_data[4]:>9.2f}")
        print(f"  差分   - Open: {bybit_data[1] - bitget_data[1]:>9.2f}, High: {bybit_data[2] - bitget_data[2]:>9.2f}, Low: {bybit_data[3] - bitget_data[3]:>9.2f}, Close: {bybit_data[4] - bitget_data[4]:>9.2f}")
        print()
    
    # 統計情報計算
    print("=" * 80)
    print("📈 価格差の統計情報 (全{} 件)".format(len(common_times)))
    print("=" * 80)
    print()
    
    differences = {'open': [], 'high': [], 'low': [], 'close': []}
    
    for ts in common_times:
        bybit_data = bybit_dict[ts]
        bitget_data = bitget_dict[ts]
        
        differences['open'].append(bybit_data[1] - bitget_data[1])
        differences['high'].append(bybit_data[2] - bitget_data[2])
        differences['low'].append(bybit_data[3] - bitget_data[3])
        differences['close'].append(bybit_data[4] - bitget_data[4])
    
    for price_type in ['open', 'high', 'low', 'close']:
        diffs = differences[price_type]
        mean_diff = sum(diffs) / len(diffs)
        max_diff = max(diffs)
        min_diff = min(diffs)
        abs_mean_diff = sum(abs(d) for d in diffs) / len(diffs)
        abs_max_diff = max(abs(d) for d in diffs)
        
        print(f"{price_type.upper()}価格:")
        print(f"  平均差:         {mean_diff:>9.2f} USD")
        print(f"  最大差:         {max_diff:>9.2f} USD")
        print(f"  最小差:         {min_diff:>9.2f} USD")
        print(f"  絶対値平均差:   {abs_mean_diff:>9.2f} USD")
        print(f"  絶対値最大差:   {abs_max_diff:>9.2f} USD")
        print()
    
    # 価格差の割合計算（CLOSE価格ベース）
    print("=" * 80)
    print("📊 価格差の割合 (CLOSE価格ベース)")
    print("=" * 80)
    print()
    
    percentage_diffs = []
    for ts in common_times:
        bybit_close = bybit_dict[ts][4]
        bitget_close = bitget_dict[ts][4]
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
    print(f"Bybit  Close: {bybit_at_max[4]:.2f} USD")
    print(f"Bitget Close: {bitget_at_max[4]:.2f} USD")
    print(f"差分:         {bybit_at_max[4] - bitget_at_max[4]:.2f} USD ({((bybit_at_max[4] - bitget_at_max[4]) / bitget_at_max[4] * 100):.4f}%)")
    
    print("\n" + "=" * 80)
    print("✅ 分析完了")
    print("=" * 80)
    print()
    print("📝 注意:")
    print("   - Bybit: 無期限先物 (BTC/USDT:USDT)")
    print("   - Bitget: 現物 (BTC/USDT)")
    print("   - 商品タイプが異なるため、若干の価格差は正常です")


if __name__ == "__main__":
    main()
