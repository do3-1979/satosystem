#!/usr/bin/env python3
"""
フェーズ2: 損失トレード分類と根本原因分析
ドローダウンが高いトレードから因果関係マトリクスを抽出
"""

import json
import glob
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import statistics

# ログディレクトリ
QUARTERLY_LOGS_DIR = 'logs/quarterly'

def load_latest_trade_logs():
    """最新のQ別ログファイルをすべて読み込む"""
    log_files = glob.glob(f"{QUARTERLY_LOGS_DIR}/Q*_trade_log_*.json")
    
    # 各Qの最新ファイルを取得
    latest_files = {}
    for f in log_files:
        basename = Path(f).name
        prefix = '_'.join(basename.split('_')[:2])
        
        if prefix not in latest_files:
            latest_files[prefix] = f
        else:
            current_timestamp = basename.split('_')[-1].replace('.json', '')
            existing_timestamp = Path(latest_files[prefix]).name.split('_')[-1].replace('.json', '')
            
            if current_timestamp > existing_timestamp:
                latest_files[prefix] = f
    
    # すべてのトレードを収集
    all_trades = []
    for q_prefix, filepath in sorted(latest_files.items()):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                trades = data.get('trades', [])
                
                # Q情報を追加
                for trade in trades:
                    trade['quarter'] = q_prefix
                
                all_trades.extend(trades)
                print(f"✓ {q_prefix}: {len(trades)} トレード")
        except Exception as e:
            print(f"✗ {q_prefix}: エラー - {e}")
    
    return all_trades


def extract_trade_metadata(trade):
    """トレードからメタデータを抽出"""
    entry = trade['entry']
    exit_data = trade['exit']
    result = trade['result']
    
    # フィルター情報
    filters = entry.get('filters', {})
    
    metadata = {
        # 基本情報
        'quarter': trade.get('quarter', 'UNKNOWN'),
        'pnl_usd': result['pnl_usd'],
        'pnl_pct': result['pnl_pct'],
        'max_drawdown_usd': result.get('max_drawdown_usd', 0),
        'side': entry['side'],
        
        # PVO フィルター
        'pvo_pass': filters.get('pvo', {}).get('pass', False),
        'pvo_value': filters.get('pvo', {}).get('value', 0),
        'pvo_threshold': filters.get('pvo', {}).get('threshold', 10),
        
        # ADX フィルター
        'adx_pass': filters.get('adx', {}).get('pass', False),
        'adx_value': filters.get('adx', {}).get('value', 0),
        'adx_threshold': filters.get('adx', {}).get('threshold', 25),
        
        # Volume フィルター
        'volume_pass': filters.get('volume', {}).get('pass', False),
        'volume_value': filters.get('volume', {}).get('value', 0),
        'volume_threshold': filters.get('volume', {}).get('threshold', 0),
        
        # Volatility フィルター
        'volatility_pass': filters.get('volatility', {}).get('pass', False),
        'volatility_value': filters.get('volatility', {}).get('value', 0),
        'volatility_threshold': filters.get('volatility', {}).get('threshold', 1200),
        
        # シグナル情報
        'strategy_signal': entry.get('signals', {}).get('strategy_signal', 'NONE'),
        'donchian_signal': entry.get('signals', {}).get('donchian_signal', False),
        
        # 市場情報
        'market_regime': entry.get('signals', {}).get('market_regime', 'UNKNOWN'),
    }
    
    return metadata


def build_causality_matrix(trades):
    """因果関係マトリクスを構築"""
    print("\n" + "=" * 100)
    print("📊 因果関係マトリクス: フィルター別の成績")
    print("=" * 100)
    
    # PVO フィルター分析
    print("\n【PVO フィルター】")
    print("-" * 80)
    
    pvo_ranges = [
        ('PVO < 50', lambda v: v < 50),
        ('PVO 50-100', lambda v: 50 <= v < 100),
        ('PVO 100-200', lambda v: 100 <= v < 200),
        ('PVO >= 200', lambda v: v >= 200),
    ]
    
    for label, condition in pvo_ranges:
        matching = [t for t in trades if condition(t['pvo_value'])]
        if matching:
            wins = [t for t in matching if t['pnl_usd'] > 0]
            losses = [t for t in matching if t['pnl_usd'] <= 0]
            win_rate = len(wins) / len(matching) * 100
            avg_pnl = statistics.mean([t['pnl_usd'] for t in matching])
            
            print(f"  {label:15s}: {len(matching):3d} トレード | 勝率: {win_rate:5.1f}% | 平均PnL: {avg_pnl:+8.2f} USD | 勝:{len(wins):2d} 負:{len(losses):2d}")
    
    # ADX フィルター分析
    print("\n【ADX フィルター】")
    print("-" * 80)
    
    adx_ranges = [
        ('ADX < 20', lambda v: v < 20),
        ('ADX 20-30', lambda v: 20 <= v < 30),
        ('ADX 30-40', lambda v: 30 <= v < 40),
        ('ADX >= 40', lambda v: v >= 40),
    ]
    
    for label, condition in adx_ranges:
        matching = [t for t in trades if condition(t['adx_value'])]
        if matching:
            wins = [t for t in matching if t['pnl_usd'] > 0]
            losses = [t for t in matching if t['pnl_usd'] <= 0]
            win_rate = len(wins) / len(matching) * 100
            avg_pnl = statistics.mean([t['pnl_usd'] for t in matching])
            
            print(f"  {label:15s}: {len(matching):3d} トレード | 勝率: {win_rate:5.1f}% | 平均PnL: {avg_pnl:+8.2f} USD | 勝:{len(wins):2d} 負:{len(losses):2d}")
    
    # Volatility フィルター分析
    print("\n【Volatility フィルター】")
    print("-" * 80)
    
    volatility_ranges = [
        ('Volatility < 800', lambda v: v < 800),
        ('Volatility 800-1200', lambda v: 800 <= v < 1200),
        ('Volatility 1200-1600', lambda v: 1200 <= v < 1600),
        ('Volatility >= 1600', lambda v: v >= 1600),
    ]
    
    for label, condition in volatility_ranges:
        matching = [t for t in trades if condition(t['volatility_value'])]
        if matching:
            wins = [t for t in matching if t['pnl_usd'] > 0]
            losses = [t for t in matching if t['pnl_usd'] <= 0]
            win_rate = len(wins) / len(matching) * 100
            avg_pnl = statistics.mean([t['pnl_usd'] for t in matching])
            
            print(f"  {label:20s}: {len(matching):3d} トレード | 勝率: {win_rate:5.1f}% | 平均PnL: {avg_pnl:+8.2f} USD | 勝:{len(wins):2d} 負:{len(losses):2d}")
    
    # フィルター組み合わせ分析
    print("\n【フィルター組み合わせ】")
    print("-" * 80)
    
    filter_combinations = [
        ('ALL PASS', lambda t: t['pvo_pass'] and t['adx_pass'] and t['volatility_pass']),
        ('PVO+ADX PASS', lambda t: t['pvo_pass'] and t['adx_pass']),
        ('PVO PASS only', lambda t: t['pvo_pass'] and not t['adx_pass']),
        ('ADX PASS only', lambda t: not t['pvo_pass'] and t['adx_pass']),
        ('ALL FAIL', lambda t: not t['pvo_pass'] and not t['adx_pass']),
    ]
    
    for label, condition in filter_combinations:
        matching = [t for t in trades if condition(t)]
        if matching:
            wins = [t for t in matching if t['pnl_usd'] > 0]
            losses = [t for t in matching if t['pnl_usd'] <= 0]
            win_rate = len(wins) / len(matching) * 100
            avg_pnl = statistics.mean([t['pnl_usd'] for t in matching])
            
            print(f"  {label:20s}: {len(matching):3d} トレード | 勝率: {win_rate:5.1f}% | 平均PnL: {avg_pnl:+8.2f} USD | 勝:{len(wins):2d} 負:{len(losses):2d}")


def analyze_loss_patterns(trades):
    """損失トレードのパターン分析"""
    print("\n" + "=" * 100)
    print("🔴 損失トレード パターン分析")
    print("=" * 100)
    
    # ドローダウンでソート
    losses = [t for t in trades if t['pnl_usd'] < 0]
    losses_sorted = sorted(losses, key=lambda t: t['max_drawdown_usd'])
    
    print(f"\n【損失トレード数】: {len(losses)}/{len(trades)} ({len(losses)/len(trades)*100:.1f}%)")
    print(f"【累積損失】: {sum(t['pnl_usd'] for t in losses):.2f} USD")
    print(f"【平均損失】: {statistics.mean([t['pnl_usd'] for t in losses]):.2f} USD/トレード")
    
    # ワースト10を表示
    print("\n【ワースト10 ドローダウン】")
    print("-" * 100)
    print(f"{'順位':<4} {'四半期':<10} {'PnL (USD)':<12} {'DD (USD)':<12} {'PVO':<8} {'ADX':<8} {'Volatility':<12} {'フィルター'}")
    print("-" * 100)
    
    for i, trade in enumerate(losses_sorted[:10], 1):
        filters_status = f"PVO:{'+' if trade['pvo_pass'] else '-'} ADX:{'+' if trade['adx_pass'] else '-'} VOL:{'+' if trade['volatility_pass'] else '-'}"
        print(f"{i:<4} {trade['quarter']:<10} {trade['pnl_usd']:>10.2f} {trade['max_drawdown_usd']:>10.2f} {trade['pvo_value']:>6.1f} {trade['adx_value']:>6.1f} {trade['volatility_value']:>10.1f} {filters_status}")
    
    # 共通パターン検出
    print("\n【ワースト10の共通パターン】")
    print("-" * 80)
    
    worst10 = losses_sorted[:10]
    
    # PVO分布
    pvo_low = sum(1 for t in worst10 if t['pvo_value'] < 100)
    print(f"  PVO < 100: {pvo_low}/10 ({pvo_low*10}%)")
    
    # ADX分布
    adx_low = sum(1 for t in worst10 if t['adx_value'] < 30)
    print(f"  ADX < 30: {adx_low}/10 ({adx_low*10}%)")
    
    # Volatility分布
    vol_high = sum(1 for t in worst10 if t['volatility_value'] > 1200)
    print(f"  Volatility > 1200: {vol_high}/10 ({vol_high*10}%)")
    
    # フィルター失敗率
    pvo_fail = sum(1 for t in worst10 if not t['pvo_pass'])
    adx_fail = sum(1 for t in worst10 if not t['adx_pass'])
    vol_fail = sum(1 for t in worst10 if not t['volatility_pass'])
    
    print(f"\n  PVO フィルター失敗: {pvo_fail}/10 ({pvo_fail*10}%)")
    print(f"  ADX フィルター失敗: {adx_fail}/10 ({adx_fail*10}%)")
    print(f"  Volatility フィルター失敗: {vol_fail}/10 ({vol_fail*10}%)")


def generate_insights(trades):
    """洞察と対策を生成"""
    print("\n" + "=" * 100)
    print("💡 洞察と対策")
    print("=" * 100)
    
    # PVO分析
    pvo_low_losses = [t for t in trades if t['pvo_value'] < 100 and t['pnl_usd'] < 0]
    pvo_high_wins = [t for t in trades if t['pvo_value'] >= 100 and t['pnl_usd'] > 0]
    
    if pvo_low_losses:
        avg_loss = statistics.mean([t['pnl_usd'] for t in pvo_low_losses])
        print(f"\n【発見1】PVO < 100 で高損失")
        print(f"  損失トレード数: {len(pvo_low_losses)}")
        print(f"  平均損失: {avg_loss:.2f} USD")
        print(f"  💡 対策: PVO閾値を100以上に引き上げる")
    
    # ADX分析
    adx_low_losses = [t for t in trades if t['adx_value'] < 30 and t['pnl_usd'] < 0]
    
    if adx_low_losses:
        avg_loss = statistics.mean([t['pnl_usd'] for t in adx_low_losses])
        print(f"\n【発見2】ADX < 30 で高損失")
        print(f"  損失トレード数: {len(adx_low_losses)}")
        print(f"  平均損失: {avg_loss:.2f} USD")
        print(f"  💡 対策: ADX閾値を30以上に引き上げる、またはADX < 30 時はエントリー禁止")
    
    # Volatility分析
    vol_high_losses = [t for t in trades if t['volatility_value'] > 1200 and t['pnl_usd'] < 0]
    vol_low_wins = [t for t in trades if t['volatility_value'] <= 1200 and t['pnl_usd'] > 0]
    
    if vol_high_losses:
        avg_loss = statistics.mean([t['pnl_usd'] for t in vol_high_losses])
        print(f"\n【発見3】Volatility > 1200 で高損失")
        print(f"  損失トレード数: {len(vol_high_losses)}")
        print(f"  平均損失: {avg_loss:.2f} USD")
        print(f"  💡 対策: Volatilityが1200を超える場合はエントリー禁止")
    
    # 組み合わせパターン
    dangerous_pattern = [
        t for t in trades 
        if t['pvo_value'] < 100 and t['adx_value'] < 30 and t['volatility_value'] > 1200 and t['pnl_usd'] < 0
    ]
    
    if dangerous_pattern:
        avg_loss = statistics.mean([t['pnl_usd'] for t in dangerous_pattern])
        print(f"\n【発見4】危険な組み合わせパターン")
        print(f"  条件: PVO < 100 AND ADX < 30 AND Volatility > 1200")
        print(f"  損失トレード数: {len(dangerous_pattern)}")
        print(f"  平均損失: {avg_loss:.2f} USD")
        print(f"  💡 対策: この組み合わせが発生した場合は強制的にエントリー禁止")


def main():
    print("\n" + "=" * 100)
    print("🔍 フェーズ2: 損失トレード分類と根本原因分析")
    print("=" * 100)
    
    # トレードログをロード
    print(f"\n📂 Q別ログファイルを読み込み中...")
    trades_raw = load_latest_trade_logs()
    
    if not trades_raw:
        print("❌ エラー: トレードログが見つかりません")
        return
    
    print(f"\n✅ 合計 {len(trades_raw)} トレードを読み込みました")
    
    # メタデータ抽出
    print(f"\n📊 メタデータを抽出中...")
    trades = [extract_trade_metadata(t) for t in trades_raw]
    
    # 基本統計
    wins = [t for t in trades if t['pnl_usd'] > 0]
    losses = [t for t in trades if t['pnl_usd'] <= 0]
    
    print(f"\n【基本統計】")
    print(f"  総トレード数: {len(trades)}")
    print(f"  勝利: {len(wins)} ({len(wins)/len(trades)*100:.1f}%)")
    print(f"  損失: {len(losses)} ({len(losses)/len(trades)*100:.1f}%)")
    print(f"  総PnL: {sum(t['pnl_usd'] for t in trades):.2f} USD")
    print(f"  平均PnL: {statistics.mean([t['pnl_usd'] for t in trades]):.2f} USD")
    
    # 因果関係マトリクス構築
    build_causality_matrix(trades)
    
    # 損失パターン分析
    analyze_loss_patterns(trades)
    
    # 洞察生成
    generate_insights(trades)
    
    print("\n" + "=" * 100)
    print("✅ フェーズ2分析が完了しました")
    print("=" * 100)


if __name__ == '__main__':
    main()
