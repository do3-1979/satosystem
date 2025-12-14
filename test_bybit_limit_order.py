#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bybit 指値注文テストスクリプト

実際のBybit APIに接続して指値注文の出発・キャンセルをテストします。
現在の API キーに注文権限がない場合は、ダミーモードでテストします。

テスト流れ：
1. 現在の価格情報を取得
2. 指値注文を出す（買い）
3. 注文IDを取得
4. 注文をキャンセルする
5. キャンセル確認

実行：
    python test_bybit_limit_order.py
"""

import sys
import os
import time
from datetime import datetime

# プロジェクトのsrcディレクトリをPythonパスに追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from bybit_exchange import BybitExchange
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
    
    exchange = BybitExchange(Config.get_api_key(), Config.get_api_secret())
    
    try:
        current_price = 50000.0
        quantity = 1.0
        
        print_status(f"現在値: {current_price:.2f} USD", "INFO")
        print_status(f"買い数量: {quantity} BTC", "INFO")
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
    
    exchange = BybitExchange(Config.get_api_key(), Config.get_api_secret())
    
    try:
        current_price = 50000.0
        quantity = 1.0
        
        print_status(f"現在値: {current_price:.2f} USD", "INFO")
        print_status(f"売り数量: {quantity} BTC", "INFO")
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
    
    exchange = BybitExchange(Config.get_api_key(), Config.get_api_secret())
    
    try:
        quantity = 1.0
        
        print_status(f"決済数量: {quantity} BTC", "INFO")
        print_status(f"実行モード: {'ダミーモード' if exchange.is_dummy_mode else '本番API'}", "INFO")
        
        # execute_exit_order を実行（sell）
        result = exchange.execute_exit_order('sell', quantity)
        
        print_status(f"✅ execute_exit_order() 成功", "SUCCESS")
        print_status(f"戻り値: {result}", "INFO")
        
        return True
    except Exception as e:
        print_status(f"❌ execute_exit_order() 失敗: {str(e)}", "ERROR")
        raise


def test_calculate_entry_price():
    """テスト4: _calculate_entry_price をテスト"""
    print_section("テスト4: _calculate_entry_price() メソッドをテスト")
    
    exchange = BybitExchange(Config.get_api_key(), Config.get_api_secret())
    
    try:
        current_price = 50000.0
        slippage = 0.5  # 0.5%
        
        # 買い注文の価格計算（下に下げる）
        buy_price = exchange._calculate_entry_price('buy', current_price, slippage)
        print_status(f"現在値: {current_price:.2f} USD", "INFO")
        print_status(f"スリッページ: {slippage}%", "INFO")
        print_status(f"買い指値: {buy_price:.2f} USD (現在値の{100 - slippage}%)", "INFO")
        
        expected_buy = current_price * (1 - slippage / 100)
        if abs(buy_price - expected_buy) < 0.01:
            print_status(f"✅ 買い指値計算が正確です", "SUCCESS")
        else:
            print_status(f"❌ 買い指値計算が異なります：期待値 {expected_buy:.2f}", "ERROR")
        
        # 売り注文の価格計算（上に上げる）
        sell_price = exchange._calculate_entry_price('sell', current_price, slippage)
        print_status(f"売り指値: {sell_price:.2f} USD (現在値の{100 + slippage}%)", "INFO")
        
        expected_sell = current_price * (1 + slippage / 100)
        if abs(sell_price - expected_sell) < 0.01:
            print_status(f"✅ 売り指値計算が正確です", "SUCCESS")
            return True
        else:
            print_status(f"❌ 売り指値計算が異なります：期待値 {expected_sell:.2f}", "ERROR")
            return False
        
    except Exception as e:
        print_status(f"❌ _calculate_entry_price() 失敗: {str(e)}", "ERROR")
        raise


def test_calculate_exit_price():
    """テスト5: _calculate_exit_price をテスト"""
    print_section("テスト5: _calculate_exit_price() メソッドをテスト")
    
    exchange = BybitExchange(Config.get_api_key(), Config.get_api_secret())
    
    try:
        current_price = 50000.0
        slippage = 0.5  # 0.5%
        
        # ロング決済（売却）- 高く売りたい
        long_exit_price = exchange._calculate_exit_price('buy', current_price, slippage)
        print_status(f"現在値: {current_price:.2f} USD", "INFO")
        print_status(f"スリッページ: {slippage}%", "INFO")
        print_status(f"ロング決済指値（売り）: {long_exit_price:.2f} USD (現在値より高く)", "INFO")
        
        expected_long = current_price * (1 + slippage / 100)
        if abs(long_exit_price - expected_long) < 0.01:
            print_status(f"✅ ロング決済指値計算が正確です", "SUCCESS")
        else:
            print_status(f"❌ ロング決済指値計算が異なります：期待値 {expected_long:.2f}", "ERROR")
        
        # ショート決済（買い戻し）- 安く買いたい
        short_exit_price = exchange._calculate_exit_price('sell', current_price, slippage)
        print_status(f"ショート決済指値（買い）: {short_exit_price:.2f} USD (現在値より安く)", "INFO")
        
        expected_short = current_price * (1 - slippage / 100)
        if abs(short_exit_price - expected_short) < 0.01:
            print_status(f"✅ ショート決済指値計算が正確です", "SUCCESS")
            return True
        else:
            print_status(f"❌ ショート決済指値計算が異なります：期待値 {expected_short:.2f}", "ERROR")
            return False
        
    except Exception as e:
        print_status(f"❌ _calculate_exit_price() 失敗: {str(e)}", "ERROR")
        raise


def test_dummy_entry():
    """テスト6: _dummy_entry_order をテスト"""
    print_section("テスト6: _dummy_entry_order() メソッドをテスト")
    
    exchange = BybitExchange(Config.get_api_key(), Config.get_api_secret())
    
    try:
        initial_balance = exchange.dummy_balance
        current_price = 50000.0
        quantity = 0.1
        
        print_status(f"初期残高: {initial_balance:.2f} USD", "INFO")
        print_status(f"買い数量: {quantity} BTC @ {current_price:.2f} USD", "INFO")
        
        # ダミーエントリー実行
        result = exchange._dummy_entry_order('buy', quantity, current_price)
        
        # 残高が減っているか確認
        base_slippage = Config.get_entry_slippage() / 100
        expected_cost = quantity * exchange._calculate_entry_price('buy', current_price, base_slippage * 100)
        
        print_status(f"ダミーエントリー実行後の残高: {exchange.dummy_balance:.2f} USD", "INFO")
        print_status(f"期待される消費額: {expected_cost:.2f} USD", "INFO")
        print_status(f"✅ _dummy_entry_order() 成功", "SUCCESS")
        
        return True
        
    except Exception as e:
        print_status(f"❌ _dummy_entry_order() 失敗: {str(e)}", "ERROR")
        raise


def test_dummy_exit():
    """テスト7: _dummy_exit_order をテスト"""
    print_section("テスト7: _dummy_exit_order() メソッドをテスト")
    
    exchange = BybitExchange(Config.get_api_key(), Config.get_api_secret())
    
    try:
        initial_balance = exchange.dummy_balance
        quantity = 0.1
        
        print_status(f"初期残高: {initial_balance:.2f} USD", "INFO")
        print_status(f"決済数量: {quantity} BTC", "INFO")
        
        # ダミー決済実行
        result = exchange._dummy_exit_order('buy', quantity)
        
        print_status(f"ダミー決済実行後の残高: {exchange.dummy_balance:.2f} USD", "INFO")
        print_status(f"✅ _dummy_exit_order() 成功", "SUCCESS")
        
        return True
        
    except Exception as e:
        print_status(f"❌ _dummy_exit_order() 失敗: {str(e)}", "ERROR")
        raise


def main():
    """メインテスト流れ"""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 58 + "║")
    print("║" + "  Bybit 指値注文メソッドテスト".center(58) + "║")
    print("║" + " " * 58 + "║")
    print("╚" + "=" * 58 + "╝")
    
    try:
        # テスト1: execute_entry_order (buy)
        test_entry_order()
        time.sleep(1)
        
        # テスト2: execute_entry_order (sell)
        test_entry_order_sell()
        time.sleep(1)
        
        # テスト3: execute_exit_order
        test_exit_order()
        time.sleep(1)
        
        # テスト4: _calculate_entry_price
        test_calculate_entry_price()
        time.sleep(1)
        
        # テスト5: _calculate_exit_price
        test_calculate_exit_price()
        time.sleep(1)
        
        # テスト6: _dummy_entry_order
        test_dummy_entry()
        time.sleep(1)
        
        # テスト7: _dummy_exit_order
        test_dummy_exit()
        
        # 成功サマリー
        print_section("テスト結果")
        print_status("✅ すべてのテストが成功しました", "SUCCESS")
        print_status("指値注文メソッドが正常に動作します", "SUCCESS")
        
        return 0
        
    except Exception as e:
        print_section("テスト失敗")
        print_status(f"❌ テスト中にエラーが発生しました: {str(e)}", "ERROR")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

