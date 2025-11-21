#!/usr/bin/env python3
"""既存バックテスト結果からの部分利確効果比較

Usage:
  # 最新2件のサマリを自動比較
  python tools/compare_existing_results.py --auto
  
  # 特定サマリを指定比較
  python tools/compare_existing_results.py \
    --base report/backtest_summary_20251121114121.json \
    --partial report/backtest_summary_20251121121336.json \
    --output report/partial_exit_comparison.json
"""
import argparse
import json
from pathlib import Path
from typing import Dict, Any
import time


def load_summary(path: str) -> Dict[str, Any]:
    """サマリファイル読み込み"""
    with open(path, 'r', encoding='utf-8') as f:
        summary = json.load(f)
    
    # trend_trades も読み込み
    ts_tag = Path(path).stem.replace("backtest_summary_", "")
    trades_path = Path(path).parent / f"trend_trades_{ts_tag}.json"
    trades_data = []
    if trades_path.exists():
        with open(trades_path, 'r', encoding='utf-8') as tf:
            trades_data = json.load(tf)
    
    summary['_meta'] = {
        'summary_path': str(path),
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


def count_partial_exits(trades: list) -> int:
    """部分利確回数カウント (partial_exit_count)"""
    return sum(t.get('partial_exit_count', 0) for t in trades)


def generate_comparison_report(base_summary: Dict, partial_summary: Dict, output_path: str):
    """比較レポート生成"""
    base_trades = base_summary.get('trades', [])
    partial_trades = partial_summary.get('trades', [])
    
    # tradesフィールドがリストの場合はカウント、数値の場合はそのまま
    base_trade_count = len(base_trades) if isinstance(base_trades, list) else base_trades
    partial_trade_count = len(partial_trades) if isinstance(partial_trades, list) else partial_trades
    
    base_metrics = {
        'total_pnl': base_summary.get('total_pnl', 0.0),
        'profit_factor': base_summary.get('profit_factor', 0.0),
        'max_drawdown_rate': base_summary.get('max_drawdown_rate', 0.0),
        'sharpe': base_summary.get('sharpe', 0.0),
        'win_rate': base_summary.get('win_rate', 0.0),
        'trade_count': base_trade_count,
        'profit_retention': compute_profit_retention(base_trades if isinstance(base_trades, list) else [])
    }
    
    partial_metrics = {
        'total_pnl': partial_summary.get('total_pnl', 0.0),
        'profit_factor': partial_summary.get('profit_factor', 0.0),
        'max_drawdown_rate': partial_summary.get('max_drawdown_rate', 0.0),
        'sharpe': partial_summary.get('sharpe', 0.0),
        'win_rate': partial_summary.get('win_rate', 0.0),
        'trade_count': partial_trade_count,
        'profit_retention': compute_profit_retention(partial_trades if isinstance(partial_trades, list) else []),
        'partial_exit_count': count_partial_exits(partial_trades if isinstance(partial_trades, list) else [])
    }
    
    # 差分計算
    deltas = {}
    for key in base_metrics.keys():
        base_val = base_metrics[key]
        partial_val = partial_metrics.get(key, 0.0)
        abs_delta = partial_val - base_val
        pct_delta = (abs_delta / base_val * 100) if base_val != 0 else 0.0
        deltas[key] = {
            'base': base_val,
            'partial': partial_val,
            'abs_delta': abs_delta,
            'pct_delta': pct_delta
        }
    
    # 評価スコア
    score = 0
    if deltas['max_drawdown_rate']['abs_delta'] < -5.0:  # DD 5%以上改善
        score += 3
    if deltas['profit_factor']['pct_delta'] > 10.0:  # PF 10%以上改善
        score += 2
    if deltas['profit_retention']['abs_delta'] > 5.0:  # 利益保持率 5%以上改善
        score += 2
    if deltas['total_pnl']['abs_delta'] > 0:  # PnL改善
        score += 1
    
    evaluation = "✅ 有効 (採用推奨)" if score >= 4 else "⚠️ 条件付き有効" if score >= 2 else "➖ 効果限定的"
    
    comparison = {
        'test_date': time.strftime('%Y-%m-%d %H:%M:%S'),
        'base_config': {
            'partial_exit_enabled': False,
            'summary_file': base_summary['_meta']['summary_path']
        },
        'partial_config': {
            'partial_exit_enabled': True,
            'summary_file': partial_summary['_meta']['summary_path'],
            'partial_exit_count': partial_metrics['partial_exit_count']
        },
        'metrics': deltas,
        'evaluation': {
            'score': score,
            'verdict': evaluation,
            'recommendations': []
        }
    }
    
    # 推奨アクション
    if score >= 4:
        comparison['evaluation']['recommendations'].append("部分利確を本番採用")
        comparison['evaluation']['recommendations'].append("profit_rate, ratio パラメータのグリッド探索実施")
    elif score >= 2:
        comparison['evaluation']['recommendations'].append("ADX/ATR動的条件追加を検討")
        comparison['evaluation']['recommendations'].append("min_bars 調整でタイミング最適化")
    else:
        comparison['evaluation']['recommendations'].append("無効化を検討 (効果不十分)")
        comparison['evaluation']['recommendations'].append("EXIT trailing stop 改善を優先")
    
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
        
        md.write("## 設定比較\n\n")
        md.write("| 項目 | ベースライン | 部分利確有効 |\n")
        md.write("|------|-------------|-------------|\n")
        md.write(f"| partial_exit_enabled | False | True |\n")
        md.write(f"| 部分決済回数 | - | {partial_metrics['partial_exit_count']} |\n\n")
        
        md.write("## メトリクス比較\n\n")
        md.write("| メトリクス | ベースライン | 部分利確 | 差分 | 変化率 |\n")
        md.write("|-----------|-------------|---------|------|-------|\n")
        for key, data in deltas.items():
            base_str = f"{data['base']:.2f}" if key != 'trade_count' else f"{int(data['base'])}"
            partial_str = f"{data['partial']:.2f}" if key != 'trade_count' else f"{int(data['partial'])}"
            delta_str = f"{data['abs_delta']:+.2f}" if key != 'trade_count' else f"{int(data['abs_delta']):+d}"
            pct_str = f"{data['pct_delta']:+.1f}%" if data['pct_delta'] != 0 else "-"
            md.write(f"| {key} | {base_str} | {partial_str} | {delta_str} | {pct_str} |\n")
        
        md.write("\n## 評価\n\n")
        md.write(f"**判定**: {comparison['evaluation']['verdict']}  \n")
        md.write(f"**スコア**: {score}/8  \n\n")
        
        md.write("### 評価基準\n\n")
        md.write("- DD率 5%以上改善: +3点\n")
        md.write("- PF 10%以上改善: +2点\n")
        md.write("- 利益保持率 5%以上改善: +2点\n")
        md.write("- PnL改善: +1点\n\n")
        
        md.write("### 推奨アクション\n\n")
        for rec in comparison['evaluation']['recommendations']:
            md.write(f"- {rec}\n")
        
        md.write("\n---\n")
        md.write(f"**生成元**: `{Path(__file__).name}`\n")
    
    print(f"✅ レポート生成完了:")
    print(f"  JSON: {output_json}")
    print(f"  Markdown: {output_md}")
    
    return comparison


def main():
    parser = argparse.ArgumentParser(description="既存バックテスト結果から部分利確効果比較")
    parser.add_argument('--base', type=str, help='ベースラインサマリJSONパス')
    parser.add_argument('--partial', type=str, help='部分利確サマリJSONパス')
    parser.add_argument('--output', type=str, default='report/partial_exit_comparison.json',
                        help='出力JSONパス')
    parser.add_argument('--auto', action='store_true',
                        help='最新2件のサマリを自動選択')
    args = parser.parse_args()
    
    script_dir = Path(__file__).parent.parent
    report_dir = script_dir / "report"
    
    print("=" * 70)
    print("部分利確効果測定: 既存結果比較")
    print("=" * 70)
    
    if args.auto:
        print("\n[自動モード] 最新2件のサマリを検索...")
        summaries = sorted(report_dir.glob("backtest_summary_*.json"), reverse=True)
        if len(summaries) < 2:
            print("❌ 比較に必要なサマリが2件未満です")
            return
        
        base_path = str(summaries[1])
        partial_path = str(summaries[0])
        print(f"  ベースライン: {Path(base_path).name}")
        print(f"  部分利確: {Path(partial_path).name}")
    else:
        if not args.base or not args.partial:
            print("❌ --base と --partial を指定するか、--auto を使用してください")
            return
        base_path = str(script_dir / args.base) if not Path(args.base).is_absolute() else args.base
        partial_path = str(script_dir / args.partial) if not Path(args.partial).is_absolute() else args.partial
    
    # サマリ読み込み
    print("\n[1/3] サマリ読み込み...")
    base_summary = load_summary(base_path)
    partial_summary = load_summary(partial_path)
    print(f"  ベースライン: total_pnl={base_summary.get('total_pnl', 0):.2f}, "
          f"max_dd_rate={base_summary.get('max_drawdown_rate', 0):.2f}%")
    print(f"  部分利確: total_pnl={partial_summary.get('total_pnl', 0):.2f}, "
          f"max_dd_rate={partial_summary.get('max_drawdown_rate', 0):.2f}%")
    
    # 比較レポート生成
    print("\n[2/3] メトリクス比較...")
    output_path = str(script_dir / args.output)
    comparison = generate_comparison_report(base_summary, partial_summary, output_path)
    
    print("\n[3/3] 評価サマリ")
    print(f"  判定: {comparison['evaluation']['verdict']}")
    print(f"  スコア: {comparison['evaluation']['score']}/8")
    
    print("\n" + "=" * 70)
    print("✅ 比較完了")
    print("=" * 70)


if __name__ == '__main__':
    main()
