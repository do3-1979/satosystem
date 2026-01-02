"""
side.py のレグレッションテスト

Side Enum と関連関数の機能検証
"""

import os
import sys
import json
from datetime import datetime

# sys.path 設定
WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(WORKSPACE_ROOT, "src")
sys.path.insert(0, SRC_DIR)

# 分析結果ファイル
ANALYSIS_FILE = os.path.join(WORKSPACE_ROOT, "docs/analysis/src/side.json")


def load_analysis():
    """分析ファイルから仕様を読む"""
    with open(ANALYSIS_FILE, encoding="utf-8") as f:
        return json.load(f)


def test_side_enum_exists():
    """Side Enum が存在することを確認"""
    try:
        from side import Side
        return True, f"✅ Side Enum が存在します"
    except ImportError as e:
        return False, f"❌ Side Enum のインポート失敗: {e}"


def test_side_normalize_function():
    """normalize_side 関数が存在することを確認"""
    try:
        from side import normalize_side
        return True, f"✅ normalize_side 関数が存在します"
    except ImportError as e:
        return False, f"❌ normalize_side 関数のインポート失敗: {e}"


def test_side_to_exchange_function():
    """to_exchange_side 関数が存在することを確認"""
    try:
        from side import to_exchange_side
        return True, f"✅ to_exchange_side 関数が存在します"
    except ImportError as e:
        return False, f"❌ to_exchange_side 関数のインポート失敗: {e}"


def test_side_enum_values():
    """Side Enum が必要な値を持つことを確認"""
    try:
        from side import Side
        
        expected_values = ["BUY", "SELL", "NONE"]
        
        missing = []
        for value in expected_values:
            if not hasattr(Side, value):
                missing.append(value)
        
        if missing:
            return False, f"❌ 欠落値: {missing}"
        
        return True, f"✅ Side Enum 値({len(expected_values)})すべて存在"
    except Exception as e:
        return False, f"❌ Enum 値確認エラー: {e}"


def run_all_tests():
    """全テストを実行"""
    tests = [
        ("Side Enum 存在確認", test_side_enum_exists),
        ("Side Enum 値確認", test_side_enum_values),
        ("normalize_side 関数確認", test_side_normalize_function),
        ("to_exchange_side 関数確認", test_side_to_exchange_function),
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
    print("🧪 side.py レグレッションテスト")
    print("=" * 70)
    results = run_all_tests()
    
    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(results)
    
    print()
    print(f"📊 結果: {passed_count}/{total_count} 成功")
    
    # 結果を JSON で保存
    RESULTS_DIR = os.path.join(WORKSPACE_ROOT, "docs/regression_test_results")
    os.makedirs(RESULTS_DIR, exist_ok=True)
    
    with open(os.path.join(RESULTS_DIR, "test_side_regression.json"), "w", encoding="utf-8") as f:
        json.dump({
            "file": "side.py",
            "total": total_count,
            "passed": passed_count,
            "results": results,
            "timestamp": datetime.now().isoformat()
        }, f, ensure_ascii=False, indent=2)
    
    sys.exit(0 if passed_count == total_count else 1)
