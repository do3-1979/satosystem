"""バックテストエンジン。

忠実度の原則（gen2の教訓）:
  - 判定はバーt終値、約定は必ずバーt+1始値±slippage（execution.fill_price経由）。
    同足約定はコード構造上不可能（pending_ordersは次バー先頭でのみ執行）。
  - 手数料・funding・最小ロット・取引バンドはライブと同一の execution/strategy を使用。
  - 連続運用: 全期間を単一の資本で複利運用し、資本リセットでDDを隠さない。
"""
from dataclasses import dataclass, field

import numpy as np

from . import data as data_mod
from . import execution as ex
from . import strategy as st


@dataclass
class BacktestResult:
    times: np.ndarray          # [T] epoch秒
    equity: np.ndarray         # [T]
    weights: np.ndarray        # [T,N] 実現ウェイト（時価/equity）
    pos_qty: np.ndarray        # [T,N]
    asset_pnl: np.ndarray      # [T,N] バーごと資産別PnL（コスト込み）
    fills: list = field(default_factory=list)
    symbols: list = field(default_factory=list)
    fees_usd: float = 0.0
    funding_usd: float = 0.0
    slippage_usd: float = 0.0
    turnover_usd: float = 0.0
    halted_at: float = None    # サーキットブレーカー発動epoch（未発動ならNone）
    config_sha1: str = ""

    def slice(self, t0, t1):
        """[t0, t1) のepoch範囲でビューを返す（メトリクス窓別計算用）。"""
        m = (self.times >= t0) & (self.times < t1)
        r = BacktestResult(self.times[m], self.equity[m], self.weights[m],
                           self.pos_qty[m], self.asset_pnl[m],
                           [f for f in self.fills if t0 <= f.ts < t1],
                           self.symbols)
        return r


def run_backtest(cfg, start_epoch=None, end_epoch=None, cost_mult=1.0,
                 target_vol=None, horizons_days=None, vol_window_days=None):
    """設定に基づいてバックテストを実行する。

    cost_mult: コストストレステスト用（手数料・slippage・fundingを一律倍率）
    target_vol / horizons_days / vol_window_days: 感応度分析用オーバーライド
    """
    horizons_days = horizons_days or cfg.horizons_days
    vol_window_days = vol_window_days or cfg.vol_window_days
    target_vol = target_vol if target_vol is not None else cfg.target_vol

    times, opens_df, closes_df = data_mod.load_universe(
        cfg.db_path, cfg.symbols, cfg.timeframe_min)
    opens = opens_df.to_numpy(float)
    closes = closes_df.to_numpy(float)
    T, N = closes.shape
    bpd, bpy = cfg.bars_per_day, cfg.bars_per_year

    # 事前計算（シグナル・vol・リターンは終値のみ使用 → 判定は常にバー確定値）
    logc = np.log(closes)
    rets = np.vstack([np.full((1, N), np.nan), np.diff(logc, axis=0)])
    horizons_bars = [(f * bpd, s * bpd) for f, s in horizons_days]
    sig = np.column_stack([st.trend_signal(logc[:, j], horizons_bars)
                           for j in range(N)])
    vol = np.column_stack([st.trailing_vol(rets[:, j], vol_window_days * bpd, bpy)
                           for j in range(N)])
    fr, fr_conservative = data_mod.load_funding(
        cfg.funding_pkl, cfg.symbols, times, cfg.timeframe_min,
        cfg.funding_default_annual)

    # 時価評価用: 上場前/欠損バーは直近有効終値で評価
    closes_ff = closes_df.ffill().to_numpy(float)

    cost_model = ex.CostModel(fee_rate=cfg.fee_rate * cost_mult,
                              slip_rate=cfg.slip_rate * cost_mult,
                              min_notional_usd=cfg.min_notional_usd)
    breaker = st.CircuitBreaker(cfg.dd_soft, cfg.dd_hard)
    pf = ex.Portfolio(cash_usd=cfg.init_capital_usd)

    warmup = max(s for _, s in horizons_bars) + vol_window_days * bpd + 2
    reb = max(1, cfg.rebalance_days * bpd)
    t_begin = warmup
    if start_epoch is not None:
        t_begin = max(t_begin, int(np.searchsorted(times, start_epoch)))
    t_end = T if end_epoch is None else int(np.searchsorted(times, end_epoch))

    equity_hist = np.full(T, np.nan)
    weights_hist = np.zeros((T, N))
    qty_hist = np.zeros((T, N))
    asset_pnl = np.zeros((T, N))
    fills = []
    fees = funding_paid = slip_total = turnover = 0.0
    halted_at = None
    pending = []  # (Order) — 次バー始値で執行
    vol_scale = 1.0

    for t in range(t_begin, t_end):
        # 1) 前バーで決定した注文をこのバーの始値で執行（唯一の約定パス）
        still_pending = []
        for od in pending:
            j = cfg.symbols.index(od.symbol)
            ref = opens[t, j]
            if np.isnan(ref):
                still_pending.append(od)  # バー欠損 → 次バーへ持ち越し
                continue
            fill = ex.execute_order(od, ref, cost_model, ts=times[t])
            pf.apply_fill(fill)
            fills.append(fill)
            fees += fill.fee_usd
            slip_total += abs(fill.slippage_usd)
            turnover += abs(fill.qty) * fill.fill_price
            asset_pnl[t, j] -= fill.fee_usd + fill.slippage_usd
        pending = still_pending

        # 2) funding授受（バーtの保有に対し、当バー区間のレートで）
        for j, sym in enumerate(cfg.symbols):
            px = closes_ff[t, j]
            if np.isnan(px):
                continue
            cost = pf.apply_funding(sym, px, fr[t, j] * cost_mult,
                                    conservative=bool(fr_conservative[j]))
            funding_paid += cost
            asset_pnl[t, j] -= cost

        # 3) 時価評価
        prices = {sym: closes_ff[t, j] for j, sym in enumerate(cfg.symbols)
                  if not np.isnan(closes_ff[t, j])}
        eq = pf.cash_usd + sum(pf.positions.get(s, 0.0) * p
                               for s, p in prices.items())
        equity_hist[t] = eq
        for j, sym in enumerate(cfg.symbols):
            q = pf.positions.get(sym, 0.0)
            qty_hist[t, j] = q
            if q != 0.0 and not np.isnan(closes_ff[t, j]) and t > 0 \
                    and not np.isnan(closes_ff[t - 1, j]):
                asset_pnl[t, j] += q * (closes_ff[t, j] - closes_ff[t - 1, j])
            if q != 0.0 and eq > 0 and not np.isnan(closes_ff[t, j]):
                weights_hist[t, j] = q * closes_ff[t, j] / eq

        # 4) サーキットブレーカー
        was_halted = breaker.halted
        vol_scale = breaker.update(eq)
        if breaker.halted:
            if not was_halted:
                halted_at = times[t]
                pending = [ex.Order(sym, -pf.positions[sym], prices.get(sym, 0.0),
                                    reason="circuit_breaker")
                           for sym in cfg.symbols
                           if pf.positions.get(sym, 0.0) != 0.0]
            continue  # 停止中はリバランスしない

        # 5) リバランス判定（終値ベース → 注文は次バー始値で執行される）
        if (t - t_begin) % reb == 0 and eq > 0:
            w = st.target_weights(sig[t], vol[t], rets[t - vol_window_days * bpd:t],
                                  target_vol * vol_scale, cfg.max_gross, bpy)
            pending = []
            for j, sym in enumerate(cfg.symbols):
                px = closes[t, j]
                if np.isnan(px):
                    continue  # 当バーの確定値が無い銘柄は触らない
                od = ex.plan_rebalance(sym, pf.positions.get(sym, 0.0),
                                       w[j] * eq, px, eq, cost_model,
                                       cfg.no_trade_band_pct)
                if od is not None:
                    pending.append(od)

    m = ~np.isnan(equity_hist)
    return BacktestResult(times=times[m], equity=equity_hist[m],
                          weights=weights_hist[m], pos_qty=qty_hist[m],
                          asset_pnl=asset_pnl[m], fills=fills,
                          symbols=list(cfg.symbols), fees_usd=fees,
                          funding_usd=funding_paid, slippage_usd=slip_total,
                          turnover_usd=turnover, halted_at=halted_at,
                          config_sha1=cfg.config_sha1)
