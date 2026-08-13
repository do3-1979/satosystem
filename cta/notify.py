"""異常時のメール通知。

gen2のbot_monitor.pyと同じGmail SMTP方式を踏襲する。認証情報は
リポジトリルートの `.gmail`（JSON, gitignore済み）から読む:
  {"gmail_address": "...", "gmail_app_password": "...", "notify_to": "..."}

設定ファイルが無い/読めない場合は静かに送信をスキップする（通知の欠落で
本体の処理を止めないため）。実際に送信できたかは戻り値で分かる。
"""
import json
import os
import smtplib
from email.mime.text import MIMEText

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           ".gmail")


def _load_config(path=None):
    path = path or CONFIG_PATH
    if not os.path.exists(path):
        return None
    with open(path) as f:
        cfg = json.load(f)
    required = ["gmail_address", "gmail_app_password", "notify_to"]
    if not all(k in cfg for k in required):
        return None
    return cfg


def send_alert(subject, body, config_path=None):
    """アラートメールを送信する。成功したらTrue、設定不備/送信失敗ならFalse。

    例外は投げない（通知失敗が本体のcron処理を止めてはならないため）。

    pytest実行中は常に送信しない。2026-08-13にテストスイートが
    実メールを送り続ける事故があったため、tests/conftest.py のモックに
    加えてここでも二重に防ぐ（モック漏れがあっても外部送信されない）。
    """
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    cfg = _load_config(config_path)
    if cfg is None:
        return False
    msg = MIMEText(body)
    msg["Subject"] = f"[CTAボット] {subject}"
    msg["From"] = cfg["gmail_address"]
    msg["To"] = cfg["notify_to"]
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(cfg["gmail_address"], cfg["gmail_app_password"])
            smtp.sendmail(cfg["gmail_address"], cfg["notify_to"], msg.as_bytes())
        return True
    except Exception:
        return False
