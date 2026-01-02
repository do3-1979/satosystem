"""
event.py のレグレッションテスト

Event, EventType, EventBus クラスの機能検証
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
ANALYSIS_FILE = os.path.join(WORKSPACE_ROOT, "docs/analysis/src/event.json")


def load_analysis():
    """分析ファイルから仕様を読む"""
    with open(ANALYSIS_FILE, encoding="utf-8") as f:
        return json.load(f)


def test_event_bus_class_exists():
    """EventBus クラスが存在することを確認"""
    try:
        from event import EventBus
        return True, f"✅ EventBus クラスが存在します"
    except ImportError as e:
        return False, f"❌ EventBus クラスのインポート失敗: {e}"


def test_event_class_exists():
    """Event クラスが存在することを確認"""
    try:
        from event import Event
        return True, f"✅ Event クラスが存在します"
    except ImportError as e:
        return False, f"❌ Event クラスのインポート失敗: {e}"


def test_event_bus_key_methods():
    """EventBus の主要メソッドが存在することを確認"""
    try:
        from event import EventBus
        
        key_methods = [
            "__init__",
            "subscribe",
            "unsubscribe",
            "emit"
        ]
        
        missing = []
        for method in key_methods:
            if not hasattr(EventBus, method):
                missing.append(method)
        
        if missing:
            return False, f"❌ 欠落主要メソッド: {missing}"
        
        return True, f"✅ EventBus 主要メソッド({len(key_methods)})すべて存在"
    except Exception as e:
        return False, f"❌ 主要メソッド確認エラー: {e}"


def test_event_bus_instantiation():
    """EventBus インスタンス化確認"""
    try:
        from event import EventBus
        
        bus = EventBus()
        
        if bus:
            return True, f"✅ EventBus インスタンス化成功"
        else:
            return False, f"❌ EventBus インスタンス化失敗"
    except Exception as e:
        return False, f"❌ EventBus インスタンス化エラー: {e}"


def run_all_tests():
    """全テストを実行"""
    tests = [
        ("Event クラス存在確認", test_event_class_exists),
        ("EventBus クラス存在確認", test_event_bus_class_exists),
        ("EventBus 主要メソッド確認", test_event_bus_key_methods),
        ("EventBus インスタンス化確認", test_event_bus_instantiation),
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
    print("🧪 event.py レグレッションテスト")
    print("=" * 70)
    results = run_all_tests()
    
    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(results)
    
    print()
    print(f"📊 結果: {passed_count}/{total_count} 成功")
    
    # 結果を JSON で保存
    RESULTS_DIR = os.path.join(WORKSPACE_ROOT, "docs/regression_test_results")
    os.makedirs(RESULTS_DIR, exist_ok=True)
    
    with open(os.path.join(RESULTS_DIR, "test_event_regression.json"), "w", encoding="utf-8") as f:
        json.dump({
            "file": "event.py",
            "total": total_count,
            "passed": passed_count,
            "results": results,
            "timestamp": datetime.now().isoformat()
        }, f, ensure_ascii=False, indent=2)
    
    sys.exit(0 if passed_count == total_count else 1)
