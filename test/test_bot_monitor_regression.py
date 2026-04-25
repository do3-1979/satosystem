"""
test_bot_monitor_regression.py — bot_monitor.py のレグレッションテスト

全てモックを使用し、実際のログファイル・Gmail・プロセスに依存しない。
"""

import json
import os
import sys
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

# src/ をパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bot_monitor import (
    BotAnalysisResult,
    BotMonitor,
    GmailSender,
    JST,
    LogAnalyzer,
    ReportBuilder,
    judge_bot_health,
    judge_entry_zero,
)


# ==============================================================
# TestLogAnalyzer
# ==============================================================

class TestLogAnalyzer(unittest.TestCase):

    def setUp(self):
        self.analyzer = LogAnalyzer()

    # --- find_latest_log ---

    def test_find_latest_log_normal(self):
        """正常: 最新ログファイルのパスを返す"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # ファイル2件作成（mtime が異なるように sleep なしで mtime 操作）
            old = os.path.join(tmpdir, "bot_BTC_20260420_090000.log")
            new = os.path.join(tmpdir, "bot_BTC_20260425_090000.log")
            Path(old).write_text("old")
            time.sleep(0.01)
            Path(new).write_text("new")

            result = self.analyzer.find_latest_log(Path(tmpdir), "BTC")
            self.assertEqual(result, new)

    def test_find_latest_log_empty_dir(self):
        """異常: ディレクトリが空 → None"""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.analyzer.find_latest_log(Path(tmpdir), "BTC")
            self.assertIsNone(result)

    def test_find_latest_log_no_dir(self):
        """異常: ディレクトリが存在しない → None"""
        result = self.analyzer.find_latest_log(Path("/nonexistent/path"), "BTC")
        self.assertIsNone(result)

    # --- parse_status_json ---

    def test_parse_status_json_normal(self):
        """正常: ネスト構造（latestキー配下）を正しくパース"""
        now_str = datetime.now(JST).strftime("%Y/%m/%d %H:%M:%S")
        data = {"updated_at": now_str,
                "latest": {"close": 93000.0, "adx": 25.5, "decision": "NONE"}}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            fname = f.name
        try:
            status, age = self.analyzer.parse_status_json(Path(fname))
            self.assertEqual(status["close"], 93000.0)
            self.assertEqual(status["adx"], 25.5)
            self.assertLess(age, 5.0)  # 作成直後なので数秒未満
        finally:
            os.unlink(fname)

    def test_parse_status_json_flat(self):
        """正常: フラット構造（latestキーなし）も動作"""
        data = {"close": 93000.0, "adx": 25.5, "decision": "NONE"}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            fname = f.name
        try:
            status, age = self.analyzer.parse_status_json(Path(fname))
            self.assertEqual(status["close"], 93000.0)
        finally:
            os.unlink(fname)

    def test_parse_status_json_not_found(self):
        """異常: ファイルが存在しない → 空 dict, inf"""
        status, age = self.analyzer.parse_status_json(Path("/nonexistent/status.json"))
        self.assertEqual(status, {})
        self.assertEqual(age, float("inf"))

    def test_parse_status_json_corrupted(self):
        """異常: JSONが壊れている → 空 dict, inf"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{invalid json!!!")
            fname = f.name
        try:
            status, age = self.analyzer.parse_status_json(Path(fname))
            self.assertEqual(status, {})
            self.assertEqual(age, float("inf"))
        finally:
            os.unlink(fname)

    # --- check_bot_alive ---

    def test_check_bot_alive_running(self):
        """正常: プロセス稼働中"""
        own_pid = os.getpid()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pid", delete=False) as f:
            f.write(str(own_pid))
            fname = f.name
        try:
            alive, pid = self.analyzer.check_bot_alive(Path(fname))
            self.assertTrue(alive)
            self.assertEqual(pid, own_pid)
        finally:
            os.unlink(fname)

    def test_check_bot_alive_no_pid_file(self):
        """異常: PIDファイルなし → False"""
        alive, pid = self.analyzer.check_bot_alive(Path("/nonexistent/bot.pid"))
        self.assertFalse(alive)
        self.assertIsNone(pid)

    def test_check_bot_alive_dead_process(self):
        """異常: 存在しないPID → False"""
        # PID 99999999 は通常存在しない
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pid", delete=False) as f:
            f.write("99999999")
            fname = f.name
        try:
            alive, pid = self.analyzer.check_bot_alive(Path(fname))
            self.assertFalse(alive)
        finally:
            os.unlink(fname)

    # --- count_log_pattern ---

    def test_count_log_pattern_normal(self):
        """正常: パターンにマッチする行数を返す"""
        content = (
            "2026-04-25 ERROR something\n"
            "2026-04-25 INFO normal\n"
            "2026-04-25 ERROR another\n"
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False, encoding="utf-8") as f:
            f.write(content)
            fname = f.name
        try:
            result = self.analyzer.count_log_pattern(fname, r"ERROR")
            self.assertEqual(result, 2)
        finally:
            os.unlink(fname)

    def test_count_log_pattern_no_file(self):
        """異常: ログファイルなし → 0"""
        result = self.analyzer.count_log_pattern("/nonexistent/bot.log", r"ERROR")
        self.assertEqual(result, 0)

    def test_log_age_calculation(self):
        """正常: ログの古さを計算（数秒以内）"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("test")
            fname = f.name
        try:
            age = self.analyzer.get_log_age_seconds(fname)
            self.assertLess(age, 5.0)  # 作成直後なので5秒未満
        finally:
            os.unlink(fname)


# ==============================================================
# TestBotAnalysis
# ==============================================================

class TestBotAnalysis(unittest.TestCase):

    def setUp(self):
        self.analyzer = LogAnalyzer()

    def _make_mock_analyzer(self, is_alive, log_age, error_count=0, rate_limit=0,
                             main_loop_err=0, entry_exec=0):
        """analyze() の結果をモックで返すヘルパー"""
        result = BotAnalysisResult(symbol="BTC")
        result.is_alive = is_alive
        result.pid = 12345 if is_alive else None
        result.last_log_age_seconds = log_age
        result.log_file = "bot_BTC_20260425_090000.log"
        result.status = {"close": 93000.0, "adx": 25.5, "decision": "NONE",
                         "dc_h": 95000.0, "dc_l": 88000.0, "pvo_val": -2.0,
                         "pnl": 0.0, "total_pnl": 10.0, "unionAvailable": 110.0,
                         "position_side": "NONE"}
        result.error_count = error_count
        result.rate_limit_count = rate_limit
        result.main_loop_error_count = main_loop_err
        result.main_loop_error_recent_count = main_loop_err  # モックでは同値を使用
        result.entry_executed = entry_exec
        return result

    def test_analyze_btc_all_normal(self):
        """正常: BTC分析モック（全て正常）"""
        with patch.object(self.analyzer, "check_bot_alive", return_value=(True, 12345)), \
             patch.object(self.analyzer, "parse_status_json", return_value=({"close": 93000.0}, 30.0)), \
             patch.object(self.analyzer, "find_latest_log", return_value="/tmp/bot_BTC_20260425.log"), \
             patch.object(self.analyzer, "get_log_age_seconds", return_value=30.0), \
             patch.object(self.analyzer, "count_log_pattern", return_value=2):

            from bot_monitor import BTC_LOGS_DIR, BTC_STATUS_JSON, BTC_PID_FILE
            result = self.analyzer.analyze("BTC", BTC_LOGS_DIR, BTC_STATUS_JSON, BTC_PID_FILE)

            self.assertTrue(result.is_alive)
            self.assertEqual(result.last_log_age_seconds, 30.0)
            self.assertEqual(result.error_count, 2)

    def test_analyze_xaut_all_normal(self):
        """正常: XAUT分析モック（全て正常）"""
        with patch.object(self.analyzer, "check_bot_alive", return_value=(True, 12346)), \
             patch.object(self.analyzer, "parse_status_json", return_value=({"close": 3245.0}, 40.0)), \
             patch.object(self.analyzer, "find_latest_log", return_value="/tmp/bot_XAUT_20260425.log"), \
             patch.object(self.analyzer, "get_log_age_seconds", return_value=45.0), \
             patch.object(self.analyzer, "count_log_pattern", return_value=0):

            from bot_monitor import XAUT_LOGS_DIR, XAUT_STATUS_JSON, XAUT_PID_FILE
            result = self.analyzer.analyze("XAUT", XAUT_LOGS_DIR, XAUT_STATUS_JSON, XAUT_PID_FILE)

            self.assertTrue(result.is_alive)
            self.assertEqual(result.symbol, "XAUT")

    def test_analyze_btc_bot_stopped(self):
        """異常: BTCが停止中"""
        with patch.object(self.analyzer, "check_bot_alive", return_value=(False, None)), \
             patch.object(self.analyzer, "parse_status_json", return_value=({}, float("inf"))), \
             patch.object(self.analyzer, "find_latest_log", return_value=None):

            from bot_monitor import BTC_LOGS_DIR, BTC_STATUS_JSON, BTC_PID_FILE
            result = self.analyzer.analyze("BTC", BTC_LOGS_DIR, BTC_STATUS_JSON, BTC_PID_FILE)

            self.assertFalse(result.is_alive)
            self.assertTrue(result.no_log)

    def test_analyze_xaut_many_errors(self):
        """異常: XAUTエラー多発（ERRORのみ600件、メインループエラーは0件）"""
        def _count_side_effect(log_path, pattern):
            # ERROR パターンのみ600、それ以外は0
            if pattern == r"ERROR":
                return 600
            return 0

        with patch.object(self.analyzer, "check_bot_alive", return_value=(True, 12346)), \
             patch.object(self.analyzer, "parse_status_json", return_value=({}, float("inf"))), \
             patch.object(self.analyzer, "find_latest_log", return_value="/tmp/bot_XAUT.log"), \
             patch.object(self.analyzer, "get_log_age_seconds", return_value=30.0), \
             patch.object(self.analyzer, "count_log_pattern", side_effect=_count_side_effect):

            from bot_monitor import XAUT_LOGS_DIR, XAUT_STATUS_JSON, XAUT_PID_FILE
            result = self.analyzer.analyze("XAUT", XAUT_LOGS_DIR, XAUT_STATUS_JSON, XAUT_PID_FILE)

            self.assertEqual(result.error_count, 600)
            self.assertEqual(result.main_loop_error_count, 0)  # 直近24h外はカウントされない
            icon, text = judge_bot_health(result)
            self.assertEqual(icon, "⚠️")
            self.assertIn("ERROR多発", text)


# ==============================================================
# TestReportBuilder
# ==============================================================

def _make_normal_result(symbol: str) -> BotAnalysisResult:
    r = BotAnalysisResult(symbol=symbol)
    r.is_alive = True
    r.pid = 12345
    r.last_log_age_seconds = 45.0
    r.log_file = f"bot_{symbol}_20260425_090000.log"
    r.status = {
        "close": 93000.0 if symbol == "BTC" else 3245.0,
        "adx": 25.5,
        "pvo_val": -2.0,
        "decision": "NONE",
        "position_side": "NONE",
        "dc_h": 95000.0 if symbol == "BTC" else 3310.0,
        "dc_l": 88000.0 if symbol == "BTC" else 3180.0,
        "pnl": 0.0,
        "total_pnl": 10.5,
        "unionAvailable": 110.5,
    }
    r.error_count = 2
    r.rate_limit_count = 1
    r.strategy_a_buy = 10
    r.strategy_a_sell = 8
    r.strategy_a_none = 982
    r.breakout_buy = 2
    r.breakout_sell = 1
    r.volume_filter_ng = 3
    r.adx_filter_ng = 0
    r.entry_allowed = 0
    r.entry_skipped = 3
    r.entry_executed = 0
    return r


class TestReportBuilder(unittest.TestCase):

    def setUp(self):
        self.builder = ReportBuilder()

    def test_build_report_both_normal(self):
        """正常: 両BOT正常時のレポート生成"""
        btc = _make_normal_result("BTC")
        xaut = _make_normal_result("XAUT")
        report = self.builder.build_report(btc, xaut)

        self.assertIn("BOT 監視レポート", report)  # タイトルにスペースあり
        self.assertIn("BTC BOT", report)
        self.assertIn("XAUT BOT", report)
        self.assertIn("【1. BOT稼働状況】", report)
        self.assertIn("【2. トレード状況】", report)
        self.assertIn("【3. シグナル・フィルタ整合性レポート】", report)
        self.assertIn("✅", report)

    def test_build_report_btc_stopped(self):
        """異常: BTC停止時のレポートに❌が含まれる"""
        btc = _make_normal_result("BTC")
        btc.is_alive = False
        btc.pid = None
        xaut = _make_normal_result("XAUT")

        report = self.builder.build_report(btc, xaut)
        self.assertIn("❌", report)

    def test_build_report_entry_zero_valid(self):
        """正常: エントリーゼロ妥当判定（出来高不足がブロック）"""
        r = _make_normal_result("BTC")
        r.breakout_buy = 2
        r.breakout_sell = 1
        r.volume_filter_ng = 3  # Breakout件数以上
        r.entry_executed = 0

        icon, reason = judge_entry_zero(r)
        self.assertEqual(icon, "✅")
        self.assertIn("出来高不足", reason)

    def test_build_report_entry_zero_combined_filters(self):
        """正常: 出来高不足+ADX不足の合計でBreakoutを全カバー → ✅妥当"""
        # BTC実際ケース: Breakout192件, 出来高51件, ADX141件 → 51+141=192
        r = _make_normal_result("BTC")
        r.breakout_buy = 192
        r.breakout_sell = 0
        r.volume_filter_ng = 51
        r.adx_filter_ng = 141
        r.entry_allowed = 0
        r.entry_executed = 0

        icon, reason = judge_entry_zero(r)
        self.assertEqual(icon, "✅")

    def test_build_report_entry_zero_suspect(self):
        """要確認: エントリー許可が出ているのに発注ゼロ"""
        r = _make_normal_result("BTC")
        r.entry_allowed = 3
        r.entry_executed = 0

        icon, reason = judge_entry_zero(r)
        self.assertEqual(icon, "❌")
        self.assertIn("ロジックバグ疑い", reason)


# ==============================================================
# TestJudgeBotHealth
# ==============================================================

class TestJudgeBotHealth(unittest.TestCase):

    def test_judge_normal(self):
        """✅ 正常"""
        r = BotAnalysisResult(symbol="BTC", is_alive=True,
                               last_log_age_seconds=30.0, status_age_seconds=30.0)
        icon, _ = judge_bot_health(r)
        self.assertEqual(icon, "✅")

    def test_judge_process_dead(self):
        """❌ プロセス停止"""
        r = BotAnalysisResult(symbol="BTC", is_alive=False)
        icon, text = judge_bot_health(r)
        self.assertEqual(icon, "❌")
        self.assertIn("停止", text)

    def test_judge_log_stale_300s(self):
        """❌ ログ・ステータス両方5分以上停止"""
        r = BotAnalysisResult(symbol="BTC", is_alive=True,
                               last_log_age_seconds=301.0, status_age_seconds=301.0)
        icon, text = judge_bot_health(r)
        self.assertEqual(icon, "❌")
        self.assertIn("ログ停止", text)

    def test_judge_status_recent_overrides_old_log(self):
        """✅ ステータスが最近ならログが古くても正常"""
        # status_age=30s(最近), log_age=3600s(1時間前) → heartbeat=30s → ✅
        r = BotAnalysisResult(symbol="BTC", is_alive=True,
                               last_log_age_seconds=3600.0, status_age_seconds=30.0)
        icon, _ = judge_bot_health(r)
        self.assertEqual(icon, "✅")

    def test_judge_log_stale_150s(self):
        """⚠️ ログ・ステータス両方2分以上遅延"""
        r = BotAnalysisResult(symbol="BTC", is_alive=True,
                               last_log_age_seconds=150.0, status_age_seconds=150.0)
        icon, text = judge_bot_health(r)
        self.assertEqual(icon, "⚠️")
        self.assertIn("遅延", text)

    def test_judge_many_errors(self):
        """⚠️ ERROR多発"""
        r = BotAnalysisResult(symbol="XAUT", is_alive=True,
                               last_log_age_seconds=30.0, status_age_seconds=30.0,
                               error_count=600)
        icon, text = judge_bot_health(r)
        self.assertEqual(icon, "⚠️")
        self.assertIn("ERROR多発", text)


# ==============================================================
# TestGmailSender
# ==============================================================

class TestGmailSender(unittest.TestCase):

    def test_send_mock_smtp(self):
        """SMTPをモックして送信成功"""
        cfg = {
            "gmail_address": "test@gmail.com",
            "gmail_app_password": "test1234",
            "notify_to": "dest@gmail.com",
            "send_hour_jst": 22,
            "subject_prefix": "[satosystem]",
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(cfg, f)
            fname = f.name

        try:
            with patch("smtplib.SMTP_SSL") as mock_smtp_cls:
                mock_smtp = MagicMock()
                mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
                mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

                sender = GmailSender(Path(fname))
                result = sender.send("テスト件名", "テスト本文")
                self.assertTrue(result)
        finally:
            os.unlink(fname)

    def test_send_invalid_config(self):
        """設定ファイルなしで FileNotFoundError"""
        with self.assertRaises(FileNotFoundError):
            GmailSender(Path("/nonexistent/.gmail"))

    def test_config_loading(self):
        """.gmail のパースが正しく動く"""
        cfg = {
            "gmail_address": "user@gmail.com",
            "gmail_app_password": "abcd efgh ijkl mnop",
            "notify_to": "notify@gmail.com",
            "send_hour_jst": 22,
            "subject_prefix": "[test]",
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(cfg, f)
            fname = f.name

        try:
            sender = GmailSender(Path(fname))
            self.assertEqual(sender.sender, "user@gmail.com")
            self.assertEqual(sender.recipient, "notify@gmail.com")
            self.assertEqual(sender.send_hour_jst, 22)
            self.assertEqual(sender.subject_prefix, "[test]")
        finally:
            os.unlink(fname)


# ==============================================================
# main
# ==============================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
