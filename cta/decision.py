"""売買判断の共有レイヤ。

ペーパートレードと実発注で**判断ロジックを一切分岐させない**ために、
「シグナル計算 → 目標ウェイト → 発注意図(Order)の生成」をここに集約する。
呼び出し側（paper.py / live_trader.py）は、ここが返したOrderを
シミュレート約定するか実発注するかだけが異なる。

gen2最大の教訓（バックテストとライブで別々の約定処理を書いた結果、
静かに乖離した）を、判断層でも繰り返さないための構造。
"""
import numpy as np

from . import execution as ex
from . import strategy as st


def compute_signals(cfg, closes, t):
    """時点tのトレンドシグナルと実現volを返す。t以前の確定バーのみ使用。"""
    bpd, bpy = cfg.bars_per_day, cfg.bars_per_year
    logc = np.log(closes)
    rets = np.vstack([np.full((1, closes.shape[1]), np.nan),
                      np.diff(logc, axis=0)])
    horizons = [(f * bpd, s * bpd) for f, s in cfg.horizons_days]
    sig_t = np.array([st.trend_signal(logc[:t + 1, j], horizons)[-1]
                      for j in range(closes.shape[1])])
    vol_t = np.array([st.trailing_vol(rets[:t + 1, j],
                                      cfg.vol_window_days * bpd, bpy)[-1]
                      for j in range(closes.shape[1])])
    return sig_t, vol_t, rets


def plan_orders(cfg, closes, t, positions, equity, vol_scale, cost_model,
                prices=None):
    """時点tのリバランス注文を組み立てて返す。

    positions: {symbol: qty} 現在の保有（実発注では取引所の実残を渡すこと）
    prices:    発注可否の判定に使う価格。Noneならバー終値を使う。
    Returns: list[ex.Order]
    """
    bpd, bpy = cfg.bars_per_day, cfg.bars_per_year
    sig_t, vol_t, rets = compute_signals(cfg, closes, t)
    w = st.target_weights(sig_t, vol_t,
                          rets[t - cfg.vol_window_days * bpd:t],
                          cfg.target_vol * vol_scale, cfg.max_gross, bpy,
                          long_only=cfg.long_only)
    orders = []
    for j, sym in enumerate(cfg.symbols):
        px = closes[t, j]
        if np.isnan(px) or px <= 0:
            continue
        if prices is not None and sym not in prices:
            continue
        od = ex.plan_rebalance(sym, positions.get(sym, 0.0), w[j] * equity,
                               px, equity, cost_model, cfg.no_trade_band_pct,
                               integer_shares=cfg.integer_shares)
        if od is not None:
            orders.append(od)
    return orders


def plan_flatten_orders(positions, signal_prices, reason="circuit_breaker"):
    """全ポジションを閉じる注文を返す（サーキットブレーカー用）。

    【重要】実発注では positions に**取引所の実ポジション**を渡すこと。
    緊急クローズ時は内部帳簿ではなく取引所の実態こそが真実であり、
    照合不一致があっても決済は断行しなければならない
    （止めると損失を止めるためのブレーカーが損失を垂れ流す）。
    """
    orders = []
    for sym, qty in positions.items():
        if qty and qty != 0.0:
            orders.append(ex.Order(symbol=sym, qty=-qty,
                                   signal_price=signal_prices.get(sym, 0.0),
                                   reason=reason))
    return orders
