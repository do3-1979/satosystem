#!/usr/bin/env python3
"""
バックテスト結果指標表示デモンストレーション

現在の最新レポートを使用して、指標表示フォーマットをプレビュー
"""

import json
import os
import glob

def demo_metrics_display():
    """指標表示のデモンストレーション"""
    
    # 最新のレポートを取得
    report_dir = '/home/satoshi/work/satosystem/report'
    summary_files = sorted(
        glob.glob(os.path.join(report_dir, 'backtest_summary_*.json')),
        key=os.path.getmtime,
        reverse=True
    )
    
    if not summary_files:
        print("❌ レポートが見つかりません")
        return
    
    with open(summary_files[0], 'r') as f:
        report = json.load(f)
    
    # メトリクスを抽出
    pnl = report.get('total_pnl', 0)
    pf = report.get('profit_factor', 0)
    sharpe = report.get('sharpe', 0)
    win_rate = report.get('win_rate', 0)
    max_dd = report.get('max_drawdown', 0)
    recovery = report.get('recovery_period', -1)
    trades = report.get('trades', 0)
    
    print("\n" + "="*80)
    print("📊 バックテスト完了指標（デモンストレーション）")
    print("="*80)
    
    # 1行フォーマット
    print(f"\n【簡潔フォーマット】")
    print(f"PnL: ${pnl:>10.0f} | PF: {pf:>6.4f} | Sharpe: {sharpe:>7.4f} | Win%: {win_rate*100:>6.1f} | Trades: {trades:>3}")
    
    # テーブルフォーマット
    print(f"\n【詳細テーブル】")
    print("-"*80)
    print(f"指標                    | 値          | 評価         | 目標値")
    print("-"*80)
    
    # 各指標の評価
    def evaluate(name, value, target_min=None, target_max=None, reverse=False):
        if target_min is not None and target_max is not None:
            if reverse:
                ok = value <= target_max and value >= target_min
            else:
                ok = value >= target_min
            eval_str = "✅" if ok else "⚠️"
        else:
            eval_str = "-"
        return f"{name:<22} | {value:>10.4f} | {eval_str:<12} | {target_min}"
    
    print(f"{'損益 (PnL)':<22} | ${pnl:>9.0f} | {'✅' if pnl > 0 else '❌':<12} | > $0")
    print(f"{'プロフィットファクター':<22} | {pf:>10.4f} | {'✅' if pf > 1.5 else '⚠️' if pf > 1.0 else '❌':<12} | > 1.5")
    print(f"{'シャープレシオ':<22} | {sharpe:>10.4f} | {'✅' if sharpe > 1.0 else '⚠️' if sharpe > 0 else '❌':<12} | > 1.0")
    print(f"{'勝率':<22} | {win_rate*100:>9.1f}% | {'✅' if win_rate > 0.5 else '⚠️' if win_rate > 0.35 else '❌':<12} | > 50%")
    print(f"{'最大ドローダウン':<22} | ${max_dd:>9.0f} | {'⚠️':<12} | < $3000")
    print(f"{'復帰期間 (candles)':<22} | {recovery:>10} | {'✅' if recovery < 100 else '⚠️' if recovery > 0 else '❌':<12} | < 100")
    print(f"{'取引数':<22} | {trades:>10} | {'✅' if trades > 30 else '⚠️':<12} | > 30")
    
    print("-"*80)
    
    # 改善提案
    print(f"\n【改善提案】")
    suggestions = []
    
    if pnl < 0:
        suggestions.append("❌ PnL負: ストップロス戦略の見直し（stop_range拡大を検討）")
    
    if pf < 1.0:
        suggestions.append("⚠️ PF < 1.0: テイクプロフィット戦略が不足")
    
    if sharpe < 0:
        suggestions.append("❌ Sharpe < 0: リスク調整後リターンが悪い。ボラティリティベースのリスク管理を導入")
    
    if win_rate < 0.45:
        suggestions.append(f"⚠️ 勝率 {win_rate*100:.1f}%: Phase 1（STRONG_TREND のみ）の有効性を検証")
    
    if max_dd > 3000:
        suggestions.append(f"❌ Max DD ${max_dd:.0f}: risk_percentage を低下させるか、ドローダウン保護ロジックを導入")
    
    if trades < 30:
        suggestions.append(f"⚠️ 取引数 {trades}: バックテスト期間が短い可能性。データ不足の確認")
    
    if suggestions:
        for suggestion in suggestions:
            print(f"  {suggestion}")
    else:
        print("  ✅ すべての指標が良好です。本番導入を検討してください。")
    
    print("\n" + "="*80)
    
    # Q別結果の例を示す
    print("\n【Q別結果の組合せ例】")
    print("\n| Quarter | PnL(USD) | PF | Sharpe | Win% | Max DD(USD) | Recovery | Trades | 評価 |")
    print("|---------|----------|----|----|------|------------|----------|--------|------|")
    
    # デモデータ
    demo_quarters = [
        ("2024 Q1", -100, 0.8, -0.5, 40, 250, -1, 25, "⚠️"),
        ("2024 Q2", -500, 0.7, -1.2, 35, 600, -1, 20, "❌"),
        ("2024 Q3", 200, 1.2, 0.3, 52, 180, 45, 35, "✅"),
        ("2024 Q4", -300, 0.9, -0.8, 38, 450, -1, 28, "❌"),
        ("2025 Q1", 50, 1.0, -0.1, 48, 220, 30, 30, "⚠️"),
    ]
    
    for quarter, pnl, pf, sharpe, win, dd, recovery, trades, eval_str in demo_quarters:
        print(f"| {quarter:<8} | {pnl:>8} | {pf:>5.2f} | {sharpe:>6.2f} | {win:>4}% | {dd:>10} | {recovery:>8} | {trades:>6} | {eval_str:<4} |")
    
    print("\n凡例:")
    print("  ✅: 良好（改善提案なし）")
    print("  ⚠️: 要改善（1～2つの指標が悪化）")
    print("  ❌: 要注意（複数指標が悪化 or 極度に悪化）")
    
    print("\n"+"="*80)


if __name__ == '__main__':
    demo_metrics_display()
