"""
リスク・オーバーレイ（キルスイッチ）モジュール

Task 40c: 資産保護のための自動取引停止機能
- 最大ドローダウン超過 → 永続的取引停止
- 日次損失上限超過   → 当日取引停止（翌日自動再開可）
- 連続損失超過       → 取引停止（翌日自動再開可）

初期資本100USD前提で設計。enabled=0でバイパス（既存動作に影響なし）。
"""

from datetime import date
from config import Config


class RiskOverlay:
    """
    リスク・オーバーレイ（キルスイッチ）クラス

    各取引サイクルの前に check_can_trade() を呼び出して
    取引可否を判断します。トレード確定後は notify_trade_result() で
    損益を報告してください。
    """

    def __init__(self):
        """RiskOverlayを初期化"""
        self.enabled = Config.get_risk_overlay_enabled() == 1
        self.max_dd_pct = Config.get_risk_overlay_max_drawdown_pct()
        self.daily_loss_limit_pct = Config.get_risk_overlay_daily_loss_limit_pct()
        self.consecutive_limit = Config.get_risk_overlay_consecutive_losses_limit()
        self.auto_resume = Config.get_risk_overlay_auto_resume_next_day() == 1
        self.initial_balance = Config.get_account_balance()

        # H-033b: DD停止後の自動再開
        self.dd_resume_bars = Config.get_risk_overlay_dd_resume_bars()
        self.time_frame = Config.get_time_frame()  # 分単位
        self._dd_stop_epoch = None  # DD停止時のepoch（秒）

        # 日次損失トラッキング
        self._daily_loss = 0.0
        self._daily_date = date.today()

        # 連続損失カウント
        self._consecutive_losses = 0

        # 停止状態管理
        self._dd_stop = False          # 最大DD超過
        self._daily_stop = False       # 日次損失超過（翌日リセット可）
        self._consecutive_stop = False  # 連続損失超過（翌日リセット可）

    def _reset_daily_if_needed(self):
        """日またぎ時に日次停止・連続停止をリセット"""
        today = date.today()
        if today != self._daily_date:
            self._daily_date = today
            self._daily_loss = 0.0
            if self.auto_resume:
                self._daily_stop = False
                self._consecutive_stop = False

    def check_can_trade(self, portfolio=None, current_epoch: int = None) -> tuple:
        """
        取引可否をチェックします。

        Args:
            portfolio: Portfolioオブジェクト（DD率取得用、Noneで無効）
            current_epoch: 現在時刻（epoch秒）。バックテスト時に指定する。

        Returns:
            (bool, str): (取引可能か, 停止理由またはOK)
        """
        if not self.enabled:
            return True, "OK"

        self._reset_daily_if_needed()

        # 最大DD超過チェック
        if portfolio is not None:
            current_dd = portfolio.get_drawdown_rate()
            if current_dd >= self.max_dd_pct:
                if not self._dd_stop:
                    self._dd_stop = True
                    self._dd_stop_epoch = current_epoch  # 停止時刻を記録

        if self._dd_stop:
            # H-033b: dd_resume_bars > 0 かつ経過バー数が閾値超なら自動再開
            if self.dd_resume_bars > 0 and self._dd_stop_epoch is not None and current_epoch is not None:
                elapsed_secs = current_epoch - self._dd_stop_epoch
                elapsed_bars = elapsed_secs / (self.time_frame * 60)
                if elapsed_bars >= self.dd_resume_bars:
                    self._dd_stop = False
                    self._dd_stop_epoch = None
                    return True, "OK"
            current_dd_str = f"{portfolio.get_drawdown_rate():.1f}%" if portfolio else "不明"
            return False, f"DD_STOP: 最大DD {self.max_dd_pct:.1f}% 超過（現在 {current_dd_str}）"

        # 日次損失上限チェック
        if self._daily_stop:
            return False, f"DAILY_STOP: 日次損失上限 {self.daily_loss_limit_pct:.1f}% 超過"

        # 連続損失チェック
        if self._consecutive_stop:
            return False, f"CONSEC_STOP: 連続損失 {self.consecutive_limit} 回超過"

        return True, "OK"

    def notify_trade_result(self, pnl: float):
        """
        トレード確定後に損益を報告します。
        日次損失と連続損失カウントを更新します。

        Args:
            pnl: 確定損益（USD）
        """
        if not self.enabled:
            return

        if pnl < 0:
            # 日次損失更新
            self._daily_loss += abs(pnl)
            daily_loss_pct = (self._daily_loss / self.initial_balance) * 100
            if daily_loss_pct >= self.daily_loss_limit_pct:
                self._daily_stop = True

            # 連続損失カウント
            self._consecutive_losses += 1
            if self._consecutive_losses >= self.consecutive_limit:
                self._consecutive_stop = True
        else:
            # 勝ちトレードで連続損失リセット
            self._consecutive_losses = 0

    def get_status(self) -> dict:
        """
        現在の状態を返します（ログ・デバッグ用）

        Returns:
            dict: 状態辞書
        """
        return {
            "enabled": self.enabled,
            "dd_stop": self._dd_stop,
            "dd_stop_epoch": self._dd_stop_epoch,
            "daily_stop": self._daily_stop,
            "consecutive_stop": self._consecutive_stop,
            "daily_loss_usd": round(self._daily_loss, 2),
            "daily_loss_pct": round((self._daily_loss / self.initial_balance) * 100, 2) if self.initial_balance > 0 else 0,
            "consecutive_losses": self._consecutive_losses,
            "daily_date": str(self._daily_date),
        }
