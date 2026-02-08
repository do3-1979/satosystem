"""
アラート通知モジュール

本番運用における重要イベントの通知機能を提供します。
- Discord Webhook通知
- API障害、大きなDD、連続損失などの検知

Task 40g: 本番運用の耐障害性
"""

import requests
import json
from datetime import datetime
from typing import Dict, Optional
from config import Config
from logger import Logger


class Alert:
    """
    アラート通知クラス
    
    重要なイベント（API障害、大きなDD、連続損失など）を
    Discord Webhookで通知します。
    """
    
    def __init__(self):
        """
        アラート通知機能を初期化
        
        config.iniから以下のパラメータを読み込み:
        - alert_enabled: アラート有効/無効
        - alert_discord_webhook_url: Discord Webhook URL
        - alert_on_*: 各種イベントの通知有効/無効
        """
        self.logger = Logger()
        self.enabled = Config.get_alert_enabled()
        self.webhook_url = Config.get_alert_discord_webhook_url()
        
        # 通知対象イベント設定
        self.alert_on_api_failure = Config.get_alert_on_api_failure()
        self.alert_on_large_drawdown = Config.get_alert_on_large_drawdown()
        self.alert_on_consecutive_losses = Config.get_alert_on_consecutive_losses()
        
        # 通知閾値
        self.drawdown_threshold = Config.get_alert_drawdown_threshold()
        self.consecutive_loss_count = Config.get_alert_consecutive_loss_count()
        
        if self.enabled and not self.webhook_url:
            self.logger.log("⚠️  アラートが有効ですが、Discord Webhook URLが設定されていません")
            self.enabled = False
    
    def send_discord_notification(self, title: str, description: str, 
                                  color: int = 0xFF0000, fields: Optional[list] = None) -> bool:
        """
        Discord Webhookに通知を送信
        
        Args:
            title: 通知タイトル
            description: 通知本文
            color: 埋め込みカラー（デフォルト: 赤 0xFF0000）
            fields: 追加フィールド（name/value/inline のリスト）
        
        Returns:
            bool: 送信成功ならTrue
        """
        if not self.enabled:
            return False
        
        try:
            # Discord Embed形式
            embed = {
                "title": title,
                "description": description,
                "color": color,
                "timestamp": datetime.utcnow().isoformat(),
                "footer": {
                    "text": "satosystem gen2"
                }
            }
            
            if fields:
                embed["fields"] = fields
            
            payload = {
                "embeds": [embed]
            }
            
            response = requests.post(
                self.webhook_url,
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code == 204:
                self.logger.log(f"📢 Discord通知送信成功: {title}")
                return True
            else:
                self.logger.log(f"⚠️  Discord通知送信失敗: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.log(f"❌ Discord通知送信エラー: {str(e)}")
            return False
    
    def notify_api_failure(self, exchange: str, error: str, retry_count: int) -> bool:
        """
        API障害を通知
        
        Args:
            exchange: 取引所名
            error: エラーメッセージ
            retry_count: リトライ回数
        
        Returns:
            bool: 送信成功ならTrue
        """
        if not self.alert_on_api_failure:
            return False
        
        title = f"🚨 API障害検知: {exchange}"
        description = f"API通信に失敗しました（リトライ回数: {retry_count}回）"
        
        fields = [
            {"name": "取引所", "value": exchange, "inline": True},
            {"name": "リトライ回数", "value": str(retry_count), "inline": True},
            {"name": "エラー", "value": error[:100], "inline": False}
        ]
        
        return self.send_discord_notification(title, description, color=0xFF0000, fields=fields)
    
    def notify_large_drawdown(self, current_dd_pct: float, balance: float, 
                             max_balance: float) -> bool:
        """
        大きなドローダウンを通知
        
        Args:
            current_dd_pct: 現在のDD率（%）
            balance: 現在の資産
            max_balance: 最高資産
        
        Returns:
            bool: 送信成功ならTrue
        """
        if not self.alert_on_large_drawdown:
            return False
        
        if current_dd_pct < self.drawdown_threshold:
            return False
        
        title = f"⚠️  大きなドローダウン検知: {current_dd_pct:.1f}%"
        description = f"ドローダウンが閾値（{self.drawdown_threshold:.1f}%）を超えました"
        
        fields = [
            {"name": "現在の資産", "value": f"{balance:.2f} USD", "inline": True},
            {"name": "最高資産", "value": f"{max_balance:.2f} USD", "inline": True},
            {"name": "DD率", "value": f"{current_dd_pct:.1f}%", "inline": True}
        ]
        
        return self.send_discord_notification(title, description, color=0xFFA500, fields=fields)
    
    def notify_consecutive_losses(self, loss_count: int, total_loss: float) -> bool:
        """
        連続損失を通知
        
        Args:
            loss_count: 連続損失回数
            total_loss: 累積損失額
        
        Returns:
            bool: 送信成功ならTrue
        """
        if not self.alert_on_consecutive_losses:
            return False
        
        if loss_count < self.consecutive_loss_count:
            return False
        
        title = f"⚠️  連続損失検知: {loss_count}回"
        description = f"連続して損失が発生しています（閾値: {self.consecutive_loss_count}回）"
        
        fields = [
            {"name": "連続損失回数", "value": f"{loss_count}回", "inline": True},
            {"name": "累積損失", "value": f"{total_loss:.2f} USD", "inline": True}
        ]
        
        return self.send_discord_notification(title, description, color=0xFFA500, fields=fields)
    
    def notify_trade_execution(self, side: str, price: float, quantity: float, 
                              pnl: Optional[float] = None) -> bool:
        """
        取引実行を通知（オプション）
        
        Args:
            side: 'BUY' または 'SELL'
            price: 約定価格
            quantity: 数量
            pnl: 損益（イグジット時のみ）
        
        Returns:
            bool: 送信成功ならTrue
        """
        color = 0x00FF00 if side == "BUY" else 0xFF6347
        
        if pnl is not None:
            title = f"{'🟢' if pnl >= 0 else '🔴'} イグジット: {side}"
            description = f"損益: {pnl:+.2f} USD"
        else:
            title = f"{'🟢' if side == 'BUY' else '🔴'} エントリー: {side}"
            description = f"価格: {price:.2f}, 数量: {quantity:.6f}"
        
        fields = [
            {"name": "価格", "value": f"{price:.2f}", "inline": True},
            {"name": "数量", "value": f"{quantity:.6f}", "inline": True}
        ]
        
        if pnl is not None:
            fields.append({"name": "損益", "value": f"{pnl:+.2f} USD", "inline": True})
        
        return self.send_discord_notification(title, description, color=color, fields=fields)
    
    def notify_system_start(self, mode: str, balance: float) -> bool:
        """
        システム起動を通知
        
        Args:
            mode: 動作モード（'backtest', 'dummy', 'live'）
            balance: 初期資産
        
        Returns:
            bool: 送信成功ならTrue
        """
        title = "🚀 システム起動"
        description = f"satosystem gen2 が起動しました"
        
        fields = [
            {"name": "モード", "value": mode, "inline": True},
            {"name": "初期資産", "value": f"{balance:.2f} USD", "inline": True},
            {"name": "起動時刻", "value": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "inline": False}
        ]
        
        return self.send_discord_notification(title, description, color=0x00FF00, fields=fields)
    
    def notify_system_stop(self, reason: str, final_balance: float, pnl: float) -> bool:
        """
        システム停止を通知
        
        Args:
            reason: 停止理由
            final_balance: 最終資産
            pnl: 総損益
        
        Returns:
            bool: 送信成功ならTrue
        """
        title = "🛑 システム停止"
        description = f"理由: {reason}"
        
        color = 0x00FF00 if pnl >= 0 else 0xFF0000
        
        fields = [
            {"name": "最終資産", "value": f"{final_balance:.2f} USD", "inline": True},
            {"name": "総損益", "value": f"{pnl:+.2f} USD", "inline": True},
            {"name": "停止時刻", "value": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "inline": False}
        ]
        
        return self.send_discord_notification(title, description, color=color, fields=fields)


# テスト用
if __name__ == "__main__":
    alert = Alert()
    
    if alert.enabled:
        # テスト通知
        alert.notify_system_start("test", 100.0)
        print("✅ テスト通知を送信しました")
    else:
        print("⚠️  アラートが無効です（config.ini alert_enabled = 0）")
