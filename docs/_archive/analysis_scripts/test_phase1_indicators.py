#!/usr/bin/env python3
"""
Phase 1: 新指標計算ロジック基盤整備のテスト

新指標（Bollinger Bands, RSI, SMA, MACD）が正しく読み込まれ、
Strategy A, B, Cのセットアップが正しく行われているか確認する。
"""

import sys
sys.path.append('/home/satoshi/work/satosystem/src')

from config import Config
from price_data_management import PriceDataManagement
from portfolio import Portfolio
from risk_management import RiskManagement

def test_phase1_config():
    """Config から新指標設定が正しく読み込まれるか確認"""
    print("=" * 60)
    print("TEST: Phase 1 - Config新指標設定の読み込み")
    print("=" * 60)
    
    try:
        # Strategy フラグの読み込み
        enable_strategy_a = Config.get_config_bool('Trading', 'enable_strategy_a_adx', 1)
        enable_strategy_b = Config.get_config_bool('Trading', 'enable_strategy_b_bb_rsi_sma', 0)
        enable_strategy_c = Config.get_config_bool('Trading', 'enable_strategy_c_combined', 0)
        
        print(f"✓ Strategy A (ADX): {enable_strategy_a}")
        print(f"✓ Strategy B (BB+RSI+SMA): {enable_strategy_b}")
        print(f"✓ Strategy C (Combined): {enable_strategy_c}")
        
        # 各指標のパラメータ読み込み
        bb_period = Config.get_config_int('Trading', 'bb_period', 20)
        bb_std_dev = Config.get_config_float('Trading', 'bb_std_dev', 2.0)
        rsi_period = Config.get_config_int('Trading', 'rsi_period', 14)
        sma_fast = Config.get_config_int('Trading', 'sma_fast_period', 50)
        sma_slow = Config.get_config_int('Trading', 'sma_slow_period', 200)
        macd_fast = Config.get_config_int('Trading', 'macd_fast_period', 12)
        
        print(f"\n✓ BB Period: {bb_period}, Std Dev: {bb_std_dev}")
        print(f"✓ RSI Period: {rsi_period}")
        print(f"✓ SMA Fast: {sma_fast}, Slow: {sma_slow}")
        print(f"✓ MACD Fast: {macd_fast}")
        
        print("\n✅ Config読み込みテスト: PASS")
        return True
    except Exception as e:
        print(f"\n❌ Config読み込みテスト: FAIL - {str(e)}")
        return False

def test_phase1_risk_management_init():
    """RiskManagementの初期化とStrategy評価メソッドの存在確認"""
    print("\n" + "=" * 60)
    print("TEST: Phase 1 - RiskManagement初期化と指標メソッド確認")
    print("=" * 60)
    
    try:
        # RiskManagementの初期化
        price_data_management = PriceDataManagement()
        portfolio = Portfolio()
        risk_manager = RiskManagement(price_data_management, portfolio)
        
        print("✓ RiskManagement初期化成功")
        
        # Strategy評価メソッドの存在確認
        assert hasattr(risk_manager, 'evaluate_strategy_a_adx'), "evaluate_strategy_a_adx メソッドが見つかりません"
        assert hasattr(risk_manager, 'evaluate_strategy_b_bb_rsi_sma'), "evaluate_strategy_b_bb_rsi_sma メソッドが見つかりません"
        assert hasattr(risk_manager, 'evaluate_strategy_c_combined'), "evaluate_strategy_c_combined メソッドが見つかりません"
        assert hasattr(risk_manager, 'evaluate_all_strategies'), "evaluate_all_strategies メソッドが見つかりません"
        
        print("✓ すべてのStrategy評価メソッドが存在します")
        
        # NewIndicatorsクラスの初期化確認
        assert hasattr(risk_manager, 'new_indicators'), "new_indicators が見つかりません"
        assert hasattr(risk_manager.new_indicators, 'calc_bollinger_bands'), "calc_bollinger_bands メソッドが見つかりません"
        assert hasattr(risk_manager.new_indicators, 'calc_rsi'), "calc_rsi メソッドが見つかりません"
        assert hasattr(risk_manager.new_indicators, 'calc_sma'), "calc_sma メソッドが見つかりません"
        assert hasattr(risk_manager.new_indicators, 'calc_macd'), "calc_macd メソッドが見つかりません"
        
        print("✓ NewIndicators内のすべての計算メソッドが存在します")
        
        print("\n✅ RiskManagement初期化テスト: PASS")
        return True
    except Exception as e:
        print(f"\n❌ RiskManagement初期化テスト: FAIL - {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_phase1_strategy_a_evaluation():
    """Strategy A (ADX)の評価"""
    print("\n" + "=" * 60)
    print("TEST: Phase 1 - Strategy A (ADX)の評価")
    print("=" * 60)
    
    try:
        price_data_management = PriceDataManagement()
        portfolio = Portfolio()
        risk_manager = RiskManagement(price_data_management, portfolio)
        
        # Strategy A評価
        result = risk_manager.evaluate_strategy_a_adx()
        
        print(f"✓ Strategy A Evaluation Result:")
        print(f"  Signal: {result.get('signal', 'N/A')}")
        print(f"  Bull: {result.get('bull', False)}")
        print(f"  Bear: {result.get('bear', False)}")
        print(f"  ADX Value: {result.get('adx', 0)}")
        
        assert 'signal' in result, "signal キーが見つかりません"
        assert 'bull' in result, "bull キーが見つかりません"
        assert 'bear' in result, "bear キーが見つかりません"
        assert 'adx' in result, "adx キーが見つかりません"
        
        print("\n✅ Strategy A評価テスト: PASS")
        return True
    except Exception as e:
        print(f"\n❌ Strategy A評価テスト: FAIL - {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_phase1_all_strategies_evaluation():
    """すべてのStrategyを評価"""
    print("\n" + "=" * 60)
    print("TEST: Phase 1 - すべてのStrategy評価")
    print("=" * 60)
    
    try:
        price_data_management = PriceDataManagement()
        portfolio = Portfolio()
        risk_manager = RiskManagement(price_data_management, portfolio)
        
        # すべてのStrategy評価
        all_results = risk_manager.evaluate_all_strategies()
        
        print("✓ All Strategies Evaluation Result:")
        for strategy_name, result in all_results.items():
            signal = result.get('signal', 'N/A')
            print(f"  {strategy_name}: signal={signal}")
        
        assert 'strategy_a' in all_results, "strategy_a が見つかりません"
        assert 'strategy_b' in all_results, "strategy_b が見つかりません"
        assert 'strategy_c' in all_results, "strategy_c が見つかりません"
        
        print("\n✅ すべてのStrategy評価テスト: PASS")
        return True
    except Exception as e:
        print(f"\n❌ すべてのStrategy評価テスト: FAIL - {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Phase 1: 新指標計算ロジック基盤整備テスト")
    print("=" * 60 + "\n")
    
    results = []
    results.append(("Config Read Test", test_phase1_config()))
    results.append(("RiskManagement Init Test", test_phase1_risk_management_init()))
    results.append(("Strategy A Evaluation Test", test_phase1_strategy_a_evaluation()))
    results.append(("All Strategies Evaluation Test", test_phase1_all_strategies_evaluation()))
    
    print("\n" + "=" * 60)
    print("テスト結果サマリー")
    print("=" * 60)
    
    passed = 0
    failed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\n総計: {passed}/{len(results)} テスト成功")
    
    if failed == 0:
        print("\n🎉 Phase 1 すべてのテストが成功しました！")
        sys.exit(0)
    else:
        print(f"\n⚠️ {failed}個のテストが失敗しました。")
        sys.exit(1)
