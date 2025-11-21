#!/usr/bin/env python3
"""PnL時系列から月次パフォーマンス集計

Usage:
  python tools/monthly_aggregator.py \
    --input report/pnl_timeseries_20251121123847.json \
    --output report/monthly_performance_2024.json
"""
import argparse
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict


def aggregate_monthly_performance(pnl_data: list, initial_balance: float) -> dict:
    """PnL時系列から月次集計"""
    monthly = defaultdict(lambda: {
        'trades': 0,
        'start_balance': 0,
        'end_balance': 0,
        'monthly_pnl': 0,
        'max_dd': 0,
        'peak_equity': 0,
        'timestamps': []
    })
    
    for entry in pnl_data:
        timestamp = entry.get('timestamp', '')
        if not timestamp:
            continue
        
        # タイムスタンプをパース
        try:
            dt = datetime.strptime(timestamp, '%Y/%m/%d %H:%M')
        except:
            try:
                dt = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
            except:
                continue
        
        year_month = f"{dt.year}-{dt.month:02d}"
        total_pnl = entry.get('total_pnl', 0)
        current_equity = initial_balance + total_pnl
        
        month_data = monthly[year_month]
        
        # 初回エントリ
        if not month_data['timestamps']:
            month_data['start_balance'] = current_equity
            month_data['peak_equity'] = current_equity
        
        month_data['timestamps'].append(timestamp)
        month_data['end_balance'] = current_equity
        
        # ピーク更新
        if current_equity > month_data['peak_equity']:
            month_data['peak_equity'] = current_equity
        
        # DD計算
        dd = month_data['peak_equity'] - current_equity
        if dd > month_data['max_dd']:
            month_data['max_dd'] = dd
        
        # トレード数カウント (total_pnlの変化で推定)
        if len(month_data['timestamps']) > 1:
            prev_idx = pnl_data.index(entry) - 1
            if prev_idx >= 0:
                prev_pnl = pnl_data[prev_idx].get('total_pnl', 0)
                if abs(total_pnl - prev_pnl) > 0.01:
                    month_data['trades'] += 1
    
    # 月次PnL計算
    results = []
    for year_month in sorted(monthly.keys()):
        data = monthly[year_month]
        data['monthly_pnl'] = data['end_balance'] - data['start_balance']
        data['max_dd_rate'] = (data['max_dd'] / data['peak_equity'] * 100) if data['peak_equity'] > 0 else 0
        
        year, month = year_month.split('-')
        results.append({
            'year': int(year),
            'month': int(month),
            'year_month': year_month,
            'monthly_pnl': data['monthly_pnl'],
            'start_balance': data['start_balance'],
            'end_balance': data['end_balance'],
            'max_drawdown': data['max_dd'],
            'max_dd_rate': data['max_dd_rate'],
            'trades_estimate': data['trades']
        })
    
    return results


def main():
    parser = argparse.ArgumentParser(description="PnL時系列から月次パフォーマンス集計")
    parser.add_argument('--input', type=str, required=True, help='PnL時系列JSONパス')
    parser.add_argument('--output', type=str, help='出力JSONパス')
    parser.add_argument('--initial-balance', type=float, default=300.0,
                       help='初期資産 (デフォルト: 300.0)')
    args = parser.parse_args()
    
    # 入力読み込み
    input_path = Path(args.input)
    with open(input_path, 'r', encoding='utf-8') as f:
        pnl_data = json.load(f)
    
    # 月次集計
    monthly_results = aggregate_monthly_performance(pnl_data, args.initial_balance)
    
    # 出力パス設定
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.parent / f"monthly_{input_path.stem}.json"
    
    # JSON出力
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(monthly_results, f, ensure_ascii=False, indent=2)
    
    # コンソール表示
    print(f"月次パフォーマンス集計完了: {output_path}")
    print(f"\n{'年月':<10} {'月次PnL':>12} {'期末残高':>12} {'最大DD':>12} {'DD率':>8}")
    print("-" * 60)
    
    for m in monthly_results:
        year_month = m['year_month']
        pnl = m['monthly_pnl']
        balance = m['end_balance']
        dd = m['max_drawdown']
        dd_rate = m['max_dd_rate']
        
        pnl_indicator = "🟢" if pnl > 0 else "🔴" if pnl < 0 else "⚪"
        
        print(f"{year_month:<10} {pnl_indicator} ${pnl:>10.2f} ${balance:>10.2f} "
              f"${dd:>10.2f} {dd_rate:>6.2f}%")
    
    # サマリ
    total_pnl = sum(m['monthly_pnl'] for m in monthly_results)
    winning_months = len([m for m in monthly_results if m['monthly_pnl'] > 0])
    final_balance = monthly_results[-1]['end_balance'] if monthly_results else args.initial_balance
    
    print("-" * 60)
    print(f"{'合計':<10} ${total_pnl:>10.2f} ${final_balance:>10.2f}")
    print(f"\n勝ち月: {winning_months}/{len(monthly_results)} "
          f"({winning_months/len(monthly_results)*100:.1f}%)")


if __name__ == '__main__':
    main()
