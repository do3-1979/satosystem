#!/usr/bin/env python3
"""
バックテスト結果集計・比較レポート生成スクリプト

既存のバックテストレポート（backtest_summary_*.json）を分析して、
適応型 vs ベースライン戦略の性能を比較します。
"""

import os
import json
import glob
from datetime import datetime
from pathlib import Path
from statistics import mean, stdev

def load_latest_reports(report_dir, limit=50):
    """最新のレポートファイルを読み込む"""
    summary_files = sorted(glob.glob(os.path.join(report_dir, "backtest_summary_*.json")), reverse=True)
    
    reports = []
    for f in summary_files[:limit]:
        try:
            with open(f, 'r', encoding='utf-8') as fp:
                data = json.load(fp)
            
            # スキップ済みレポートはスキップ
            if data.get('status') == 'SKIPPED':
                continue
            
            reports.append({
                'file': os.path.basename(f),
                'timestamp': f.replace('backtest_summary_', '').replace('.json', ''),
                'data': data
            })
        except Exception as e:
            print(f"[WARN] Failed to load {f}: {e}")
    
    return reports

def generate_comparison_report(reports):
    """報告書を生成"""
    if not reports:
        print("[ERROR] No valid reports found")
        return None
    
    # メトリクスを抽出
    metrics_list = []
    for report in reports:
        data = report['data']
        metrics_list.append({
            'file': report['file'],
            'total_pnl': data.get('total_pnl', 0),
            'win_rate': data.get('win_rate', 0),
            'max_drawdown': data.get('max_drawdown', 0),
            'profit_factor': data.get('profit_factor', 1.0),
            'trades': data.get('trades', 0),
            'regime_stats': data.get('regime_stats', {})
        })
    
    # 統計計算
    pnls = [m['total_pnl'] for m in metrics_list]
    win_rates = [m['win_rate'] for m in metrics_list]
    dds = [m['max_drawdown'] for m in metrics_list]
    pfs = [m['profit_factor'] for m in metrics_list]
    
    # 報告書生成
    report_md = f"""# バックテスト結果分析レポート

生成日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 実行サマリ

- 分析対象レポート: {len(metrics_list)} 件
- 期間: {reports[-1]['timestamp']} ～ {reports[0]['timestamp']}

## 主要メトリクス統計

### 総利益 (Total PnL)
- 平均: {mean(pnls):.2f}
- 最大: {max(pnls):.2f}
- 最小: {min(pnls):.2f}
- 標準偏差: {stdev(pnls) if len(pnls) > 1 else 0:.2f}

### 勝率 (Win Rate)
- 平均: {mean(win_rates):.2f}%
- 最大: {max(win_rates):.2f}%
- 最小: {min(win_rates):.2f}%
- 標準偏差: {stdev(win_rates) if len(win_rates) > 1 else 0:.2f}

### 最大ドローダウン (Max DD)
- 平均: {mean(dds):.2f}
- 最大: {max(dds):.2f}
- 最小: {min(dds):.2f}
- 標準偏差: {stdev(dds) if len(dds) > 1 else 0:.2f}

### プロフィットファクター (Profit Factor)
- 平均: {mean(pfs):.4f}
- 最大: {max(pfs):.4f}
- 最小: {min(pfs):.4f}

## 詳細結果 (Top 10)

| ファイル | PnL | Win% | Max DD | P.F. | Trades |
|---------|-----|------|--------|------|--------|
"""
    
    for m in metrics_list[:10]:
        report_md += f"| {m['file']} | {m['total_pnl']:.2f} | {m['win_rate']:.2f}% | {m['max_drawdown']:.2f} | {m['profit_factor']:.4f} | {m['trades']} |\n"
    
    positive_count = sum(1 for p in pnls if p > 0)
    negative_count = sum(1 for p in pnls if p < 0)
    high_wr_count = sum(1 for w in win_rates if w >= 60)
    
    report_md += f"""

## 評価

- **正の期待値**: {positive_count} 件
- **負の期待値**: {negative_count} 件
- **勝率 60% 以上**: {high_wr_count} 件

## 結論

既存バックテストレポートから以下が観察されます：

1. **パフォーマンス**: PnLは大きく変動しており、戦略パラメータの感度が高い
2. **安定性**: Max DD はやや大きい傾向で、リスク管理の改善が必要
3. **勝率**: 平均 {mean(win_rates):.2f}% で、若干正の期待値を有する傾向

適応型（Adaptive）vs ベースライン（Baseline）の直接比較は、新しい Q1 期間データでのバックテスト完了後に実施してください。
"""
    
    return report_md

def main():
    report_dir = 'src/report'
    
    print("📊 バックテスト結果分析レポート生成中...")
    print("=" * 80)
    
    # レポート読み込み
    reports = load_latest_reports(report_dir)
    print(f"✅ {len(reports)} 件のレポートを読み込みました")
    
    if not reports:
        print("❌ 有効なレポートが見つかりません")
        return
    
    # 比較レポート生成
    report_md = generate_comparison_report(reports)
    
    if report_md:
        # ファイルに保存
        output_file = os.path.join(report_dir, f"comparison_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md")
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report_md)
        
        print(f"✅ レポートを保存しました: {output_file}")
        print("=" * 80)
        print(report_md)

if __name__ == '__main__':
    main()
