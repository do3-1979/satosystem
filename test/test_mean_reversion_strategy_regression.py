"""mean_reversion_strategy.py のレグレッションテスト

MeanReversionStrategy の計算系が例外なく動作し、戻り値形式が崩れていないことを確認します。
"""

import os
import sys
import json
from datetime import datetime

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(WORKSPACE_ROOT, "src")
sys.path.insert(0, SRC_DIR)


def _make_candles_list(n=60, start=100.0, step=0.5):
    candles = []
    price = start
    for _ in range(n):
        price += step
        candles.append([0, price, price + 2, price - 2, price, 1000])
    return candles


def _make_candles_dict(n=60, start=100.0, step=0.5):
    candles = []
    price = start
    for _ in range(n):
        price += step
        candles.append({"close_price": price})
    return candles


def test_import_and_construct():
    try:
        from mean_reversion_strategy import MeanReversionStrategy

        s = MeanReversionStrategy()
        return True, f"✅ MeanReversionStrategy 初期化OK: bb_period={s.bb_period}, rsi_period={s.rsi_period}"
    except Exception as e:
        return False, f"❌ MeanReversionStrategy インポート/初期化失敗: {e}"


def test_bollinger_and_rsi_calculation_smoke():
    try:
        from mean_reversion_strategy import MeanReversionStrategy

        s = MeanReversionStrategy()

        candles_list = _make_candles_list(max(25, s.bb_period + 5))
        upper, middle, lower = s.calculate_bollinger_bands(candles_list)
        if upper is None or middle is None or lower is None:
            return False, "❌ Bollinger Bands が計算できませんでした"

        candles_dict = _make_candles_dict(max(25, s.rsi_period + 5))
        rsi = s.calculate_rsi(candles_dict)
        if rsi is None:
            return False, "❌ RSI が計算できませんでした"

        if not (0.0 <= float(rsi) <= 100.0):
            return False, f"❌ RSI 範囲外: {rsi}"

        return True, f"✅ BB/RSI 計算OK: BB=({upper:.2f},{middle:.2f},{lower:.2f}), RSI={rsi:.2f}"
    except Exception as e:
        return False, f"❌ BB/RSI スモーク失敗: {e}"


def test_evaluate_entry_output_shape():
    try:
        from mean_reversion_strategy import MeanReversionStrategy

        s = MeanReversionStrategy()
        candles = _make_candles_list(max(60, s.bb_period + s.rsi_period + 5))

        # 価格をBB下限より下に置いて、シグナルが出る可能性を作る
        current_price = candles[-1][4] - 50
        result = s.evaluate_entry(candles, current_price=current_price)

        required_keys = {"signal", "bb_upper", "bb_middle", "bb_lower", "bb_position", "rsi", "reason"}
        missing = required_keys - set(result.keys())
        if missing:
            return False, f"❌ evaluate_entry 戻り値キー不足: {sorted(missing)}"

        if not isinstance(result["signal"], bool):
            return False, f"❌ signal 型不正: {type(result['signal'])}"

        return True, f"✅ evaluate_entry 形式OK: signal={result['signal']}, reason={result['reason'][:80]}"
    except Exception as e:
        return False, f"❌ evaluate_entry 実行失敗: {e}"


def run_all_tests():
    tests = [
        ("MeanReversionStrategy import/初期化", test_import_and_construct),
        ("BB/RSI 計算スモーク", test_bollinger_and_rsi_calculation_smoke),
        ("evaluate_entry 戻り値形式", test_evaluate_entry_output_shape),
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
    print("🧪 mean_reversion_strategy.py レグレッションテスト")
    print("=" * 70)

    results = run_all_tests()
    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(results)

    print()
    print(f"📊 結果: {passed_count}/{total_count} 成功")

    results_dir = os.path.join(WORKSPACE_ROOT, "docs/regression_test_results")
    os.makedirs(results_dir, exist_ok=True)

    with open(
        os.path.join(results_dir, "test_mean_reversion_strategy_regression.json"),
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            {
                "file": "mean_reversion_strategy.py",
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
