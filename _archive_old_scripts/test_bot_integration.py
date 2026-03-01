#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bot.py の execute_order メソッド動作確認テスト

修正後の execute_order が正しく execute_entry_order を呼び出しているか確認します。
"""

import sys
import os
from unittest.mock import Mock, patch, MagicMock

# プロジェクトのsrcディレクトリをPythonパスに追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from bot import Bot
from config import Config
from bybit_exchange import BybitExchange
from logger import Logger


def test_bot_execute_order():
    """bot.execute_order メソッドのテスト"""
    print("\n" + "=" * 70)
    print("  bot.execute_order メソッドのテスト")
    print("=" * 70)
    
    try:
        # Config をバックテストモードに設定
        with patch('config.Config.get_back_test_mode', return_value=1):
            with patch('config.Config.get_hot_test_dummy_mode', return_value=1):
                
                # Mock オブジェクトの作成
                mock_exchange = MagicMock(spec=BybitExchange)
                mock_strategy = MagicMock()
                mock_risk_management = MagicMock()
                mock_price_data = MagicMock()
                mock_portfolio = MagicMock()
                
                # ダミーモードを有効化
                mock_exchange.is_dummy_mode = True
                
                # execute_entry_order を呼び出せるようにする
                mock_exchange.execute_entry_order = Mock(return_value=True)
                
                # price_data_management.get_ticker を設定
                mock_price_data.get_ticker = Mock(return_value=50000.0)
                
                # Bot インスタンスを作成
                bot = Bot(mock_exchange, mock_strategy, mock_risk_management, mock_price_data, mock_portfolio)
                
                # 注文データを準備
                order = {
                    'symbol': 'BTC/USD',
                    'side': 'buy',
                    'quantity': 1.0,
                    'price': 49000.0,
                    'order_type': 'limit'
                }
                
                # execute_order を実行
                print(f"\n実行: bot.execute_order({order})")
                result = bot.execute_order(order)
                
                # execute_entry_order が呼ばれたか確認
                print(f"\nexecute_entry_order の呼び出し確認:")
                print(f"  呼ばれたか: {mock_exchange.execute_entry_order.called}")
                print(f"  呼び出し回数: {mock_exchange.execute_entry_order.call_count}")
                
                if mock_exchange.execute_entry_order.called:
                    call_args = mock_exchange.execute_entry_order.call_args
                    print(f"  呼び出し引数: {call_args}")
                    print(f"  戻り値: {result}")
                    print(f"\n✅ bot.execute_order が execute_entry_order を正しく呼び出しました")
                    return True
                else:
                    print(f"\n❌ bot.execute_order が execute_entry_order を呼び出していません")
                    return False
                    
    except Exception as e:
        print(f"\n❌ テスト失敗: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_dummy_mode_protection():
    """ダミーモードが本番取引を防ぐかテスト"""
    print("\n" + "=" * 70)
    print("  ダミーモード保護テスト")
    print("=" * 70)
    
    try:
        # バックテストモード
        Config.config['Backtest']['back_test'] = '1'
        Config.config['Backtest']['hot_test_dummy_mode'] = '1'
        
        is_dummy = Config.is_dummy_mode()
        print(f"\nバックテスト時の is_dummy_mode: {is_dummy}")
        
        if is_dummy:
            print(f"✅ バックテストはダミーモードで保護されています")
            
            # ペーパートレードテスト
            Config.config['Backtest']['back_test'] = '0'
            Config.config['Backtest']['hot_test_dummy_mode'] = '1'
            
            is_dummy = Config.is_dummy_mode()
            print(f"\nペーパートレード時の is_dummy_mode: {is_dummy}")
            
            if is_dummy:
                print(f"✅ ペーパートレードはダミーモードで保護されています")
                
                # 本番取引テスト
                Config.config['Backtest']['back_test'] = '0'
                Config.config['Backtest']['hot_test_dummy_mode'] = '0'
                
                is_dummy = Config.is_dummy_mode()
                print(f"\n本番取引時の is_dummy_mode: {is_dummy}")
                
                if not is_dummy:
                    print(f"✅ 本番取引は本番モードに設定されています")
                    return True
                else:
                    print(f"❌ 本番取引がダミーモードになっています")
                    return False
            else:
                print(f"❌ ペーパートレードがダミーモードになっていません")
                return False
        else:
            print(f"❌ バックテストがダミーモードになっていません")
            return False
            
    except Exception as e:
        print(f"\n❌ テスト失敗: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """メインテスト"""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 68 + "║")
    print("║" + "  bot.py と ダミーモード機能 統合テスト".center(68) + "║")
    print("║" + " " * 68 + "║")
    print("╚" + "=" * 68 + "╝")
    
    all_pass = True
    
    # テスト1: execute_order メソッド
    result1 = test_bot_execute_order()
    all_pass = all_pass and result1
    
    # テスト2: ダミーモード保護
    result2 = test_dummy_mode_protection()
    all_pass = all_pass and result2
    
    # 結果表示
    print("\n" + "=" * 70)
    print("  テスト結果")
    print("=" * 70)
    
    if all_pass:
        print("✅ すべてのテストが成功しました")
        print("\nbot.py の修正とダミーモード保護が正常に機能しています。")
        return 0
    else:
        print("❌ テストが失敗しました")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
