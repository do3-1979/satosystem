"""
bitget_exchange.py のレグレッションテスト

BitgetExchange クラスの主要メソッド存在確認・初期化モード・ダミー動作検証
本番で実際に呼ばれる全メソッドをカバーする。
対象メソッド:
  - get_account_balance / get_account_balance_total
  - execute_entry_order / execute_exit_order
  - fetch_ohlcv / fetch_latest_ohlcv / fetch_ticker
  - get_market_symbol
  - fetchCurrencies=False オプション
  - reduceOnly=True (決済注文で逆張りポジション開設防止)
  - execute_exit_order を EXIT時に呼び出す bot.execute_order の振り分け
  - 初期化モードフラグ / passphrase パラメータ
"""

import os
import sys
import json
import inspect
from unittest.mock import patch, MagicMock
from datetime import datetime

# sys.path 設定
WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(WORKSPACE_ROOT, "src")
sys.path.insert(0, SRC_DIR)


# -------------------------------------------------------------------
# ピンポイントヘルパー: BitgetExchangeをバックテストモードでインスタンス化
# -------------------------------------------------------------------
def _make_bitget_backtest():
    """back_test=1 モードの BitgetExchange インスタンスを返す"""
    from bitget_exchange import BitgetExchange
    with patch("bitget_exchange.Config") as mock_cfg:
        mock_cfg.get_back_test_mode.return_value = 1
        mock_cfg.get_hot_test_dummy_mode.return_value = 1
        mock_cfg.get_time_frame.return_value = 240
        mock_cfg.get_market.return_value = "BTC/USDT"
        mock_cfg.get_server_retry_wait.return_value = 120
        mock_cfg.get_entry_slippage.return_value = 0.5
        with patch("bitget_exchange.ccxt") as mock_ccxt:
            mock_ccxt.bitget.return_value = MagicMock()
            ex = BitgetExchange("test_key", "test_secret", "test_pass")
    return ex


def _make_bitget_papertrading():
    """back_test=0, hot_test_dummy_mode=1 モードの BitgetExchange インスタンスを返す"""
    from bitget_exchange import BitgetExchange
    with patch("bitget_exchange.Config") as mock_cfg:
        mock_cfg.get_back_test_mode.return_value = 0
        mock_cfg.get_hot_test_dummy_mode.return_value = 1
        mock_cfg.get_time_frame.return_value = 240
        mock_cfg.get_market.return_value = "BTC/USDT"
        mock_cfg.get_server_retry_wait.return_value = 120
        mock_cfg.get_entry_slippage.return_value = 0.5
        with patch("bitget_exchange.ccxt") as mock_ccxt:
            mock_ccxt.bitget.return_value = MagicMock()
            ex = BitgetExchange("test_key", "test_secret", "test_pass")
    return ex


# -------------------------------------------------------------------
# テスト
# -------------------------------------------------------------------

def test_bitget_exchange_exists():
    """BitgetExchange クラスが存在することを確認"""
    try:
        from bitget_exchange import BitgetExchange
        assert BitgetExchange is not None
        return True, "✅ BitgetExchange クラスが存在"
    except ImportError as e:
        return False, f"❌ インポート失敗: {e}"


def test_production_methods_exist():
    """**本番実際に呼ばれる**全メソッドの存在確認"""
    from bitget_exchange import BitgetExchange
    required = [
        "__init__",
        "get_account_balance",
        "get_account_balance_total",
        "execute_entry_order",
        "execute_exit_order",
        "fetch_ohlcv",
        "fetch_latest_ohlcv",
        "fetch_ticker",
        "get_market_symbol",
        "_fetch_ticker_from_api",
        "_fetch_balance_from_api",
        "_fetch_futures_union_available",   # 合算証拠金モード対応
        "_execute_market_order",
        "_execute_market_order_final",
    ]
    missing = [m for m in required if not hasattr(BitgetExchange, m)]
    if missing:
        return False, f"❌ 欠落メソッド: {missing}"
    return True, f"✅ 本番呼び出しメソッド {len(required)}件 全て存在"


def test_init_passphrase_param():
    """__init__ に passphrase パラメータがあるか確認 (Bitget必須)"""
    from bitget_exchange import BitgetExchange
    sig = inspect.signature(BitgetExchange.__init__)
    params = list(sig.parameters.keys())
    assert "passphrase" in params, f"❌ passphrase パラメータなし: {params}"
    return True, f"✅ __init__ passphrase パラメータあり ({len(params)-1}個)"


def test_init_backtest_mode_flags():
    """back_test=1 時の初期化フラグが正しいか確認"""
    ex = _make_bitget_backtest()
    assert ex.is_dummy_mode is True,    f"is_dummy_mode={ex.is_dummy_mode}"
    assert ex.is_backtest_mode is True,  f"is_backtest_mode={ex.is_backtest_mode}"
    assert ex.is_papertrading_mode is False
    assert ex.is_live_trading_mode is False
    return True, "✅ back_test=1 初期化フラグ OK"


def test_init_papertrading_mode_flags():
    """back_test=0, hot_test_dummy=1 時のフラグ確認"""
    ex = _make_bitget_papertrading()
    assert ex.is_dummy_mode is False
    assert ex.is_backtest_mode is False
    assert ex.is_papertrading_mode is True
    assert ex.is_live_trading_mode is False
    return True, "✅ papertradingモードフラグ OK"


def test_fetchcurrencies_disabled():
    """両モードで fetchCurrencies=False が設定されているか確認"""
    from bitget_exchange import BitgetExchange
    captured_opts = {}

    def capture_init(opts):
        captured_opts.update(opts)
        return MagicMock()

    for back_test_val in [0, 1]:
        with patch("bitget_exchange.Config") as mock_cfg:
            mock_cfg.get_back_test_mode.return_value = back_test_val
            mock_cfg.get_hot_test_dummy_mode.return_value = 1
            mock_cfg.get_time_frame.return_value = 240
            mock_cfg.get_market.return_value = "BTC/USDT"
            mock_cfg.get_server_retry_wait.return_value = 120
            mock_cfg.get_entry_slippage.return_value = 0.5
            with patch("bitget_exchange.ccxt") as mock_ccxt:
                mock_ccxt.bitget.side_effect = capture_init
                try:
                    BitgetExchange("k", "s", "p")
                except Exception:
                    pass
        opts = captured_opts.get("options", {})
        assert opts.get("fetchCurrencies") is False, \
            f"❌ back_test={back_test_val}: fetchCurrencies={opts.get('fetchCurrencies')}"

    return True, "✅ fetchCurrencies=False が両モードで設定済み"


def test_get_account_balance_dummy():
    """ダミー残高返協構造を確認"""
    for ex in [_make_bitget_backtest(), _make_bitget_papertrading()]:
        bal = ex.get_account_balance()
        assert "USDT" in bal, f"❌ USDTキーなし: {bal}"
        assert "total" in bal["USDT"]
        assert bal["USDT"]["total"] > 0
    return True, "✅ get_account_balance ダミー返協 OK"


def test_get_account_balance_total_dummy():
    """ダミーモードで float を返すか確認"""
    for ex in [_make_bitget_backtest(), _make_bitget_papertrading()]:
        total = ex.get_account_balance_total()
        assert isinstance(total, float), f"❌ float以外: {type(total)}"
        assert total > 0
    return True, "✅ get_account_balance_total ダミー返協 OK"


def test_fetch_ticker_backtest():
    """バックテスト時にダミー価格（float）を返すか確認"""
    ex = _make_bitget_backtest()
    with patch("bitget_exchange.Config") as mock_cfg:
        mock_cfg.get_back_test_mode.return_value = 1
        mock_cfg.get_market.return_value = "BTC/USDT"
        ex.is_backtest_mode = True
        price = ex.fetch_ticker()
    assert isinstance(price, (int, float)), f"❌ 数値以外: {type(price)}"
    assert price > 0
    return True, f"✅ fetch_ticker backtest ダミー価格={price:.0f} OK"


def test_execute_entry_order_dummy():
    """バックテスト時の execute_entry_order が True を返すか確認"""
    ex = _make_bitget_backtest()
    result = ex.execute_entry_order(side="buy", quantity=0.001, current_price=80000.0)
    assert result is True, f"❌ ダミーエントリーが True でない: {result}"
    return True, "✅ execute_entry_order バックテストダミー OK"


def test_execute_entry_order_papertrading_no_real_api():
    """【重要】ペーパートレード時に execute_entry_order が実APIを呼ばないか確認"""
    ex = _make_bitget_papertrading()
    # 実APIが呼ばれたら AssertionError になるよう create_market_order を監視
    ex.exchange.create_market_order = MagicMock(side_effect=AssertionError("❌ ペーパーモードで実APIが呼ばれました"))
    ex.exchange.create_limit_order  = MagicMock(side_effect=AssertionError("❌ ペーパーモードで実APIが呼ばれました"))
    result = ex.execute_entry_order(side="buy", quantity=0.001, current_price=80000.0)
    assert result is True, f"❌ ペーパートレードエントリーが True でない: {result}"
    assert not ex.exchange.create_market_order.called
    assert not ex.exchange.create_limit_order.called
    return True, "✅ execute_entry_order ペーパートレード → 実APIを呼ばない OK"


def test_execute_exit_order_dummy():
    """バックテスト時の execute_exit_order が True を返すか確認"""
    ex = _make_bitget_backtest()
    result = ex.execute_exit_order(side="sell", quantity=0.001)
    assert result is True, f"❌ ダミー決済が True でない: {result}"
    return True, "✅ execute_exit_order バックテストダミー OK"


def test_execute_exit_order_papertrading_no_real_api():
    """【重要】ペーパートレード時に execute_exit_order が実APIを呼ばないか確認"""
    ex = _make_bitget_papertrading()
    ex.exchange.create_market_order = MagicMock(side_effect=AssertionError("❌ ペーパーモードで実APIが呼ばれました"))
    ex.exchange.create_limit_order  = MagicMock(side_effect=AssertionError("❌ ペーパーモードで実APIが呼ばれました"))
    result = ex.execute_exit_order(side="sell", quantity=0.001)
    assert result is True, f"❌ ペーパートレード決済が True でない: {result}"
    assert not ex.exchange.create_market_order.called
    assert not ex.exchange.create_limit_order.called
    return True, "✅ execute_exit_order ペーパートレード → 実APIを呼ばない OK"


def test_execute_exit_order_reduceonly():
    """ライブモードの execute_exit_order が reduceOnly=True で呼び出すか確認
    (決済注文が逆張りポジション開設を防ぐ最重要テスト)"""
    from bitget_exchange import BitgetExchange
    with patch("bitget_exchange.Config") as mock_cfg:
        mock_cfg.get_back_test_mode.return_value = 0
        mock_cfg.get_hot_test_dummy_mode.return_value = 0  # LIVE
        mock_cfg.get_time_frame.return_value = 240
        mock_cfg.get_market.return_value = "BTC/USDT"
        mock_cfg.get_server_retry_wait.return_value = 120
        mock_cfg.get_entry_slippage.return_value = 0.5
        with patch("bitget_exchange.ccxt") as mock_ccxt:
            mock_exchange = MagicMock()
            mock_ccxt.bitget.return_value = mock_exchange
            ex = BitgetExchange("key", "secret", "pass")

    mock_order = {"id": "test123", "status": "closed"}
    ex.exchange.create_market_order.return_value = mock_order

    ex.execute_exit_order(side="sell", quantity=0.001)

    assert ex.exchange.create_market_order.called, "❌ create_market_orderが呼ばれていません"
    call_args = ex.exchange.create_market_order.call_args
    # keyword引数 params を取得
    kwargs = call_args[1] if call_args[1] else {}
    args = call_args[0] if call_args[0] else ()
    params = kwargs.get("params", args[3] if len(args) > 3 else {})
    assert params.get("reduceOnly") is True, \
        f"❌ reduceOnly=True が設定されていません: params={params}"
    return True, "✅ execute_exit_order に reduceOnly=True 設定済み"


def test_get_market_symbol():
    """マーケットシンボルを正しく返すか確認"""
    ex = _make_bitget_backtest()
    sym = ex.get_market_symbol()
    assert isinstance(sym, str) and len(sym) > 0, f"❌ 空文字列: {sym}"
    return True, f"✅ get_market_symbol={sym}"


def test_get_account_balance_total_union_mode():
    """合算証拠金モード（USDT=0、BTC担保）時に unionAvailable を返すか確認"""
    from bitget_exchange import BitgetExchange
    with patch("bitget_exchange.Config") as mock_cfg:
        mock_cfg.get_back_test_mode.return_value = 0
        mock_cfg.get_hot_test_dummy_mode.return_value = 0
        mock_cfg.get_time_frame.return_value = 240
        mock_cfg.get_market.return_value = "BTC/USDT"
        mock_cfg.get_server_retry_wait.return_value = 120
        mock_cfg.get_entry_slippage.return_value = 0.5
        with patch("bitget_exchange.ccxt") as mock_ccxt:
            mock_exchange = MagicMock()
            mock_ccxt.bitget.return_value = mock_exchange
            ex = BitgetExchange("key", "secret", "pass")

    # fetchBalance は USDT=0 を返す（合算証拠金モード）
    mock_exchange.fetchBalance.return_value = {
        'USDT': {'total': 0.0, 'used': 0.0, 'free': 0.0}
    }
    # V2 Mix API は unionAvailable=69.9 を返す
    mock_exchange.privateMixGetV2MixAccountAccounts.return_value = {
        'data': [{'assetMode': 'union', 'unionAvailable': '69.90', 'available': '0'}]
    }

    total = ex.get_account_balance_total()
    assert abs(total - 69.90) < 0.01, f"❌ unionAvailable が反映されていません: {total}"
    return True, f"✅ 合算証拠金モード: get_account_balance_total={total:.2f} USDT (unionAvailable)"


def test_get_account_balance_union_mode():
    """合算証拠金モード時に get_account_balance が USDT構造で unionAvailable を返すか確認"""
    from bitget_exchange import BitgetExchange
    with patch("bitget_exchange.Config") as mock_cfg:
        mock_cfg.get_back_test_mode.return_value = 0
        mock_cfg.get_hot_test_dummy_mode.return_value = 0
        mock_cfg.get_time_frame.return_value = 240
        mock_cfg.get_market.return_value = "BTC/USDT"
        mock_cfg.get_server_retry_wait.return_value = 120
        mock_cfg.get_entry_slippage.return_value = 0.5
        with patch("bitget_exchange.ccxt") as mock_ccxt:
            mock_exchange = MagicMock()
            mock_ccxt.bitget.return_value = mock_exchange
            ex = BitgetExchange("key", "secret", "pass")

    mock_exchange.fetchBalance.return_value = {
        'USDT': {'total': 0.0, 'used': 0.0, 'free': 0.0}
    }
    mock_exchange.privateMixGetV2MixAccountAccounts.return_value = {
        'data': [{'assetMode': 'union', 'unionAvailable': '69.90', 'available': '0'}]
    }

    bal = ex.get_account_balance()
    usdt_total = bal['USDT']['total']
    assert abs(usdt_total - 69.90) < 0.01, f"❌ USDT total={usdt_total}"
    return True, f"✅ 合算証拠金モード: get_account_balance USDT.total={usdt_total:.2f} OK"


def test_get_open_position_dummy():
    """ダミー/バックテスト時に get_open_position が None を返すか確認"""
    for ex in [_make_bitget_backtest(), _make_bitget_papertrading()]:
        pos = ex.get_open_position()
        assert pos is None, f"❌ ダミーモードでポジションが返った: {pos}"
    return True, "✅ get_open_position ダミーモード → None OK"


def test_get_position_quantity_dummy():
    """ダミー/バックテスト時に get_position_quantity が 0.0 を返すか確認"""
    for ex in [_make_bitget_backtest(), _make_bitget_papertrading()]:
        qty = ex.get_position_quantity()
        assert qty == 0.0, f"❌ ダミーモードで非ゼロ返却: {qty}"
    return True, "✅ get_position_quantity ダミーモード → 0.0 OK"


def test_get_position_quantity_live_api():
    """ライブモード時に get_position_quantity が fetchPositions を呼び API経由で取得するか確認"""
    from bitget_exchange import BitgetExchange
    with patch("bitget_exchange.Config") as mock_cfg:
        mock_cfg.get_back_test_mode.return_value = 0
        mock_cfg.get_hot_test_dummy_mode.return_value = 0
        mock_cfg.get_time_frame.return_value = 240
        mock_cfg.get_market.return_value = "BTC/USDT"
        mock_cfg.get_server_retry_wait.return_value = 120
        mock_cfg.get_entry_slippage.return_value = 0.5
        with patch("bitget_exchange.ccxt") as mock_ccxt:
            mock_exchange = MagicMock()
            mock_ccxt.bitget.return_value = mock_exchange
            ex = BitgetExchange("key", "secret", "pass")

    # ポジションあり(BTC 0.001 LONG)を模擬
    mock_exchange.fetchPositions.return_value = [
        {"symbol": "BTC/USDT:USDT", "side": "long", "contracts": 0.001, "entryPrice": 80000.0}
    ]

    qty = ex.get_position_quantity()
    assert mock_exchange.fetchPositions.called, "❌ fetchPositions が呼ばれていません"
    assert abs(qty - 0.001) < 1e-9, f"❌ 期待 0.001、実際 {qty}"
    return True, f"✅ get_position_quantity ライブAPI呼び出し OK (qty={qty})"


def test_bot_execute_order_routing():
    """【重要】bot.execute_order が
       ENTRY/ADD → execute_entry_order、
       EXIT    → execute_exit_order
    を呼び分けるか確認"""
    from bot import Bot
    from unittest.mock import patch, MagicMock, call

    mock_bot = MagicMock(spec=Bot)
    mock_bot.execute_order = Bot.execute_order.__get__(mock_bot, Bot)

    mock_exchange = MagicMock()
    mock_exchange.execute_entry_order.return_value = True
    mock_exchange.execute_exit_order.return_value = True
    mock_bot.exchange = mock_exchange

    mock_pdm = MagicMock()
    mock_pdm.get_ticker.return_value = 80000.0
    mock_bot.price_data_management = mock_pdm

    mock_alert = MagicMock()
    mock_bot.alert = mock_alert

    mock_logger = MagicMock()
    mock_bot.logger = mock_logger

    order = {"symbol": "BTC/USDT", "side": "BUY", "quantity": 0.001,
             "order_type": "market", "price": 0}

    # ENTRY → execute_entry_order
    mock_bot.execute_order(order, decision="ENTRY")
    assert mock_exchange.execute_entry_order.called, "❌ ENTRY時に execute_entry_order が呼ばれませんでした"
    mock_exchange.reset_mock()

    # ADD → execute_entry_order
    mock_bot.execute_order(order, decision="ADD")
    assert mock_exchange.execute_entry_order.called, "❌ ADD時に execute_entry_order が呼ばれませんでした"
    mock_exchange.reset_mock()

    # EXIT → execute_exit_order
    order_exit = {"symbol": "BTC/USDT", "side": "SELL", "quantity": 0.001,
                  "order_type": "market", "price": 0}
    mock_bot.execute_order(order_exit, decision="EXIT")
    assert mock_exchange.execute_exit_order.called, "❌ EXIT時に execute_exit_order が呼ばれませんでした"
    assert not mock_exchange.execute_entry_order.called, "❌ EXIT時に execute_entry_order が呼ばれてしまいました"

    return True, "✅ bot.execute_order ENTRY/ADD→entry / EXIT→exit 振り分け OK"


# -------------------------------------------------------------------
# テストランナー
# -------------------------------------------------------------------

def run_all_tests():
    tests = [
        ("BitgetExchange クラス存在確認",              test_bitget_exchange_exists),
        ("本番呼び出しメソッド全件の存在確認",      test_production_methods_exist),
        ("passphrase パラメータ確認",             test_init_passphrase_param),
        ("back_test=1 初期化フラグ確認",          test_init_backtest_mode_flags),
        ("papertrading 初期化フラグ確認",         test_init_papertrading_mode_flags),
        ("fetchCurrencies=False 設定確認",         test_fetchcurrencies_disabled),
        ("get_account_balance ダミー動作確認",    test_get_account_balance_dummy),
        ("get_account_balance_total ダミー動作確認", test_get_account_balance_total_dummy),
        ("get_account_balance_total 合算証拠金モード確認", test_get_account_balance_total_union_mode),
        ("get_account_balance 合算証拠金モード確認",      test_get_account_balance_union_mode),
        ("fetch_ticker バックテストダミー確認",    test_fetch_ticker_backtest),
        ("execute_entry_order ダミー動作確認",    test_execute_entry_order_dummy),
        ("execute_entry_order ペーパートレード→実API不呼出確認", test_execute_entry_order_papertrading_no_real_api),
        ("execute_exit_order ダミー動作確認",     test_execute_exit_order_dummy),
        ("execute_exit_order ペーパートレード→実API不呼出確認",  test_execute_exit_order_papertrading_no_real_api),
        ("execute_exit_order reduceOnly=True確認", test_execute_exit_order_reduceonly),
        ("get_market_symbol 確認",                test_get_market_symbol),
        ("get_open_position ダミー→None確認",     test_get_open_position_dummy),
        ("get_position_quantity ダミー→0確認",    test_get_position_quantity_dummy),
        ("get_position_quantity ライブAPI確認",    test_get_position_quantity_live_api),
        ("bot.execute_order ENTRY/EXIT振り分け確認", test_bot_execute_order_routing),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            passed, message = test_func()
            results.append({"name": test_name, "passed": passed, "message": message,
                            "timestamp": datetime.now().isoformat()})
            print(message)
        except Exception as e:
            results.append({"name": test_name, "passed": False,
                            "message": f"❌ テストエラー: {e}",
                            "timestamp": datetime.now().isoformat()})
            print(f"❌ {test_name}: {e}")

    return results


if __name__ == "__main__":
    print("=" * 70)
    print("🧪 bitget_exchange.py レグレッションテスト")
    print("=" * 70)
    results = run_all_tests()

    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(results)
    print()
    print(f"📊 結果: {passed_count}/{total_count} 成功")

    RESULTS_DIR = os.path.join(WORKSPACE_ROOT, "docs/regression_test_results")
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(os.path.join(RESULTS_DIR, "test_bitget_exchange_regression.json"), "w", encoding="utf-8") as f:
        json.dump({"file": "bitget_exchange.py", "total": total_count, "passed": passed_count,
                   "results": results, "timestamp": datetime.now().isoformat()},
                  f, ensure_ascii=False, indent=2)

    sys.exit(0 if passed_count == total_count else 1)



def load_analysis():
    """analysis/bybit_exchange.json から Exchange クラスの仕様を読む (Bitget も同じ構造)"""
    with open(ANALYSIS_FILE, encoding="utf-8") as f:
        return json.load(f)


def test_bitget_exchange_exists():
    """BitgetExchange クラスが存在することを確認"""
    try:
        from bitget_exchange import BitgetExchange
        return True, f"✅ BitgetExchange クラスが存在します"
    except ImportError as e:
        return False, f"❌ BitgetExchange クラスのインポート失敗: {e}"


def test_bitget_exchange_methods():
    """BitgetExchange の主要メソッドが存在することを確認"""
    try:
        from bitget_exchange import BitgetExchange
        
        # Bybit同様の基本メソッドをチェック
        expected_methods = {
            "__init__",
            "get_account_balance",
            "get_account_balance_total",
            "fetch_ohlcv",
            "fetch_latest_ohlcv",
            "fetch_ticker",
            "execute_order",
            "execute_entry_order",
            "execute_exit_order",
            "fetch_open_orders",
            "create_limit_order",
            "cancel_order"
        }
        
        actual_methods = {m for m in dir(BitgetExchange) if not m.startswith("_") or m == "__init__"}
        
        missing = expected_methods - actual_methods
        if missing:
            return False, f"❌ 欠落メソッド: {missing}"
        
        return True, f"✅ 全メソッド({len(expected_methods)})が存在"
    except Exception as e:
        return False, f"❌ メソッド確認エラー: {e}"


def test_exchange_operations():
    """取引所操作メソッドが存在することを確認"""
    try:
        from bitget_exchange import BitgetExchange
        
        exchange_methods = [
            "get_account_balance",
            "get_account_balance_total",
            "fetch_ohlcv",
            "fetch_latest_ohlcv",
            "fetch_ticker",
            "execute_order",
            "execute_entry_order",
            "execute_exit_order"
        ]
        
        missing = []
        for method in exchange_methods:
            if not hasattr(BitgetExchange, method):
                missing.append(method)
        
        if missing:
            return False, f"❌ 欠落取引所操作メソッド: {missing}"
        
        return True, f"✅ 取引所操作メソッド({len(exchange_methods)})すべて存在"
    except Exception as e:
        return False, f"❌ 取引所操作メソッド確認エラー: {e}"


def test_bitget_exchange_init():
    """BitgetExchange.__init__ が存在することを確認"""
    try:
        from bitget_exchange import BitgetExchange
        
        if hasattr(BitgetExchange, "__init__"):
            sig = inspect.signature(BitgetExchange.__init__)
            params = list(sig.parameters.keys())
            # Bitgetは api_key, api_secret, passphrase の3つのパラメータ
            if 'passphrase' in params:
                return True, f"✅ BitgetExchange.__init__ が定義されています (パラメータ: {len(params)-1} 個、passphrase対応)"
            else:
                return False, f"❌ BitgetExchange.__init__ に passphrase パラメータがありません"
        else:
            return False, f"❌ __init__ が見つかりません"
    except Exception as e:
        return False, f"❌ __init__ 確認エラー: {e}"


def test_api_compatibility():
    """Bitget固有のAPI互換性を確認"""
    try:
        from bitget_exchange import BitgetExchange
        
        # Bitget特有のメソッド
        bitget_specific_methods = [
            "fetch_open_orders",
            "create_limit_order",
            "cancel_order"
        ]
        
        missing = []
        for method in bitget_specific_methods:
            if not hasattr(BitgetExchange, method):
                missing.append(method)
        
        if missing:
            return False, f"❌ 欠落Bitget固有メソッド: {missing}"
        
        return True, f"✅ Bitget固有メソッド({len(bitget_specific_methods)})すべて存在"
    except Exception as e:
        return False, f"❌ Bitget API互換性確認エラー: {e}"


def run_all_tests():
    """全テストを実行"""
    tests = [
        ("BitgetExchange クラス存在確認", test_bitget_exchange_exists),
        ("BitgetExchange メソッド確認", test_bitget_exchange_methods),
        ("取引所操作メソッド確認", test_exchange_operations),
        ("BitgetExchange.__init__ 確認", test_bitget_exchange_init),
        ("Bitget API互換性確認", test_api_compatibility),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            passed, message = test_func()
            results.append({
                "name": test_name,
                "passed": passed,
                "message": message,
                "timestamp": datetime.now().isoformat()
            })
            print(message)
        except Exception as e:
            results.append({
                "name": test_name,
                "passed": False,
                "message": f"❌ テスト実行エラー: {e}",
                "timestamp": datetime.now().isoformat()
            })
            print(f"❌ テスト実行エラー ({test_name}): {e}")
    
    return results


if __name__ == "__main__":
    print("=" * 70)
    print("🧪 bitget_exchange.py レグレッションテスト")
    print("=" * 70)
    results = run_all_tests()
    
    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(results)
    
    print()
    print(f"📊 結果: {passed_count}/{total_count} 成功")
    
    # 結果を JSON で保存
    RESULTS_DIR = os.path.join(WORKSPACE_ROOT, "docs/regression_test_results")
    os.makedirs(RESULTS_DIR, exist_ok=True)
    
    with open(os.path.join(RESULTS_DIR, "test_bitget_exchange_regression.json"), "w", encoding="utf-8") as f:
        json.dump({
            "file": "bitget_exchange.py",
            "total": total_count,
            "passed": passed_count,
            "results": results,
            "timestamp": datetime.now().isoformat()
        }, f, ensure_ascii=False, indent=2)
    
    sys.exit(0 if passed_count == total_count else 1)
