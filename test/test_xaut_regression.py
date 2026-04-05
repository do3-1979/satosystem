"""
XAUT/USDT レグレッションテスト

config_xaut.ini の読み込み・設定値の妥当性検証、
XAUT 専用機能（ChandelierExit 等）の動作確認
"""

import os
import sys
import json
import subprocess
from datetime import datetime

# sys.path 設定
WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(WORKSPACE_ROOT, "src")
RESULTS_DIR = os.path.join(WORKSPACE_ROOT, "docs/regression_test_results")
sys.path.insert(0, SRC_DIR)
os.makedirs(RESULTS_DIR, exist_ok=True)


def test_xaut_config_exists():
    """config_xaut.ini が存在することを確認"""
    config_path = os.path.join(SRC_DIR, "config_xaut.ini")
    if os.path.exists(config_path):
        return True, f"✅ config_xaut.ini が存在します"
    return False, f"❌ config_xaut.ini が見つかりません: {config_path}"


def test_xaut_config_market():
    """config_xaut.ini の市場設定が XAUT/USDT であることを確認"""
    config_path = os.path.join(SRC_DIR, "config_xaut.ini")
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            content = f.read()
        if 'market = XAUT/USDT' in content:
            return True, "✅ market = XAUT/USDT"
        # 他の形式も許容
        for line in content.splitlines():
            if line.strip().startswith('market') and 'XAUT' in line:
                return True, f"✅ XAUT 市場設定を確認: {line.strip()}"
        return False, "❌ market に XAUT が設定されていません"
    except Exception as e:
        return False, f"❌ 設定ファイル読み込みエラー: {e}"


def test_xaut_config_chandelier_exit():
    """config_xaut.ini に ChandelierExit が有効化されていることを確認"""
    config_path = os.path.join(SRC_DIR, "config_xaut.ini")
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            content = f.read()
        if 'enable_chandelier_exit = 1' in content:
            return True, "✅ ChandelierExit が有効 (enable_chandelier_exit = 1)"
        return False, "❌ ChandelierExit が無効または未設定"
    except Exception as e:
        return False, f"❌ 設定ファイル読み込みエラー: {e}"


def test_xaut_config_load():
    """Config.load_config() で config_xaut.ini を読み込めることを確認"""
    try:
        from config import Config
        config_path = os.path.join(SRC_DIR, "config_xaut.ini")
        Config.load_config(config_path)
        market = Config.get_market()
        if 'XAUT' in market:
            return True, f"✅ Config.load_config() 成功: market={market}"
        return False, f"❌ market に XAUT がありません: {market}"
    except Exception as e:
        return False, f"❌ Config.load_config() エラー: {e}"
    finally:
        # BTC 設定に戻す
        try:
            from config import Config
            btc_config = os.path.join(SRC_DIR, "config.ini")
            Config.load_config(btc_config)
        except Exception:
            pass


def test_xaut_config_params():
    """config_xaut.ini の主要パラメータが合理的な範囲内であることを確認"""
    config_path = os.path.join(SRC_DIR, "config_xaut.ini")
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            content = f.read()

        issues = []

        # leverage が 1-20 の範囲
        for line in content.splitlines():
            line = line.strip()
            if line.startswith('leverage ='):
                val = int(line.split('=')[1].strip())
                if not (1 <= val <= 20):
                    issues.append(f"leverage={val} が範囲外(1-20)")
            elif line.startswith('risk_percentage ='):
                val = float(line.split('=')[1].strip())
                if not (0.01 <= val <= 1.0):
                    issues.append(f"risk_percentage={val} が範囲外(0.01-1.0)")
            elif line.startswith('donchian_buy_term ='):
                val = int(line.split('=')[1].strip())
                if not (5 <= val <= 200):
                    issues.append(f"donchian_buy_term={val} が範囲外(5-200)")

        if issues:
            return False, f"❌ パラメータ異常: {'; '.join(issues)}"
        return True, "✅ 主要パラメータが合理的な範囲内"
    except Exception as e:
        return False, f"❌ パラメータ確認エラー: {e}"


def test_xaut_short_backtest():
    """XAUT config で短期バックテストが完走できることを確認"""
    try:
        # XAUT データ開始は 2025-04-03 なので 2025-06-01 ~ 2025-06-03 で実行
        result = subprocess.run(
            ["python3", "src/bot.py", "--config", "config_xaut.ini", "test",
             "2025-06-01", "2025-06-03"],
            cwd=WORKSPACE_ROOT,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            return True, "✅ XAUT 短期バックテスト (2025-06-01~06-03) 完走"
        return False, f"❌ XAUT バックテスト失敗\nstderr: {result.stderr[:300]}"
    except subprocess.TimeoutExpired:
        return False, "❌ XAUT バックテストタイムアウト（120秒）"
    except Exception as e:
        return False, f"❌ 実行エラー: {e}"


def test_xaut_db_data_exists():
    """XAUT/USDT の OHLCV データが DB に存在することを確認"""
    try:
        sys.path.insert(0, os.path.join(WORKSPACE_ROOT, "src"))
        from ohlcv_cache import OHLCVCache
        cache = OHLCVCache()
        import sqlite3
        with sqlite3.connect(cache.cache_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM candles WHERE symbol LIKE '%XAUT%'"
            )
            count = cursor.fetchone()[0]
        if count > 0:
            return True, f"✅ XAUT DB レコード: {count} 件"
        return False, "❌ XAUT の DB データが 0 件です"
    except Exception as e:
        return False, f"❌ DB 確認エラー: {e}"


def run_all_tests():
    tests = [
        ("xaut_config_exists",     test_xaut_config_exists),
        ("xaut_config_market",     test_xaut_config_market),
        ("xaut_chandelier_exit",   test_xaut_config_chandelier_exit),
        ("xaut_config_load",       test_xaut_config_load),
        ("xaut_config_params",     test_xaut_config_params),
        ("xaut_db_data_exists",    test_xaut_db_data_exists),
        ("xaut_short_backtest",    test_xaut_short_backtest),
    ]

    passed = 0
    total = len(tests)
    results_detail = []

    for name, fn in tests:
        try:
            ok, msg = fn()
        except Exception as e:
            ok, msg = False, f"❌ 例外: {e}"
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}: {msg}")
        if ok:
            passed += 1
        results_detail.append({"name": name, "passed": ok, "detail": msg})

    # 結果を JSON に保存
    summary = {
        "test_file": "test_xaut_regression",
        "passed": passed,
        "total": total,
        "timestamp": datetime.now().isoformat(),
        "details": results_detail,
    }
    with open(os.path.join(RESULTS_DIR, "test_xaut_regression.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    return passed, total


if __name__ == "__main__":
    os.chdir(SRC_DIR)
    print("=" * 60)
    print("🧪 XAUT レグレッションテスト")
    print("=" * 60)
    passed, total = run_all_tests()
    print(f"\n{'✅' if passed == total else '❌'} {passed}/{total} テスト合格")
    sys.exit(0 if passed == total else 1)
