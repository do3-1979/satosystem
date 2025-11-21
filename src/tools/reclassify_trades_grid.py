#!/usr/bin/env python3
"""Reclassify trend_trades.json with grid search over k1, k2, k3, L parameters.

Reads existing trend_trades_*.json and applies different classification thresholds.
Outputs summary statistics for each parameter combination to find optimal settings.

Usage:
  python src/tools/reclassify_trades_grid.py --input report/trend_trades_20251121092441.json \
      --output report/classification_grid_results.json
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import List, Dict
import itertools


def classify_trade(trade: Dict, k1: float, k2: float, k3: float, L: int = 20) -> str:
    """Classify a single trade based on MFE/MAE vs ATR thresholds.
    
    Args:
        trade: Trade dict with mfe, mae, atr_at_entry, bars_held
        k1: Minimum ATR multiple for initial trend detection
        k2: MFE threshold for TREND classification
        k3: MAE threshold for FALSE_BREAK classification
        L: Minimum bars required for trend (currently not enforced in simple version)
    
    Returns:
        Classification string: 'TREND', 'FALSE_BREAK', or 'NEUTRAL'
    """
    mfe = trade.get('mfe', 0.0)
    mae = trade.get('mae', 0.0)
    atr = trade.get('atr_at_entry', 1.0)
    
    if atr <= 0:
        return 'NEUTRAL'
    
    # Simple classification logic matching bot.py
    if mfe >= atr * k2:
        return 'TREND'
    elif mae >= atr * k3 and mfe < atr * k2:
        return 'FALSE_BREAK'
    else:
        return 'NEUTRAL'


def compute_summary(trades: List[Dict], k1: float, k2: float, k3: float, L: int) -> Dict:
    """Compute summary statistics for given classification parameters.
    
    Returns:
        Dict with classification counts, PnL breakdown, capture ratios, etc.
    """
    classified = []
    for t in trades:
        cls = classify_trade(t, k1, k2, k3, L)
        classified.append({**t, 'classification': cls})
    
    # Aggregate statistics
    class_counts = {}
    class_pnl = {}
    class_capture = {}
    class_loss_cont = {}
    
    for t in classified:
        cls = t['classification']
        class_counts[cls] = class_counts.get(cls, 0) + 1
        class_pnl[cls] = class_pnl.get(cls, 0.0) + t.get('realized_pnl', 0.0)
        
        cap = t.get('capture_ratio', 0.0)
        if cap > 0:
            if cls not in class_capture:
                class_capture[cls] = []
            class_capture[cls].append(cap)
        
        loss_c = t.get('loss_containment_ratio', 0.0)
        if loss_c > 0:
            if cls not in class_loss_cont:
                class_loss_cont[cls] = []
            class_loss_cont[cls].append(loss_c)
    
    # Averages
    avg_capture = {}
    avg_loss_cont = {}
    for cls, vals in class_capture.items():
        avg_capture[cls] = sum(vals) / len(vals) if vals else 0.0
    for cls, vals in class_loss_cont.items():
        avg_loss_cont[cls] = sum(vals) / len(vals) if vals else 0.0
    
    total_pnl = sum(t.get('realized_pnl', 0.0) for t in classified)
    trend_pnl = class_pnl.get('TREND', 0.0)
    false_pnl = class_pnl.get('FALSE_BREAK', 0.0)
    neutral_pnl = class_pnl.get('NEUTRAL', 0.0)
    
    return {
        'k1': k1,
        'k2': k2,
        'k3': k3,
        'L': L,
        'total_trades': len(classified),
        'class_counts': class_counts,
        'class_pnl': class_pnl,
        'total_pnl': total_pnl,
        'trend_pnl_ratio': (trend_pnl / total_pnl) if total_pnl != 0 else 0.0,
        'false_break_pnl_ratio': (false_pnl / total_pnl) if total_pnl != 0 else 0.0,
        'avg_capture_by_class': avg_capture,
        'avg_loss_containment_by_class': avg_loss_cont,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', type=str, required=True, help='Path to trend_trades_*.json')
    ap.add_argument('--output', type=str, required=True, help='Output path for grid results')
    ap.add_argument('--k1-range', type=str, default='1.0,1.5,2.0', help='Comma-separated k1 values')
    ap.add_argument('--k2-range', type=str, default='1.5,2.0,2.5,3.0', help='Comma-separated k2 values')
    ap.add_argument('--k3-range', type=str, default='1.0,1.2,1.5', help='Comma-separated k3 values')
    ap.add_argument('--L-range', type=str, default='20', help='Comma-separated L values (bars)')
    args = ap.parse_args()
    
    input_path = Path(args.input)
    if not input_path.exists():
        raise SystemExit(f'Input file not found: {input_path}')
    
    trades = json.loads(input_path.read_text(encoding='utf-8'))
    print(f'Loaded {len(trades)} trades from {input_path}')
    
    k1_vals = [float(x) for x in args.k1_range.split(',')]
    k2_vals = [float(x) for x in args.k2_range.split(',')]
    k3_vals = [float(x) for x in args.k3_range.split(',')]
    L_vals = [int(x) for x in args.L_range.split(',')]
    
    results = []
    for k1, k2, k3, L in itertools.product(k1_vals, k2_vals, k3_vals, L_vals):
        summary = compute_summary(trades, k1, k2, k3, L)
        results.append(summary)
        print(f'k1={k1} k2={k2} k3={k3} L={L} -> TREND:{summary["class_counts"].get("TREND", 0)} '
              f'FALSE:{summary["class_counts"].get("FALSE_BREAK", 0)} '
              f'NEUTRAL:{summary["class_counts"].get("NEUTRAL", 0)} '
              f'TotalPnL:{summary["total_pnl"]:.2f}')
    
    # Sort by trend_pnl_ratio descending (maximize trend capture)
    results_sorted = sorted(results, key=lambda r: r['trend_pnl_ratio'], reverse=True)
    
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps({
        'grid_results': results_sorted,
        'top_5': results_sorted[:5]
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    
    print(f'\nGrid search complete. Results saved to: {output_path}')
    print('\nTop 5 configurations (by trend_pnl_ratio):')
    for i, r in enumerate(results_sorted[:5], 1):
        print(f'{i}. k1={r["k1"]} k2={r["k2"]} k3={r["k3"]} L={r["L"]} -> '
              f'Trend%:{r["trend_pnl_ratio"]*100:.1f}% '
              f'TrendCount:{r["class_counts"].get("TREND", 0)} '
              f'PnL:{r["total_pnl"]:.2f}')


if __name__ == '__main__':
    main()
