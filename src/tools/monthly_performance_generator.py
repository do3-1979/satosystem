#!/usr/bin/env python3
import json, sys, os
from datetime import datetime
from collections import defaultdict

def load_pnl_timeseries(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def month_key(dt_str):
    # dt_str format: YYYY/MM/DD HH:MM
    dt = datetime.strptime(dt_str, '%Y/%m/%d %H:%M')
    return dt.strftime('%Y-%m')

def compute_monthly_metrics(data):
    bars = data['bars']
    monthly = defaultdict(list)
    for b in bars:
        # Ignore the synthetic first epoch line if year not 2024
        t = b['time']
        if not t.startswith('2024/'):  # target year
            continue
        mk = month_key(t)
        monthly[mk].append(b)
    results = {}
    for mk, blist in sorted(monthly.items()):
        if not blist:
            continue
        # Sort by time (already in order) and extract pnl series
        pnls = [b['pnl'] for b in blist]
        start_pnl = pnls[0]
        end_pnl = pnls[-1]
        pnl_change = end_pnl - start_pnl
        # Max drawdown within month
        peak = pnls[0]
        max_dd = 0.0
        for p in pnls:
            if p > peak:
                peak = p
            dd = peak - p
            if dd > max_dd:
                max_dd = dd
        # Simple volatility proxy: (max - min)
        month_range = max(pnls) - min(pnls)
        results[mk] = {
            'start_pnl': round(start_pnl, 6),
            'end_pnl': round(end_pnl, 6),
            'pnl_change': round(pnl_change, 6),
            'max_drawdown_in_month': round(max_dd, 6),
            'range_in_month': round(month_range, 6),
            'bar_count': len(blist)
        }
    return results

def main():
    if len(sys.argv) < 3:
        print('Usage: monthly_performance_generator.py <pnl_timeseries_json> <output_json>')
        sys.exit(1)
    src = sys.argv[1]
    out = sys.argv[2]
    data = load_pnl_timeseries(src)
    monthly = compute_monthly_metrics(data)
    out_obj = {
        'source': os.path.basename(src),
        'generated_at': datetime.utcnow().isoformat(),
        'year': 2024,
        'months': monthly
    }
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(out_obj, f, ensure_ascii=False, indent=2)
    print(f'Wrote monthly metrics -> {out}')

if __name__ == '__main__':
    main()
