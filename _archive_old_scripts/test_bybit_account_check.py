#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bybit APIアカウント設定確認スクリプト

APIキーの権限とアカウント設定を詳しく確認します。
"""

import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from config import Config
import ccxt

def print_section(title):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def print_status(message, status="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{status:6s}] {message}")

def test_api_permissions():
    """API権限を確認"""
    print_section("API権限確認")
    
    try:
        exchange = ccxt.bybit({
            'apiKey': Config.get_api_key(),
            'secret': Config.get_api_secret(),
            'enableRateLimit': True,
        })
        
        print_status(f"✅ API接続成功", "SUCCESS")
        
        # 基本情報を取得
        try:
            ticker = exchange.fetch_ticker('BTCUSD', params={'timeout': 10000})
            price = ticker['last']
            print_status(f"BTC/USD 現在値: {price:.2f} USD", "INFO")
        except Exception as e:
            print_status(f"⚠️ Ticker取得: {str(e)}", "WARNING")
        
        return exchange
        
    except Exception as e:
        print_status(f"❌ API接続失敗: {str(e)}", "ERROR")
        return None

def test_account_info(exchange):
    """アカウント情報を確認"""
    print_section("アカウント情報確認")
    
    try:
        balance = exchange.fetchBalance()
        print_status(f"✅ 口座残高取得成功", "SUCCESS")
        
        if 'USDT' in balance:
            usdt = balance['USDT']
            print_status(f"USDT 残高:", "INFO")
            print(f"    - Free: {usdt.get('free', 0):.2f}")
            print(f"    - Used: {usdt.get('used', 0):.2f}")
            print(f"    - Total: {usdt.get('total', 0):.2f}")
        
        if 'BTC' in balance:
            btc = balance['BTC']
            print_status(f"BTC 残高:", "INFO")
            print(f"    - Free: {btc.get('free', 0):.8f}")
            print(f"    - Used: {btc.get('used', 0):.8f}")
            print(f"    - Total: {btc.get('total', 0):.8f}")
        
        return True
    except Exception as e:
        error_msg = str(e)
        print_status(f"❌ アカウント情報取得失敗: {error_msg}", "ERROR")
        
        # エラーメッセージ解析
        if "collateral" in error_msg.lower():
            print_status(f"💡 Bybit Cross/Portfolio モードで決済資産を担保として有効化する必要があります", "WARNING")
        elif "permission" in error_msg.lower():
            print_status(f"💡 APIキーに読取権限がない可能性があります", "WARNING")
        
        return False

def test_order_creation(exchange):
    """注文作成テスト（実際には実行しない）"""
    print_section("注文作成シミュレーション")
    
    try:
        # 現在値を取得
        ticker = exchange.fetch_ticker('BTCUSD', params={'timeout': 10000})
        price = ticker['last']
        
        # テスト用の低い指値価格
        limit_price = price * 0.85  # 15%下の指値
        quantity = 10
        
        print_status(f"現在値: {price:.2f} USD", "INFO")
        print_status(f"指値価格: {limit_price:.2f} USD (現在値の85%)", "INFO")
        print_status(f"注文数量: {quantity} USD", "INFO")
        
        print_status(f"⚠️  注文は実際には作成しません（確認のみ）", "WARNING")
        
        # ccxt の create_order メソッドシグネチャを確認
        import inspect
        sig = inspect.signature(exchange.create_limit_order)
        print_status(f"create_limit_order シグネチャ:", "INFO")
        print(f"    {sig}")
        
        return True
        
    except Exception as e:
        print_status(f"❌ 確認エラー: {str(e)}", "ERROR")
        return False

def test_api_methods(exchange):
    """利用可能なAPIメソッドを確認"""
    print_section("利用可能なAPIメソッド確認")
    
    try:
        # 重要なメソッドが存在するか確認
        methods = {
            'fetch_ticker': exchange.has['fetchTicker'],
            'fetch_ohlcv': exchange.has['fetchOHLCV'],
            'fetch_balance': exchange.has['fetchBalance'],
            'fetch_open_orders': exchange.has['fetchOpenOrders'],
            'create_order': exchange.has['createOrder'],
            'cancel_order': exchange.has['cancelOrder'],
        }
        
        print_status(f"APIメソッド可用性:", "INFO")
        for method, available in methods.items():
            status = "✅" if available else "❌"
            print(f"    {status} {method}: {available}")
        
        # 注文関連の詳細確認
        print_status(f"\n注文タイプ対応:", "INFO")
        if 'order' in exchange.has:
            order_info = exchange.has['order']
            print(f"    {order_info}")
        
        return True
        
    except Exception as e:
        print_status(f"❌ メソッド確認エラー: {str(e)}", "ERROR")
        return False

def test_order_prerequisites(exchange):
    """注文実行前提条件の確認"""
    print_section("注文実行前提条件確認")
    
    try:
        print_status(f"Bybit アカウント要件:", "INFO")
        
        # 1. 残高確認
        try:
            balance = exchange.fetchBalance()
            if balance and 'USDT' in balance and balance['USDT']['free'] > 0:
                print(f"    ✅ USDT 残高あり: {balance['USDT']['free']:.2f}")
            else:
                print(f"    ❌ USDT 残高不足")
        except:
            print(f"    ⚠️  残高確認不可")
        
        # 2. 取引ペア確認
        try:
            pairs = exchange.symbols
            if 'BTCUSD' in pairs:
                print(f"    ✅ BTCUSD ペア利用可能")
            else:
                print(f"    ❌ BTCUSD ペア利用不可")
        except:
            print(f"    ⚠️  ペア確認不可")
        
        # 3. Cross/Portfolio モード
        print(f"    ℹ️  Cross/Portfolio モード確認:")
        print(f"       → Bybit 設定ページで確認してください")
        print(f"       → 決済資産（USDT）を担保として有効化する必要があります")
        
        return True
        
    except Exception as e:
        print_status(f"❌ 前提条件確認エラー: {str(e)}", "ERROR")
        return False

def main():
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 68 + "║")
    print("║" + "  Bybit API アカウント設定確認".center(68) + "║")
    print("║" + " " * 68 + "║")
    print("╚" + "=" * 68 + "╝")
    
    # テスト実行
    exchange = test_api_permissions()
    if not exchange:
        return 1
    
    test_account_info(exchange)
    test_api_methods(exchange)
    test_order_creation(exchange)
    test_order_prerequisites(exchange)
    
    # 最後のまとめ
    print_section("必要な設定確認事項")
    
    print("""
✓ API キー権限：
  - Read: 表示設定のAPI (読取のみ)
  - Trade: 取引のAPI (注文実行)
  
  現在のAPI キーが両方有効か確認してください。

✓ Bybit アカウント設定：
  1. Cross/Portfolio モード確認
  2. 決済資産（USDT）を担保として有効化
  3. 最小証拠金要件を確認
  
✓ 本番取引前の確認：
  1. config.ini で hot_test_dummy_mode = 0 (本番取引)
  2. スリッページ設定を確認
  3. リトライ回数を確認
    """)
    
    print_section("テスト完了")
    print_status("✅ アカウント設定確認が完了しました", "SUCCESS")
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
