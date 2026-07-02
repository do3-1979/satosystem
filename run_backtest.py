#!/usr/bin/env python3
"""バックテスト実行 + サマリ表示（+ 任意でHTMLレポート生成）。"""
import argparse
import datetime as dt
import subprocess

from cta.config import load_config
from cta.engine import run_backtest
from cta.metrics import compute_metrics, yearly_metrics


def ep(s):
    return dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc).timestamp()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/default.ini")
    ap.add_argument("--start", default=None, help="YYYY-MM-DD")
    ap.add_argument("--end", default=None, help="YYYY-MM-DD")
    ap.add_argument("--cost-mult", type=float, default=1.0)
    ap.add_argument("--report", default=None, help="HTMLレポート出力パス")
    args = ap.parse_args()

    cfg = load_config(args.config)
    res = run_backtest(cfg,
                       start_epoch=ep(args.start) if args.start else None,
                       end_epoch=ep(args.end) if args.end else None,
                       cost_mult=args.cost_mult)
    m = compute_metrics(res, cfg.bars_per_year)
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        commit = "?"

    print(f"=== backtest {m['start']} .. {m['end']} "
          f"(config {cfg.config_sha1} @ {commit}, cost x{args.cost_mult}) ===")
    print(f"equity     : {cfg.init_capital_usd:.0f} -> {m['final_equity']:.2f} USD "
          f"({m['ann_return']*100:+.1f}%/yr)")
    print(f"sharpe     : {m['sharpe']:.2f}   sortino: {m['sortino']:.2f}   "
          f"vol: {m['ann_vol']*100:.1f}%")
    print(f"maxDD      : {m['maxdd']*100:.1f}% ({m['maxdd_days']:.0f}d)   "
          f"halted: {m['halted']}")
    print(f"trades     : {m['n_trades']}   turnover: {m['turnover_x']:.1f}x/yr   "
          f"cost drag: {m['cost_drag_pct']:.1f}%/yr")
    print(f"costs USD  : fee {m['fees_usd']:.2f} / funding {m['funding_usd']:.2f} "
          f"/ slip {m['slippage_usd']:.2f}")
    print(f"gross lev  : avg {m['avg_gross']:.2f}x / max {m['max_gross']:.2f}x")
    print(f"concentr.  : top quarter {m['top_quarter_share']*100:.0f}% / "
          f"top asset {m['top_asset_share']*100:.0f}%")
    print("--- yearly ---")
    for y, ym in yearly_metrics(res, cfg.bars_per_year).items():
        if ym.get("valid"):
            print(f"  {y}: {ym['ann_return']*100:+7.1f}%/yr  "
                  f"sharpe {ym['sharpe']:5.2f}  maxDD {ym['maxdd']*100:4.1f}%  "
                  f"pnl {ym['total_pnl']:+8.2f}")
    print("--- asset pnl ---")
    for s, v in sorted(m["asset_pnl"].items(), key=lambda x: -x[1]):
        print(f"  {s:20s} {v:+9.2f}")

    if args.report:
        from cta.report import write_report
        write_report(args.report, cfg, res, m,
                     yearly_metrics(res, cfg.bars_per_year), commit)
        print(f"report -> {args.report}")


if __name__ == "__main__":
    main()
