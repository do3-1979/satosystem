"""東証ETF価格修復の回帰テスト。

2026-08-15、yfinanceの日本銘柄データに分割調整漏れと単日桁化けがあり、
「1日で-99%」という実在しない値動きを含んでいた。これを掴んだまま検証すると
平均相関が0.143（真値0.330）と出て、結論が逆転する。
ここで固定するのは「壊れた入力を壊れたまま通さない」という一点。
"""
import numpy as np
import pandas as pd
import pytest

from cta import jp_repair


def mkseries(vals, start="2020-01-01"):
    idx = pd.bdate_range(start, periods=len(vals))
    return pd.Series(np.asarray(vals, float), index=idx)


def test_unrecorded_split_is_rescaled_to_latest_level():
    """分割がsplitsに無くても、段差の前を最新スケールへ揃える。

    発注数量は最新スケールで計算されるため、ここを基準にしないと桁が狂う。
    """
    s = mkseries([1200, 1210, 1190, 1205,   # 分割前
                  120, 121, 119, 120.5])    # 1:10分割後（Yahooは未調整）
    fixed, notes = jp_repair.repair_close_series(s)
    assert len(fixed) == len(s)                    # 行は落とさない
    assert fixed.iloc[-1] == pytest.approx(120.5)  # 最新はそのまま
    assert fixed.iloc[0] == pytest.approx(120.0)   # 過去が1/10へ
    assert len(jp_repair.residual_anomalies(fixed)) == 0
    assert any("分割調整" in n for n in notes)


def test_single_day_glitch_is_removed():
    """1日だけ桁が化けて翌日戻る異常値は、その日を除去する。"""
    s = mkseries([100, 101, 9900, 102, 103])
    fixed, notes = jp_repair.repair_close_series(s)
    assert len(fixed) == 4
    assert 9900.0 not in set(fixed.values)
    assert len(jp_repair.residual_anomalies(fixed)) == 0
    assert any("単日スパイク" in n for n in notes)


def test_real_crash_is_preserved():
    """実在する急落(原油2020など)を分割と誤認して消さないこと。

    -30%は異常判定の閾値(25%)を超えるが、2.5倍未満なので修復対象外。
    """
    s = mkseries([100, 98, 68, 66, 67])
    fixed, _ = jp_repair.repair_close_series(s)
    assert len(fixed) == len(s)
    assert fixed.iloc[2] == pytest.approx(68.0)     # 値を書き換えない
    assert len(jp_repair.residual_anomalies(fixed)) == 1


def test_unclassified_jump_is_left_alone_and_reported():
    """分割比に当てはまらない段差は、勝手に直さず報告だけする。"""
    s = mkseries([100, 101, 700, 705, 710])         # 約7倍（候補比率から外れる）
    fixed, notes = jp_repair.repair_close_series(s)
    assert fixed.iloc[0] == pytest.approx(100.0)    # 書き換えていない
    assert any("未分類" in n for n in notes)


def test_clean_series_is_untouched():
    s = mkseries([100, 101, 99, 102, 103])
    fixed, notes = jp_repair.repair_close_series(s)
    pd.testing.assert_series_equal(fixed, s)
    assert notes == []


def test_is_jp_symbol():
    assert jp_repair.is_jp_symbol("1306.T")
    assert jp_repair.is_jp_symbol("1540.t")
    assert not jp_repair.is_jp_symbol("SPY")
    assert not jp_repair.is_jp_symbol("IAU")


def test_fetch_and_cache_repairs_jp_ohlc(tmp_path, monkeypatch):
    """取り込み経路で修復が必ず適用され、OHLC全体が同じ係数で揃うこと。

    終値だけ直してOpenを放置すると、約定価格(次足始値)が10倍ずれる。
    """
    from cta import etf_data

    idx = pd.bdate_range("2020-01-01", periods=6)
    raw = pd.DataFrame({
        "Open":  [1200, 1210, 1190, 120, 121, 119],
        "High":  [1220, 1230, 1200, 122, 123, 121],
        "Low":   [1190, 1200, 1180, 119, 120, 118],
        "Close": [1210, 1200, 1195, 120, 122, 119],
        "Volume": [1000] * 6,
    }, index=idx)

    class FakeYF:
        @staticmethod
        def download(sym, **kw):
            return raw.copy()

    monkeypatch.setitem(__import__("sys").modules, "yfinance", FakeYF)
    db = str(tmp_path / "jp.db")
    log = {}
    etf_data.fetch_and_cache(db, ["1306.T"], now_utc=None, repair_log=log)

    _, opens, closes = etf_data.load_universe(db, ["1306.T"])
    c = closes["1306.T"].dropna()
    o = opens["1306.T"].dropna()
    # 分割前が1/10になり、日次変動が正常範囲に収まる
    assert c.iloc[0] == pytest.approx(121.0)
    assert o.iloc[0] == pytest.approx(120.0)
    assert (c.pct_change().dropna().abs() < 0.25).all()
    # OpenとCloseの比が元データと保たれている（同じ係数で直っている）
    assert (o.iloc[0] / c.iloc[0]) == pytest.approx(1200 / 1210)
    assert log["1306.T"]


# --- 市場ごとの確定時刻 ------------------------------------------------

def test_jp_bar_settles_earlier_than_us_bar():
    """東証バーは18:00 JST(09:00 UTC)で確定すること。

    米国用の23:00 UTCを東証に適用すると、判定できるのが翌日08:00 JSTになり
    寄成注文（寄付板の受付は08:00頃から）にほとんど間に合わない。
    """
    import datetime as dt
    from cta import etf_data

    # 2026-08-17 07:00 UTC = 16:00 JST（東証の引け後1時間・米国はまだ場中）
    now = dt.datetime(2026, 8, 17, 7, 0, tzinfo=dt.timezone.utc)
    assert etf_data.is_settled("2026-08-17", now, symbol="1308.T") is False
    assert etf_data.is_settled("2026-08-17", now, symbol="ITOT") is False

    # 2026-08-17 09:00 UTC = 18:00 JST（東証は確定・米国はまだ場中）
    now = dt.datetime(2026, 8, 17, 9, 0, tzinfo=dt.timezone.utc)
    assert etf_data.is_settled("2026-08-17", now, symbol="1308.T") is True
    assert etf_data.is_settled("2026-08-17", now, symbol="ITOT") is False

    # 2026-08-17 23:00 UTC = 米国も確定
    now = dt.datetime(2026, 8, 17, 23, 0, tzinfo=dt.timezone.utc)
    assert etf_data.is_settled("2026-08-17", now, symbol="ITOT") is True


def test_settled_hour_defaults_to_us_when_symbol_unknown():
    """symbol未指定は従来どおり米国基準（既存の呼び出しを壊さない）。"""
    from cta import etf_data
    assert etf_data.settled_hour_utc(None) == etf_data.SETTLED_HOUR_UTC
    assert etf_data.settled_hour_utc("SPY") == etf_data.SETTLED_HOUR_UTC
    assert etf_data.settled_hour_utc("1308.T") == etf_data.SETTLED_HOUR_UTC_JP
