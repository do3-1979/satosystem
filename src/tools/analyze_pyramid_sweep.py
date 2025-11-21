#!/usr/bin/env python3
"""
Pyramiding最適化結果分析
リスク効率（Sharpe, DD率, 回復期間）と収益性のバランスを評価
"""
import json
from pathlib import Path

def load_summary(path):
    """Load JSON summary file."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {path}: {e}")
        return None

def analyze_pyramid():
    """Analyze pyramiding sweep results."""
    sweep_dir = Path("report/pyramid_sweep")
    
    if not sweep_dir.exists():
        print(f"Sweep directory not found: {sweep_dir}")
        return
    
    # Collect results
    results = []
    for summary_file in sorted(sweep_dir.glob("pyramid_entry*_summary.json")):
        config_name = summary_file.stem.replace("_summary", "")
        data = load_summary(summary_file)
        if data:
            # Parse entry_times from filename: pyramid_entry3
            entry_times = int(config_name.replace("pyramid_entry", ""))
            
            results.append({
                'entry_times': entry_times,
                'pnl': data.get('total_pnl', 0),
                'pf': data.get('profit_factor', 0),
                'dd_rate': data.get('max_drawdown_rate', 0),
                'sharpe': data.get('sharpe', 0),
                'win_rate': data.get('win_rate', 0),
                'trades': data.get('trades', 0),
                'recovery': data.get('recovery_period', -1)
            })
    
    if not results:
        print("No results found")
        return
    
    # Sort by entry_times ascending
    results.sort(key=lambda x: x['entry_times'])
    
    # Generate report
    report_lines = [
        "# Pyramiding最適化分析",
        "",
        "**期間**: 2025/10/01 - 2025/11/01",
        "",
        "## 結果一覧",
        "",
        "| entry_times | 総損益 | PF | Sharpe | DD率(%) | 勝率(%) | 取引数 | 回復日数 |",
        "|-------------|--------|-----|--------|---------|---------|--------|----------|"
    ]
    
    for r in results:
        recovery_str = str(r['recovery']) if r['recovery'] >= 0 else "未回復"
        report_lines.append(
            f"| {r['entry_times']} | {r['pnl']:.2f} | {r['pf']:.2f} | "
            f"{r['sharpe']:.2f} | {r['dd_rate']:.2f} | {r['win_rate']:.2f} | "
            f"{r['trades']} | {recovery_str} |"
        )
    
    # Find best by different criteria
    best_pnl = max(results, key=lambda x: x['pnl'])
    best_sharpe = max(results, key=lambda x: x['sharpe'])
    best_dd = min(results, key=lambda x: x['dd_rate'])
    
    # Calculate risk-adjusted score (PnL / DD_rate * 100)
    for r in results:
        if r['dd_rate'] > 0:
            r['risk_adj_score'] = (r['pnl'] / r['dd_rate']) * 100
        else:
            r['risk_adj_score'] = r['pnl']
    
    best_risk_adj = max(results, key=lambda x: x['risk_adj_score'])
    
    report_lines.extend([
        "",
        "## ベスト指標",
        "",
        f"### 最高損益: entry_times={best_pnl['entry_times']}",
        f"- 総損益: {best_pnl['pnl']:.2f}",
        f"- PF: {best_pnl['pf']:.2f}, DD率: {best_pnl['dd_rate']:.2f}%",
        "",
        f"### 最高Sharpe: entry_times={best_sharpe['entry_times']}",
        f"- Sharpe: {best_sharpe['sharpe']:.2f}",
        f"- 損益: {best_sharpe['pnl']:.2f}, DD率: {best_sharpe['dd_rate']:.2f}%",
        "",
        f"### 最小DD率: entry_times={best_dd['entry_times']}",
        f"- DD率: {best_dd['dd_rate']:.2f}%",
        f"- 損益: {best_dd['pnl']:.2f}, PF: {best_dd['pf']:.2f}",
        "",
        f"### 最高リスク調整スコア: entry_times={best_risk_adj['entry_times']}",
        f"- スコア: {best_risk_adj['risk_adj_score']:.2f} (損益/DD率×100)",
        f"- 損益: {best_risk_adj['pnl']:.2f}, DD率: {best_risk_adj['dd_rate']:.2f}%",
        "",
        "## 推奨設定",
        ""
    ])
    
    # Recommendation logic
    if best_pnl['entry_times'] == best_risk_adj['entry_times']:
        report_lines.extend([
            f"**推奨: entry_times={best_pnl['entry_times']}**",
            "",
            "理由: 損益とリスク調整スコアの両方で最優秀",
            f"- 総損益: {best_pnl['pnl']:.2f}",
            f"- DD率: {best_pnl['dd_rate']:.2f}%",
            f"- Sharpe: {best_pnl['sharpe']:.2f}",
            f"- 取引数: {best_pnl['trades']}"
        ])
    elif best_sharpe['sharpe'] > 0.3 and best_sharpe['pnl'] > 20:
        report_lines.extend([
            f"**推奨: entry_times={best_sharpe['entry_times']}**",
            "",
            "理由: Sharpe高く安定的な収益",
            f"- Sharpe: {best_sharpe['sharpe']:.2f}",
            f"- 総損益: {best_sharpe['pnl']:.2f}",
            f"- DD率: {best_sharpe['dd_rate']:.2f}%"
        ])
    else:
        report_lines.extend([
            f"**推奨: entry_times={best_risk_adj['entry_times']}**",
            "",
            "理由: リスク調整後の収益性が最良",
            f"- リスク調整スコア: {best_risk_adj['risk_adj_score']:.2f}",
            f"- 総損益: {best_risk_adj['pnl']:.2f}",
            f"- DD率: {best_risk_adj['dd_rate']:.2f}%"
        ])
    
    # Write report
    report_path = sweep_dir / "pyramid_analysis.md"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(report_lines))
    
    print(f"分析レポート: {report_path}")
    print("\n" + "\n".join(report_lines))

if __name__ == "__main__":
    analyze_pyramid()
