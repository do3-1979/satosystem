#!/usr/bin/env python3
"""Generate monthly baseline config files preserving comments.

Template: src/config.ini (with comments). Only [Period] start_time/end_time replaced.
Output: output_configs/config_baseline_<YYYY-MM>.ini

Usage:
  python src/tools/generate_monthly_configs.py --year 2025 --start-month 1 --end-month 10 \
      --template src/config.ini --outdir output_configs
"""
from __future__ import annotations
import argparse
from pathlib import Path
import re
from datetime import datetime, timedelta


def month_range(year: int, start: int, end: int):
    for m in range(start, end + 1):
        yield m


def compute_period(year: int, month: int):
    start_dt = datetime(year, month, 1)
    # 次月1日 0:00 を end とする
    if month == 12:
        end_dt = datetime(year + 1, 1, 1)
    else:
        end_dt = datetime(year, month + 1, 1)
    return start_dt, end_dt


def replace_period_block(lines, start_str, end_str):
    period_block_indices = []
    for i, line in enumerate(lines):
        if re.match(r'^\[Period\]\s*$', line.strip()):
            period_block_indices.append(i)
    if not period_block_indices:
        raise RuntimeError('[Period] セクションがテンプレートに存在しません')
    # 最初のPeriodセクションのみ変更
    start_idx = period_block_indices[0] + 1
    # 探索して start_time / end_time 行差し替え
    for j in range(start_idx, len(lines)):
        if re.match(r'^\[.+\]', lines[j]):
            break  # 次セクション到達
        if re.match(r'\s*start_time\s*=.*', lines[j]):
            lines[j] = f'start_time = {start_str}\n'
        elif re.match(r'\s*end_time\s*=.*', lines[j]):
            lines[j] = f'end_time = {end_str}\n'
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--year', type=int, required=True)
    ap.add_argument('--start-month', type=int, required=True)
    ap.add_argument('--end-month', type=int, required=True)
    ap.add_argument('--template', type=str, default='src/config.ini')
    ap.add_argument('--outdir', type=str, default='output_configs')
    args = ap.parse_args()

    template_path = Path(args.template)
    if not template_path.exists():
        raise SystemExit(f'テンプレート未存在: {template_path}')

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    template_lines = template_path.read_text(encoding='utf-8').splitlines(keepends=True)

    for m in month_range(args.year, args.start_month, args.end_month):
        start_dt, end_dt = compute_period(args.year, m)
        start_str = start_dt.strftime('%Y/%m/%d %H:%M')
        end_str = end_dt.strftime('%Y/%m/%d %H:%M')
        lines = list(template_lines)  # copy
        lines = replace_period_block(lines, start_str, end_str)
        out_file = outdir / f'config_baseline_{args.year}-{m:02d}.ini'
        out_file.write_text(''.join(lines), encoding='utf-8')
        print(f'生成: {out_file} 期間 {start_str} -> {end_str}')


if __name__ == '__main__':
    main()
