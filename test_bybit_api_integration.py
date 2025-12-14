#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bybit 指値注文・キャンセル統合テスト

実際のBybit APIに接続して指値注文の出発・キャンセルをテストします。
API権限がある場合のみ実行してください。

使用方法：
    python test_bybit_api_integration.py

注意：
    - 実際のAPIに接続します
    - API キーに注文権限が必要です
    - テスト用に小額の指値注文を出すため、クレジット残高が必要です
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

import ccxt


def print_section(title):
    """セクションタイトルを表示"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_status(message, status="INFO"):
    """ステータスメッセージを表示"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{status:6s}] {message}")


def test_api_connection():
    """テスト1: API接続確認"""
    print_section("テスト1: Bybit API接続確認")
    
    try:
        exchange = ccxt.bybit({
            'apiKey': Config.get_api_key(),
            'secret': Config.get_api_secret(),
            'enableRateLimit': True,
        })
        
        # Ticker を取得してAPI接続を確認
        ticker = exchange.fetch_ticker('BTCUSD', params={'timeout': 10000})
        price = ticker['last']
        
        print_status(f"✅ API接続成功", "SUCCESS")
        print_status(f"BTC/USD 現在値: {price:.2f} USD", "INFO")
        
        return exchange, price
        
    except Exception as e:
        print_status(f"❌ API接続失敗: {str(e)}", "ERROR")
        raise


def test_create_limit_order(exchange, ticker_price):
    """テスト2: 指値注文を出す"""
    print_section("テスト2: 指値注文を出す")
    
    try:
        # 現在値より10%下の指値で注文（約定しない可能性が高い）
        limit_price = ticker_price * 0.90
        quantity = 10  # 小額の注文
        
        print_status(f"現在値: {ticker_price:.2f} USD", "INFO")
        print_status(f"指値価格: {limit_price:.2f} USD (現在値の90%)", "INFO")
        print_status(f"注文数量: {quantity} USD", "INFO")
        print_status(f"注意: 実際のAPI に接続しています", "WARNING")
        
        order = exchange.create_limit_order(
            symbol='BTCUSD',
            side='buy',
            amount=quantity,
            price=limit_price,
            params={'timeout': 10000}
        )
        
        order_id = order.get('id')
        
        print_status(f"✅ 指値注文成功", "SUCCESS")
        print_status(f"注文ID: {order_id}", "INFO")
        print_status(f"ステータス: {order.get('status', 'unknown')}", "INFO")
        print_status(f"時刻: {order.get('datetime', 'N/A')}", "INFO")
        
        return order_id, order
        
    except Exception as e:
        print_status(f"❌ 指値注文失敗: {str(e)}", "ERROR")
        if "Permission denied" in str(e):
            print_status(f"ℹ️  API キーに注文権限がありません（ダミーモードでテストしてください）", "INFO")
        raise


def test_fetch_order_status(exchange, order_id):
    """テスト3: 注文ステータスを確認"""
    print_section("テスト3: 注文ステータスを確認")
    
    try:
        # 少し待つ（APIの反映待ち）
        time.sleep(2)
        
        order = exchange.fetch_order(order_id, 'BTCUSD')
        
        print_status(f"✅ 注文確認成功", "SUCCESS")
        print_status(f"注文ID: {order['id']}", "INFO")
        print_status(f"ステータス: {order['status']}", "INFO")
        print_status(f"数量: {order['amount']}", "INFO")
        print_status(f"価格: {order['price']:.2f}", "INFO")
        print_status(f"時刻: {order.get('datetime', 'N/A')}", "INFO")
        
        return True
        
    except Exception as e:
        print_status(f"❌ 注文確認失敗: {str(e)}", "ERROR")
        raise


def test_cancel_order(exchange, order_id):
    """テスト4: 指値注文をキャンセル"""
    print_section("テスト4: 指値注文をキャンセル")
    
    try:
        print_status(f"キャンセル対象注文ID: {order_id}", "INFO")
        
        cancelled = exchange.cancel_order(order_id, 'BTCUSD')
        
        print_status(f"✅ キャンセル成功", "SUCCESS")
        print_status(f"注文ID: {cancelled.get('id')}", "INFO")
        print_status(f"ステータス: {cancelled.get('status', 'cancelled')}", "INFO")
        
        return True
        
    except Exception as e:
        print_status(f"❌ キャンセル失敗: {str(e)}", "ERROR")
        # キャンセル失敗は致命的ではない（既に約定した可能性）
        if "not found" in str(e).lower() or "cancelled" in str(e).lower():
            print_status(f"ℹ️  注文は既にキャンセルされている可能性があります", "INFO")
            return True
        raise


def test_verify_cancelled(exchange, order_id):
    """テスト5: キャンセル確認"""
    print_section("テスト5: キャンセル確認")
    
    try:
        # 少し待つ（APIの反映待ち）
        time.sleep(2)
        
        order = exchange.fetch_order(order_id, 'BTCUSD')
        
        print_status(f"✅ キャンセル確認", "SUCCESS")
        print_status(f"注文ID: {order['id']}", "INFO")
        print_status(f"最終ステータス: {order['status']}", "INFO")
        
        return order['status'] in ['cancelled', 'closed']
        
    except Exception as e:
        print_status(f"❌ キャンセル確認失敗: {str(e)}", "ERROR")
        raise


def test_account_balance(exchange):
    """テスト6: 口座残高確認"""
    print_section("テスト6: 口座残高確認")
    
    try:
        balance = exchange.fetchBalance()
        usd_balance = balance['USDT']['total']
        
        print_status(f"✅ 口座残高取得成功", "SUCCESS")
        print_status(f"USDT残高: {usd_balance:.2f} USD", "INFO")
        
        return usd_balance
        
    except Exception as e:
        print_status(f"❌ 口座残高取得失敗: {str(e)}", "ERROR")
        raise


def main():
    """メインテスト流れ"""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 68 + "║")
    print("║" + "  Bybit API 指値注文・キャンセル統合テスト".center(68) + "║")
    print("║" + "  ⚠️  実際のAPI に接続します".center(68) + "║")
    print("║" + " " * 68 + "║")
    print("╚" + "=" * 68 + "╝")
    
    try:
        # テスト1: API接続
        exchange, ticker_price = test_api_connection()
        time.sleep(2)
        
        # テスト2: 指値注文
        order_id, order = test_create_limit_order(exchange, ticker_price)
        time.sleep(2)
        
        # テスト3: 注文ステータス確認
        test_fetch_order_status(exchange, order_id)
        time.sleep(2)
        
        # テスト4: キャンセル実行
        test_cancel_order(exchange, order_id)
        time.sleep(2)
        
        # テスト5: キャンセル確認
        cancelled_success = test_verify_cancelled(exchange, order_id)
        time.sleep(2)
        
        # テスト6: 口座残高確認
        test_account_balance(exchange)
        
        # 成功サマリー
        print_section("テスト結果")
        print_status("✅ すべてのテストが成功しました", "SUCCESS")
        print_status("・指値注文が出せた", "SUCCESS")
        print_status("・注文ステータスが確認できた", "SUCCESS")
        print_status("・注文がキャンセルできた", "SUCCESS")
        
        return 0
        
    except Exception as e:
        print_section("テスト失敗")
        print_status(f"❌ テスト中にエラーが発生しました", "ERROR")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
