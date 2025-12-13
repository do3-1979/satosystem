#!/usr/bin/env python3
"""
Phase 22a-22c vs Phase 0 Baseline 比較

複数四半期の簡単な比較スクリプト
4 つの設定で順番にバックテストを実行：
  1. Baseline (指標全OFF)
  2. Strategy A のみ
  3. Strategy B のみ
  4. Strategy C のみ
"""

import os
import sys
import json
import subprocess
import shutil
from datetime import datetime
from configparser import ConfigParser
import glob

WORKSPACE_ROOT = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(WORKSPACE_ROOT, "src")
CONFIG_FILE = os.path.join(SRC_DIR, "config.ini")
RESULTS_DIR = os.path.join(WORKSPACE_ROOT, "docs/quarterly_backtest_results")

def backup_config():
    """config.ini をバックアップ"""
    backup_file = CONFIG_FILE + ".backup_phase22_compare"
    if not os.path.exists(backup_file):
        shutil.copy(CONFIG_FILE, backup_file)
        print(f"✓ Config バックアップ: {backup_file}")

def set_strategy_flags(strategy_a=False, strategy_b=False, strategy_c=False):
    """Strategy フラグを設定"""
    config = ConfigParser()
    config.read(CONFIG_FILE, encoding='utf-8_sig')
    
    if 'Strategy' not in config:
        config.add_section('Strategy')
    
    config['Strategy']['enable_strategy_a_adx'] = '1' if strategy_a else '0'
    config['Strategy']['enable_strategy_b_bb_rsi_sma'] = '1' if strategy_b else '0'
    config['Strategy']['enable_strategy_c_combined'] = '1' if strategy_c else '0'
    
    with open(CONFIG_FILE, 'w', encoding='utf-8_sig') as f:
        config.write(f)

def run_quarterly_backtest():
    """全四半期バックテストを実行し、結果ファイルを返す"""
    try:
        result = subprocess.run(
            ['python', 'run_quarterly_backtest.py'],
            cwd=WORKSPACE_ROOT,
            capture_output=True,
            timeout=7200,
            text=True
        )
        
        output = result.stdout
        
        # "✅ 結果を保存しました: " から ファイルパスを抽出
        for line in output.split('\n'):
            if '✅ 結果を保存しました:' in line:
                json_file = line.split('✅ 結果を保存しました: ')[-1].strip()
                if os.path.exists(json_file):
                    print(f"✓ バックテスト完了: {os.path.basename(json_file)}")
                    return json_file
        
        # 見つからない場合は最新ファイルを探す
        json_files = glob.glob(os.path.join(RESULTS_DIR, 'quarterly_results_*.json'))
        if json_files:
            latest_file = max(json_files, key=os.path.getctime)
            print(f"✓ バックテスト完了: {os.path.basename(latest_file)}")
            return latest_file
        
        return None
        
    except subprocess.TimeoutExpired:
        print(f"❌ バックテスト タイムアウト (7200秒)")
        return None
    except Exception as e:
        print(f"❌ バックテスト実行エラー: {str(e)}")
        return None

def load_results_from_json(json_file):
    """JSON ファイルから結果を抽出"""
    results = {}
    
    if not os.path.exists(json_file):
        return results
    
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if isinstance(data, list):
            for result in data:
                year = result.get('year')
                quarter = result.get('quarter')
                metrics = result.get('metrics', {})
                
                if year and quarter and metrics:
                    quarter_key = f"{year}/Q{quarter}"
                    results[quarter_key] = {
                        'pnl': metrics.get('total_pnl', 0),
                        'win_rate': metrics.get('win_rate', 0),
                        'sharpe': metrics.get('sharpe', 0),
                        'profit_factor': metrics.get('profit_factor', 0),
                        'max_drawdown': metrics.get('max_drawdown', 0)
                    }
    except Exception as e:
        print(f"❌ JSON 解析エラー: {str(e)}")
    
    return results

def compare_all_strategies(baseline_results, strategy_a_results, strategy_b_results, strategy_c_results):
    """すべての戦略を比較"""
    print("\n" + "=" * 130)
    print("【全四半期バックテスト比較】")
    print("=" * 130)
    
    # ヘッダ
    print(f"\n{'Quarter':<12} {'Baseline':>15} {'Strat.A':>15} {'Strat.B':>15} {'Strat.C':>15} {'最良改善':>12}")
    print("-" * 130)
    
    all_quarters = sorted(set(baseline_results.keys()))
    
    totals = {
        'baseline': 0,
        'strat_a': 0,
        'strat_b': 0,
        'strat_c': 0,
        'best_count': [0, 0, 0, 0]  # baseline, a, b, c
    }
    
    for quarter in all_quarters:
        baseline_pnl = baseline_results.get(quarter, {}).get('pnl', 0)
        strat_a_pnl = strategy_a_results.get(quarter, {}).get('pnl', 0)
        strat_b_pnl = strategy_b_results.get(quarter, {}).get('pnl', 0)
        strat_c_pnl = strategy_c_results.get(quarter, {}).get('pnl', 0)
        
        # 最高パフォーマンスを特定
        all_pnls = {
            'baseline': baseline_pnl,
            'strat_a': strat_a_pnl,
            'strat_b': strat_b_pnl,
            'strat_c': strat_c_pnl
        }
        best_strategy = max(all_pnls, key=all_pnls.get)
        best_pnl = all_pnls[best_strategy]
        
        if best_strategy == 'baseline':
            totals['best_count'][0] += 1
        elif best_strategy == 'strat_a':
            totals['best_count'][1] += 1
        elif best_strategy == 'strat_b':
            totals['best_count'][2] += 1
        elif best_strategy == 'strat_c':
            totals['best_count'][3] += 1
        
        # マーク
        mark = '✓' if best_strategy != 'baseline' else '-'
        best_name = {'baseline': 'BL', 'strat_a': 'A', 'strat_b': 'B', 'strat_c': 'C'}[best_strategy]
        
        print(f"{quarter:<12} {baseline_pnl:>15.2f} {strat_a_pnl:>15.2f} {strat_b_pnl:>15.2f} {strat_c_pnl:>15.2f} {best_name:>12}")
        
        totals['baseline'] += baseline_pnl
        totals['strat_a'] += strat_a_pnl
        totals['strat_b'] += strat_b_pnl
        totals['strat_c'] += strat_c_pnl
    
    # 合計
    print("-" * 130)
    print(f"{'【合計】':<12} {totals['baseline']:>15.2f} {totals['strat_a']:>15.2f} {totals['strat_b']:>15.2f} {totals['strat_c']:>15.2f}")
    
    # 改善分析
    print("\n" + "=" * 130)
    print("【改善分析】")
    print("=" * 130)
    
    improvements = {
        'Strategy A': totals['strat_a'] - totals['baseline'],
        'Strategy B': totals['strat_b'] - totals['baseline'],
        'Strategy C': totals['strat_c'] - totals['baseline']
    }
    
    best_improvement_name = max(improvements, key=improvements.get)
    best_improvement_value = improvements[best_improvement_name]
    
    print(f"\nStrategy A: {improvements['Strategy A']:>10.2f} USD ({improvements['Strategy A'] / abs(totals['baseline']) * 100 if totals['baseline'] != 0 else 0:>7.1f}%)")
    print(f"Strategy B: {improvements['Strategy B']:>10.2f} USD ({improvements['Strategy B'] / abs(totals['baseline']) * 100 if totals['baseline'] != 0 else 0:>7.1f}%)")
    print(f"Strategy C: {improvements['Strategy C']:>10.2f} USD ({improvements['Strategy C'] / abs(totals['baseline']) * 100 if totals['baseline'] != 0 else 0:>7.1f}%)")
    
    print(f"\n最高パフォーマンス: {best_improvement_name}")
    print(f"  改善額: {best_improvement_value:.2f} USD")
    print(f"  最高成績Q数: {totals['best_count'][1 if best_improvement_name == 'Strategy A' else (2 if best_improvement_name == 'Strategy B' else 3)]}/{len(all_quarters)}")
    
    return totals, improvements

def save_final_report(baseline_results, strategy_a_results, strategy_b_results, strategy_c_results, totals, improvements):
    """最終レポートを保存"""
    report = {
        'timestamp': datetime.now().isoformat(),
        'baseline_total': totals['baseline'],
        'strategy_a_total': totals['strat_a'],
        'strategy_b_total': totals['strat_b'],
        'strategy_c_total': totals['strat_c'],
        'improvements': improvements,
        'quarterly_results': {
            'baseline': baseline_results,
            'strategy_a': strategy_a_results,
            'strategy_b': strategy_b_results,
            'strategy_c': strategy_c_results
        }
    }
    
    report_file = os.path.join(WORKSPACE_ROOT, 'phase22_final_comparison_report.json')
    
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"\n✓ 最終レポート保存: {report_file}")

def main():
    """メイン処理"""
    print("=" * 130)
    print("Phase 22a-22c 最終効果測定")
    print("=" * 130)
    
    backup_config()
    
    # 4つの設定でテスト
    configs = [
        ('Baseline (指標OFF)', False, False, False),
        ('Strategy A (ADX)', True, False, False),
        ('Strategy B (BB+RSI+SMA)', False, True, False),
        ('Strategy C (統合)', True, True, True),
    ]
    
    all_results = {}
    
    for config_name, a, b, c in configs:
        print(f"\n【{config_name}】")
        set_strategy_flags(strategy_a=a, strategy_b=b, strategy_c=c)
        
        print(f"📊 バックテスト実行中...")
        json_file = run_quarterly_backtest()
        
        if json_file is None:
            print(f"❌ バックテスト失敗")
            return False
        
        results = load_results_from_json(json_file)
        all_results[config_name] = results
        print(f"✓ {len(results)} 四半期のデータを読み込み完了")
    
    # 比較実行
    baseline_results = all_results.get('Baseline (指標OFF)', {})
    strategy_a_results = all_results.get('Strategy A (ADX)', {})
    strategy_b_results = all_results.get('Strategy B (BB+RSI+SMA)', {})
    strategy_c_results = all_results.get('Strategy C (統合)', {})
    
    totals, improvements = compare_all_strategies(baseline_results, strategy_a_results, strategy_b_results, strategy_c_results)
    
    # レポート保存
    save_final_report(baseline_results, strategy_a_results, strategy_b_results, strategy_c_results, totals, improvements)
    
    print(f"\n" + "=" * 130)
    print("【最終結論】")
    print("=" * 130)
    
    best_strategy = max(improvements, key=improvements.get)
    if improvements[best_strategy] > 0:
        print(f"✅ 新指標により PnL が改善されました")
        print(f"   最高パフォーマンス: {best_strategy}")
        print(f"   改善額: {improvements[best_strategy]:.2f} USD")
    else:
        print(f"⚠️  新指標は改善をもたらしていません")
        print(f"   Baseline が最高パフォーマンスです")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
