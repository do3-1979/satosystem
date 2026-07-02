"""Phase 3 検証ゲート: walk-forward OOS / コストストレス / パラメータ感応度。

本戦略はパラメータをデータに最適化しない（ホライズン等は文献標準の固定値）ため、
walk-forwardは「fit→OOS」ではなく暦年ごとの独立評価＝レジーム頑健性テストとして行う。
感応度分析は過学習の定量指標: 近傍パラメータでPnLが激しく振れる＝危険信号。
"""
import datetime as dt

import numpy as np

from .engine import run_backtest
from .metrics import compute_metrics


def _ep(y, m=1, d=1):
    return dt.datetime(y, m, d, tzinfo=dt.timezone.utc).timestamp()


def walk_forward(cfg, years=(2022, 2023, 2024, 2025, 2026)):
    """暦年ごとに資本$initでリセットした独立窓評価（各窓の内部は連続運用）。"""
    out = {}
    for y in years:
        res = run_backtest(cfg, start_epoch=_ep(y), end_epoch=_ep(y + 1))
        m = compute_metrics(res, cfg.bars_per_year)
        if m.get("valid"):
            out[str(y)] = {k: m[k] for k in
                           ("start", "end", "total_pnl", "ann_return", "sharpe",
                            "maxdd", "n_trades", "halted")}
    return out


def wf_gates(wf):
    """KEEP/KILL判定ゲート: 全窓プラス & 最大貢献窓を除いても累積プラス。"""
    pnls = {y: w["total_pnl"] for y, w in wf.items()}
    if not pnls:
        return {"all_windows_positive": False, "positive_ex_best": False}
    best = max(pnls, key=pnls.get)
    ex_best = sum(v for y, v in pnls.items() if y != best)
    return {
        "all_windows_positive": all(v > 0 for v in pnls.values()),
        "best_window": best,
        "sum_ex_best": ex_best,
        "positive_ex_best": ex_best > 0,
    }


def cost_stress(cfg, mults=(1.0, 3.0, 5.0)):
    """コスト1x/3x/5xでの全期間成績。現実コストの3-5倍で有意にプラスが理想。"""
    out = {}
    for m in mults:
        res = run_backtest(cfg, cost_mult=m)
        met = compute_metrics(res, cfg.bars_per_year)
        out[f"{m:g}x"] = {k: met[k] for k in
                          ("ann_return", "sharpe", "maxdd", "final_equity",
                           "cost_drag_pct", "halted")}
    return out


def sensitivity(cfg,
                target_vols=(0.10, 0.15, 0.20, 0.25, 0.30),
                horizon_scales=(0.5, 0.75, 1.0, 1.5, 2.0),
                vol_windows=(15, 30, 60)):
    """2枚のヒートマップ用グリッド:
    (A) target_vol × horizon_scale — リスク水準とトレンド速度の感応度
    (B) target_vol × vol_window   — vol推定窓の感応度
    各セル: sharpe / ann_return / maxdd / halted。滑らかであること＝低過学習の証拠。"""
    def run(tv, hs=1.0, vw=None):
        hd = [(max(1, round(f * hs)), max(2, round(s * hs)))
              for f, s in cfg.horizons_days]
        res = run_backtest(cfg, target_vol=tv, horizons_days=hd,
                           vol_window_days=vw or cfg.vol_window_days)
        m = compute_metrics(res, cfg.bars_per_year)
        return {k: m[k] for k in ("sharpe", "ann_return", "maxdd",
                                  "final_equity", "halted")}

    grid_a = {f"tv={tv:g}|hs={hs:g}": run(tv, hs=hs)
              for tv in target_vols for hs in horizon_scales}
    grid_b = {f"tv={tv:g}|vw={vw}": run(tv, vw=vw)
              for tv in target_vols for vw in vol_windows}
    return {"vol_x_horizon": grid_a, "vol_x_volwindow": grid_b,
            "axes": {"target_vols": list(target_vols),
                     "horizon_scales": list(horizon_scales),
                     "vol_windows": list(vol_windows)}}


def statistical_power(m, min_trades=100):
    """判定に足る取引数か。加えてバー数ベースのSharpe標準誤差を示す。"""
    n = m.get("n_trades", 0)
    years = m.get("years", 0.0)
    # Sharpe推定の標準誤差 ≈ sqrt((1+SR^2/2)/T_years) （年次観測近似）
    sr = m.get("sharpe", 0.0)
    se = np.sqrt((1 + sr * sr / 2) / years) if years > 0.5 else float("inf")
    return {"n_trades": n, "min_trades": min_trades,
            "sufficient_trades": n >= min_trades,
            "sharpe_se": float(se),
            "sharpe_t": float(sr / se) if se > 0 and np.isfinite(se) else 0.0}
