#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bitget 指値注文・キャンセル統合テスト

実際のBitget APIに接続して指値注文の発注・キャンセルをテストします。
Bitget注文画面を目視で確認しながら実行します。

使用方法：
    python test_bitget_api_integration.py

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

from bitget_exchange import BitgetExchange
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
    print_status(f"👀 Bitget画面で確認してください。{seconds}秒待機します...", "WAIT")
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
        ticker = exchange.fetch_ticker('BTC/USDT:USDT', params={'timeout': 10000})
        price = ticker['last']
        
        print_status(f"✅ API接続成功", "SUCCESS")
        print_status(f"BTC/USDT 現在値: {price:.2f} USDT", "INFO")
        
        return price
        
    except Exception as e:
        print_status(f"❌ API接続失敗: {str(e)}", "ERROR")
        raise


def get_open_orders_before_test(exchange):
    """テスト前の未決済注文を取得"""
    print_section("テスト前の未決済注文確認")
    
    try:
        orders = exchange.fetch_open_orders('BTC/USDT:USDT')
        
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
        quantity = 0.001  # 最小注文数量
        
        print_status(f"現在値: {ticker_price:.2f} USDT", "INFO")
        print_status(f"指値価格: {limit_price:.2f} USDT (現在値の80%)", "INFO")
        print_status(f"注文数量: {quantity} BTC", "INFO")
        print_status(f"注文内容: 買い指値注文を発注します", "WARNING")
        
        order = exchange.create_limit_order(
            symbol='BTC/USDT:USDT',
            side='buy',
            amount=quantity,
            price=limit_price,
            params={'timeout': 10000}
        )
        
        buy_order_id = order.get('id')
        
        print_status(f"✅ 買い指値注文成功", "SUCCESS")
        print_status(f"注文ID: {buy_order_id}", "INFO")
        print_status(f"ステータス: {order.get('status', 'unknown')}", "INFO")
        
        # ステップ3: Bitget画面で確認
        print_section("ステップ3: 買い注文をBitget画面で確認（15秒）")
        countdown_wait(15)
        
        return buy_order_id
        
    except Exception as e:
        print_status(f"❌ 買い指値注文失敗: {str(e)}", "ERROR")
        if "Permission denied" in str(e) or "permission" in str(e).lower():
            print_status(f"ℹ️  API キーに注文権限がありません", "INFO")
        raise


def test_cancel_buy_order(exchange, buy_order_id):
    """ステップ4-5: 買い注文をキャンセルして確認"""
    print_section("ステップ4: 買い注文をキャンセル")
    
    try:
        print_status(f"キャンセル対象注文ID: {buy_order_id}", "INFO")
        
        cancelled = exchange.cancel_order(buy_order_id, 'BTC/USDT:USDT')
        
        print_status(f"✅ 買い注文キャンセル成功", "SUCCESS")
        print_status(f"ステータス: {cancelled.get('status', 'cancelled')}", "INFO")
        
        # ステップ5: Bitget画面で確認
        print_section("ステップ5: キャンセルをBitget画面で確認（15秒）")
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
        quantity = 0.001  # 最小注文数量
        
        print_status(f"現在値: {ticker_price:.2f} USDT", "INFO")
        print_status(f"指値価格: {limit_price:.2f} USDT (現在値の120%)", "INFO")
        print_status(f"注文数量: {quantity} BTC", "INFO")
        print_status(f"注文内容: 売り指値注文を発注します", "WARNING")
        
        order = exchange.create_limit_order(
            symbol='BTC/USDT:USDT',
            side='sell',
            amount=quantity,
            price=limit_price,
            params={'timeout': 10000}
        )
        
        sell_order_id = order.get('id')
        
        print_status(f"✅ 売り指値注文成功", "SUCCESS")
        print_status(f"注文ID: {sell_order_id}", "INFO")
        print_status(f"ステータス: {order.get('status', 'unknown')}", "INFO")
        
        # ステップ7: Bitget画面で確認
        print_section("ステップ7: 売り注文をBitget画面で確認（15秒）")
        countdown_wait(15)
        
        return sell_order_id
        
    except Exception as e:
        print_status(f"❌ 売り指値注文失敗: {str(e)}", "ERROR")
        if "Permission denied" in str(e) or "permission" in str(e).lower():
            print_status(f"ℹ️  API キーに注文権限がありません", "INFO")
        raise


def test_cancel_sell_order(exchange, sell_order_id):
    """ステップ8-9: 売り注文をキャンセルして確認"""
    print_section("ステップ8: 売り注文をキャンセル")
    
    try:
        print_status(f"キャンセル対象注文ID: {sell_order_id}", "INFO")
        
        cancelled = exchange.cancel_order(sell_order_id, 'BTC/USDT:USDT')
        
        print_status(f"✅ 売り注文キャンセル成功", "SUCCESS")
        print_status(f"ステータス: {cancelled.get('status', 'cancelled')}", "INFO")
        
        # ステップ9: Bitget画面で確認
        print_section("ステップ9: キャンセルをBitget画面で確認（15秒）")
        countdown_wait(15)
        
        return True
        
    except Exception as e:
        print_status(f"⚠️  売り注文キャンセル失敗: {str(e)}", "WARNING")
        if "not found" in str(e).lower() or "cancelled" in str(e).lower():
            print_status(f"ℹ️  注文は既にキャンセルされている可能性があります", "INFO")
            return True
        raise


def cleanup_remaining_orders(exchange, initial_orders):
    """ステップ10: 残っている注文をクリーンアップ"""
    print_section("ステップ10: 残りの注文をクリーンアップ")
    
    try:
        current_orders = exchange.fetch_open_orders('BTC/USDT:USDT')
        
        # テスト前に存在しなかった注文のみキャンセル
        new_orders = [order for order in current_orders if order['id'] not in initial_orders]
        
        if new_orders:
            print_status(f"⚠️  {len(new_orders)} 件の未決済注文があります", "WARNING")
            for order in new_orders:
                try:
                    exchange.cancel_order(order['id'], 'BTC/USDT:USDT')
                    print_status(f"✅ 注文キャンセル: {order['id']}", "SUCCESS")
                except Exception as e:
                    print_status(f"⚠️  キャンセル失敗: {order['id']} - {str(e)}", "WARNING")
        else:
            print_status(f"✅ クリーンアップ不要", "SUCCESS")
        
        return True
        
    except Exception as e:
        print_status(f"⚠️  クリーンアップ失敗: {str(e)}", "WARNING")
        return False


def main():
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 68 + "║")
    print("║" + "  Bitget 指値注文・キャンセル統合テスト".center(68) + "║")
    print("║" + " " * 68 + "║")
    print("╚" + "=" * 68 + "╝")
    
    # BitgetExchange クラスを初期化
    exchange = BitgetExchange(Config.get_api_key(), Config.get_api_secret(), Config.get_api_passphrase())
    
    try:
        # ステップ0: テスト前の未決済注文を取得
        initial_orders = get_open_orders_before_test(exchange)
        
        # ステップ1: API接続確認と現在価格取得
        ticker_price = test_api_connection(exchange)
        
        # ステップ2-3: 買い指値注文を出して確認
        buy_order_id = test_create_buy_limit_order(exchange, ticker_price)
        
        # ステップ4-5: 買い注文をキャンセルして確認
        test_cancel_buy_order(exchange, buy_order_id)
        
        # ステップ1（再取得）: 現在価格取得
        ticker_price = test_api_connection(exchange)
        
        # ステップ6-7: 売り指値注文を出して確認
        sell_order_id = test_create_sell_limit_order(exchange, ticker_price)
        
        # ステップ8-9: 売り注文をキャンセルして確認
        test_cancel_sell_order(exchange, sell_order_id)
        
        # ステップ10: 残りの注文をクリーンアップ
        cleanup_remaining_orders(exchange, initial_orders)
        
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
