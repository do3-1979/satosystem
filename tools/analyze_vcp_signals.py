"""
VCPシグナル分析ツール

トレードログからVCPシグナルを分析し、VCP戦略単独のパフォーマンスを評価。
既存Donchian戦略との併用効果も検証。

使用方法:
    python3 tools/analyze_vcp_signals.py --year 2025
    python3 tools/analyze_vcp_signals.py --year 2025 --quarter Q1
"""

import json
import glob
import argparse
from datetime import datetime
from collections import defaultdict

def load_trade_logs(pattern='logs/*.json'):
    """トレードログを読み込み"""
    logs = []
    for log_file in glob.glob(pattern):
        try:
            with open(log_file, 'r') as f:
                data = json.load(f)
                if 'trades' in data:
                    logs.extend(data['trades'])
        except Exception as e:
            print(f"⚠️  {log_file} 読み込みエラー: {e}")
    return logs

def filter_logs_by_period(logs, year=None, quarter=None):
    """期間でログをフィルタリング"""
    filtered = []
    for trade in logs:
        if 'entry' not in trade or 'close_time_dt' not in trade['entry']:
            continue
        
        close_time_dt = trade['entry']['close_time_dt']
        # "2025/01/15 12:00" 形式を解析
        try:
            dt = datetime.strptime(close_time_dt[:10], "%Y/%m/%d")
        except:
            continue
        
        if year and dt.year != year:
            continue
        
        if quarter:
            q_num = (dt.month - 1) // 3 + 1
            if f"Q{q_num}" != quarter:
                continue
        
        filtered.append(trade)
    
    return filtered

def analyze_vcp_signals(logs):
    """VCPシグナルを分析"""
    results = {
        'total_trades': len(logs),
        'vcp_signal_count': 0,
        'vcp_buy_signals': 0,
        'vcp_sell_signals': 0,
        'vcp_confidence_distribution': defaultdict(int),
        'vcp_signals_by_quarter': defaultdict(lambda: {'count': 0, 'signals': []}),
        'donchian_only_trades': [],
        'vcp_only_trades': [],
        'both_signal_trades': [],
        'neither_signal_trades': []
    }
    
    for trade in logs:
        if 'entry' not in trade:
            continue
        
        entry = trade['entry']
        vcp_data = entry.get('vcp', {})
        vcp_signal = vcp_data.get('signal', 0)
        vcp_confidence = vcp_data.get('confidence', 0.0)
        vcp_reason = vcp_data.get('reason', '')
        
        donchian_signal = entry.get('signals', {}).get('donchian_signal', False)
        
        # VCPシグナル統計
        if vcp_signal != 0:
            results['vcp_signal_count'] += 1
            if vcp_signal == 1:
                results['vcp_buy_signals'] += 1
            elif vcp_signal == -1:
                results['vcp_sell_signals'] += 1
            
            # 信頼度分布
            conf_bucket = int(vcp_confidence * 10) / 10.0
            results['vcp_confidence_distribution'][conf_bucket] += 1
            
            # 四半期別
            close_time_dt = entry.get('close_time_dt', '')
            if close_time_dt:
                try:
                    dt = datetime.strptime(close_time_dt[:10], "%Y/%m/%d")
                    q_num = (dt.month - 1) // 3 + 1
                    quarter_key = f"{dt.year}-Q{q_num}"
                    results['vcp_signals_by_quarter'][quarter_key]['count'] += 1
                    results['vcp_signals_by_quarter'][quarter_key]['signals'].append({
                        'date': close_time_dt,
                        'signal': vcp_signal,
                        'confidence': vcp_confidence,
                        'reason': vcp_reason
                    })
                except:
                    pass
        
        # シグナル組み合わせ分類
        if donchian_signal and vcp_signal != 0:
            results['both_signal_trades'].append(trade)
        elif donchian_signal and vcp_signal == 0:
            results['donchian_only_trades'].append(trade)
        elif not donchian_signal and vcp_signal != 0:
            results['vcp_only_trades'].append(trade)
        else:
            results['neither_signal_trades'].append(trade)
    
    return results

def calculate_performance(trades):
    """トレードのパフォーマンスを計算"""
    if not trades:
        return {
            'total_trades': 0,
            'wins': 0,
            'losses': 0,
            'win_rate': 0.0,
            'total_pnl': 0.0,
            'avg_pnl': 0.0,
            'profit_factor': 0.0,
            'max_drawdown': 0.0
        }
    
    wins = 0
    losses = 0
    total_pnl = 0.0
    total_profit = 0.0
    total_loss = 0.0
    max_dd = 0.0
    
    for trade in trades:
        if 'result' not in trade:
            continue
        
        result = trade['result']
        pnl = result.get('pnl_usd', 0.0)
        dd = result.get('max_drawdown_usd', 0.0)
        
        total_pnl += pnl
        
        if pnl > 0:
            wins += 1
            total_profit += pnl
        elif pnl < 0:
            losses += 1
            total_loss += abs(pnl)
        
        if dd > max_dd:
            max_dd = dd
    
    total_trades = wins + losses
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0
    avg_pnl = total_pnl / total_trades if total_trades > 0 else 0.0
    profit_factor = (total_profit / total_loss) if total_loss > 0 else (float('inf') if total_profit > 0 else 0.0)
    
    return {
        'total_trades': total_trades,
        'wins': wins,
        'losses': losses,
        'win_rate': win_rate,
        'total_pnl': total_pnl,
        'avg_pnl': avg_pnl,
        'profit_factor': profit_factor,
        'max_drawdown': max_dd
    }

def print_results(results, year=None, quarter=None):
    """結果を表示"""
    period_str = f"{year}" if year else "全期間"
    if quarter:
        period_str += f" {quarter}"
    
    print(f"\n{'='*80}")
    print(f"VCPシグナル分析結果 ({period_str})")
    print(f"{'='*80}")
    
    print(f"\n📊 全体統計:")
    print(f"  - 総トレード数: {results['total_trades']}")
    print(f"  - VCPシグナル発生回数: {results['vcp_signal_count']} ({results['vcp_signal_count']/max(results['total_trades'],1)*100:.1f}%)")
    print(f"    * BUYシグナル: {results['vcp_buy_signals']}")
    print(f"    * SELLシグナル: {results['vcp_sell_signals']}")
    
    print(f"\n📈 VCP信頼度分布:")
    if results['vcp_confidence_distribution']:
        for conf in sorted(results['vcp_confidence_distribution'].keys()):
            count = results['vcp_confidence_distribution'][conf]
            print(f"  - {conf:.1f}-{conf+0.1:.1f}: {count} 回")
    else:
        print(f"  - VCPシグナルなし")
    
    print(f"\n📅 四半期別VCPシグナル:")
    if results['vcp_signals_by_quarter']:
        for quarter_key in sorted(results['vcp_signals_by_quarter'].keys()):
            q_data = results['vcp_signals_by_quarter'][quarter_key]
            print(f"  - {quarter_key}: {q_data['count']} 回")
    else:
        print(f"  - VCPシグナルなし")
    
    print(f"\n🔍 シグナル組み合わせ分析:")
    print(f"  - Donchianのみ: {len(results['donchian_only_trades'])} トレード")
    print(f"  - VCPのみ: {len(results['vcp_only_trades'])} トレード")
    print(f"  - 両方一致: {len(results['both_signal_trades'])} トレード")
    print(f"  - どちらもなし: {len(results['neither_signal_trades'])} トレード")
    
    # パフォーマンス比較
    print(f"\n💰 パフォーマンス比較:")
    
    # Donchianのみ
    donchian_perf = calculate_performance(results['donchian_only_trades'])
    print(f"\n  【Donchianのみ】")
    print(f"    - トレード数: {donchian_perf['total_trades']}")
    print(f"    - 勝率: {donchian_perf['win_rate']:.1f}%")
    print(f"    - 総損益: {donchian_perf['total_pnl']:.2f} USD")
    print(f"    - PF: {donchian_perf['profit_factor']:.2f}")
    
    # VCPのみ
    vcp_perf = calculate_performance(results['vcp_only_trades'])
    print(f"\n  【VCPのみ】")
    print(f"    - トレード数: {vcp_perf['total_trades']}")
    print(f"    - 勝率: {vcp_perf['win_rate']:.1f}%")
    print(f"    - 総損益: {vcp_perf['total_pnl']:.2f} USD")
    print(f"    - PF: {vcp_perf['profit_factor']:.2f}")
    
    # 両方一致
    both_perf = calculate_performance(results['both_signal_trades'])
    print(f"\n  【両方一致】")
    print(f"    - トレード数: {both_perf['total_trades']}")
    print(f"    - 勝率: {both_perf['win_rate']:.1f}%")
    print(f"    - 総損益: {both_perf['total_pnl']:.2f} USD")
    print(f"    - PF: {both_perf['profit_factor']:.2f}")
    
    print(f"\n{'='*80}\n")

def main():
    parser = argparse.ArgumentParser(description='VCPシグナル分析ツール')
    parser.add_argument('--year', type=int, help='分析対象年（例: 2025）')
    parser.add_argument('--quarter', type=str, help='分析対象四半期（例: Q1）')
    parser.add_argument('--logs', type=str, default='logs/*.json', help='ログファイルパターン')
    
    args = parser.parse_args()
    
    # ログ読み込み
    print(f"📂 ログ読み込み中: {args.logs}")
    all_logs = load_trade_logs(args.logs)
    print(f"✅ {len(all_logs)} トレードを読み込みました")
    
    # 期間フィルタリング
    filtered_logs = filter_logs_by_period(all_logs, args.year, args.quarter)
    print(f"✅ フィルタリング後: {len(filtered_logs)} トレード")
    
    # 分析実行
    results = analyze_vcp_signals(filtered_logs)
    
    # 結果表示
    print_results(results, args.year, args.quarter)

if __name__ == '__main__':
    main()
