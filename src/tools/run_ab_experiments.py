#!/usr/bin/env python3
"""Run A/B experiments and generate comparison reports.

Executes paired backtests for Keltner and Pyramiding experiments, then generates
comparison tables showing the impact of each parameter change.

Usage:
  python src/tools/run_ab_experiments.py --configs output_configs/ab_test_*.ini \
      --report-dir report/ab_experiments
"""
from __future__ import annotations
import argparse
import json
import subprocess
import shutil
from pathlib import Path
from typing import List, Dict
import time


def run_backtest(config_path: Path, src_dir: Path) -> Dict:
    """Run single backtest with given config, return metrics."""
    # Copy config to config.ini
    config_backup = src_dir / 'config_ab_backup.ini'
    config_target = src_dir / 'config.ini'
    
    if config_target.exists():
        shutil.copy(config_target, config_backup)
    
    shutil.copy(config_path, config_target)
    
    # Run bot using bot_run.sh (統一されたAPI key管理)
    print(f'Running backtest: {config_path.name}...')
    bot_run_script = src_dir / 'bot_run.sh'
    
    # Ensure bot_run.sh exists and is executable
    if not bot_run_script.exists():
        print(f'Error: bot_run.sh not found at {bot_run_script}')
        return {}
    
    result = subprocess.run(
        ['bash', str(bot_run_script.resolve())],
        cwd=str(src_dir.resolve()),
        capture_output=True,
        text=True,
        timeout=600
    )
    
    if result.returncode != 0:
        print(f'Error running {config_path.name}:')
        print(result.stderr)
        return {}
    
    # Find latest backtest_summary_*.json in report/
    report_dir = src_dir / 'report'
    summaries = sorted(report_dir.glob('backtest_summary_*.json'), key=lambda p: p.stat().st_mtime)
    if not summaries:
        print(f'No summary found for {config_path.name}')
        return {}
    
    latest_summary = summaries[-1]
    metrics = json.loads(latest_summary.read_text(encoding='utf-8'))
    
    # Also get trend_summary if exists
    trend_summaries = sorted(report_dir.glob('trend_summary_*.json'), key=lambda p: p.stat().st_mtime)
    if trend_summaries:
        trend_summary = json.loads(trend_summaries[-1].read_text(encoding='utf-8'))
        metrics['trend_summary'] = trend_summary
    
    # Restore original config
    if config_backup.exists():
        shutil.copy(config_backup, config_target)
        config_backup.unlink()
    
    return metrics


def format_comparison_table(exp_name: str, baseline: Dict, variant: Dict, baseline_name: str, variant_name: str) -> str:
    """Generate markdown comparison table."""
    md = f"## {exp_name}\n\n"
    md += f"| 指標 | {baseline_name} | {variant_name} | 差分 | 改善率 |\n"
    md += "|------|-------:|-------:|-------:|-------:|\n"
    
    metrics_to_compare = [
        ('total_pnl', '最終損益'),
        ('profit_factor', 'PF'),
        ('sharpe', 'Sharpe'),
        ('max_drawdown', '最大DD'),
        ('max_drawdown_rate', 'DD率(%)'),
        ('win_rate', '勝率(%)'),
        ('trades', '取引数'),
        ('recovery_period', '回復期間'),
    ]
    
    for key, label in metrics_to_compare:
        base_val = baseline.get(key, 0)
        var_val = variant.get(key, 0)
        diff = var_val - base_val
        
        if key in ('max_drawdown', 'max_drawdown_rate', 'recovery_period'):
            # Lower is better
            improvement = ((base_val - var_val) / base_val * 100) if base_val != 0 else 0
        else:
            # Higher is better
            improvement = ((var_val - base_val) / base_val * 100) if base_val != 0 else 0
        
        md += f"| {label} | {base_val:.2f} | {var_val:.2f} | {diff:+.2f} | {improvement:+.1f}% |\n"
    
    # Trend metrics if available
    if 'trend_summary' in baseline and 'trend_summary' in variant:
        md += "\n### トレンド指標比較\n\n"
        md += f"| 指標 | {baseline_name} | {variant_name} | 差分 |\n"
        md += "|------|-------:|-------:|-------:|\n"
        
        trend_metrics = [
            ('mfe_median', 'MFE中央値'),
            ('mae_median', 'MAE中央値'),
            ('capture_avg', 'Capture平均'),
            ('loss_containment_avg', 'Loss Contain平均'),
        ]
        
        for key, label in trend_metrics:
            base_val = baseline['trend_summary'].get(key, 0)
            var_val = variant['trend_summary'].get(key, 0)
            diff = var_val - base_val
            md += f"| {label} | {base_val:.3f} | {var_val:.3f} | {diff:+.3f} |\n"
    
    md += "\n"
    return md


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src-dir', type=str, default='src')
    ap.add_argument('--report-dir', type=str, default='report/ab_experiments')
    args = ap.parse_args()
    
    src_dir = Path(args.src_dir)
    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    
    configs_dir = Path('output_configs')
    
    # Experiment pairs
    experiments = [
        {
            'name': 'Keltnerフィルタ効果検証',
            'baseline': configs_dir / 'ab_test_keltner_baseline.ini',
            'variant': configs_dir / 'ab_test_keltner_enabled.ini',
            'baseline_name': 'Keltner無効',
            'variant_name': 'Keltner有効'
        },
        {
            'name': 'ピラミッディング制限効果検証',
            'baseline': configs_dir / 'ab_test_pyramid_10.ini',
            'variant': configs_dir / 'ab_test_pyramid_3.ini',
            'baseline_name': 'entry_times=10',
            'variant_name': 'entry_times=3'
        },
    ]
    
    all_results = []
    markdown_report = "# A/B実験結果レポート\n\n"
    markdown_report += f"実行日時: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    for exp in experiments:
        print(f"\n{'='*60}")
        print(f"実験: {exp['name']}")
        print(f"{'='*60}")
        
        if not exp['baseline'].exists() or not exp['variant'].exists():
            print(f"設定ファイルが見つかりません: {exp['baseline']} or {exp['variant']}")
            continue
        
        # Run baseline
        baseline_metrics = run_backtest(exp['baseline'], src_dir)
        time.sleep(2)
        
        # Run variant
        variant_metrics = run_backtest(exp['variant'], src_dir)
        time.sleep(2)
        
        if not baseline_metrics or not variant_metrics:
            print(f"実験 {exp['name']} でメトリクス取得失敗")
            continue
        
        # Generate comparison
        comparison = format_comparison_table(
            exp['name'],
            baseline_metrics,
            variant_metrics,
            exp['baseline_name'],
            exp['variant_name']
        )
        
        markdown_report += comparison
        
        all_results.append({
            'experiment': exp['name'],
            'baseline': baseline_metrics,
            'variant': variant_metrics
        })
    
    # Save results
    results_json_path = report_dir / 'ab_results.json'
    results_json_path.write_text(json.dumps(all_results, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'\n結果JSON保存: {results_json_path}')
    
    results_md_path = report_dir / 'ab_comparison_report.md'
    results_md_path.write_text(markdown_report, encoding='utf-8')
    print(f'比較レポート保存: {results_md_path}')
    
    print(f'\n{"="*60}')
    print('A/B実験完了')
    print(f'{"="*60}')


if __name__ == '__main__':
    main()
