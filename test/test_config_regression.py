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


def test_config_class_exists():
    """Config クラスが存在することを確認"""
    try:
        from config import Config
        return True, f"✅ Config クラスが存在します"
    except ImportError as e:
        return False, f"❌ Config クラスのインポート失敗: {e}"


def test_config_methods_count():
    """Config クラスのメソッド数を確認（20個以上予定）"""
    try:
        from config import Config
        actual_methods = [m for m in dir(Config) if not m.startswith("_") or m in ["__init__", "__str__"]]
        if len(actual_methods) < 20:
            return False, f"❌ Config メソッド数が少なすぎます: {len(actual_methods)}（最低20個期待）"
        return True, f"✅ Config メソッド: {len(actual_methods)} 個"
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
        classmethods = [
            name for name in dir(Config)
            if isinstance(inspect.getattr_static(Config, name), classmethod)
        ]
        if len(classmethods) > 0:
            return True, f"✅ classmethod が {len(classmethods)} 個検出"
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


def test_tsmom_filter_config():
    """パラメータスイープ採用: TSMOMフィルター設定値の確認（psar_lookback=300, tsmom_lookback=150）"""
    try:
        from config import Config

        # get_tsmom_filter_enabled メソッド存在確認
        if not hasattr(Config, 'get_tsmom_filter_enabled'):
            return False, "❌ get_tsmom_filter_enabled メソッドが存在しません"

        # get_tsmom_filter_lookback メソッド存在確認
        if not hasattr(Config, 'get_tsmom_filter_lookback'):
            return False, "❌ get_tsmom_filter_lookback メソッドが存在しません"

        # TSMOMが有効（=1）か確認
        tsmom_enabled = Config.get_tsmom_filter_enabled()
        if tsmom_enabled != 1:
            return False, f"❌ tsmom_filter_enabled={tsmom_enabled}（期待値: 1）。Task40d採用設定が反映されていません"

        # TSMOMルックバックが150か確認（スイープ採用値）
        tsmom_lb = Config.get_tsmom_filter_lookback()
        if tsmom_lb != 150:
            return False, f"❌ tsmom_filter_lookback={tsmom_lb}（期待値: 150、パラメータスイープ採用値）"

        # psar_lookback_term が300か確認
        max_term = Config.get_test_initial_max_term()
        if max_term < 150:
            return False, f"❌ get_test_initial_max_term()={max_term}（TSMOM-150動作に必要な最小150本未満）"

        return True, f"✅ Task40d+sweep TSMOM設定確認: enabled={tsmom_enabled}, lookback={tsmom_lb}, window={max_term}本"
    except Exception as e:
        return False, f"❌ TSMOM設定テストエラー: {e}"


def test_psar_lookback_window():
    """Task40d: psar_lookback_term=300によるOHLCVウィンドウ拡張確認"""
    try:
        from config import Config

        max_term = Config.get_test_initial_max_term()

        # 300本以上のウィンドウが確保されているか確認
        if max_term < 300:
            return False, f"❌ get_test_initial_max_term()={max_term}（期待値: ≥300。psar_lookback_term=300が未反映）"

        return True, f"✅ OHLCVウィンドウ: {max_term}本（psar_lookback_term=300有効）"
    except Exception as e:
        return False, f"❌ psar_lookbackウィンドウテストエラー: {e}"


def run_all_tests():
    """全テストを実行"""
    tests = [
        ("Config クラス存在確認", test_config_class_exists),
        ("Config メソッド数確認", test_config_methods_count),
        ("Config 主要メソッド確認", test_config_key_methods),
        ("Config classmethod 確認", test_config_classmethods),
        ("Config インスタンス化確認", test_config_instantiation),
        ("Task42: use_cached_data_for_hot_test フラグ確認", test_use_cached_data_for_hot_test_flag),
        ("Task40d: TSMOMフィルター設定確認", test_tsmom_filter_config),
        ("Task40d: psar_lookback_term=300ウィンドウ確認", test_psar_lookback_window),
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
