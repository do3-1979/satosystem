#!/usr/bin/env python3
"""
Phase 0: Mean Reversion 事前評価スクリプト (OHLCV直接分析版)

目的:
- 2025年の実際の価格データからBB 2σ逸脱後の平均回帰を分析
- 平均回帰発生率が60%以上ならPhase 1実装へ進む
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import statistics

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from price_data_management import PriceDataManagement
from ohlcv_cache import OHLCVCache
from config import Config


class BollingerBand:
    """Bollinger Band計算"""
    
    def __init__(self, period: int = 20, std_dev: float = 2.0):
        self.period = period
        self.std_dev = std_dev
    
    def calculate(self, closes: List[float]) -> Tuple[float, float, float]:
        """
        BB上限、中央、下限を計算
        
        Returns:
            (upper, middle, lower)
        """
        if len(closes) < self.period:
            return None, None, None
        
        recent = closes[-self.period:]
        middle = statistics.mean(recent)
        std = statistics.stdev(recent)
        
        upper = middle + (self.std_dev * std)
        lower = middle - (self.std_dev * std)
        
        return upper, middle, lower


class RSICalculator:
    """RSI計算"""
    
    def __init__(self, period: int = 14):
        self.period = period
    
    def calculate(self, closes: List[float]) -> float:
        """RSI値を計算"""
        if len(closes) < self.period + 1:
            return None
        
        deltas = [closes[i] - closes[i-1] for i in range(-self.period, 0)]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        
        avg_gain = sum(gains) / self.period
        avg_loss = sum(losses) / self.period
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi


def analyze_quarter_ohlcv(start_date: str, end_date: str, quarter_label: str) -> Dict:
    """
    OHLCV データから四半期の Mean Reversion 発生率を分析
    
    Args:
        start_date: "2025-01-01"
        end_date: "2025-03-31"
        quarter_label: "Q1"
    
    Returns:
        分析結果
    """
    print(f"\n📊 {quarter_label} 2025 分析開始 ({start_date} ~ {end_date})")
    
    # OHLCVキャッシュから直接データ取得
    cache = OHLCVCache()
    
    try:
        start_epoch = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp())
        end_epoch = int((datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)).timestamp())
        
        # 4時間足データを取得
        symbol = "BTC/USDT:USDT"  # Bybit形式
        timeframe = 240  # 分単位
        
        candles = cache.get_ohlcv_data(
            symbol=symbol,
            time_frame=timeframe,
            start_epoch=start_epoch,
            end_epoch=end_epoch
        )
        
        if not candles:
            print(f"❌ {quarter_label} のOHLCVデータが取得できませんでした")
            return {
                'quarter': quarter_label,
                'total_candles': 0,
                'bb_violations': 0,
                'mean_reversions': 0,
                'mean_reversion_rate': 0.0,
                'avg_success_price_change': 0.0,
                'avg_fail_price_change': 0.0
            }
        
        print(f"   取得キャンドル数: {len(candles)}")
        
    except Exception as e:
        print(f"❌ OHLCVデータ取得エラー: {e}")
        return {
            'quarter': quarter_label,
            'total_candles': 0,
            'bb_violations': 0,
            'mean_reversions': 0,
            'mean_reversion_rate': 0.0,
            'avg_success_price_change': 0.0,
            'avg_fail_price_change': 0.0
        }
    
    # BB & RSI 計算
    bb = BollingerBand(period=20, std_dev=2.0)
    rsi = RSICalculator(period=14)
    
    closes = [c[4] for c in candles]  # close価格
    bb_violation_events = []
    
    for i in range(30, len(candles)):  # 最初の30本はスキップ (BB+RSI計算に必要)
        current_closes = closes[:i+1]
        current_price = closes[i]
        
        # BB計算
        upper, middle, lower = bb.calculate(current_closes)
        rsi_value = rsi.calculate(current_closes)
        
        if lower is None or rsi_value is None:
            continue
        
        # BB下限違反 + RSI < 30
        if current_price < lower and rsi_value < 30:
            # 平均回帰の確認: 次の5-20本 (20-80時間) で価格がBB中央に戻ったか
            mean_reversion_occurred = False
            lookforward = min(20, len(closes) - i - 1)
            
            if lookforward > 0:
                future_closes = closes[i+1:i+1+lookforward]
                max_future_price = max(future_closes) if future_closes else current_price
                
                # BB中央を超えた = 平均回帰成功
                if max_future_price >= middle:
                    mean_reversion_occurred = True
            
            # 価格変化率を計算
            price_change_pct = ((max_future_price - current_price) / current_price * 100) if lookforward > 0 else 0
            
            bb_violation_events.append({
                'timestamp': candles[i][0],
                'price': current_price,
                'bb_lower': lower,
                'bb_middle': middle,
                'bb_upper': upper,
                'rsi': rsi_value,
                'deviation_pct': (current_price - lower) / lower * 100,
                'mean_reversion': mean_reversion_occurred,
                'max_future_price': max_future_price if lookforward > 0 else current_price,
                'price_change_pct': price_change_pct,
                'lookforward_candles': lookforward
            })
    
    # 統計計算
    total_violations = len(bb_violation_events)
    mean_reversions = sum(1 for e in bb_violation_events if e['mean_reversion'])
    mean_reversion_rate = (mean_reversions / total_violations * 100) if total_violations > 0 else 0
    
    # 平均回帰成功/失敗時の価格変化率
    success_price_changes = [e['price_change_pct'] for e in bb_violation_events if e['mean_reversion']]
    fail_price_changes = [e['price_change_pct'] for e in bb_violation_events if not e['mean_reversion']]
    
    avg_success_change = statistics.mean(success_price_changes) if success_price_changes else 0
    avg_fail_change = statistics.mean(fail_price_changes) if fail_price_changes else 0
    
    result = {
        'quarter': quarter_label,
        'total_candles': len(candles),
        'bb_violations': total_violations,
        'mean_reversions': mean_reversions,
        'mean_reversion_rate': mean_reversion_rate,
        'avg_success_price_change': avg_success_change,
        'avg_fail_price_change': avg_fail_change,
        'sample_events': bb_violation_events[:10]  # サンプル10件
    }
    
    return result


def main():
    """Phase 0 メイン実行"""
    print("=" * 70)
    print("Phase 0: Mean Reversion 事前評価 (OHLCV直接分析)")
    print("=" * 70)
    
    # 2025年四半期定義
    quarters = [
        ("2025-01-01", "2025-03-31", "Q1"),
        ("2025-04-01", "2025-06-30", "Q2"),
        ("2025-07-01", "2025-09-30", "Q3"),
        ("2025-10-01", "2025-12-31", "Q4"),
    ]
    
    all_results = []
    
    for start, end, label in quarters:
        result = analyze_quarter_ohlcv(start, end, label)
        all_results.append(result)
        
        print(f"\n{'='*60}")
        print(f"📈 {label} 2025 結果:")
        print(f"{'='*60}")
        print(f"   総キャンドル数:      {result['total_candles']}")
        print(f"   BB 2σ逸脱 (RSI<30): {result['bb_violations']} 回")
        print(f"   平均回帰成功:        {result['mean_reversions']} 回")
        print(f"   平均回帰率:          {result['mean_reversion_rate']:.1f}%")
        print(f"   成功時価格変化:      +{result['avg_success_price_change']:.2f}%")
        print(f"   失敗時価格変化:      {result['avg_fail_price_change']:.2f}%")
        
        # サンプルイベント表示
        if result.get('sample_events'):
            print(f"\n   📋 サンプルイベント (最初3件):")
            for i, event in enumerate(result['sample_events'][:3], 1):
                status = "✅ 回帰成功" if event['mean_reversion'] else "❌ 回帰失敗"
                dt = datetime.fromtimestamp(event['timestamp'] / 1000).strftime('%Y-%m-%d %H:%M')
                print(f"      {i}. {dt}: "
                      f"Price=${event['price']:.2f}, "
                      f"BB下限=${event['bb_lower']:.2f}, "
                      f"逸脱={event['deviation_pct']:.2f}%, "
                      f"RSI={event['rsi']:.1f}, "
                      f"{status}, "
                      f"変化={event['price_change_pct']:.2f}%")
    
    # 総合評価
    print(f"\n{'='*70}")
    print(f"📊 総合評価 (2025年全体)")
    print(f"{'='*70}")
    
    total_violations = sum(r['bb_violations'] for r in all_results)
    total_reversions = sum(r['mean_reversions'] for r in all_results)
    overall_rate = (total_reversions / total_violations * 100) if total_violations > 0 else 0
    
    all_success_changes = []
    all_fail_changes = []
    for r in all_results:
        for event in r.get('sample_events', []):
            if event['mean_reversion']:
                all_success_changes.append(event['price_change_pct'])
            else:
                all_fail_changes.append(event['price_change_pct'])
    
    avg_overall_success = statistics.mean(all_success_changes) if all_success_changes else 0
    avg_overall_fail = statistics.mean(all_fail_changes) if all_fail_changes else 0
    
    print(f"   BB 2σ逸脱総数:   {total_violations} 回")
    print(f"   平均回帰成功:     {total_reversions} 回")
    print(f"   平均回帰率:       {overall_rate:.1f}%")
    print(f"   成功時価格変化:   +{avg_overall_success:.2f}%")
    print(f"   失敗時価格変化:   {avg_overall_fail:.2f}%")
    
    # Go/No-Go判断
    print(f"\n{'='*70}")
    print(f"🔍 Go/No-Go 判断")
    print(f"{'='*70}")
    
    if overall_rate >= 60:
        print(f"✅ GO: 平均回帰率 {overall_rate:.1f}% ≥ 60%")
        print(f"   → Phase 1 (最小実装) に進むことを推奨")
        go_decision = "GO"
    elif overall_rate >= 50:
        print(f"⚠️ CONDITIONAL: 平均回帰率 {overall_rate:.1f}% (50-60%)")
        print(f"   → Phase 1実装は可能だが、慎重な評価が必要")
        go_decision = "CONDITIONAL"
    else:
        print(f"❌ NO-GO: 平均回帰率 {overall_rate:.1f}% < 50%")
        print(f"   → Mean Reversion戦略は2025年市場に不適合")
        print(f"   → Task 38c (Range Breakout Enhanced) を検討推奨")
        go_decision = "NO-GO"
    
    # レポート保存
    import json
    
    report = {
        'evaluation_date': datetime.now().isoformat(),
        'phase': 'Phase 0',
        'data_source': 'OHLCV (4h candles)',
        'quarterly_results': all_results,
        'overall_statistics': {
            'total_bb_violations': total_violations,
            'total_mean_reversions': total_reversions,
            'mean_reversion_rate': overall_rate,
            'avg_success_price_change': avg_overall_success,
            'avg_fail_price_change': avg_overall_fail
        },
        'decision': go_decision,
        'recommendation': {
            'GO': 'Phase 1実装に進む',
            'CONDITIONAL': 'Phase 1実装は可能だが慎重評価',
            'NO-GO': 'Mean Reversion不採用、Task 38c検討'
        }.get(go_decision, '')
    }
    
    report_path = "docs/analysis/mean_reversion_phase0_evaluation.json"
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n💾 評価レポート保存: {report_path}")
    
    # Markdown レポートも生成
    md_report_path = "docs/analysis/mean_reversion_phase0_evaluation.md"
    with open(md_report_path, 'w') as f:
        f.write("# Mean Reversion Phase 0 評価結果\n\n")
        f.write(f"**評価日**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**データソース**: OHLCV 4時間足データ (BTC/USDT)\n\n")
        f.write(f"**目的**: 2025年市場でBB 2σ逸脱+RSI<30後に平均回帰が発生しているか確認\n\n")
        f.write("## 四半期別結果\n\n")
        f.write("| 四半期 | キャンドル数 | BB逸脱 | 平均回帰 | 回帰率 | 成功時変化 | 失敗時変化 |\n")
        f.write("|--------|-------------|--------|---------|--------|-----------|------------|\n")
        for r in all_results:
            f.write(f"| {r['quarter']} 2025 | {r['total_candles']} | {r['bb_violations']} | "
                   f"{r['mean_reversions']} | {r['mean_reversion_rate']:.1f}% | "
                   f"+{r['avg_success_price_change']:.2f}% | {r['avg_fail_price_change']:.2f}% |\n")
        
        f.write(f"\n## 総合評価\n\n")
        f.write(f"- **BB 2σ逸脱総数**: {total_violations} 回\n")
        f.write(f"- **平均回帰成功**: {total_reversions} 回\n")
        f.write(f"- **平均回帰率**: {overall_rate:.1f}%\n")
        f.write(f"- **成功時価格変化**: +{avg_overall_success:.2f}%\n")
        f.write(f"- **失敗時価格変化**: {avg_overall_fail:.2f}%\n\n")
        
        f.write(f"## 判定結果\n\n")
        if go_decision == "GO":
            f.write(f"✅ **GO**: 平均回帰率 {overall_rate:.1f}% ≥ 60%\n\n")
            f.write(f"→ **Phase 1 (最小実装) に進むことを推奨**\n\n")
            f.write(f"**理由**:\n")
            f.write(f"- BB 2σ逸脱+RSI<30後に高確率で平均回帰が発生\n")
            f.write(f"- 成功時の平均価格上昇: +{avg_overall_success:.2f}%\n")
            f.write(f"- 2025年レンジ相場に適合する戦略\n")
        elif go_decision == "CONDITIONAL":
            f.write(f"⚠️ **CONDITIONAL**: 平均回帰率 {overall_rate:.1f}% (50-60%)\n\n")
            f.write(f"→ Phase 1実装は可能だが、慎重な評価が必要\n\n")
            f.write(f"**注意点**:\n")
            f.write(f"- 平均回帰率が基準値(60%)をわずかに下回る\n")
            f.write(f"- Q1評価で厳格なPF基準(>0.8)を適用\n")
            f.write(f"- 早期に問題が見つかった場合は撤退\n")
        else:
            f.write(f"❌ **NO-GO**: 平均回帰率 {overall_rate:.1f}% < 50%\n\n")
            f.write(f"→ Mean Reversion戦略は2025年市場に不適合\n\n")
            f.write(f"→ Task 38c (Range Breakout Enhanced) を検討推奨\n\n")
            f.write(f"**却下理由**:\n")
            f.write(f"- BB 2σ逸脱後の平均回帰発生率が50%未満\n")
            f.write(f"- ランダムトレード(50%)と同等以下の効果\n")
            f.write(f"- 実装コストに見合う効果が期待できない\n")
    
    print(f"💾 Markdownレポート保存: {md_report_path}")
    print(f"\n{'='*70}")
    print(f"Phase 0 評価完了")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
