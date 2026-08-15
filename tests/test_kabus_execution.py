"""kabuステーション実発注層の回帰テスト。実APIには接続せずopenerを差し替える。

最重要:
  - kabuステーションAPIは**Client Order IDに非対応**で重複を弾いてくれない。
    「発注前に当日の注文を照会」という自前の冪等性が確実に働くこと。
  - 売買単位(TradingUnit)がconfigとずれたまま発注しないこと。
    東証ETFは1口/10口が銘柄ごとに異なり、ずれると数量が桁違いになる。
  - 執行条件が寄成(13)であること。バックテストの「次足始値で約定」と
    一致させるための要。成行(10)に変わると検証結果と食い違う。
"""
import urllib.error

import pytest

from cta import execution as ex
from cta.kabus_execution import KabusExecutor, KabusOrderError


class FakeApi:
    """kabuステーションAPIのフェイク。呼ばれた内容を記録する。"""

    def __init__(self):
        self.calls = []          # (method, path, body)
        self.orders = []         # GET /orders が返す行
        self.positions = []
        self.cash = 300000.0
        self.trading_unit = 10
        self.send_result = 0
        self.token_calls = 0
        self.raise_on_send = None
        self.raise_401_once = False

    def __call__(self, method, url, body, headers):
        path = url.split("/kabusapi", 1)[1]
        self.calls.append((method, path, body))
        if path == "/token":
            self.token_calls += 1
            return {"ResultCode": 0, "Token": f"tok{self.token_calls}"}
        if self.raise_401_once and "X-API-KEY" in headers:
            self.raise_401_once = False
            raise urllib.error.HTTPError(url, 401, "unauth", {}, None)
        if path.startswith("/symbol/"):
            return {"Symbol": path.split("/")[2], "TradingUnit": self.trading_unit}
        if path.startswith("/orders"):
            return list(self.orders)
        if path.startswith("/positions"):
            return list(self.positions)
        if path == "/wallet/cash":
            return {"StockAccountWallet": self.cash}
        if path.startswith("/board/"):
            return {"CurrentPrice": 440.0}
        if path == "/sendorder":
            if self.raise_on_send is not None:
                e, self.raise_on_send = self.raise_on_send, None
                self.orders.append({"ID": "X1", "State": 1, "CumQty": 0,
                                    "Symbol": body["Symbol"]})
                raise e
            if self.send_result != 0:
                return {"Result": self.send_result}
            self.orders.append({"ID": "OID1", "State": 1, "CumQty": 0,
                                "Symbol": body["Symbol"]})
            return {"Result": 0, "OrderId": "OID1"}
        raise AssertionError(f"未対応のパス {path}")


def mk(api=None):
    api = api or FakeApi()
    e = KabusExecutor("apipass", "orderpass", opener=api)
    return e, api


BAR = 1786752000


def sends(api):
    return [c for c in api.calls if c[1] == "/sendorder"]


# --- 冪等性 ------------------------------------------------------------

def test_existing_order_is_not_resent():
    """当日すでに同じ銘柄の注文があれば再発注しない。"""
    e, api = mk()
    api.orders.append({"ID": "OID0", "State": 1, "CumQty": 0, "Symbol": "1306"})
    e.place_order(ex.Order("1306.T", 10, signal_price=440.0), BAR, lot_size=10)
    assert sends(api) == []


def test_timeout_then_already_placed_is_not_duplicated():
    """通信断でも実は届いていた場合、再送してはならない。"""
    e, api = mk()
    api.raise_on_send = OSError("timeout")
    fill = e.place_order(ex.Order("1306.T", 10, signal_price=440.0), BAR,
                         lot_size=10)
    assert len(sends(api)) == 1          # 1回だけ
    assert fill.qty == pytest.approx(10.0)


def test_cancelled_order_does_not_block_new_one():
    """取消・失効で約定ゼロの注文は「無かった」扱いにして再発注できること。"""
    e, api = mk()
    api.orders.append({"ID": "OLD", "State": 5, "CumQty": 0, "Symbol": "1306"})
    e.place_order(ex.Order("1306.T", 10, signal_price=440.0), BAR, lot_size=10)
    assert len(sends(api)) == 1


# --- 売買単位 ----------------------------------------------------------

def test_quantity_must_be_multiple_of_lot():
    e, api = mk()
    with pytest.raises(KabusOrderError):
        e.place_order(ex.Order("1306.T", 15, signal_price=440.0), BAR, lot_size=10)
    assert sends(api) == []


def test_below_one_lot_is_rejected():
    e, api = mk()
    with pytest.raises(KabusOrderError):
        e.place_order(ex.Order("1306.T", 5, signal_price=440.0), BAR, lot_size=10)
    assert sends(api) == []


def test_verify_lot_sizes_detects_config_mismatch():
    """configの売買単位が取引所の実値と違えば検出すること。"""
    from cta.config import Config
    e, api = mk()
    api.trading_unit = 10
    cfg = Config(db_path="", timeframe_min=1440, funding_pkl="",
                 symbols=["1306.T", "1540.T"], horizons_days=[(10, 40)],
                 vol_window_days=30, target_vol=0.15, max_gross=3.0,
                 rebalance_days=21, no_trade_band_pct=0.05, dd_soft=0.35,
                 dd_hard=0.40, fee_rate=0.0, slip_rate=0.0,
                 min_notional_usd=1.0, lot_sizes={"1306.T": 10, "1540.T": 1})
    bad = e.verify_lot_sizes(cfg)
    assert "1540.T" in bad and bad["1540.T"] == {"config": 1, "exchange": 10}
    assert "1306.T" not in bad


# --- 発注内容 ----------------------------------------------------------

def test_buy_order_body_is_spot_open_market():
    """現物買いが寄成で、受渡区分・資産区分が現物買いの値になること。"""
    e, api = mk()
    e.place_order(ex.Order("1306.T", 20, signal_price=440.0), BAR, lot_size=10)
    b = sends(api)[0][2]
    assert b["Symbol"] == "1306"          # '.T'を落とす
    assert b["Exchange"] == 1 and b["SecurityType"] == 1
    assert b["Side"] == "2"               # 買い
    assert b["CashMargin"] == 1           # 現物
    assert b["DelivType"] == 2            # お預り金
    assert b["FundType"] == "02"          # 保護
    assert b["FrontOrderType"] == 13      # ★寄成（次足始値約定と一致させる）
    assert b["Price"] == 0
    assert b["Qty"] == 20


def test_sell_order_uses_sell_side_deliv_and_fund():
    e, api = mk()
    e.place_order(ex.Order("1306.T", -10, signal_price=440.0), BAR, lot_size=10)
    b = sends(api)[0][2]
    assert b["Side"] == "1"               # 売り
    assert b["DelivType"] == 0            # 指定なし
    assert b["FundType"] == "  "          # 半角スペース2つ
    assert b["Qty"] == 10


def test_rejected_order_raises():
    e, api = mk()
    api.send_result = -1
    with pytest.raises(KabusOrderError):
        e.place_order(ex.Order("1306.T", 10, signal_price=440.0), BAR, lot_size=10)


# --- 認証 --------------------------------------------------------------

def test_token_is_obtained_once_and_reused():
    e, api = mk()
    e.fetch_available_usd()
    e.fetch_available_usd()
    assert api.token_calls == 1


def test_token_is_reissued_on_401():
    """kabuステーション再起動でトークンが失効しても自動で回復すること。"""
    e, api = mk()
    e.ensure_token()
    api.raise_401_once = True
    assert e.fetch_available_usd() == pytest.approx(300000.0)
    assert api.token_calls == 2


# --- 照会 --------------------------------------------------------------

def test_positions_and_equity():
    e, api = mk()
    api.positions = [{"Symbol": "1306", "LeavesQty": 20, "CurrentPrice": 440.0}]
    assert e.fetch_positions(["1306.T", "1540.T"]) == {"1306.T": 20.0, "1540.T": 0.0}
    assert e.fetch_equity_usd() == pytest.approx(300000.0 + 20 * 440.0)


def test_reconcile_detects_mismatch():
    e, api = mk()
    api.positions = [{"Symbol": "1306", "LeavesQty": 20, "CurrentPrice": 440.0}]
    r = e.reconcile_positions(["1306.T", "1540.T"], {"1306.T": 20.0, "1540.T": 3.0})
    assert "1540.T" in r["mismatches"]
    assert "1306.T" not in r["mismatches"]
