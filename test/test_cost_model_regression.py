"""cost_model.py のレグレッションテスト

CostModel クラスの手数料計算・スリッページ計算・設定サマリ取得が
正しく動作することを検証するスモークテスト。
"""

import os
import sys
import json
from datetime import datetime

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(WORKSPACE_ROOT, "src")
sys.path.insert(0, SRC_DIR)


def test_import_and_init():
    """CostModel のインポートと初期化確認"""
    try:
        from cost_model import CostModel
        model = CostModel()
        summary = model.get_cost_summary()

        required_keys = ['enabled', 'maker_fee', 'taker_fee', 'slippage_rate', 'execution_delay_candles']
        for key in required_keys:
            if key not in summary:
                return False, f"❌ サマリにキーがありません: {key}"

        return True, f"✅ CostModel 初期化OK: maker={summary['maker_fee']}%, taker={summary['taker_fee']}%, slippage={summary['slippage_rate']}%"
    except Exception as e:
        return False, f"❌ CostModel インポート/初期化失敗: {e}"


def test_slippage_buy():
    """BUY時スリッページ: 価格が上昇する方向に不利になること"""
    try:
        from cost_model import CostModel
        model = CostModel()

        price = 100000.0
        slipped = model._apply_slippage(price, 'buy')

        if slipped <= price:
            return False, f"❌ BUY スリッページが正しくありません: {price} → {slipped}"

        return True, f"✅ BUY スリッページOK: {price} → {slipped:.2f}"
    except Exception as e:
        return False, f"❌ BUY スリッページ計算失敗: {e}"


def test_slippage_sell():
    """SELL時スリッページ: 価格が下落する方向に不利になること"""
    try:
        from cost_model import CostModel
        model = CostModel()

        price = 100000.0
        slipped = model._apply_slippage(price, 'sell')

        if slipped >= price:
            return False, f"❌ SELL スリッページが正しくありません: {price} → {slipped}"

        return True, f"✅ SELL スリッページOK: {price} → {slipped:.2f}"
    except Exception as e:
        return False, f"❌ SELL スリッページ計算失敗: {e}"


def test_entry_cost_enabled():
    """コストモデル有効時: 手数料+スリッページが計算されること"""
    try:
        from cost_model import CostModel
        model = CostModel()
        model.is_enabled = True
        model.taker_fee = 0.05
        model.slippage_rate = 0.02

        price = 100000.0
        qty = 0.01
        exec_price, total_cost, details = model.calculate_entry_cost('buy', qty, price, is_market_order=True)

        if total_cost <= 0:
            return False, f"❌ コスト有効時にtotal_cost={total_cost}（正の値でない）"
        if exec_price <= price:
            return False, f"❌ BUY実約定価格がシグナル価格以下: {exec_price} <= {price}"
        if 'fee_cost' not in details or 'slippage_cost' not in details:
            return False, f"❌ cost_details のキーが不正: {list(details.keys())}"

        return True, (f"✅ エントリーコスト計算OK: "
                      f"exec={exec_price:.2f}, total={total_cost:.4f} USD "
                      f"(fee={details['fee_cost']:.4f}, slip={details['slippage_cost']:.4f})")
    except Exception as e:
        return False, f"❌ エントリーコスト計算失敗: {e}"


def test_entry_cost_disabled():
    """コストモデル無効時: 元価格そのまま・コスト0が返ること"""
    try:
        from cost_model import CostModel
        model = CostModel()
        model.is_enabled = False

        price = 50000.0
        qty = 0.01
        exec_price, total_cost, details = model.calculate_entry_cost('buy', qty, price)

        if exec_price != price:
            return False, f"❌ 無効時の実約定価格が変化: {exec_price} != {price}"
        if total_cost != 0.0:
            return False, f"❌ 無効時のコストが0でない: {total_cost}"

        return True, f"✅ コストモデル無効時: price={exec_price}, cost={total_cost}"
    except Exception as e:
        return False, f"❌ コストモデル無効テスト失敗: {e}"


def test_exit_cost():
    """イグジットコスト計算がエントリーと同等のロジックで動作すること"""
    try:
        from cost_model import CostModel
        model = CostModel()
        model.is_enabled = True
        model.taker_fee = 0.05
        model.slippage_rate = 0.02

        price = 100000.0
        qty = 0.01

        entry_exec, entry_cost, _ = model.calculate_entry_cost('buy', qty, price)
        exit_exec, exit_cost, _ = model.calculate_exit_cost('buy', qty, price)

        if entry_exec != exit_exec or abs(entry_cost - exit_cost) > 1e-10:
            return False, f"❌ exit_cost と entry_cost が一致しない: {entry_cost} vs {exit_cost}"

        return True, f"✅ イグジットコスト計算OK: cost={exit_cost:.4f} USD"
    except Exception as e:
        return False, f"❌ イグジットコスト計算失敗: {e}"


def run_all_tests():
    tests = [
        ("CostModel import/初期化", test_import_and_init),
        ("BUY スリッページ計算", test_slippage_buy),
        ("SELL スリッページ計算", test_slippage_sell),
        ("エントリーコスト計算（有効時）", test_entry_cost_enabled),
        ("エントリーコスト計算（無効時）", test_entry_cost_disabled),
        ("イグジットコスト計算", test_exit_cost),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            passed, message = test_func()
            results.append({
                "test_name": test_name,
                "passed": passed,
                "message": message
            })
            status = "✅" if passed else "❌"
            print(f"  {status} {test_name}: {message}")
        except Exception as e:
            results.append({
                "test_name": test_name,
                "passed": False,
                "message": f"❌ 例外: {e}"
            })
            print(f"  ❌ {test_name}: 例外 {e}")

    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(results)

    # 結果をJSONで保存
    output = {
        "test": "test_cost_model_regression",
        "test_suite": "test_cost_model_regression",
        "timestamp": datetime.now().isoformat(),
        "passed": passed_count,
        "total": total_count,
        "results": results
    }

    result_dir = os.path.join(WORKSPACE_ROOT, "docs", "regression_test_results")
    os.makedirs(result_dir, exist_ok=True)
    result_path = os.path.join(result_dir, "test_cost_model_regression.json")
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n  📊 結果: {passed_count}/{total_count} 成功")
    return passed_count, total_count


if __name__ == "__main__":
    print("🧪 CostModel レグレッションテスト")
    print("=" * 50)
    passed, total = run_all_tests()
    sys.exit(0 if passed == total else 1)
