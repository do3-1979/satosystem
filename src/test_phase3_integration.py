#!/usr/bin/env python3
"""
Phase 3: エントリー判定への統合テスト

新指標を trading_strategy.py に統合し、正常にエントリー判定が行われるか確認。
"""

import sys
sys.path.insert(0, '/home/satoshi/work/satosystem/src')

from config import Config
from price_data_management import PriceDataManagement
from portfolio import Portfolio
from risk_management import RiskManagement
from trading_strategy import TradingStrategy

def test_phase3_integration():
    """
    Phase 3: Strategy統合テスト
    """
    print("=" * 70)
    print("Phase 3: エントリー判定への統合テスト")
    print("=" * 70)
    
    try:
        # 初期化
        price_data_management = PriceDataManagement()
        portfolio = Portfolio()
        
        # バックテストモード初期化
        back_test_mode = Config.get_back_test_mode()
        print(f"\n✓ バックテストモード: {'ON' if back_test_mode == 1 else 'OFF'}")
        
        if back_test_mode == 1:
            price_data_management.initialise_back_test_ohlcv_data()
            price_data_management.update_price_data_backtest()
        
        risk_manager = RiskManagement(price_data_management, portfolio)
        strategy = TradingStrategy(price_data_management, risk_manager, portfolio)
        
        print(f"✓ TradingStrategy 初期化成功")
        
        # すべてのStrategy評価メソッドが存在するか確認
        assert hasattr(risk_manager, 'evaluate_all_strategies'), "evaluate_all_strategies メソッドが見つかりません"
        assert hasattr(strategy, '_evaluate_new_indicator_strategy'), "_evaluate_new_indicator_strategy メソッドが見つかりません"
        
        print(f"✓ Strategy評価メソッドが存在します")
        
        # 新指標Strategy評価
        print(f"\n📊 新指標Strategyを評価中...")
        strategy_result = strategy._evaluate_new_indicator_strategy()
        
        if strategy_result:
            print(f"\n✅ Strategy評価結果:")
            print(f"  Signal: {strategy_result.get('signal', 'N/A')}")
            print(f"  Strategy: {strategy_result.get('strategy', 'N/A')}")
            print(f"  Confidence: {strategy_result.get('confidence', 0):.2f}")
        else:
            print(f"\n⚠️ Strategy評価結果: 有効なシグナルなし")
        
        # すべてのStrategyの詳細評価
        print(f"\n📊 詳細Strategy評価:")
        all_strategies = risk_manager.evaluate_all_strategies()
        
        print(f"  Strategy A (ADX): {all_strategies.get('strategy_a', {}).get('signal', 'N/A')}")
        print(f"  Strategy B (BB+RSI+SMA): {all_strategies.get('strategy_b', {}).get('signal', 'N/A')}")
        print(f"  Strategy C (Combined): {all_strategies.get('strategy_c', {}).get('signal', 'N/A')}")
        
        # evaluate_entry のテスト
        print(f"\n📊 evaluate_entry() を実行中...")
        strategy.evaluate_entry()
        
        print(f"  Decision: {strategy.trade_decision.get('decision', 'N/A')}")
        print(f"  Side: {strategy.trade_decision.get('side', 'N/A')}")
        
        if strategy.entry_record:
            print(f"  Entry Record:")
            print(f"    Entry Price: {strategy.entry_record.get('entry_price', 'N/A')}")
            print(f"    Strategy Result: {strategy.entry_record.get('strategy_result', {}).get('signal', 'N/A')}")
        
        print(f"\n✅ Phase 3 統合テスト完了")
        return True
        
    except Exception as e:
        print(f"\n❌ Phase 3 統合テスト失敗: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_phase3_integration()
    sys.exit(0 if success else 1)
