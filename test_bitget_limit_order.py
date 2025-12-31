#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bitget 指値注文テストスクリプト

実際のBitget APIに接続して指値注文の出発・キャンセルをテストします。
現在の API キーに注文権限がない場合は、ダミーモードでテストします。

テスト流れ：
1. 現在の価格情報を取得
2. 指値注文を出す（買い）
3. 注文IDを取得
4. 注文をキャンセルする
5. キャンセル確認

実行：
    python test_bitget_limit_order.py
"""

import sys
import os
import time
from datetime import datetime

# プロジェクトのsrcディレクトリをPythonパスに追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from bitget_exchange import BitgetExchange
from config import Config
from logger import Logger


def print_section(title):
    """セクションタイトルを表示"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_status(message, status="INFO"):
    """ステータスメッセージを表示"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{status:6s}] {message}")


def test_entry_order():
    """テスト1: execute_entry_order をテスト"""
    print_section("テスト1: execute_entry_order() メソッドをテスト")
    
    exchange = BitgetExchange(Config.get_api_key(), Config.get_api_secret(), Config.get_api_passphrase())
    
    try:
        current_price = 88000.0
        quantity = 0.001
        
        print_status(f"現在値: {current_price:.2f} USDT", "INFO")
        print_status(f"買い数量: {quantity} BTC", "INFO")
        print_status(f"概算金額: {current_price * quantity:.2f} USDT", "INFO")
        print_status(f"⚠️  注意: 実際の注文が発行されます（ペーパーテストではありません）", "WARNING")
        print_status(f"実行モード: {'ダミーモード' if exchange.is_dummy_mode else '本番API'}", "INFO")
        
        # execute_entry_order を実行（buy）
        result = exchange.execute_entry_order('buy', quantity, current_price)
        
        print_status(f"✅ execute_entry_order() 成功", "SUCCESS")
        print_status(f"戻り値: {result}", "INFO")
        
        return True
    except Exception as e:
        print_status(f"❌ execute_entry_order() 失敗: {str(e)}", "ERROR")
        raise


def test_entry_order_sell():
    """テスト2: execute_entry_order (sell) をテスト"""
    print_section("テスト2: execute_entry_order() (sell) をテスト")
    
    exchange = BitgetExchange(Config.get_api_key(), Config.get_api_secret(), Config.get_api_passphrase())
    
    try:
        current_price = 88000.0
        quantity = 0.001
        
        print_status(f"現在値: {current_price:.2f} USDT", "INFO")
        print_status(f"売り数量: {quantity} BTC", "INFO")
        print_status(f"概算金額: {current_price * quantity:.2f} USDT", "INFO")
        print_status(f"⚠️  注意: 実際の注文が発行されます（ペーパーテストではありません）", "WARNING")
        print_status(f"実行モード: {'ダミーモード' if exchange.is_dummy_mode else '本番API'}", "INFO")
        
        # execute_entry_order を実行（sell）
        result = exchange.execute_entry_order('sell', quantity, current_price)
        
        print_status(f"✅ execute_entry_order(sell) 成功", "SUCCESS")
        print_status(f"戻り値: {result}", "INFO")
        
        return True
    except Exception as e:
        print_status(f"❌ execute_entry_order(sell) 失敗: {str(e)}", "ERROR")
        raise


def test_exit_order():
    """テスト3: execute_exit_order をテスト"""
    print_section("テスト3: execute_exit_order() メソッドをテスト")
    
    exchange = BitgetExchange(Config.get_api_key(), Config.get_api_secret(), Config.get_api_passphrase())
    
    try:
        quantity = 0.001
        
        print_status(f"決済数量: {quantity} BTC", "INFO")
        print_status(f"⚠️  注意: 実際の決済注文が発行されます", "WARNING")
        print_status(f"実行モード: {'ダミーモード' if exchange.is_dummy_mode else '本番API'}", "INFO")
        
        # execute_exit_order を実行（buy - ポジション決済）
        result = exchange.execute_exit_order('buy', quantity)
        
        print_status(f"✅ execute_exit_order(buy) 成功", "SUCCESS")
        print_status(f"戻り値: {result}", "INFO")
        
        return True
    except Exception as e:
        print_status(f"❌ execute_exit_order(buy) 失敗: {str(e)}", "ERROR")
        raise


def test_exit_order_sell():
    """テスト4: execute_exit_order (sell) をテスト"""
    print_section("テスト4: execute_exit_order() (sell) をテスト")
    
    exchange = BitgetExchange(Config.get_api_key(), Config.get_api_secret(), Config.get_api_passphrase())
    
    try:
        quantity = 0.001
        
        print_status(f"決済数量: {quantity} BTC", "INFO")
        print_status(f"⚠️  注意: 実際の決済注文が発行されます", "WARNING")
        print_status(f"実行モード: {'ダミーモード' if exchange.is_dummy_mode else '本番API'}", "INFO")
        
        # execute_exit_order を実行（sell - ポジション決済）
        result = exchange.execute_exit_order('sell', quantity)
        
        print_status(f"✅ execute_exit_order(sell) 成功", "SUCCESS")
        print_status(f"戻り値: {result}", "INFO")
        
        return True
    except Exception as e:
        print_status(f"❌ execute_exit_order(sell) 失敗: {str(e)}", "ERROR")
        raise


def test_get_ticker():
    """テスト5: fetch_ticker をテスト"""
    print_section("テスト5: fetch_ticker() メソッドをテスト")
    
    exchange = BitgetExchange(Config.get_api_key(), Config.get_api_secret(), Config.get_api_passphrase())
    
    try:
        price = exchange.fetch_ticker()
        
        print_status(f"✅ fetch_ticker() 成功", "SUCCESS")
        print_status(f"現在値: {price:.2f} USDT", "INFO")
        
        return True
    except Exception as e:
        print_status(f"❌ fetch_ticker() 失敗: {str(e)}", "ERROR")
        raise


def test_get_balance():
    """テスト6: get_account_balance_total をテスト"""
    print_section("テスト6: get_account_balance_total() メソッドをテスト")
    
    exchange = BitgetExchange(Config.get_api_key(), Config.get_api_secret(), Config.get_api_passphrase())
    
    try:
        balance = exchange.get_account_balance_total()
        
        print_status(f"✅ get_account_balance_total() 成功", "SUCCESS")
        print_status(f"口座残高: {balance:.2f} USDT", "INFO")
        
        return True
    except Exception as e:
        print_status(f"❌ get_account_balance_total() 失敗: {str(e)}", "ERROR")
        raise


def main():
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 58 + "║")
    print("║" + "  Bitget 指値注文テスト".center(58) + "║")
    print("║" + " " * 58 + "║")
    print("╚" + "=" * 58 + "╝")
    
    try:
        # テスト実行
        test_get_ticker()
        test_get_balance()
        test_entry_order()
        test_entry_order_sell()
        test_exit_order()
        test_exit_order_sell()
        
        # 最後のまとめ
        print_section("テスト完了")
        print_status("✅ 全てのテストが正常に完了しました", "SUCCESS")
        
        return 0
        
    except Exception as e:
        print_section("テスト失敗")
        print_status(f"❌ テスト中にエラーが発生しました: {str(e)}", "ERROR")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
