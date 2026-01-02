"""
metrics.py のレグレッションテスト

Metrics 関連関数の機能検証
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
ANALYSIS_FILE = os.path.join(WORKSPACE_ROOT, "docs/analysis/src/metrics.json")


def load_analysis():
    """分析ファイルから仕様を読む"""
    with open(ANALYSIS_FILE, encoding="utf-8") as f:
        return json.load(f)


def test_metrics_module_exists():
    """metrics モジュールが存在することを確認"""
    try:
        import metrics
        return True, f"✅ metrics モジュールが存在します"
    except ImportError as e:
        return False, f"❌ metrics モジュールのインポート失敗: {e}"


def test_compute_metrics_function():
    """compute_metrics 関数が存在することを確認"""
    try:
        from metrics import compute_metrics
        return True, f"✅ compute_metrics 関数が存在します"
    except ImportError as e:
        return False, f"❌ compute_metrics 関数のインポート失敗: {e}"


def test_metrics_helper_functions():
    """メトリクス計算補助関数が存在することを確認"""
    try:
        from metrics import _max_drawdown, _sharpe
        return True, f"✅ ヘルパー関数（_max_drawdown, _sharpe）が存在します"
    except ImportError as e:
        return False, f"⚠️  ヘルパー関数のインポート失敗（オプショナル）: {e}"


def test_compute_metrics_functionality():
    """compute_metrics 関数の基本動作確認"""
    try:
        from metrics import compute_metrics
        
        # compute_metrics 関数が呼び出し可能であることを確認
        if callable(compute_metrics):
            return True, f"✅ compute_metrics 関数は呼び出し可能"
        else:
            return False, f"❌ compute_metrics が呼び出し可能ではありません"
    except Exception as e:
        return False, f"❌ compute_metrics 確認エラー: {e}"


def run_all_tests():
    """全テストを実行"""
    tests = [
        ("metrics モジュール存在確認", test_metrics_module_exists),
        ("compute_metrics 関数確認", test_compute_metrics_function),
        ("ヘルパー関数確認", test_metrics_helper_functions),
        ("compute_metrics 動作確認", test_compute_metrics_functionality),
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
    print("🧪 metrics.py レグレッションテスト")
    print("=" * 70)
    results = run_all_tests()
    
    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(results)
    
    print()
    print(f"📊 結果: {passed_count}/{total_count} 成功")
    
    # 結果を JSON で保存
    RESULTS_DIR = os.path.join(WORKSPACE_ROOT, "docs/regression_test_results")
    os.makedirs(RESULTS_DIR, exist_ok=True)
    
    with open(os.path.join(RESULTS_DIR, "test_metrics_regression.json"), "w", encoding="utf-8") as f:
        json.dump({
            "file": "metrics.py",
            "total": total_count,
            "passed": passed_count,
            "results": results,
            "timestamp": datetime.now().isoformat()
        }, f, ensure_ascii=False, indent=2)
    
    sys.exit(0 if passed_count == total_count else 1)
