"""執行モデルの回帰テスト。fill式・手数料・funding符号・最小ロットの仕様を固定する。"""
import pytest

from cta import execution as ex

CM = ex.CostModel(fee_rate=0.001, slip_rate=0.002, min_notional_usd=5.0)


def test_fill_price_buy_slips_up_sell_slips_down():
    assert ex.fill_price(100.0, +1.0, 0.002) == pytest.approx(100.2)
    assert ex.fill_price(100.0, -1.0, 0.002) == pytest.approx(99.8)


def test_execute_order_fee_on_filled_notional():
    od = ex.Order("BTC", qty=2.0, signal_price=99.0)
    fill = ex.execute_order(od, ref_price=100.0, cost_model=CM)
    assert fill.fill_price == pytest.approx(100.2)
    assert fill.fee_usd == pytest.approx(2.0 * 100.2 * 0.001)
    # signal(99) → fill(100.2) の乖離が買い方向のコストとして記録される
    assert fill.signal_deviation_usd == pytest.approx(2.0 * (100.2 - 99.0))


def test_plan_rebalance_skips_small_deltas():
    # バンド: max(min_notional=5, 1%*equity=10) 未満はスキップ
    od = ex.plan_rebalance("BTC", current_qty=0.0, target_notional_usd=9.0,
                           price=100.0, equity_usd=1000.0,
                           cost_model=CM, no_trade_band_pct=0.01)
    assert od is None
    od = ex.plan_rebalance("BTC", current_qty=0.0, target_notional_usd=50.0,
                           price=100.0, equity_usd=1000.0,
                           cost_model=CM, no_trade_band_pct=0.01)
    assert od is not None and od.qty == pytest.approx(0.5)


def test_plan_rebalance_full_close_bypasses_min_notional():
    # 残骸ポジション(3 USD相当)でも target=0 なら必ずクローズ注文を出す
    od = ex.plan_rebalance("BTC", current_qty=0.03, target_notional_usd=0.0,
                           price=100.0, equity_usd=1000.0,
                           cost_model=CM, no_trade_band_pct=0.01)
    assert od is not None and od.qty == pytest.approx(-0.03)


def test_funding_sign_convention():
    # rate>0: ロング支払い(+コスト)、ショート受取り(−コスト)
    assert ex.funding_cost_usd(+1.0, 100.0, 0.0001) == pytest.approx(0.01)
    assert ex.funding_cost_usd(-1.0, 100.0, 0.0001) == pytest.approx(-0.01)
    # conservative: 実レート不明の資産は方向に関わらずコスト
    assert ex.funding_cost_usd(-1.0, 100.0, 0.0001, conservative=True) \
        == pytest.approx(0.01)


def test_portfolio_round_trip_loses_only_costs():
    pf = ex.Portfolio(cash_usd=1000.0)
    buy = ex.execute_order(ex.Order("BTC", 1.0, 100.0), 100.0, CM)
    pf.apply_fill(buy)
    sell = ex.execute_order(ex.Order("BTC", -1.0, 100.0), 100.0, CM)
    pf.apply_fill(sell)
    assert pf.positions["BTC"] == 0.0
    # 損失 = slippage往復(0.2%×2×100) + 手数料2回
    expected_loss = (100.2 - 99.8) + buy.fee_usd + sell.fee_usd
    assert 1000.0 - pf.cash_usd == pytest.approx(expected_loss)


def test_portfolio_equity_marks_to_market():
    pf = ex.Portfolio(cash_usd=1000.0)
    pf.apply_fill(ex.execute_order(ex.Order("BTC", 2.0, 100.0), 100.0, CM))
    eq = pf.equity({"BTC": 110.0})
    assert eq > 1000.0  # 値上がりが反映される
    assert pf.gross_notional({"BTC": 110.0}) == pytest.approx(220.0)
