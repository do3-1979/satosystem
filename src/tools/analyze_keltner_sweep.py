#!/usr/bin/env python3
"""
Keltnerパラメータスイープ結果分析
各パラメータ組み合わせの効果を比較し、ベースライン(Keltner無効)との差分を評価
"""
import json
from pathlib import Path
import sys

def load_summary(path):
    """Load JSON summary file."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {path}: {e}")
        return None

def analyze_sweep():
    """Analyze Keltner parameter sweep results."""
    sweep_dir = Path("report/keltner_sweep")
    # Prefer dedicated A/B baseline summary if exists (Keltner無効結果)
    ab_baseline = Path("report/ab_experiments/ab_test_keltner_baseline_summary.json")
    legacy_baseline = Path("src/report/backtest_summary_20251121092441.json")
    if ab_baseline.exists():
        baseline_path = ab_baseline
    else:
        baseline_path = legacy_baseline
    
    if not baseline_path.exists():
        print(f"Baseline not found: {baseline_path}")
        return
    
    baseline = load_summary(baseline_path)
    if not baseline:
        print("Failed to load baseline")
        return
    
    # Collect all sweep results
    results = []
    for summary_file in sorted(sweep_dir.glob("*_summary.json")):
        config_name = summary_file.stem.replace("_summary", "")
        data = load_summary(summary_file)
        if data:
            # Parse parameters from filename: keltner_ema10_atr1.5
            parts = config_name.replace("keltner_ema", "").split("_atr")
            if len(parts) == 2:
                ema = int(parts[0])
                atr_mult = float(parts[1])
                
                results.append({
                    'config': config_name,
                    'ema': ema,
                    'atr_mult': atr_mult,
                    'pnl': data.get('total_pnl', 0),
                    'pf': data.get('profit_factor', 0),
                    'dd_rate': data.get('max_drawdown_rate', 0),
                    'win_rate': data.get('win_rate', 0),
                    'trades': data.get('trades', 0),
                    'sharpe': data.get('sharpe', 0)
                })
    
    if not results:
        print("No sweep results found")
        return
    
    # Sort by PnL descending
    results.sort(key=lambda x: x['pnl'], reverse=True)
    
    # Generate report
    report_lines = [
        "# Keltnerパラメータスイープ分析",
        "",
        f"**ベースライン** (Keltner無効): PnL={baseline.get('total_pnl', 0):.2f}, PF={baseline.get('profit_factor', 0):.2f}, DD率={baseline.get('max_drawdown_rate', 0):.2f}%, 勝率={baseline.get('win_rate', 0):.2f}%, 取引数={baseline.get('trades', 0)}",
        "",
        "## 結果一覧（損益順）",
        "",
        "| 順位 | EMA | ATR×倍率 | 総損益 | 差分 | PF | DD率(%) | 勝率(%) | 取引数 |",
        "|------|-----|----------|--------|------|-----|---------|---------|--------|"
    ]
    
    baseline_pnl = baseline.get('total_pnl', 0)
    
    for rank, r in enumerate(results, 1):
        pnl_diff = r['pnl'] - baseline_pnl
        pnl_diff_str = f"+{pnl_diff:.2f}" if pnl_diff > 0 else f"{pnl_diff:.2f}"
        
        report_lines.append(
            f"| {rank} | {r['ema']} | {r['atr_mult']:.1f} | "
            f"{r['pnl']:.2f} | {pnl_diff_str} | "
            f"{r['pf']:.2f} | {r['dd_rate']:.2f} | "
            f"{r['win_rate']:.2f} | {r['trades']} |"
        )
    
    report_lines.extend([
        "",
        "## トップ3分析",
        ""
    ])
    
    for i, r in enumerate(results[:3], 1):
        pnl_improve = ((r['pnl'] - baseline_pnl) / abs(baseline_pnl) * 100) if baseline_pnl != 0 else 0
        dd_improve = baseline.get('max_drawdown_rate', 0) - r['dd_rate']
        
        report_lines.extend([
            f"### {i}位: EMA={r['ema']}, ATR×{r['atr_mult']:.1f}",
            "",
            f"- **損益**: {r['pnl']:.2f} (ベースライン比: {pnl_improve:+.1f}%)",
            f"- **PF**: {r['pf']:.2f}",
            f"- **DD率改善**: {dd_improve:+.2f}%ポイント",
            f"- **勝率**: {r['win_rate']:.2f}%",
            f"- **取引数**: {r['trades']}",
            ""
        ])
    
    # Find configs better than baseline
    better_count = sum(1 for r in results if r['pnl'] > baseline_pnl)
    
    report_lines.extend([
        "## 総括",
        "",
        f"- 検証パラメータ組み合わせ数: {len(results)}",
        f"- ベースライン超え: {better_count}/{len(results)} ({better_count/len(results)*100:.1f}%)",
        ""
    ])
    
    if better_count == 0:
        report_lines.extend([
            "**結論**: Keltnerフィルタは押し目買いロジックでもベースラインを超える効果なし。",
            "→ **不採用**を推奨"
        ])
    else:
        best = results[0]
        report_lines.extend([
            f"**ベストパラメータ**: EMA={best['ema']}, ATR×{best['atr_mult']:.1f}",
            f"- 損益改善: {((best['pnl'] - baseline_pnl) / abs(baseline_pnl) * 100):+.1f}%",
            f"- DD率改善: {(baseline.get('max_drawdown_rate', 0) - best['dd_rate']):+.2f}%ポイント"
        ])
    
    # Write report
    report_path = sweep_dir / "keltner_sweep_analysis.md"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(report_lines))
    
    print(f"分析レポート生成: {report_path}")
    print("\n" + "\n".join(report_lines))

if __name__ == "__main__":
    analyze_sweep()
