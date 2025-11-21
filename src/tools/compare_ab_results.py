"""
A/B実験結果比較スクリプト(簡略版)
baseline vs keltner_enabled vs pyramid_3 の比較レポート生成
"""
import json
from pathlib import Path

def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def format_diff(baseline, variant):
    """差分を計算し符号付き文字列で返す"""
    if baseline is None or variant is None:
        return "N/A"
    diff = variant - baseline
    sign = "+" if diff > 0 else ""
    return f"{sign}{diff:.2f}"

def format_percent_diff(baseline, variant):
    """パーセント差分を計算"""
    if baseline is None or variant is None or baseline == 0:
        return "N/A"
    diff_pct = ((variant - baseline) / abs(baseline)) * 100
    sign = "+" if diff_pct > 0 else ""
    return f"{sign}{diff_pct:.1f}%"

def main():
    report_dir = Path("report/ab_experiments")
    
    # Load summaries
    baseline_path = Path("src/report/backtest_summary_20251121092441.json")
    keltner_path = report_dir / "ab_test_keltner_enabled_summary.json"
    pyramid_path = report_dir / "ab_test_pyramid_3_summary.json"
    
    if not baseline_path.exists():
        print(f"ベースライン結果なし: {baseline_path}")
        return
    
    baseline = load_json(baseline_path)
    
    # Load variants
    results = {
        "baseline": baseline,
        "keltner_enabled": load_json(keltner_path) if keltner_path.exists() else None,
        "pyramid_3": load_json(pyramid_path) if pyramid_path.exists() else None
    }
    
    # Generate markdown report
    report_lines = [
        "# A/B実験比較レポート",
        "",
        f"**期間**: 2025/10/01 - 2025/11/01",
        "",
        "## 実験サマリー",
        "",
        "| 実験名 | 説明 | 変更パラメータ |",
        "|--------|------|----------------|",
        "| baseline | ベースライン(10月) | keltner_enabled=False, entry_times=10 |",
        "| keltner_enabled | Keltnerフィルタ有効化 | keltner_enabled=True |",
        "| pyramid_3 | ピラミッディング制限 | entry_times=3 |",
        "",
        "## 主要指標比較",
        "",
    ]
    
    # Metrics table
    metrics = [
        ("total_pnl", "総損益"),
        ("profit_factor", "プロフィットファクター"),
        ("sharpe_ratio", "シャープレシオ"),
        ("max_drawdown_rate", "最大DD率(%)"),
        ("win_rate", "勝率(%)"),
        ("total_trades", "総取引回数"),
    ]
    
    report_lines.append("| 指標 | baseline | keltner_enabled | 差分 | pyramid_3 | 差分 |")
    report_lines.append("|------|----------|-----------------|------|-----------|------|")
    
    for key, label in metrics:
        baseline_val = baseline.get(key, 0)
        keltner_val = results["keltner_enabled"].get(key, 0) if results["keltner_enabled"] else None
        pyramid_val = results["pyramid_3"].get(key, 0) if results["pyramid_3"] else None
        
        keltner_diff = format_diff(baseline_val, keltner_val) if keltner_val is not None else "N/A"
        pyramid_diff = format_diff(baseline_val, pyramid_val) if pyramid_val is not None else "N/A"
        
        # Format values with proper handling
        baseline_str = f"{baseline_val:.2f}" if baseline_val is not None else "0.00"
        keltner_str = f"{keltner_val:.2f}" if keltner_val is not None else "N/A"
        pyramid_str = f"{pyramid_val:.2f}" if pyramid_val is not None else "N/A"
        
        report_lines.append(
            f"| {label} | {baseline_str} | {keltner_str} | {keltner_diff} | {pyramid_str} | {pyramid_diff} |"
        )
    
    report_lines.extend([
        "",
        "## 分析",
        "",
        "### Keltnerフィルタ効果",
        "",
    ])
    
    if results["keltner_enabled"]:
        k_trades = results["keltner_enabled"].get("total_trades", 0)
        b_trades = baseline.get("total_trades", 1)
        trade_reduction = ((b_trades - k_trades) / b_trades * 100) if b_trades > 0 else 0
        
        k_pnl = results["keltner_enabled"].get("total_pnl", 0)
        b_pnl = baseline.get("total_pnl", 0)
        pnl_impact = format_percent_diff(b_pnl, k_pnl)
        
        report_lines.extend([
            f"- 取引回数変化: {b_trades} → {k_trades} ({trade_reduction:+.1f}%)",
            f"- 損益変化: {pnl_impact}",
            f"- 勝率変化: {baseline.get('win_rate', 0):.1f}% → {results['keltner_enabled'].get('win_rate', 0):.1f}%",
            "",
        ])
    else:
        report_lines.append("- データなし")
    
    report_lines.extend([
        "### ピラミッディング制限効果",
        "",
    ])
    
    if results["pyramid_3"]:
        p_dd = results["pyramid_3"].get("max_drawdown_rate", 0)
        b_dd = baseline.get("max_drawdown_rate", 0)
        dd_reduction = b_dd - p_dd
        
        p_pnl = results["pyramid_3"].get("total_pnl", 0)
        b_pnl = baseline.get("total_pnl", 0)
        pnl_impact = format_percent_diff(b_pnl, p_pnl)
        
        report_lines.extend([
            f"- DD率変化: {b_dd:.2f}% → {p_dd:.2f}% ({dd_reduction:+.2f}%ポイント)",
            f"- 損益変化: {pnl_impact}",
            f"- PF変化: {baseline.get('profit_factor', 0):.2f} → {results['pyramid_3'].get('profit_factor', 0):.2f}",
            "",
        ])
    else:
        report_lines.append("- データなし")
    
    # Write report
    output_path = report_dir / "ab_comparison_simple.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(report_lines))
    
    print(f"比較レポート生成完了: {output_path}")
    print("\n" + "\n".join(report_lines))

if __name__ == "__main__":
    main()
