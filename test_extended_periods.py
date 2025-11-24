#!/usr/bin/env python3
"""
Phase 1マーケットレジーム検出の効果比較テスト

期間別バックテスト:
1. Q1 (2025-01-01 ～ 2025-03-31)   - 既存ベースライン
2. Q2 (2025-04-01 ～ 2025-06-30)   - 新規テスト期間
3. Q4初期 (2025-10-01 ～ 2025-11-24 12:00) - 新規テスト期間

目的: Phase 1マーケットレジーム検出がQ1以外の期間でも
     効果的であることを検証
"""

import os
import sys
import json
import subprocess
import shutil
from datetime import datetime
from pathlib import Path

src_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(src_dir)
sys.path.insert(0, os.path.join(src_dir, 'src'))

from src.config_manager import ConfigManager

class ExtendedPeriodBacktestRunner:
    """複数期間のバックテストを実行して結果を比較"""
    
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.output_dir = os.path.join(self.base_dir, 'report')
        self.config_dir = os.path.join(self.base_dir, 'output_configs')
        os.makedirs(self.output_dir, exist_ok=True)
        
        self.periods = {
            'Q1_2025': {
                'label': 'Q1 2025 (Baseline)',
                'start': '2025-01-01',
                'end': '2025-03-31',
                'config_pattern': '_q1.ini'
            },
            'Q2_2025': {
                'label': 'Q2 2025 (Apr-Jun)',
                'start': '2025-04-01',
                'end': '2025-06-30',
                'config_pattern': '_q2.ini'
            },
            'Q4_EARLY_2025': {
                'label': 'Q4 Early 2025 (Oct 1 - Nov 24 12:00)',
                'start': '2025-10-01',
                'end': '2025-11-24',
                'config_pattern': '_q4early.ini'
            }
        }
        
        self.results = {}
    
    def generate_configs(self):
        """
        各期間のバックテストコンフィグを生成
        
        Baseline (No Regime Detection):
        - Donchian + PVO + Keltner チャネル
        - マーケットレジーム検出なし
        
        Adaptive (With Regime Detection - Phase 1):
        - Donchian + PVO + Keltner + マーケットレジーム検出
        - STRONG_TREND時のみエントリーを許可
        """
        ConfigManager.init_config_files(self.base_dir)
        
        template_config = os.path.join(self.config_dir, 'config_baseline_2025-01.ini')
        if not os.path.exists(template_config):
            print(f"❌ Template config not found: {template_config}")
            return False
        
        # 各期間のコンフィグを生成
        for period_key, period_info in self.periods.items():
            # Baselineコンフィグ (Phase 1なし)
            baseline_config = os.path.join(
                self.config_dir,
                f'extended_{period_key}_baseline.ini'
            )
            self._create_config(
                template_config, baseline_config,
                period_info['start'], period_info['end'],
                enable_regime_detection=False
            )
            
            # Adaptiveコンフィグ (Phase 1あり)
            adaptive_config = os.path.join(
                self.config_dir,
                f'extended_{period_key}_adaptive.ini'
            )
            self._create_config(
                template_config, adaptive_config,
                period_info['start'], period_info['end'],
                enable_regime_detection=True
            )
        
        print("✅ Config files generated successfully")
        return True
    
    def _create_config(self, template_path, output_path, start_date, end_date,
                      enable_regime_detection=False):
        """テンプレートから期間別コンフィグを生成"""
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 期間を設定
        content = content.replace(
            'start_date = 2025-01-01',
            f'start_date = {start_date}'
        )
        content = content.replace(
            'end_date = 2025-03-31',
            f'end_date = {end_date}'
        )
        
        # マーケットレジーム検出の有効/無効を設定
        if enable_regime_detection:
            content = content.replace(
                'enable_market_regime_detection = false',
                'enable_market_regime_detection = true'
            )
        else:
            content = content.replace(
                'enable_market_regime_detection = true',
                'enable_market_regime_detection = false'
            )
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def run_backtest(self, config_file, label):
        """単一のバックテストを実行"""
        print(f"\n{'='*70}")
        print(f"🚀 Running Backtest: {label}")
        print(f"   Config: {os.path.basename(config_file)}")
        print(f"{'='*70}")
        
        try:
            # backtest.pyを実行
            result = subprocess.run(
                [sys.executable, os.path.join('src', 'backtest.py'), config_file],
                capture_output=False,
                text=True,
                timeout=3600  # 1時間のタイムアウト
            )
            
            if result.returncode != 0:
                print(f"❌ Backtest failed with return code {result.returncode}")
                return None
            
            # 最新のレポートを取得
            return self._get_latest_report()
        
        except subprocess.TimeoutExpired:
            print(f"❌ Backtest timed out (> 1 hour)")
            return None
        except Exception as e:
            print(f"❌ Error running backtest: {e}")
            return None
    
    def _get_latest_report(self):
        """最新のバックテストレポートを取得"""
        report_dir = os.path.join(self.base_dir, 'report')
        
        # 最新のsummaryファイルを探す
        summary_files = sorted(
            Path(report_dir).glob('backtest_summary_*.json'),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        
        if not summary_files:
            return None
        
        latest_summary = summary_files[0]
        
        try:
            with open(latest_summary, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  Failed to read summary: {e}")
            return None
    
    def run_all_tests(self):
        """すべての期間でバックテストを実行"""
        print("="*70)
        print("📊 Phase 1 Extended Period Backtest Comparison")
        print("="*70)
        print()
        print("Periods to test:")
        for period_key, period_info in self.periods.items():
            print(f"  - {period_info['label']}: {period_info['start']} to {period_info['end']}")
        print()
        
        # コンフィグを生成
        if not self.generate_configs():
            return False
        
        # 各期間でBaselineとAdaptiveを実行
        for period_key, period_info in self.periods.items():
            baseline_config = os.path.join(
                self.config_dir,
                f'extended_{period_key}_baseline.ini'
            )
            adaptive_config = os.path.join(
                self.config_dir,
                f'extended_{period_key}_adaptive.ini'
            )
            
            baseline_label = f"{period_info['label']} - Baseline (No Regime Detection)"
            adaptive_label = f"{period_info['label']} - Adaptive (With Phase 1)"
            
            # Baselineを実行
            baseline_report = self.run_backtest(baseline_config, baseline_label)
            
            # Adaptiveを実行
            adaptive_report = self.run_backtest(adaptive_config, adaptive_label)
            
            # 結果を保存
            self.results[period_key] = {
                'label': period_info['label'],
                'baseline': baseline_report,
                'adaptive': adaptive_report
            }
        
        # 結果を比較・表示
        self._display_comparison_results()
        
        return True
    
    def _display_comparison_results(self):
        """バックテスト結果の比較を表示"""
        print("\n" + "="*70)
        print("📈 Phase 1 Effectiveness Comparison")
        print("="*70)
        
        comparison_data = []
        
        for period_key, result in self.results.items():
            period_label = result['label']
            baseline = result['baseline']
            adaptive = result['adaptive']
            
            if not baseline or not adaptive:
                print(f"\n⚠️  {period_label}: Missing data for comparison")
                continue
            
            # 主要メトリクスを抽出
            baseline_trades = baseline.get('trade_count', 0)
            adaptive_trades = adaptive.get('trade_count', 0)
            
            baseline_pnl = baseline.get('total_pnl', 0)
            adaptive_pnl = adaptive.get('total_pnl', 0)
            
            baseline_win_rate = baseline.get('win_rate', 0)
            adaptive_win_rate = adaptive.get('win_rate', 0)
            
            baseline_profit_factor = baseline.get('profit_factor', 0)
            adaptive_profit_factor = adaptive.get('profit_factor', 0)
            
            # 比較を計算
            trade_reduction = ((baseline_trades - adaptive_trades) / baseline_trades * 100) if baseline_trades > 0 else 0
            pnl_change = ((adaptive_pnl - baseline_pnl) / abs(baseline_pnl) * 100) if baseline_pnl != 0 else 0
            win_rate_change = adaptive_win_rate - baseline_win_rate
            pf_change = adaptive_profit_factor - baseline_profit_factor
            
            comparison_data.append({
                'period': period_label,
                'baseline_trades': baseline_trades,
                'adaptive_trades': adaptive_trades,
                'trade_reduction': trade_reduction,
                'baseline_pnl': baseline_pnl,
                'adaptive_pnl': adaptive_pnl,
                'pnl_change': pnl_change,
                'baseline_win_rate': baseline_win_rate,
                'adaptive_win_rate': adaptive_win_rate,
                'win_rate_change': win_rate_change,
                'baseline_pf': baseline_profit_factor,
                'adaptive_pf': adaptive_profit_factor,
                'pf_change': pf_change
            })
            
            print(f"\n{'='*70}")
            print(f"📊 {period_label}")
            print(f"{'='*70}")
            print(f"\n【Trade Count】")
            print(f"  Baseline (No Regime):  {baseline_trades:3d} trades")
            print(f"  Adaptive (Phase 1):    {adaptive_trades:3d} trades")
            print(f"  → Reduction: {trade_reduction:+.1f}% ({baseline_trades - adaptive_trades:+d} trades)")
            
            print(f"\n【Total PnL (USDT)】")
            print(f"  Baseline (No Regime):  ${baseline_pnl:+.2f}")
            print(f"  Adaptive (Phase 1):    ${adaptive_pnl:+.2f}")
            print(f"  → Change: {pnl_change:+.1f}% (${adaptive_pnl - baseline_pnl:+.2f})")
            
            print(f"\n【Win Rate】")
            print(f"  Baseline (No Regime):  {baseline_win_rate:.1f}%")
            print(f"  Adaptive (Phase 1):    {adaptive_win_rate:.1f}%")
            print(f"  → Change: {win_rate_change:+.1f}pp")
            
            print(f"\n【Profit Factor】")
            print(f"  Baseline (No Regime):  {baseline_profit_factor:.2f}")
            print(f"  Adaptive (Phase 1):    {adaptive_profit_factor:.2f}")
            print(f"  → Change: {pf_change:+.2f}")
        
        # 総括テーブルを表示
        self._display_summary_table(comparison_data)
        
        # 結果をJSONで保存
        self._save_comparison_results(comparison_data)
    
    def _display_summary_table(self, comparison_data):
        """比較結果をテーブル形式で表示"""
        print(f"\n{'='*70}")
        print("📋 Summary Table")
        print(f"{'='*70}\n")
        
        print(f"{'Period':<35} | {'Trade Reduction':<15} | {'PnL Change':<15} | {'WR Change':<12}")
        print("-" * 80)
        
        for row in comparison_data:
            period = row['period'][:32]  # 期間名を32文字以内に制限
            trade_red = f"{row['trade_reduction']:+.1f}%"
            pnl_chg = f"{row['pnl_change']:+.1f}%"
            wr_chg = f"{row['win_rate_change']:+.1f}pp"
            
            print(f"{period:<35} | {trade_red:>14} | {pnl_chg:>14} | {wr_chg:>11}")
    
    def _save_comparison_results(self, comparison_data):
        """比較結果をJSONで保存"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = os.path.join(
            self.output_dir,
            f'phase1_extended_comparison_{timestamp}.json'
        )
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'test_date': datetime.now().isoformat(),
                'test_name': 'Phase 1 Extended Period Effectiveness Comparison',
                'results': comparison_data
            }, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ Results saved to: {output_file}")

def main():
    runner = ExtendedPeriodBacktestRunner()
    success = runner.run_all_tests()
    
    if success:
        print(f"\n{'='*70}")
        print("✅ All tests completed successfully!")
        print(f"{'='*70}\n")
        sys.exit(0)
    else:
        print(f"\n{'='*70}")
        print("❌ Tests completed with errors")
        print(f"{'='*70}\n")
        sys.exit(1)

if __name__ == '__main__':
    main()
