#!/usr/bin/env python3
"""Generate monthly baseline summary Markdown table.
Assumes the latest N (months) backtest_summary_*.json files correspond to months 1..N.
Usage:
  python src/tools/generate_baseline_summary.py --year 2025 --months 10 --report-dir src/report --output src/report/baseline_2025_summary.md
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import List

COLUMNS = [
    ("month", "月"),
    ("total_pnl", "最終損益"),
    ("profit_factor", "PF"),
    ("sharpe", "Sharpe"),
    ("max_drawdown", "最大DD"),
    ("max_drawdown_rate", "最大DD率(%)"),
    ("win_rate", "勝率(%)"),
    ("trades", "取引数"),
    ("recovery_period", "回復期間(バー)"),
]


def load_latest_summaries(report_dir: Path, months: int) -> List[Path]:
    files = sorted(report_dir.glob("backtest_summary_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return list(reversed(files[:months]))  # chronological order


def format_row(m: int, data: dict) -> str:
    return "| {month:>2} | {total_pnl:>9.2f} | {profit_factor:>6.2f} | {sharpe:>6.2f} | {max_drawdown:>8.2f} | {max_drawdown_rate:>9.2f} | {win_rate:>7.2f} | {trades:>6} | {recovery_period:>8} |".format(month=m, **data)


def build_markdown(year: int, months: int, datasets: List[dict]) -> str:
    header = f"# {year}年 ベースライン月次パフォーマンス (1～{months}月)\n\n"
    header += "集計指標: 最終損益, PF, Sharpe, 最大DD, 最大DD率, 勝率, 取引数, 回復期間。最大DD率は初期証拠金補正後の値。\n\n"
    table_header = "| 月 | 最終損益 | PF | Sharpe | 最大DD | 最大DD率(%) | 勝率(%) | 取引数 | 回復期間(バー) |\n"
    table_sep = "|---:|---------:|----:|-------:|-------:|-----------:|--------:|-------:|--------------:|\n"
    rows = []
    for i, d in enumerate(datasets, start=1):
        rows.append(format_row(i, d))

    # aggregates
    total_pnl = sum(d['total_pnl'] for d in datasets)
    avg_pf = sum(d['profit_factor'] for d in datasets) / months
    avg_sharpe = sum(d['sharpe'] for d in datasets) / months
    avg_max_dd = sum(d['max_drawdown'] for d in datasets) / months
    recovered = [d['recovery_period'] for d in datasets if d['recovery_period'] not in (-1, 0)]
    median_recovery = sorted(recovered)[len(recovered)//2] if recovered else 'なし'
    summary_block = (
        "\n**総括**\n\n"
        f"- 合計損益: {total_pnl:.2f}\n"
        f"- 平均PF: {avg_pf:.2f} / 平均Sharpe: {avg_sharpe:.2f}\n"
        f"- 平均最大DD: {avg_max_dd:.2f}\n"
        f"- 回復達成月数: {len(recovered)} / 中央回復期間: {median_recovery}\n"
    )

    return header + table_header + table_sep + "\n".join(rows) + summary_block + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--months", type=int, required=True)
    ap.add_argument("--report-dir", type=str, default="src/report")
    ap.add_argument("--output", type=str, default="src/report/baseline_summary.md")
    args = ap.parse_args()

    report_dir = Path(args.report_dir)
    files = load_latest_summaries(report_dir, args.months)
    if len(files) < args.months:
        raise SystemExit(f"必要ファイルが不足: {len(files)} < {args.months}")

    datasets = []
    for f in files:
        data = json.loads(f.read_text())
        # サマリ用途のキーのみ抽出
        datasets.append({
            'total_pnl': data.get('total_pnl', 0.0),
            'profit_factor': data.get('profit_factor', 0.0),
            'sharpe': data.get('sharpe', 0.0),
            'max_drawdown': data.get('max_drawdown', 0.0),
            'max_drawdown_rate': data.get('max_drawdown_rate', 0.0),
            'win_rate': data.get('win_rate', 0.0),
            'trades': data.get('trades', 0),
            'recovery_period': data.get('recovery_period', -1),
        })

    md = build_markdown(args.year, args.months, datasets)
    out_path = Path(args.output)
    out_path.write_text(md)
    print(f"生成: {out_path} (月数={args.months})")

if __name__ == '__main__':
    main()
