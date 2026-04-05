#!/usr/bin/env python3
"""
## 本番注文テスト（手動実行専用）

⚠️  このスクリプトは実際の資金を使用してBitgetに注文を出します。
⚠️  テスト中は常にBitgetダッシュボードを監視してください。
⚠️  異常時はBitgetで直接ポジションを決済してください。

テスト内容:
  Test 1: 成行買い → 5秒待機 → 成行決済
  Test 2: 指値買い（現在値+0.1%） → 約定確認 → 成行決済

実行方法:
  cd /home/satoshi/work/satosystem
  python3 test_live_order.py

注意:
  - config.ini の back_test=1 を 0 に、hot_test_dummy_mode=1 を 0 に
    一時的に書き換えてテストを実施します（テスト後に自動復元）
  - 最小注文量 0.001 BTC を使用します
"""

import sys
import os
import json
import time
import configparser
import shutil

# src ディレクトリをパスに追加
SRC_DIR = os.path.join(os.path.dirname(__file__), 'src')
sys.path.insert(0, SRC_DIR)

CONFIG_PATH = os.path.join(SRC_DIR, 'config.ini')
CONFIG_BACKUP_PATH = CONFIG_PATH + '.test_backup'

# =====================================================
# テストパラメータ（変更可能）
# =====================================================
TEST_QUANTITY = 0.001      # テスト注文数量（BTC）※ 最小 0.0001 、推奨 0.001
WAIT_BEFORE_EXIT = 5       # エントリー後の待機秒数
LIMIT_ORDER_OFFSET = 0.1   # 指値買いは現在値 + x% 上に設定（即時約定を狙う）
# =====================================================


def print_sep(title=""):
    print(f"\n{'='*60}")
    if title:
        print(f"  {title}")
        print('='*60)


def patch_config_for_live():
    """config.ini を本番モード（back_test=0, hot_test_dummy_mode=0）に書き換え、バックアップを保存"""
    shutil.copy2(CONFIG_PATH, CONFIG_BACKUP_PATH)
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_PATH)
    for section in cfg.sections():
        if cfg.has_option(section, 'back_test'):
            cfg.set(section, 'back_test', '0')
        if cfg.has_option(section, 'hot_test_dummy_mode'):
            cfg.set(section, 'hot_test_dummy_mode', '0')
    with open(CONFIG_PATH, 'w') as f:
        cfg.write(f)
    print("✅ config.ini → 本番モード（back_test=0, hot_test_dummy_mode=0）に変更")


def restore_config():
    """config.ini をテスト前の状態に復元"""
    if os.path.exists(CONFIG_BACKUP_PATH):
        shutil.copy2(CONFIG_BACKUP_PATH, CONFIG_PATH)
        os.remove(CONFIG_BACKUP_PATH)
        print("✅ config.ini を元に戻しました")
    else:
        print("⚠️  バックアップが見つかりません。config.ini を手動確認してください")


def get_exchange():
    """BitgetExchange インスタンスを生成（config.ini パッチ後）"""
    from config import Config
    # クラス変数として保持している config を再読み込み
    Config.config.read(CONFIG_PATH, encoding='utf-8_sig')
    from bitget_exchange import BitgetExchange
    exchange = BitgetExchange(
        Config.get_bitget_api_key(),
        Config.get_bitget_api_secret(),
        Config.get_bitget_api_passphrase()
    )
    return exchange


def check_position(exchange):
    """現在のポジションを確認して表示"""
    try:
        positions = exchange.exchange.fetch_positions([exchange.market])
        open_pos = [p for p in positions if float(p.get('contracts', 0) or 0) > 0]
        if open_pos:
            for p in open_pos:
                print(f"  📌 ポジション: {p['side']} {p.get('contracts', '?')} BTC @ {p.get('entryPrice', '?')} USD  未実現損益: {p.get('unrealizedPnl', '?')} USDT")
        else:
            print("  📌 オープンポジション: なし")
        return open_pos
    except Exception as e:
        print(f"  ⚠️  ポジション確認失敗: {e}")
        return []


def wait_with_countdown(seconds):
    for i in range(seconds, 0, -1):
        print(f"  ⏳ {i}秒後に決済...", end='\r')
        time.sleep(1)
    print("                        ")


def test_market_entry_exit(exchange):
    """Test 1: 成行買い → 成行決済"""
    print_sep("Test 1: 成行買い → 成行決済")

    # 現在価格取得
    current_price = exchange.fetch_ticker()
    print(f"  現在価格: {current_price:,.2f} USD")
    print(f"  注文数量: {TEST_QUANTITY} BTC（≒ {TEST_QUANTITY * current_price:,.2f} USD）")

    input("\n  ✋ Enterを押すとエントリー注文を出します（Ctrl+Cで中止）: ")

    # エントリー（成行 buy）
    print("  📤 成行買い注文を発注中...")
    entry_order = exchange.execute_entry_order('buy', TEST_QUANTITY, current_price)
    if not entry_order:
        print("  ❌ エントリー注文に失敗しました")
        return False

    print(f"  ✅ エントリー成功")
    print(f"     注文ID  : {entry_order.get('id', 'N/A')}")
    print(f"     約定価格: {entry_order.get('average', 'N/A')} USD")
    print(f"     ステータス: {entry_order.get('status', 'N/A')}")

    # ポジション確認
    time.sleep(1)
    check_position(exchange)

    # 待機
    wait_with_countdown(WAIT_BEFORE_EXIT)

    # 決済（成行 sell, reduceOnly）
    print("  📤 成行決済注文を発注中...")
    exit_order = exchange.execute_exit_order('sell', TEST_QUANTITY)
    if not exit_order:
        print("  ❌ 決済注文に失敗しました → Bitgetで手動決済してください！")
        return False

    print(f"  ✅ 決済成功")
    print(f"     注文ID  : {exit_order.get('id', 'N/A')}")
    print(f"     約定価格: {exit_order.get('average', 'N/A')} USD")
    print(f"     ステータス: {exit_order.get('status', 'N/A')}")

    time.sleep(1)
    check_position(exchange)
    return True


def test_limit_entry_market_exit(exchange):
    """Test 2: 指値買い（現在値+offset%） → 成行決済"""
    print_sep("Test 2: 指値買い（現在値より上）→ 成行決済")

    # 現在価格取得
    current_price = exchange.fetch_ticker()
    limit_price = round(current_price * (1 + LIMIT_ORDER_OFFSET / 100), 2)
    print(f"  現在価格: {current_price:,.2f} USD")
    print(f"  指値価格: {limit_price:,.2f} USD（+{LIMIT_ORDER_OFFSET}%、即時約定を狙う）")
    print(f"  注文数量: {TEST_QUANTITY} BTC（≒ {TEST_QUANTITY * current_price:,.2f} USD）")
    print(f"  ※ 指値価格が現在値より高いため、市場価格で即時約定が期待されます")

    input("\n  ✋ Enterを押すと指値買い注文を出します（Ctrl+Cで中止）: ")

    # 指値 buy 注文（直接ccxtで発注）
    print("  📤 指値買い注文を発注中...")
    try:
        entry_order = exchange.exchange.create_limit_order(
            symbol=exchange.market,
            side='buy',
            amount=TEST_QUANTITY,
            price=limit_price,
            params={'timeout': 10000}
        )
    except Exception as e:
        print(f"  ❌ 指値注文失敗: {e}")
        return False

    order_id = entry_order.get('id')
    print(f"  ✅ 指値注文発注成功")
    print(f"     注文ID  : {order_id}")
    print(f"     指値価格: {limit_price:,.2f} USD")
    print(f"     ステータス: {entry_order.get('status', 'N/A')}")

    # 約定確認（最大10秒待機）
    print("  ⏳ 約定確認中（最大10秒）...")
    filled_order = None
    for i in range(10):
        time.sleep(1)
        try:
            checked = exchange.exchange.fetch_order(order_id, exchange.market)
            status = checked.get('status', 'unknown')
            filled = checked.get('filled', 0) or 0
            print(f"     {i+1}秒経過: status={status}, filled={filled}")
            if status == 'closed':
                filled_order = checked
                break
        except Exception as e:
            print(f"     注文確認失敗: {e}")

    if not filled_order:
        # 未約定ならキャンセル
        print("\n  ⚠️  10秒経過しても未約定です。注文をキャンセルします...")
        try:
            exchange.exchange.cancel_order(order_id, exchange.market)
            print("  ✅ キャンセル完了")
        except Exception as e:
            print(f"  ⚠️  キャンセル失敗（既に約定済みの可能性）: {e}")
        check_position(exchange)
        # ポジションあれば決済
        open_pos = [p for p in exchange.exchange.fetch_positions([exchange.market])
                    if float(p.get('contracts', 0) or 0) > 0]
        if open_pos:
            print("  📌 ポジションが残っています。成行決済を試みます...")
            exit_order = exchange.execute_exit_order('sell', TEST_QUANTITY)
            if not exit_order:
                print("  ❌ 決済失敗 → Bitgetで手動決済してください！")
                return False
            print("  ✅ 決済完了")
        return False

    print(f"\n  ✅ 約定確認成功")
    print(f"     約定価格: {filled_order.get('average', 'N/A')} USD")

    # ポジション確認
    check_position(exchange)

    # 待機
    wait_with_countdown(WAIT_BEFORE_EXIT)

    # 決済（成行 sell, reduceOnly）
    print("  📤 成行決済注文を発注中...")
    exit_order = exchange.execute_exit_order('sell', TEST_QUANTITY)
    if not exit_order:
        print("  ❌ 決済注文に失敗しました → Bitgetで手動決済してください！")
        return False

    print(f"  ✅ 決済成功")
    print(f"     注文ID  : {exit_order.get('id', 'N/A')}")
    print(f"     約定価格: {exit_order.get('average', 'N/A')} USD")
    print(f"     ステータス: {exit_order.get('status', 'N/A')}")

    time.sleep(1)
    check_position(exchange)
    return True


def main():
    print_sep("Bitget 本番注文テスト")
    print("  ⚠️  このテストは実際の資金を使用します")
    print("  ⚠️  Bitgetダッシュボードを開いて監視しながら実行してください")
    print(f"\n  テストパラメータ:")
    print(f"    注文数量    : {TEST_QUANTITY} BTC")
    print(f"    決済待機    : {WAIT_BEFORE_EXIT} 秒")
    print(f"    指値オフセット: +{LIMIT_ORDER_OFFSET}%（Test 2）")

    confirm = input("\n  続けますか？ (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("  中止しました")
        return

    # config.ini をバックアップして本番モードに変更
    patch_config_for_live()

    try:
        exchange = get_exchange()

        # 残高確認
        print_sep("事前確認: 残高")
        balance = exchange.get_account_balance()
        print(f"  残高: {balance}")

        # ==== Test 1: 成行買い → 成行決済 ====
        result1 = test_market_entry_exit(exchange)
        if result1:
            print("\n  🎉 Test 1: PASS")
        else:
            print("\n  ❌ Test 1: FAIL")

        time.sleep(2)

        # ==== Test 2: 指値買い → 成行決済 ====
        do_test2 = input("\n  Test 2（指値買い→成行決済）を実行しますか？ (yes/no): ").strip().lower()
        if do_test2 == 'yes':
            result2 = test_limit_entry_market_exit(exchange)
            if result2:
                print("\n  🎉 Test 2: PASS")
            else:
                print("\n  ❌ Test 2: FAIL（キャンセルまたは未約定）")
        else:
            print("  Test 2 をスキップしました")

        print_sep("テスト完了")
        print("  Bitgetダッシュボードでポジションが残っていないことを確認してください")

    except KeyboardInterrupt:
        print("\n\n  ⛔ 中断されました！")
        print("  ⚠️  Bitgetダッシュボードでオープンポジションを確認・手動決済してください！")
    except Exception as e:
        print(f"\n  ❌ 予期しないエラー: {e}")
        print("  ⚠️  Bitgetダッシュボードでオープンポジションを確認・手動決済してください！")
        raise
    finally:
        restore_config()


if __name__ == '__main__':
    main()
