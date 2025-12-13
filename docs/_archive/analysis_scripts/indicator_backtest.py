#!/usr/bin/env python3
"""
Phase 2: 指標値単体検証（バックテスト）

新指標のみをバックテストして、期待値通りの計算値が出ているか確認。
ログに指標値を出力し、数値の妥当性を視覚的に検証する。

実行方法:
  python indicator_backtest.py [strategy_name] [output_csv]
  
  strategy_name: a (ADX), b (BB+RSI+SMA), c (combined)
  output_csv: 出力CSVファイルパス（デフォルト: indicator_results.csv）

例:
  python indicator_backtest.py b indicator_results_strategy_b.csv
"""

import sys
sys.path.insert(0, '/home/satoshi/work/satosystem/src')

from config import Config
from price_data_management import PriceDataManagement
from portfolio import Portfolio
from risk_management import RiskManagement
import csv
from datetime import datetime

def validate_indicators_for_strategy(strategy_name='a', output_csv='indicator_results.csv'):
    """
    指定されたStrategyの指標値を検証し、CSVに出力
    """
    print("=" * 70)
    print(f"Phase 2: 指標値単体検証 - Strategy {strategy_name.upper()}")
    print("=" * 70)
    
    # RiskManagementの初期化
    try:
        price_data_management = PriceDataManagement()
        portfolio = Portfolio()
        
        # バックテストモードの場合、OHLCVデータを初期化
        back_test_mode = Config.get_back_test_mode()
        print(f"✓ バックテストモード: {'ON' if back_test_mode == 1 else 'OFF'}")
        
        if back_test_mode == 1:
            price_data_management.initialise_back_test_ohlcv_data()
            price_data_management.update_price_data_backtest()
            print(f"✓ バックテストOHLCVデータを初期化・更新")
        
        risk_manager = RiskManagement(price_data_management, portfolio)
        
        print(f"✓ RiskManagement初期化成功")
        print(f"  - Strategy A (ADX): {'有効' if risk_manager.enable_strategy_a_adx else '無効'}")
        print(f"  - Strategy B (BB+RSI+SMA): {'有効' if risk_manager.enable_strategy_b_bb_rsi_sma else '無効'}")
        print(f"  - Strategy C (Combined): {'有効' if risk_manager.enable_strategy_c_combined else '無効'}")
        
    except Exception as e:
        print(f"❌ RiskManagement初期化失敗: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    # 使用するOHLCVデータ取得
    try:
        main_time_frame = Config.get_time_frame()
        ohlcv_data = price_data_management.get_ohlcv_data(main_time_frame)
        
        print(f"\n✓ OHLCV データ取得: {len(ohlcv_data)}キャンドル")
        if len(ohlcv_data) == 0:
            print(f"❌ エラー: OHLCVデータが取得できません")
            return False
        elif len(ohlcv_data) < 100:
            print(f"⚠️ 警告: データ量が少なめ（{len(ohlcv_data)}キャンドル）")
        
    except Exception as e:
        print(f"❌ OHLCVデータ取得失敗: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    # 指標値の履歴を格納
    results = []
    
    print(f"\n指標を計算中...")
    
    # バックテストモードの場合、最初の価格更新を実行
    try:
        if back_test_mode == 1:
            # 最初の価格データを更新
            is_end = price_data_management.update_price_data_backtest()
            print(f"✓ バックテスト最初の価格更新: 終了={is_end}")
    except Exception as e:
        print(f"⚠️ 価格データ更新警告: {str(e)}")
    
    try:
        if strategy_name.lower() == 'a':
            # Strategy A: ADX のみ検証
            result_a = risk_manager.evaluate_strategy_a_adx()
            
            print(f"\nStrategy A (ADX) 結果:")
            print(f"  Signal: {result_a.get('signal', 'N/A')}")
            print(f"  Bull: {result_a.get('bull', False)}")
            print(f"  Bear: {result_a.get('bear', False)}")
            print(f"  ADX Value: {result_a.get('adx', 0):.2f}")
            
            # ADX値の履歴出力
            if risk_manager.adx:
                print(f"\n  ADX 値の推移（最後の10キャンドル）:")
                for i, adx_val in enumerate(risk_manager.adx[-10:]):
                    print(f"    [{len(risk_manager.adx)-10+i}] {adx_val:.2f}")
            
            results.append({
                'timestamp': datetime.now().isoformat(),
                'strategy': 'A',
                'signal': result_a.get('signal', 'N/A'),
                'adx': result_a.get('adx', 0),
                'bull': result_a.get('bull', False),
                'bear': result_a.get('bear', False)
            })
            
        elif strategy_name.lower() == 'b':
            # Strategy B: BB + RSI + SMA 検証
            result_b = risk_manager.evaluate_strategy_b_bb_rsi_sma()
            
            print(f"\nStrategy B (BB+RSI+SMA) 結果:")
            print(f"  Signal: {result_b.get('signal', 'N/A')}")
            
            if 'bb' in result_b and result_b['bb']:
                bb = result_b['bb']
                print(f"  Bollinger Bands:")
                print(f"    Upper: {bb.get('upper', 0):.2f}")
                print(f"    Middle: {bb.get('middle', 0):.2f}")
                print(f"    Lower: {bb.get('lower', 0):.2f}")
                print(f"    Signal: {bb.get('signal', 'N/A')}")
            
            if 'rsi' in result_b and result_b['rsi']:
                rsi = result_b['rsi']
                print(f"  RSI:")
                print(f"    Value: {rsi.get('value', 0):.2f}")
                print(f"    Signal: {rsi.get('signal', 'N/A')}")
            
            if 'sma' in result_b and result_b['sma']:
                sma = result_b['sma']
                print(f"  SMA:")
                print(f"    Fast (50): {sma.get('fast', 0):.2f}")
                print(f"    Slow (200): {sma.get('slow', 0):.2f}")
                print(f"    Signal: {sma.get('signal', 'N/A')}")
            
            results.append({
                'timestamp': datetime.now().isoformat(),
                'strategy': 'B',
                'signal': result_b.get('signal', 'N/A'),
                'bb_upper': result_b.get('bb', {}).get('upper', 0),
                'bb_middle': result_b.get('bb', {}).get('middle', 0),
                'bb_lower': result_b.get('bb', {}).get('lower', 0),
                'rsi': result_b.get('rsi', {}).get('value', 0),
                'sma_fast': result_b.get('sma', {}).get('fast', 0),
                'sma_slow': result_b.get('sma', {}).get('slow', 0)
            })
            
        elif strategy_name.lower() == 'c':
            # Strategy C: 全指標統合検証
            result_c = risk_manager.evaluate_strategy_c_combined()
            
            print(f"\nStrategy C (Combined) 結果:")
            print(f"  Signal: {result_c.get('signal', 'N/A')}")
            
            if 'strategy_a' in result_c:
                print(f"  Strategy A Signal: {result_c['strategy_a'].get('signal', 'N/A')}")
            
            if 'strategy_b' in result_c:
                print(f"  Strategy B Signal: {result_c['strategy_b'].get('signal', 'N/A')}")
            
            results.append({
                'timestamp': datetime.now().isoformat(),
                'strategy': 'C',
                'signal': result_c.get('signal', 'N/A'),
                'strategy_a_signal': result_c.get('strategy_a', {}).get('signal', 'N/A'),
                'strategy_b_signal': result_c.get('strategy_b', {}).get('signal', 'N/A')
            })
        
        else:
            print(f"❌ 無効な strategy_name: {strategy_name}")
            print(f"   使用可能: a, b, c")
            return False
        
    except Exception as e:
        print(f"\n❌ 指標計算エラー: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    # CSV出力
    try:
        if results:
            with open(output_csv, 'w', newline='') as f:
                fieldnames = results[0].keys()
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(results)
            
            print(f"\n✓ 結果を {output_csv} に出力しました")
        
    except Exception as e:
        print(f"\n❌ CSV出力エラー: {str(e)}")
        return False
    
    print("\n✅ 指標値検証完了")
    return True

if __name__ == "__main__":
    strategy = 'a'
    output_file = 'indicator_results.csv'
    
    if len(sys.argv) > 1:
        strategy = sys.argv[1]
    
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    
    success = validate_indicators_for_strategy(strategy, output_file)
    sys.exit(0 if success else 1)
