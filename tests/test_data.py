"""cta/data.py の回帰テスト。

2026-07-18判明の重大バグの再発防止: 取引所のfetch_ohlcvは末尾に「形成中の
未確定バー」を含めて返すことがある。これをそのままキャッシュに書き込むと、
INSERT ... WHERE NOT EXISTS のガードにより、バーが実際に確定した後も
二度と正しい終値で上書きされず、誤った値が永久に固定されてしまう。
paper trading開始(2026-07-02)以降、全銘柄のsignal_priceが実質「バー開始
5分後のスナップショット」になっており、本来の終値ではなかったことが発覚した。
"""
import sqlite3

import pytest

from cta import data as data_mod


def _make_db(tmp_path):
    db = str(tmp_path / "cache.db")
    con = sqlite3.connect(db)
    con.execute("""CREATE TABLE candles (
        id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, start_epoch INT,
        end_epoch INT, time_frame INT, close_time INT, close_time_dt TEXT,
        open_price REAL, high_price REAL, low_price REAL, close_price REAL,
        volume REAL, created_at TEXT)""")
    con.commit()
    con.close()
    return db


class FakeExchangeOneBatch:
    """1回のfetch_ohlcv呼び出しで [確定バー, 確定バー, 形成中バー] を返すフェイク。

    実際のBybit等の挙動を模す: 最後の要素は close_time が未来(now以降)になる。
    """

    def __init__(self, now_ms, step_ms):
        self.now_ms = now_ms
        self.step_ms = step_ms
        self.calls = 0

    def fetch_ohlcv(self, symbol, timeframe, since, limit):
        self.calls += 1
        if self.calls > 1:
            return []  # 2回目以降は「もう新しいデータは無い」を模す
        # 確定バー2本 + 形成中(未確定)バー1本
        closed1_open = self.now_ms - 2 * self.step_ms
        closed2_open = self.now_ms - 1 * self.step_ms
        forming_open = self.now_ms  # このバーのclose_timeはnow+step > now → 未確定
        return [
            [closed1_open, 100.0, 101.0, 99.0, 100.5, 10.0],
            [closed2_open, 100.5, 102.0, 100.0, 101.5, 12.0],
            [forming_open, 101.5, 101.6, 101.4, 101.55, 0.5],
        ]


def test_forming_incomplete_bar_is_not_cached(tmp_path, monkeypatch):
    """形成中バー（close_timeが未来）はキャッシュに書き込まれないこと。"""
    db = _make_db(tmp_path)
    step_ms = 240 * 60 * 1000
    now_ms = 1_800_000_000_000  # 適当な基準時刻(ms)
    fake = FakeExchangeOneBatch(now_ms, step_ms)

    import ccxt
    monkeypatch.setattr(ccxt, "bybit", lambda *a, **kw: fake)
    monkeypatch.setattr(data_mod.time, "time", lambda: fake.now_ms / 1000)

    since_epoch = (now_ms - 2 * step_ms) / 1000 - 1
    until_epoch = now_ms / 1000 + 1
    inserted = data_mod.fetch_and_cache(db, "BTC/USDT:USDT", 240,
                                        since_epoch, until_epoch)

    con = sqlite3.connect(db)
    rows = con.execute(
        "SELECT close_time, close_price FROM candles ORDER BY close_time").fetchall()
    con.close()

    assert inserted == 2  # 確定した2本のみ
    assert len(rows) == 2
    # 形成中バー(open=now_ms, close_price=101.55)は含まれていない
    assert all(price != 101.55 for _, price in rows)


def test_closed_bars_are_cached_correctly(tmp_path, monkeypatch):
    db = _make_db(tmp_path)
    step_ms = 240 * 60 * 1000
    now_ms = 1_800_000_000_000
    fake = FakeExchangeOneBatch(now_ms, step_ms)

    import ccxt
    monkeypatch.setattr(ccxt, "bybit", lambda *a, **kw: fake)
    monkeypatch.setattr(data_mod.time, "time", lambda: fake.now_ms / 1000)

    since_epoch = (now_ms - 2 * step_ms) / 1000 - 1
    until_epoch = now_ms / 1000 + 1
    data_mod.fetch_and_cache(db, "BTC/USDT:USDT", 240, since_epoch, until_epoch)

    con = sqlite3.connect(db)
    rows = con.execute(
        "SELECT close_time, close_price FROM candles ORDER BY close_time").fetchall()
    con.close()
    closes = [price for _, price in rows]
    assert closes == pytest.approx([100.5, 101.5])


def test_rerun_after_bar_closes_fills_in_the_now_completed_bar(tmp_path, monkeypatch):
    """1回目の実行で「形成中」だったバーが、次回実行時(時間が進んで確定後)には
    正しくキャッシュされること（cronが4時間ごとに回る実運用を模す）。"""
    db = _make_db(tmp_path)
    step_ms = 240 * 60 * 1000
    now_ms = 1_800_000_000_000
    fake = FakeExchangeOneBatch(now_ms, step_ms)

    import ccxt
    monkeypatch.setattr(ccxt, "bybit", lambda *a, **kw: fake)
    monkeypatch.setattr(data_mod.time, "time", lambda: fake.now_ms / 1000)

    since_epoch = (now_ms - 2 * step_ms) / 1000 - 1
    data_mod.fetch_and_cache(db, "BTC/USDT:USDT", 240, since_epoch,
                             now_ms / 1000 + 1)

    # 時間が進み、さっき「形成中」だったバーが確定した状況を模す
    fake.calls = 0
    fake.now_ms = now_ms + step_ms

    def fetch_ohlcv_2(symbol, timeframe, since, limit):
        fake.calls += 1
        if fake.calls > 1:
            return []
        return [[now_ms, 101.5, 101.6, 101.0, 101.55, 5.0]]  # 今度は確定値として返る

    fake.fetch_ohlcv = fetch_ohlcv_2
    data_mod.fetch_and_cache(db, "BTC/USDT:USDT", 240, since_epoch,
                             fake.now_ms / 1000 + 1)

    con = sqlite3.connect(db)
    rows = con.execute(
        "SELECT close_time, close_price FROM candles ORDER BY close_time").fetchall()
    con.close()
    closes = [price for _, price in rows]
    assert 101.55 in closes  # 確定後は正しく取り込まれている
    assert len(rows) == 3
