#!/usr/bin/env python3
"""分類動的最適化: 月次MFE/MAE分布再計算とk2/k3推奨値算出

Usage:
  python tools/dynamic_classification_optimizer.py \
    --input report/trend_trades_20251121121336.json \
    --output report/classification_drift_analysis.json
  
機能:
  1. trend_trades から MFE/MAE vs ATR 分布を集計
  2. パーセンタイル分析で k2/k3 推奨値を算出
  3. 現設定 (k2=1.5, k3=1.2) との乖離を検出
  4. 月次分割再計算でドリフト追跡
  5. アラート判定 (閾値超過時に再最適化推奨)
"""
import argparse
import json
import statistics
from pathlib import Path
from typing import Dict, List, Tuple
import time


def load_trades(trades_path: str) -> List[Dict]:
    """トレードデータ読み込み"""
    with open(trades_path, 'r', encoding='utf-8') as f:
        trades = json.load(f)
    return trades


def compute_mfe_mae_distribution(trades: List[Dict]) -> Dict:
    """MFE/MAE 分布統計"""
    mfe_atr_ratios = []
    mae_atr_ratios = []
    
    for t in trades:
        mfe = t.get('mfe', 0.0)
        mae = t.get('mae', 0.0)
        atr = t.get('atr_at_entry', 1.0)
        
        if atr > 0:
            mfe_atr_ratios.append(mfe / atr)
            mae_atr_ratios.append(mae / atr)
    
    if not mfe_atr_ratios:
        return {}
    
    # パーセンタイル計算
    mfe_sorted = sorted(mfe_atr_ratios)
    mae_sorted = sorted(mae_atr_ratios)
    
    def percentile(data, p):
        k = (len(data) - 1) * p / 100
        f = int(k)
        c = f + 1 if f + 1 < len(data) else f
        return data[f] + (k - f) * (data[c] - data[f])
    
    return {
        'mfe_atr': {
            'mean': statistics.mean(mfe_atr_ratios),
            'median': statistics.median(mfe_atr_ratios),
            'p25': percentile(mfe_sorted, 25),
            'p50': percentile(mfe_sorted, 50),
            'p60': percentile(mfe_sorted, 60),
            'p70': percentile(mfe_sorted, 70),
            'p75': percentile(mfe_sorted, 75),
            'p80': percentile(mfe_sorted, 80),
            'std': statistics.stdev(mfe_atr_ratios) if len(mfe_atr_ratios) > 1 else 0.0,
            'count': len(mfe_atr_ratios)
        },
        'mae_atr': {
            'mean': statistics.mean(mae_atr_ratios),
            'median': statistics.median(mae_atr_ratios),
            'p25': percentile(mae_sorted, 25),
            'p50': percentile(mae_sorted, 50),
            'p60': percentile(mae_sorted, 60),
            'p70': percentile(mae_sorted, 70),
            'p75': percentile(mae_sorted, 75),
            'p80': percentile(mae_sorted, 80),
            'std': statistics.stdev(mae_atr_ratios) if len(mae_atr_ratios) > 1 else 0.0,
            'count': len(mae_atr_ratios)
        }
    }


def recommend_k2_k3(distribution: Dict) -> Tuple[float, float, str]:
    """k2, k3 推奨値算出
    
    推奨ロジック:
      k2 (TREND閾値): MFE/ATR の 60-70パーセンタイル (真のトレンドを捉える)
      k3 (FALSE_BREAK閾値): MAE/ATR の 60-70パーセンタイル (ダマシ検出)
    """
    if not distribution:
        return 1.5, 1.2, "データ不足"
    
    mfe_stats = distribution.get('mfe_atr', {})
    mae_stats = distribution.get('mae_atr', {})
    
    # k2: MFE p65 (中央値より上でトレンド判定)
    k2_candidate = (mfe_stats.get('p60', 1.5) + mfe_stats.get('p70', 1.5)) / 2
    # k3: MAE p65
    k3_candidate = (mae_stats.get('p60', 1.2) + mae_stats.get('p70', 1.2)) / 2
    
    # 丸め (0.1刻み)
    k2_recommend = round(k2_candidate / 0.1) * 0.1
    k3_recommend = round(k3_candidate / 0.1) * 0.1
    
    # 妥当性チェック (k2 > k3 を維持)
    if k2_recommend <= k3_recommend:
        k2_recommend = k3_recommend + 0.2
    
    # 範囲制約 (極端値回避)
    k2_recommend = max(1.0, min(k2_recommend, 4.0))
    k3_recommend = max(0.8, min(k3_recommend, 2.5))
    
    rationale = (f"k2={k2_recommend:.1f} (MFE p60-70={mfe_stats.get('p60', 0):.2f}-{mfe_stats.get('p70', 0):.2f}), "
                 f"k3={k3_recommend:.1f} (MAE p60-70={mae_stats.get('p60', 0):.2f}-{mae_stats.get('p70', 0):.2f})")
    
    return k2_recommend, k3_recommend, rationale


def detect_drift(current_k2: float, current_k3: float, 
                 recommended_k2: float, recommended_k3: float,
                 threshold_pct: float = 15.0) -> Dict:
    """ドリフト検出: 現設定と推奨値の乖離判定"""
    k2_drift_pct = abs((recommended_k2 - current_k2) / current_k2) * 100 if current_k2 > 0 else 0.0
    k3_drift_pct = abs((recommended_k3 - current_k3) / current_k3) * 100 if current_k3 > 0 else 0.0
    
    alert = (k2_drift_pct > threshold_pct) or (k3_drift_pct > threshold_pct)
    
    return {
        'current': {'k2': current_k2, 'k3': current_k3},
        'recommended': {'k2': recommended_k2, 'k3': recommended_k3},
        'drift': {
            'k2_abs': recommended_k2 - current_k2,
            'k2_pct': k2_drift_pct,
            'k3_abs': recommended_k3 - current_k3,
            'k3_pct': k3_drift_pct
        },
        'alert': alert,
        'threshold_pct': threshold_pct,
        'message': (f"⚠️ ドリフト検出: k2 {k2_drift_pct:.1f}%, k3 {k3_drift_pct:.1f}% (閾値 {threshold_pct}%)" 
                    if alert else "✅ 現設定は推奨範囲内")
    }


def monthly_segmentation_analysis(trades: List[Dict]) -> Dict:
    """月次分割再計算 (entry時刻ベース)"""
    from datetime import datetime
    from collections import defaultdict
    
    monthly_trades = defaultdict(list)
    
    for t in trades:
        # entry_price から推定できないため、realized_pnl から逆算不可
        # ここでは trade index を時系列順と仮定して12分割
        pass
    
    # 簡易版: 全体を N等分してドリフト追跡
    n_segments = 3  # 前期/中期/後期
    segment_size = len(trades) // n_segments if len(trades) >= n_segments else 1
    
    segments = {}
    for i in range(n_segments):
        start_idx = i * segment_size
        end_idx = start_idx + segment_size if i < n_segments - 1 else len(trades)
        segment_trades = trades[start_idx:end_idx]
        
        dist = compute_mfe_mae_distribution(segment_trades)
        k2_rec, k3_rec, _ = recommend_k2_k3(dist)
        
        segments[f'segment_{i+1}'] = {
            'trades_count': len(segment_trades),
            'distribution': dist,
            'recommended': {'k2': k2_rec, 'k3': k3_rec}
        }
    
    return segments


def generate_markdown_report(analysis: Dict, output_md: Path):
    """Markdown レポート生成"""
    with open(output_md, 'w', encoding='utf-8') as md:
        md.write("# 分類動的最適化分析レポート\n\n")
        md.write(f"**実行日時**: {analysis['timestamp']}\n")
        md.write(f"**入力データ**: {analysis['input_file']}\n")
        md.write(f"**トレード数**: {analysis['total_trades']}\n\n")
        
        md.write("## 全体MFE/MAE分布統計\n\n")
        
        dist = analysis.get('distribution', {})
        mfe_stats = dist.get('mfe_atr', {})
        mae_stats = dist.get('mae_atr', {})
        
        md.write("### MFE/ATR分布\n\n")
        md.write("| 統計量 | 値 |\n")
        md.write("|--------|----|\n")
        for key in ['mean', 'median', 'p60', 'p70', 'p75', 'std']:
            val = mfe_stats.get(key, 0)
            md.write(f"| {key} | {val:.2f} |\n")
        
        md.write("\n### MAE/ATR分布\n\n")
        md.write("| 統計量 | 値 |\n")
        md.write("|--------|----|\n")
        for key in ['mean', 'median', 'p60', 'p70', 'p75', 'std']:
            val = mae_stats.get(key, 0)
            md.write(f"| {key} | {val:.2f} |\n")
        
        md.write("\n## 推奨閾値\n\n")
        rec = analysis['recommendation']
        md.write(f"**k2 (TREND)**: {rec['k2']:.1f}  \n")
        md.write(f"**k3 (FALSE_BREAK)**: {rec['k3']:.1f}  \n")
        md.write(f"**根拠**: {rec['rationale']}\n\n")
        
        md.write("## ドリフト判定\n\n")
        drift = analysis['drift_detection']
        md.write(f"**現設定**: k2={drift['current']['k2']}, k3={drift['current']['k3']}  \n")
        md.write(f"**推奨値**: k2={drift['recommended']['k2']}, k3={drift['recommended']['k3']}  \n")
        md.write(f"**k2乖離**: {drift['drift']['k2_abs']:+.1f} ({drift['drift']['k2_pct']:.1f}%)  \n")
        md.write(f"**k3乖離**: {drift['drift']['k3_abs']:+.1f} ({drift['drift']['k3_pct']:.1f}%)  \n")
        md.write(f"**判定**: {drift['message']}\n\n")
        
        if drift['alert']:
            md.write("### ⚠️ 再最適化推奨アクション\n\n")
            md.write("```bash\n")
            md.write("# config.ini を更新\n")
            md.write(f"classification_k2 = {drift['recommended']['k2']:.1f}\n")
            md.write(f"classification_k3 = {drift['recommended']['k3']:.1f}\n")
            md.write("\n# グリッド探索で再検証\n")
            md.write("python tools/reclassify_trades_grid.py \\\n")
            md.write("  --input <latest_trend_trades.json> \\\n")
            md.write("  --output report/classification_grid_revalidation.json \\\n")
            md.write(f"  --k2-range '{drift['recommended']['k2']-0.3:.1f},{drift['recommended']['k2']:.1f},{drift['recommended']['k2']+0.3:.1f}' \\\n")
            md.write(f"  --k3-range '{drift['recommended']['k3']-0.2:.1f},{drift['recommended']['k3']:.1f},{drift['recommended']['k3']+0.2:.1f}'\n")
            md.write("```\n\n")
        
        md.write("## セグメント別分析\n\n")
        segments = analysis.get('segments', {})
        if segments:
            md.write("| セグメント | トレード数 | 推奨k2 | 推奨k3 |\n")
            md.write("|-----------|-----------|--------|--------|\n")
            for seg_name, seg_data in segments.items():
                count = seg_data['trades_count']
                k2 = seg_data['recommended']['k2']
                k3 = seg_data['recommended']['k3']
                md.write(f"| {seg_name} | {count} | {k2:.1f} | {k3:.1f} |\n")
            md.write("\n")
        
        md.write("---\n")
        md.write(f"**生成**: `{Path(__file__).name}`  \n")
        md.write(f"**詳細データ**: `{output_md.with_suffix('.json').name}`\n")
    
    print(f"✅ Markdownレポート: {output_md}")


def main():
    parser = argparse.ArgumentParser(description="分類動的最適化: MFE/MAE分布再計算とk2/k3推奨")
    parser.add_argument('--input', type=str, required=True,
                        help='入力trend_trades JSONパス')
    parser.add_argument('--output', type=str, default='report/classification_drift_analysis.json',
                        help='出力JSONパス (デフォルト: report/classification_drift_analysis.json)')
    parser.add_argument('--current-k2', type=float, default=1.5,
                        help='現在のk2設定 (デフォルト: 1.5)')
    parser.add_argument('--current-k3', type=float, default=1.2,
                        help='現在のk3設定 (デフォルト: 1.2)')
    parser.add_argument('--drift-threshold', type=float, default=15.0,
                        help='ドリフト警告閾値 (%) (デフォルト: 15.0)')
    args = parser.parse_args()
    
    print("=" * 70)
    print("分類動的最適化: MFE/MAE分布再計算")
    print("=" * 70)
    
    # 1. トレードデータ読み込み
    print(f"\n[1/5] トレードデータ読み込み: {args.input}")
    trades = load_trades(args.input)
    print(f"  トレード数: {len(trades)}")
    
    if not trades:
        print("⚠️ トレードデータが空です")
        return
    
    # 2. MFE/MAE分布統計
    print("\n[2/5] MFE/MAE分布統計計算...")
    distribution = compute_mfe_mae_distribution(trades)
    print(f"  MFE/ATR 平均: {distribution['mfe_atr']['mean']:.2f}, "
          f"中央値: {distribution['mfe_atr']['median']:.2f}")
    print(f"  MAE/ATR 平均: {distribution['mae_atr']['mean']:.2f}, "
          f"中央値: {distribution['mae_atr']['median']:.2f}")
    
    # 3. k2/k3推奨値算出
    print("\n[3/5] k2/k3推奨値算出...")
    k2_rec, k3_rec, rationale = recommend_k2_k3(distribution)
    print(f"  推奨k2: {k2_rec:.1f}")
    print(f"  推奨k3: {k3_rec:.1f}")
    print(f"  根拠: {rationale}")
    
    # 4. ドリフト検出
    print("\n[4/5] ドリフト検出...")
    drift_result = detect_drift(args.current_k2, args.current_k3, 
                                  k2_rec, k3_rec, args.drift_threshold)
    print(f"  {drift_result['message']}")
    
    # 5. セグメント別分析
    print("\n[5/5] セグメント別分析...")
    segments = monthly_segmentation_analysis(trades)
    print(f"  セグメント数: {len(segments)}")
    
    # 結果集約
    analysis = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'input_file': args.input,
        'total_trades': len(trades),
        'distribution': distribution,
        'recommendation': {
            'k2': k2_rec,
            'k3': k3_rec,
            'rationale': rationale
        },
        'drift_detection': drift_result,
        'segments': segments
    }
    
    # JSON出力
    output_json = Path(args.output)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2)
    print(f"\n✅ JSON出力: {output_json}")
    
    # Markdown出力
    output_md = output_json.with_suffix('.md')
    generate_markdown_report(analysis, output_md)
    
    print("\n" + "=" * 70)
    print("✅ 分類動的最適化完了")
    print("=" * 70)


if __name__ == '__main__':
    main()
