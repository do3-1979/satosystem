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
import glob
from datetime import datetime
from pathlib import Path

# Path utilities をインポート
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
from path_utils import PathManager


class QuarterlyBacktestScheduler:
    """四半期バックテスト スケジューラ"""
    
    def __init__(self):
        self.project_root = PathManager.get_project_root()
        self.work_reports_dir = PathManager.get_work_reports_dir()
        
        # 四半期定義（優先度順）
        self.quarters_high = [
            ('2024_Q1', '2024 Q1 (Baseline)', '2024-01-01', '2024-03-31'),
            ('2024_Q2', '2024 Q2 (Drawdown)', '2024-04-01', '2024-06-30'),
            ('2024_Q3', '2024 Q3 (Drawdown)', '2024-07-01', '2024-09-30'),
            ('2025_Q1', '2025 Q1 (New Period)', '2025-01-01', '2025-03-31'),
            ('2025_Q3', '2025 Q3 (Recent)', '2025-07-01', '2025-09-30'),
        ]
        
        self.quarters_medium = [
            ('2024_Q4', '2024 Q4', '2024-10-01', '2024-12-31'),
            ('2025_Q2', '2025 Q2', '2025-04-01', '2025-06-30'),
        ]
        
        # Task 17 以降は単一パターン（現在の config 設定）でテスト
        self.patterns = [
            'current',   # Phase 1 ON, Phase 2 ON (Task 17以降の本番設定)
        ]
        
        self.results = {}
    
    def run_backtest(self, quarter_key, quarter_label, start_date, end_date, pattern_key):
        """バックテストを実行"""
        # Task 17 以降は config.ini を直接使用
        if pattern_key == 'current':
            config_file = self.project_root / 'src' / 'config.ini'
        else:
            config_file = self.project_root / 'output_configs' / f'quarterly_{quarter_key}_{pattern_key}.ini'
        
        if not config_file.exists():
            print(f"  ⚠️  Config not found: {config_file.name}")
            return None
        
        # 一時的に config.ini を修正して期間を設定
        temp_config = self._create_temp_config(config_file, start_date, end_date)
        
        print(f"  🚀 {start_date} to {end_date}...", end='', flush=True)
        
        try:
            # バックテスト実行前に古いレポートをクリア
            report_dir = PathManager.get_report_dir()
            for report_file in report_dir.glob('*.json'):
                try:
                    report_file.unlink()
                except:
                    pass
            
            # backtest.py を実行（修正した期間設定で）
            result = subprocess.run(
                [sys.executable, str(self.project_root / 'src' / 'backtest.py'), str(temp_config)],
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
        """レポートから主要メトリクスを抽出"""
        try:
            report_dir = PathManager.get_report_dir()
            
            report_files = sorted(
                report_dir.glob('backtest_summary_*.json'),
                key=lambda x: x.stat().st_mtime,
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
    
    def _create_temp_config(self, base_config, start_date, end_date):
        """期間設定を変更した一時的な config ファイルを作成"""
        from configparser import ConfigParser
        
        # ベース config を読み込み
        cfg = ConfigParser()
        cfg.read(base_config)
        
        # 期間設定を更新
        if not cfg.has_section('Period'):
            cfg.add_section('Period')
        
        cfg.set('Period', 'start_time', f'{start_date} 0:00')
        cfg.set('Period', 'end_time', f'{end_date} 23:59')
        
        # 一時ファイルに保存
        temp_config = self.project_root / 'src' / f'config_temp_{start_date.replace("-", "")}.ini'
        
        with open(temp_config, 'w', encoding='utf-8') as f:
            cfg.write(f)
        
        return temp_config
    
    def run_priority_backtests(self):
        """優先度 HIGH の四半期でバックテストを実行"""
        print("\n" + "="*70)
        print("🧪 QUARTERLY BACKTEST (PRIORITY: HIGH)")
        print("="*70)
        
        total = len(self.quarters_high) * len(self.patterns)
        current = 0
        
        for quarter_key, quarter_label, start_date, end_date in self.quarters_high:
            print(f"\n📅 {quarter_label}")
            self.results[quarter_key] = {}
            
            for pattern_key in self.patterns:
                current += 1
                print(f"   [{current}/{total}]", end='')
                
                result = self.run_backtest(quarter_key, quarter_label, start_date, end_date, pattern_key)
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
        
        for quarter_key, quarter_label, start_date, end_date in all_quarters:
            print(f"\n📅 {quarter_label}")
            self.results[quarter_key] = {}
            
            for pattern_key in self.patterns:
                current += 1
                print(f"   [{current}/{total}]", end='')
                
                result = self.run_backtest(quarter_key, quarter_label, start_date, end_date, pattern_key)
                self.results[quarter_key][pattern_key] = result
            
            # 進捗を保存
            self._save_interim_results()
        
        return True
    
    def _save_interim_results(self):
        """進捗をファイルに保存"""
        PathManager.ensure_dir_exists(self.work_reports_dir)
        
        date_dir = self.work_reports_dir / datetime.now().strftime("%Y-%m-%d")
        PathManager.ensure_dir_exists(date_dir)
        
        interim_file = date_dir / 'quarterly_backtest_interim.json'
        
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
        
        # Task 17 以降: 本番設定 (Phase 1 ON + Phase 2 ON) のパフォーマンス
        print("📊 現在の設定（Phase 1 ON + Phase 2 ON）のパフォーマンス分析")
        print("-" * 90)
        
        total_count = 0
        total_pnl = 0
        total_trades = 0
        total_wins = 0
        avg_pf = 0
        avg_sharpe = 0
        
        for quarter_key in self.results:
            current_result = self.results[quarter_key].get('current')
            
            if current_result:
                total_count += 1
                pnl = current_result['pnl']
                trades = current_result['trades']
                win_rate = current_result['win_rate']
                pf = current_result['profit_factor']
                sharpe = current_result['sharpe']
                max_dd = current_result['max_drawdown']
                
                total_pnl += pnl
                total_trades += trades
                total_wins += (trades * win_rate / 100)
                avg_pf += pf
                avg_sharpe += sharpe
                
                status = "✅" if pnl > 0 else "⚠️"
                print(f"{status} {quarter_key:12} | PnL: ${pnl:>10.0f} | PF: {pf:>7.4f} | Sharpe: {sharpe:>7.4f} | Win: {win_rate:>6.1f}% | Max DD: {max_dd:>10.2f}")
        
        if total_count > 0:
            print("\n【総計】")
            print(f"  期間数: {total_count}")
            print(f"  総PnL: ${total_pnl:+.0f}")
            print(f"  総取引数: {int(total_trades)}")
            print(f"  平均勝率: {(total_wins/total_trades*100) if total_trades > 0 else 0:.1f}%")
            print(f"  平均PF: {avg_pf/total_count:.4f}")
            print(f"  平均Sharpe: {avg_sharpe/total_count:.4f}")
    
    def save_final_results(self):
        """最終結果をファイルに保存"""
        PathManager.ensure_dir_exists(self.work_reports_dir)
        
        date_dir = self.work_reports_dir / datetime.now().strftime("%Y-%m-%d")
        PathManager.ensure_dir_exists(date_dir)
        
        final_file = date_dir / f'quarterly_backtest_final_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        
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
