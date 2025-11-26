#!/usr/bin/env python3
"""
Q別バックテスト結果サマリ抽出
既存のバックテスト結果から2024/2025年の主要指標を集計
"""

import json
import os
import glob
from datetime import datetime
from pathlib import Path

def analyze_existing_backtests():
    """既存のバックテスト結果を分析"""
    
    # 2024年のバックテスト結果を探索
    report_dir = '/home/satoshi/work/satosystem/report'
    
    quarters_data = {
        '2024_Q1': [],
        '2024_Q2': [],
        '2024_Q3': [],
        '2024_Q4': [],
        '2025_Q1': [],
        '2025_Q2': [],
        '2025_Q3': [],
    }
    
    # 利用可能なレポートを確認
    summary_files = sorted(
        glob.glob(os.path.join(report_dir, 'backtest_summary_*.json')),
        key=os.path.getmtime
    )
    
    if not summary_files:
        print("❌ バックテストレポートが見つかりません")
        return None
    
    print(f"✅ 利用可能なレポート: {len(summary_files)} 件")
    print(f"   最新: {os.path.basename(summary_files[-1])}")
    
    # 最新のレポートを読み込み
    with open(summary_files[-1], 'r') as f:
        latest_report = json.load(f)
    
    return latest_report


def format_metrics_table(report):
    """メトリクスをテーブル形式で表示"""
    
    print("\n" + "="*80)
    print("📊 バックテスト主要指標")
    print("="*80)
    
    print("\n【損益・パフォーマンス】")
    print(f"  総損益 (PnL):           ${report.get('total_pnl', 0):>10.2f}")
    print(f"  プロフィットファクター:  {report.get('profit_factor', 0):>10.4f}")
    print(f"  シャープレシオ:          {report.get('sharpe', 0):>10.4f}")
    
    print("\n【リスク管理】")
    print(f"  最大ドローダウン:        ${report.get('max_drawdown', 0):>10.2f}")
    print(f"  最大ドローダウン率:      {report.get('max_drawdown_rate', 0):>10.2f}%")
    print(f"  復帰期間:                {report.get('recovery_period', -1):>10} candles")
    
    print("\n【取引統計】")
    print(f"  勝率:                   {report.get('win_rate', 0)*100:>10.1f}%")
    print(f"  総トレード数:            {report.get('trades', 0):>10} 回")
    print(f"  キャンドル数:            {report.get('samples', 0):>10}")
    
    print("\n【市場レジーム分析】")
    regime_stats = report.get('regime_stats', {})
    if regime_stats:
        print(f"  現在レジーム:           {regime_stats.get('current_regime', 'N/A'):>20}")
        print(f"  レジーム変化回数:       {regime_stats.get('regime_change_count', 0):>20}")
        
        regime_pcts = regime_stats.get('regime_percentages', {})
        for regime, pct in regime_pcts.items():
            print(f"    - {regime:20s}: {pct:>18.1f}%")
        
        print(f"  平均ボラティリティ比:   {regime_stats.get('avg_volatility_ratio', 0):>10.4f}")
        print(f"  平均トレンド強度:       {regime_stats.get('avg_trend_strength', 0):>10.4f}")


def create_quarterly_template():
    """Q別レポートテンプレートを作成"""
    
    template = """
【Q別バックテスト結果テンプレート】

| Quarter | PnL | PF | Sharpe | Max DD | Recovery | Win% | Trades |
|---------|-----|----|----|--------|----------|------|--------|
| 2024 Q1 | ? | ? | ? | ? | ? | ? | ? |
| 2024 Q2 | ? | ? | ? | ? | ? | ? | ? |
| 2024 Q3 | ? | ? | ? | ? | ? | ? | ? |
| 2024 Q4 | ? | ? | ? | ? | ? | ? | ? |
| 2025 Q1 | ? | ? | ? | ? | ? | ? | ? |
| 2025 Q2 | ? | ? | ? | ? | ? | ? | ? |
| 2025 Q3 | ? | ? | ? | ? | ? | ? | ? |

※ 凡例:
  - PnL: 総損益（ドル）
  - PF: プロフィットファクター
  - Sharpe: シャープレシオ
  - Max DD: 最大ドローダウン（ドル）
  - Recovery: 復帰期間（キャンドル）
  - Win%: 勝率（パーセンテージ）
  - Trades: トレード数（回）
"""
    
    return template


def main():
    """メイン実行"""
    
    print("="*80)
    print("🔍 既存バックテスト結果の分析")
    print("="*80)
    
    report = analyze_existing_backtests()
    
    if not report:
        print("\n❌ 分析対象のレポートが見つかりません")
        return
    
    # メトリクスを表示
    format_metrics_table(report)
    
    # テンプレートを表示
    print(create_quarterly_template())
    
    print("\n"+"="*80)
    print("📝 次のステップ")
    print("="*80)
    print("""
1. quarterly_backtest_scheduler.py で優先度 HIGH を実行
   $ python3 quarterly_backtest_scheduler.py --priority high
   
   推定時間: 3～5時間
   対象: 2024 Q1, Q2, Q3 / 2025 Q1, Q3 (5期間 × 4パターン = 20バックテスト)

2. 実行完了後、結果を集計して上記テンプレートを埋める

3. 指標の改善案を検討:
   - シャープレシオ < 0: リスク調整后のリターン不足
   - プロフィットファクター < 1.5: 利益トレードの不足
   - 最大ドローダウン > 初期資金30%: リスク過大
   - 勝率 < 45%: エントリロジックの改善必要
""")


if __name__ == '__main__':
    main()
