#!/usr/bin/env python3
"""
四半期別バックテスト 実行スケジューラ

2024 Q1～Q4、2025 Q1～Q3 の重要な期間から優先的に実行
実行時間の都合上、以下の優先順序で実行:

優先度 HIGH:
1. 2024 Q1 (ベースライン期間)
2. 2024 Q2/Q3 (ドローダウン期間)
3. 2025 Q1 (新規期間)
4. 2025 Q3 (最近期間)

優先度 MEDIUM (時間に余裕があれば):
5. 2024 Q4
6. 2025 Q2

実行方法:
  python3 quarterly_backtest_scheduler.py --priority high
  python3 quarterly_backtest_scheduler.py --all
"""

import os
import sys
import json
import subprocess
import time
from datetime import datetime

src_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(src_dir)


class QuarterlyBacktestScheduler:
    """四半期バックテスト スケジューラ"""
    
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.work_reports_dir = os.path.join(self.base_dir, 'work_reports')
        
        # 四半期定義（優先度順）
        self.quarters_high = [
            ('2024_Q1', '2024 Q1 (Baseline)'),
            ('2024_Q2', '2024 Q2 (Drawdown)'),
            ('2024_Q3', '2024 Q3 (Drawdown)'),
            ('2025_Q1', '2025 Q1 (New Period)'),
            ('2025_Q3', '2025 Q3 (Recent)'),
        ]
        
        self.quarters_medium = [
            ('2024_Q4', '2024 Q4'),
            ('2025_Q2', '2025 Q2'),
        ]
        
        self.patterns = [
            'baseline_old',   # Phase 1 OFF, stop_range=2.0
            'baseline_new',   # Phase 1 OFF, stop_range=4.0
            'phase1_old',     # Phase 1 ON, stop_range=2.0
            'phase1_new',     # Phase 1 ON, stop_range=4.0
        ]
        
        self.results = {}
    
    def run_backtest(self, quarter_key, pattern_key):
        """バックテストを実行"""
        config_file = os.path.join(
            self.base_dir, 'output_configs',
            f'quarterly_{quarter_key}_{pattern_key}.ini'
        )
        
        if not os.path.exists(config_file):
            print(f"  ⚠️  Config not found: {os.path.basename(config_file)}")
            return None
        
        print(f"  🚀 {pattern_key}...", end='', flush=True)
        
        try:
            # バックテスト実行前に古いレポートをクリア
            import glob
            for report_file in glob.glob(os.path.join(self.base_dir, 'report', '*.json')):
                try:
                    os.remove(report_file)
                except:
                    pass
            
            # backtest.py を実行
            result = subprocess.run(
                [sys.executable, os.path.join('src', 'backtest.py'), config_file],
                capture_output=True,
                text=True,
                timeout=3600  # 1時間
            )
            
            if result.returncode == 0:
                print(" ✅")
                return self._extract_metrics()
            else:
                print(" ❌")
                return None
        
        except subprocess.TimeoutExpired:
            print(" ⏱️")
            return None
        except Exception as e:
            print(f" ❌ {e}")
            return None
    
    def _extract_metrics(self):
        """レポートから主要メトリクスを抽出"""
        try:
            import glob
            
            report_files = sorted(
                glob.glob(os.path.join('report', 'backtest_summary_*.json')),
                key=os.path.getmtime,
                reverse=True
            )
            
            if not report_files:
                return None
            
            with open(report_files[0], 'r', encoding='utf-8') as f:
                report = json.load(f)
            
            # キー名を統一（異なる形式に対応）
            pnl = report.get('total_pnl') or report.get('total_profit_loss') or 0
            trades = report.get('trades') or report.get('total_trades') or 0
            win_rate = report.get('win_rate') or 0
            pf = report.get('profit_factor') or 0
            max_dd = report.get('max_drawdown') or report.get('max_drawdown_percent') or 0
            sharpe = report.get('sharpe') or 0
            recovery = report.get('recovery_period') or -1
            
            return {
                'pnl': float(pnl),
                'trades': int(trades),
                'win_rate': float(win_rate) * 100 if win_rate < 1 else float(win_rate),
                'profit_factor': float(pf),
                'max_drawdown': float(max_dd),
                'sharpe': float(sharpe),
                'recovery_period': int(recovery),
            }
        
        except Exception as e:
            print(f"    ⚠️  Metric extraction error: {e}")
            return None
    
    def run_priority_backtests(self):
        """優先度 HIGH の四半期でバックテストを実行"""
        print("\n" + "="*70)
        print("🧪 QUARTERLY BACKTEST (PRIORITY: HIGH)")
        print("="*70)
        
        total = len(self.quarters_high) * len(self.patterns)
        current = 0
        
        for quarter_key, quarter_label in self.quarters_high:
            print(f"\n📅 {quarter_label}")
            self.results[quarter_key] = {}
            
            for pattern_key in self.patterns:
                current += 1
                print(f"   [{current}/{total}]", end='')
                
                result = self.run_backtest(quarter_key, pattern_key)
                self.results[quarter_key][pattern_key] = result
            
            # 進捗を保存
            self._save_interim_results()
        
        return True
    
    def run_all_backtests(self):
        """すべての四半期でバックテストを実行"""
        print("\n" + "="*70)
        print("🧪 QUARTERLY BACKTEST (ALL)")
        print("="*70)
        
        all_quarters = self.quarters_high + self.quarters_medium
        total = len(all_quarters) * len(self.patterns)
        current = 0
        
        for quarter_key, quarter_label in all_quarters:
            print(f"\n📅 {quarter_label}")
            self.results[quarter_key] = {}
            
            for pattern_key in self.patterns:
                current += 1
                print(f"   [{current}/{total}]", end='')
                
                result = self.run_backtest(quarter_key, pattern_key)
                self.results[quarter_key][pattern_key] = result
            
            # 進捗を保存
            self._save_interim_results()
        
        return True
    
    def _save_interim_results(self):
        """進捗をファイルに保存"""
        os.makedirs(self.work_reports_dir, exist_ok=True)
        
        date_dir = os.path.join(
            self.work_reports_dir,
            datetime.now().strftime("%Y-%m-%d")
        )
        os.makedirs(date_dir, exist_ok=True)
        
        interim_file = os.path.join(
            date_dir,
            'quarterly_backtest_interim.json'
        )
        
        with open(interim_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
    
    def print_summary(self):
        """サマリを表示"""
        print("\n" + "="*90)
        print("📊 Q別バックテスト結果サマリ")
        print("="*90)
        
        # テーブルヘッダ
        print(f"\n{'Quarter':<12} {'Pattern':<20} {'PnL':>12} {'PF':>8} {'Sharpe':>8} {'Win%':>8} {'Trades':>8} {'Max DD':>12} {'Recovery':>10}")
        print("-" * 120)
        
        # 各四半期の結果を表示
        for quarter_key in self.results:
            quarter_results = self.results[quarter_key]
            completed = sum(1 for r in quarter_results.values() if r is not None)
            total = len(quarter_results)
            
            # 四半期ラベル（最初の行だけ表示）
            first_row = True
            for pattern_key in self.patterns:
                result = quarter_results.get(pattern_key)
                
                if result:
                    quarter_label = quarter_key if first_row else ""
                    pnl = result.get('pnl', 0)
                    pf = result.get('profit_factor', 0)
                    sharpe = result.get('sharpe', 0)
                    win_pct = result.get('win_rate', 0)
                    trades = result.get('trades', 0)
                    max_dd = result.get('max_drawdown', 0)
                    recovery = result.get('recovery_period', -1)
                    
                    # 損益の色分け（+は緑、-は赤）
                    pnl_str = f"${pnl:>10.0f}"
                    
                    # 復帰期間の表示
                    recovery_str = f"{recovery}" if recovery >= 0 else "N/A"
                    
                    print(f"{quarter_label:<12} {pattern_key:<20} {pnl_str:>12} {pf:>8.4f} {sharpe:>8.4f} {win_pct:>7.1f}% {trades:>8} {max_dd:>12.2f} {recovery_str:>10}")
                    
                    first_row = False
                else:
                    quarter_label = quarter_key if first_row else ""
                    print(f"{quarter_label:<12} {pattern_key:<20} {'N/A':>12} {'N/A':>8} {'N/A':>8} {'N/A':>8} {'N/A':>8} {'N/A':>12} {'N/A':>10}")
                    first_row = False
            
            print("-" * 120)
        
        # 統計情報を表示
        self._print_statistics()
    
    def _print_statistics(self):
        """統計情報を表示"""
        print("\n【統計分析】\n")
        
        # stop_range の効果を比較
        print("📈 stop_range 修正の影響（baseline_old vs baseline_new）")
        print("-" * 90)
        
        improved_count = 0
        total_count = 0
        total_pnl_delta = 0
        
        for quarter_key in self.results:
            baseline_old = self.results[quarter_key].get('baseline_old')
            baseline_new = self.results[quarter_key].get('baseline_new')
            
            if baseline_old and baseline_new:
                total_count += 1
                pnl_delta = baseline_new['pnl'] - baseline_old['pnl']
                total_pnl_delta += pnl_delta
                
                if pnl_delta > 0:
                    improved_count += 1
                    symbol = "✅"
                else:
                    symbol = "❌"
                
                trade_delta = baseline_new['trades'] - baseline_old['trades']
                wr_delta = baseline_new['win_rate'] - baseline_old['win_rate']
                pf_delta = baseline_new['profit_factor'] - baseline_old['profit_factor']
                
                print(f"{symbol} {quarter_key}")
                print(f"   PnL:        ${baseline_old['pnl']:>10.0f} → ${baseline_new['pnl']:>10.0f} (Δ ${pnl_delta:>8.0f})")
                print(f"   Trades:     {baseline_old['trades']:>10} → {baseline_new['trades']:>10} (Δ {trade_delta:>8})")
                print(f"   Win Rate:   {baseline_old['win_rate']:>9.1f}% → {baseline_new['win_rate']:>9.1f}% (Δ {wr_delta:>7.1f}%)")
                print(f"   PF:         {baseline_old['profit_factor']:>10.4f} → {baseline_new['profit_factor']:>10.4f} (Δ {pf_delta:>8.4f})")
        
        if total_count > 0:
            print(f"\n✅ 改善期間: {improved_count}/{total_count}")
            print(f"   総PnL改善: ${total_pnl_delta:+.0f}")
            print(f"   平均PnL改善: ${total_pnl_delta/total_count:+.0f}")
        
        # Phase 1 の効果を比較
        print("\n\n🎯 Phase 1 の有効性（baseline_old vs phase1_old）")
        print("-" * 90)
        
        phase1_improved = 0
        phase1_total = 0
        
        for quarter_key in self.results:
            baseline_old = self.results[quarter_key].get('baseline_old')
            phase1_old = self.results[quarter_key].get('phase1_old')
            
            if baseline_old and phase1_old:
                phase1_total += 1
                pnl_delta = phase1_old['pnl'] - baseline_old['pnl']
                
                if pnl_delta > 0:
                    phase1_improved += 1
                    symbol = "✅"
                else:
                    symbol = "❌"
                
                print(f"{symbol} {quarter_key}: ${baseline_old['pnl']:>10.0f} → ${phase1_old['pnl']:>10.0f} (Δ ${pnl_delta:>8.0f})")
        
        if phase1_total > 0:
            print(f"\n✅ 改善期間: {phase1_improved}/{phase1_total}")
        
        # 両方改善の効果
        print("\n\n⚡ 両方の改善（baseline_old vs phase1_new）")
        print("-" * 90)
        
        both_improved = 0
        both_total = 0
        total_both_delta = 0
        
        for quarter_key in self.results:
            baseline_old = self.results[quarter_key].get('baseline_old')
            phase1_new = self.results[quarter_key].get('phase1_new')
            
            if baseline_old and phase1_new:
                both_total += 1
                pnl_delta = phase1_new['pnl'] - baseline_old['pnl']
                total_both_delta += pnl_delta
                
                if pnl_delta > 0:
                    both_improved += 1
                    symbol = "✅"
                else:
                    symbol = "❌"
                
                print(f"{symbol} {quarter_key}: ${baseline_old['pnl']:>10.0f} → ${phase1_new['pnl']:>10.0f} (Δ ${pnl_delta:>8.0f})")
        
        if both_total > 0:
            print(f"\n✅ 改善期間: {both_improved}/{both_total}")
            print(f"   総PnL改善: ${total_both_delta:+.0f}")
            print(f"   平均PnL改善: ${total_both_delta/both_total:+.0f}")
    
    def save_final_results(self):
        """最終結果をファイルに保存"""
        os.makedirs(self.work_reports_dir, exist_ok=True)
        
        date_dir = os.path.join(
            self.work_reports_dir,
            datetime.now().strftime("%Y-%m-%d")
        )
        os.makedirs(date_dir, exist_ok=True)
        
        final_file = os.path.join(
            date_dir,
            f'quarterly_backtest_final_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        )
        
        with open(final_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Results saved: {final_file}")


def main():
    """メイン実行"""
    import argparse
    
    parser = argparse.ArgumentParser(description='四半期別バックテスト スケジューラ')
    parser.add_argument('--priority', choices=['high', 'medium', 'all'],
                       default='high', help='実行優先度')
    args = parser.parse_args()
    
    scheduler = QuarterlyBacktestScheduler()
    
    if args.priority == 'high':
        scheduler.run_priority_backtests()
    elif args.priority == 'all':
        scheduler.run_all_backtests()
    
    scheduler.print_summary()
    scheduler.save_final_results()
    
    print("\n✅ Quarterly backtest completed")


if __name__ == '__main__':
    main()
