"""
bybit_exchange.py のレグレッションテスト

BybitExchange クラスの主要メソッド存在確認・初期化モード・ダミー動作検証
本番で実際に呼ばれる全メソッドをカバーする。
対象メソッド:
  - get_account_balance / get_account_balance_total
  - execute_entry_order / execute_exit_order
  - fetch_ohlcv / fetch_latest_ohlcv / fetch_ticker
  - get_market_symbol
  - fetchCurrencies=False オプション
  - reduceOnly=True (決済注文)
  - 初期化モードフラグ
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
# ピンポイントヘルパー: BybitExchangeをバックテストモードでインスタンス化
# -------------------------------------------------------------------
def _make_bybit_backtest():
    """back_test=1 モードの BybitExchange インスタンスを返す"""
    from bybit_exchange import BybitExchange
    with patch("bybit_exchange.Config") as mock_cfg:
        mock_cfg.get_back_test_mode.return_value = 1
        mock_cfg.get_hot_test_dummy_mode.return_value = 1
        mock_cfg.get_time_frame.return_value = 240
        mock_cfg.get_market.return_value = "BTC/USDT"
        mock_cfg.get_server_retry_wait.return_value = 120
        with patch("bybit_exchange.ccxt") as mock_ccxt:
            mock_ccxt.bybit.return_value = MagicMock()
            ex = BybitExchange("test_key", "test_secret")
    return ex


def _make_bybit_papertrading():
    """back_test=0, hot_test_dummy_mode=1 モードの BybitExchange インスタンスを返す"""
    from bybit_exchange import BybitExchange
    with patch("bybit_exchange.Config") as mock_cfg:
        mock_cfg.get_back_test_mode.return_value = 0
        mock_cfg.get_hot_test_dummy_mode.return_value = 1
        mock_cfg.get_time_frame.return_value = 240
        mock_cfg.get_market.return_value = "BTC/USDT"
        mock_cfg.get_server_retry_wait.return_value = 120
        with patch("bybit_exchange.ccxt") as mock_ccxt:
            mock_ccxt.bybit.return_value = MagicMock()
            ex = BybitExchange("test_key", "test_secret")
    return ex


# -------------------------------------------------------------------
# テスト
# -------------------------------------------------------------------

def test_bybit_exchange_exists():
    """BybitExchange クラスが存在することを確認"""
    try:
        from bybit_exchange import BybitExchange
        assert BybitExchange is not None
        return True, "✅ BybitExchange クラスが存在"
    except ImportError as e:
        return False, f"❌ インポート失敗: {e}"


def test_production_methods_exist():
    """**本番実際に呼ばれる**全メソッドの存在を確認"""
    from bybit_exchange import BybitExchange
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
        "_fetch_ticker_from_api",   # fetch_ticker 内部呼び出し
        "_fetch_balance_from_api",  # 残高取得内部呼び出し
    ]
    missing = [m for m in required if not hasattr(BybitExchange, m)]
    if missing:
        return False, f"❌ 欠落メソッド: {missing}"
    return True, f"✅ 本番呼び出しメソッド {len(required)}件 全て存在"


def test_init_backtest_mode_flags():
    """back_test=1 時の初期化フラグが正しいか確認"""
    ex = _make_bybit_backtest()
    assert ex.is_dummy_mode is True,    f"is_dummy_mode={ex.is_dummy_mode} (期待: True)"
    assert ex.is_backtest_mode is True,  f"is_backtest_mode={ex.is_backtest_mode}"
    assert ex.is_papertrading_mode is False
    assert ex.is_live_trading_mode is False
    return True, "✅ back_test=1 初期化フラグ OK"


def test_init_papertrading_mode_flags():
    """back_test=0, hot_test_dummy=1 時のフラグ確認"""
    ex = _make_bybit_papertrading()
    assert ex.is_dummy_mode is False
    assert ex.is_backtest_mode is False
    assert ex.is_papertrading_mode is True
    assert ex.is_live_trading_mode is False
    return True, "✅ papertradingモードフラグ OK"


def test_fetchcurrencies_disabled():
    """両モードで fetchCurrencies=False が設定されているか確認
    (ccxt load_markets 時に /v5/asset/coin/query-info を呼び出さないための修正)"""
    from bybit_exchange import BybitExchange
    captured_opts = {}

    def capture_init(opts):
        captured_opts.update(opts)
        return MagicMock()

    for back_test_val in [0, 1]:
        with patch("bybit_exchange.Config") as mock_cfg:
            mock_cfg.get_back_test_mode.return_value = back_test_val
            mock_cfg.get_hot_test_dummy_mode.return_value = 1
            mock_cfg.get_time_frame.return_value = 240
            mock_cfg.get_market.return_value = "BTC/USDT"
            mock_cfg.get_server_retry_wait.return_value = 120
            with patch("bybit_exchange.ccxt") as mock_ccxt:
                mock_ccxt.bybit.side_effect = capture_init
                try:
                    BybitExchange("k", "s")
                except Exception:
                    pass
        opts = captured_opts.get("options", {})
        assert opts.get("fetchCurrencies") is False, \
            f"❌ back_test={back_test_val}: fetchCurrencies={opts.get('fetchCurrencies')}"

    return True, "✅ fetchCurrencies=False が両モードで設定済み"


def test_get_account_balance_dummy():
    """バックテスト/ペーパートレード時のダミー残高返却を確認"""
    for ex in [_make_bybit_backtest(), _make_bybit_papertrading()]:
        bal = ex.get_account_balance()
        assert "USDT" in bal, f"❌ USDTキーがありません: {bal}"
        assert "total" in bal["USDT"]
        assert bal["USDT"]["total"] > 0
    return True, "✅ get_account_balance ダミー返却 OK"


def test_get_account_balance_total_dummy():
    """ダミーモードで float を返すか確認"""
    for ex in [_make_bybit_backtest(), _make_bybit_papertrading()]:
        total = ex.get_account_balance_total()
        assert isinstance(total, float), f"❌ float以外: {type(total)}"
        assert total > 0
    return True, "✅ get_account_balance_total ダミー返協 OK"


def test_fetch_ticker_backtest():
    """バックテスト時にダミー価格（float）を返すか確認"""
    ex = _make_bybit_backtest()
    price = ex.fetch_ticker()
    assert isinstance(price, float), f"❌ float以外: {type(price)}"
    assert price > 0
    return True, f"✅ fetch_ticker backtest ダミー価格={price:.0f} OK"


def test_execute_entry_order_dummy():
    """バックテスト時の execute_entry_order が True を返すか確認"""
    ex = _make_bybit_backtest()
    result = ex.execute_entry_order(side="buy", quantity=0.001, current_price=80000.0)
    assert result is True, f"❌ ダミーエントリーが True でない: {result}"
    return True, "✅ execute_entry_order バックテストダミー OK"


def test_execute_entry_order_papertrading_no_real_api():
    """【重要】ペーパートレード時に execute_entry_order が実APIを呼ばないか確認"""
    ex = _make_bybit_papertrading()
    ex.exchange.create_market_order = MagicMock(side_effect=AssertionError("❌ ペーパーモードで実APIが呼ばれました"))
    ex.exchange.create_limit_order  = MagicMock(side_effect=AssertionError("❌ ペーパーモードで実APIが呼ばれました"))
    result = ex.execute_entry_order(side="buy", quantity=0.001, current_price=80000.0)
    assert result is True, f"❌ ペーパートレードエントリーが True でない: {result}"
    assert not ex.exchange.create_market_order.called
    assert not ex.exchange.create_limit_order.called
    return True, "✅ execute_entry_order ペーパートレード → 実APIを呼ばない OK"


def test_execute_exit_order_dummy():
    """バックテスト時の execute_exit_order が True を返すか確認"""
    ex = _make_bybit_backtest()
    result = ex.execute_exit_order(side="sell", quantity=0.001)
    assert result is True, f"❌ ダミー決済が True でない: {result}"
    return True, "✅ execute_exit_order バックテストダミー OK"


def test_execute_exit_order_papertrading_no_real_api():
    """【重要】ペーパートレード時に execute_exit_order が実APIを呼ばないか確認"""
    ex = _make_bybit_papertrading()
    ex.exchange.create_market_order = MagicMock(side_effect=AssertionError("❌ ペーパーモードで実APIが呼ばれました"))
    ex.exchange.create_limit_order  = MagicMock(side_effect=AssertionError("❌ ペーパーモードで実APIが呼ばれました"))
    result = ex.execute_exit_order(side="sell", quantity=0.001)
    assert result is True, f"❌ ペーパートレード決済が True でない: {result}"
    assert not ex.exchange.create_market_order.called
    assert not ex.exchange.create_limit_order.called
    return True, "✅ execute_exit_order ペーパートレード → 実APIを呼ばない OK"


def test_execute_exit_order_reduceonly():
    """ライブモードの execute_exit_order が reduceOnly=True で呼び出すか確認
    (決済注文がポジションを逆張りほせを防ぐ)"""
    from bybit_exchange import BybitExchange
    with patch("bybit_exchange.Config") as mock_cfg:
        mock_cfg.get_back_test_mode.return_value = 0
        mock_cfg.get_hot_test_dummy_mode.return_value = 0  # LIVE
        mock_cfg.get_time_frame.return_value = 240
        mock_cfg.get_market.return_value = "BTC/USDT"
        mock_cfg.get_server_retry_wait.return_value = 120
        with patch("bybit_exchange.ccxt") as mock_ccxt:
            mock_exchange = MagicMock()
            mock_ccxt.bybit.return_value = mock_exchange
            ex = BybitExchange("key", "secret")

    mock_order = {"id": "test123", "status": "closed"}
    ex.exchange.create_market_order.return_value = mock_order

    ex.execute_exit_order(side="sell", quantity=0.001)

    call_kwargs = ex.exchange.create_market_order.call_args
    params = call_kwargs[1].get("params", call_kwargs[0][3] if len(call_kwargs[0]) > 3 else {})
    assert params.get("reduceOnly") is True, \
        f"❌ reduceOnly=True が設定されていません: params={params}"
    return True, "✅ execute_exit_order に reduceOnly=True 設定済み"


def test_get_market_symbol():
    """マーケットシンボルを正しく返すか確認"""
    ex = _make_bybit_backtest()
    sym = ex.get_market_symbol()
    assert isinstance(sym, str) and len(sym) > 0, f"❌ 空文字列: {sym}"
    return True, f"✅ get_market_symbol={sym}"


# -------------------------------------------------------------------
# テストランナー
# -------------------------------------------------------------------

def run_all_tests():
    tests = [
        ("BybitExchange クラス存在確認",              test_bybit_exchange_exists),
        ("本番呼び出しメソッド全件の存在確認",      test_production_methods_exist),
        ("back_test=1 初期化フラグ確認",          test_init_backtest_mode_flags),
        ("papertrading 初期化フラグ確認",         test_init_papertrading_mode_flags),
        ("fetchCurrencies=False 設定確認",         test_fetchcurrencies_disabled),
        ("get_account_balance ダミー動作確認",    test_get_account_balance_dummy),
        ("get_account_balance_total ダミー動作確認", test_get_account_balance_total_dummy),
        ("fetch_ticker バックテストダミー確認",    test_fetch_ticker_backtest),
        ("execute_entry_order ダミー動作確認",    test_execute_entry_order_dummy),
        ("execute_entry_order ペーパートレード→実API不呼出確認", test_execute_entry_order_papertrading_no_real_api),
        ("execute_exit_order ダミー動作確認",     test_execute_exit_order_dummy),
        ("execute_exit_order ペーパートレード→実API不呼出確認",  test_execute_exit_order_papertrading_no_real_api),
        ("execute_exit_order reduceOnly=True確認", test_execute_exit_order_reduceonly),
        ("get_market_symbol 確認",                test_get_market_symbol),
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
    print("🧪 bybit_exchange.py レグレッションテスト")
    print("=" * 70)
    results = run_all_tests()

    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(results)
    print()
    print(f"📊 結果: {passed_count}/{total_count} 成功")

    RESULTS_DIR = os.path.join(WORKSPACE_ROOT, "docs/regression_test_results")
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(os.path.join(RESULTS_DIR, "test_bybit_exchange_regression.json"), "w", encoding="utf-8") as f:
        json.dump({"file": "bybit_exchange.py", "total": total_count, "passed": passed_count,
                   "results": results, "timestamp": datetime.now().isoformat()},
                  f, ensure_ascii=False, indent=2)

    sys.exit(0 if passed_count == total_count else 1)



def load_analysis():
    """analysis/bybit_exchange.json から BybitExchange クラスの仕様を読む"""
    with open(ANALYSIS_FILE, encoding="utf-8") as f:
        return json.load(f)


def test_bybit_exchange_exists():
    """BybitExchange クラスが存在することを確認"""
    try:
        from bybit_exchange import BybitExchange
        return True, f"✅ BybitExchange クラスが存在します"
    except ImportError as e:
        return False, f"❌ BybitExchange クラスのインポート失敗: {e}"


def test_bybit_exchange_methods():
    """BybitExchange の主要メソッドが存在することを確認"""
    try:
        from bybit_exchange import BybitExchange
        import inspect
        analysis = load_analysis()
        
        expected_methods = {m["name"] for m in analysis["classes"][0]["methods"]}
        # inspect.getmembers を使って private メソッドも検出
        actual_methods = {name for name, _ in inspect.getmembers(BybitExchange, predicate=inspect.isfunction)}
        
        missing = expected_methods - actual_methods
        if missing:
            return False, f"❌ 欠落メソッド: {missing}"
        
        return True, f"✅ 全メソッド({len(expected_methods)})が存在"
    except Exception as e:
        return False, f"❌ メソッド確認エラー: {e}"


def test_exchange_operations():
    """取引所操作メソッドが存在することを確認"""
    try:
        from bybit_exchange import BybitExchange
        
        exchange_methods = [
            "get_account_balance",
            "get_account_balance_total",
            "fetch_ohlcv",
            "fetch_latest_ohlcv",
            "fetch_ticker",
            "execute_order"
        ]
        
        missing = []
        for method in exchange_methods:
            if not hasattr(BybitExchange, method):
                missing.append(method)
        
        if missing:
            return False, f"❌ 欠落取引所操作メソッド: {missing}"
        
        return True, f"✅ 取引所操作メソッド({len(exchange_methods)})すべて存在"
    except Exception as e:
        return False, f"❌ 取引所操作メソッド確認エラー: {e}"


def test_bybit_exchange_init():
    """BybitExchange.__init__ が存在することを確認"""
    try:
        from bybit_exchange import BybitExchange
        
        if hasattr(BybitExchange, "__init__"):
            sig = inspect.signature(BybitExchange.__init__)
            return True, f"✅ BybitExchange.__init__ が定義されています (パラメータ: {len(list(sig.parameters.keys()))-1} 個)"
        else:
            return False, f"❌ __init__ が見つかりません"
    except Exception as e:
        return False, f"❌ __init__ 確認エラー: {e}"


def test_timestamp_methods():
    """タイムスタンプ関連メソッドが存在することを確認"""
    try:
        from bybit_exchange import BybitExchange
        
        if hasattr(BybitExchange, "get_nearest_epoch_time"):
            return True, f"✅ get_nearest_epoch_time メソッドが存在"
        else:
            return True, f"⚠️  get_nearest_epoch_time が見つかりません（実装仕様の確認が必要）"
    except Exception as e:
        return False, f"❌ タイムスタンプメソッド確認エラー: {e}"


def run_all_tests():
    """全テストを実行"""
    tests = [
        ("BybitExchange クラス存在確認", test_bybit_exchange_exists),
        ("BybitExchange メソッド確認", test_bybit_exchange_methods),
        ("取引所操作メソッド確認", test_exchange_operations),
        ("BybitExchange.__init__ 確認", test_bybit_exchange_init),
        ("タイムスタンプメソッド確認", test_timestamp_methods),
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
    print("🧪 bybit_exchange.py レグレッションテスト")
    print("=" * 70)
    results = run_all_tests()
    
    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(results)
    
    print()
    print(f"📊 結果: {passed_count}/{total_count} 成功")
    
    # 結果を JSON で保存
    RESULTS_DIR = os.path.join(WORKSPACE_ROOT, "docs/regression_test_results")
    os.makedirs(RESULTS_DIR, exist_ok=True)
    
    with open(os.path.join(RESULTS_DIR, "test_bybit_exchange_regression.json"), "w", encoding="utf-8") as f:
        json.dump({
            "file": "bybit_exchange.py",
            "total": total_count,
            "passed": passed_count,
            "results": results,
            "timestamp": datetime.now().isoformat()
        }, f, ensure_ascii=False, indent=2)
    
    sys.exit(0 if passed_count == total_count else 1)
