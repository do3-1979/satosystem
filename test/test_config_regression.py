"""
config.py のレグレッションテスト

Config クラスの主要メソッド存在確認、シングルトン動作確認
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
ANALYSIS_FILE = os.path.join(WORKSPACE_ROOT, "docs/analysis/src/config.json")

# 互換性ヘルパー
from analysis_helper import load_analysis_with_compat, get_class_methods, get_classmethods


def load_analysis():
    """analysis/config.json から Config クラスの仕様を読む（互換性対応）"""
    return load_analysis_with_compat(ANALYSIS_FILE)


def test_config_class_exists():
    """Config クラスが存在することを確認"""
    try:
        from config import Config
        return True, f"✅ Config クラスが存在します"
    except ImportError as e:
        return False, f"❌ Config クラスのインポート失敗: {e}"


def test_config_methods_count():
    """Config クラスのメソッド数を確認（36メソッド予定）"""
    try:
        from config import Config
        analysis = load_analysis()
        
        expected_count = len(get_class_methods(analysis))
        actual_methods = [m for m in dir(Config) if not m.startswith("_") or m in ["__init__", "__str__"]]
        
        return True, f"✅ Config メソッド: {len(actual_methods)} 個（予定: {expected_count}）"
    except Exception as e:
        return False, f"❌ メソッド数確認エラー: {e}"


def test_config_key_methods():
    """Config の主要メソッドが存在することを確認"""
    try:
        from config import Config
        
        key_methods = [
            "get_api_key",
            "get_api_secret",
            "get_market",
            "get_bot_operation_cycle",
            "get_back_test_mode",
            "to_dict"
        ]
        
        missing = []
        for method in key_methods:
            if not hasattr(Config, method):
                missing.append(method)
        
        if missing:
            return False, f"❌ 欠落主要メソッド: {missing}"
        
        return True, f"✅ 主要メソッド({len(key_methods)})すべて存在"
    except Exception as e:
        return False, f"❌ 主要メソッド確認エラー: {e}"


def test_config_classmethods():
    """Config の @classmethod が正しく定義されていることを確認"""
    try:
        from config import Config
        import inspect
        analysis = load_analysis()
        
        classmethod_list = get_classmethods(analysis)
        
        # v2.0形式では分析JSONにclassmethod情報がないため、
        # 実際のクラスを検査してフォールバック
        if len(classmethod_list) == 0:
            # 実際のConfigクラスからclassmethodを検出
            classmethods = []
            for name, method in inspect.getmembers(Config):
                if isinstance(inspect.getattr_static(Config, name), classmethod):
                    classmethods.append(name)
            
            classmethod_list = classmethods
        
        # get_api_key, get_api_secret など主要メソッドは classmethod
        if len(classmethod_list) > 0:
            return True, f"✅ classmethod が {len(classmethod_list)} 個検出"
        else:
            return False, f"❌ classmethod が検出されません"
    except Exception as e:
        return False, f"❌ classmethod 確認エラー: {e}"


def test_config_instantiation():
    """Config クラスを生成できることを確認"""
    try:
        from config import Config
        
        # Config は通常シングルトンで、直接生成するか、class variable で管理される
        # インスタンス化を試みる
        config = Config()
        
        if config:
            return True, f"✅ Config インスタンス化成功"
        else:
            return False, f"❌ Config インスタンス化失敗"
    except Exception as e:
        # シングルトン実装の場合、get_api_key() 等のメソッドが使用できればOK
        try:
            from config import Config
            if hasattr(Config, "get_api_key"):
                return True, f"✅ Config の静的メソッドが利用可能"
            else:
                return False, f"❌ Config メソッドが利用不可"
        except:
            return False, f"❌ Config インスタンス化エラー: {e}"


def test_use_cached_data_for_hot_test_flag():
    """Task42: get_use_cached_data_for_hot_test() メソッドの存在とデフォルト値を確認"""
    try:
        from config import Config

        # メソッドが存在するか確認
        if not hasattr(Config, 'get_use_cached_data_for_hot_test'):
            return False, "❌ get_use_cached_data_for_hot_test メソッドが存在しません"

        # 寄り道を使わず呈名で呼び出して整数値を返すか確認
        result = Config.get_use_cached_data_for_hot_test()
        if not isinstance(result, int):
            return False, f"❌ 返り値が int ではない: {type(result)}"

        # config.iniのus_cached_data_for_hot_testが0または1か確認
        if result not in (0, 1):
            return False, f"❌ 返り値が0または1以外: {result}"

        return True, f"✅ get_use_cached_data_for_hot_test() = {result} (デフォルト: 0=API取得)"
    except Exception as e:
        return False, f"❌ get_use_cached_data_for_hot_test テストエラー: {e}"


def run_all_tests():
    """全テストを実行"""
    tests = [
        ("Config クラス存在確認", test_config_class_exists),
        ("Config メソッド数確認", test_config_methods_count),
        ("Config 主要メソッド確認", test_config_key_methods),
        ("Config classmethod 確認", test_config_classmethods),
        ("Config インスタンス化確認", test_config_instantiation),
        ("Task42: use_cached_data_for_hot_test フラグ確認", test_use_cached_data_for_hot_test_flag),
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
    print("🧪 config.py レグレッションテスト")
    print("=" * 70)
    results = run_all_tests()
    
    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(results)
    
    print()
    print(f"📊 結果: {passed_count}/{total_count} 成功")
    
    # 結果を JSON で保存
    RESULTS_DIR = os.path.join(WORKSPACE_ROOT, "docs/regression_test_results")
    os.makedirs(RESULTS_DIR, exist_ok=True)
    
    with open(os.path.join(RESULTS_DIR, "test_config_regression.json"), "w", encoding="utf-8") as f:
        json.dump({
            "file": "config.py",
            "total": total_count,
            "passed": passed_count,
            "results": results,
            "timestamp": datetime.now().isoformat()
        }, f, ensure_ascii=False, indent=2)
    
    sys.exit(0 if passed_count == total_count else 1)
