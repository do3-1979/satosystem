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


def test_equity_raises_on_unpriced_position():
    """価格の無い保有があれば黙って続行せず落とすこと。

    ゼロ扱いで飛ばすとequityを過小評価し、サーキットブレーカーの誤作動や
    誤ったサイジングにつながる。ユニバース変更後に旧銘柄の保有が state に
    残っている場合に起きる（2026-08-15にETFを19銘柄構成へ変えた後、
    WSLで実際に発生）。"""
    pf = ex.Portfolio(cash_usd=1000.0, positions={"SPY": 3.0})
    with pytest.raises(ValueError) as e:
        pf.equity({"ITOT": 170.0})          # SPYの価格が無い
    assert "SPY" in str(e.value)
    with pytest.raises(ValueError):
        pf.gross_notional({"ITOT": 170.0})


def test_equity_ok_when_stale_symbol_is_flat():
    """保有ゼロの銘柄が残っていても評価は通る（決済済みなら無害）。"""
    pf = ex.Portfolio(cash_usd=1000.0, positions={"SPY": 0.0, "ITOT": 2.0})
    assert pf.equity({"ITOT": 170.0}) == pytest.approx(1000.0 + 340.0)


def test_plan_rebalance_respects_lot_size():
    """売買単位が10口の銘柄は10の倍数に切り捨てること。

    東証ETFは銘柄ごとに1口/10口と異なる。1固定にすると10口単位の銘柄で
    発注が通らないか、意図しない数量になる。
    """
    # 目標27口 → 10口単位なら20口
    od = ex.plan_rebalance("1306.T", current_qty=0.0, target_notional_usd=2700.0,
                           price=100.0, equity_usd=100000.0, cost_model=CM,
                           no_trade_band_pct=0.0, integer_shares=True, lot_size=10)
    assert od.qty == pytest.approx(20.0)
    # 同じ条件でも1口単位なら27口
    od = ex.plan_rebalance("1540.T", current_qty=0.0, target_notional_usd=2700.0,
                           price=100.0, equity_usd=100000.0, cost_model=CM,
                           no_trade_band_pct=0.0, integer_shares=True, lot_size=1)
    assert od.qty == pytest.approx(27.0)


def test_plan_rebalance_lot_size_below_one_lot_is_skipped():
    """1単位に満たない目標は発注しない（切り捨てで0になる）。"""
    od = ex.plan_rebalance("1306.T", current_qty=0.0, target_notional_usd=900.0,
                           price=100.0, equity_usd=100000.0, cost_model=CM,
                           no_trade_band_pct=0.0, integer_shares=True, lot_size=10)
    assert od is None


def test_lot_size_does_not_affect_fractional_markets():
    """integer_shares=False（暗号資産）ではlot_sizeを無視すること。"""
    od = ex.plan_rebalance("BTC", current_qty=0.0, target_notional_usd=2700.0,
                           price=100.0, equity_usd=100000.0, cost_model=CM,
                           no_trade_band_pct=0.0, integer_shares=False, lot_size=10)
    assert od.qty == pytest.approx(27.0)
