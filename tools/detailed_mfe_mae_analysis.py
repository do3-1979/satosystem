#!/usr/bin/env python3
"""
個別トレード MFE/MAE 詳細分析
- 各トレード区間での高値・安値から実際のMFE/MAEを計算
- 利益が伸びたが反転してストップに触れたケースを特定
- 出口戦略の改善機会を定量化
"""

import json
import sys
import os
from datetime import datetime

class DetailedTradeAnalyzer:
    def __init__(self, log_file):
        with open(log_file, 'r') as f:
            self.log_data = json.load(f)
        
        self.trades = []
        self._parse_trades_with_ohlc()
    
    def _parse_trades_with_ohlc(self):
        """エントリー～エグジット期間のOHLCデータを収集してトレード情報を構築"""
        entry_idx = None
        
        for i, entry in enumerate(self.log_data):
            if entry.get('decision') == 'ENTRY':
                entry_idx = i
            
            elif entry.get('decision') == 'EXIT' and entry_idx is not None:
                # Entry～Exit の期間を抽出
                trade_period = self.log_data[entry_idx:i+1]
                trade = self._construct_detailed_trade(trade_period, entry_idx, i)
                self.trades.append(trade)
                entry_idx = None
    
    def _construct_detailed_trade(self, trade_period, entry_idx, exit_idx):
        """トレード期間のOHLC分析を含む詳細トレード情報を構築"""
        entry_data = trade_period[0]
        exit_data = trade_period[-1]
        
        entry_price = entry_data.get('position_price', 0)
        exit_price = exit_data.get('exec_price', exit_data.get('close_price', 0))
        
        # Entry～Exit期間のHigh/Low を追跡
        high_prices = []
        low_prices = []
        
        for candle in trade_period:
            high_prices.append(candle.get('high_price', 0))
            low_prices.append(candle.get('low_price', 0))
        
        max_price = max(high_prices)
        min_price = min(low_prices)
        
        # MFE/MAEを計算
        mfe = ((max_price - entry_price) / entry_price * 100) if entry_price else 0
        mae = ((entry_price - min_price) / entry_price * 100) if entry_price else 0
        actual_return = ((exit_price - entry_price) / entry_price * 100) if entry_price else 0
        
        # どの段階で反転したかを判定
        peak_idx = None
        for idx, price in enumerate(high_prices):
            if price == max_price:
                peak_idx = idx
                break
        
        bars_to_peak = peak_idx if peak_idx is not None else len(high_prices)
        bars_to_exit = len(trade_period) - 1
        
        trade = {
            'entry_time': entry_data.get('close_time_dt'),
            'exit_time': exit_data.get('close_time_dt'),
            'entry_price': entry_price,
            'exit_price': exit_price,
            'max_price': max_price,
            'min_price': min_price,
            'peak_time': trade_period[min(peak_idx, len(trade_period)-1)].get('close_time_dt') if peak_idx else None,
            
            # トレード統計
            'mfe': mfe,                           # 最大利益率
            'mae': mae,                           # 最大逆行率
            'actual_return': actual_return,       # 実際の利益率
            'unrealized_profit_lost': mfe - actual_return,  # 失った利益
            'total_pnl': exit_data.get('total_profit_and_loss', 0),
            
            # タイミング分析
            'bars_to_peak': bars_to_peak,         # ピークまでの足数
            'bars_total': bars_to_exit,           # 総保持足数
            
            # Entry指標
            'entry_psar': entry_data.get('psar'),
            'entry_adx': entry_data.get('adx'),
            'entry_pvo': entry_data.get('pvo_val'),
            'entry_volatility': entry_data.get('volatility'),
            
            # Exit指標
            'exit_psar': exit_data.get('psar'),
            'exit_adx': exit_data.get('adx'),
            'exit_pvo': exit_data.get('pvo_val'),
            'exit_volatility': exit_data.get('volatility'),
            
            # Exit段階のDonchian
            'exit_donchian_h': exit_data.get('donchian', {}).get('info', {}).get('highest'),
            'exit_donchian_l': exit_data.get('donchian', {}).get('info', {}).get('lowest'),
            
            'period_length': len(trade_period),
        }
        
        return trade
    
    def analyze_missed_profits(self):
        """失われた利益パターンを分析"""
        print("\n" + "="*120)
        print("【個別トレード詳細分析】利益を失ったパターンの解析")
        print("="*120 + "\n")
        
        # 利益が伸びたが、その後反転してストップに触れたケース
        missed_profit_trades = []
        good_profit_trades = []
        
        for trade in self.trades:
            mfe = trade['mfe']
            actual = trade['actual_return']
            lost = trade['unrealized_profit_lost']
            
            if mfe > 1.0 and lost > 0.5:  # 1%以上の利益が見込めたが、0.5%以上失った
                missed_profit_trades.append(trade)
            elif actual > 1.0:  # 1%以上の利益を確定できた
                good_profit_trades.append(trade)
        
        print(f"📊 利益を失ったトレード:  {len(missed_profit_trades)} / {len(self.trades)}")
        print(f"✅ 良好な利益確定:        {len(good_profit_trades)} / {len(self.trades)}")
        print(f"📈 平均失われた利益:      {sum(t['unrealized_profit_lost'] for t in missed_profit_trades) / len(missed_profit_trades) if missed_profit_trades else 0:.3f}%")
        
        print("\n" + "-"*120)
        print("【利益を失ったトレード TOP 5 - 最も損失が大きい順】")
        print("-"*120 + "\n")
        
        sorted_missed = sorted(missed_profit_trades, key=lambda t: t['unrealized_profit_lost'], reverse=True)[:5]
        for i, trade in enumerate(sorted_missed, 1):
            self._print_detailed_trade_analysis(i, trade, "MISSED_PROFIT")
        
        print("\n" + "-"*120)
        print("【良好な利確ができたトレード TOP 5 - 最大利益に最も接近】")
        print("-"*120 + "\n")
        
        # 失われた利益が最小のトレード
        good_sorted = sorted(good_profit_trades, key=lambda t: t['unrealized_profit_lost'])[:5]
        for i, trade in enumerate(good_sorted, 1):
            self._print_detailed_trade_analysis(i, trade, "GOOD_EXIT")
    
    def _print_detailed_trade_analysis(self, idx, trade, trade_type):
        """トレード詳細分析を出力"""
        print(f"Trade #{idx} [{trade_type}]")
        print(f"  ⏰ Entry:  {trade['entry_time']} @ ${trade['entry_price']:,.2f}")
        print(f"  ⏰ Peak:   {trade['peak_time']} (Entry後 {trade['bars_to_peak']} 足)")
        print(f"  ⏰ Exit:   {trade['exit_time']} @ ${trade['exit_price']:,.2f} (Peak後 {trade['bars_total'] - trade['bars_to_peak']} 足で反転)")
        print(f"")
        print(f"  📊 利益分析:")
        print(f"     MFE (最大利益率):       {trade['mfe']:+.3f}%  (最大価格: ${trade['max_price']:,.2f})")
        print(f"     MAE (最大逆行率):       {trade['mae']:+.3f}%  (最小価格: ${trade['min_price']:,.2f})")
        print(f"     実現利益率:             {trade['actual_return']:+.3f}%")
        print(f"     失われた利益:           {trade['unrealized_profit_lost']:+.3f}%  ← 改善の余地")
        print(f"     確定PnL:                ${trade['total_pnl']:+,.2f}")
        print(f"")
        print(f"  📈 Entry時の指標:")
        print(f"     ADX: {trade['entry_adx']:.2f} (トレンド強度)")
        print(f"     PVO: {trade['entry_pvo']:+.2f} (モメンタム)")
        print(f"     Volatility: {trade['entry_volatility']:.2f}")
        print(f"")
        print(f"  📉 Exit時の指標（逆転のサイン?）:")
        print(f"     ADX: {trade['exit_adx']:.2f} (Entry比: {trade['exit_adx'] - trade['entry_adx']:+.2f})")
        print(f"     PVO: {trade['exit_pvo']:+.2f} (Entry比: {trade['exit_pvo'] - trade['entry_pvo']:+.2f})")
        print(f"     Volatility: {trade['exit_volatility']:.2f} (Entry比: {trade['exit_volatility'] - trade['entry_volatility']:+.2f})")
        
        if trade['exit_pvo'] and trade['entry_pvo']:
            pvo_flipped = (trade['entry_pvo'] > 0 and trade['exit_pvo'] < 0)
            if pvo_flipped:
                print(f"     ⚠️  PVO反転! (正 → 負: モメンタムが消失)")
        
        adx_declining = trade['exit_adx'] < trade['entry_adx']
        if adx_declining:
            print(f"     ⚠️  ADXが低下! (トレンド減衰)")
        
        print()
    
    def suggest_exit_improvements(self):
        """出口戦略の改善案を定量化"""
        print("\n" + "="*120)
        print("【出口戦略改善の定量化】複合指標による潜在的な利益改善")
        print("="*120 + "\n")
        
        print("💡 現状分析:")
        print(f"   - 全トレード数: {len(self.trades)}")
        print(f"   - 利益を失ったトレード: {sum(1 for t in self.trades if t['unrealized_profit_lost'] > 0.5)}")
        print(f"   - 平均失われた利益: {sum(t['unrealized_profit_lost'] for t in self.trades) / len(self.trades):.3f}%")
        print()
        
        # PVO反転で出口した場合のシミュレーション
        pvo_flip_trades = [t for t in self.trades if t['entry_pvo'] and t['exit_pvo']]
        pvo_flipped_at_exit = [t for t in pvo_flip_trades if (t['entry_pvo'] > 0 and t['exit_pvo'] < 0)]
        
        if pvo_flipped_at_exit:
            print(f"🔄 PVO反転出口戦略:")
            print(f"   - PVO反転が発生したトレード: {len(pvo_flipped_at_exit)}")
            avg_mfe_at_pvo_flip = sum(t['mfe'] for t in pvo_flipped_at_exit) / len(pvo_flipped_at_exit)
            avg_actual = sum(t['actual_return'] for t in pvo_flipped_at_exit) / len(pvo_flipped_at_exit)
            print(f"   - PVO反転時のMFE平均: {avg_mfe_at_pvo_flip:.3f}%")
            print(f"   - 実現利益平均: {avg_actual:.3f}%")
            print(f"   - 潜在的改善: {avg_mfe_at_pvo_flip - avg_actual:.3f}% / トレード")
        
        # ADX減衰で出口した場合
        adx_declining_trades = [t for t in self.trades if t['exit_adx'] < t['entry_adx']]
        
        if adx_declining_trades:
            print(f"\n📊 ADX減衰出口戦略:")
            print(f"   - ADXが減衰したトレード: {len(adx_declining_trades)}")
            avg_mfe_at_adx_decline = sum(t['mfe'] for t in adx_declining_trades) / len(adx_declining_trades)
            avg_actual_adx = sum(t['actual_return'] for t in adx_declining_trades) / len(adx_declining_trades)
            print(f"   - ADX減衰時のMFE平均: {avg_mfe_at_adx_decline:.3f}%")
            print(f"   - 実現利益平均: {avg_actual_adx:.3f}%")
            print(f"   - 潜在的改善: {avg_mfe_at_adx_decline - avg_actual_adx:.3f}% / トレード")
        
        # ハイブリッド提案
        print("\n" + "-"*120)
        print("【推奨: ハイブリッド出口戦略】")
        print("-"*120 + "\n")
        
        print("📌 Stage 1: トレンド継続中 (ADX > 50 かつ PVO > 0)")
        print("   → 出口しない。トレーリングストップで利益を伸ばす")
        print("   → PSARがストップロスの役割を担当")
        print()
        
        print("📌 Stage 2: トレンド減衰 (ADX 30-50 かつ PVO > 0)")
        print("   → 50% ポジションを部分利確")
        print("   → 残り50%はトレーリングストップで保持")
        print()
        
        print("📌 Stage 3: モメンタム消失 (PVO < 0 または ADX < 30)")
        print("   → 全ポジションを出口")
        print("   → PSARレベルまで逃げることで最小損失")
        print()
        
        print("📌 Stage 4: 安全弁 (PSAR ブレイク)")
        print("   → 無条件出口（最小損失で逃げる）")
        print()
        
        # 期待改善値
        total_trades = len(self.trades)
        total_current_pnl = sum(t['total_pnl'] for t in self.trades)
        total_potential_mfe = sum(t['mfe'] * t['entry_price'] / 100 for t in self.trades if t['entry_price'])
        
        print("=" * 120)
        print("【改善予想シナリオ】")
        print("=" * 120 + "\n")
        
        print(f"現状:")
        print(f"  - 総PnL: ${total_current_pnl:+,.2f}")
        print(f"  - トレード当たり平均: ${total_current_pnl/total_trades:+,.2f}")
        print()
        
        # 保守的な改善予想：失われた利益の50%を回復
        conservative_improvement = (sum(t['unrealized_profit_lost'] * t['entry_price'] / 100 for t in self.trades if t['entry_price']) * 0.5)
        new_pnl_conservative = total_current_pnl + conservative_improvement
        
        print(f"改善シナリオ (失われた利益の50%を回復):")
        print(f"  - 追加PnL: ${conservative_improvement:+,.2f}")
        print(f"  - 新しい総PnL: ${new_pnl_conservative:+,.2f}")
        print(f"  - トレード当たり平均: ${new_pnl_conservative/total_trades:+,.2f}")
        print(f"  - 改善率: {(conservative_improvement/abs(total_current_pnl)*100) if total_current_pnl != 0 else 0:.1f}%")

def main():
    log_dir = "/home/satoshi/work/satosystem/src/logs"
    log_files = [f for f in os.listdir(log_dir) if f.endswith('.json') and f[0].isdigit()]
    
    # 最新の有効なログを探す
    latest_log = None
    for candidate in sorted(log_files, reverse=True):
        try:
            test_path = os.path.join(log_dir, candidate)
            with open(test_path, 'r') as f:
                json.load(f)
            latest_log = candidate
            break
        except:
            continue
    
    if not latest_log:
        print("❌ 有効なログファイルが見つかりません")
        sys.exit(1)
    
    log_file = os.path.join(log_dir, latest_log)
    print(f"📂 ログファイル: {latest_log}\n")
    
    analyzer = DetailedTradeAnalyzer(log_file)
    print(f"📊 合計トレード数: {len(analyzer.trades)}\n")
    
    analyzer.analyze_missed_profits()
    analyzer.suggest_exit_improvements()

if __name__ == "__main__":
    main()
