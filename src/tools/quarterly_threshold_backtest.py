#!/usr/bin/env python3
"""四半期ごとの適応型閾値バックテスト

各四半期の最初の2ヶ月でk2/k3を最適化し、残り1ヶ月で検証する。
これを2024年Q1〜2025年Q4まで実施してトータルパフォーマンスを評価。

Usage:
  python tools/quarterly_threshold_backtest.py --years 2024,2025
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple


class QuarterlyThresholdBacktest:
    """四半期ごとの適応型閾値バックテストシステム"""
    
    def __init__(self, src_root: Path):
        self.src_root = Path(src_root)
        self.tools_dir = self.src_root / 'tools'
        self.config_path = self.src_root / 'config.ini'
        self.report_dir = self.src_root / 'report'
        
        # 四半期定義 (月の範囲)
        self.quarters = {
            'Q1': (1, 2, 3),
            'Q2': (4, 5, 6),
            'Q3': (7, 8, 9),
            'Q4': (10, 11, 12)
        }
    
    def get_quarter_periods(self, year: int, quarter: str) -> Tuple[str, str, str, str]:
        """四半期の期間を取得
        
        Returns:
            (training_start, training_end, validation_start, validation_end)
            training: 最初の2ヶ月（最適化用）
            validation: 最後の1ヶ月（検証用）
        """
        months = self.quarters[quarter]
        
        # Training期間: 最初の2ヶ月
        train_start_month = months[0]
        train_end_month = months[1]
        
        # 月末日を取得
        if train_end_month in [1, 3, 5, 7, 8, 10, 12]:
            train_end_day = 31
        elif train_end_month in [4, 6, 9, 11]:
            train_end_day = 30
        else:  # 2月
            train_end_day = 29 if year % 4 == 0 else 28
        
        train_start = f"{year}/{train_start_month:02d}/01 0:00"
        train_end = f"{year}/{train_end_month:02d}/{train_end_day} 23:59"
        
        # Validation期間: 最後の1ヶ月
        val_month = months[2]
        if val_month in [1, 3, 5, 7, 8, 10, 12]:
            val_end_day = 31
        elif val_month in [4, 6, 9, 11]:
            val_end_day = 30
        else:
            val_end_day = 29 if year % 4 == 0 else 28
        
        val_start = f"{year}/{val_month:02d}/01 0:00"
        val_end = f"{year}/{val_month:02d}/{val_end_day} 23:59"
        
        return train_start, train_end, val_start, val_end
    
    def update_config_period(self, start_time: str, end_time: str):
        """config.iniの期間を更新"""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        updated_lines = []
        for line in lines:
            if line.strip().startswith('start_time'):
                updated_lines.append(f'start_time = {start_time}\n')
            elif line.strip().startswith('end_time') and not line.strip().startswith('#'):
                updated_lines.append(f'end_time = {end_time}\n')
            else:
                updated_lines.append(line)
        
        with open(self.config_path, 'w', encoding='utf-8') as f:
            f.writelines(updated_lines)
    
    def update_config_thresholds(self, k2: float, k3: float):
        """config.iniの閾値を更新"""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        updated_lines = []
        for line in lines:
            if line.strip().startswith('classification_k2'):
                updated_lines.append(f'classification_k2 = {k2:.1f}\n')
            elif line.strip().startswith('classification_k3'):
                updated_lines.append(f'classification_k3 = {k3:.1f}\n')
            else:
                updated_lines.append(line)
        
        with open(self.config_path, 'w', encoding='utf-8') as f:
            f.writelines(updated_lines)
    
    def run_backtest(self, period_label: str) -> Dict:
        """バックテスト実行"""
        print(f"  バックテスト実行中: {period_label}...")
        
        # bot_run.shを実行
        cmd = ['bash', 'bot_run.sh', 'run']
        result = subprocess.run(
            cmd,
            cwd=self.src_root,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"  ⚠️ バックテストエラー: {result.stderr[:200]}")
            return {}
        
        # 最新のsummary JSONを取得
        summary_files = sorted(self.report_dir.glob('backtest_summary_*.json'), reverse=True)
        if not summary_files:
            print(f"  ⚠️ サマリーファイルが見つかりません")
            return {}
        
        with open(summary_files[0], 'r') as f:
            summary = json.load(f)
        
        return summary
    
    def find_latest_trend_trades(self) -> Path:
        """最新のtrend_trades JSONを検索"""
        trade_files = sorted(self.report_dir.glob('trend_trades_*.json'), reverse=True)
        if trade_files:
            return trade_files[0]
        return None
    
    def optimize_thresholds(self, period_label: str) -> Tuple[float, float]:
        """閾値最適化（dynamic_classification_optimizer使用）"""
        print(f"  閾値最適化中: {period_label}...")
        
        # 最新のtrend_tradesを取得
        trade_file = self.find_latest_trend_trades()
        if not trade_file:
            print(f"  ⚠️ trend_trades ファイルが見つかりません")
            return 2.2, 1.6  # デフォルト値
        
        # dynamic_classification_optimizerを実行
        output_json = self.report_dir / f'opt_{period_label}.json'
        
        cmd = [
            sys.executable,
            str(self.tools_dir / 'dynamic_classification_optimizer.py'),
            '--input', str(trade_file),
            '--output', str(output_json),
            '--current-k2', '2.2',
            '--current-k3', '1.6'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"  ⚠️ 最適化エラー: {result.stderr[:200]}")
            return 2.2, 1.6
        
        # 結果読み込み
        with open(output_json, 'r') as f:
            analysis = json.load(f)
        
        rec = analysis.get('recommendation', {})
        k2 = rec.get('k2', 2.2)
        k3 = rec.get('k3', 1.6)
        
        print(f"    推奨閾値: k2={k2:.1f}, k3={k3:.1f}")
        
        return k2, k3
    
    def run_quarterly_experiment(self, years: List[int]) -> Dict:
        """四半期ごとの実験実行"""
        results = {
            'quarters': [],
            'summary': {}
        }
        
        # config.iniをバックアップ
        backup_path = self.config_path.with_suffix('.ini.backup_quarterly')
        with open(self.config_path, 'r') as f:
            backup_content = f.read()
        with open(backup_path, 'w') as f:
            f.write(backup_content)
        
        print("=" * 70)
        print("四半期ごとの適応型閾値バックテスト")
        print("=" * 70)
        
        total_pnl_adaptive = 0.0
        total_pnl_fixed = 0.0
        total_trades_adaptive = 0
        total_trades_fixed = 0
        
        for year in years:
            for quarter in ['Q1', 'Q2', 'Q3', 'Q4']:
                print(f"\n{'=' * 70}")
                print(f"{year} {quarter}")
                print(f"{'=' * 70}")
                
                # 期間取得
                train_start, train_end, val_start, val_end = self.get_quarter_periods(year, quarter)
                
                # === Training期間でバックテスト → 閾値最適化 ===
                print(f"\n[1/3] Training期間バックテスト ({train_start} ~ {train_end})")
                self.update_config_period(train_start, train_end)
                self.update_config_thresholds(2.2, 1.6)  # 固定値でトレーニング
                
                train_summary = self.run_backtest(f"{year}_{quarter}_train")
                
                if not train_summary:
                    print(f"  ⚠️ Training期間のバックテスト失敗、スキップ")
                    continue
                
                print(f"  Training PnL: {train_summary.get('total_pnl', 0):.2f}")
                
                # === 閾値最適化 ===
                print(f"\n[2/3] 閾値最適化")
                k2_opt, k3_opt = self.optimize_thresholds(f"{year}_{quarter}_train")
                
                # === Validation期間で2パターンバックテスト ===
                print(f"\n[3/3] Validation期間バックテスト ({val_start} ~ {val_end})")
                self.update_config_period(val_start, val_end)
                
                # (A) 固定閾値 (k2=2.2, k3=1.6)
                print(f"  (A) 固定閾値 k2=2.2, k3=1.6")
                self.update_config_thresholds(2.2, 1.6)
                fixed_summary = self.run_backtest(f"{year}_{quarter}_val_fixed")
                
                fixed_pnl = fixed_summary.get('total_pnl', 0) if fixed_summary else 0
                fixed_trades = fixed_summary.get('trades', 0) if fixed_summary else 0
                fixed_pf = fixed_summary.get('profit_factor', 0) if fixed_summary else 0
                
                print(f"    PnL: {fixed_pnl:.2f}, Trades: {fixed_trades}, PF: {fixed_pf:.2f}")
                
                # (B) 適応型閾値
                print(f"  (B) 適応型閾値 k2={k2_opt:.1f}, k3={k3_opt:.1f}")
                self.update_config_thresholds(k2_opt, k3_opt)
                adaptive_summary = self.run_backtest(f"{year}_{quarter}_val_adaptive")
                
                adaptive_pnl = adaptive_summary.get('total_pnl', 0) if adaptive_summary else 0
                adaptive_trades = adaptive_summary.get('trades', 0) if adaptive_summary else 0
                adaptive_pf = adaptive_summary.get('profit_factor', 0) if adaptive_summary else 0
                
                print(f"    PnL: {adaptive_pnl:.2f}, Trades: {adaptive_trades}, PF: {adaptive_pf:.2f}")
                
                # 比較
                improvement = adaptive_pnl - fixed_pnl
                improvement_pct = (improvement / abs(fixed_pnl) * 100) if fixed_pnl != 0 else 0
                
                print(f"\n  【比較】")
                print(f"    PnL改善: {improvement:+.2f} ({improvement_pct:+.1f}%)")
                print(f"    Winner: {'✅ 適応型' if adaptive_pnl > fixed_pnl else '⚠️ 固定'}")
                
                # 累積
                total_pnl_adaptive += adaptive_pnl
                total_pnl_fixed += fixed_pnl
                total_trades_adaptive += adaptive_trades
                total_trades_fixed += fixed_trades
                
                # 結果記録
                results['quarters'].append({
                    'year': year,
                    'quarter': quarter,
                    'training_period': f"{train_start} ~ {train_end}",
                    'validation_period': f"{val_start} ~ {val_end}",
                    'optimized_k2': k2_opt,
                    'optimized_k3': k3_opt,
                    'fixed': {
                        'pnl': fixed_pnl,
                        'trades': fixed_trades,
                        'profit_factor': fixed_pf
                    },
                    'adaptive': {
                        'pnl': adaptive_pnl,
                        'trades': adaptive_trades,
                        'profit_factor': adaptive_pf
                    },
                    'improvement': {
                        'pnl_diff': improvement,
                        'pnl_diff_pct': improvement_pct,
                        'winner': 'adaptive' if adaptive_pnl > fixed_pnl else 'fixed'
                    }
                })
        
        # === 総合サマリー ===
        print(f"\n{'=' * 70}")
        print("総合サマリー")
        print(f"{'=' * 70}")
        
        total_improvement = total_pnl_adaptive - total_pnl_fixed
        total_improvement_pct = (total_improvement / abs(total_pnl_fixed) * 100) if total_pnl_fixed != 0 else 0
        
        print(f"\n【固定閾値 (k2=2.2, k3=1.6)】")
        print(f"  総PnL: {total_pnl_fixed:.2f}")
        print(f"  総トレード数: {total_trades_fixed}")
        
        print(f"\n【適応型閾値】")
        print(f"  総PnL: {total_pnl_adaptive:.2f}")
        print(f"  総トレード数: {total_trades_adaptive}")
        
        print(f"\n【改善効果】")
        print(f"  PnL改善: {total_improvement:+.2f} ({total_improvement_pct:+.1f}%)")
        print(f"  勝率: {sum(1 for q in results['quarters'] if q['improvement']['winner'] == 'adaptive')}/{len(results['quarters'])} 四半期")
        
        results['summary'] = {
            'total_quarters': len(results['quarters']),
            'fixed_total_pnl': total_pnl_fixed,
            'fixed_total_trades': total_trades_fixed,
            'adaptive_total_pnl': total_pnl_adaptive,
            'adaptive_total_trades': total_trades_adaptive,
            'improvement_pnl': total_improvement,
            'improvement_pct': total_improvement_pct,
            'adaptive_win_rate': sum(1 for q in results['quarters'] if q['improvement']['winner'] == 'adaptive') / len(results['quarters']) * 100
        }
        
        # config.ini復元
        with open(backup_path, 'r') as f:
            backup_content = f.read()
        with open(self.config_path, 'w') as f:
            f.write(backup_content)
        
        print(f"\n✅ config.ini を復元しました")
        
        return results
    
    def save_results(self, results: Dict, output_path: Path):
        """結果をJSON/Markdown保存"""
        # JSON保存
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n✅ 結果JSON: {output_path}")
        
        # Markdown保存
        md_path = output_path.with_suffix('.md')
        with open(md_path, 'w', encoding='utf-8') as md:
            md.write("# 四半期ごとの適応型閾値バックテスト結果\n\n")
            md.write(f"**実行日時**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            md.write("## 実験概要\n\n")
            md.write("各四半期を以下のように分割:\n")
            md.write("- **Training期間**: 最初の2ヶ月（閾値最適化用）\n")
            md.write("- **Validation期間**: 最後の1ヶ月（効果検証用）\n\n")
            md.write("Validation期間で固定閾値 vs 適応型閾値を比較。\n\n")
            
            md.write("## 四半期別結果\n\n")
            md.write("| 期間 | 最適化k2 | 最適化k3 | 固定PnL | 適応PnL | 改善 | Winner |\n")
            md.write("|------|---------|---------|---------|---------|------|--------|\n")
            
            for q in results['quarters']:
                period = f"{q['year']} {q['quarter']}"
                k2 = q['optimized_k2']
                k3 = q['optimized_k3']
                fixed_pnl = q['fixed']['pnl']
                adaptive_pnl = q['adaptive']['pnl']
                improvement = q['improvement']['pnl_diff']
                winner = '✅ 適応' if q['improvement']['winner'] == 'adaptive' else '⚠️ 固定'
                
                md.write(f"| {period} | {k2:.1f} | {k3:.1f} | {fixed_pnl:.2f} | {adaptive_pnl:.2f} | {improvement:+.2f} | {winner} |\n")
            
            md.write("\n## 総合サマリー\n\n")
            summary = results['summary']
            md.write(f"- **総四半期数**: {summary['total_quarters']}\n")
            md.write(f"- **固定閾値 総PnL**: {summary['fixed_total_pnl']:.2f}\n")
            md.write(f"- **適応型閾値 総PnL**: {summary['adaptive_total_pnl']:.2f}\n")
            md.write(f"- **改善効果**: {summary['improvement_pnl']:+.2f} ({summary['improvement_pct']:+.1f}%)\n")
            md.write(f"- **適応型勝率**: {summary['adaptive_win_rate']:.1f}% ({sum(1 for q in results['quarters'] if q['improvement']['winner'] == 'adaptive')}/{summary['total_quarters']} 四半期)\n\n")
            
            if summary['improvement_pnl'] > 0:
                md.write("### ✅ 結論: 適応型閾値が有効\n\n")
                md.write("四半期ごとの市場環境変化に応じた閾値調整により、固定閾値を上回るパフォーマンスを達成。\n")
            else:
                md.write("### ⚠️ 結論: 固定閾値が優位\n\n")
                md.write("本期間においては固定閾値が安定的。適応型の調整頻度や手法の見直しが必要。\n")
        
        print(f"✅ 結果Markdown: {md_path}")


def main():
    parser = argparse.ArgumentParser(description="四半期ごとの適応型閾値バックテスト")
    parser.add_argument('--years', type=str, default='2024,2025',
                        help='対象年（カンマ区切り、例: 2024,2025）')
    parser.add_argument('--src-root', type=str, default='.',
                        help='srcディレクトリのルートパス')
    args = parser.parse_args()
    
    years = [int(y.strip()) for y in args.years.split(',')]
    
    tester = QuarterlyThresholdBacktest(Path(args.src_root))
    results = tester.run_quarterly_experiment(years)
    
    # 結果保存
    output_path = tester.report_dir / f'quarterly_threshold_backtest_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    tester.save_results(results, output_path)
    
    print("\n" + "=" * 70)
    print("✅ 四半期バックテスト完了")
    print("=" * 70)


if __name__ == '__main__':
    main()
