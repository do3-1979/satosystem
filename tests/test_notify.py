"""cta/notify.py の回帰テスト。実際のSMTP送信は一切行わない（モック）。"""
import json

from cta import notify


def test_no_config_skips_silently(tmp_path):
    missing = str(tmp_path / ".gmail")
    ok = notify.send_alert("件名", "本文", config_path=missing)
    assert ok is False


def test_incomplete_config_skips_silently(tmp_path):
    path = tmp_path / ".gmail"
    path.write_text(json.dumps({"gmail_address": "a@example.com"}))  # 必須キー不足
    ok = notify.send_alert("件名", "本文", config_path=str(path))
    assert ok is False


def test_valid_config_sends_via_smtp(tmp_path, monkeypatch):
    path = tmp_path / ".gmail"
    path.write_text(json.dumps({
        "gmail_address": "sender@example.com",
        "gmail_app_password": "dummy",
        "notify_to": "dest@example.com",
    }))

    sent = {}

    class FakeSMTP:
        def __init__(self, host, port):
            sent["host"] = host
            sent["port"] = port

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def login(self, user, password):
            sent["login"] = (user, password)

        def sendmail(self, from_addr, to_addr, msg_bytes):
            sent["from"] = from_addr
            sent["to"] = to_addr
            sent["body"] = msg_bytes

    monkeypatch.setattr(notify.smtplib, "SMTP_SSL", FakeSMTP)

    ok = notify.send_alert("テスト件名", "テスト本文", config_path=str(path))
    assert ok is True
    assert sent["login"] == ("sender@example.com", "dummy")
    assert sent["to"] == "dest@example.com"
    import email
    from email.header import decode_header
    parsed = email.message_from_bytes(sent["body"])
    subject = decode_header(parsed["Subject"])[0]
    subject_text = subject[0].decode(subject[1]) if subject[1] else subject[0]
    assert "テスト件名" in subject_text
    assert "テスト本文" in parsed.get_payload(decode=True).decode("utf-8")


def test_smtp_failure_returns_false_not_raises(tmp_path, monkeypatch):
    path = tmp_path / ".gmail"
    path.write_text(json.dumps({
        "gmail_address": "sender@example.com",
        "gmail_app_password": "dummy",
        "notify_to": "dest@example.com",
    }))

    class RaisingSMTP:
        def __init__(self, host, port):
            raise ConnectionError("network down")

    monkeypatch.setattr(notify.smtplib, "SMTP_SSL", RaisingSMTP)
    ok = notify.send_alert("件名", "本文", config_path=str(path))
    assert ok is False  # 例外を投げず、Falseで通知失敗を表す
