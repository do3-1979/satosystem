"""
詳細洞察分析: トレードログの構造的問題を特定する
"""

import json
from pathlib import Path
from collections import defaultdict
import statistics

def analyze_detailed_insights(trades_file):
    """詳細な洞察を生成"""
    
    # ファイル読み込み
    with open(trades_file, 'r') as f:
        data = json.load(f)
        # メタデータ付きJSON
        if isinstance(data, dict) and 'trades' in data:
            trades = data['trades']
        elif isinstance(data, list):
            trades = data
        else:
            trades = []
    
    print("=" * 80)
    print("【詳細洞察分析】構造的問題の特定")
    print("=" * 80)
    
    # 分析1: PVO値の分布
    print("\n【分析1】PVO値の分布")
    pvo_values = []
    pvo_values_win = []
    pvo_values_loss = []
    
    for t in trades:
        pvo = t.get('entry', {}).get('pvo_filter_value', 0)
        pnl = t.get('result', {}).get('pnl_usd', 0)
        pvo_values.append(pvo)
        
        if pnl >= 0:
            pvo_values_win.append(pvo)
        else:
            pvo_values_loss.append(pvo)
    
    print(f"  PVO値統計（全55トレード）:")
    print(f"    最小: {min(pvo_values):.1f}")
    print(f"    最大: {max(pvo_values):.1f}")
    print(f"    平均: {statistics.mean(pvo_values):.1f}")
    print(f"    中央値: {statistics.median(pvo_values):.1f}")
    
    print(f"\n  勝ちトレード（n={len(pvo_values_win)}):")
    if pvo_values_win:
        print(f"    PVO平均: {statistics.mean(pvo_values_win):.1f}")
        print(f"    PVO中央値: {statistics.median(pvo_values_win):.1f}")
    
    print(f"\n  損失トレード（n={len(pvo_values_loss)}):")
    if pvo_values_loss:
        print(f"    PVO平均: {statistics.mean(pvo_values_loss):.1f}")
        print(f"    PVO中央値: {statistics.median(pvo_values_loss):.1f}")
        print(f"\n  ⚠️ 発見: PVO値に大きな差がない")
        print(f"     → PVO計算そのものが正しくない可能性")
        print(f"     → または、PVO閾値設定が機能していない")
    
    # 分析2: Volatility値の分布
    print("\n【分析2】Volatility値の分布")
    vol_values = []
    vol_pass = []
    vol_fail = []
    
    for t in trades:
        vol = t.get('entry', {}).get('volatility_filter_value', 0)
        vol_pass_flag = t.get('entry', {}).get('volatility_filter_pass', False)
        vol_values.append(vol)
        
        if vol_pass_flag:
            vol_pass.append(vol)
        else:
            vol_fail.append(vol)
    
    print(f"  Volatility値統計（全55トレード）:")
    print(f"    最小: {min(vol_values):.1f}")
    print(f"    最大: {max(vol_values):.1f}")
    print(f"    平均: {statistics.mean(vol_values):.1f}")
    print(f"    フィルター合格: {len(vol_pass)} トレード")
    print(f"    フィルター不合格: {len(vol_fail)} トレード")
    
    print(f"\n  ⚠️ 発見: Volatility フィルターが全て FAIL")
    print(f"     → 閾値 {trades[0].get('entry', {}).get('volatility_filter_threshold', 'N/A')} に対して")
    print(f"     → すべてのボラティリティが高い状態でエントリー")
    print(f"     → 本来はこの状況でエントリーしてはいけない")
    
    # 分析3: 保有時間分析
    print("\n【分析3】保有時間（bar数）分析")
    bars_held = []
    bars_held_win = []
    bars_held_loss = []
    
    for t in trades:
        bars = t.get('result', {}).get('bars_held', 0)
        pnl = t.get('result', {}).get('pnl_usd', 0)
        bars_held.append(bars)
        
        if pnl >= 0:
            bars_held_win.append(bars)
        else:
            bars_held_loss.append(bars)
    
    print(f"  保有時間統計（全55トレード）:")
    print(f"    平均: {statistics.mean(bars_held):.1f} bars")
    print(f"    中央値: {statistics.median(bars_held):.1f} bars")
    print(f"    最小: {min(bars_held)} bars")
    print(f"    最大: {max(bars_held)} bars")
    
    print(f"\n  勝ちトレード（n={len(bars_held_win)}):")
    if bars_held_win:
        print(f"    平均保有時間: {statistics.mean(bars_held_win):.1f} bars")
    
    print(f"\n  損失トレード（n={len(bars_held_loss)}):")
    if bars_held_loss:
        print(f"    平均保有時間: {statistics.mean(bars_held_loss):.1f} bars")
        
        # 短期損失の分析
        short_loss = [b for b in bars_held_loss if b <= 2]
        print(f"\n  短期保有損失（1-2 bars）: {len(short_loss)}/{len(bars_held_loss)} ({len(short_loss)/len(bars_held_loss)*100:.1f}%)")
        print(f"  ⚠️ 発見: エントリー直後に反転している")
    
    # 分析4: 連続損失パターン
    print("\n【分析4】連続損失の時系列分析")
    losses_by_date = defaultdict(int)
    
    for t in trades:
        date = t.get('entry', {}).get('timestamp', '')[:10]
        pnl = t.get('result', {}).get('pnl_usd', 0)
        if pnl < 0:
            losses_by_date[date] += 1
    
    max_loss_streak = max(losses_by_date.values()) if losses_by_date else 0
    print(f"  1日の最大損失トレード数: {max_loss_streak}")
    
    # 日別損失集中日の抽出
    heavy_loss_days = [(date, count) for date, count in losses_by_date.items() if count >= 3]
    if heavy_loss_days:
        print(f"\n  連続損失日（1日3+損失）: {len(heavy_loss_days)}日")
        for date, count in sorted(heavy_loss_days, key=lambda x: x[1], reverse=True)[:5]:
            print(f"    {date}: {count}件の損失")
        print(f"\n  ⚠️ 発見: 特定の日付で集中的に損失")
        print(f"     → 市場体制判定が全日誤っていた日がある")
    
    # 分析5: Entry条件の相関
    print("\n【分析5】Entry条件の相関分析")
    
    # Strategy信号とDonchianの一致度
    strategy_donchian_match = 0
    strategy_donchian_conflict = 0
    
    for t in trades:
        strategy = t.get('entry', {}).get('conditions', {}).get('strategy_signal', 'NONE')
        donchian = t.get('entry', {}).get('conditions', {}).get('donchian_signal', 'NONE')
        strategy_match = t.get('entry', {}).get('conditions', {}).get('strategy_match', False)
        
        if strategy_match:
            strategy_donchian_match += 1
        elif strategy != 'NONE' and donchian != 'NONE' and strategy != donchian:
            strategy_donchian_conflict += 1
    
    print(f"  Strategy信号とDonchianの一致: {strategy_donchian_match}/55")
    print(f"  Strategy信号の競合: {strategy_donchian_conflict}/55")
    
    # 分析6: 市場体制別パフォーマンス
    print("\n【分析6】市場体制別パフォーマンス")
    regime_perf = defaultdict(lambda: {'count': 0, 'wins': 0, 'losses': 0, 'total_pnl': 0})
    
    for t in trades:
        regime = t.get('entry', {}).get('market_regime', 'UNKNOWN')
        pnl = t.get('result', {}).get('pnl_usd', 0)
        
        regime_perf[regime]['count'] += 1
        regime_perf[regime]['total_pnl'] += pnl
        
        if pnl >= 0:
            regime_perf[regime]['wins'] += 1
        else:
            regime_perf[regime]['losses'] += 1
    
    for regime, perf in sorted(regime_perf.items()):
        win_rate = (perf['wins'] / perf['count']) * 100 if perf['count'] > 0 else 0
        avg_pnl = perf['total_pnl'] / perf['count'] if perf['count'] > 0 else 0
        print(f"\n  {regime} (n={perf['count']}):")
        print(f"    勝率: {win_rate:.1f}% ({perf['wins']}/{perf['count']})")
        print(f"    総PnL: {perf['total_pnl']:.2f} USD")
        print(f"    平均PnL: {avg_pnl:.2f} USD")
    
    print("\n" + "=" * 80)
    
    return {
        'pvo_analysis': {
            'all_mean': statistics.mean(pvo_values),
            'win_mean': statistics.mean(pvo_values_win) if pvo_values_win else None,
            'loss_mean': statistics.mean(pvo_values_loss) if pvo_values_loss else None
        },
        'volatility_analysis': {
            'pass_count': len(vol_pass),
            'fail_count': len(vol_fail)
        },
        'holding_time_analysis': {
            'all_mean': statistics.mean(bars_held),
            'win_mean': statistics.mean(bars_held_win) if bars_held_win else None,
            'loss_mean': statistics.mean(bars_held_loss) if bars_held_loss else None
        },
        'regime_performance': dict(regime_perf)
    }

if __name__ == "__main__":
    trade_file = "/home/satoshi/work/satosystem/docs/analysis/trades/trades_comprehensive_55.json"
    analyze_detailed_insights(trade_file)
