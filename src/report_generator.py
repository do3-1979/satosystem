"""
Backtest Report Generator

Generates Markdown (and simple HTML) reports combining:
- Metrics summary (from metrics.py output)
- Performance timing summary (from PerformanceTracker)
- PnL time series metadata and links

No external dependencies; produces lightweight Markdown.
"""
from __future__ import annotations
import os
import json
from datetime import datetime
from typing import Dict, Optional, Tuple


def _fmt_pct(x: float) -> str:
    return f"{x:.2f}%"


def _fmt_sec(x: float) -> str:
    return f"{x:.3f}s"


def _phase_table(perf_summary: Dict) -> str:
    phases = perf_summary.get("phases", [])
    if not phases:
        return "(no phase data)\n"
    lines = ["| Phase | Total | Avg/iter | Share |", "|---|---:|---:|---:|"]
    for p in phases:
        lines.append(
            f"| {p['name']} | {_fmt_sec(p['total_sec'])} | {_fmt_sec(p['avg_per_iteration_sec'])} | {_fmt_pct(p['percent'])} |"
        )
    return "\n".join(lines) + "\n"


def _metrics_table(metrics: Dict) -> str:
    recovery = metrics.get("recovery_period", 0)
    recovery_str = f"{recovery} bars" if recovery >= 0 else "Not recovered"
    rows = [
        ("Total PnL", metrics.get("total_pnl", 0)),
        ("Profit Factor", metrics.get("profit_factor", 0)),
        ("Max Drawdown", metrics.get("max_drawdown", 0)),
        ("Max DD Rate", f"{metrics.get('max_drawdown_rate', 0)}%"),
        ("Recovery Period", recovery_str),
        ("Sharpe", metrics.get("sharpe", 0)),
        ("Win Rate", f"{metrics.get('win_rate', 0)}%"),
        ("Trades", metrics.get("trades", 0)),
        ("Samples", metrics.get("samples", 0)),
    ]
    lines = ["| Metric | Value |", "|---|---:|"]
    for k, v in rows:
        lines.append(f"| {k} | {v} |")
    return "\n".join(lines) + "\n"


def _pnl_section(pnl_json_path: Optional[str], pnl_csv_path: Optional[str]) -> Tuple[str, int, int, str, str]:
    bar_count = 0
    daily_count = 0
    if pnl_json_path and os.path.exists(pnl_json_path):
        try:
            with open(pnl_json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            meta = data.get('metadata', {})
            bar_count = int(meta.get('bar_count', 0))
            daily_count = int(meta.get('daily_count', 0))
            start_time = meta.get('start_time', '-')
            end_time = meta.get('end_time', '-')
        except Exception:
            start_time = end_time = '-'
    else:
        start_time = end_time = '-'
    csv_link = f"[{os.path.basename(pnl_csv_path)}]({pnl_csv_path})" if pnl_csv_path else "-"
    json_link = f"[{os.path.basename(pnl_json_path)}]({pnl_json_path})" if pnl_json_path else "-"
    section = (
        f"- Bars: {bar_count} / Daily buckets: {daily_count}\n"
        f"- Period: {start_time} → {end_time}\n"
        f"- Files: CSV {csv_link} | JSON {json_link}\n"
    )
    return section, bar_count, daily_count, csv_link, json_link


def generate_markdown_report(
    metrics: Dict,
    perf_summary: Dict,
    output_dir: str,
    ts: Optional[str] = None,
    pnl_csv_path: Optional[str] = None,
    pnl_json_path: Optional[str] = None,
    extra_notes: Optional[str] = None,
) -> str:
    """Create Markdown report file and return its path."""
    os.makedirs(output_dir, exist_ok=True)
    if not ts:
        ts = datetime.now().strftime('%Y%m%d%H%M%S')
    md_path = os.path.join(output_dir, f"backtest_report_{ts}.md")

    title = f"Backtest Report ({ts})"
    pnl_sec, bar_count, daily_count, csv_link, json_link = _pnl_section(pnl_json_path, pnl_csv_path)

    md = []
    md.append(f"# {title}")
    md.append("")
    md.append("## Summary Metrics")
    md.append(_metrics_table(metrics))
    md.append("")
    md.append("## Performance (Phase Timing)")
    md.append(f"- Iterations: {perf_summary.get('iterations', 0)}")
    md.append(f"- Total: {_fmt_sec(perf_summary.get('grand_total_sec', 0.0))}")
    md.append("")
    md.append(_phase_table(perf_summary))
    md.append("")
    md.append("## PnL Time Series")
    md.append(pnl_sec)
    if extra_notes:
        md.append("")
        md.append("## Notes")
        md.append(extra_notes)

    with open(md_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(md) + "\n")

    return md_path


if __name__ == "__main__":
    # simple self-check
    metrics = {"total_pnl": 10, "profit_factor": 1.2, "max_drawdown": 5, "max_drawdown_rate": 10, "sharpe": 0.5, "win_rate": 60, "trades": 10, "samples": 100}
    perf = {"iterations": 100, "grand_total_sec": 12.345, "phases": [
        {"name": "price_update", "total_sec": 10.0, "avg_per_iteration_sec": 0.1, "percent": 81.0},
        {"name": "logging", "total_sec": 2.0, "avg_per_iteration_sec": 0.02, "percent": 16.0},
    ]}
    p = generate_markdown_report(metrics, perf, ".", ts="TEST", pnl_csv_path="logs/pnl_timeseries_TEST.csv", pnl_json_path="logs/pnl_timeseries_TEST.json")
    print(p)
