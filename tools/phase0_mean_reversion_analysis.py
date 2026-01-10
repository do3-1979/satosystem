#!/usr/bin/env python3
"""
Phase 0: Mean Reversion 事前評価スクリプト

目的:
- 2025年市場でBB 2σ逸脱後に平均回帰が発生しているか確認
- 平均回帰発生率が60%以上ならPhase 1実装へ進む
"""

import json
import glob
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple
import statistics

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))


class BollingerBand:
    """Bollinger Band計算"""
    
    def __init__(self, period: int = 20, std_dev: float = 2.0):
        self.period = period
        self.std_dev = std_dev
    
    def calculate(self, prices: List[float]) -> Tuple[float, float, float]:
        """
        BB上限、中央、下限を計算
        
        Returns:
            (upper, middle, lower)
        """
        if len(prices) < self.period:
            return None, None, None
        
        recent = prices[-self.period:]
        middle = statistics.mean(recent)
        std = statistics.stdev(recent)
        
        upper = middle + (self.std_dev * std)
        lower = middle - (self.std_dev * std)
        
        return upper, middle, lower


class RSICalculator:
    """RSI計算"""
    
    def __init__(self, period: int = 14):
        self.period = period
    
    def calculate(self, prices: List[float]) -> float:
        """RSI値を計算"""
        if len(prices) < self.period + 1:
            return None
        
        deltas = [prices[i] - prices[i-1] for i in range(-self.period, 0)]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        
        avg_gain = sum(gains) / self.period
        avg_loss = sum(losses) / self.period
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi


def load_2025_quarter_logs(quarter: str) -> List[Dict]:
    """
    2025年の四半期ログを読み込む
    
    Args:
        quarter: "Q1", "Q2", "Q3", "Q4"
    
    Returns:
        トレードログのリスト
    """
    # パターン1: logs/quarterly/backtest_2025_Q*_*.json
    log_files = sorted(glob.glob(f"logs/quarterly/backtest_2025_{quarter}_*.json"))
    
    # パターン2: logs/quarterly/Q*_2025_*.json
    if not log_files:
        log_files = sorted(glob.glob(f"logs/quarterly/{quarter}_2025_*.json"))
    
    if not log_files:
        print(f"❌ {quarter} 2025のログが見つかりません")
        return []
    
    # 最新のログファイルを使用
    log_file = log_files[-1]
    print(f"📂 読み込み: {log_file}")
    
    try:
        with open(log_file, 'r') as f:
            data = json.load(f)
            return data.get('trades', [])
    except Exception as e:
        print(f"❌ ログ読み込みエラー: {e}")
        return []


def analyze_mean_reversion_potential(trades: List[Dict], quarter: str) -> Dict:
    """
    Mean Reversion発生率を分析
    
    戦略:
    1. エントリー時の価格がBB下限を下回っているか
    2. RSI < 30 (売られすぎ)
    3. その後、価格がBB中央に戻ったか (平均回帰成功)
    
    Returns:
        分析結果の辞書
    """
    bb_calculator = BollingerBand(period=20, std_dev=2.0)
    rsi_calculator = RSICalculator(period=14)
    
    print(f"\n📊 {quarter} 2025 分析開始")
    print(f"   総トレード数: {len(trades)}")
    
    # 価格履歴を構築
    price_history = []
    bb_violation_events = []  # BB 2σ逸脱イベント
    
    for i, trade in enumerate(trades):
        entry_price = trade.get('entry_price', 0)
        exit_price = trade.get('exit_price', 0)
        
        if entry_price == 0:
            continue
        
        price_history.append(entry_price)
        
        # BB計算
        if len(price_history) >= 20:
            upper, middle, lower = bb_calculator.calculate(price_history)
            rsi = rsi_calculator.calculate(price_history)
            
            # BB下限違反 + RSI < 30 のケースを記録
            if lower is not None and entry_price < lower:
                if rsi is not None and rsi < 30:
                    # 平均回帰の確認: 次の5-10トレードで価格がBB中央に戻ったか
                    future_prices = []
                    for j in range(i+1, min(i+11, len(trades))):
                        future_price = trades[j].get('entry_price', 0)
                        if future_price > 0:
                            future_prices.append(future_price)
                    
                    # 平均回帰判定: 将来価格の最高値がBB中央を超える
                    mean_reversion_occurred = False
                    if future_prices:
                        max_future_price = max(future_prices)
                        if max_future_price >= middle:
                            mean_reversion_occurred = True
                    
                    bb_violation_events.append({
                        'trade_index': i,
                        'entry_price': entry_price,
                        'bb_lower': lower,
                        'bb_middle': middle,
                        'bb_upper': upper,
                        'rsi': rsi,
                        'deviation': (entry_price - lower) / lower * 100,  # %
                        'mean_reversion': mean_reversion_occurred,
                        'exit_price': exit_price,
                        'pnl': trade.get('pnl', 0)
                    })
        
        # Exit価格も追加
        if exit_price > 0:
            price_history.append(exit_price)
    
    # 統計計算
    total_violations = len(bb_violation_events)
    mean_reversions = sum(1 for e in bb_violation_events if e['mean_reversion'])
    mean_reversion_rate = (mean_reversions / total_violations * 100) if total_violations > 0 else 0
    
    # 平均回帰成功時のPnL分析
    mr_success_pnl = [e['pnl'] for e in bb_violation_events if e['mean_reversion']]
    mr_fail_pnl = [e['pnl'] for e in bb_violation_events if not e['mean_reversion']]
    
    avg_success_pnl = statistics.mean(mr_success_pnl) if mr_success_pnl else 0
    avg_fail_pnl = statistics.mean(mr_fail_pnl) if mr_fail_pnl else 0
    
    result = {
        'quarter': quarter,
        'total_trades': len(trades),
        'bb_violations': total_violations,
        'mean_reversions': mean_reversions,
        'mean_reversion_rate': mean_reversion_rate,
        'avg_success_pnl': avg_success_pnl,
        'avg_fail_pnl': avg_fail_pnl,
        'events': bb_violation_events[:10]  # サンプル10件
    }
    
    return result


def main():
    """Phase 0 メイン実行"""
    print("=" * 70)
    print("Phase 0: Mean Reversion 事前評価")
    print("=" * 70)
    
    quarters = ["Q1", "Q2", "Q3", "Q4"]
    all_results = []
    
    for quarter in quarters:
        trades = load_2025_quarter_logs(quarter)
        if not trades:
            continue
        
        result = analyze_mean_reversion_potential(trades, quarter)
        all_results.append(result)
        
        print(f"\n{'='*60}")
        print(f"📈 {quarter} 2025 結果:")
        print(f"{'='*60}")
        print(f"   総トレード数:        {result['total_trades']}")
        print(f"   BB 2σ逸脱 (RSI<30): {result['bb_violations']} 回")
        print(f"   平均回帰成功:        {result['mean_reversions']} 回")
        print(f"   平均回帰率:          {result['mean_reversion_rate']:.1f}%")
        print(f"   成功時平均PnL:       ${result['avg_success_pnl']:.2f}")
        print(f"   失敗時平均PnL:       ${result['avg_fail_pnl']:.2f}")
        
        # サンプルイベント表示
        if result['events']:
            print(f"\n   📋 サンプルイベント (最初5件):")
            for i, event in enumerate(result['events'][:5], 1):
                status = "✅ 回帰成功" if event['mean_reversion'] else "❌ 回帰失敗"
                print(f"      {i}. Trade #{event['trade_index']}: "
                      f"Entry=${event['entry_price']:.2f}, "
                      f"BB下限=${event['bb_lower']:.2f}, "
                      f"逸脱={event['deviation']:.2f}%, "
                      f"RSI={event['rsi']:.1f}, "
                      f"{status}, "
                      f"PnL=${event['pnl']:.2f}")
    
    # 総合評価
    print(f"\n{'='*70}")
    print(f"📊 総合評価 (2025年全体)")
    print(f"{'='*70}")
    
    total_violations = sum(r['bb_violations'] for r in all_results)
    total_reversions = sum(r['mean_reversions'] for r in all_results)
    overall_rate = (total_reversions / total_violations * 100) if total_violations > 0 else 0
    
    all_success_pnl = []
    all_fail_pnl = []
    for r in all_results:
        trades = load_2025_quarter_logs(r['quarter'])
        for event in r['events']:
            if event['mean_reversion']:
                all_success_pnl.append(event['pnl'])
            else:
                all_fail_pnl.append(event['pnl'])
    
    avg_overall_success = statistics.mean(all_success_pnl) if all_success_pnl else 0
    avg_overall_fail = statistics.mean(all_fail_pnl) if all_fail_pnl else 0
    
    print(f"   BB 2σ逸脱総数:   {total_violations} 回")
    print(f"   平均回帰成功:     {total_reversions} 回")
    print(f"   平均回帰率:       {overall_rate:.1f}%")
    print(f"   成功時平均PnL:    ${avg_overall_success:.2f}")
    print(f"   失敗時平均PnL:    ${avg_overall_fail:.2f}")
    
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
    report = {
        'evaluation_date': datetime.now().isoformat(),
        'phase': 'Phase 0',
        'quarterly_results': all_results,
        'overall_statistics': {
            'total_bb_violations': total_violations,
            'total_mean_reversions': total_reversions,
            'mean_reversion_rate': overall_rate,
            'avg_success_pnl': avg_overall_success,
            'avg_fail_pnl': avg_overall_fail
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
        f.write(f"**目的**: 2025年市場でBB 2σ逸脱後に平均回帰が発生しているか確認\n\n")
        f.write("## 四半期別結果\n\n")
        f.write("| 四半期 | 総トレード | BB逸脱 | 平均回帰 | 回帰率 | 成功PnL | 失敗PnL |\n")
        f.write("|--------|-----------|--------|---------|--------|---------|----------|\n")
        for r in all_results:
            f.write(f"| {r['quarter']} 2025 | {r['total_trades']} | {r['bb_violations']} | "
                   f"{r['mean_reversions']} | {r['mean_reversion_rate']:.1f}% | "
                   f"${r['avg_success_pnl']:.2f} | ${r['avg_fail_pnl']:.2f} |\n")
        
        f.write(f"\n## 総合評価\n\n")
        f.write(f"- **BB 2σ逸脱総数**: {total_violations} 回\n")
        f.write(f"- **平均回帰成功**: {total_reversions} 回\n")
        f.write(f"- **平均回帰率**: {overall_rate:.1f}%\n")
        f.write(f"- **成功時平均PnL**: ${avg_overall_success:.2f}\n")
        f.write(f"- **失敗時平均PnL**: ${avg_overall_fail:.2f}\n\n")
        
        f.write(f"## 判定結果\n\n")
        if go_decision == "GO":
            f.write(f"✅ **GO**: 平均回帰率 {overall_rate:.1f}% ≥ 60%\n\n")
            f.write(f"→ **Phase 1 (最小実装) に進むことを推奨**\n")
        elif go_decision == "CONDITIONAL":
            f.write(f"⚠️ **CONDITIONAL**: 平均回帰率 {overall_rate:.1f}% (50-60%)\n\n")
            f.write(f"→ Phase 1実装は可能だが、慎重な評価が必要\n")
        else:
            f.write(f"❌ **NO-GO**: 平均回帰率 {overall_rate:.1f}% < 50%\n\n")
            f.write(f"→ Mean Reversion戦略は2025年市場に不適合\n")
            f.write(f"→ Task 38c (Range Breakout Enhanced) を検討推奨\n")
    
    print(f"💾 Markdownレポート保存: {md_report_path}")
    print(f"\n{'='*70}")
    print(f"Phase 0 評価完了")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
