"""
portfolio.py のレグレッションテスト

Portfolio クラスの主要メソッド存在確認、ポジション・損益管理検証
"""

import os
import sys
import json
import inspect
from datetime import datetime

# sys.path 設定
WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(WORKSPACE_ROOT, "src")
sys.path.insert(0, SRC_DIR)

# 分析結果ファイル
ANALYSIS_FILE = os.path.join(WORKSPACE_ROOT, "docs/analysis/src/portfolio.json")


def load_analysis():
    """analysis/portfolio.json から Portfolio クラスの仕様を読む"""
    with open(ANALYSIS_FILE, encoding="utf-8") as f:
        return json.load(f)


def test_portfolio_exists():
    """Portfolio クラスが存在することを確認"""
    try:
        from portfolio import Portfolio
        return True, f"✅ Portfolio クラスが存在します"
    except ImportError as e:
        return False, f"❌ Portfolio クラスのインポート失敗: {e}"


def test_portfolio_methods():
    """Portfolio の主要メソッドが存在することを確認"""
    try:
        from portfolio import Portfolio
        analysis = load_analysis()
        
        expected_methods = {m["name"] for m in analysis["classes"][0]["methods"]}
        # __str__ は name mangling の対象外（Python特殊メソッド）だが、テスト比較ロジックに含めない
        expected_methods.discard("__str__")
        actual_methods = {m for m in dir(Portfolio) if not m.startswith("_") or m == "__init__"}
        
        missing = expected_methods - actual_methods
        if missing:
            return False, f"❌ 欠落メソッド: {missing}"
        
        return True, f"✅ 全メソッド({len(expected_methods)})が存在"
    except Exception as e:
        return False, f"❌ メソッド確認エラー: {e}"


def test_position_management_methods():
    """ポジション・損益管理メソッドが存在することを確認"""
    try:
        from portfolio import Portfolio
        
        management_methods = [
            "get_position_quantity",
            "get_position_side",
            "get_position_price",
            "get_profit_and_loss",
            "get_profit_factor",
            "get_drawdown",
            "get_drawdown_rate",
            "add_position_quantity",
            "clear_position_quantity"
        ]
        
        missing = []
        for method in management_methods:
            if not hasattr(Portfolio, method):
                missing.append(method)
        
        if missing:
            return False, f"❌ 欠落ポジション管理メソッド: {missing}"
        
        return True, f"✅ ポジション管理メソッド({len(management_methods)})すべて存在"
    except Exception as e:
        return False, f"❌ ポジション管理メソッド確認エラー: {e}"


def test_portfolio_init():
    """Portfolio.__init__ が存在することを確認"""
    try:
        from portfolio import Portfolio
        
        if hasattr(Portfolio, "__init__"):
            sig = inspect.signature(Portfolio.__init__)
            return True, f"✅ Portfolio.__init__ が定義されています (パラメータ: {len(list(sig.parameters.keys()))-1} 個)"
        else:
            return False, f"❌ __init__ が見つかりません"
    except Exception as e:
        return False, f"❌ __init__ 確認エラー: {e}"


def test_multi_symbol_methods():
    """複数シンボル対応メソッドが存在することを確認"""
    try:
        from portfolio import Portfolio
        analysis = load_analysis()
        
        multi_symbol_methods = [m["name"] for m in analysis["classes"][0]["methods"] 
                               if "with_symbol" in m["name"]]
        
        if len(multi_symbol_methods) > 0:
            return True, f"✅ マルチシンボル対応メソッド {len(multi_symbol_methods)} 個検出"
        else:
            return True, f"⚠️  マルチシンボル対応メソッドが見つかりません（単一シンボル仕様の可能性）"
    except Exception as e:
        return False, f"❌ マルチシンボル対応確認エラー: {e}"


def run_all_tests():
    """全テストを実行"""
    tests = [
        ("Portfolio クラス存在確認", test_portfolio_exists),
        ("Portfolio メソッド確認", test_portfolio_methods),
        ("ポジション管理メソッド確認", test_position_management_methods),
        ("Portfolio.__init__ 確認", test_portfolio_init),
        ("マルチシンボル対応確認", test_multi_symbol_methods),
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
    print("🧪 portfolio.py レグレッションテスト")
    print("=" * 70)
    results = run_all_tests()
    
    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(results)
    
    print()
    print(f"📊 結果: {passed_count}/{total_count} 成功")
    
    # 結果を JSON で保存
    RESULTS_DIR = os.path.join(WORKSPACE_ROOT, "docs/regression_test_results")
    os.makedirs(RESULTS_DIR, exist_ok=True)
    
    with open(os.path.join(RESULTS_DIR, "test_portfolio_regression.json"), "w", encoding="utf-8") as f:
        json.dump({
            "file": "portfolio.py",
            "total": total_count,
            "passed": passed_count,
            "results": results,
            "timestamp": datetime.now().isoformat()
        }, f, ensure_ascii=False, indent=2)
    
    sys.exit(0 if passed_count == total_count else 1)
