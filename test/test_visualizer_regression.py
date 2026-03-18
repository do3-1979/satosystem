"""
visualizer.py のレグレッションテスト

Visualizer クラスの主要メソッド存在確認、グラフ生成・可視化検証
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

def test_visualizer_exists():
    """Visualizer クラスが存在することを確認"""
    try:
        from visualizer import Visualizer
        return True, f"✅ Visualizer クラスが存在します"
    except ImportError as e:
        return False, f"❌ Visualizer クラスのインポート失敗: {e}"


def test_visualizer_methods():
    """Visualizer の主要メソッドが存在することを確認"""
    try:
        from visualizer import Visualizer
        critical_methods = [
            'detect_period_log_files', 'load_logs_data',
            'create_interactive_chart', 'visualize_backtest'
        ]
        missing = [m for m in critical_methods if not hasattr(Visualizer, m)]
        if missing:
            return False, f"❌ 欠落メソッド: {missing}"
        return True, f"✅ 主要メソッド({len(critical_methods)})が存在"
    except Exception as e:
        return False, f"❌ メソッド確認エラー: {e}"


def test_visualization_methods():
    """グラフ生成・可視化メソッドが存在することを確認"""
    try:
        from visualizer import Visualizer
        
        viz_methods = [
            "detect_period_log_files",
            "load_logs_data",
            "create_interactive_chart",
            "visualize_backtest"
        ]
        
        missing = []
        for method in viz_methods:
            if not hasattr(Visualizer, method):
                missing.append(method)
        
        if missing:
            return False, f"❌ 欠落可視化メソッド: {missing}"
        
        return True, f"✅ 可視化メソッド({len(viz_methods)})すべて存在"
    except Exception as e:
        return False, f"❌ 可視化メソッド確認エラー: {e}"


def test_visualizer_init():
    """Visualizer.__init__ が存在することを確認"""
    try:
        from visualizer import Visualizer
        
        if hasattr(Visualizer, "__init__"):
            sig = inspect.signature(Visualizer.__init__)
            return True, f"✅ Visualizer.__init__ が定義されています (パラメータ: {len(list(sig.parameters.keys()))-1} 個)"
        else:
            return False, f"❌ __init__ が見つかりません"
    except Exception as e:
        return False, f"❌ __init__ 確認エラー: {e}"


def test_html_output_capability():
    """HTML出力機能があることを確認（create_interactive_chart）"""
    try:
        from visualizer import Visualizer
        
        if hasattr(Visualizer, "create_interactive_chart"):
            return True, f"✅ HTML可視化メソッド（create_interactive_chart）が存在"
        else:
            return False, f"❌ HTML可視化メソッドが見つかりません"
    except Exception as e:
        return False, f"❌ HTML出力機能確認エラー: {e}"


def run_all_tests():
    """全テストを実行"""
    tests = [
        ("Visualizer クラス存在確認", test_visualizer_exists),
        ("Visualizer メソッド確認", test_visualizer_methods),
        ("可視化メソッド確認", test_visualization_methods),
        ("Visualizer.__init__ 確認", test_visualizer_init),
        ("HTML出力機能確認", test_html_output_capability),
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
    print("🧪 visualizer.py レグレッションテスト")
    print("=" * 70)
    results = run_all_tests()
    
    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(results)
    
    print()
    print(f"📊 結果: {passed_count}/{total_count} 成功")
    
    # 結果を JSON で保存
    RESULTS_DIR = os.path.join(WORKSPACE_ROOT, "docs/regression_test_results")
    os.makedirs(RESULTS_DIR, exist_ok=True)
    
    with open(os.path.join(RESULTS_DIR, "test_visualizer_regression.json"), "w", encoding="utf-8") as f:
        json.dump({
            "file": "visualizer.py",
            "total": total_count,
            "passed": passed_count,
            "results": results,
            "timestamp": datetime.now().isoformat()
        }, f, ensure_ascii=False, indent=2)
    
    sys.exit(0 if passed_count == total_count else 1)
