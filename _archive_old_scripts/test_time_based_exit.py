#!/usr/bin/env python3
"""
Time-Based Exit (Task 39d) のテスト

目的:
- 72時間保有で強制決済されることを確認
- 利益ポジションは利益確定、損失ポジションは損切りされることを確認
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from exit_strategy_v2 import ExitStrategyV2
import time


def test_time_based_exit_profit():
    """利益ポジションの場合、72時間後に利益確定することを確認"""
    print("\n=== Test 1: Time-Based Exit - Profit Position ===")
    
    strategy = ExitStrategyV2()
    strategy.time_based_exit_enabled = True
    strategy.max_holding_hours = 72
    
    entry_time = 1704067200  # 2024-01-01 00:00:00 UTC
    current_time = entry_time + (73 * 3600)  # 73時間後
    
    entry_price = 40000
    current_price = 41000  # +2.5% profit
    
    current_ohlcv = {
        'timestamp': current_time,
        'close_price': current_price,
        'psar': 39000,
        'adx': 35,
        'pvo_val': 15,
        'volatility': 500
    }
    
    position_info = {
        'quantity': 0.1,
        'side': 'BUY',
        'entry_price': entry_price
    }
    
    entry_info = {
        'entry_time': entry_time,
        'entry_price': entry_price,
        'entry_adx': 30,
        'entry_pvo': 12
    }
    
    result = strategy.evaluate_exit_condition(
        current_ohlcv=current_ohlcv,
        position_info=position_info,
        entry_info=entry_info
    )
    
    print(f"Should Exit: {result.get('should_exit')}")
    print(f"Exit Reason: {result.get('exit_reason')}")
    print(f"Holding Hours: {result.get('holding_hours', 0):.1f}")
    print(f"PnL %: {result.get('pnl_pct', 0):.2f}%")
    
    assert result.get('should_exit') == True, "72時間超過で強制決済されるべき"
    assert result.get('exit_reason') == 'TIME_LIMIT_PROFIT', "利益確定判定であるべき"
    assert result.get('holding_hours', 0) > 72, "保有時間が72時間超であるべき"
    
    print("✅ Test 1 PASSED\n")


def test_time_based_exit_loss():
    """損失ポジションの場合、72時間後に損切りすることを確認"""
    print("\n=== Test 2: Time-Based Exit - Loss Position ===")
    
    strategy = ExitStrategyV2()
    strategy.time_based_exit_enabled = True
    strategy.max_holding_hours = 72
    
    entry_time = 1704067200  # 2024-01-01 00:00:00 UTC
    current_time = entry_time + (80 * 3600)  # 80時間後
    
    entry_price = 40000
    current_price = 38500  # -3.75% loss
    
    current_ohlcv = {
        'timestamp': current_time,
        'close_price': current_price,
        'psar': 39500,
        'adx': 25,
        'pvo_val': -5,
        'volatility': 600
    }
    
    position_info = {
        'quantity': 0.1,
        'side': 'BUY',
        'entry_price': entry_price
    }
    
    entry_info = {
        'entry_time': entry_time,
        'entry_price': entry_price,
        'entry_adx': 35,
        'entry_pvo': 15
    }
    
    result = strategy.evaluate_exit_condition(
        current_ohlcv=current_ohlcv,
        position_info=position_info,
        entry_info=entry_info
    )
    
    print(f"Should Exit: {result.get('should_exit')}")
    print(f"Exit Reason: {result.get('exit_reason')}")
    print(f"Holding Hours: {result.get('holding_hours', 0):.1f}")
    print(f"PnL %: {result.get('pnl_pct', 0):.2f}%")
    
    assert result.get('should_exit') == True, "72時間超過で強制決済されるべき"
    assert result.get('exit_reason') == 'TIME_LIMIT_LOSS', "損切り判定であるべき"
    assert result.get('pnl_pct', 0) < 0, "損失であるべき"
    
    print("✅ Test 2 PASSED\n")


def test_time_based_exit_not_triggered():
    """72時間未満の場合、強制決済されないことを確認"""
    print("\n=== Test 3: Time-Based Exit - Not Triggered (< 72h) ===")
    
    strategy = ExitStrategyV2()
    strategy.time_based_exit_enabled = True
    strategy.max_holding_hours = 72
    
    entry_time = 1704067200  # 2024-01-01 00:00:00 UTC
    current_time = entry_time + (50 * 3600)  # 50時間後（72時間未満）
    
    entry_price = 40000
    current_price = 39000  # -2.5% loss
    
    current_ohlcv = {
        'timestamp': current_time,
        'close_price': current_price,
        'psar': 38000,
        'adx': 30,
        'pvo_val': 10,
        'volatility': 500
    }
    
    position_info = {
        'quantity': 0.1,
        'side': 'BUY',
        'entry_price': entry_price
    }
    
    entry_info = {
        'entry_time': entry_time,
        'entry_price': entry_price,
        'entry_adx': 32,
        'entry_pvo': 14
    }
    
    result = strategy.evaluate_exit_condition(
        current_ohlcv=current_ohlcv,
        position_info=position_info,
        entry_info=entry_info
    )
    
    print(f"Should Exit: {result.get('should_exit')}")
    print(f"Exit Reason: {result.get('exit_reason')}")
    
    # Time-Based Exitではshould_exit=Falseだが、他のシグナルで決済される可能性がある
    if result.get('should_exit') and result.get('exit_reason') not in ['TIME_LIMIT_PROFIT', 'TIME_LIMIT_LOSS']:
        print(f"ℹ️  別のシグナル（{result.get('exit_reason')}）で決済判定")
    else:
        assert result.get('exit_reason') not in ['TIME_LIMIT_PROFIT', 'TIME_LIMIT_LOSS'], \
            "72時間未満ではTime-Based Exitは発動しないべき"
    
    print("✅ Test 3 PASSED\n")


def test_time_based_exit_disabled():
    """機能が無効の場合、強制決済されないことを確認"""
    print("\n=== Test 4: Time-Based Exit - Disabled ===")
    
    strategy = ExitStrategyV2()
    strategy.time_based_exit_enabled = False  # 無効
    strategy.max_holding_hours = 72
    
    entry_time = 1704067200
    current_time = entry_time + (100 * 3600)  # 100時間後（72時間超）
    
    entry_price = 40000
    current_price = 39000
    
    current_ohlcv = {
        'timestamp': current_time,
        'close_price': current_price,
        'psar': 38500,
        'adx': 28,
        'pvo_val': 8,
        'volatility': 450
    }
    
    position_info = {
        'quantity': 0.1,
        'side': 'BUY',
        'entry_price': entry_price
    }
    
    entry_info = {
        'entry_time': entry_time,
        'entry_price': entry_price,
        'entry_adx': 30,
        'entry_pvo': 12
    }
    
    result = strategy.evaluate_exit_condition(
        current_ohlcv=current_ohlcv,
        position_info=position_info,
        entry_info=entry_info
    )
    
    print(f"Should Exit: {result.get('should_exit')}")
    print(f"Exit Reason: {result.get('exit_reason')}")
    
    # 無効化されているので、Time-Based Exitでは発動しない
    if result.get('should_exit'):
        assert result.get('exit_reason') not in ['TIME_LIMIT_PROFIT', 'TIME_LIMIT_LOSS'], \
            "機能無効時はTime-Based Exitは発動しないべき"
        print(f"ℹ️  別のシグナル（{result.get('exit_reason')}）で決済判定")
    else:
        print("ℹ️  Time-Based Exit無効のため、決済シグナルなし")
    
    print("✅ Test 4 PASSED\n")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("Time-Based Exit (Task 39d) Unit Tests")
    print("="*60)
    
    try:
        test_time_based_exit_profit()
        test_time_based_exit_loss()
        test_time_based_exit_not_triggered()
        test_time_based_exit_disabled()
        
        print("\n" + "="*60)
        print("✅ All tests PASSED!")
        print("="*60 + "\n")
        
    except AssertionError as e:
        print(f"\n❌ Test FAILED: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
