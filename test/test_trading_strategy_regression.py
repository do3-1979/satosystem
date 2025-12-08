"""
trading_strategy.py のレグレッションテスト

TradingStrategy クラスの主要メソッド存在確認、判定ロジック検証
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
ANALYSIS_FILE = os.path.join(WORKSPACE_ROOT, "docs/analysis/trading_strategy.json")


def load_analysis():
    """analysis/trading_strategy.json から TradingStrategy クラスの仕様を読む"""
    with open(ANALYSIS_FILE, encoding="utf-8") as f:
        return json.load(f)


def test_trading_strategy_exists():
    """TradingStrategy クラスが存在することを確認"""
    try:
        from trading_strategy import TradingStrategy
        return True, f"✅ TradingStrategy クラスが存在します"
    except ImportError as e:
        return False, f"❌ TradingStrategy クラスのインポート失敗: {e}"


def test_trading_strategy_methods():
    """TradingStrategy の主要メソッドが存在することを確認"""
    try:
        from trading_strategy import TradingStrategy
        analysis = load_analysis()
        
        expected_methods = {m["name"] for m in analysis["classes"][0]["methods"]}
        # __str__ は name mangling の対象外（Python特殊メソッド）だが、テスト比較ロジックに含めない
        expected_methods.discard("__str__")
        actual_methods = {m for m in dir(TradingStrategy) if not m.startswith("_") or m == "__init__"}
        
        missing = expected_methods - actual_methods
        if missing:
            return False, f"❌ 欠落メソッド: {missing}"
        
        return True, f"✅ 全メソッド({len(expected_methods)})が存在"
    except Exception as e:
        return False, f"❌ メソッド確認エラー: {e}"


def test_trading_decision_methods():
    """ENTRY/ADD/EXIT 判定メソッドが存在することを確認"""
    try:
        from trading_strategy import TradingStrategy
        
        decision_methods = [
            "initialize_trade_decision",
            "evaluate_entry",
            "evaluate_add",
            "evaluate_exit",
            "make_trade_decision"
        ]
        
        missing = []
        for method in decision_methods:
            if not hasattr(TradingStrategy, method):
                missing.append(method)
        
        if missing:
            return False, f"❌ 欠落判定メソッド: {missing}"
        
        return True, f"✅ 判定メソッド({len(decision_methods)})すべて存在"
    except Exception as e:
        return False, f"❌ 判定メソッド確認エラー: {e}"


def test_trading_strategy_init_signature():
    """TradingStrategy.__init__ のシグネチャを確認"""
    try:
        from trading_strategy import TradingStrategy
        sig = inspect.signature(TradingStrategy.__init__)
        params = list(sig.parameters.keys())
        
        # 期待: self および他のパラメータ
        if "self" in params:
            return True, f"✅ __init__ が定義されています (パラメータ: {len(params)}-1 個)"
        else:
            return False, f"❌ __init__ シグネチャが不正"
    except Exception as e:
        return False, f"❌ シグネチャ確認エラー: {e}"


def run_all_tests():
    """全テストを実行"""
    tests = [
        ("TradingStrategy クラス存在確認", test_trading_strategy_exists),
        ("TradingStrategy メソッド確認", test_trading_strategy_methods),
        ("判定メソッド確認", test_trading_decision_methods),
        ("TradingStrategy.__init__ シグネチャ確認", test_trading_strategy_init_signature),
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
    print("🧪 trading_strategy.py レグレッションテスト")
    print("=" * 70)
    results = run_all_tests()
    
    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(results)
    
    print()
    print(f"📊 結果: {passed_count}/{total_count} 成功")
    
    # 結果を JSON で保存
    RESULTS_DIR = os.path.join(WORKSPACE_ROOT, "docs/regression_test_results")
    os.makedirs(RESULTS_DIR, exist_ok=True)
    
    with open(os.path.join(RESULTS_DIR, "test_trading_strategy_regression.json"), "w", encoding="utf-8") as f:
        json.dump({
            "file": "trading_strategy.py",
            "total": total_count,
            "passed": passed_count,
            "results": results,
            "timestamp": datetime.now().isoformat()
        }, f, ensure_ascii=False, indent=2)
    
    sys.exit(0 if passed_count == total_count else 1)
