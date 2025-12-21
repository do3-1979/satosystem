#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bybit 指値注文・キャンセル統合テスト（改善版）

実際のBybit APIに接続して指値注文の発注・キャンセルをテストします。
Bybit注文画面を目視で確認しながら実行します。

使用方法：
    python test_bybit_api_integration.py

手順：
    1. 現在価格を取得
    2. 現在価格より十分低い値で買い指値注文を発注
    3. 15秒待機（目視確認）
    4. 買い注文をキャンセル
    5. 15秒待機（目視確認）
    6. 現在価格を取得
    7. 現在価格より十分高い値で売り指値注文を発注
    8. 15秒待機（目視確認）
    9. 売り注文をキャンセル
    10. 15秒待機（目視確認）
    11. 全未決済注文をクリーンアップ

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
    status_map = {
        "INFO": "ℹ️ ",
        "SUCCESS": "✅",
        "ERROR": "❌",
        "WARNING": "⚠️ ",
        "WAIT": "⏳"
    }
    prefix = status_map.get(status, "•")
    print(f"[{timestamp}] {prefix} {message}")


def countdown_wait(seconds):
    """カウントダウン付き待機"""
    print_status(f"👀 Bybit画面で確認してください。{seconds}秒待機します...", "WAIT")
    for i in range(seconds, 0, -1):
        if i % 5 == 0 or i <= 5:
            print(f"    ⏳ あと {i} 秒...", end="\r")
        time.sleep(1)
    print("    ✅ 待機完了                 ")



def test_api_connection(exchange):
    """ステップ1: API接続確認と現在価格取得"""
    print_section("ステップ1: API接続確認と現在価格取得")
    
    try:
        # Ticker を取得してAPI接続を確認
        ticker = exchange.fetch_ticker('BTCUSD', params={'timeout': 10000})
        price = ticker['last']
        
        print_status(f"✅ API接続成功", "SUCCESS")
        print_status(f"BTC/USD 現在値: {price:.2f} USD", "INFO")
        
        return price
        
    except Exception as e:
        print_status(f"❌ API接続失敗: {str(e)}", "ERROR")
        raise


def get_open_orders_before_test(exchange):
    """テスト前の未決済注文を取得"""
    print_section("テスト前の未決済注文確認")
    
    try:
        orders = exchange.fetch_open_orders('BTCUSD')
        
        if orders:
            print_status(f"⚠️  テスト前に {len(orders)} 件の未決済注文があります", "WARNING")
            for order in orders:
                print_status(f"  - 注文ID: {order['id']}, 方向: {order['side'].upper()}, 数量: {order['amount']}, 価格: {order['price']:.2f}", "INFO")
        else:
            print_status(f"✅ テスト前の未決済注文なし", "SUCCESS")
        
        return [order['id'] for order in orders]
        
    except Exception as e:
        print_status(f"⚠️  既存注文取得に失敗（続行）: {str(e)}", "WARNING")
        return []


def test_create_buy_limit_order(exchange, ticker_price):
    """ステップ2-3: 買い指値注文を出して確認"""
    print_section("ステップ2: 買い指値注文を発注")
    
    try:
        # 現在値より20%下の指値で注文（約定しない可能性が高い）
        limit_price = ticker_price * 0.80
        quantity = 10  # 小額の注文
        
        print_status(f"現在値: {ticker_price:.2f} USD", "INFO")
        print_status(f"指値価格: {limit_price:.2f} USD (現在値の80%)", "INFO")
        print_status(f"注文数量: {quantity} USD", "INFO")
        print_status(f"注文内容: 買い指値注文を発注します", "WARNING")
        
        order = exchange.create_limit_order(
            symbol='BTCUSD',
            side='buy',
            amount=quantity,
            price=limit_price,
            params={'timeout': 10000}
        )
        
        buy_order_id = order.get('id')
        
        print_status(f"✅ 買い指値注文成功", "SUCCESS")
        print_status(f"注文ID: {buy_order_id}", "INFO")
        print_status(f"ステータス: {order.get('status', 'unknown')}", "INFO")
        
        # ステップ3: Bybit画面で確認
        print_section("ステップ3: 買い注文をBybit画面で確認（15秒）")
        countdown_wait(15)
        
        return buy_order_id
        
    except Exception as e:
        print_status(f"❌ 買い指値注文失敗: {str(e)}", "ERROR")
        if "Permission denied" in str(e):
            print_status(f"ℹ️  API キーに注文権限がありません", "INFO")
        raise


def test_cancel_buy_order(exchange, buy_order_id):
    """ステップ4-5: 買い注文をキャンセルして確認"""
    print_section("ステップ4: 買い注文をキャンセル")
    
    try:
        print_status(f"キャンセル対象注文ID: {buy_order_id}", "INFO")
        
        cancelled = exchange.cancel_order(buy_order_id, 'BTCUSD')
        
        print_status(f"✅ 買い注文キャンセル成功", "SUCCESS")
        print_status(f"ステータス: {cancelled.get('status', 'cancelled')}", "INFO")
        
        # ステップ5: Bybit画面で確認
        print_section("ステップ5: キャンセルをBybit画面で確認（15秒）")
        countdown_wait(15)
        
        return True
        
    except Exception as e:
        print_status(f"⚠️  買い注文キャンセル失敗: {str(e)}", "WARNING")
        if "not found" in str(e).lower() or "cancelled" in str(e).lower():
            print_status(f"ℹ️  注文は既にキャンセルされている可能性があります", "INFO")
            return True
        raise


def test_create_sell_limit_order(exchange, ticker_price):
    """ステップ6-7: 売り指値注文を出して確認"""
    print_section("ステップ6: 売り指値注文を発注")
    
    try:
        # 現在値より20%上の指値で注文（約定しない可能性が高い）
        limit_price = ticker_price * 1.20
        quantity = 10  # 小額の注文
        
        print_status(f"現在値: {ticker_price:.2f} USD", "INFO")
        print_status(f"指値価格: {limit_price:.2f} USD (現在値の120%)", "INFO")
        print_status(f"注文数量: {quantity} USD", "INFO")
        print_status(f"注文内容: 売り指値注文を発注します", "WARNING")
        
        order = exchange.create_limit_order(
            symbol='BTCUSD',
            side='sell',
            amount=quantity,
            price=limit_price,
            params={'timeout': 10000}
        )
        
        sell_order_id = order.get('id')
        
        print_status(f"✅ 売り指値注文成功", "SUCCESS")
        print_status(f"注文ID: {sell_order_id}", "INFO")
        print_status(f"ステータス: {order.get('status', 'unknown')}", "INFO")
        
        # ステップ7: Bybit画面で確認
        print_section("ステップ7: 売り注文をBybit画面で確認（15秒）")
        countdown_wait(15)
        
        return sell_order_id
        
    except Exception as e:
        print_status(f"❌ 売り指値注文失敗: {str(e)}", "ERROR")
        raise


def test_cancel_sell_order(exchange, sell_order_id):
    """ステップ8-9: 売り注文をキャンセルして確認"""
    print_section("ステップ8: 売り注文をキャンセル")
    
    try:
        print_status(f"キャンセル対象注文ID: {sell_order_id}", "INFO")
        
        cancelled = exchange.cancel_order(sell_order_id, 'BTCUSD')
        
        print_status(f"✅ 売り注文キャンセル成功", "SUCCESS")
        print_status(f"ステータス: {cancelled.get('status', 'cancelled')}", "INFO")
        
        # ステップ9: Bybit画面で確認
        print_section("ステップ9: キャンセルをBybit画面で確認（15秒）")
        countdown_wait(15)
        
        return True
        
    except Exception as e:
        print_status(f"⚠️  売り注文キャンセル失敗: {str(e)}", "WARNING")
        if "not found" in str(e).lower() or "cancelled" in str(e).lower():
            print_status(f"ℹ️  注文は既にキャンセルされている可能性があります", "INFO")
            return True
        raise


def cleanup_all_open_orders(exchange, orders_before_test):
    """ステップ10: すべての未決済注文をクリーンアップ"""
    print_section("ステップ10: 全未決済注文の確認とクリーンアップ")
    
    try:
        current_orders = exchange.fetch_open_orders('BTCUSD')
        
        if not current_orders:
            print_status(f"✅ 未決済注文なし（正常）", "SUCCESS")
            return True
        
        print_status(f"⚠️  {len(current_orders)} 件の未決済注文が残っています", "WARNING")
        
        # テスト中に出した注文（テスト前になかった注文）を抽出
        new_order_ids = [order['id'] for order in current_orders 
                         if order['id'] not in orders_before_test]
        
        if new_order_ids:
            print_status(f"テスト中に出した注文: {len(new_order_ids)} 件", "INFO")
            for order in current_orders:
                if order['id'] in new_order_ids:
                    print_status(f"  - 注文ID: {order['id']}, 方向: {order['side'].upper()}, 価格: {order['price']:.2f}", "INFO")
            
            # これらをキャンセル
            cancelled_count = 0
            for order_id in new_order_ids:
                try:
                    exchange.cancel_order(order_id, 'BTCUSD')
                    print_status(f"  ✅ キャンセル完了: {order_id}", "SUCCESS")
                    cancelled_count += 1
                except Exception as e:
                    print_status(f"  ⚠️  キャンセル失敗: {order_id} - {str(e)}", "WARNING")
            
            print_status(f"キャンセル完了: {cancelled_count}/{len(new_order_ids)} 件", "INFO")
        
        # テスト前からあった注文は警告
        if orders_before_test:
            print_status(f"⚠️  テスト前からあった注文: {len(orders_before_test)} 件（キャンセルしません）", "WARNING")
        
        return True
        
    except Exception as e:
        print_status(f"❌ クリーンアップ処理エラー: {str(e)}", "ERROR")
        return False


def test_account_balance(exchange):
    """最終確認: 口座残高確認"""
    print_section("最終確認: 口座残高確認")
    
    try:
        balance = exchange.fetchBalance()
        usd_balance = balance['USDT']['total']
        
        print_status(f"✅ 口座残高取得成功", "SUCCESS")
        print_status(f"USDT残高: {usd_balance:.2f} USD", "INFO")
        
        return usd_balance
        
    except Exception as e:
        print_status(f"❌ 口座残高取得失敗: {str(e)}", "ERROR")
        return None


def main():
    """メインテスト流れ"""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 68 + "║")
    print("║" + "  Bybit API 指値注文・キャンセル統合テスト".center(68) + "║")
    print("║" + "  👀 Bybit注文画面を目視で確認しながら実行します".center(68) + "║")
    print("║" + "  ⚠️  実際のAPI に接続します".center(68) + "║")
    print("║" + " " * 68 + "║")
    print("╚" + "=" * 68 + "╝")
    
    try:
        # ccxt exchange を直接作成
        exchange = ccxt.bybit({
            'apiKey': Config.get_api_key(),
            'secret': Config.get_api_secret(),
            'enableRateLimit': True,
        })
        
        # テスト前の準備
        orders_before_test = get_open_orders_before_test(exchange)
        time.sleep(2)
        
        # ステップ1: API接続と現在価格取得
        ticker_price = test_api_connection(exchange)
        time.sleep(2)
        
        # ステップ2-5: 買い注文 → 確認 → キャンセル → 確認
        buy_order_id = test_create_buy_limit_order(exchange, ticker_price)
        test_cancel_buy_order(exchange, buy_order_id)
        
        # ステップ6-9: 売り注文 → 確認 → キャンセル → 確認
        sell_order_id = test_create_sell_limit_order(exchange, ticker_price)
        test_cancel_sell_order(exchange, sell_order_id)
        
        # ステップ10: 全注文クリーンアップ
        cleanup_all_open_orders(exchange, orders_before_test)
        time.sleep(2)
        
        # 最終確認: 口座残高確認
        test_account_balance(exchange)
        
        # 成功サマリー
        print_section("テスト完了 ✅")
        print_status("すべてのテストが成功しました", "SUCCESS")
        print_status("✅ 買い指値注文が発注できた", "INFO")
        print_status("✅ 買い注文がキャンセルできた", "INFO")
        print_status("✅ 売り指値注文が発注できた", "INFO")
        print_status("✅ 売り注文がキャンセルできた", "INFO")
        print_status("✅ すべての注文が正常にキャンセルされた", "INFO")
        
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

