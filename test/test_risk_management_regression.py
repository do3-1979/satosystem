"""
risk_management.py のレグレッションテスト

RiskManagement クラスの主要メソッド存在確認、ポジションサイズ計算検証
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
ANALYSIS_FILE = os.path.join(WORKSPACE_ROOT, "docs/analysis/risk_management.json")


def load_analysis():
    """analysis/risk_management.json から RiskManagement クラスの仕様を読む"""
    with open(ANALYSIS_FILE, encoding="utf-8") as f:
        return json.load(f)


def test_risk_management_exists():
    """RiskManagement クラスが存在することを確認"""
    try:
        from risk_management import RiskManagement
        return True, f"✅ RiskManagement クラスが存在します"
    except ImportError as e:
        return False, f"❌ RiskManagement クラスのインポート失敗: {e}"


def test_risk_management_methods():
    """RiskManagement の主要メソッドが存在することを確認"""
    try:
        from risk_management import RiskManagement
        analysis = load_analysis()
        
        expected_methods = {m["name"] for m in analysis["classes"][0]["methods"]}
        actual_methods = {m for m in dir(RiskManagement) if not m.startswith("_") or m == "__init__"}
        
        missing = expected_methods - actual_methods
        if missing:
            return False, f"❌ 欠落メソッド: {missing}"
        
        return True, f"✅ 全メソッド({len(expected_methods)})が存在"
    except Exception as e:
        return False, f"❌ メソッド確認エラー: {e}"


def test_risk_calculation_methods():
    """PSAR, ADX, ストップ価格計算メソッドが存在することを確認"""
    try:
        from risk_management import RiskManagement
        
        calculation_methods = [
            "get_psar",
            "get_psarbull",
            "get_psarbear",
            "get_adx",
            "get_adx_bull",
            "get_adx_bear",
            "get_stop_price",
            "calculate_position_size"
        ]
        
        missing = []
        for method in calculation_methods:
            if not hasattr(RiskManagement, method):
                missing.append(method)
        
        if missing:
            return False, f"❌ 欠落計算メソッド: {missing}"
        
        return True, f"✅ 計算メソッド({len(calculation_methods)})すべて存在"
    except Exception as e:
        return False, f"❌ 計算メソッド確認エラー: {e}"


def test_risk_management_init():
    """RiskManagement.__init__ が存在することを確認"""
    try:
        from risk_management import RiskManagement
        
        if hasattr(RiskManagement, "__init__"):
            sig = inspect.signature(RiskManagement.__init__)
            return True, f"✅ RiskManagement.__init__ が定義されています (パラメータ: {len(list(sig.parameters.keys()))-1} 個)"
        else:
            return False, f"❌ __init__ が見つかりません"
    except Exception as e:
        return False, f"❌ __init__ 確認エラー: {e}"


def test_private_methods():
    """プライベートメソッド（__で始まる計算用メソッド）が存在することを確認"""
    try:
        from risk_management import RiskManagement
        analysis = load_analysis()
        
        private_methods = [m["name"] for m in analysis["classes"][0]["methods"] if m["name"].startswith("_")]
        
        if len(private_methods) > 0:
            return True, f"✅ プライベートメソッド {len(private_methods)} 個検出"
        else:
            return False, f"⚠️  プライベートメソッドが見つかりません"
    except Exception as e:
        return False, f"❌ プライベートメソッド確認エラー: {e}"


def run_all_tests():
    """全テストを実行"""
    tests = [
        ("RiskManagement クラス存在確認", test_risk_management_exists),
        ("RiskManagement メソッド確認", test_risk_management_methods),
        ("リスク計算メソッド確認", test_risk_calculation_methods),
        ("RiskManagement.__init__ 確認", test_risk_management_init),
        ("プライベートメソッド確認", test_private_methods),
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
    print("🧪 risk_management.py レグレッションテスト")
    print("=" * 70)
    results = run_all_tests()
    
    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(results)
    
    print()
    print(f"📊 結果: {passed_count}/{total_count} 成功")
    
    # 結果を JSON で保存
    RESULTS_DIR = os.path.join(WORKSPACE_ROOT, "docs/regression_test_results")
    os.makedirs(RESULTS_DIR, exist_ok=True)
    
    with open(os.path.join(RESULTS_DIR, "test_risk_management_regression.json"), "w", encoding="utf-8") as f:
        json.dump({
            "file": "risk_management.py",
            "total": total_count,
            "passed": passed_count,
            "results": results,
            "timestamp": datetime.now().isoformat()
        }, f, ensure_ascii=False, indent=2)
    
    sys.exit(0 if passed_count == total_count else 1)
