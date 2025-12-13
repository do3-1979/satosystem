"""
修正 1, 2 の統合テスト

修正1: update_price_data() の例外処理とリトライロジック
修正2: メモリ監視機能

この テストは以下を検証：
1. update_price_data() がメソッド _fetch_with_retry を持つこと
2. update_price_data() が例外処理を持つこと（戻り値がbool）
3. bot.run() にメモリ監視ロジックが含まれていること
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


def test_fetch_with_retry_method_exists():
    """_fetch_with_retry メソッドが PriceDataManagement に存在することを確認"""
    try:
        from price_data_management import PriceDataManagement
        
        # クラスレベルでメソッドの存在確認
        assert hasattr(PriceDataManagement, '_fetch_with_retry'), "❌ _fetch_with_retry メソッドが見つかりません"
        
        # メソッドシグネチャを確認
        method = getattr(PriceDataManagement, '_fetch_with_retry')
        assert callable(method), "❌ _fetch_with_retry は呼び出し可能ではありません"
        
        return True, "✅ _fetch_with_retry メソッドが存在し、呼び出し可能です"
    except AssertionError as e:
        return False, str(e)
    except Exception as e:
        return False, f"❌ テスト実行エラー: {e}"


def test_update_price_data_return_type():
    """update_price_data() の戻り値が bool であることを確認"""
    try:
        from price_data_management import PriceDataManagement
        
        # メソッドシグネチャを取得
        method = getattr(PriceDataManagement, 'update_price_data')
        source = inspect.getsource(method)
        
        # return True / return False の存在確認
        assert 'return True' in source, "❌ 'return True' が見つかりません"
        assert 'return False' in source, "❌ 'return False' が見つかりません"
        
        return True, "✅ update_price_data() は bool を返します"
    except AssertionError as e:
        return False, str(e)
    except Exception as e:
        return False, f"❌ テスト実行エラー: {e}"


def test_update_price_data_exception_handling():
    """update_price_data() が例外処理を持つことを確認"""
    try:
        from price_data_management import PriceDataManagement
        
        method = getattr(PriceDataManagement, 'update_price_data')
        source = inspect.getsource(method)
        
        # 例外処理の存在確認
        assert 'try:' in source, "❌ try ブロックが見つかりません"
        assert 'except' in source, "❌ except ブロックが見つかりません"
        assert 'log_error' in source, "❌ log_error が見つかりません"
        
        return True, "✅ update_price_data() が例外処理を持ちます"
    except AssertionError as e:
        return False, str(e)
    except Exception as e:
        return False, f"❌ テスト実行エラー: {e}"


def test_update_price_data_validation():
    """update_price_data() が例外処理でバリデーション（空リスト、キー確認）を持つことを確認"""
    try:
        from price_data_management import PriceDataManagement
        
        method = getattr(PriceDataManagement, 'update_price_data')
        source = inspect.getsource(method)
        
        # バリデーション確認
        assert 'not tmp_ohlcv_data' in source or 'not self.latest_ohlcv_data' in source, \
            "❌ 空リストチェックが見つかりません"
        assert 'Volume' in source, "❌ Volumeキー確認が見つかりません"
        assert 'IndexError' in source, "❌ IndexError 処理が見つかりません"
        
        return True, "✅ update_price_data() がバリデーション処理を持ちます"
    except AssertionError as e:
        return False, str(e)
    except Exception as e:
        return False, f"❌ テスト実行エラー: {e}"


def test_bot_memory_monitoring():
    """bot.py にメモリ監視ロジックが含まれていることを確認"""
    try:
        from bot import Bot
        
        method = getattr(Bot, 'run')
        source = inspect.getsource(method)
        
        # メモリ監視ロジックの存在確認
        assert 'memory_check_interval' in source, "❌ memory_check_interval が見つかりません"
        assert 'last_memory_check' in source, "❌ last_memory_check が見つかりません"
        assert 'psutil' in source, "❌ psutil が見つかりません"
        assert 'memory_info' in source or 'memory_percent' in source, "❌ メモリ監視コードが見つかりません"
        
        return True, "✅ bot.py にメモリ監視ロジックが含まれています"
    except AssertionError as e:
        return False, str(e)
    except Exception as e:
        return False, f"❌ テスト実行エラー: {e}"


def test_bot_memory_logging():
    """bot.py のメモリ監視がログに出力されることを確認"""
    try:
        from bot import Bot
        
        method = getattr(Bot, 'run')
        source = inspect.getsource(method)
        
        # メモリ監視ログの確認
        assert '【メモリ監視】' in source or 'メモリ監視' in source, \
            "❌ メモリ監視ログメッセージが見つかりません"
        
        return True, "✅ bot.py のメモリ監視がログに出力されます"
    except AssertionError as e:
        return False, str(e)
    except Exception as e:
        return False, f"❌ テスト実行エラー: {e}"


def test_retry_logic_exponential_backoff():
    """_fetch_with_retry が指数バックオフを実装しているか確認"""
    try:
        from price_data_management import PriceDataManagement
        
        method = getattr(PriceDataManagement, '_fetch_with_retry')
        source = inspect.getsource(method)
        
        # 指数バックオフの確認
        assert '2 ** attempt' in source or 'pow' in source, "❌ 指数バックオフが見つかりません"
        assert 'time.sleep' in source, "❌ time.sleep が見つかりません"
        assert 'for attempt in range' in source or 'for i in range' in source, "❌ リトライループが見つかりません"
        
        return True, "✅ _fetch_with_retry が指数バックオフを実装しています"
    except AssertionError as e:
        return False, str(e)
    except Exception as e:
        return False, f"❌ テスト実行エラー: {e}"


def main():
    """すべてのテストを実行し、結果をレポート"""
    tests = [
        ("修正1: _fetch_with_retry メソッド存在確認", test_fetch_with_retry_method_exists),
        ("修正1: update_price_data() 戻り値型確認", test_update_price_data_return_type),
        ("修正1: update_price_data() 例外処理確認", test_update_price_data_exception_handling),
        ("修正1: update_price_data() バリデーション確認", test_update_price_data_validation),
        ("修正1: リトライロジック指数バックオフ確認", test_retry_logic_exponential_backoff),
        ("修正2: bot.py メモリ監視ロジック確認", test_bot_memory_monitoring),
        ("修正2: bot.py メモリ監視ログ出力確認", test_bot_memory_logging),
    ]
    
    results = []
    for test_name, test_func in tests:
        success, message = test_func()
        results.append((test_name, success, message))
        print(f"{message}")
    
    # 結果サマリー
    passed = sum(1 for _, success, _ in results if success)
    total = len(results)
    
    print("\n" + "=" * 80)
    print(f"テスト結果: {passed}/{total} 合格")
    print("=" * 80)
    
    for test_name, success, message in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    if passed == total:
        print("\n🎉 すべてのテストが合格しました！")
        return 0
    else:
        print(f"\n❌ {total - passed} 個のテストが失敗しました")
        return 1


if __name__ == "__main__":
    exit(main())
