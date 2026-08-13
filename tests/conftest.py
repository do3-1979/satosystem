"""pytest共通設定。

【重要】テスト実行中に実メールを送信させない。

2026-08-13、テストスイートを流すたびに本物のGmail通知がユーザーへ
送信される事故が発生した（銘柄"A"・exchange 5.0/internal 0.0 という
テスト用の値がそのまま本文に載って届いた）。
send_alert をモックし忘れたテストが原因。個別テストでのモック忘れに
依存しないよう、ここで全テストに一律のガードをかける。
"""
import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "sends_alert: send_alert自体の実装を検証するテスト。"
        "送信関数の差し替えを行わない（SMTPはfixture側で塞いだまま）")


@pytest.fixture(autouse=True)
def _block_real_emails(request, monkeypatch):
    """全テストで送信処理を無効化する。

    autouse=True なので、テスト側が何もしなくても必ず適用される。
    send_alert の実装自体を検証したいテストは
    @pytest.mark.sends_alert を付けると差し替えを免除される
    （その場合もSMTP接続は下で塞ぐので外部へは出ない）。
    """
    def _blocked(subject, body, config_path=None):
        return False

    if not request.node.get_closest_marker("sends_alert"):
        _patch_senders(monkeypatch, _blocked)
    _block_smtp(monkeypatch)


def _patch_senders(monkeypatch, replacement):
    """送信関数そのものと、各モジュールが取り込んだ参照の両方を潰す。"""
    for target in ("cta.notify.send_alert", "cta.live_trader.send_alert",
                   "run_live.send_alert", "run_paper.send_alert"):
        monkeypatch.setattr(target, replacement, raising=False)


def _block_smtp(monkeypatch):
    """最後の砦: SMTP接続自体を失敗させる。

    send_alertの差し替えを漏らしても、これがある限り外部へは出ない。"""
    import smtplib

    def _no_smtp(*a, **kw):
        raise RuntimeError("テスト中のSMTP接続は禁止されています")

    monkeypatch.setattr(smtplib, "SMTP_SSL", _no_smtp)
    monkeypatch.setattr(smtplib, "SMTP", _no_smtp)
