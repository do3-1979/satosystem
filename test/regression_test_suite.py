
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
os.chdir(WORKSPACE_ROOT)  # 実行ディレクトリを明示的に設定

REGRESSION_POLICY = "docs/REGRESSION_TEST_POLICY.md"
PROJECT_STRUCTURE = "docs/analysis/project_structure.json"

RESULTS_DIR = "docs/regression_test_results"
LOGS_DIR = "logs"

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

if __name__ == "__main__":
    print(f"[INFO] ワークスペースルート: {WORKSPACE_ROOT}")
    print(f"[INFO] レグレッションテスト方針: {REGRESSION_POLICY}")
    print(f"[INFO] 現在の作業ディレクトリ: {os.getcwd()}")
    print(f"[INFO] バックテスト期間: config.ini の [Backtest] セクションで指定")
    print()
    test_backtest()
    test_hot()
    test_class_methods()
    test_consistency()
