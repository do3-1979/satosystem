#!/usr/bin/env python3
"""
Phase 22a-22c vs Phase 0 Baseline 効果測定

run_quarterly_backtest.py を使用して、
全 Baseline と新指標有効時の PnL を Q ごとに比較します。
"""

import os
import sys
import json
import subprocess
import shutil
import glob
from datetime import datetime
from configparser import ConfigParser

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
    return backup_file

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
    
    status = f"A={strategy_a}, B={strategy_b}, C={strategy_c}"
    print(f"✓ Strategy 設定: {status}")

def run_all_quarters_backtest():
    """全四半期バックテストを実行"""
    try:
        result = subprocess.run(
            ['python', 'run_quarterly_backtest.py'],
            cwd=WORKSPACE_ROOT,
            capture_output=True,
            timeout=3600,
            text=True
        )
        
        print(f"✓ バックテスト実行完了")
        
        # 出力で作成されたファイルを探す
        output = result.stdout
        
        # "✅ 結果を保存しました: " から ファイルパスを抽出
        for line in output.split('\n'):
            if '✅ 結果を保存しました:' in line:
                json_file = line.split('✅ 結果を保存しました: ')[-1].strip()
                if os.path.exists(json_file):
                    return json_file
        
        # 見つからない場合は最新ファイルを探す
        json_files = glob.glob(os.path.join(RESULTS_DIR, 'quarterly_results_*.json'))
        if json_files:
            latest_file = max(json_files, key=os.path.getctime)
            return latest_file
        
        print(f"⚠️  バックテスト結果ファイルが見つかりません")
        return None
        
    except subprocess.TimeoutExpired:
        print(f"❌ バックテスト タイムアウト (3600秒)")
        return None
    except Exception as e:
        print(f"❌ バックテスト実行エラー: {str(e)}")
        return None

def extract_quarterly_results(json_file):
    """バックテスト結果 JSON から Q ごとの PnL を抽出"""
    results = {}
    
    if not os.path.exists(json_file):
        print(f"⚠️  JSON ファイルが見つかりません: {json_file}")
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

def compare_results(baseline_results, new_results):
    """Baseline と新指標の結果を比較"""
    print("\n" + "=" * 100)
    print("【全Q バックテスト比較結果】")
    print("=" * 100)
    
    print(f"\n{'Quarter':<12} {'Baseline PnL':>15} {'新指標 PnL':>15} {'改善':>12} {'改善%':>8} {'Baseline WR':>12} {'新指標 WR':>12}")
    print("-" * 100)
    
    total_baseline = 0
    total_new = 0
    improvement_count = 0
    total_quarters = 0
    
    all_quarters = sorted(set(baseline_results.keys()) | set(new_results.keys()))
    
    for quarter in all_quarters:
        baseline = baseline_results.get(quarter, {})
        new = new_results.get(quarter, {})
        
        baseline_pnl = baseline.get('pnl', 0)
        new_pnl = new.get('pnl', 0)
        improvement = new_pnl - baseline_pnl
        improvement_rate = (improvement / abs(baseline_pnl) * 100) if baseline_pnl != 0 else 0
        
        baseline_wr = baseline.get('win_rate', 0)
        new_wr = new.get('win_rate', 0)
        
        improvement_mark = "📈" if improvement > 0 else ("📉" if improvement < 0 else "→")
        
        print(f"{quarter:<12} {baseline_pnl:>15.2f} {new_pnl:>15.2f} {improvement:>10.2f} {improvement_mark} {improvement_rate:>7.1f}% {baseline_wr:>11.1f}% {new_wr:>11.1f}%")
        
        total_baseline += baseline_pnl
        total_new += new_pnl
        
        if improvement > 0:
            improvement_count += 1
        total_quarters += 1
    
    # 合計
    print("-" * 100)
    total_improvement = total_new - total_baseline
    total_improvement_rate = (total_improvement / abs(total_baseline) * 100) if total_baseline != 0 else 0
    total_mark = "📈" if total_improvement > 0 else ("📉" if total_improvement < 0 else "→")
    
    print(f"{'【合計】':<12} {total_baseline:>15.2f} {total_new:>15.2f} {total_improvement:>10.2f} {total_mark} {total_improvement_rate:>7.1f}%")
    print(f"{'改善Q数':<12} {'-':>15} {'-':>15} {improvement_count}/{total_quarters}")
    print()
    
    return total_improvement, total_improvement_rate, improvement_count, total_quarters

def save_comparison_report(baseline_results, new_results, comparison_metrics):
    """比較結果をファイルに保存"""
    report = {
        'timestamp': datetime.now().isoformat(),
        'baseline': baseline_results,
        'new_indicators_ab': new_results,
        'comparison': {
            'total_improvement': comparison_metrics[0],
            'improvement_rate_percent': comparison_metrics[1],
            'improved_quarters': comparison_metrics[2],
            'total_quarters': comparison_metrics[3]
        }
    }
    
    report_file = os.path.join(WORKSPACE_ROOT, 'docs/quarterly_backtest_results/phase22_vs_baseline.json')
    os.makedirs(os.path.dirname(report_file), exist_ok=True)
    
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"\n✓ 比較レポート保存: {report_file}")

def main():
    """メイン処理"""
    print("=" * 100)
    print("Phase 22a-22c vs Phase 0 Baseline 効果測定")
    print("=" * 100)
    
    # Config バックアップ
    backup_config()
    
    # ===== Phase 0: Baseline =====
    print(f"\n【Phase 0: Baseline テスト実行】")
    print(f"新指標: OFF (すべて無効)")
    set_strategy_flags(strategy_a=False, strategy_b=False, strategy_c=False)
    
    print(f"\n📊 全四半期バックテスト実行中（Phase 0 Baseline）...\n")
    baseline_json = run_all_quarters_backtest()
    
    if baseline_json is None:
        print(f"❌ Baseline バックテスト失敗")
        return False
    
    baseline_results = extract_quarterly_results(baseline_json)
    print(f"✓ Baseline 結果抽出: {len(baseline_results)} 四半期")
    
    # ===== Phase 22: 新指標 A+B =====
    print(f"\n【Phase 22: 新指標テスト実行】")
    print(f"新指標: Strategy A (ADX) + B (BB+RSI+SMA)")
    set_strategy_flags(strategy_a=True, strategy_b=True, strategy_c=False)
    
    print(f"\n📊 全四半期バックテスト実行中（Phase 22 新指標）...\n")
    new_json = run_all_quarters_backtest()
    
    if new_json is None:
        print(f"❌ 新指標 バックテスト失敗")
        return False
    
    new_results = extract_quarterly_results(new_json)
    print(f"✓ 新指標 結果抽出: {len(new_results)} 四半期")
    
    # ===== 比較 =====
    comparison_metrics = compare_results(baseline_results, new_results)
    
    # レポート保存
    save_comparison_report(baseline_results, new_results, comparison_metrics)
    
    # 結論
    total_improvement, improvement_rate, improved_quarters, total_quarters = comparison_metrics
    
    print(f"\n" + "=" * 100)
    print("【結論】")
    print("=" * 100)
    
    if total_improvement > 0:
        print(f"✅ 新指標により PnL が改善されました")
        print(f"   総改善額: {total_improvement:.2f} USD")
        print(f"   改善率: {improvement_rate:.1f}%")
        print(f"   改善Q数: {improved_quarters}/{total_quarters}")
    elif total_improvement < 0:
        print(f"❌ 新指標により PnL が悪化しました")
        print(f"   総悪化額: {abs(total_improvement):.2f} USD")
        print(f"   悪化率: {abs(improvement_rate):.1f}%")
        print(f"   改善Q数: {improved_quarters}/{total_quarters}")
    else:
        print(f"→ 新指標による変化なし")
    
    print(f"\n詳細レポート: {os.path.join(WORKSPACE_ROOT, 'docs/quarterly_backtest_results/phase22_vs_baseline.json')}")
    
    return total_improvement >= 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
