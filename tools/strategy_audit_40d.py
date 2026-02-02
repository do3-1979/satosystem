#!/usr/bin/env python3
"""
Task 40d: 現行戦略の監査スクリプト

目的:
- Donchian/PVO/ADX/Exit(PSAR)の相互作用を分析
- (1)過剰フィルタで機会損失、(2)Exit早すぎ、(3)反転局面逆行 を定量化
- 改善案を提示

入力:
- baseline_backup/BASELINE_904.35USD_20251221.json (8四半期のメトリクス)
- logs/trade_log_*.json (直近のトレード詳細)

出力:
- docs/analysis/TASK_40d_STRATEGY_AUDIT.md (分析レポート)
"""

import json
import sys
import os
from pathlib import Path
from collections import defaultdict
from datetime import datetime

# プロジェクトルートとsrcディレクトリをパスに追加
WORKSPACE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT / "src"))


def load_baseline_metrics():
    """ベースラインメトリクスを読み込む"""
    baseline_path = WORKSPACE_ROOT / "baseline_backup" / "BASELINE_904.35USD_20251221.json"
    with open(baseline_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def analyze_quarterly_performance(baseline_data):
    """四半期ごとのパフォーマンスを分析"""
    quarters = []
    total_pnl = 0
    winning_quarters = 0
    losing_quarters = 0
    
    for q in baseline_data:
        metrics = q['metrics']
        pnl = metrics['total_pnl']
        total_pnl += pnl
        
        if pnl > 0:
            winning_quarters += 1
        else:
            losing_quarters += 1
        
        quarters.append({
            'period': f"{q['year']}Q{q['quarter']}",
            'pnl': pnl,
            'trades': metrics['trades'],
            'win_rate': metrics['win_rate'],
            'profit_factor': metrics['profit_factor'],
            'max_drawdown': metrics['max_drawdown'],
            'sharpe': metrics['sharpe']
        })
    
    return {
        'quarters': quarters,
        'total_pnl': total_pnl,
        'winning_quarters': winning_quarters,
        'losing_quarters': losing_quarters,
        'avg_trades_per_quarter': sum(q['trades'] for q in quarters) / len(quarters)
    }


def identify_problem_patterns(quarterly_analysis):
    """問題パターンを特定"""
    problems = {
        'low_trade_frequency': [],  # 過剰フィルタの疑い
        'poor_profit_factor': [],   # Exit早すぎの疑い
        'high_drawdown': [],        # 反転局面逆行の疑い
    }
    
    for q in quarterly_analysis['quarters']:
        # (1) 過剰フィルタ: トレード数が極端に少ない
        if q['trades'] < 20:
            problems['low_trade_frequency'].append({
                'period': q['period'],
                'trades': q['trades'],
                'pnl': q['pnl']
            })
        
        # (2) Exit早すぎ: profit_factor < 1.0 かつ win_rate > 50%
        if q['profit_factor'] < 1.0 and q['win_rate'] > 50:
            problems['poor_profit_factor'].append({
                'period': q['period'],
                'profit_factor': q['profit_factor'],
                'win_rate': q['win_rate'],
                'pnl': q['pnl']
            })
        
        # (3) 反転局面逆行: max_drawdown_rate が異常に高い
        if q.get('max_drawdown', 0) > 200:
            problems['high_drawdown'].append({
                'period': q['period'],
                'max_drawdown': q['max_drawdown'],
                'pnl': q['pnl']
            })
    
    return problems


def generate_recommendations(problems, quarterly_analysis):
    """改善案を生成"""
    recommendations = []
    
    # (1) 過剰フィルタ問題
    if len(problems['low_trade_frequency']) >= 3:
        avg_trades = quarterly_analysis['avg_trades_per_quarter']
        recommendations.append({
            'priority': 'HIGH',
            'issue': '過剰フィルタによる機会損失',
            'evidence': f"{len(problems['low_trade_frequency'])}四半期でトレード数<20（平均{avg_trades:.1f}）",
            'impact': '潜在的な利益機会を逃している可能性',
            'suggestions': [
                'PVO閾値を10→8に緩和（トレード機会+20%想定）',
                'ADX閾値を31→28に緩和（トレード機会+15%想定）',
                'Two-Tier Entry System（既に実装済み）の中確度条件を検証'
            ]
        })
    
    # (2) Exit早すぎ問題
    if len(problems['poor_profit_factor']) >= 2:
        avg_pf = sum(q['profit_factor'] for q in quarterly_analysis['quarters']) / len(quarterly_analysis['quarters'])
        recommendations.append({
            'priority': 'MEDIUM',
            'issue': 'Exit戦略が早すぎて期待値を棄損',
            'evidence': f"{len(problems['poor_profit_factor'])}四半期でprofit_factor<1.0（平均PF={avg_pf:.2f}）",
            'impact': '勝率は高いが利益が小さく、損失が大きい',
            'suggestions': [
                'PSAR Exit の感度を調整（現状: af_start=0.02, af_max=0.2）',
                'Trailing Stop の発動タイミングを遅らせる（+2%→+3%）',
                'Time-Based Exit (Task 39d) で長期保有を許容'
            ]
        })
    
    # (3) 反転局面逆行問題
    if len(problems['high_drawdown']) >= 2:
        recommendations.append({
            'priority': 'HIGH',
            'issue': '反転局面での逆行ポジション',
            'evidence': f"{len(problems['high_drawdown'])}四半期でmax_drawdown>200",
            'impact': '大きなドローダウンがパフォーマンスを圧迫',
            'suggestions': [
                'ADXフィルタを強化（トレンド弱時のエントリー抑制）',
                'Dynamic Stop Loss Width (Task 39e) で変動に応じたSTOP設定',
                'Weekend Avoidance (Task 39f) で低流動性時の取引回避'
            ]
        })
    
    return recommendations


def generate_markdown_report(quarterly_analysis, problems, recommendations):
    """Markdownレポートを生成"""
    lines = [
        "# Task 40d - 現行戦略の監査レポート",
        "",
        f"- 作成日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 対象期間: 2024Q1～2025Q4 (8四半期)",
        "- ベースライン: +904.35 USD",
        "",
        "## サマリー",
        "",
        f"- 累積損益: ${quarterly_analysis['total_pnl']:.2f}",
        f"- 勝ち四半期: {quarterly_analysis['winning_quarters']} / 負け四半期: {quarterly_analysis['losing_quarters']}",
        f"- 平均トレード数/四半期: {quarterly_analysis['avg_trades_per_quarter']:.1f}",
        "",
        "## 四半期別パフォーマンス",
        "",
        "| 期間 | PnL | Trades | Win Rate | Profit Factor | Max DD | Sharpe |",
        "|------|-----|--------|----------|---------------|--------|--------|"
    ]
    
    for q in quarterly_analysis['quarters']:
        lines.append(
            f"| {q['period']} | ${q['pnl']:.2f} | {q['trades']} | "
            f"{q['win_rate']:.1f}% | {q['profit_factor']:.2f} | "
            f"${q['max_drawdown']:.2f} | {q['sharpe']:.2f} |"
        )
    
    lines.extend([
        "",
        "## 問題パターンの定量化",
        ""
    ])
    
    # (1) 過剰フィルタ
    lines.extend([
        "### (1) 過剰フィルタによる機会損失",
        "",
        f"**発生頻度**: {len(problems['low_trade_frequency'])} / 8四半期",
        ""
    ])
    
    if problems['low_trade_frequency']:
        lines.append("| 期間 | トレード数 | PnL |")
        lines.append("|------|-----------|-----|")
        for p in problems['low_trade_frequency']:
            lines.append(f"| {p['period']} | {p['trades']} | ${p['pnl']:.2f} |")
    else:
        lines.append("該当なし（トレード数は適正範囲）")
    
    lines.extend(["", ""])
    
    # (2) Exit早すぎ
    lines.extend([
        "### (2) Exit戦略が早すぎて期待値を棄損",
        "",
        f"**発生頻度**: {len(problems['poor_profit_factor'])} / 8四半期",
        ""
    ])
    
    if problems['poor_profit_factor']:
        lines.append("| 期間 | Profit Factor | Win Rate | PnL |")
        lines.append("|------|---------------|----------|-----|")
        for p in problems['poor_profit_factor']:
            lines.append(f"| {p['period']} | {p['profit_factor']:.2f} | {p['win_rate']:.1f}% | ${p['pnl']:.2f} |")
    else:
        lines.append("該当なし（Profit Factorは健全）")
    
    lines.extend(["", ""])
    
    # (3) 反転局面逆行
    lines.extend([
        "### (3) 反転局面での逆行ポジション",
        "",
        f"**発生頻度**: {len(problems['high_drawdown'])} / 8四半期",
        ""
    ])
    
    if problems['high_drawdown']:
        lines.append("| 期間 | Max Drawdown | PnL |")
        lines.append("|------|--------------|-----|")
        for p in problems['high_drawdown']:
            lines.append(f"| {p['period']} | ${p['max_drawdown']:.2f} | ${p['pnl']:.2f} |")
    else:
        lines.append("該当なし（ドローダウンは許容範囲）")
    
    lines.extend(["", ""])
    
    # 改善案
    lines.extend([
        "## 改善案",
        ""
    ])
    
    for i, rec in enumerate(recommendations, 1):
        lines.extend([
            f"### {i}. {rec['issue']} [{rec['priority']}]",
            "",
            f"**根拠**: {rec['evidence']}",
            "",
            f"**影響**: {rec['impact']}",
            "",
            "**推奨アクション**:",
            ""
        ])
        for sug in rec['suggestions']:
            lines.append(f"- {sug}")
        lines.extend(["", ""])
    
    lines.extend([
        "## 次のステップ",
        "",
        "1. Task 39d (Time-Based Exit) を優先実装",
        "2. PVO/ADX閾値の感度テストを実施",
        "3. Exit戦略（PSAR/Trailing Stop）のパラメータ調整を検討",
        ""
    ])
    
    return "\n".join(lines)


def main():
    print("=" * 80)
    print("Task 40d: 現行戦略の監査")
    print("=" * 80)
    
    # ベースラインロード
    print("\n[1/4] ベースラインメトリクスを読み込み中...")
    baseline_data = load_baseline_metrics()
    print(f"✅ {len(baseline_data)}四半期のデータを読み込みました")
    
    # 四半期分析
    print("\n[2/4] 四半期別パフォーマンスを分析中...")
    quarterly_analysis = analyze_quarterly_performance(baseline_data)
    print(f"✅ 累積PnL: ${quarterly_analysis['total_pnl']:.2f}")
    
    # 問題パターン特定
    print("\n[3/4] 問題パターンを特定中...")
    problems = identify_problem_patterns(quarterly_analysis)
    print(f"✅ 過剰フィルタ: {len(problems['low_trade_frequency'])}四半期")
    print(f"✅ Exit早すぎ: {len(problems['poor_profit_factor'])}四半期")
    print(f"✅ 反転逆行: {len(problems['high_drawdown'])}四半期")
    
    # 改善案生成
    print("\n[4/4] 改善案を生成中...")
    recommendations = generate_recommendations(problems, quarterly_analysis)
    print(f"✅ {len(recommendations)}個の改善案を生成しました")
    
    # レポート出力
    report = generate_markdown_report(quarterly_analysis, problems, recommendations)
    output_path = WORKSPACE_ROOT / "docs" / "analysis" / "TASK_40d_STRATEGY_AUDIT.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n✅ レポートを生成しました: {output_path.relative_to(WORKSPACE_ROOT)}")
    print("=" * 80)


if __name__ == "__main__":
    main()
