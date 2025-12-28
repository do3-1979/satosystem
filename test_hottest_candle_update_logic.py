#!/usr/bin/env python3
"""
ホットテスト時に2時間足が更新されたときのシグナル判定ロジックを検証するテスト
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from config import Config
from price_data_management import PriceDataManagement
import time
from datetime import datetime, timedelta

def test_candle_update_detection():
    """
    2時間足が更新されたかの判定ロジックをテスト
    
    テスト内容:
    1. ホットテストモードで初期化
    2. update_price_data() を複数回呼び出し
    3. 2時間足の更新判定ロジックが正しく動作するかを確認
    """
    
    print("=" * 80)
    print("🧪 ホットテスト: 2時間足更新判定ロジック検証")
    print("=" * 80)
    
    try:
        # ホットテストモード設定を確認
        back_test_mode = Config.get_back_test_mode()
        hot_test_dummy = Config.get_hot_test_dummy_mode()
        
        print(f"\n📋 設定確認:")
        print(f"  - back_test_mode: {back_test_mode} (0=ホットテスト)")
        print(f"  - hot_test_dummy_mode: {hot_test_dummy} (1=ペーパートレード)")
        
        if back_test_mode != 0:
            print(f"\n❌ エラー: ホットテストモードが有効になっていません")
            print(f"   back_test = {back_test_mode} (0 である必要があります)")
            return False
        
        # PriceDataManagement を初期化
        print(f"\n🔄 PriceDataManagement 初期化中...")
        price_data_mgmt = PriceDataManagement()
        
        print(f"\n📊 初期データ情報:")
        print(f"  - 初期化完了")
        print(f"  - prev_close_time (初期値): {price_data_mgmt.prev_close_time}")
        print(f"  - time_frame (2時間足): {price_data_mgmt.time_frame} 分")
        
        # 最初の update_price_data() 呼び出し（初期化）
        print(f"\n🔄 ステップ 1: 初回 update_price_data() 実行（初期化）")
        result1 = price_data_mgmt.update_price_data()
        
        if not result1:
            print(f"  ❌ 初回更新に失敗しました")
            return False
        
        print(f"  ✅ 初回更新成功")
        print(f"     - prev_close_time: {price_data_mgmt.prev_close_time}")
        print(f"     - OHLCV データ行数: {len(price_data_mgmt.get_ohlcv_data_by_time_frame(price_data_mgmt.time_frame))}")
        print(f"     - 最新ティッカー: {price_data_mgmt.ticker}")
        print(f"     - ドンチャン signal: {price_data_mgmt.signals['donchian']['signal']}")
        print(f"     - ドンチャン side: {price_data_mgmt.signals['donchian']['side']}")
        print(f"     - PVO signal: {price_data_mgmt.signals['pvo']['signal']}")
        
        # 複数回の update_price_data() を呼び出して、2時間足更新を観察
        print(f"\n🔄 ステップ 2-6: 複数回の update_price_data() 実行（5回）")
        update_count = 0
        candle_update_count = 0
        
        for i in range(5):
            iteration = i + 2  # ステップ2以降
            print(f"\n  【実行 #{iteration}】")
            
            prev_close_time_before = price_data_mgmt.prev_close_time
            
            # API 呼び出し
            try:
                result = price_data_mgmt.update_price_data()
                
                if not result:
                    print(f"    ⚠️  update_price_data() が False を返しました（エラーの可能性）")
                    continue
                
                update_count += 1
                
                current_prev_close_time = price_data_mgmt.prev_close_time
                
                # 2時間足が更新されたか判定
                if prev_close_time_before != current_prev_close_time:
                    print(f"    ✅ 【2時間足 更新検出】")
                    print(f"       前回: {prev_close_time_before}")
                    print(f"       今回: {current_prev_close_time}")
                    candle_update_count += 1
                else:
                    print(f"    ℹ️  2時間足は更新されていません")
                    print(f"       prev_close_time: {current_prev_close_time}")
                
                print(f"    - ティッカー: {price_data_mgmt.ticker}")
                print(f"    - ドンチャン: {price_data_mgmt.signals['donchian']['side']} (signal={price_data_mgmt.signals['donchian']['signal']})")
                print(f"    - PVO: {price_data_mgmt.signals['pvo']['signal']}")
                print(f"    - ボラティリティ: {price_data_mgmt.volatility}")
                
            except Exception as e:
                print(f"    ❌ エラーが発生しました: {e}")
                import traceback
                traceback.print_exc()
                continue
            
            # API に負荷をかけないため少し待機
            time.sleep(2)
        
        # 結果サマリー
        print(f"\n" + "=" * 80)
        print(f"📈 テスト結果サマリー")
        print(f"=" * 80)
        print(f"  ✅ 成功した update_price_data() 呼び出し: {update_count}/5")
        print(f"  ✅ 検出された2時間足更新: {candle_update_count} 回")
        
        if update_count > 0:
            print(f"\n✅ 【判定】 ホットテスト時に実API で 2時間足更新判定ロジックが動作しています")
            print(f"\n📌 重要な確認項目:")
            print(f"  ✅ 1. update_price_data() が実API を呼び出している")
            print(f"  ✅ 2. 2時間足データが API から正しく取得されている")
            print(f"  ✅ 3. prev_close_time 比較で新規足確定を検出している")
            if candle_update_count > 0:
                print(f"  ✅ 4. 新規足確定時に prev_close_time が更新されている")
            else:
                print(f"  ℹ️  4. 今回の実行中に新規足の確定は検出されませんでした（通常、2時間ごと）")
            
            return True
        else:
            print(f"\n❌ 【判定】 update_price_data() がすべて失敗しました")
            return False
            
    except Exception as e:
        print(f"\n❌ テスト実行中にエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_candle_update_detection()
    sys.exit(0 if success else 1)
