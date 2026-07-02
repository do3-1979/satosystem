"""評価指標。プロンプト合意済みの指標セット（Sharpe/Sortino/MaxDD/集中度など）。"""
import datetime as dt

import numpy as np


def compute_metrics(res, bars_per_year):
    """BacktestResult -> dict。equity系列とfillsから全指標を計算する。"""
    eq = res.equity
    if len(eq) < 3 or eq[0] <= 0:
        return {"valid": False}
    rets = np.diff(np.log(np.maximum(eq, 1e-9)))
    years = len(eq) / bars_per_year

    ann_ret = (eq[-1] / eq[0]) ** (1 / years) - 1 if years > 0 else 0.0
    mu, sd = rets.mean(), rets.std()
    sharpe = mu / sd * np.sqrt(bars_per_year) if sd > 0 else 0.0
    downside = rets[rets < 0]
    sortino = (mu / downside.std() * np.sqrt(bars_per_year)
               if len(downside) > 1 and downside.std() > 0 else 0.0)

    peak = np.maximum.accumulate(eq)
    dd = 1 - eq / peak
    maxdd = float(dd.max())
    # DD継続期間（最長の水面下バー数 → 日数）
    under, longest, cur = dd > 1e-9, 0, 0
    for u in under:
        cur = cur + 1 if u else 0
        longest = max(longest, cur)
    dd_days = longest / (bars_per_year / 365)

    # 取引統計
    fills = res.fills
    n_trades = len(fills)
    total_slip = sum(abs(f.slippage_usd) for f in fills)
    total_dev = sum(f.signal_deviation_usd for f in fills)

    # 四半期別PnLと利益集中度
    qpnl = {}
    for i in range(1, len(eq)):
        d = dt.datetime.utcfromtimestamp(res.times[i])
        q = f"{d.year}Q{(d.month - 1) // 3 + 1}"
        qpnl[q] = qpnl.get(q, 0.0) + (eq[i] - eq[i - 1])
    total_pnl = eq[-1] - eq[0]
    pos_q = {k: v for k, v in qpnl.items() if v > 0}
    top_q_share = (max(pos_q.values()) / sum(pos_q.values())
                   if pos_q else 0.0)

    # 資産別PnL集中度
    asset_tot = res.asset_pnl.sum(axis=0)
    pos_assets = asset_tot[asset_tot > 0]
    top_asset_share = (pos_assets.max() / pos_assets.sum()
                       if len(pos_assets) and pos_assets.sum() > 0 else 0.0)

    avg_eq = float(np.mean(eq))
    return {
        "valid": True,
        "start": dt.datetime.utcfromtimestamp(res.times[0]).strftime("%Y-%m-%d"),
        "end": dt.datetime.utcfromtimestamp(res.times[-1]).strftime("%Y-%m-%d"),
        "years": years,
        "final_equity": float(eq[-1]),
        "total_pnl": float(total_pnl),
        "ann_return": float(ann_ret),
        "ann_vol": float(sd * np.sqrt(bars_per_year)),
        "sharpe": float(sharpe),
        "sortino": float(sortino),
        "maxdd": maxdd,
        "maxdd_days": float(dd_days),
        "n_trades": n_trades,
        "turnover_usd": res.turnover_usd,
        "turnover_x": res.turnover_usd / avg_eq / years if years > 0 else 0.0,
        "fees_usd": res.fees_usd,
        "funding_usd": res.funding_usd,
        "slippage_usd": total_slip,
        "cost_drag_pct": ((res.fees_usd + res.funding_usd + total_slip)
                          / avg_eq / years * 100 if years > 0 else 0.0),
        "signal_deviation_usd": total_dev,
        "top_quarter_share": float(top_q_share),
        "top_asset_share": float(top_asset_share),
        "quarterly_pnl": qpnl,
        "asset_pnl": {s: float(v) for s, v in zip(res.symbols, asset_tot)},
        "avg_gross": float(np.abs(res.weights).sum(axis=1).mean()),
        "max_gross": float(np.abs(res.weights).sum(axis=1).max()),
        "halted": res.halted_at is not None,
    }


def yearly_metrics(res, bars_per_year):
    """暦年ごとの指標（walk-forward窓・レジーム分析用）。"""
    out = {}
    years = sorted({dt.datetime.utcfromtimestamp(t).year for t in res.times})
    for y in years:
        t0 = dt.datetime(y, 1, 1).replace(tzinfo=dt.timezone.utc).timestamp()
        t1 = dt.datetime(y + 1, 1, 1).replace(tzinfo=dt.timezone.utc).timestamp()
        sub = res.slice(t0, t1)
        if len(sub.equity) > bars_per_year // 12:  # 1ヶ月分以上あるときのみ
            out[y] = compute_metrics(sub, bars_per_year)
    return out
