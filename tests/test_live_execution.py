"""実発注層の回帰テスト。ccxtをモックし、実際のAPI呼び出しは一切行わない。

最重要: タイムアウト後の再送で二重発注が起きないことをコードで保証する。
"""
import ccxt
import pytest

from cta import execution as ex
from cta.live_execution import BitgetLiveExecutor, OrderPlacementError, client_order_id


class FakeExchange:
    """ccxt.bitgetの最小限フェイク。呼び出し回数と状態を記録する。"""

    def __init__(self):
        self.create_calls = 0
        self.create_call_log = []  # 各呼び出しの(side, amount, params)を記録
        self.raise_on_create = None  # 例外 or None
        self.orders_by_coid = {}  # coid -> order dict (作成済み注文)
        self.open_orders_answer = []
        self.closed_orders_answer = []
        self._positions_answer = []  # デフォルトはフラット(ヘッジmode両leg無し)
        self.amount_step = 1e-8  # デフォルトは実質丸め無し。BTCの実精度0.0001を模す場合に上書き

    def fetch_ticker(self, symbol):
        return {'last': 100.0}

    def amount_to_precision(self, symbol, amount):
        step = self.amount_step
        truncated = (amount // step) * step  # 実ccxtはTRUNCATE(切り捨て)
        rounded = round(truncated, 10)
        if rounded == 0.0:
            raise ccxt.InvalidOrder(f"amount below precision {step}")
        return rounded

    def fetch_open_orders(self, symbol):
        return self.open_orders_answer

    def fetch_closed_orders(self, symbol, limit=20):
        return self.closed_orders_answer

    def create_order(self, symbol, type, side, amount, params=None):
        self.create_calls += 1
        self.create_call_log.append((side, amount, dict(params or {})))
        if self.raise_on_create is not None:
            exc = self.raise_on_create
            self.raise_on_create = None  # 次回は成功させる(1回だけ失敗を模擬)
            raise exc
        coid = params.get('clientOid')
        order = {'clientOrderId': coid, 'filled': amount, 'average': 100.5,
                 'fee': {'cost': 0.05}, 'timestamp': 1700000000000}
        self.orders_by_coid[coid] = order
        return order

    def fetch_positions(self, symbols):
        return self._positions_answer

    def load_markets(self):
        return {}


def _executor(fake):
    ex_ = BitgetLiveExecutor.__new__(BitgetLiveExecutor)
    ex_.exchange = fake
    ex_.max_attempts = 3
    ex_.initial_delay = 0.001
    ex_.backoff_multiplier = 2.0
    ex_.max_delay = 0.01
    return ex_


def test_place_order_success():
    fake = FakeExchange()
    execu = _executor(fake)
    order = ex.Order(symbol="BTC/USDT:USDT", qty=0.5, signal_price=99.0)
    fill = execu.place_order(order, bar_epoch=1700000000)
    assert fake.create_calls == 1
    assert fill.qty == pytest.approx(0.5)
    assert fill.fill_price == pytest.approx(100.5)
    assert fill.fee_usd == pytest.approx(0.05)


def test_timeout_then_actually_succeeded_does_not_double_place():
    """タイムアウトが起きたが実は発注済みだったケース → 再送してはならない。

    逆legが無い通常ケースなので、実際に使われるclientOidは
    coid_base + 'o'(新規開設分のサフィックス)になる。"""
    fake = FakeExchange()
    coid = client_order_id("BTC/USDT:USDT", 1700000000) + "o"
    # 「1回目の発注は実は成功していた」を模擬: open_ordersに既に存在
    fake.open_orders_answer = [{'clientOrderId': coid, 'filled': 0.5,
                                'average': 100.7, 'fee': {'cost': 0.04},
                                'timestamp': 1700000000000}]
    execu = _executor(fake)
    order = ex.Order(symbol="BTC/USDT:USDT", qty=0.5, signal_price=99.0)
    fill = execu.place_order(order, bar_epoch=1700000000)
    # 事前チェックで既存注文を発見 → create_orderは一度も呼ばれない
    assert fake.create_calls == 0
    assert fill.fill_price == pytest.approx(100.7)


def test_retryable_error_then_recovers_via_lookup():
    """1回目でタイムアウト例外が飛ぶが、取引所には実は届いていた場合。
    再送前のfind_existingチェックで検出し、create_orderを再度呼ばない。"""
    fake = FakeExchange()
    coid = client_order_id("BTC/USDT:USDT", 1700000000) + "o"

    call_state = {'n': 0}
    orig_fetch_open = fake.fetch_open_orders

    def fetch_open_orders_side_effect(symbol):
        call_state['n'] += 1
        if call_state['n'] == 1:
            return []  # 発注前チェック: まだ無い
        # リトライ前チェック: タイムアウトの裏で実は成立していた
        return [{'clientOrderId': coid, 'filled': 0.5, 'average': 101.0,
                'fee': {'cost': 0.03}, 'timestamp': 1700000000000}]

    fake.fetch_open_orders = fetch_open_orders_side_effect
    fake.raise_on_create = ccxt.RequestTimeout("timeout")
    execu = _executor(fake)
    order = ex.Order(symbol="BTC/USDT:USDT", qty=0.5, signal_price=99.0)
    fill = execu.place_order(order, bar_epoch=1700000000)
    assert fake.create_calls == 1  # create_orderは1回しか呼ばれていない(=二重発注なし)
    assert fill.fill_price == pytest.approx(101.0)


def test_retryable_error_genuinely_not_placed_retries_and_succeeds():
    fake = FakeExchange()
    fake.raise_on_create = ccxt.NetworkError("blip")
    execu = _executor(fake)
    order = ex.Order(symbol="BTC/USDT:USDT", qty=0.3, signal_price=99.0)
    fill = execu.place_order(order, bar_epoch=1700000001)
    assert fake.create_calls == 2  # 1回失敗→本当に不在確認→再送で成功
    assert fill.qty == pytest.approx(0.3)


def test_non_retryable_error_raises_immediately_no_retry():
    fake = FakeExchange()
    fake.raise_on_create = ccxt.InsufficientFunds("no money")
    execu = _executor(fake)
    order = ex.Order(symbol="BTC/USDT:USDT", qty=0.3, signal_price=99.0)
    with pytest.raises(OrderPlacementError):
        execu.place_order(order, bar_epoch=1700000002)
    assert fake.create_calls == 1  # リトライしていない


def test_min_notional_blocks_dust_order():
    fake = FakeExchange()
    execu = _executor(fake)
    order = ex.Order(symbol="BTC/USDT:USDT", qty=0.01, signal_price=99.0)  # 100*0.01=1USD
    with pytest.raises(OrderPlacementError):
        execu.place_order(order, bar_epoch=1700000003, min_notional_usd=5.0)
    assert fake.create_calls == 0


def test_client_order_id_is_deterministic():
    a = client_order_id("BTC/USDT:USDT", 1700000000)
    b = client_order_id("BTC/USDT:USDT", 1700000000)
    c = client_order_id("ETH/USDT:USDT", 1700000000)
    assert a == b
    assert a != c


def test_reconcile_positions_detects_mismatch():
    fake = FakeExchange()
    fake._positions_answer = [
        {'symbol': 'BTC/USDT:USDT', 'contracts': 0.5, 'side': 'long'},
        {'symbol': 'ETH/USDT:USDT', 'contracts': 1.0, 'side': 'short'},
    ]
    execu = _executor(fake)
    result = execu.reconcile_positions(
        ["BTC/USDT:USDT", "ETH/USDT:USDT"],
        {"BTC/USDT:USDT": 0.5, "ETH/USDT:USDT": 0.5})  # ETHが内部帳簿とズレている
    assert "ETH/USDT:USDT" in result["mismatches"]
    assert "BTC/USDT:USDT" not in result["mismatches"]
    assert result["mismatches"]["ETH/USDT:USDT"]["diff"] == pytest.approx(-1.5)


# --- ヘッジモード対応（2026-07-05の実機検証で発覚したバグの回帰テスト） -------

def test_reconcile_sums_both_hedge_mode_legs_same_symbol():
    """同一銘柄でlong/short両legが同時に存在する場合、上書きせず合算する。"""
    fake = FakeExchange()
    fake._positions_answer = [
        {'symbol': 'BTC/USDT:USDT', 'contracts': 0.0001, 'side': 'long'},
        {'symbol': 'BTC/USDT:USDT', 'contracts': 0.0001, 'side': 'short'},
    ]
    execu = _executor(fake)
    result = execu.reconcile_positions(["BTC/USDT:USDT"], {"BTC/USDT:USDT": 0.0})
    # long 0.0001 - short 0.0001 = 純ポジション0 → 内部帳簿(0.0)と一致、ミスマッチなし
    assert result["exchange_positions"]["BTC/USDT:USDT"] == pytest.approx(0.0)
    assert "BTC/USDT:USDT" not in result["mismatches"]


def test_place_order_no_opposite_leg_places_single_open_order():
    """逆legが無ければ、これまで通り新規開設1回のみ（reduceOnlyは使わない）。"""
    fake = FakeExchange()
    execu = _executor(fake)
    order = ex.Order(symbol="BTC/USDT:USDT", qty=0.5, signal_price=99.0)
    fill = execu.place_order(order, bar_epoch=1700000010)
    assert fake.create_calls == 1
    side, amount, params = fake.create_call_log[0]
    assert side == 'buy' and amount == pytest.approx(0.5)
    assert params.get('reduceOnly') is None
    # 新規建てでは holdSide を送らない（送るとBitgetが一方向モードの注文と
    # 誤認し code 40774 で拒否される。2026-08-15に実機で判明）
    assert params.get('holdSide') is None
    assert fill.qty == pytest.approx(0.5)


def test_place_order_reduces_opposite_leg_before_opening_remainder():
    """既存のshort 0.2があるところへ+0.5(buy)したい場合:
    まずreduceOnlyでshort 0.2を閉じ、残り0.3を新規long開設する2段階になること。
    これが実機で発生した二重leg事故を防ぐ核心のロジック。"""
    fake = FakeExchange()
    fake._positions_answer = [
        {'symbol': 'BTC/USDT:USDT', 'contracts': 0.2, 'side': 'short'},
    ]
    execu = _executor(fake)
    order = ex.Order(symbol="BTC/USDT:USDT", qty=0.5, signal_price=99.0)
    fill = execu.place_order(order, bar_epoch=1700000011)

    assert fake.create_calls == 2
    (side1, amt1, params1), (side2, amt2, params2) = fake.create_call_log
    # 1段階目: shortを縮小(reduceOnly)
    assert side1 == 'buy' and amt1 == pytest.approx(0.2)
    # 決済側は holdSide でどちらのlegを閉じるか指定する
    assert params1.get('reduceOnly') is True and params1.get('holdSide') == 'short'
    # 2段階目: 残り0.3をlongで新規開設(reduceOnlyではない)
    assert side2 == 'buy' and amt2 == pytest.approx(0.3)
    # 新規開設側は holdSide を送らない
    assert params2.get('reduceOnly') is None and params2.get('holdSide') is None
    # 2件のfilled合計が要求量と一致する
    assert fill.qty == pytest.approx(0.5)


def test_dust_remainder_below_precision_is_skipped_not_rejected():
    """実機事故の回帰テスト: long 0.0001保有中に0.00014を売ろうとすると、
    reduceOnly分(0.0001)の後に残り0.00004という取引所最小刻み(0.0001)未満の
    端数が生じる。この端数は新規発注せず切り捨てるべき（発注してInvalidOrderに
    なるのは事故、静かに丸めて1回のreduceOnlyだけで完結するのが正しい）。"""
    fake = FakeExchange()
    fake.amount_step = 0.0001  # 実際のBTC/USDT:USDT精度を模す
    fake._positions_answer = [
        {'symbol': 'BTC/USDT:USDT', 'contracts': 0.0001, 'side': 'long'},
    ]
    execu = _executor(fake)
    order = ex.Order(symbol="BTC/USDT:USDT", qty=-0.00014, signal_price=99.0)
    fill = execu.place_order(order, bar_epoch=1700000013, min_notional_usd=0.0)
    # reduceOnly 1回のみ。端数0.00004は取引所精度未満のため新規開設は発生しない
    assert fake.create_calls == 1
    side, amount, params = fake.create_call_log[0]
    assert side == 'sell' and amount == pytest.approx(0.0001)
    assert params.get('reduceOnly') is True
    assert fill.qty == pytest.approx(-0.0001)


def test_place_order_exact_opposite_leg_only_reduces_no_remainder():
    """逆legの量とちょうど一致する場合は、reduceOnly1回だけで新規開設は発生しない。"""
    fake = FakeExchange()
    fake._positions_answer = [
        {'symbol': 'BTC/USDT:USDT', 'contracts': 0.5, 'side': 'long'},
    ]
    execu = _executor(fake)
    order = ex.Order(symbol="BTC/USDT:USDT", qty=-0.5, signal_price=99.0)  # 売り
    fill = execu.place_order(order, bar_epoch=1700000012)
    assert fake.create_calls == 1
    side, amount, params = fake.create_call_log[0]
    assert side == 'sell' and amount == pytest.approx(0.5)
    assert params.get('reduceOnly') is True and params.get('holdSide') == 'long'
    assert fill.qty == pytest.approx(-0.5)
