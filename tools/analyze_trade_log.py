"""
トレードログ分析スクリプト

TradeLogger が出力した JSON トレードログを分析します
これが新しい分析パイプラインのベースになります
"""

import json
import sys
from pathlib import Path
from typing import List, Dict

def load_trade_log(filepath: str) -> Dict:
    """トレードログ JSON を読み込む"""
    with open(filepath, 'r') as f:
        return json.load(f)

def analyze_trade_log(trade_log: Dict) -> Dict:
    """トレードログを分析"""
    
    trades = trade_log.get('trades', [])
    metadata = trade_log.get('metadata', {})
    
    print("=" * 80)
    print("【トレードログ分析結果】")
    print("=" * 80)
    
    print(f"\n【基本情報】")
    print(f"  生成日時: {metadata.get('generated_at')}")
    print(f"  総トレード数: {metadata.get('total_trades')}")
    print(f"  完了トレード数: {metadata.get('completed_trades')}")
    
    # フィルター別集計
    print(f"\n【フィルター統計】")
    
    pvo_pass = sum(1 for t in trades if t.get('entry', {}).get('filters', {}).get('pvo', {}).get('pass', False))
    pvo_fail = len(trades) - pvo_pass
    print(f"  PVO フィルター: {pvo_pass} 合格 / {pvo_fail} 不合格")
    
    adx_pass = sum(1 for t in trades if t.get('entry', {}).get('filters', {}).get('adx', {}).get('pass', False))
    adx_fail = len(trades) - adx_pass
    print(f"  ADX フィルター: {adx_pass} 合格 / {adx_fail} 不合格")
    
    vol_pass = sum(1 for t in trades if t.get('entry', {}).get('filters', {}).get('volume', {}).get('pass', False))
    vol_fail = len(trades) - vol_pass
    print(f"  Volume フィルター: {vol_pass} 合格 / {vol_fail} 不合格")
    
    vola_pass = sum(1 for t in trades if t.get('entry', {}).get('filters', {}).get('volatility', {}).get('pass', False))
    vola_fail = len(trades) - vola_pass
    print(f"  Volatility フィルター: {vola_pass} 合格 / {vola_fail} 不合格")
    
    # 市場体制別
    print(f"\n【市場体制別統計】")
    regimes = {}
    for t in trades:
        regime = t.get('entry', {}).get('market', {}).get('regime', 'UNKNOWN')
        if regime not in regimes:
            regimes[regime] = 0
        regimes[regime] += 1
    
    for regime, count in sorted(regimes.items()):
        print(f"  {regime}: {count} トレード ({count/len(trades)*100:.1f}%)")
    
    # 結果統計
    print(f"\n【パフォーマンス統計】")
    
    pnls = [t.get('result', {}).get('pnl_usd', 0) for t in trades if t.get('result') is not None]
    wins = sum(1 for p in pnls if p >= 0)
    losses = len(pnls) - wins
    
    print(f"  勝利: {wins} トレード ({wins/len(pnls)*100:.1f}%)")
    print(f"  損失: {losses} トレード ({losses/len(pnls)*100:.1f}%)")
    print(f"  総 PnL: {sum(pnls):.2f} USD")
    print(f"  平均 PnL: {sum(pnls)/len(pnls) if pnls else 0:.2f} USD")
    
    # エントリー信号別
    print(f"\n【エントリー信号別統計】")
    signals = {}
    for t in trades:
        sig = t.get('entry', {}).get('signals', {}).get('strategy_signal', 'NONE')
        if sig not in signals:
            signals[sig] = []
        signals[sig].append(t.get('result', {}).get('pnl_usd', 0))
    
    for sig, pnls_list in sorted(signals.items()):
        win_count = sum(1 for p in pnls_list if p >= 0)
        print(f"  {sig}: {len(pnls_list)} トレード, {win_count} 勝 ({win_count/len(pnls_list)*100:.1f}%), {sum(pnls_list):.2f} USD")
    
    print(f"\n【フィルター効果分析】")
    
    # PVO による分類
    pvo_pass_pnls = [t.get('result', {}).get('pnl_usd', 0) for t in trades if t.get('entry', {}).get('filters', {}).get('pvo', {}).get('pass', False) and t.get('result') is not None]
    pvo_fail_pnls = [t.get('result', {}).get('pnl_usd', 0) for t in trades if not t.get('entry', {}).get('filters', {}).get('pvo', {}).get('pass', False) and t.get('result') is not None]
    
    if pvo_pass_pnls:
        pvo_pass_win = sum(1 for p in pvo_pass_pnls if p >= 0)
        print(f"\n  PVO PASS ({len(pvo_pass_pnls)} trades):")
        print(f"    勝率: {pvo_pass_win/len(pvo_pass_pnls)*100:.1f}%")
        print(f"    平均 PnL: {sum(pvo_pass_pnls)/len(pvo_pass_pnls):.2f} USD")
        print(f"    総 PnL: {sum(pvo_pass_pnls):.2f} USD")
    
    if pvo_fail_pnls:
        pvo_fail_win = sum(1 for p in pvo_fail_pnls if p >= 0)
        print(f"\n  PVO FAIL ({len(pvo_fail_pnls)} trades):")
        print(f"    勝率: {pvo_fail_win/len(pvo_fail_pnls)*100:.1f}%")
        print(f"    平均 PnL: {sum(pvo_fail_pnls)/len(pvo_fail_pnls):.2f} USD")
        print(f"    総 PnL: {sum(pvo_fail_pnls):.2f} USD")
    
    print("\n" + "=" * 80)
    
    return {
        'metadata': metadata,
        'total_trades': len(trades),
        'completed_trades': metadata.get('completed_trades', 0),
        'wins': wins,
        'losses': losses,
        'win_rate': (wins / len(pnls) * 100) if pnls else 0,
        'total_pnl': sum(pnls),
        'avg_pnl': sum(pnls) / len(pnls) if pnls else 0
    }

if __name__ == "__main__":
    # デフォルトのログファイル
    default_file = "/home/satoshi/work/satosystem/logs/trade_log_20260105082010.json"
    
    filepath = sys.argv[1] if len(sys.argv) > 1 else default_file
    
    if not Path(filepath).exists():
        print(f"Error: {filepath} not found")
        sys.exit(1)
    
    print(f"📖 トレードログ読み込み: {filepath}\n")
    
    trade_log = load_trade_log(filepath)
    results = analyze_trade_log(trade_log)
    
    # 結果を JSON で保存
    output_file = filepath.replace('trade_log_', 'trade_log_analysis_')
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"✓ 分析結果保存: {output_file}")
