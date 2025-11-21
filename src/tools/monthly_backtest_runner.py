#!/usr/bin/env python3
"""月次バックテスト実行と累積資産計算

Usage:
  python tools/monthly_backtest_runner.py \
    --start-year 2024 --start-month 1 \
    --end-year 2025 --end-month 10 \
    --output report/monthly_backtest_results.json
"""
import argparse
import json
import subprocess
import shutil
from pathlib import Path
from datetime import datetime, timedelta
import time
import re


def backup_config(config_path: Path) -> Path:
    """config.iniバックアップ"""
    backup_path = config_path.with_suffix(f'.ini.backup_{int(time.time())}')
    shutil.copy2(config_path, backup_path)
    return backup_path


def restore_config(backup_path: Path, config_path: Path):
    """config.ini復元"""
    shutil.copy2(backup_path, config_path)
    backup_path.unlink()


def update_config_period(config_path: Path, start_date: str, end_date: str):
    """config.iniの期間を更新"""
    with open(config_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # start_time更新
    content = re.sub(
        r'start_time\s*=\s*[^\n]+',
        f'start_time = {start_date}',
        content
    )
    
    # end_time更新
    content = re.sub(
        r'end_time\s*=\s*[^\n]+',
        f'end_time = {end_date}',
        content
    )
    
    with open(config_path, 'w', encoding='utf-8') as f:
        f.write(content)


def run_monthly_backtest(year: int, month: int, wrapper_script: Path, src_dir: Path) -> dict:
    """指定月のバックテスト実行"""
    # 月の開始日と終了日
    start_date = datetime(year, month, 1)
    if month == 12:
        end_date = datetime(year + 1, 1, 1) - timedelta(seconds=1)
    else:
        end_date = datetime(year, month + 1, 1) - timedelta(seconds=1)
    
    start_str = start_date.strftime('%Y/%m/%d %H:%M')
    end_str = end_date.strftime('%Y/%m/%d %H:%M')
    
    print(f"\n{'='*70}")
    print(f"バックテスト実行: {year}年{month}月 ({start_str} - {end_str})")
    print('='*70)
    
    # config.ini更新
    config_path = src_dir / "config.ini"
    update_config_period(config_path, start_str, end_str)
    
    # バックテスト実行
    result = subprocess.run(
        ["bash", str(wrapper_script), "run"],
        cwd=str(src_dir),
        capture_output=True,
        text=True,
        timeout=1800  # 30分タイムアウト
    )
    
    if result.returncode != 0:
        print(f"⚠️ バックテスト失敗: {result.stderr}")
        return None
    
    # 最新サマリ取得
    report_dir = src_dir / "report"
    summaries = sorted(report_dir.glob("backtest_summary_*.json"), reverse=True)
    if not summaries:
        print("⚠️ サマリファイルが見つかりません")
        return None
    
    latest_summary = summaries[0]
    with open(latest_summary, 'r', encoding='utf-8') as f:
        summary = json.load(f)
    
    summary['_meta'] = {
        'year': year,
        'month': month,
        'start_date': start_str,
        'end_date': end_str,
        'summary_file': str(latest_summary.name)
    }
    
    print(f"✅ 完了: total_pnl={summary.get('total_pnl', 0):.2f}, "
          f"max_dd_rate={summary.get('max_drawdown_rate', 0):.2f}%, "
          f"trades={summary.get('trades', 0)}")
    
    return summary


def calculate_cumulative_equity(monthly_results: list, initial_balance: float) -> list:
    """累積資産計算"""
    cumulative = []
    current_balance = initial_balance
    
    for result in monthly_results:
        if result is None:
            continue
        
        pnl = result.get('total_pnl', 0.0)
        current_balance += pnl
        
        cumulative.append({
            'year': result['_meta']['year'],
            'month': result['_meta']['month'],
            'monthly_pnl': pnl,
            'balance_after': current_balance,
            'cumulative_pnl': current_balance - initial_balance,
            'return_pct': ((current_balance - initial_balance) / initial_balance * 100)
        })
    
    return cumulative


def generate_report(monthly_results: list, cumulative: list, 
                   initial_balance: float, output_path: Path):
    """レポート生成"""
    report = {
        'test_date': time.strftime('%Y-%m-%d %H:%M:%S'),
        'initial_balance': initial_balance,
        'monthly_results': monthly_results,
        'cumulative_equity': cumulative,
        'summary': {
            'total_months': len([r for r in monthly_results if r is not None]),
            'final_balance': cumulative[-1]['balance_after'] if cumulative else initial_balance,
            'total_pnl': cumulative[-1]['cumulative_pnl'] if cumulative else 0.0,
            'total_return_pct': cumulative[-1]['return_pct'] if cumulative else 0.0,
            'winning_months': len([c for c in cumulative if c['monthly_pnl'] > 0]),
            'losing_months': len([c for c in cumulative if c['monthly_pnl'] < 0]),
            'best_month': max(cumulative, key=lambda x: x['monthly_pnl']) if cumulative else None,
            'worst_month': min(cumulative, key=lambda x: x['monthly_pnl']) if cumulative else None
        }
    }
    
    # JSON出力
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    # Markdown出力
    output_md = output_path.with_suffix('.md')
    with open(output_md, 'w', encoding='utf-8') as md:
        md.write("# 月次バックテスト結果レポート\n\n")
        md.write(f"**実行日時**: {report['test_date']}\n")
        md.write(f"**初期資産**: ${initial_balance:.2f}\n")
        md.write(f"**最終資産**: ${report['summary']['final_balance']:.2f}\n")
        md.write(f"**累積PnL**: ${report['summary']['total_pnl']:.2f} ({report['summary']['total_return_pct']:.2f}%)\n\n")
        
        md.write("## 月次パフォーマンス\n\n")
        md.write("| 年月 | 月次PnL | 資産残高 | 累積PnL | リターン率 |\n")
        md.write("|------|---------|----------|---------|----------|\n")
        
        for c in cumulative:
            year_month = f"{c['year']}/{c['month']:02d}"
            monthly_pnl = c['monthly_pnl']
            balance = c['balance_after']
            cum_pnl = c['cumulative_pnl']
            ret_pct = c['return_pct']
            
            pnl_indicator = "🟢" if monthly_pnl > 0 else "🔴" if monthly_pnl < 0 else "⚪"
            
            md.write(f"| {year_month} | {pnl_indicator} ${monthly_pnl:+.2f} | "
                    f"${balance:.2f} | ${cum_pnl:+.2f} | {ret_pct:+.2f}% |\n")
        
        md.write("\n## サマリ統計\n\n")
        md.write(f"- **対象期間**: {len(cumulative)}ヶ月\n")
        md.write(f"- **勝ち月**: {report['summary']['winning_months']}ヶ月\n")
        md.write(f"- **負け月**: {report['summary']['losing_months']}ヶ月\n")
        md.write(f"- **勝率**: {report['summary']['winning_months'] / len(cumulative) * 100:.1f}%\n\n")
        
        best = report['summary']['best_month']
        worst = report['summary']['worst_month']
        
        if best:
            md.write(f"- **最高月**: {best['year']}/{best['month']:02d} (${best['monthly_pnl']:+.2f})\n")
        if worst:
            md.write(f"- **最低月**: {worst['year']}/{worst['month']:02d} (${worst['monthly_pnl']:+.2f})\n")
        
        md.write("\n---\n")
        md.write(f"**生成元**: `{Path(__file__).name}`\n")
    
    print(f"\n✅ レポート生成完了:")
    print(f"  JSON: {output_path}")
    print(f"  Markdown: {output_md}")


def main():
    parser = argparse.ArgumentParser(description="月次バックテスト実行と累積資産計算")
    parser.add_argument('--start-year', type=int, required=True, help='開始年')
    parser.add_argument('--start-month', type=int, required=True, help='開始月')
    parser.add_argument('--end-year', type=int, required=True, help='終了年')
    parser.add_argument('--end-month', type=int, required=True, help='終了月')
    parser.add_argument('--initial-balance', type=float, default=300.0,
                       help='初期資産 (デフォルト: 300.0)')
    parser.add_argument('--output', type=str, default='report/monthly_backtest_results.json',
                       help='出力JSONパス')
    args = parser.parse_args()
    
    script_dir = Path(__file__).parent.parent
    config_path = script_dir / "config.ini"
    wrapper_script = script_dir / "bot_run.sh"
    
    print("=" * 70)
    print("月次バックテスト実行")
    print("=" * 70)
    print(f"期間: {args.start_year}/{args.start_month} - {args.end_year}/{args.end_month}")
    print(f"初期資産: ${args.initial_balance:.2f}")
    
    # config.iniバックアップ
    backup_path = backup_config(config_path)
    print(f"\nconfig.iniバックアップ: {backup_path.name}")
    
    try:
        monthly_results = []
        
        # 月次ループ
        current_year = args.start_year
        current_month = args.start_month
        
        while (current_year < args.end_year) or \
              (current_year == args.end_year and current_month <= args.end_month):
            
            result = run_monthly_backtest(current_year, current_month, 
                                         wrapper_script, script_dir)
            monthly_results.append(result)
            
            # 次の月へ
            if current_month == 12:
                current_year += 1
                current_month = 1
            else:
                current_month += 1
        
        # 累積資産計算
        print(f"\n{'='*70}")
        print("累積資産計算")
        print('='*70)
        
        cumulative = calculate_cumulative_equity(monthly_results, args.initial_balance)
        
        # レポート生成
        output_path = script_dir / args.output
        generate_report(monthly_results, cumulative, args.initial_balance, output_path)
        
        # サマリ表示
        print(f"\n{'='*70}")
        print("実行完了サマリ")
        print('='*70)
        print(f"初期資産: ${args.initial_balance:.2f}")
        print(f"最終資産: ${cumulative[-1]['balance_after']:.2f}")
        print(f"累積PnL: ${cumulative[-1]['cumulative_pnl']:+.2f}")
        print(f"リターン率: {cumulative[-1]['return_pct']:+.2f}%")
        print(f"勝ち月: {len([c for c in cumulative if c['monthly_pnl'] > 0])}/{len(cumulative)}")
        
    finally:
        # config.ini復元
        print(f"\nconfig.ini復元中...")
        restore_config(backup_path, config_path)
        print("✅ 復元完了")


if __name__ == '__main__':
    main()
