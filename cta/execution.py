"""約定・コストモデル — バックテストとライブ（ペーパー/実）で共有する唯一の実行コードパス。

gen2最大の教訓: バックテストとライブで別々の約定処理を書いた結果、
「バックテストは4H終値約定・ライブはstop値約定」という乖離が静かに発生し、
存在しない利益を1年以上信じ続けた。本モジュールはその構造的再発防止であり、
fill価格・手数料・funding・最小ロットの計算は必ずここを経由する。

- バックテスト: ref_price = 次足始値 を渡す（同足約定は呼び出し側で構造的に不可能）
- ライブ:       ref_price = 発注時点の板mid/ticker を渡す
どちらも fill_price() が slippage を同一式で適用する。
"""
from dataclasses import dataclass, field


@dataclass
class CostModel:
    fee_rate: float           # taker手数料率（片道）
    slip_rate: float          # スリッページ率（片道、逆向きに滑る想定）
    min_notional_usd: float   # 取引所最小注文ノーショナル


@dataclass
class Order:
    symbol: str
    qty: float          # 符号付き数量（+買い/−売り）
    signal_price: float  # 判定時点の価格（fill乖離ロギング用）
    reason: str = "rebalance"


@dataclass
class Fill:
    symbol: str
    qty: float
    signal_price: float
    ref_price: float    # 約定基準価格（backtest: 次足始値 / live: 発注時mid）
    fill_price: float   # slippage適用後
    fee_usd: float
    reason: str
    ts: float = 0.0

    @property
    def slippage_usd(self):
        return abs(self.qty) * (self.fill_price - self.ref_price) * (1 if self.qty > 0 else -1)

    @property
    def signal_deviation_usd(self):
        """signal価格からの総乖離（gen2で未計測だった値。必ずログする）"""
        return abs(self.qty) * (self.fill_price - self.signal_price) * (1 if self.qty > 0 else -1)


def fill_price(ref_price, qty, slip_rate):
    """買いは高く・売りは安く滑る。backtest/live共通の唯一のfill式。"""
    if qty > 0:
        return ref_price * (1.0 + slip_rate)
    return ref_price * (1.0 - slip_rate)


def plan_rebalance(symbol, current_qty, target_notional_usd, price, equity_usd,
                   cost_model, no_trade_band_pct):
    """目標ノーショナルとの差分から注文を作る。バンド未満・最小ロット未満はスキップ。

    Returns Order or None."""
    if price <= 0:
        return None
    target_qty = target_notional_usd / price
    delta_qty = target_qty - current_qty
    delta_notional = abs(delta_qty) * price
    # 完全クローズ（target=0）は最小ロット制約の対象外（残骸ポジションを許さない）
    closing = target_notional_usd == 0.0 and current_qty != 0.0
    if not closing:
        if delta_notional < max(cost_model.min_notional_usd,
                                no_trade_band_pct * equity_usd):
            return None
    elif delta_notional == 0.0:
        return None
    return Order(symbol=symbol, qty=delta_qty, signal_price=price)


def execute_order(order, ref_price, cost_model, ts=0.0):
    """注文を約定させFillを返す。手数料は約定ノーショナルに対して課す。"""
    fp = fill_price(ref_price, order.qty, cost_model.slip_rate)
    fee = abs(order.qty) * fp * cost_model.fee_rate
    return Fill(symbol=order.symbol, qty=order.qty, signal_price=order.signal_price,
                ref_price=ref_price, fill_price=fp, fee_usd=fee,
                reason=order.reason, ts=ts)


def funding_cost_usd(qty, price, rate, conservative=False):
    """funding授受。rate>0でロングが支払い・ショートが受取り（perp標準）。

    conservative=True は実レート履歴が無い資産用: 符号に関わらずコストとして課す。"""
    notional = qty * price
    if conservative:
        return abs(notional) * abs(rate)
    return notional * rate  # ロング(+qty)は支払い、ショートは受取り(負のコスト)


@dataclass
class Portfolio:
    """現金+ポジションの会計。backtest/paperで共有。equityは時価評価。"""
    cash_usd: float
    positions: dict = field(default_factory=dict)   # symbol -> qty(符号付き)

    def apply_fill(self, fill):
        self.cash_usd -= fill.qty * fill.fill_price
        self.cash_usd -= fill.fee_usd
        q = self.positions.get(fill.symbol, 0.0) + fill.qty
        if abs(q) < 1e-12:
            q = 0.0
        self.positions[fill.symbol] = q

    def apply_funding(self, symbol, price, rate, conservative=False):
        qty = self.positions.get(symbol, 0.0)
        if qty == 0.0 or rate == 0.0:
            return 0.0
        cost = funding_cost_usd(qty, price, rate, conservative)
        self.cash_usd -= cost
        return cost

    def equity(self, prices):
        eq = self.cash_usd
        for sym, qty in self.positions.items():
            if qty != 0.0:
                eq += qty * prices[sym]
        return eq

    def gross_notional(self, prices):
        return sum(abs(q) * prices[s] for s, q in self.positions.items() if q != 0.0)
