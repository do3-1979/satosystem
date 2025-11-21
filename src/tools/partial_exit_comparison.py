#!/usr/bin/env python3
"""部分利確効果測定: ON/OFF比較バックテスト実行と差分レポート生成

Usage:
  python tools/partial_exit_comparison.py --output report/partial_exit_comparison.json
  
機能:
  1. config.ini のバックアップ
  2. partial_exit_enabled=False でバックテスト実行 (A)
  3. partial_exit_enabled=True でバックテスト実行 (B)
  4. メトリクス比較 (DD率, PF, Sharpe, 利益保持率, 部分決済回数)
  5. Markdown差分レポート生成
"""
import argparse
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Dict, Any


def backup_config(config_path: str) -> str:
    """config.ini バックアップ"""
    backup_path = f"{config_path}.backup_{int(time.time())}"
    shutil.copy2(config_path, backup_path)
    return backup_path


def restore_config(backup_path: str, config_path: str):
    """config.ini 復元"""
    shutil.copy2(backup_path, config_path)
    os.remove(backup_path)


def set_partial_exit_enabled(config_path: str, enabled: bool):
    """config.ini の partial_exit_enabled を書き換え"""
    with open(config_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    modified = False
    for i, line in enumerate(lines):
        if line.strip().startswith('partial_exit_enabled'):
            lines[i] = f'partial_exit_enabled = {str(enabled)}\n'
            modified = True
            break
    
    if not modified:
        raise ValueError("config.ini に partial_exit_enabled が見つかりません")
    
    with open(config_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)


def run_backtest(wrapper_script: str = "../bot_run.sh") -> Dict[str, Any]:
    """バックテスト実行と最新サマリ取得"""
    script_dir = Path(__file__).parent.parent  # src/
    wrapper_path = script_dir / "bot_run.sh"
    
    env = os.environ.copy()
    env['BOT_WRAPPER_INVOKED'] = '1'
    
    result = subprocess.run(
        ["bash", str(wrapper_path), "run"],
        cwd=str(script_dir),
        env=env,
        capture_output=True,
        text=True,
        timeout=3600  # 1時間タイムアウト
    )
    
    if result.returncode != 0:
        raise RuntimeError(f"Backtest failed: {result.stderr}")
    
    # 最新サマリファイル取得
    report_dir = script_dir / "report"
    summaries = sorted(report_dir.glob("backtest_summary_*.json"), reverse=True)
    if not summaries:
        raise FileNotFoundError("No backtest summary found")
    
    latest_summary = summaries[0]
    with open(latest_summary, 'r', encoding='utf-8') as f:
        summary = json.load(f)
    
    # trend_trades も取得 (部分決済回数カウント用)
    ts_tag = latest_summary.stem.replace("backtest_summary_", "")
    trades_path = report_dir / f"trend_trades_{ts_tag}.json"
    trades_data = []
    if trades_path.exists():
        with open(trades_path, 'r', encoding='utf-8') as tf:
            trades_data = json.load(tf)
    
    summary['_meta'] = {
        'summary_path': str(latest_summary),
        'trades_path': str(trades_path) if trades_path.exists() else None,
        'timestamp': ts_tag
    }
    summary['trades'] = trades_data
    
    return summary


def compute_profit_retention(trades: list) -> float:
    """利益保持率: 実現PnL / 最大MFE (正トレードのみ)"""
    if not trades:
        return 0.0
    
    total_realized = 0.0
    total_mfe = 0.0
    
    for t in trades:
        pnl = t.get('realized_pnl', 0.0)
        mfe = t.get('mfe', 0.0)
        if pnl > 0 and mfe > 0:
            total_realized += pnl
            total_mfe += mfe
    
    return (total_realized / total_mfe * 100) if total_mfe > 0 else 0.0


def generate_comparison_report(base_summary: Dict, partial_summary: Dict, output_path: str):
    """比較レポート生成 (JSON + Markdown)"""
    comparison = {
        'test_date': time.strftime('%Y-%m-%d %H:%M:%S'),
        'base_config': {
            'partial_exit_enabled': False,
            'summary_file': base_summary['_meta']['summary_path'],
            'trades_file': base_summary['_meta']['trades_path']
        },
        'partial_config': {
            'partial_exit_enabled': True,
            'summary_file': partial_summary['_meta']['summary_path'],
            'trades_file': partial_summary['_meta']['trades_path']
        },
        'metrics_comparison': {},
        'trades_comparison': {}
    }
    
    # メトリクス比較
    metrics_keys = ['total_pnl', 'profit_factor', 'max_drawdown_rate', 'sharpe', 'win_rate', 'trades']
    for key in metrics_keys:
        base_val = base_summary.get(key, 0)
        partial_val = partial_summary.get(key, 0)
        diff = partial_val - base_val
        diff_pct = (diff / base_val * 100) if base_val != 0 else 0.0
        
        comparison['metrics_comparison'][key] = {
            'base': base_val,
            'partial': partial_val,
            'diff': diff,
            'diff_pct': diff_pct
        }
    
    # 利益保持率計算
    base_retention = compute_profit_retention(base_summary.get('trades', []))
    partial_retention = compute_profit_retention(partial_summary.get('trades', []))
    comparison['metrics_comparison']['profit_retention'] = {
        'base': base_retention,
        'partial': partial_retention,
        'diff': partial_retention - base_retention,
        'diff_pct': ((partial_retention - base_retention) / base_retention * 100) if base_retention > 0 else 0.0
    }
    
    # 部分決済回数カウント (portfolio.partial_exit_count 集計)
    # 注: 現状 trend_trades に partial_exit フラグがないため、別途収集必要
    # ここでは trades 数差分から推定
    base_trades_count = len(base_summary.get('trades', []))
    partial_trades_count = len(partial_summary.get('trades', []))
    comparison['trades_comparison']['count'] = {
        'base': base_trades_count,
        'partial': partial_trades_count,
        'diff': partial_trades_count - base_trades_count
    }
    
    # JSON出力
    output_json = Path(output_path)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(comparison, f, ensure_ascii=False, indent=2)
    
    # Markdown出力
    output_md = output_json.with_suffix('.md')
    with open(output_md, 'w', encoding='utf-8') as md:
        md.write("# 部分利確効果測定レポート\n\n")
        md.write(f"**実行日時**: {comparison['test_date']}\n\n")
        
        md.write("## 設定\n\n")
        md.write("| 項目 | ベースライン (OFF) | 部分利確 (ON) |\n")
        md.write("|------|-------------------|---------------|\n")
        md.write(f"| partial_exit_enabled | False | True |\n")
        md.write(f"| サマリファイル | {base_summary['_meta']['timestamp']} | {partial_summary['_meta']['timestamp']} |\n\n")
        
        md.write("## メトリクス比較\n\n")
        md.write("| 指標 | ベースライン | 部分利確 | 差分 | 変化率 |\n")
        md.write("|------|-------------|---------|------|--------|\n")
        
        for key, vals in comparison['metrics_comparison'].items():
            label_map = {
                'total_pnl': '総損益 (USD)',
                'profit_factor': 'プロフィットファクター',
                'max_drawdown_rate': '最大DD率 (%)',
                'sharpe': 'Sharpe比',
                'win_rate': '勝率 (%)',
                'trades': 'トレード数',
                'profit_retention': '利益保持率 (%)'
            }
            label = label_map.get(key, key)
            base = vals['base']
            partial = vals['partial']
            diff = vals['diff']
            diff_pct = vals['diff_pct']
            
            # 値のフォーマット
            if key in ['max_drawdown_rate', 'win_rate', 'profit_retention']:
                base_str = f"{base:.2f}"
                partial_str = f"{partial:.2f}"
                diff_str = f"{diff:+.2f}"
            elif key in ['sharpe']:
                base_str = f"{base:.3f}"
                partial_str = f"{partial:.3f}"
                diff_str = f"{diff:+.3f}"
            elif key == 'trades':
                base_str = f"{int(base)}"
                partial_str = f"{int(partial)}"
                diff_str = f"{int(diff):+d}"
            else:
                base_str = f"{base:.2f}"
                partial_str = f"{partial:.2f}"
                diff_str = f"{diff:+.2f}"
            
            md.write(f"| {label} | {base_str} | {partial_str} | {diff_str} | {diff_pct:+.1f}% |\n")
        
        md.write("\n## 評価サマリ\n\n")
        
        # DD率改善判定
        dd_diff = comparison['metrics_comparison']['max_drawdown_rate']['diff']
        if dd_diff < -5:
            md.write(f"✅ **最大DD率が {abs(dd_diff):.1f}% 改善** (リスク抑制効果あり)\n\n")
        elif dd_diff > 5:
            md.write(f"⚠️ 最大DD率が {dd_diff:.1f}% 悪化 (要因分析必要)\n\n")
        else:
            md.write(f"➖ 最大DD率変化はわずか ({dd_diff:.1f}%)\n\n")
        
        # PF改善判定
        pf_diff_pct = comparison['metrics_comparison']['profit_factor']['diff_pct']
        if pf_diff_pct > 10:
            md.write(f"✅ **プロフィットファクターが {pf_diff_pct:.1f}% 向上**\n\n")
        elif pf_diff_pct < -10:
            md.write(f"⚠️ プロフィットファクターが {abs(pf_diff_pct):.1f}% 低下\n\n")
        else:
            md.write(f"➖ プロフィットファクター変化は軽微 ({pf_diff_pct:+.1f}%)\n\n")
        
        # 利益保持率
        retention_diff = comparison['metrics_comparison']['profit_retention']['diff']
        if retention_diff > 5:
            md.write(f"✅ **利益保持率が {retention_diff:.1f}% 向上** (早期利確効果)\n\n")
        elif retention_diff < -5:
            md.write(f"⚠️ 利益保持率が {abs(retention_diff):.1f}% 低下 (部分決済タイミング要調整)\n\n")
        else:
            md.write(f"➖ 利益保持率変化はわずか ({retention_diff:+.1f}%)\n\n")
        
        md.write("## 推奨アクション\n\n")
        
        total_score = 0
        if dd_diff < -5:
            total_score += 1
        if pf_diff_pct > 5:
            total_score += 1
        if retention_diff > 3:
            total_score += 1
        
        if total_score >= 2:
            md.write("**部分利確を本採用推奨** (2指標以上で改善確認)\n\n")
            md.write("次のステップ:\n")
            md.write("- [ ] `partial_exit_profit_rate` 閾値微調整 (0.08, 0.10, 0.12 比較)\n")
            md.write("- [ ] `partial_exit_ratio` 最適化 (0.33, 0.50, 0.67 比較)\n")
            md.write("- [ ] `partial_exit_min_bars` 導入検討 (5, 10 で安定性評価)\n")
        elif total_score == 1:
            md.write("**部分利確は限定的効果** (条件付き有効)\n\n")
            md.write("次のステップ:\n")
            md.write("- [ ] 部分決済トリガー条件を ADX/ATR 連動へ強化\n")
            md.write("- [ ] 残ポジション管理ロジック精緻化 (戻り待ち条件)\n")
        else:
            md.write("**部分利確の効果不明瞭または負** (無効化検討)\n\n")
            md.write("次のステップ:\n")
            md.write("- [ ] 部分決済閾値が過剰に早い可能性 → 閾値引き上げ\n")
            md.write("- [ ] 全量EXIT戦略の先行改善 (トレール強化)\n")
        
        md.write("\n---\n")
        md.write(f"**生成**: `{Path(__file__).name}`  \n")
        md.write(f"**詳細データ**: `{output_json.name}`\n")
    
    print(f"✅ 比較レポート生成完了:")
    print(f"  JSON: {output_json}")
    print(f"  Markdown: {output_md}")
    
    return comparison


def main():
    parser = argparse.ArgumentParser(description="部分利確効果測定: ON/OFF比較")
    parser.add_argument('--output', type=str, default='report/partial_exit_comparison.json',
                        help='出力JSONパス (デフォルト: report/partial_exit_comparison.json)')
    parser.add_argument('--config', type=str, default='config.ini',
                        help='config.iniパス (デフォルト: config.ini)')
    parser.add_argument('--wrapper', type=str, default='./bot_run.sh',
                        help='bot_run.shパス (デフォルト: ./bot_run.sh)')
    args = parser.parse_args()
    
    # パス解決 (tools/ からの相対パス)
    script_dir = Path(__file__).parent.parent  # src/
    config_path = str(script_dir / args.config)
    wrapper_script = args.wrapper
    output_path = str(script_dir / args.output)
    
    print("=" * 70)
    print("部分利確効果測定: ベースライン vs 部分利確有効化")
    print("=" * 70)
    
    # 1. config.ini バックアップ
    print("\n[1/5] config.ini バックアップ...")
    backup_path = backup_config(config_path)
    print(f"  バックアップ: {backup_path}")
    
    try:
        # 2. ベースライン実行 (partial_exit_enabled=False)
        print("\n[2/5] ベースラインバックテスト実行 (partial_exit_enabled=False)...")
        set_partial_exit_enabled(config_path, False)
        base_summary = run_backtest(wrapper_script)
        print(f"  完了: {base_summary['_meta']['summary_path']}")
        print(f"    total_pnl={base_summary.get('total_pnl', 0):.2f}, "
              f"max_dd_rate={base_summary.get('max_drawdown_rate', 0):.2f}%, "
              f"PF={base_summary.get('profit_factor', 0):.2f}")
        
        # 3. 部分利確実行 (partial_exit_enabled=True)
        print("\n[3/5] 部分利確バックテスト実行 (partial_exit_enabled=True)...")
        set_partial_exit_enabled(config_path, True)
        partial_summary = run_backtest(wrapper_script)
        print(f"  完了: {partial_summary['_meta']['summary_path']}")
        print(f"    total_pnl={partial_summary.get('total_pnl', 0):.2f}, "
              f"max_dd_rate={partial_summary.get('max_drawdown_rate', 0):.2f}%, "
              f"PF={partial_summary.get('profit_factor', 0):.2f}")
        
        # 4. 比較レポート生成
        print("\n[4/5] 比較レポート生成...")
        comparison = generate_comparison_report(base_summary, partial_summary, output_path)
        
        # 5. config.ini 復元
        print("\n[5/5] config.ini 復元...")
        restore_config(backup_path, config_path)
        print(f"  復元完了")
        
        print("\n" + "=" * 70)
        print("✅ 部分利確効果測定完了")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ エラー発生: {e}")
        import traceback
        traceback.print_exc()
        
        # エラー時も復元試行
        try:
            restore_config(backup_path, config_path)
            print(f"config.ini 復元完了 (エラー後)")
        except:
            print(f"config.ini 復元失敗 - 手動で {backup_path} を確認してください")
        
        raise


if __name__ == '__main__':
    main()
