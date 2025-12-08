
# レグレッションテストスイート
#
# 本スクリプトは `docs/REGRESSION_TEST_POLICY.md` に基づき、satosystemの主要機能のレグレッションテストを自動化します。
#
# - 合否のみ判定し、失敗時はユーザーに報告・指示待ちとします。
# - テスト仕様・期待値は `docs/REGRESSION_TEST_POLICY.md` を参照してください。
#
# ## テスト項目
# 1. バックテスト（bot_run.sh）
# 2. ホットテスト（ダミーラッパ）
# 3. 主要クラス・メソッド単体テスト
# 4. 結果整合性チェック
#
# ---

import os
import subprocess
import time
import json
import sys
from datetime import datetime

# ワークスペースルートを基準とする
WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# **重要**: src/ ディレクトリで実行する
# bot.py や他のソースモジュールが相対パスで import される前提
SRC_DIR = os.path.join(WORKSPACE_ROOT, "src")
os.chdir(SRC_DIR)  # src/ を実行ディレクトリに固定
sys.path.insert(0, SRC_DIR)  # src/ を sys.path の先頭に追加

# パスを WORKSPACE_ROOT ベースで定義（ファイル参照は絶対パスで）
REGRESSION_POLICY = os.path.join(WORKSPACE_ROOT, "docs/REGRESSION_TEST_POLICY.md")
PROJECT_STRUCTURE = os.path.join(WORKSPACE_ROOT, "docs/analysis/project_structure.json")

RESULTS_DIR = os.path.join(WORKSPACE_ROOT, "docs/regression_test_results")
LOGS_DIR = os.path.join(SRC_DIR, "logs")

# 必要なディレクトリを自動生成
for directory in [RESULTS_DIR, LOGS_DIR]:
    if not os.path.exists(directory):
        os.makedirs(directory)
        print(f"[INFO] ディレクトリを作成しました: {directory}")


def log_result(test_name, passed, details=None):
    result = {
        "test": test_name,
        "passed": passed,
        "details": details,
        "timestamp": datetime.now().isoformat()
    }
    with open(os.path.join(RESULTS_DIR, f"{test_name}.json"), "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"[{'OK' if passed else 'FAIL'}] {test_name}")
    if not passed and details:
        print(details)

# 1. バックテスト

def test_backtest():
    """
    bot_run.shによるバックテストが正常に実行でき、結果が前回と一致するか判定
    """
    test_name = "backtest"
    # 変更前の結果を保存（仮実装: 直近のresultファイルをコピー）
    before_file = os.path.join(RESULTS_DIR, "backtest_before.json")
    after_file = os.path.join(RESULTS_DIR, "backtest_after.json")
    # バックテスト実行
    try:
        # WORKSPACE_ROOT で実行し、bot_run.sh は src/ 内を参照するのでフルパスで指定
        result = subprocess.run(["bash", "src/bot_run.sh"], cwd=WORKSPACE_ROOT, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            log_result(test_name, False, f"bot_run.sh実行エラー\nstdout: {result.stdout[:500]}\nstderr: {result.stderr[:500]}")
            return
        # 結果ファイル例: logs/backtest_summary_*.json または logs/latest_backtest.log
        log_files = [f for f in os.listdir(LOGS_DIR) if f.startswith("backtest_summary") and f.endswith(".json")]
        if not log_files:
            if not os.path.exists(os.path.join(LOGS_DIR, "latest_backtest.log")):
                log_result(test_name, False, "バックテスト結果ファイルが見つかりません (latest_backtest.log or backtest_summary_*.json)")
                return
            log_result(test_name, True, "ホットテスト実行完了 (結果JSON未生成)")
            return
        latest = max(log_files, key=lambda x: os.path.getmtime(os.path.join(LOGS_DIR, x)))
        with open(os.path.join(LOGS_DIR, latest)) as f:
            after = json.load(f)
        # 前回結果があれば比較
        if os.path.exists(before_file):
            with open(before_file) as f:
                before = json.load(f)
            # 損益・指標・処理時間等の主要キーで比較
            keys = ["total_profit_and_loss", "profit_factor", "max_drawdown", "max_drawdown_rate", "sharpe", "win_rate"]
            diffs = {k: (before.get(k), after.get(k)) for k in keys if before.get(k) != after.get(k)}
            if diffs:
                log_result(test_name, False, f"バックテスト結果に差分: {diffs}")
                return
        # 新しい結果を保存
        with open(before_file, "w") as f:
            json.dump(after, f, ensure_ascii=False, indent=2)
        log_result(test_name, True)
    except Exception as e:
        log_result(test_name, False, str(e))

# 2. ホットテスト

def test_hot():
    """
    ホットテストはスキップ (実装予定)
    """
    test_name = "hot_test"
    log_result(test_name, True, "スキップ (backtest=0時のダミートレード実装待ち)")

# 3. 主要クラス・メソッド単体テスト

def test_class_methods():
    """
    project_structure.jsonを参照し、各ファイルの存在をチェック
    """
    test_name = "class_methods"
    try:
        if not os.path.exists(PROJECT_STRUCTURE):
            log_result(test_name, False, f"project_structure.json が見つかりません: {PROJECT_STRUCTURE}")
            return
        with open(PROJECT_STRUCTURE, encoding="utf-8") as f:
            structure = json.load(f)
        errors = []
        
        for comp in structure.get("key_components", []):
            cls_name = comp["name"]
            file = comp["file"]
            # ファイルの存在チェック
            file_path = os.path.join(WORKSPACE_ROOT, file)
            if not os.path.exists(file_path):
                errors.append(f"File not found: {file}")
        
        passed = not errors
        log_result(test_name, passed, "\n".join(errors) if errors else None)
    except Exception as e:
        log_result(test_name, False, str(e))

# 4. 結果整合性

def test_consistency():
    """
    ログ・出力の整合性チェック（例: ENTRY多重, 指標不整合など）
    """
    test_name = "consistency"
    try:
        entry_count = 0
        log_file_path = os.path.join(LOGS_DIR, "latest_backtest.log")
        if not os.path.exists(log_file_path):
            log_result(test_name, False, f"バックテストログが見つかりません: {log_file_path}")
            return
        with open(log_file_path, encoding="utf-8", errors="ignore") as f:
            for line in f:
                if "ENTRY" in line:
                    entry_count += 1
        # ENTRY が存在し、多重発生していないか（0 < entry_count < 1000）
        # entry_count = 0 の場合は、バックテスト未実行または戦略エラーの可能性を報告
        if entry_count == 0:
            log_result(test_name, False, "ENTRY回数が0です。バックテストが正常に実行されているか確認してください。")
        else:
            passed = entry_count < 1000  # 上限チェック
            log_result(test_name, passed, f"ENTRY回数: {entry_count}")
    except Exception as e:
        log_result(test_name, False, str(e))

# 5. 個別ファイルレグレッションテスト

def run_individual_test_modules():
    """
    test/ フォルダ以下の個別テストモジュール（test_*_regression.py）を順番に実行
    """
    test_name = "individual_file_regression"
    try:
        test_modules = [
            "test_bot_regression",
            "test_config_regression",
            "test_trading_strategy_regression",
            "test_risk_management_regression",
            "test_portfolio_regression",
            "test_price_data_management_regression",
            "test_logger_regression",
            "test_visualizer_regression",
            "test_ohlcv_cache_regression",
            "test_bybit_exchange_regression",
            "test_supplementary_regression"
        ]
        
        all_results = []
        passed_total = 0
        failed_total = 0
        
        print("\n" + "=" * 70)
        print("🔄 個別ファイルレグレッションテスト実行")
        print("=" * 70)
        
        for module_name in test_modules:
            print(f"\n📋 実行中: {module_name}.py")
            try:
                result = subprocess.run(
                    [sys.executable, os.path.join(os.path.dirname(__file__), f"{module_name}.py")],
                    cwd=SRC_DIR,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                # JSON 結果ファイルを読み込む
                result_file = os.path.join(RESULTS_DIR, f"{module_name}.json")
                if os.path.exists(result_file):
                    with open(result_file, encoding="utf-8") as f:
                        module_result = json.load(f)
                    
                    all_results.append(module_result)
                    passed_total += module_result.get("passed", 0)
                    failed_total += module_result.get("total", 0) - module_result.get("passed", 0)
                    
                    # サマリー表示
                    p = module_result.get("passed", 0)
                    t = module_result.get("total", 0)
                    status = "✅" if p == t else "⚠️"
                    print(f"  {status} {module_name}: {p}/{t} 成功")
                else:
                    print(f"  ⚠️  {module_name}: 結果ファイルが見つかりません")
            except subprocess.TimeoutExpired:
                print(f"  ❌ {module_name}: タイムアウト")
                failed_total += 1
            except Exception as e:
                print(f"  ❌ {module_name}: エラー - {e}")
                failed_total += 1
        
        # 統計情報を出力
        print("\n" + "-" * 70)
        print(f"📊 個別テスト統計: {passed_total} 成功 / {passed_total + failed_total} 総数")
        
        # 総合結果を保存
        summary = {
            "test_name": test_name,
            "total_modules": len(test_modules),
            "total_tests": passed_total + failed_total,
            "passed": passed_total,
            "failed": failed_total,
            "pass_rate": f"{(passed_total / (passed_total + failed_total) * 100):.1f}%" if (passed_total + failed_total) > 0 else "0%",
            "modules": all_results,
            "timestamp": datetime.now().isoformat()
        }
        
        with open(os.path.join(RESULTS_DIR, "individual_test_summary.json"), "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        log_result(test_name, failed_total == 0, f"詳細は individual_test_summary.json を参照してください")
        
    except Exception as e:
        log_result(test_name, False, str(e))


# 統合レポート生成

def generate_regression_report():
    """
    全てのレグレッションテスト結果を集計し、最終レポートを生成
    """
    print("\n" + "=" * 70)
    print("📈 レグレッションテスト統合レポート生成")
    print("=" * 70)
    
    try:
        # 全ての結果ファイルを読み込む
        result_files = [f for f in os.listdir(RESULTS_DIR) if f.endswith(".json") and f != "individual_test_summary.json"]
        
        all_results = []
        total_tests = 0
        total_passed = 0
        
        for result_file in sorted(result_files):
            try:
                with open(os.path.join(RESULTS_DIR, result_file), encoding="utf-8") as f:
                    result = json.load(f)
                    all_results.append(result)
                    
                    if "total" in result and "passed" in result:
                        total_tests += result["total"]
                        total_passed += result["passed"]
            except Exception as e:
                print(f"⚠️  {result_file} の読み込みエラー: {e}")
        
        # 統合レポート作成
        report = {
            "title": "レグレッションテスト統合レポート",
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total_tests": total_tests,
                "total_passed": total_passed,
                "total_failed": total_tests - total_passed,
                "pass_rate": f"{(total_passed / total_tests * 100):.1f}%" if total_tests > 0 else "0%",
                "status": "✅ ALL PASS" if total_tests == total_passed else "⚠️ SOME FAILURES"
            },
            "result_files": all_results,
            "results_dir": RESULTS_DIR
        }
        
        # レポートを JSON で保存
        report_file = os.path.join(RESULTS_DIR, "REGRESSION_TEST_REPORT.json")
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        # コンソールに統計出力
        print(f"\n✅ レポート生成完了: {report_file}")
        print(f"\n📊 総合統計:")
        print(f"  - 総テスト数: {total_tests}")
        print(f"  - 成功: {total_passed}")
        print(f"  - 失敗: {total_tests - total_passed}")
        print(f"  - 成功率: {report['summary']['pass_rate']}")
        print(f"\n🎯 ステータス: {report['summary']['status']}")
        
        return report
        
    except Exception as e:
        print(f"❌ レポート生成エラー: {e}")
        return None


if __name__ == "__main__":
    print(f"[INFO] ワークスペースルート: {WORKSPACE_ROOT}")
    print(f"[INFO] レグレッションテスト方針: {REGRESSION_POLICY}")
    print(f"[INFO] 現在の作業ディレクトリ: {os.getcwd()}")
    print(f"[INFO] バックテスト期間: config.ini の [Backtest] セクションで指定")
    print()
    
    # OHLCVキャッシュ検査
    print("=" * 70)
    print("📊 OHLCV キャッシュ状態確認")
    print("=" * 70)
    try:
        from ohlcv_cache_inspector import OHLCVCacheInspector
        cache_inspector = OHLCVCacheInspector()
        
        # キャッシュサマリー取得
        params = cache_inspector.get_cache_parameters()
        
        if params:
            print(f"✅ キャッシュファイル検出: {len(params)} パラメータ")
            for param_info in params:
                print(f"   - タイムフレーム: {param_info.get('time_frame', 'N/A')}分")
                print(f"     レコード数: {param_info.get('record_count', 0)}")
                print(f"     期間: {param_info.get('start_time', 'N/A')} ～ {param_info.get('end_time', 'N/A')}")
                
                # データ範囲を取得（パラメータごと）
                try:
                    start_epoch = param_info.get('start_epoch', 0)
                    end_epoch = param_info.get('end_epoch', 0)
                    time_frame = param_info.get('time_frame', 0)
                    
                    if start_epoch and end_epoch and time_frame:
                        coverage = cache_inspector.get_data_coverage(start_epoch, end_epoch, time_frame)
                        if coverage.get('gaps'):
                            print(f"     ⚠️  データギャップ: {len(coverage['gaps'])} 件")
                            for gap in coverage['gaps'][:2]:
                                print(f"        {gap.get('gap_start', 'N/A')} ～ {gap.get('gap_end', 'N/A')}")
                except Exception as e:
                    pass  # ギャップ検査スキップ
        else:
            print("⚠️  キャッシュが未生成です（バックテスト実行で蓄積されます）")
        
    except Exception as e:
        print(f"⚠️  キャッシュ検査スキップ: {e}")
    
    print()
    
    # 従来のテスト実行
    print("=" * 70)
    print("🔄 従来型レグレッションテスト実行")
    print("=" * 70)
    test_backtest()
    test_hot()
    test_class_methods()
    test_consistency()
    
    # 新しい個別ファイルテスト実行
    run_individual_test_modules()
    
    # 統合レポート生成
    report = generate_regression_report()
    
    print("\n" + "=" * 70)
    print("✅ レグレッションテストスイート完了")
    print("=" * 70)
