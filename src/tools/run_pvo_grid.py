#!/usr/bin/env python3
"""Run PVO parameter grid backtests.

Generates runs for (pvo_s_term, pvo_l_term, pvo_threshold) combinations per year.
Outputs renamed summary & trades JSON plus an aggregated CSV/JSON including PVO hit ratio.

Usage:
    python tools/run_pvo_grid.py --years 2024 2025
    python tools/run_pvo_grid.py --years 2024 --limit 8

Design:
    - Edits config.ini in-place (backup then restore at end).
    - For each year: set start/end period 1/1 00:00 -> 12/31 23:59.
    - Reload Config, reset singletons, run Bot directly (skip wrapper for speed).
    - After each run, locate latest backtest_summary_*.json & trend_trades_*.json and copy
      to report/pvo_runs/<year>/pvo_S{S}_L{L}_T{T}_{year}_summary.json etc.
    - Aggregate metrics into list and finally write:
         report/pvo_runs/<year>/pvo_grid_aggregate_<timestamp>.json
         report/pvo_runs/<year>/pvo_grid_aggregate_<timestamp>.csv

Early stop logic:
    For a fixed (L, T), if S sweep (5,8,12) produces three consecutive runs with
    total_pnl < 0 and profit_factor < 0.8, remaining S for that (L,T) are skipped.

Safety:
    Restores original config.ini on success/failure.
"""
import argparse
import shutil
import time
import json
import os
import sys
import re
from pathlib import Path
from datetime import datetime

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from config import Config
from bybit_exchange import BybitExchange
from price_data_management import PriceDataManagement
from indicator_service import IndicatorService
from risk_management import RiskManagement
from trading_strategy import TradingStrategy
from portfolio import Portfolio
from bot import Bot


COMBINATIONS = [
    # Filtered 32 combos (see docs/PVO_OPT_PLAN.md)
    (5, 26, 0), (5, 26, 10), (5, 26, 20), (5, 26, 30),
    (5, 50, 0), (5, 50, 10), (5, 50, 20), (5, 50, 30),
    (5, 70, 0), (5, 70, 10), (5, 70, 20),
    (8, 26, 0), (8, 26, 10), (8, 26, 20), (8, 26, 30),
    (8, 50, 0), (8, 50, 10), (8, 50, 20), (8, 50, 30),
    (8, 70, 0), (8, 70, 10), (8, 70, 20),
    (12, 26, 0), (12, 26, 10), (12, 26, 20), (12, 26, 30),
    (12, 50, 0), (12, 50, 10), (12, 50, 20), (12, 50, 30),
    (12, 70, 0), (12, 70, 10),
]


def load_api_keys():
    """Load API keys from .api_key file."""
    api_key = None
    api_secret = None
    api_key_file = ".api_key"
    if os.path.exists(api_key_file):
        with open(api_key_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('api_key'):
                    api_key = line.split('=', 1)[1].strip()
                elif line.startswith('api_secret'):
                    api_secret = line.split('=', 1)[1].strip()
    return api_key, api_secret


def inject_api_keys(config_file, api_key, api_secret):
    """Inject API keys into config file, replacing placeholder values only."""
    with open(config_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Simple replacement approach: replace api_key and api_secret lines directly
    content = re.sub(r'^api_key\s*=.*$', f'api_key = {api_key}', content, flags=re.MULTILINE)
    content = re.sub(r'^api_secret\s*=.*$', f'api_secret = {api_secret}', content, flags=re.MULTILINE)
    
    with open(config_file, 'w', encoding='utf-8') as f:
        f.write(content)


def write_config_params(original_lines, year, s_term, l_term, threshold):
    """Return modified config lines with period & PVO params replaced."""
    start_line = f"start_time = {year}/01/01 0:00\n"
    end_line = f"end_time = {year}/12/31 23:59\n"
    new_lines = []
    for line in original_lines:
        if line.startswith("start_time = "):
            new_lines.append(start_line)
        elif line.startswith("end_time = "):
            new_lines.append(end_line)
        elif line.startswith("pvo_s_term = "):
            new_lines.append(f"pvo_s_term = {s_term}\n")
        elif line.startswith("pvo_l_term = "):
            new_lines.append(f"pvo_l_term = {l_term}\n")
        elif line.startswith("pvo_threshold = "):
            new_lines.append(f"pvo_threshold = {threshold}\n")
        else:
            new_lines.append(line)
    return new_lines


def locate_latest(pattern: str, report_dir: Path):
    files = sorted(report_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def run_single(year: int, s: int, l: int, t: int, report_root: Path):
    """Run one backtest for a given combination, return metrics dict."""
    # Reset config cache & singletons
    Config.reload_config()
    PriceDataManagement.reset_instance()
    from logger import Logger
    Logger.reset_instance()

    exchange = BybitExchange(Config.get_api_key(), Config.get_api_secret())
    portfolio = Portfolio()
    indicator_service = IndicatorService()
    pdm = PriceDataManagement(indicator_service=indicator_service)
    risk = RiskManagement(pdm, portfolio, indicator_service=indicator_service)
    strat = TradingStrategy(pdm, risk, portfolio)
    bot = Bot(exchange, strat, risk, pdm, portfolio)

    bot.run()  # backtest mode expected

    # After run locate latest summary/trades
    summary = locate_latest("backtest_summary_*.json", report_root)
    trades = locate_latest("trend_trades_*.json", report_root)
    metrics = {}
    if summary and summary.exists():
        with open(summary, 'r', encoding='utf-8') as f:
            metrics = json.load(f)
    else:
        metrics = {"total_pnl": 0, "profit_factor": 0, "max_drawdown": 0, "win_rate": 0, "trades": 0}

    # Add PVO hit info
    pvo_metrics = pdm.get_pvo_donchian_metrics()
    metrics.update({
        "donchian_candidates": pvo_metrics['donchian_candidates'],
        "pvo_passes": pvo_metrics['pvo_passes'],
        "pvo_pass_ratio": pvo_metrics['pvo_pass_ratio']
    })

    # Copy artifacts
    year_dir = report_root / "pvo_runs" / str(year)
    year_dir.mkdir(parents=True, exist_ok=True)
    ts_tag = datetime.now().strftime("%Y%m%d%H%M%S")
    base_name = f"pvo_S{s}_L{l}_T{t}_{year}"
    if summary:
        shutil.copy(summary, year_dir / f"{base_name}_summary.json")
    if trades:
        shutil.copy(trades, year_dir / f"{base_name}_trades.json")
    # Persist extended metrics for this run
    with open(year_dir / f"{base_name}_metrics.json", 'w', encoding='utf-8') as wf:
        json.dump(metrics, wf, ensure_ascii=False, indent=2)
    return metrics


def main():
    parser = argparse.ArgumentParser(description="PVO grid backtester")
    parser.add_argument("--years", nargs="+", type=int, required=True, help="Target years e.g. 2024 2025")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of combinations (debug)")
    parser.add_argument("--early-stop", action="store_true", help="Enable early stop pruning logic")
    args = parser.parse_args()

    # Load API keys first
    api_key, api_secret = load_api_keys()
    if not api_key or not api_secret:
        print("Error: API keys not found in .api_key file")
        return
    print(f"Loaded API keys from .api_key")

    report_dir = Path(Config.get_report_dir_name())
    config_path = Path("config.ini")
    backup_path = Path("config_pvo_grid_backup.ini")
    if config_path.exists():
        shutil.copy(config_path, backup_path)

    try:
        original_lines = config_path.read_text(encoding="utf-8_sig").splitlines(keepends=True)
        all_results = {}
        combos = COMBINATIONS[: args.limit] if args.limit else COMBINATIONS

        for year in args.years:
            year_results = []
            print(f"==== YEAR {year} ====")
            # Group combinations by (L,T) for early-stop logic
            grouped = {}
            for s,l,t in combos:
                grouped.setdefault((l,t), []).append((s,l,t))

            for (l_val, t_val), tuple_list in grouped.items():
                failure_count = 0
                for (s,l,t) in tuple_list:
                    print(f"[RUN] Year={year} S={s} L={l} T={t}")
                    # Rewrite config
                    new_lines = write_config_params(original_lines, year, s, l, t)
                    config_path.write_text(''.join(new_lines), encoding="utf-8_sig")
                    # Inject API keys
                    inject_api_keys(str(config_path), api_key, api_secret)
                    # Reload config
                    Config.reload_config()
                    # Run single
                    metrics = run_single(year, s, l, t, report_dir)
                    metrics.update({"year": year, "pvo_s_term": s, "pvo_l_term": l, "pvo_threshold": t})
                    year_results.append(metrics)
                    pnl = metrics.get("total_pnl", 0)
                    pf = metrics.get("profit_factor", 0)
                    if args.early_stop:
                        if pnl < 0 and pf < 0.8:
                            failure_count += 1
                        else:
                            failure_count = 0
                        if failure_count >= 3:
                            print(f"[PRUNE] (L={l_val},T={t_val}) 連続3失敗で残りS打ち切り")
                            break

            # Aggregate outputs per year
            ts = time.strftime('%Y%m%d%H%M%S')
            agg_dir = report_dir / "pvo_runs" / str(year)
            agg_dir.mkdir(parents=True, exist_ok=True)
            agg_json = agg_dir / f"pvo_grid_aggregate_{ts}.json"
            agg_csv = agg_dir / f"pvo_grid_aggregate_{ts}.csv"
            with open(agg_json, 'w', encoding='utf-8') as jf:
                json.dump(year_results, jf, ensure_ascii=False, indent=2)
            # CSV
            headers = ["year","pvo_s_term","pvo_l_term","pvo_threshold","total_pnl","profit_factor","max_drawdown","win_rate","trades","donchian_candidates","pvo_passes","pvo_pass_ratio"]
            with open(agg_csv, 'w', encoding='utf-8') as cf:
                cf.write(','.join(headers) + '\n')
                for r in year_results:
                    row = [
                        r.get(h.split('_')[0] if h.startswith('pvo_') else h, r.get(h)) if h not in ("pvo_s_term","pvo_l_term","pvo_threshold") else r.get(h)
                        for h in headers
                    ]
                    # Adjust direct keys
                    row = [r.get("year"), r.get("pvo_s_term"), r.get("pvo_l_term"), r.get("pvo_threshold"), r.get("total_pnl"), r.get("profit_factor"), r.get("max_drawdown"), r.get("win_rate"), r.get("trades"), r.get("donchian_candidates"), r.get("pvo_passes"), r.get("pvo_pass_ratio")]
                    cf.write(','.join(str(x) for x in row) + '\n')
            print(f"[AGG] JSON: {agg_json}")
            print(f"[AGG] CSV : {agg_csv}")
            all_results[year] = year_results

    finally:
        # Restore original config
        if backup_path.exists():
            shutil.move(str(backup_path), str(config_path))
            print("[RESTORE] config.ini restored from backup")
        # Reload to original
        Config.reload_config()

    print("\nDone.")


if __name__ == "__main__":
    main()
