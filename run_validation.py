#!/usr/bin/env python3
"""Phase 3 検証ゲート一式を実行し、out/validation.json に保存 + コンソール要約。"""
import argparse
import json
import subprocess

from cta.config import load_config
from cta.engine import run_backtest
from cta.metrics import compute_metrics
from cta import validate as v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/default.ini")
    ap.add_argument("--out", default="out/validation.json")
    ap.add_argument("--skip-sensitivity", action="store_true")
    args = ap.parse_args()

    cfg = load_config(args.config)
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        commit = "?"

    print("=== full period ===")
    res = run_backtest(cfg)
    m = compute_metrics(res, cfg.bars_per_year)
    print(f"  {m['start']}..{m['end']}  sharpe {m['sharpe']:.2f}  "
          f"ann {m['ann_return']*100:+.1f}%  maxDD {m['maxdd']*100:.1f}%  "
          f"halted {m['halted']}")

    print("=== walk-forward (暦年独立窓) ===")
    wf = v.walk_forward(cfg)
    for y, w in wf.items():
        print(f"  {y}: pnl {w['total_pnl']:+8.2f}  sharpe {w['sharpe']:5.2f}  "
              f"maxDD {w['maxdd']*100:4.1f}%  halted {w['halted']}")
    gates = v.wf_gates(wf)
    print(f"  gates: all_positive={gates['all_windows_positive']}  "
          f"ex-best({gates.get('best_window')})={gates.get('sum_ex_best', 0):+.2f}")

    print("=== cost stress ===")
    cs = v.cost_stress(cfg)
    for k, c in cs.items():
        print(f"  {k}: sharpe {c['sharpe']:5.2f}  ann {c['ann_return']*100:+6.1f}%  "
              f"maxDD {c['maxdd']*100:4.1f}%  halted {c['halted']}")

    sens = None
    if not args.skip_sensitivity:
        print("=== sensitivity (数分かかります) ===")
        sens = v.sensitivity(cfg)
        for name, grid in (("target_vol × horizon_scale", sens["vol_x_horizon"]),
                           ("target_vol × vol_window", sens["vol_x_volwindow"])):
            print(f"  --- {name} (sharpe / halted) ---")
            for key, cell in grid.items():
                flag = " HALT" if cell["halted"] else ""
                print(f"    {key:16s} sharpe {cell['sharpe']:5.2f}  "
                      f"ann {cell['ann_return']*100:+6.1f}%  "
                      f"maxDD {cell['maxdd']*100:4.1f}%{flag}")

    power = v.statistical_power(m)
    print(f"=== statistical power ===\n  trades {power['n_trades']} "
          f"(min {power['min_trades']})  sharpe_se {power['sharpe_se']:.2f}  "
          f"t-stat {power['sharpe_t']:.2f}")

    out = {"commit": commit, "config_sha1": cfg.config_sha1,
           "config_path": cfg.config_path,
           "full_period": {k: val for k, val in m.items()
                           if k not in ("quarterly_pnl",)},
           "walk_forward": wf, "wf_gates": gates, "cost_stress": cs,
           "sensitivity": sens, "statistical_power": power}
    import os
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(out, f, indent=1, ensure_ascii=False, default=str)
    print(f"saved -> {args.out}")


if __name__ == "__main__":
    main()
