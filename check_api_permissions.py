#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bybit API 権限確認スクリプト

現在のAPIキーが持っている権限をすべて確認します。
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from config import Config
import ccxt

def check_api_permissions():
    """API権限を確認"""
    print("\n" + "=" * 70)
    print("  Bybit API 権限確認")
    print("=" * 70)
    
    api_key = Config.get_api_key()
    api_secret = Config.get_api_secret()
    
    print(f"\nAPI Key: {api_key[:15]}...{api_key[-5:]}")
    print(f"API Secret: {api_secret[:15]}...{api_secret[-5:]}")
    
    exchange = ccxt.bybit({
        'apiKey': api_key,
        'secret': api_secret,
        'enableRateLimit': True,
    })
    
    # 1. 残高確認（ReadOnly権限が必要）
    print(f"\n1️⃣  残高確認テスト（ReadOnly権限）:")
    try:
        balance = exchange.fetchBalance()
        print(f"   ✅ 成功 - USDT残高: {balance['USDT']['total']:.2f} USD")
    except Exception as e:
        print(f"   ❌ 失敗 - {str(e)[:100]}")
    
    # 2. ティッカー取得（公開API）
    print(f"\n2️⃣  ティッカー取得テスト（公開API）:")
    try:
        ticker = exchange.fetch_ticker('BTCUSD')
        print(f"   ✅ 成功 - BTC/USD: {ticker['last']:.2f} USD")
    except Exception as e:
        print(f"   ❌ 失敗 - {str(e)[:100]}")
    
    # 3. 市場データ取得
    print(f"\n3️⃣  市場データ取得テスト（公開API）:")
    try:
        ohlcv = exchange.fetch_ohlcv('BTCUSD', '1h', limit=1)
        print(f"   ✅ 成功 - 取得件数: {len(ohlcv)}")
    except Exception as e:
        print(f"   ❌ 失敗 - {str(e)[:100]}")
    
    # 4. 指値注文テスト（Trade権限が必要）
    print(f"\n4️⃣  指値注文テスト（Trade権限）:")
    print(f"   注: 実際に注文が出される可能性があります")
    try:
        # $1の非常に小さな注文を試みる
        order = exchange.create_limit_order(
            'BTCUSD',
            'buy',
            1,  # USD
            89000,  # 現在値より低い
            params={'timeout': 10000}
        )
        print(f"   ✅ 成功 - 注文ID: {order.get('id')}")
        print(f"   ⚠️  注文がキャンセルできるか確認中...")
        
        # 注文をキャンセル
        try:
            cancelled = exchange.cancel_order(order['id'], 'BTCUSD')
            print(f"   ✅ キャンセル成功")
        except Exception as e:
            print(f"   ❌ キャンセル失敗 - {str(e)[:100]}")
            
    except PermissionError as e:
        print(f"   ❌ 権限不足 - Trade権限がない可能性があります")
    except Exception as e:
        error_msg = str(e)
        if "Permission denied" in error_msg or "10005" in error_msg:
            print(f"   ❌ 権限不足 - API キーに Trade 権限がありません")
        else:
            print(f"   ❌ 失敗 - {error_msg[:100]}")
    
    # 5. オープン注文確認テスト（ReadOnly権限が必要）
    print(f"\n5️⃣  オープン注文確認テスト（ReadOnly権限）:")
    try:
        open_orders = exchange.fetch_open_orders('BTCUSD')
        print(f"   ✅ 成功 - オープン注文数: {len(open_orders)}")
    except Exception as e:
        print(f"   ❌ 失敗 - {str(e)[:100]}")
    
    print("\n" + "=" * 70)
    print("  権限確認完了")
    print("=" * 70)
    print("\n📋 必要な権限:")
    print("  - ReadOnly: 残高確認、市場データ取得、オープン注文確認")
    print("  - Trade: 指値注文・成行注文の実行、注文キャンセル")
    print("\n💡 ヒント:")
    print("  Bybit の API管理ページで以下を確認してください：")
    print("  - API権限: \"Trade\"  が有効になっているか")
    print("  - IP制限: 現在のIPが許可リストに入っているか")
    print("  - 認証: APIキーの有効性と秘密鍵の正確性")

if __name__ == "__main__":
    check_api_permissions()
