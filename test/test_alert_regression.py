"""
test_alert_regression.py

Task 40g: Alertクラスのレグレッションテスト
- alert_enabled=0（デフォルト）でネットワーク呼び出しなし
- 各通知メソッドが正常に動作する（disabled時はFalseを返す）
- 初期化エラーが発生しない
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import unittest
from unittest.mock import patch, MagicMock
from alert import Alert


class TestAlertDisabledByDefault(unittest.TestCase):
    """alert_enabled=0時の動作テスト（デフォルト設定）"""

    def setUp(self):
        """Alertインスタンス作成（デフォルト設定ではalert_enabled=0）"""
        self.alert = Alert()

    def test_init_no_exception(self):
        """初期化時に例外が発生しないこと"""
        alert = Alert()
        self.assertIsNotNone(alert)

    def test_disabled_by_default(self):
        """デフォルトではalert_enabled=0で無効"""
        # config.iniのalert_enabled = 0（デフォルト）
        # Alert.enabled はFalseであること
        self.assertFalse(self.alert.enabled)

    def test_notify_api_failure_disabled(self):
        """disabled時にnotify_api_failureがFalseを返す（ネットワーク不使用）"""
        result = self.alert.notify_api_failure("bybit", "ConnectionError", 3)
        self.assertFalse(result)

    def test_notify_large_drawdown_disabled(self):
        """disabled時にnotify_large_drawdownがFalseを返す"""
        result = self.alert.notify_large_drawdown(35.0, 65.0, 100.0)
        self.assertFalse(result)

    def test_notify_consecutive_losses_disabled(self):
        """disabled時にnotify_consecutive_lossesがFalseを返す"""
        result = self.alert.notify_consecutive_losses(5, 20.0)
        self.assertFalse(result)

    def test_notify_trade_execution_entry_disabled(self):
        """disabled時にnotify_trade_execution（エントリー）がFalseを返す"""
        result = self.alert.notify_trade_execution("BUY", 95000.0, 0.001)
        self.assertFalse(result)

    def test_notify_trade_execution_exit_disabled(self):
        """disabled時にnotify_trade_execution（EXIT・損益あり）がFalseを返す"""
        result = self.alert.notify_trade_execution("SELL", 96000.0, 0.001, pnl=10.0)
        self.assertFalse(result)

    def test_notify_system_start_disabled(self):
        """disabled時にnotify_system_startがFalseを返す"""
        result = self.alert.notify_system_start("LIVE", 100.0)
        self.assertFalse(result)

    def test_notify_system_stop_disabled(self):
        """disabled時にnotify_system_stopがFalseを返す"""
        result = self.alert.notify_system_stop("END", 110.0, 10.0)
        self.assertFalse(result)


class TestAlertThresholds(unittest.TestCase):
    """アラート閾値の設定テスト"""

    def setUp(self):
        self.alert = Alert()

    def test_drawdown_threshold_is_numeric(self):
        """drawdown_thresholdが数値（デフォルト: 40.0）"""
        self.assertIsInstance(self.alert.drawdown_threshold, float)
        self.assertGreater(self.alert.drawdown_threshold, 0)

    def test_consecutive_loss_count_is_int(self):
        """consecutive_loss_countが整数（デフォルト: 3）"""
        self.assertIsInstance(self.alert.consecutive_loss_count, int)
        self.assertGreater(self.alert.consecutive_loss_count, 0)


class TestAlertEnabledWithMock(unittest.TestCase):
    """alert_enabled=1時の動作（Webhookをモック）"""

    def test_send_discord_when_enabled(self):
        """enabled=True時にWebhookが呼び出されること"""
        with patch('alert.Config') as MockConfig:
            MockConfig.get_alert_enabled.return_value = 1
            MockConfig.get_alert_discord_webhook_url.return_value = "https://discord.com/api/webhooks/dummy"
            MockConfig.get_alert_on_api_failure.return_value = True
            MockConfig.get_alert_on_large_drawdown.return_value = True
            MockConfig.get_alert_on_consecutive_losses.return_value = True
            MockConfig.get_alert_drawdown_threshold.return_value = 40.0
            MockConfig.get_alert_consecutive_loss_count.return_value = 3
            MockConfig.get_account_balance.return_value = 100.0

            alert = Alert()
            self.assertTrue(alert.enabled)

            # requestsをモックしてHTTPを呼ばない
            with patch('requests.post') as mock_post:
                mock_response = MagicMock()
                mock_response.status_code = 204  # Discord Webhook成功コード
                mock_post.return_value = mock_response

                result = alert.notify_api_failure("bybit", "TimeoutError", 2)
                self.assertTrue(result)
                mock_post.assert_called_once()


if __name__ == '__main__':
    unittest.main()
