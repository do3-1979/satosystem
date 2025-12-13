#!/usr/bin/env python3
"""
Phase 4: 効果測定（Baseline 比較）

新指標を有効にした各Strategy (A, B, C) と無効時（baseline）のバックテスト結果を比較。
主要指標（損益、勝率、ドローダウン等）を集計。
"""

import sys
sys.path.insert(0, '/home/satoshi/work/satosystem/src')

import json
import subprocess
import os
from datetime import datetime
from config import Config

def run_backtest_with_strategy(strategy_a=False, strategy_b=False, strategy_c=False, config_backup=None):
    """
    指定のStrategyで backtest.py を実行し、結果を取得
    """
    # config.ini をバックアップして設定を変更
    src_dir = '/home/satoshi/work/satosystem/src'
    config_path = os.path.join(src_dir, 'config.ini')
    
    try:
        # 現在の config.ini を読み込み
        import configparser
        config = configparser.ConfigParser()
        config.read(config_path, encoding='utf-8_sig')
        
        # Strategy フラグを設定
        if 'Strategy' not in config:
            config.add_section('Strategy')
        
        config['Strategy']['enable_strategy_a_adx'] = '1' if strategy_a else '0'
        config['Strategy']['enable_strategy_b_bb_rsi_sma'] = '1' if strategy_b else '0'
        config['Strategy']['enable_strategy_c_combined'] = '1' if strategy_c else '0'
        
        # config.ini に書き込み
        with open(config_path, 'w', encoding='utf-8_sig') as f:
            config.write(f)
        
        print(f"✓ Config 設定: A={strategy_a}, B={strategy_b}, C={strategy_c}")
        
        # バックテスト実行
        print(f"📊 バックテスト実行中...")
        result = subprocess.run(
            ['python', 'backtest.py'],
            cwd=src_dir,
            capture_output=True,
            timeout=300,
            text=True
        )
        
        if result.returncode != 0:
            print(f"⚠️ バックテスト終了コード: {result.returncode}")
            if result.stderr:
                print(f"   エラー: {result.stderr[:200]}")
        
        print(f"✓ バックテスト完了")
        
        # 結果ログから指標を抽出
        metrics = _extract_metrics_from_log(result.stdout, result.stderr)
        return metrics
        
    except subprocess.TimeoutExpired:
        print(f"❌ バックテストがタイムアウト（300秒）")
        return None
    except Exception as e:
        print(f"❌ バックテスト実行エラー: {str(e)}")
        return None

def _extract_metrics_from_log(stdout, stderr):
    """
    バックテストログから主要指標を抽出
    """
    metrics = {
        'profit': 0,
        'sharpe': 0,
        'win_rate': 0,
        'trades': 0,
        'max_drawdown': 0,
        'drawdown_rate': 0
    }
    
    try:
        # stdout/stderr から指標を抽出
        combined_log = stdout + '\n' + stderr
        
        for line in combined_log.split('\n'):
            if '最終損益:' in line:
                # 例: "最終損益:   500 [BTC/USD]"
                try:
                    profit_str = line.split('最終損益:')[1].split('[')[0].strip()
                    metrics['profit'] = float(profit_str)
                except:
                    pass
            
            elif 'Sharpe:' in line:
                # 例: "Sharpe: 0.123"
                try:
                    sharpe_str = line.split('Sharpe:')[1].strip().split()[0]
                    metrics['sharpe'] = float(sharpe_str)
                except:
                    pass
            
            elif 'WinRate:' in line:
                # 例: "WinRate: 55.00% Trades: 20"
                try:
                    parts = line.split('WinRate:')[1].split('Trades:')
                    metrics['win_rate'] = float(parts[0].replace('%', '').strip())
                    metrics['trades'] = int(parts[1].strip())
                except:
                    pass
            
            elif '最大ドローダウン:' in line:
                # 例: "最大ドローダウン:  -500.00 [BTC/USD]"
                try:
                    dd_str = line.split('最大ドローダウン:')[1].split('[')[0].strip()
                    metrics['max_drawdown'] = float(dd_str)
                except:
                    pass
            
            elif '最大ドローダウン率:' in line:
                # 例: "最大ドローダウン率:   -5.50 [%]"
                try:
                    dd_rate_str = line.split('最大ドローダウン率:')[1].split('[')[0].strip()
                    metrics['drawdown_rate'] = float(dd_rate_str)
                except:
                    pass
        
        return metrics
    
    except Exception as e:
        print(f"⚠️ 指標抽出エラー: {str(e)}")
        return metrics

def compare_strategies():
    """
    複数のStrategy設定でバックテストを実行し、結果を比較
    """
    print("=" * 70)
    print("Phase 4: 効果測定（Baseline 比較）")
    print("=" * 70)
    
    strategies = [
        {'name': 'Baseline (全指標OFF)', 'a': False, 'b': False, 'c': False},
        {'name': 'Strategy A (ADX)', 'a': True, 'b': False, 'c': False},
        {'name': 'Strategy B (BB+RSI+SMA)', 'a': False, 'b': True, 'c': False},
        {'name': 'Strategy C (Combined)', 'a': False, 'b': False, 'c': True},
        {'name': 'Strategy A+B', 'a': True, 'b': True, 'c': False},
    ]
    
    results = {}
    
    print(f"\n📊 各Strategyでバックテストを実行...")
    for strategy in strategies:
        print(f"\n▶ {strategy['name']}")
        metrics = run_backtest_with_strategy(
            strategy_a=strategy['a'],
            strategy_b=strategy['b'],
            strategy_c=strategy['c']
        )
        
        if metrics:
            results[strategy['name']] = metrics
            print(f"  損益: {metrics['profit']:.2f}")
            print(f"  Sharpe: {metrics['sharpe']:.3f}")
            print(f"  勝率: {metrics['win_rate']:.2f}%")
            print(f"  取引数: {metrics['trades']}")
            print(f"  Max DD: {metrics['max_drawdown']:.2f}")
            print(f"  DD率: {metrics['drawdown_rate']:.2f}%")
        else:
            results[strategy['name']] = None
            print(f"  ❌ バックテスト失敗")
    
    # 結果を比較表示
    print(f"\n" + "=" * 70)
    print("比較結果サマリー")
    print("=" * 70)
    
    baseline_result = results.get('Baseline (全指標OFF)')
    if not baseline_result:
        print("❌ Baseline 結果が取得できません")
        return False
    
    baseline_profit = baseline_result['profit']
    
    print(f"\n{'Strategy':<30} {'損益':>12} {'改善率':>10} {'勝率':>8} {'Sharpe':>8}")
    print("-" * 70)
    
    for strategy_name, metrics in results.items():
        if metrics:
            profit = metrics['profit']
            improvement = ((profit - baseline_profit) / abs(baseline_profit) * 100) if baseline_profit != 0 else 0
            
            baseline_marker = " ◀ Baseline" if strategy_name == 'Baseline (全指標OFF)' else ""
            print(f"{strategy_name:<30} {profit:>12.2f} {improvement:>9.1f}% {metrics['win_rate']:>7.1f}% {metrics['sharpe']:>8.3f}{baseline_marker}")
        else:
            print(f"{strategy_name:<30} {'失敗':>12}")
    
    # 結果をJSONで保存
    output_file = '/home/satoshi/work/satosystem/src/phase4_comparison_results.json'
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n✓ 結果を {output_file} に保存しました")
    except Exception as e:
        print(f"\n⚠️ 結果保存エラー: {str(e)}")
    
    print(f"\n✅ Phase 4 効果測定完了")
    return True

if __name__ == "__main__":
    success = compare_strategies()
    sys.exit(0 if success else 1)
