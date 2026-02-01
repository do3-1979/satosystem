"""trade_logger.py のレグレッションテスト

TradeLogger の entry/exit 記録と JSON 保存が破綻していないことを確認します。
"""

import os
import sys
import json
import tempfile
from datetime import datetime

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(WORKSPACE_ROOT, "src")
sys.path.insert(0, SRC_DIR)


def test_trade_logger_entry_exit_and_save():
    try:
        from trade_logger import TradeLogger

        with tempfile.TemporaryDirectory() as tmpdir:
            logger = TradeLogger(log_dir=tmpdir)

            logger.log_entry(
                {
                    "timestamp": datetime.now().isoformat(),
                    "close_time_dt": "2026/02/01 00:00",
                    "side": "BUY",
                    "price": 100.0,
                    "pvo_signal": True,
                    "pvo_filter_pass": True,
                    "adx_filter_pass": True,
                    "volume_filter_pass": True,
                    "volatility_filter_pass": True,
                    "market_regime": "TRENDING_UP",
                    "market_regime_confidence": 0.75,
                    "market_regime_reason": "Test regime",
                    "market_regime_filter_enabled": 0,
                    "donchian_signal": 1,
                    "strategy_signal": 1,
                }
            )

            logger.log_exit(
                {
                    "timestamp": datetime.now().isoformat(),
                    "close_time_dt": "2026/02/01 00:03",
                    "price": 101.0,
                    "pnl_usd": 1.0,
                    "pnl_pct": 1.0,
                    "duration_minutes": 3,
                    "bars_held": 1,
                    "cumulative_pnl": 1.0,
                    "reason": "TEST",
                }
            )

            if logger.get_trade_count() != 1:
                return False, f"❌ trade_count 不正: {logger.get_trade_count()}"

            path = logger.save_trades_json(filename="test_trade_log.json")
            if not path or not os.path.exists(path):
                return False, "❌ JSON 保存に失敗しました"

            with open(path, encoding="utf-8") as f:
                data = json.load(f)

            if "metadata" not in data or "trades" not in data:
                return False, "❌ JSON 形式が不正（metadata/trades が無い）"

            if data["metadata"].get("total_trades") != 1:
                return False, f"❌ total_trades 不正: {data['metadata'].get('total_trades')}"

            return True, f"✅ TradeLogger 保存OK: {path}"

    except Exception as e:
        return False, f"❌ TradeLogger スモーク失敗: {e}"


def run_all_tests():
    tests = [
        ("TradeLogger entry/exit/save", test_trade_logger_entry_exit_and_save),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            passed, message = test_func()
            results.append(
                {
                    "name": test_name,
                    "passed": passed,
                    "message": message,
                    "timestamp": datetime.now().isoformat(),
                }
            )
            print(message)
        except Exception as e:
            results.append(
                {
                    "name": test_name,
                    "passed": False,
                    "message": f"❌ テスト実行エラー: {e}",
                    "timestamp": datetime.now().isoformat(),
                }
            )
            print(f"❌ テスト実行エラー ({test_name}): {e}")

    return results


if __name__ == "__main__":
    print("=" * 70)
    print("🧪 trade_logger.py レグレッションテスト")
    print("=" * 70)

    results = run_all_tests()
    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(results)

    print()
    print(f"📊 結果: {passed_count}/{total_count} 成功")

    results_dir = os.path.join(WORKSPACE_ROOT, "docs/regression_test_results")
    os.makedirs(results_dir, exist_ok=True)

    with open(
        os.path.join(results_dir, "test_trade_logger_regression.json"),
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            {
                "file": "trade_logger.py",
                "total": total_count,
                "passed": passed_count,
                "results": results,
                "timestamp": datetime.now().isoformat(),
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    sys.exit(0 if passed_count == total_count else 1)
