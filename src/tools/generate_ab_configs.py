#!/usr/bin/env python3
"""Generate A/B test config pairs for Keltner, Pyramiding, and Partial Exit experiments.

Creates paired config files with one parameter varied while keeping others at baseline.
Output: output_configs/ab_test_<experiment>_<variant>.ini

Usage:
  python src/tools/generate_ab_configs.py --template src/config.ini \
      --period-start "2025/10/01 0:00" --period-end "2025/11/01 0:00" \
      --outdir output_configs
"""
from __future__ import annotations
import argparse
from pathlib import Path
import re


def replace_config_value(lines: list, section: str, key: str, value: str) -> list:
    """Replace a specific key=value in given section."""
    in_section = False
    result = []
    for line in lines:
        # Check for section header
        section_match = re.match(r'^\[(.+)\]\s*$', line.strip())
        if section_match:
            in_section = (section_match.group(1) == section)
            result.append(line)
            continue
        
        # If in target section, check for key
        if in_section:
            key_match = re.match(r'\s*(\w+)\s*=.*', line)
            if key_match and key_match.group(1) == key:
                # Replace this line
                result.append(f'{key} = {value}\n')
                continue
        
        result.append(line)
    return result


def generate_period_config(template_lines: list, start_str: str, end_str: str) -> list:
    """Replace [Period] start_time and end_time."""
    lines = list(template_lines)
    lines = replace_config_value(lines, 'Period', 'start_time', start_str)
    lines = replace_config_value(lines, 'Period', 'end_time', end_str)
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--template', type=str, default='src/config.ini')
    ap.add_argument('--period-start', type=str, required=True, help='Start time e.g. "2025/10/01 0:00"')
    ap.add_argument('--period-end', type=str, required=True, help='End time e.g. "2025/11/01 0:00"')
    ap.add_argument('--outdir', type=str, default='output_configs')
    args = ap.parse_args()
    
    template_path = Path(args.template)
    if not template_path.exists():
        raise SystemExit(f'Template not found: {template_path}')
    
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    
    template_lines = template_path.read_text(encoding='utf-8').splitlines(keepends=True)
    
    # ベースライン期間設定
    base_lines = generate_period_config(template_lines, args.period_start, args.period_end)
    
    # === Experiment 1: Keltner Filter (baseline vs enabled) ===
    # A: keltner_enabled = False (baseline)
    keltner_a = list(base_lines)
    keltner_a = replace_config_value(keltner_a, 'Strategy', 'keltner_enabled', 'False')
    keltner_a_path = outdir / 'ab_test_keltner_baseline.ini'
    keltner_a_path.write_text(''.join(keltner_a), encoding='utf-8')
    print(f'生成: {keltner_a_path} (Keltner=False)')
    
    # B: keltner_enabled = True
    keltner_b = list(base_lines)
    keltner_b = replace_config_value(keltner_b, 'Strategy', 'keltner_enabled', 'True')
    keltner_b_path = outdir / 'ab_test_keltner_enabled.ini'
    keltner_b_path.write_text(''.join(keltner_b), encoding='utf-8')
    print(f'生成: {keltner_b_path} (Keltner=True)')
    
    # === Experiment 2: Pyramiding Limit (entry_times 10 vs 3) ===
    # A: entry_times = 10 (baseline)
    pyramid_a = list(base_lines)
    pyramid_a = replace_config_value(pyramid_a, 'RiskManagement', 'entry_times', '10')
    pyramid_a_path = outdir / 'ab_test_pyramid_10.ini'
    pyramid_a_path.write_text(''.join(pyramid_a), encoding='utf-8')
    print(f'生成: {pyramid_a_path} (entry_times=10)')
    
    # B: entry_times = 3
    pyramid_b = list(base_lines)
    pyramid_b = replace_config_value(pyramid_b, 'RiskManagement', 'entry_times', '3')
    pyramid_b_path = outdir / 'ab_test_pyramid_3.ini'
    pyramid_b_path.write_text(''.join(pyramid_b), encoding='utf-8')
    print(f'生成: {pyramid_b_path} (entry_times=3)')
    
    # === Experiment 3: Partial Exit (placeholder for future implementation) ===
    # Note: PARTIAL_EXIT logic is commented out in trading_strategy.py
    # Creating config pairs for when it's enabled
    # A: partial_exit_enabled = False (via comment state - manual toggle needed)
    partial_a = list(base_lines)
    # Add custom section marker for reference
    partial_a.append('\n# Partial Exit: DISABLED (baseline)\n')
    partial_a_path = outdir / 'ab_test_partial_disabled.ini'
    partial_a_path.write_text(''.join(partial_a), encoding='utf-8')
    print(f'生成: {partial_a_path} (Partial Exit未実装=baseline)')
    
    # B: partial_exit_enabled = True (future)
    partial_b = list(base_lines)
    partial_b.append('\n# Partial Exit: TODO - コード実装後に有効化\n')
    partial_b_path = outdir / 'ab_test_partial_enabled.ini'
    partial_b_path.write_text(''.join(partial_b), encoding='utf-8')
    print(f'生成: {partial_b_path} (Partial Exit実装待ち)')
    
    print(f'\nA/B設定ファイル生成完了 (6ファイル) -> {outdir}')
    print('\n実行推奨順序:')
    print('  1. Keltner実験: baseline vs enabled')
    print('  2. Pyramiding実験: 10 vs 3')
    print('  3. Partial Exit実験: コード実装後に再実行')


if __name__ == '__main__':
    main()
