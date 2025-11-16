"""
PnL Time Series Reporter

Generates PnL (Profit & Loss) time series exports in CSV and JSON formats.
Supports granularity levels: per-minute (bar) and per-day (daily).

Functions:
    generate_pnl_timeseries(price_data_mgmt, pnl_history, trade_data_list, output_dir)
        -> (csv_path, json_path)
"""
import os
import json
import csv
from datetime import datetime
from typing import List, Dict, Optional, Tuple


def _resample_pnl_daily(pnl_bar_data: List[Dict]) -> List[Dict]:
    """
    Resample bar-level PnL data to daily candles.
    Returns: list of {'date': YYYY-MM-DD, 'open': float, 'high': float, 'low': float, 'close': float}
    """
    if not pnl_bar_data:
        return []
    
    daily = {}
    for item in pnl_bar_data:
        date_key = item['time'][:10]  # YYYY-MM-DD
        pnl_val = item['pnl']
        
        if date_key not in daily:
            daily[date_key] = {
                'date': date_key,
                'open': pnl_val,
                'high': pnl_val,
                'low': pnl_val,
                'close': pnl_val,
                'bar_count': 1
            }
        else:
            daily[date_key]['high'] = max(daily[date_key]['high'], pnl_val)
            daily[date_key]['low'] = min(daily[date_key]['low'], pnl_val)
            daily[date_key]['close'] = pnl_val
            daily[date_key]['bar_count'] += 1
    
    return sorted(daily.values(), key=lambda x: x['date'])


def generate_pnl_timeseries(
    pnl_history: List[float],
    close_times: List[str],
    output_dir: str,
    prefix: str = "pnl_timeseries"
) -> Tuple[str, str]:
    """
    Generate PnL time series in CSV and JSON formats.
    
    Args:
        pnl_history: List of cumulative PnL values (one per bar)
        close_times: List of close timestamps in format 'YYYY-MM-DD HH:MM:SS'
        output_dir: Directory to save output files
        prefix: Filename prefix (default: 'pnl_timeseries')
    
    Returns:
        (csv_path, json_path) tuple of output file paths
    """
    if not pnl_history or not close_times:
        return "", ""
    
    if len(pnl_history) != len(close_times):
        raise ValueError(f"pnl_history and close_times must have same length: {len(pnl_history)} vs {len(close_times)}")
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Timestamp for filename
    ts = datetime.now().strftime('%Y%m%d%H%M%S')
    csv_path = os.path.join(output_dir, f"{prefix}_{ts}.csv")
    json_path = os.path.join(output_dir, f"{prefix}_{ts}.json")
    
    # Build bar-level data
    pnl_bar_data = []
    for i, (pnl, close_time) in enumerate(zip(pnl_history, close_times)):
        pnl_bar_data.append({
            'bar_number': i + 1,
            'time': close_time,
            'pnl': round(pnl, 6),
            'pnl_change': round(pnl - pnl_history[i-1], 6) if i > 0 else 0.0
        })
    
    # Resample to daily
    pnl_daily_data = _resample_pnl_daily(pnl_bar_data)
    
    # Export CSV (bar-level)
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['bar_number', 'time', 'pnl', 'pnl_change'])
        writer.writeheader()
        writer.writerows(pnl_bar_data)
    
    # Export JSON (bar-level + daily summary)
    json_data = {
        'metadata': {
            'generated_at': datetime.now().isoformat(),
            'bar_count': len(pnl_bar_data),
            'daily_count': len(pnl_daily_data),
            'start_time': close_times[0],
            'end_time': close_times[-1],
            'final_pnl': pnl_history[-1],
            'max_pnl': max(pnl_history),
            'min_pnl': min(pnl_history)
        },
        'bars': pnl_bar_data,
        'daily_summary': pnl_daily_data
    }
    
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    
    return csv_path, json_path


if __name__ == "__main__":
    # Simple self-test
    pnl_hist = [0, 10, 5, 15, 12, 25, 20, 30, 28, 35]
    times = [
        '2025-11-01 10:00:00', '2025-11-01 10:01:00', '2025-11-01 10:02:00',
        '2025-11-01 10:03:00', '2025-11-01 10:04:00', '2025-11-02 10:00:00',
        '2025-11-02 10:01:00', '2025-11-02 10:02:00', '2025-11-02 10:03:00',
        '2025-11-02 10:04:00'
    ]
    
    csv_p, json_p = generate_pnl_timeseries(pnl_hist, times, ".", prefix="test_pnl")
    print(f"CSV: {csv_p}")
    print(f"JSON: {json_p}")
    print("✓ Test passed")
