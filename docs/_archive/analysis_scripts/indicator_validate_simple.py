#!/usr/bin/env python3
"""
Phase 2: 指標値単体検証（バックテスト不要）

新指標を現在のOHLCVデータに対して直接計算し、期待値通りの計算値が出ているか確認。
バックテストループなしで効率的に検証。

実行方法:
  python indicator_validate_simple.py [strategy_name] [output_csv]
  
  strategy_name: a (ADX), b (BB+RSI+SMA), c (combined), all (全て)
  output_csv: 出力CSVファイルパス（デフォルト: indicator_results.csv）

例:
  python indicator_validate_simple.py all indicator_results_all.csv
"""

import sys
sys.path.insert(0, '/home/satoshi/work/satosystem/src')

from config import Config
from price_data_management import PriceDataManagement
from portfolio import Portfolio
from risk_management import RiskManagement
import csv
from datetime import datetime

def validate_indicators(strategy_name='all', output_csv='indicator_results.csv'):
    """
    OHLCV データから直接指標を計算して検証
    """
    print("=" * 70)
    print(f"Phase 2: 新指標単体検証 - Strategy {strategy_name.upper()}")
    print("=" * 70)
    
    # 初期化
    try:
        price_data_management = PriceDataManagement()
        portfolio = Portfolio()
        
        # バックテストモードの場合、データを初期化
        back_test_mode = Config.get_back_test_mode()
        print(f"\n✓ バックテストモード: {'ON' if back_test_mode == 1 else 'OFF'}")
        
        if back_test_mode == 1:
            price_data_management.initialise_back_test_ohlcv_data()
            price_data_management.update_price_data_backtest()
            print(f"✓ バックテストOHLCVデータを初期化・更新")
        
        risk_manager = RiskManagement(price_data_management, portfolio)
        
        print(f"\n✓ RiskManagement初期化成功")
        print(f"  - Strategy A (ADX): {'有効' if risk_manager.enable_strategy_a_adx else '無効'}")
        print(f"  - Strategy B (BB+RSI+SMA): {'有効' if risk_manager.enable_strategy_b_bb_rsi_sma else '無効'}")
        print(f"  - Strategy C (Combined): {'有効' if risk_manager.enable_strategy_c_combined else '無効'}")
        
    except Exception as e:
        print(f"❌ 初期化失敗: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    # OHLCV データの確認
    try:
        main_time_frame = Config.get_time_frame()
        ohlcv_data = price_data_management.get_ohlcv_data(main_time_frame)
        
        print(f"\n✓ OHLCV データ確認: {len(ohlcv_data)}キャンドル")
        if len(ohlcv_data) == 0:
            print(f"❌ エラー: OHLCVデータが取得できません")
            return False
        elif len(ohlcv_data) < 100:
            print(f"⚠️ 警告: データ量が少なめ（{len(ohlcv_data)}キャンドル）")
        
        # 価格情報の確認
        close_prices = [item['close_price'] for item in ohlcv_data]
        print(f"  最新価格: ${close_prices[-1]:.2f}")
        print(f"  価格範囲: ${min(close_prices):.2f} - ${max(close_prices):.2f}")
        
    except Exception as e:
        print(f"❌ OHLCVデータ取得失敗: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    # 指標値の評価
    results = []
    
    print(f"\n📊 指標を計算・評価中...")
    
    try:
        if strategy_name.lower() in ['a', 'all']:
            # Strategy A: ADX のみ検証
            print("\n--- Strategy A: ADX ---")
            result_a = risk_manager.evaluate_strategy_a_adx()
            
            print(f"  Signal: {result_a.get('signal', 'N/A')}")
            print(f"  Bull: {result_a.get('bull', False)}")
            print(f"  Bear: {result_a.get('bear', False)}")
            print(f"  ADX Value: {result_a.get('adx', 0):.2f}")
            
            # ADX値の履歴出力
            if risk_manager.adx:
                print(f"\n  ADX 推移（最後の10キャンドル）:")
                for i, adx_val in enumerate(risk_manager.adx[-10:]):
                    candle_idx = len(risk_manager.adx) - 10 + i
                    close_price = ohlcv_data[candle_idx]['close_price'] if candle_idx < len(ohlcv_data) else 0
                    print(f"    [{candle_idx:4d}] ADX={adx_val:6.2f}  Close=${close_price:8.2f}")
            
            results.append({
                'timestamp': datetime.now().isoformat(),
                'strategy': 'A',
                'signal': result_a.get('signal', 'N/A'),
                'adx': result_a.get('adx', 0),
                'bull': result_a.get('bull', False),
                'bear': result_a.get('bear', False)
            })
        
        if strategy_name.lower() in ['b', 'all']:
            # Strategy B: BB + RSI + SMA 検証
            print("\n--- Strategy B: Bollinger Bands + RSI + SMA ---")
            result_b = risk_manager.evaluate_strategy_b_bb_rsi_sma()
            
            print(f"  Signal: {result_b.get('signal', 'N/A')}")
            
            if 'bb' in result_b and result_b['bb']:
                bb = result_b['bb']
                close_price = price_data_management.get_ticker()
                print(f"  Bollinger Bands (Period={risk_manager.bb_period}):")
                print(f"    Upper:  ${bb.get('upper', 0):8.2f}")
                print(f"    Middle: ${bb.get('middle', 0):8.2f}")
                print(f"    Lower:  ${bb.get('lower', 0):8.2f}")
                print(f"    Close:  ${close_price:8.2f}")
                print(f"    Signal: {bb.get('signal', 'N/A')}")
            
            if 'rsi' in result_b and result_b['rsi'] and isinstance(result_b['rsi'], dict):
                rsi = result_b['rsi']
                print(f"  RSI (Period={risk_manager.rsi_period}):")
                print(f"    Value:    {rsi.get('value', 0):6.2f}")
                print(f"    Overbought threshold: {risk_manager.rsi_overbought}")
                print(f"    Oversold threshold: {risk_manager.rsi_oversold}")
                print(f"    Signal: {rsi.get('signal', 'N/A')}")
            
            if 'sma' in result_b and result_b['sma']:
                sma = result_b['sma']
                print(f"  SMA:")
                print(f"    Fast ({risk_manager.sma_fast_period}): ${sma.get('fast', 0):8.2f}")
                print(f"    Slow ({risk_manager.sma_slow_period}): ${sma.get('slow', 0):8.2f}")
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
        
        if strategy_name.lower() in ['c', 'all']:
            # Strategy C: 全指標統合検証
            print("\n--- Strategy C: Combined (A + B) ---")
            result_c = risk_manager.evaluate_strategy_c_combined()
            
            print(f"  Combined Signal: {result_c.get('signal', 'N/A')}")
            
            if 'strategy_a' in result_c:
                print(f"    Strategy A Signal: {result_c['strategy_a'].get('signal', 'N/A')}")
            
            if 'strategy_b' in result_c:
                print(f"    Strategy B Signal: {result_c['strategy_b'].get('signal', 'N/A')}")
            
            results.append({
                'timestamp': datetime.now().isoformat(),
                'strategy': 'C',
                'signal': result_c.get('signal', 'N/A'),
                'strategy_a_signal': result_c.get('strategy_a', {}).get('signal', 'N/A'),
                'strategy_b_signal': result_c.get('strategy_b', {}).get('signal', 'N/A')
            })
        
        if strategy_name.lower() not in ['a', 'b', 'c', 'all']:
            print(f"❌ 無効な strategy_name: {strategy_name}")
            print(f"   使用可能: a, b, c, all")
            return False
        
    except Exception as e:
        print(f"\n❌ 指標計算エラー: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    # CSV出力
    try:
        if results:
            # フィールド名を統一（すべてのキーを含める）
            all_keys = set()
            for r in results:
                all_keys.update(r.keys())
            
            fieldnames = sorted(list(all_keys))
            
            with open(output_csv, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, restval='N/A')
                writer.writeheader()
                writer.writerows(results)
            
            print(f"\n✓ 結果を {output_csv} に出力しました")
        
    except Exception as e:
        print(f"\n❌ CSV出力エラー: {str(e)}")
        return False
    
    print("\n✅ 指標値検証完了")
    return True

if __name__ == "__main__":
    strategy = 'all'
    output_file = 'indicator_results.csv'
    
    if len(sys.argv) > 1:
        strategy = sys.argv[1]
    
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    
    success = validate_indicators(strategy, output_file)
    sys.exit(0 if success else 1)
