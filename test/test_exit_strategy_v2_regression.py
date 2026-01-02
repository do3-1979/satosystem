"""
exit_strategy_v2.py のレグレッションテスト

ExitStrategyV2 と PortfolioExitExecutor クラスの機能検証
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
ANALYSIS_FILE = os.path.join(WORKSPACE_ROOT, "docs/analysis/src/exit_strategy_v2.json")


def load_analysis():
    """分析ファイルから仕様を読む"""
    with open(ANALYSIS_FILE, encoding="utf-8") as f:
        return json.load(f)


def test_exit_strategy_v2_class_exists():
    """ExitStrategyV2 クラスが存在することを確認"""
    try:
        from exit_strategy_v2 import ExitStrategyV2
        return True, f"✅ ExitStrategyV2 クラスが存在します"
    except ImportError as e:
        return False, f"❌ ExitStrategyV2 クラスのインポート失敗: {e}"


def test_exit_strategy_v2_key_methods():
    """ExitStrategyV2 の主要メソッドが存在することを確認"""
    try:
        from exit_strategy_v2 import ExitStrategyV2
        
        key_methods = [
            "__init__",
            "evaluate_exit_condition",
            "_identify_stage",
            "_check_stop_loss"
        ]
        
        missing = []
        for method in key_methods:
            if not hasattr(ExitStrategyV2, method):
                missing.append(method)
        
        if missing:
            return False, f"❌ 欠落主要メソッド: {missing}"
        
        return True, f"✅ 主要メソッド({len(key_methods)})すべて存在"
    except Exception as e:
        return False, f"❌ 主要メソッド確認エラー: {e}"


def test_portfolio_exit_executor_class():
    """PortfolioExitExecutor クラスが存在することを確認"""
    try:
        from exit_strategy_v2 import PortfolioExitExecutor
        return True, f"✅ PortfolioExitExecutor クラスが存在します"
    except ImportError as e:
        return False, f"⚠️  PortfolioExitExecutor クラスのインポート失敗（オプショナル）: {e}"


def test_exit_strategy_v2_instantiation():
    """ExitStrategyV2 インスタンス化確認"""
    try:
        from exit_strategy_v2 import ExitStrategyV2
        
        # インスタンス化を試みる
        exit_strategy = ExitStrategyV2()
        
        if exit_strategy:
            return True, f"✅ ExitStrategyV2 インスタンス化成功"
        else:
            return False, f"❌ ExitStrategyV2 インスタンス化失敗"
    except Exception as e:
        return False, f"❌ ExitStrategyV2 インスタンス化エラー: {e}"


def run_all_tests():
    """全テストを実行"""
    tests = [
        ("ExitStrategyV2 クラス存在確認", test_exit_strategy_v2_class_exists),
        ("ExitStrategyV2 主要メソッド確認", test_exit_strategy_v2_key_methods),
        ("PortfolioExitExecutor クラス確認", test_portfolio_exit_executor_class),
        ("ExitStrategyV2 インスタンス化確認", test_exit_strategy_v2_instantiation),
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
    print("🧪 exit_strategy_v2.py レグレッションテスト")
    print("=" * 70)
    results = run_all_tests()
    
    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(results)
    
    print()
    print(f"📊 結果: {passed_count}/{total_count} 成功")
    
    # 結果を JSON で保存
    RESULTS_DIR = os.path.join(WORKSPACE_ROOT, "docs/regression_test_results")
    os.makedirs(RESULTS_DIR, exist_ok=True)
    
    with open(os.path.join(RESULTS_DIR, "test_exit_strategy_v2_regression.json"), "w", encoding="utf-8") as f:
        json.dump({
            "file": "exit_strategy_v2.py",
            "total": total_count,
            "passed": passed_count,
            "results": results,
            "timestamp": datetime.now().isoformat()
        }, f, ensure_ascii=False, indent=2)
    
    sys.exit(0 if passed_count == total_count else 1)
