#!/usr/bin/env python3
"""
2024 Q1～Q4、2025 Q1～Q3 四半期別バックテスト実施
修正したストップロス計算（stop_range調整）の影響を確認

実行パターン:
1. Phase 1 OFF + 修正前ストップ (stop_range=2.0) - ベースライン
2. Phase 1 OFF + 修正後ストップ (stop_range=4.0) - ストップのみ改善
3. Phase 1 ON  + 修正前ストップ (stop_range=2.0) - Phase 1のみ効果
4. Phase 1 ON  + 修正後ストップ (stop_range=4.0) - 両方改善

各四半期: 2024 Q1, Q2, Q3, Q4 / 2025 Q1, Q2, Q3 (計7期間)
"""

import os
import sys
import json
import subprocess
import shutil
import glob
from datetime import datetime
from pathlib import Path
from configparser import ConfigParser

src_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(src_dir)
sys.path.insert(0, os.path.join(src_dir, 'src'))

from src.config_manager import ConfigManager


class QuarterlyBacktestRunner:
    """四半期別バックテスト実施クラス"""
    
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.output_dir = os.path.join(self.base_dir, 'report')
        self.config_dir = os.path.join(self.base_dir, 'output_configs')
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.config_dir, exist_ok=True)
        
        # 四半期定義
        self.quarters = {
            '2024_Q1': {'start': '2024-01-01', 'end': '2024-03-31', 'label': '2024 Q1'},
            '2024_Q2': {'start': '2024-04-01', 'end': '2024-06-30', 'label': '2024 Q2'},
            '2024_Q3': {'start': '2024-07-01', 'end': '2024-09-30', 'label': '2024 Q3'},
            '2024_Q4': {'start': '2024-10-01', 'end': '2024-12-31', 'label': '2024 Q4'},
            '2025_Q1': {'start': '2025-01-01', 'end': '2025-03-31', 'label': '2025 Q1'},
            '2025_Q2': {'start': '2025-04-01', 'end': '2025-06-30', 'label': '2025 Q2'},
            '2025_Q3': {'start': '2025-07-01', 'end': '2025-09-30', 'label': '2025 Q3'},
        }
        
        self.patterns = {
            'baseline_old': {
                'label': 'Baseline (Phase 1 OFF, stop_range=2.0)',
                'regime_detection': False,
                'stop_range': 2.0
            },
            'baseline_new': {
                'label': 'Improved Stop (Phase 1 OFF, stop_range=4.0)',
                'regime_detection': False,
                'stop_range': 4.0
            },
            'phase1_old': {
                'label': 'Phase 1 Only (Phase 1 ON, stop_range=2.0)',
                'regime_detection': True,
                'stop_range': 2.0
            },
            'phase1_new': {
                'label': 'Phase 1 + Stop (Phase 1 ON, stop_range=4.0)',
                'regime_detection': True,
                'stop_range': 4.0
            }
        }
        
        self.results = {}  # {quarter: {pattern: metrics}}
    
    def generate_configs(self):
        """各期間×パターンのコンフィグを生成"""
        print("\n" + "="*70)
        print("📋 Generating Configuration Files")
        print("="*70)
        
        # テンプレートファイルを確認
        template_candidates = [
            'extended_2024_Q1_baseline.ini',
            'phase2_2024_Q1_baseline.ini',
            'test_2025_q1_baseline.ini',
        ]
        
        template_path = None
        for template in template_candidates:
            candidate = os.path.join(self.config_dir, template)
            if os.path.exists(candidate):
                template_path = candidate
                break
        
        if not template_path:
            print("❌ Template config not found")
            return False
        
        print(f"✅ Using template: {os.path.basename(template_path)}")
        
        # 各四半期×パターンでコンフィグを生成
        generated_count = 0
        for quarter_key, quarter_info in self.quarters.items():
            for pattern_key, pattern_info in self.patterns.items():
                config_filename = f"quarterly_{quarter_key}_{pattern_key}.ini"
                config_path = os.path.join(self.config_dir, config_filename)
                
                self._create_config(
                    template_path, config_path,
                    quarter_info['start'], quarter_info['end'],
                    pattern_info['regime_detection'],
                    pattern_info['stop_range']
                )
                generated_count += 1
                print(f"  ✅ {config_filename}")
        
        print(f"\n📝 Total configs generated: {generated_count}")
        return True
    
    def _create_config(self, template_path, output_path, start_date, end_date,
                      regime_detection, stop_range):
        """コンフィグファイルを生成"""
        config = ConfigParser()
        config.read(template_path, encoding='utf-8')
        
        # 期間を設定（形式: YYYY/MM/DD HH:MM）
        start_time = start_date.replace('-', '/') + ' 00:00'
        end_time = end_date.replace('-', '/') + ' 23:59'
        
        # Period セクションに設定
        if not config.has_section('Period'):
            config.add_section('Period')
        config.set('Period', 'start_time', start_time)
        config.set('Period', 'end_time', end_time)
        
        # Backtest セクションに back_test フラグを設定
        if not config.has_section('Backtest'):
            config.add_section('Backtest')
        config.set('Backtest', 'back_test', '1')
        
        # Strategy セクション: Phase 1 (マーケットレジーム検出)を設定
        if not config.has_section('Strategy'):
            config.add_section('Strategy')
        config.set('Strategy', 'regime_detection_enabled', str(regime_detection))
        
        # RiskManagement セクション: stop_range を設定
        if not config.has_section('RiskManagement'):
            config.add_section('RiskManagement')
        config.set('RiskManagement', 'stop_range', str(stop_range))
        
        # ファイルに保存
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            config.write(f)
    
    def run_backtest(self, config_file, quarter_key, pattern_key):
        """バックテストを実行"""
        quarter_info = self.quarters[quarter_key]
        pattern_info = self.patterns[pattern_key]
        
        print(f"\n{'='*70}")
        print(f"🚀 {quarter_info['label']} - {pattern_info['label']}")
        print(f"   Config: {os.path.basename(config_file)}")
        print(f"{'='*70}")
        
        try:
            # backtest.py を実行
            result = subprocess.run(
                [sys.executable, os.path.join('src', 'backtest.py'), config_file],
                capture_output=False,
                text=True,
                timeout=3600  # 1時間
            )
            
            if result.returncode != 0:
                print(f"❌ Backtest failed for {quarter_key} - {pattern_key}")
                return None
            
            # 最新のレポートを取得
            return self._get_latest_report(quarter_key, pattern_key)
        
        except subprocess.TimeoutExpired:
            print(f"⏱️  Backtest timeout for {quarter_key} - {pattern_key}")
            return None
        except Exception as e:
            print(f"❌ Error: {e}")
            return None
    
    def _get_latest_report(self, quarter_key, pattern_key):
        """最新のレポートファイルから結果を抽出"""
        try:
            report_files = sorted(
                glob.glob(os.path.join('report', 'backtest_summary_*.json')),
                key=os.path.getmtime,
                reverse=True
            )
            
            if not report_files:
                print(f"  ⚠️  No report found")
                return None
            
            with open(report_files[0], 'r', encoding='utf-8') as f:
                report = json.load(f)
            
            # メトリクスを抽出
            metrics = {
                'pnl': report.get('total_profit_loss', 0),
                'trades': report.get('total_trades', 0),
                'win_rate': report.get('win_rate', 0),
                'profit_factor': report.get('profit_factor', 0),
                'max_drawdown': report.get('max_drawdown_percent', 0),
                'avg_pnl_per_trade': report.get('average_profit_per_trade', 0),
            }
            
            print(f"  ✅ PnL: ${metrics['pnl']:.2f}")
            print(f"  📊 Trades: {metrics['trades']}, Win Rate: {metrics['win_rate']:.1f}%, PF: {metrics['profit_factor']:.2f}")
            
            return metrics
        
        except Exception as e:
            print(f"  ❌ Error extracting report: {e}")
            return None
    
    def run_all_backtests(self):
        """すべての四半期×パターンでバックテストを実行"""
        print("\n" + "="*70)
        print("🧪 QUARTERLY BACKTEST EXECUTION")
        print("="*70)
        
        # コンフィグを生成
        if not self.generate_configs():
            return False
        
        # バックテストを実行
        total_tests = len(self.quarters) * len(self.patterns)
        current_test = 0
        
        for quarter_key in self.quarters.keys():
            self.results[quarter_key] = {}
            
            for pattern_key in self.patterns.keys():
                current_test += 1
                print(f"\n[{current_test}/{total_tests}]")
                
                config_file = os.path.join(
                    self.config_dir,
                    f"quarterly_{quarter_key}_{pattern_key}.ini"
                )
                
                result = self.run_backtest(config_file, quarter_key, pattern_key)
                self.results[quarter_key][pattern_key] = result
        
        return True
    
    def analyze_results(self):
        """結果を分析"""
        print("\n" + "="*70)
        print("📊 QUARTERLY BACKTEST RESULTS ANALYSIS")
        print("="*70)
        
        # テーブルヘッダ
        print("\n【2024年度結果】")
        self._print_quarterly_summary('2024')
        
        print("\n【2025年度結果】")
        self._print_quarterly_summary('2025')
        
        # 比較分析
        print("\n" + "="*70)
        print("🔍 IMPACT ANALYSIS")
        print("="*70)
        
        self._analyze_stop_range_impact()
        self._analyze_phase1_impact()
        self._analyze_combined_impact()
    
    def _print_quarterly_summary(self, year):
        """四半期ごとのサマリを表示"""
        quarters_to_show = [k for k in self.quarters.keys() if k.startswith(year)]
        
        # ヘッダ
        print(f"\n{'Quarter':<15} {'Pattern':<30} {'PnL':<12} {'Trades':<10} {'Win%':<8} {'PF':<8}")
        print("-" * 85)
        
        for quarter_key in quarters_to_show:
            quarter_label = self.quarters[quarter_key]['label']
            
            for pattern_key in self.patterns.keys():
                pattern_label = self.patterns[pattern_key]['label']
                result = self.results.get(quarter_key, {}).get(pattern_key, {})
                
                if not result:
                    print(f"{quarter_label:<15} {pattern_label:<30} {'N/A':<12}")
                    continue
                
                pnl = result.get('pnl', 0)
                trades = result.get('trades', 0)
                win_rate = result.get('win_rate', 0)
                pf = result.get('profit_factor', 0)
                
                pnl_str = f"${pnl:+.0f}"
                print(f"{quarter_label:<15} {pattern_label:<30} {pnl_str:<12} {trades:<10} {win_rate:<8.1f} {pf:<8.2f}")
    
    def _analyze_stop_range_impact(self):
        """stop_range 修正の影響を分析"""
        print("\n📈 Stop Range Impact (baseline_old → baseline_new)")
        print("-" * 70)
        
        for quarter_key in self.quarters.keys():
            quarter_label = self.quarters[quarter_key]['label']
            old = self.results.get(quarter_key, {}).get('baseline_old', {})
            new = self.results.get(quarter_key, {}).get('baseline_new', {})
            
            if not old or not new:
                continue
            
            pnl_change = new.get('pnl', 0) - old.get('pnl', 0)
            trade_change = new.get('trades', 0) - old.get('trades', 0)
            wr_change = new.get('win_rate', 0) - old.get('win_rate', 0)
            pf_change = new.get('profit_factor', 0) - old.get('profit_factor', 0)
            
            print(f"\n{quarter_label}")
            print(f"  PnL:        ${old['pnl']:+.0f} → ${new['pnl']:+.0f} (Δ ${pnl_change:+.0f})")
            print(f"  Trades:     {old['trades']} → {new['trades']} (Δ {trade_change:+d})")
            print(f"  Win Rate:   {old['win_rate']:.1f}% → {new['win_rate']:.1f}% (Δ {wr_change:+.1f}%)")
            print(f"  Profit Factor: {old['profit_factor']:.2f} → {new['profit_factor']:.2f} (Δ {pf_change:+.2f})")
    
    def _analyze_phase1_impact(self):
        """Phase 1 の影響を分析"""
        print("\n🎯 Phase 1 Impact (baseline_old → phase1_old)")
        print("-" * 70)
        
        for quarter_key in self.quarters.keys():
            quarter_label = self.quarters[quarter_key]['label']
            old = self.results.get(quarter_key, {}).get('baseline_old', {})
            phase1 = self.results.get(quarter_key, {}).get('phase1_old', {})
            
            if not old or not phase1:
                continue
            
            pnl_change = phase1.get('pnl', 0) - old.get('pnl', 0)
            trade_change = phase1.get('trades', 0) - old.get('trades', 0)
            
            print(f"\n{quarter_label}")
            print(f"  PnL:        ${old['pnl']:+.0f} → ${phase1['pnl']:+.0f} (Δ ${pnl_change:+.0f})")
            print(f"  Trades:     {old['trades']} → {phase1['trades']} (Δ {trade_change:+d})")
    
    def _analyze_combined_impact(self):
        """Phase 1 + Stop Range の両方の影響を分析"""
        print("\n⚡ Combined Impact (baseline_old → phase1_new)")
        print("-" * 70)
        
        total_quarters = 0
        improved_quarters = 0
        total_pnl_improvement = 0
        
        for quarter_key in self.quarters.keys():
            quarter_label = self.quarters[quarter_key]['label']
            old = self.results.get(quarter_key, {}).get('baseline_old', {})
            combined = self.results.get(quarter_key, {}).get('phase1_new', {})
            
            if not old or not combined:
                continue
            
            total_quarters += 1
            pnl_change = combined.get('pnl', 0) - old.get('pnl', 0)
            
            if pnl_change > 0:
                improved_quarters += 1
            
            total_pnl_improvement += pnl_change
            
            symbol = "✅" if pnl_change > 0 else "❌"
            print(f"\n{symbol} {quarter_label}")
            print(f"  PnL:        ${old['pnl']:+.0f} → ${combined['pnl']:+.0f} (Δ ${pnl_change:+.0f})")
        
        # サマリ
        if total_quarters > 0:
            improvement_rate = 100 * improved_quarters / total_quarters
            avg_pnl_improvement = total_pnl_improvement / total_quarters
            
            print(f"\n📋 Summary (across {total_quarters} quarters)")
            print(f"  Improved:   {improved_quarters}/{total_quarters} ({improvement_rate:.0f}%)")
            print(f"  Total PnL Improvement: ${total_pnl_improvement:+.0f}")
            print(f"  Average per Quarter:  ${avg_pnl_improvement:+.0f}")
    
    def save_results(self):
        """結果をレポートファイルに保存"""
        print("\n" + "="*70)
        print("💾 Saving Results")
        print("="*70)
        
        # work_reports に日付ディレクトリを作成（docs/README.md ルール）
        work_reports_dir = os.path.join(self.base_dir, 'work_reports')
        os.makedirs(work_reports_dir, exist_ok=True)
        
        date_dir = os.path.join(
            work_reports_dir,
            datetime.now().strftime("%Y-%m-%d")
        )
        os.makedirs(date_dir, exist_ok=True)
        
        # JSON レポートを保存
        report_file = os.path.join(
            date_dir,
            f'quarterly_backtest_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        )
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Results saved: {report_file}")


def main():
    """メイン実行"""
    
    runner = QuarterlyBacktestRunner()
    
    # バックテスト実行
    if runner.run_all_backtests():
        # 結果を分析
        runner.analyze_results()
        
        # 結果を保存
        runner.save_results()
        
        print("\n" + "="*70)
        print("✅ QUARTERLY BACKTEST COMPLETED")
        print("="*70)
    else:
        print("\n❌ QUARTERLY BACKTEST FAILED")
        sys.exit(1)


if __name__ == '__main__':
    main()
