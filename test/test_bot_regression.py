"""
bot.py のレグレッションテスト

Bot クラスの主要メソッド存在確認、シグネチャ検証
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
ANALYSIS_FILE = os.path.join(WORKSPACE_ROOT, "docs/analysis/src/bot.json")

# 互換性ヘルパー
from analysis_helper import load_analysis_with_compat, get_class_method_names


def load_analysis():
    """analysis/bot.json から Bot クラスの仕様を読む（互換性対応）"""
    return load_analysis_with_compat(ANALYSIS_FILE)


def test_bot_class_exists():
    """Bot クラスが存在することを確認"""
    try:
        from bot import Bot
        return True, f"✅ Bot クラスが存在します"
    except ImportError as e:
        return False, f"❌ Bot クラスのインポート失敗: {e}"


def test_bot_methods_exist():
    """Bot クラスの主要メソッドが存在することを確認"""
    try:
        from bot import Bot
        analysis = load_analysis()
        
        expected_methods = get_class_method_names(analysis)
        actual_methods = {m for m in dir(Bot) if not m.startswith("_") or m in ["__init__"]}
        
        missing = expected_methods - actual_methods
        if missing:
            return False, f"❌ 欠落メソッド: {missing}"
        
        return True, f"✅ 全メソッド({len(expected_methods)})が存在"
    except Exception as e:
        return False, f"❌ メソッド確認エラー: {e}"


def test_bot_init_signature():
    """Bot.__init__ のシグネチャを確認"""
    try:
        from bot import Bot
        sig = inspect.signature(Bot.__init__)
        params = list(sig.parameters.keys())
        
        # 期待: self, exchange, strategy, risk_management, price_data_management, portfolio
        expected = ["self", "exchange", "strategy", "risk_management", "price_data_management", "portfolio"]
        
        if params == expected:
            return True, f"✅ __init__ シグネチャが正確"
        else:
            return False, f"❌ シグネチャ不一致\n  期待: {expected}\n  実際: {params}"
    except Exception as e:
        return False, f"❌ シグネチャ確認エラー: {e}"


def test_bot_run_callable():
    """Bot.run メソッドが実行可能であることを確認"""
    try:
        from bot import Bot
        if not hasattr(Bot, "run"):
            return False, f"❌ run メソッドが見つかりません"
        
        if callable(getattr(Bot, "run")):
            return True, f"✅ run メソッドが実行可能です"
        else:
            return False, f"❌ run はメソッドではありません"
    except Exception as e:
        return False, f"❌ 実行可能性確認エラー: {e}"


def run_all_tests():
    """全テストを実行"""
    tests = [
        ("Bot クラス存在確認", test_bot_class_exists),
        ("Bot メソッド確認", test_bot_methods_exist),
        ("Bot.__init__ シグネチャ確認", test_bot_init_signature),
        ("Bot.run 実行可能確認", test_bot_run_callable),
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
    print("🧪 bot.py レグレッションテスト")
    print("=" * 70)
    results = run_all_tests()
    
    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(results)
    
    print()
    print(f"📊 結果: {passed_count}/{total_count} 成功")
    
    # 結果を JSON で保存
    RESULTS_DIR = os.path.join(WORKSPACE_ROOT, "docs/regression_test_results")
    os.makedirs(RESULTS_DIR, exist_ok=True)
    
    with open(os.path.join(RESULTS_DIR, "test_bot_regression.json"), "w", encoding="utf-8") as f:
        json.dump({
            "file": "bot.py",
            "total": total_count,
            "passed": passed_count,
            "results": results,
            "timestamp": datetime.now().isoformat()
        }, f, ensure_ascii=False, indent=2)
    
    sys.exit(0 if passed_count == total_count else 1)
