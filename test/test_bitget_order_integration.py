"""
Bitget 注文統合テスト（実API）

実際の Bitget API に対して以下の4ステップを検証する:
  STEP 1: BUY  指値注文を発注（現在価格の50%下 → 約定しない安全価格）
  STEP 2: BUY  注文をキャンセル
  STEP 3: SELL 指値注文を発注（現在価格の200%上 → 約定しない安全価格）
  STEP 4: SELL 注文をキャンセル

事前条件:
  - .api_key に Bitget API 認証情報が設定済みであること
  - config.ini: back_test=0, hot_test_dummy_mode=0 (本番モード)
  - Bitget アカウントにポジションがない状態を推奨

実行方法:
  cd /path/to/satosystem
  python test/test_bitget_order_integration.py

注意:
  - 本テストは実際の注文を Bitget サーバーに送信します
  - 注文はすぐにキャンセルされますが、手数料が発生する場合があります
  - 市場の急変動により稀に約定する可能性があります（価格は現在値の50%/200%に設定）
"""

import os
import sys
import time
from datetime import datetime

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(WORKSPACE_ROOT, "src")
sys.path.insert(0, SRC_DIR)

from config import Config
from bitget_exchange import BitgetExchange

# ──────────────────────────────────────────────────────────────
# 設定
# ──────────────────────────────────────────────────────────────
SYMBOL          = "BTC/USDT:USDT"   # Bitget 無期限先物シンボル
ORDER_QUANTITY  = 0.001              # 最小注文量 (BTC)
BUY_PRICE_RATIO = 0.50              # 現在価格の 50%  → 約定しない
SELL_PRICE_RATIO = 2.00             # 現在価格の 200% → 約定しない
CANCEL_WAIT_SEC = 2.0               # 発注 → キャンセルまでの待機秒数

LOG_SEP = "=" * 64


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{ts}] {msg}")


def assert_eq(label, actual, expected):
    if actual != expected:
        raise AssertionError(f"❌ {label}: 期待={expected}, 実際={actual}")
    log(f"   ✅ {label} = {actual}")


# ──────────────────────────────────────────────────────────────
# テスト実装
# ──────────────────────────────────────────────────────────────

def step_buy(exchange: BitgetExchange, buy_price: float) -> str:
    """
    STEP 1: BUY 指値注文を発注し、注文IDを返す

    Returns:
        str: 発注した注文の ID
    """
    log(f"STEP 1 ▶ BUY 指値注文発注: {ORDER_QUANTITY} BTC @ {buy_price:.2f} USDT")
    order = exchange.create_limit_order(
        symbol=SYMBOL,
        side="buy",
        amount=ORDER_QUANTITY,
        price=buy_price,
    )
    order_id = order["id"]
    log(f"   注文ID   : {order_id}")
    log(f"   ステータス: {order.get('status', 'N/A')}")
    assert order_id, "注文IDが空です"
    log("   ✅ BUY 発注成功")
    return order_id


def step_cancel_buy(exchange: BitgetExchange, order_id: str):
    """STEP 2: BUY 注文をキャンセル"""
    log(f"STEP 2 ▶ BUY 注文キャンセル: ID={order_id}")
    time.sleep(CANCEL_WAIT_SEC)
    result = exchange.cancel_order(order_id, symbol=SYMBOL)
    status = result.get("status", "")
    log(f"   キャンセル結果ステータス: {status}")
    # Bitget は status=None / canceled / cancelled のいずれかを返す
    # cancel_order が例外を投げずに返った時点でキャンセル成功と見なす
    if status and status.lower() not in ("canceled", "cancelled", "cancel"):
        log(f"   ⚠️  ステータスが想定外ですが、例外なく完了しました: {status}")
    else:
        log("   ✅ BUY キャンセル成功")


def step_sell(exchange: BitgetExchange, sell_price: float) -> str:
    """
    STEP 3: SELL 指値注文を発注し、注文IDを返す

    現在ポジションを持っていない場合、SELL 注文はショートポジション開設注文となる。
    価格を現在値の 200% に設定しているため通常は約定しない。
    """
    log(f"STEP 3 ▶ SELL 指値注文発注: {ORDER_QUANTITY} BTC @ {sell_price:.2f} USDT")
    order = exchange.create_limit_order(
        symbol=SYMBOL,
        side="sell",
        amount=ORDER_QUANTITY,
        price=sell_price,
    )
    order_id = order["id"]
    log(f"   注文ID   : {order_id}")
    log(f"   ステータス: {order.get('status', 'N/A')}")
    assert order_id, "注文IDが空です"
    log("   ✅ SELL 発注成功")
    return order_id


def step_cancel_sell(exchange: BitgetExchange, order_id: str):
    """STEP 4: SELL 注文をキャンセル"""
    log(f"STEP 4 ▶ SELL 注文キャンセル: ID={order_id}")
    time.sleep(CANCEL_WAIT_SEC)
    result = exchange.cancel_order(order_id, symbol=SYMBOL)
    status = result.get("status", "")
    log(f"   キャンセル結果ステータス: {status}")
    # Bitget は status=None / canceled / cancelled のいずれかを返す
    # cancel_order が例外を投げずに返った時点でキャンセル成功と見なす
    if status and status.lower() not in ("canceled", "cancelled", "cancel"):
        log(f"   ⚠️  ステータスが想定外ですが、例外なく完了しました: {status}")
    else:
        log("   ✅ SELL キャンセル成功")


# ──────────────────────────────────────────────────────────────
# メイン
# ──────────────────────────────────────────────────────────────

def run():
    print(LOG_SEP)
    print("🧪 Bitget 注文統合テスト（実API）")
    print(f"   シンボル  : {SYMBOL}")
    print(f"   数量      : {ORDER_QUANTITY} BTC")
    print(f"   BUY価格比 : 現在値 × {BUY_PRICE_RATIO} (50%下)")
    print(f"   SELL価格比: 現在値 × {SELL_PRICE_RATIO} (200%上)")
    print(LOG_SEP)

    # ── 接続確認 ──────────────────────────────────────────────
    log("接続: BitgetExchange を初期化")
    exchange = BitgetExchange(
        api_key    = Config.get_api_key(),
        api_secret = Config.get_api_secret(),
        passphrase = Config.get_api_passphrase(),
    )
    if not exchange.is_live_trading_mode:
        print("⚠️  本テストは live_trading_mode (back_test=0, hot_test_dummy_mode=0) で実行してください")
        print("   現在のモード: "
              f"backtest={exchange.is_backtest_mode}, "
              f"papertrading={exchange.is_papertrading_mode}")
        sys.exit(1)

    # ── 現在価格を取得 ──────────────────────────────────────────
    log("現在の BTC/USDT 価格を取得")
    current_price = exchange.fetch_ticker()
    log(f"   現在価格: {current_price:,.2f} USDT")

    buy_price  = round(current_price * BUY_PRICE_RATIO,  1)
    sell_price = round(current_price * SELL_PRICE_RATIO, 1)
    log(f"   BUY  指値価格: {buy_price:,.1f} USDT  (× {BUY_PRICE_RATIO})")
    log(f"   SELL 指値価格: {sell_price:,.1f} USDT (× {SELL_PRICE_RATIO})")
    print(LOG_SEP)

    results = {}

    # ── STEP 1: BUY 発注 ────────────────────────────────────────
    try:
        buy_order_id = step_buy(exchange, buy_price)
        results["STEP1_buy"] = ("PASS", buy_order_id)
    except Exception as e:
        log(f"   ❌ BUY 発注失敗: {e}")
        results["STEP1_buy"] = ("FAIL", str(e))
        buy_order_id = None
    print()

    # ── STEP 2: BUY キャンセル ───────────────────────────────────
    if buy_order_id:
        try:
            step_cancel_buy(exchange, buy_order_id)
            results["STEP2_cancel_buy"] = ("PASS", buy_order_id)
        except Exception as e:
            log(f"   ❌ BUY キャンセル失敗: {e}")
            results["STEP2_cancel_buy"] = ("FAIL", str(e))
    else:
        log("STEP 2 ▶ SKIP (STEP 1 が失敗したためスキップ)")
        results["STEP2_cancel_buy"] = ("SKIP", "")
    print()

    # ── STEP 3: SELL 発注 ───────────────────────────────────────
    try:
        sell_order_id = step_sell(exchange, sell_price)
        results["STEP3_sell"] = ("PASS", sell_order_id)
    except Exception as e:
        log(f"   ❌ SELL 発注失敗: {e}")
        results["STEP3_sell"] = ("FAIL", str(e))
        sell_order_id = None
    print()

    # ── STEP 4: SELL キャンセル ──────────────────────────────────
    if sell_order_id:
        try:
            step_cancel_sell(exchange, sell_order_id)
            results["STEP4_cancel_sell"] = ("PASS", sell_order_id)
        except Exception as e:
            log(f"   ❌ SELL キャンセル失敗: {e}")
            results["STEP4_cancel_sell"] = ("FAIL", str(e))
    else:
        log("STEP 4 ▶ SKIP (STEP 3 が失敗したためスキップ)")
        results["STEP4_cancel_sell"] = ("SKIP", "")
    print()

    # ── 結果サマリー ────────────────────────────────────────────
    print(LOG_SEP)
    print("📊 テスト結果サマリー")
    print(LOG_SEP)
    labels = {
        "STEP1_buy":         "STEP 1  BUY  発注",
        "STEP2_cancel_buy":  "STEP 2  BUY  キャンセル",
        "STEP3_sell":        "STEP 3  SELL 発注",
        "STEP4_cancel_sell": "STEP 4  SELL キャンセル",
    }
    all_pass = True
    for key, label in labels.items():
        status, detail = results[key]
        icon = {"PASS": "✅", "FAIL": "❌", "SKIP": "⏭️ "}.get(status, "?")
        print(f"  {icon} {label:30s}  {status}  {detail}")
        if status == "FAIL":
            all_pass = False

    print(LOG_SEP)
    if all_pass:
        print("🎉 全ステップ成功")
    else:
        print("💥 失敗したステップがあります")
    print(LOG_SEP)
    return all_pass


if __name__ == "__main__":
    ok = run()
    sys.exit(0 if ok else 1)
