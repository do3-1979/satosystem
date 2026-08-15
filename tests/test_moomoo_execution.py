"""moomoo実発注層の回帰テスト。OpenDには接続せず、SDKをフェイクで置き換える。

最重要:
  - moomooは**Client Order IDに非対応**で取引所が重複を弾いてくれない。
    remarkによる自前の冪等性が確実に働くことをコードで保証する。
  - 発注レート制限(30秒15回)を超えないこと。19銘柄を一度に出すと超えるため
    実運用で必ず問題になる。
"""
import time

import pytest

from cta import execution as ex
from cta import moomoo_execution as mm
from cta.moomoo_execution import MoomooExecutor, MoomooOrderError, order_tag


class FakeCtx:
    """moomoo SDKの OpenSecTradeContext を模したフェイク。"""

    def __init__(self):
        self.orders = []          # 発注済み(remark付き)
        self.place_calls = 0
        self.raise_on_place = None
        self.place_ret = 0
        self.positions = []
        self.acc = [{"total_assets": "450.0", "power": "450.0", "cash": "450.0"}]
        self.order_query_ret = 0
        self.unlocked = False

    def unlock_trade(self, password=None, **kw):
        self.unlocked = True
        return 0, "ok"

    def order_list_query(self, **kw):
        return self.order_query_ret, list(self.orders)

    def position_list_query(self, **kw):
        return 0, list(self.positions)

    def accinfo_query(self, **kw):
        return 0, list(self.acc)

    def place_order(self, price, qty, code, trd_side, remark=None, **kw):
        self.place_calls += 1
        if self.raise_on_place is not None:
            exc = self.raise_on_place
            self.raise_on_place = None
            raise exc
        if self.place_ret != 0:
            return self.place_ret, "rejected"
        row = {"code": code, "qty": qty, "dealt_qty": qty,
               "dealt_avg_price": price, "remark": remark,
               "trd_side": trd_side}
        self.orders.append(row)
        return 0, [row]


def _mk(ctx=None, **kw):
    return MoomooExecutor(ctx or FakeCtx(), acc_id=1,
                          unlock_password="dummy", **kw)


BAR = 1786752000
# remarkの日付は実装と同じ方法で導出する（ハードコードするとズレる）
import datetime as _dt
BAR_DATE = _dt.datetime.utcfromtimestamp(BAR).strftime("%Y%m%d")


# --- 冪等性（moomooは取引所側で弾いてくれない） ------------------------

def test_order_tag_is_deterministic():
    a = order_tag("SPY", "20260814")
    b = order_tag("SPY", "20260814")
    c = order_tag("SPY", "20260815")   # 日が違えば別ID
    d = order_tag("IAU", "20260814")   # 銘柄が違えば別ID
    assert a == b
    assert a != c and a != d


def test_existing_order_is_not_resent():
    """同じremarkの注文が既にあれば再発注しない。"""
    ctx = FakeCtx()
    tag = order_tag("SPY", BAR_DATE)
    ctx.orders.append({"code": "US.SPY", "qty": 3, "dealt_qty": 3,
                       "dealt_avg_price": 170.0, "remark": tag})
    e = _mk(ctx)
    fill = e.place_order(ex.Order("SPY", 3, signal_price=170.0), bar_epoch=BAR)
    assert ctx.place_calls == 0          # 一度も発注していない
    assert fill.qty == pytest.approx(3.0)


def test_timeout_then_already_placed_is_not_duplicated():
    """通信断でも実は発注済みだった場合、再送してはならない。"""
    ctx = FakeCtx()
    tag = order_tag("SPY", BAR_DATE)

    def place_then_fail(price, qty, code, trd_side, remark=None, **kw):
        ctx.place_calls += 1
        # 取引所には届いたが応答が返らなかった状況
        ctx.orders.append({"code": code, "qty": qty, "dealt_qty": qty,
                           "dealt_avg_price": price, "remark": remark})
        raise ConnectionError("timeout")

    ctx.place_order = place_then_fail
    e = _mk(ctx)
    fill = e.place_order(ex.Order("SPY", 3, signal_price=170.0), bar_epoch=BAR)
    assert ctx.place_calls == 1          # 再送していない
    assert fill.qty == pytest.approx(3.0)


def test_cannot_verify_duplicates_then_no_order():
    """注文一覧を照会できないときは発注しない（重複を防げないため）。"""
    ctx = FakeCtx()
    ctx.order_query_ret = -1
    e = _mk(ctx)
    with pytest.raises(MoomooOrderError):
        e.place_order(ex.Order("SPY", 3, signal_price=170.0), bar_epoch=BAR)
    assert ctx.place_calls == 0


# --- レート制限（19銘柄を一度に出すと必ず超える） ----------------------

def test_rate_limit_waits_after_15_orders(monkeypatch):
    """30秒15回の上限を超えないこと。16件目で待機が入る。"""
    ctx = FakeCtx()
    e = _mk(ctx)
    slept = []
    monkeypatch.setattr(mm.time, "sleep", lambda s: slept.append(s))
    fake_now = [1000.0]
    monkeypatch.setattr(mm.time, "time", lambda: fake_now[0])

    for _ in range(mm.MAX_ORDERS_PER_WINDOW):
        e._respect_rate_limit()
    assert not [s for s in slept if s > 1.0], "15件までは長い待機をしない"

    e._respect_rate_limit()              # 16件目
    assert any(s > 1.0 for s in slept), "上限超過時に待機していない"


def test_min_interval_between_orders(monkeypatch):
    ctx = FakeCtx()
    e = _mk(ctx)
    slept = []
    monkeypatch.setattr(mm.time, "sleep", lambda s: slept.append(s))
    fake_now = [1000.0]
    monkeypatch.setattr(mm.time, "time", lambda: fake_now[0])
    e._respect_rate_limit()
    e._respect_rate_limit()              # 間隔ゼロで連続
    assert any(0 < s <= mm.MIN_ORDER_INTERVAL_SEC for s in slept)


# --- 端数株の拒否（moomooはAPI経由の端数株に非対応） -------------------

def test_fractional_share_is_rejected():
    ctx = FakeCtx()
    e = _mk(ctx)
    with pytest.raises(MoomooOrderError):
        e.place_order(ex.Order("SPY", 0.5, signal_price=170.0), bar_epoch=BAR)
    assert ctx.place_calls == 0


# --- 発注・照会 --------------------------------------------------------

def test_place_order_success_uses_remark_and_us_code():
    ctx = FakeCtx()
    e = _mk(ctx)
    fill = e.place_order(ex.Order("IAU", 4, signal_price=83.0), bar_epoch=BAR)
    assert ctx.place_calls == 1
    row = ctx.orders[0]
    assert row["code"] == "US.IAU"                    # moomooの銘柄コード形式
    assert row["remark"] == order_tag("IAU", BAR_DATE)
    assert row["trd_side"] == "BUY"
    assert fill.qty == pytest.approx(4.0)


def test_sell_side_is_mapped():
    ctx = FakeCtx()
    e = _mk(ctx)
    e.place_order(ex.Order("IAU", -4, signal_price=83.0), bar_epoch=BAR)
    assert ctx.orders[0]["trd_side"] == "SELL"


def test_unlock_is_called_before_first_order():
    ctx = FakeCtx()
    e = _mk(ctx)
    assert ctx.unlocked is False
    e.place_order(ex.Order("SPY", 1, signal_price=170.0), bar_epoch=BAR)
    assert ctx.unlocked is True


def test_reconcile_positions_detects_mismatch():
    ctx = FakeCtx()
    ctx.positions = [{"code": "US.SPY", "qty": "3"},
                     {"code": "US.IAU", "qty": "5"}]
    e = _mk(ctx)
    r = e.reconcile_positions(["SPY", "IAU"], {"SPY": 3.0, "IAU": 0.0})
    assert "IAU" in r["mismatches"]
    assert "SPY" not in r["mismatches"]
    assert r["exchange_positions"]["IAU"] == pytest.approx(5.0)


def test_equity_and_available():
    e = _mk(FakeCtx())
    assert e.fetch_equity_usd() == pytest.approx(450.0)
    assert e.fetch_available_usd() == pytest.approx(450.0)
