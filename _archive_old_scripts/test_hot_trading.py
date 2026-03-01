#!/usr/bin/env python3
"""
ホットテスト検証スクリプト

back_test = 1（バックテストモード）で、180秒間動作させて、
60秒周期の価格取得が正しく動作することを検証します。

使用方法:
  python test_hot_trading.py
"""

import sys
import os
import time
from datetime import datetime

# ワークスペースルートを sys.path に追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# src ディレクトリに移動（config.ini を読み込むため）
os.chdir(os.path.join(os.path.dirname(__file__), 'src'))

from config import Config
from bybit_exchange import BybitExchange


def test_hot_trading():
    """ホットテスト検証"""
    
    print("=" * 80)
    print("🔥 ホットテスト開始")
    print("=" * 80)
    
    # 設定確認
    back_test_mode = Config.get_back_test_mode()
    bot_operation_cycle = Config.get_bot_operation_cycle()
    
    print(f"\n📋 設定情報:")
    print(f"  - バックテストモード: {back_test_mode}")
    print(f"  - Bot操作周期: {bot_operation_cycle}秒")
    
    if back_test_mode != 1:
        print(f"❌ エラー: back_test = 1 である必要があります（現在: {back_test_mode}）")
        return False
    
    # BybitExchange初期化
    try:
        exchange = BybitExchange(Config.get_api_key(), Config.get_api_secret())
        print(f"\n✅ Exchange初期化完了（ダミーモード）")
    except Exception as e:
        print(f"❌ Exchange初期化失敗: {e}")
        return False
    
    # テスト実行時間（180秒）
    total_test_duration = 180
    price_fetch_cycle = 60  # 60秒周期
    expected_fetches = total_test_duration // price_fetch_cycle  # 3回予想
    
    print(f"\n📊 テスト計画:")
    print(f"  - 総実行時間: {total_test_duration}秒")
    print(f"  - 価格取得周期: {price_fetch_cycle}秒")
    print(f"  - 予想取得回数: {expected_fetches}回")
    
    # ホットテスト実行
    print(f"\n🚀 ホットテスト実行中...\n")
    
    start_time = time.time()
    fetch_count = 0
    fetch_times = []
    prices = []
    
    try:
        while True:
            elapsed = time.time() - start_time
            
            # 60秒周期で価格取得
            if elapsed >= fetch_count * price_fetch_cycle and fetch_count * price_fetch_cycle < total_test_duration:
                fetch_time = time.time()
                fetch_count += 1
                
                # 最新価格取得
                print(f"[{fetch_count}] 価格取得実行中... ({elapsed:.1f}秒経過)")
                
                try:
                    ohlcv_data = exchange.fetch_latest_ohlcv(120)
                    
                    if ohlcv_data:
                        entry = ohlcv_data[0]
                        close_price = entry['close_price']
                        close_time_dt = entry['close_time_dt']
                        
                        prices.append(close_price)
                        fetch_times.append(elapsed)
                        
                        print(f"    ✅ 価格取得成功")
                        print(f"    - 時刻: {close_time_dt}")
                        print(f"    - 終値: {close_price:.2f} USD")
                        print(f"    - 実経過時間: {elapsed:.2f}秒\n")
                    else:
                        print(f"    ❌ 価格データが空です\n")
                        return False
                        
                except Exception as e:
                    print(f"    ❌ 価格取得失敗: {e}\n")
                    return False
            
            # テスト完了判定
            if elapsed >= total_test_duration:
                break
            
            # CPU負荷軽減のため短く待機
            time.sleep(0.5)
    
    except KeyboardInterrupt:
        print("\n⚠️  ホットテストが中断されました")
        return False
    
    # テスト結果
    print("=" * 80)
    print("🎯 ホットテスト完了")
    print("=" * 80)
    
    # 検証
    print(f"\n📊 結果検証:")
    print(f"  - 実際の取得回数: {fetch_count}回")
    print(f"  - 予想取得回数: {expected_fetches}回")
    
    success = True
    
    if fetch_count == expected_fetches:
        print(f"  ✅ 取得回数が正確です")
    else:
        print(f"  ❌ 取得回数が不正です（期待: {expected_fetches}, 実際: {fetch_count}）")
        success = False
    
    # タイミング検証（±5秒の許容範囲）
    print(f"\n⏱️  タイミング検証:")
    timing_ok = True
    for i, fetch_time in enumerate(fetch_times):
        # 最初は0秒、その後60秒周期
        expected_time = i * price_fetch_cycle
        timing_error = abs(fetch_time - expected_time)
        margin = 5  # 5秒の許容範囲
        
        if timing_error <= margin:
            print(f"  [{i+1}] ✅ {fetch_time:.1f}秒（期待: {expected_time}秒, 誤差: {timing_error:.1f}秒）")
        else:
            print(f"  [{i+1}] ❌ {fetch_time:.1f}秒（期待: {expected_time}秒, 誤差: {timing_error:.1f}秒 > {margin}秒）")
            timing_ok = False
    
    if not timing_ok:
        success = False
    
    # 価格データ検証
    print(f"\n💰 価格データ検証:")
    print(f"  - 取得した価格数: {len(prices)}")
    for i, price in enumerate(prices):
        print(f"  [{i+1}] 価格: {price:.2f} USD")
    
    if len(prices) == expected_fetches:
        print(f"  ✅ すべての価格データが取得されました")
    else:
        print(f"  ❌ 価格データが不足しています（期待: {expected_fetches}, 実際: {len(prices)}）")
        success = False
    
    # 最終判定
    print(f"\n" + "=" * 80)
    if success:
        print("✅ ホットテスト成功: 60秒周期の価格取得が正しく動作しています")
    else:
        print("❌ ホットテスト失敗: いくつかの検証に失敗しました")
    print("=" * 80)
    
    return success


if __name__ == '__main__':
    success = test_hot_trading()
    sys.exit(0 if success else 1)
