#!/usr/bin/env python3
"""
四半期別バックテスト実行スクリプト（シンプル版）
Task 19用の日常監視スクリプト

用途:
- Phase 2 導入後の四半期別パフォーマンス測定
- 期間設定を動的に変更して各四半期を実行

使用方法:
  python3 run_quarterly_backtest_simple.py --priority high
  python3 run_quarterly_backtest_simple.py --all
"""

import os
import sys
import json
import subprocess
import tempfile
from configparser import ConfigParser
from datetime import datetime
from pathlib import Path

# Path utilities をインポート
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
from path_utils import PathManager


class SimpleQuarterlyBacktest:
    """シンプルな四半期バックテスト実行"""
    
    def __init__(self):
        self.project_root = PathManager.get_project_root()
        self.src_dir = self.project_root / 'src'
        self.report_dir = PathManager.get_report_dir()
        self.work_reports_dir = PathManager.get_work_reports_dir()
        
        # 四半期定義
        self.quarters_high = [
            ('2024_Q1', '2024-01-01', '2024-03-31'),
            ('2024_Q2', '2024-04-01', '2024-06-30'),
            ('2024_Q3', '2024-07-01', '2024-09-30'),
            ('2025_Q1', '2025-01-01', '2025-03-31'),
            ('2025_Q3', '2025-07-01', '2025-09-30'),
        ]
        
        self.quarters_medium = [
            ('2024_Q4', '2024-10-01', '2024-12-31'),
            ('2025_Q2', '2025-04-01', '2025-06-30'),
        ]
        
        self.results = {}
    
    def create_temp_config(self, start_date, end_date):
        """期間設定を変更した一時的な config を作成"""
        cfg = ConfigParser()
        cfg.read(self.src_dir / 'config.ini')
        
        if not cfg.has_section('Period'):
            cfg.add_section('Period')
        
        cfg.set('Period', 'start_time', f'{start_date} 0:00')
        cfg.set('Period', 'end_time', f'{end_date} 23:59')
        
        # 一時ファイルに保存
        temp_config = self.src_dir / f'config_temp_{start_date.replace("-", "")}.ini'
        with open(temp_config, 'w') as f:
            cfg.write(f)
        
        return temp_config
    
    def run_backtest(self, quarter_key, start_date, end_date):
        """バックテストを実行"""
        # 古いレポートをクリア
        for report_file in self.report_dir.glob('*.json'):
            try:
                report_file.unlink()
            except:
                pass
        
        # 一時 config を作成
        temp_config = self.create_temp_config(start_date, end_date)
        
        print(f"  🚀 {start_date} to {end_date}...", end='', flush=True)
        
        try:
            result = subprocess.run(
                [sys.executable, str(self.src_dir / 'backtest.py'), str(temp_config)],
                capture_output=True,
                text=True,
                timeout=600,
                cwd=str(self.src_dir)
            )
            
            if result.returncode == 0:
                print(" ✅")
                metrics = self._extract_metrics()
                return metrics
            else:
                print(" ❌")
                return None
        
        except subprocess.TimeoutExpired:
            print(" ⏱️")
            return None
        except Exception as e:
            print(f" ❌ ({e})")
            return None
        finally:
            # クリーンアップ
            try:
                temp_config.unlink()
            except:
                pass
    
    def _extract_metrics(self):
        """レポートから主要メトリクスを抽出"""
        try:
            report_files = sorted(
                self.report_dir.glob('backtest_summary_*.json'),
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )
            
            if not report_files:
                return None
            
            with open(report_files[0], 'r', encoding='utf-8') as f:
                report = json.load(f)
            
            pnl = report.get('total_pnl') or report.get('total_profit_loss') or 0
            trades = report.get('trades') or report.get('total_trades') or 0
            win_rate = report.get('win_rate') or 0
            pf = report.get('profit_factor') or 0
            sharpe = report.get('sharpe') or 0
            max_dd = report.get('max_drawdown') or report.get('max_drawdown_percent') or 0
            
            return {
                'pnl': float(pnl),
                'trades': int(trades),
                'win_rate': float(win_rate) * 100 if win_rate < 1 else float(win_rate),
                'profit_factor': float(pf),
                'sharpe': float(sharpe),
                'max_drawdown': float(max_dd),
            }
        
        except Exception as e:
            print(f"    ⚠️  Error: {e}")
            return None
    
    def run_priority_backtests(self):
        """優先度 HIGH の四半期を実行"""
        print("\n" + "="*80)
        print("🧪 QUARTERLY BACKTEST - Phase 2 Verification (HIGH Priority)")
        print("="*80)
        
        quarters = self.quarters_high
        total = len(quarters)
        
        for i, (quarter_key, start_date, end_date) in enumerate(quarters, 1):
            print(f"\n📅 {quarter_key}")
            print(f"   [{i}/{total}]", end='')
            
            result = self.run_backtest(quarter_key, start_date, end_date)
            self.results[quarter_key] = result
        
        return True
    
    def run_all_backtests(self):
        """すべての四半期を実行"""
        print("\n" + "="*80)
        print("🧪 QUARTERLY BACKTEST - Phase 2 Verification (ALL)")
        print("="*80)
        
        quarters = self.quarters_high + self.quarters_medium
        total = len(quarters)
        
        for i, (quarter_key, start_date, end_date) in enumerate(quarters, 1):
            print(f"\n📅 {quarter_key}")
            print(f"   [{i}/{total}]", end='')
            
            result = self.run_backtest(quarter_key, start_date, end_date)
            self.results[quarter_key] = result
        
        return True
    
    def print_summary(self):
        """結果サマリを表示"""
        print("\n" + "="*100)
        print("📊 Summary - Phase 2 Setting (Regime ON + Graduated ON)")
        print("="*100)
        print()
        
        # テーブルヘッダ
        print(f"{'Quarter':<12} | {'PnL':>12} | {'Trades':>8} | {'Win%':>7} | {'PF':>8} | {'Sharpe':>8} | {'Max DD':>10}")
        print("-" * 100)
        
        total_pnl = 0
        total_trades = 0
        total_wins = 0
        count = 0
        
        for quarter_key in sorted(self.results.keys()):
            result = self.results[quarter_key]
            
            if result:
                pnl = result['pnl']
                trades = result['trades']
                win_rate = result['win_rate']
                pf = result['profit_factor']
                sharpe = result['sharpe']
                max_dd = result['max_drawdown']
                
                status = "✅" if pnl > 0 else "⚠️"
                
                print(f"{status} {quarter_key:<10} | ${pnl:>11.0f} | {trades:>8} | {win_rate:>6.1f}% | {pf:>8.4f} | {sharpe:>8.4f} | {max_dd:>10.2f}")
                
                total_pnl += pnl
                total_trades += trades
                total_wins += trades * win_rate / 100
                count += 1
            else:
                print(f"❌ {quarter_key:<10} | {'N/A':>12} | {'N/A':>8} | {'N/A':>7} | {'N/A':>8} | {'N/A':>8} | {'N/A':>10}")
        
        print("-" * 100)
        
        if count > 0:
            avg_win = (total_wins / total_trades * 100) if total_trades > 0 else 0
            print()
            print("【統計】")
            print(f"  期間数:     {count}")
            print(f"  総PnL:      ${total_pnl:+.0f}")
            print(f"  総取引数:   {int(total_trades)}")
            print(f"  平均勝率:   {avg_win:.1f}%")
            print(f"  平均PF:     {total_pnl / count / total_wins * 100 if total_wins > 0 else 0:.4f}")
    
    def save_results(self):
        """結果を JSON で保存"""
        PathManager.ensure_dir_exists(self.work_reports_dir)
        
        result_file = self.work_reports_dir / f'quarterly_backtest_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        
        output = {
            'timestamp': datetime.now().isoformat(),
            'phase': 'Phase 2 (Regime ON + Graduated ON)',
            'results': self.results
        }
        
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Results saved: {result_file}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Quarterly Backtest Simple Version')
    parser.add_argument('--priority', choices=['high', 'all'], default='high', help='Priority level')
    args = parser.parse_args()
    
    bt = SimpleQuarterlyBacktest()
    
    if args.priority == 'high':
        bt.run_priority_backtests()
    else:
        bt.run_all_backtests()
    
    bt.print_summary()
    bt.save_results()
    
    print("\n✅ Quarterly backtest completed")


if __name__ == '__main__':
    main()
