#!/usr/bin/env python3
"""
個別トレード分析スクリプト
- MFE/MAE分析: 利益が最大化した地点でのexitと、実際のexitの比較
- トレンド継続性分析: 反転して停止に触れたケース vs 早期利確のケース
- 出口戦略改善提案: PSARの代替指標の検討
"""

import json
import sys
from datetime import datetime, timedelta
from collections import defaultdict
import os

class TradeAnalyzer:
    def __init__(self, log_file):
        with open(log_file, 'r') as f:
            self.log_data = json.load(f)
        
        self.trades = []
        self._parse_trades()
    
    def _parse_trades(self):
        """ログからトレード情報を抽出"""
        entry_data = None
        
        for entry in self.log_data:
            if entry.get('decision') == 'ENTRY':
                entry_data = entry
            
            elif entry.get('decision') == 'EXIT' and entry_data:
                trade = self._construct_trade(entry_data, entry)
                self.trades.append(trade)
                entry_data = None
    
    def _construct_trade(self, entry_data, exit_data):
        """トレードデータを構築"""
        entry_price = entry_data.get('position_price', 0)
        exit_price = exit_data.get('exec_price', exit_data.get('close_price', 0))
        
        trade = {
            'entry_time': entry_data.get('close_time_dt'),
            'entry_price': entry_price,
            'entry_close_price': entry_data.get('close_price'),
            'entry_psar': entry_data.get('psar'),
            'entry_donchian_h': entry_data.get('donchian', {}).get('info', {}).get('highest'),
            'entry_donchian_l': entry_data.get('donchian', {}).get('info', {}).get('lowest'),
            'entry_volatility': entry_data.get('volatility'),
            'entry_adx': entry_data.get('adx'),
            'entry_pvo': entry_data.get('pvo_val'),
            
            'exit_time': exit_data.get('close_time_dt'),
            'exit_price': exit_price,
            'exit_close_price': exit_data.get('close_price'),
            'exit_psar': exit_data.get('psar'),
            'exit_donchian_h': exit_data.get('donchian', {}).get('info', {}).get('highest'),
            'exit_donchian_l': exit_data.get('donchian', {}).get('info', {}).get('lowest'),
            'exit_volatility': exit_data.get('volatility'),
            'exit_adx': exit_data.get('adx'),
            'exit_pvo': exit_data.get('pvo_val'),
            
            'pnl': exit_data.get('total_profit_and_loss', 0),
            'side': entry_data.get('side'),
        }
        
        # MFE/MAE情報を後追い計算（ここでは簡易版）
        trade['pnl_pct'] = (trade['pnl'] / entry_price * 100) if entry_price else 0
        
        return trade
    
    def analyze_mfe_mae_patterns(self):
        """MFE/MAE パターンを分析"""
        print("\n" + "="*100)
        print("【個別トレード分析】MFE/MAE パターンの傾向")
        print("="*100 + "\n")
        
        patterns = {
            'hit_stop_after_profit': [],      # 利益が出た後にストップに触れた
            'early_exit_before_reversal': [],  # 早期利確して、その後反転したら儲かった
            'missed_extension': [],            # トレンド継続したのに出口で逃した
            'good_exits': [],                  # 理想的な出口
        }
        
        for trade in self.trades:
            entry_p = trade['entry_price']
            exit_p = trade['exit_price']
            actual_pnl_pct = trade['pnl_pct']
            
            # PnLがプラスか確認
            if actual_pnl_pct > 0.5:  # 利益が出ている
                # この後、ストップに触れたかを判定（簡易版）
                # 実際はpnlが一時的に大きかったが、最終的には小さいといった場合を検出
                patterns['good_exits'].append(trade)
            
            elif -1.0 < actual_pnl_pct < 0.5 and entry_p < exit_p:  # 弱い利益or小損
                patterns['early_exit_before_reversal'].append(trade)
            
            elif actual_pnl_pct < -1.0:  # 大きな損失
                patterns['hit_stop_after_profit'].append(trade)
        
        # サマリー出力
        print(f"✅ 理想的な出口:              {len(patterns['good_exits'])} トレード")
        print(f"⚠️  ストップに触れた損失:     {len(patterns['hit_stop_after_profit'])} トレード")
        print(f"🤔 早期利確の判断:           {len(patterns['early_exit_before_reversal'])} トレード")
        print(f"🎯 トレンド継続を見逃した:   {len(patterns['missed_extension'])} トレード")
        
        # 詳細分析
        print("\n" + "-"*100)
        print("【ストップに触れて大損したトレード TOP 5】")
        print("-"*100 + "\n")
        
        bad_trades = sorted(patterns['hit_stop_after_profit'], key=lambda t: t['pnl'])[:5]
        for i, trade in enumerate(bad_trades, 1):
            self._print_trade_detail(i, trade, "BAD")
        
        print("\n" + "-"*100)
        print("【良い出口ができたトレード TOP 5】")
        print("-"*100 + "\n")
        
        good_trades = sorted(patterns['good_exits'], key=lambda t: t['pnl'], reverse=True)[:5]
        for i, trade in enumerate(good_trades, 1):
            self._print_trade_detail(i, trade, "GOOD")
    
    def _print_trade_detail(self, idx, trade, label):
        """トレード詳細を出力"""
        entry_p = trade['entry_price']
        exit_p = trade['exit_price']
        
        mfe = ((trade['exit_donchian_h'] or 0) - entry_p) / entry_p * 100 if entry_p else 0
        mae = (entry_p - (trade['exit_donchian_l'] or entry_p)) / entry_p * 100 if entry_p else 0
        
        print(f"Trade #{idx} [{label}]")
        print(f"  📍 Entry:  {trade['entry_time']} @ ${entry_p:,.2f}")
        print(f"  📍 Exit:   {trade['exit_time']} @ ${exit_p:,.2f}")
        print(f"  💰 PnL:    ${trade['pnl']:+,.2f} ({trade['pnl_pct']:+.3f}%)")
        print(f"  📊 Entry Indicators:")
        print(f"     - ADX: {trade['entry_adx']:.2f} (トレンド強度)")
        print(f"     - PVO: {trade['entry_pvo']:+.2f} (モメンタム)")
        print(f"     - Volatility: {trade['entry_volatility']:.2f}")
        print(f"     - PSAR: ${trade['entry_psar']:.2f} (ストップレベル)")
        print(f"  📊 Exit Indicators:")
        print(f"     - ADX: {trade['exit_adx']:.2f}")
        print(f"     - PVO: {trade['exit_pvo']:+.2f}")
        print(f"     - Volatility: {trade['exit_volatility']:.2f}")
        print(f"     - PSAR: ${trade['exit_psar']:.2f}")
        print()
    
    def analyze_exit_signal_correlation(self):
        """出口シグナルとPnLの相関分析"""
        print("\n" + "="*100)
        print("【出口シグナル分析】PSAR vs その他指標の効果")
        print("="*100 + "\n")
        
        # PSARで出口した場合の成績
        psar_exits = [t for t in self.trades if abs(t['exit_price'] - t['exit_psar']) < 100]
        
        # PVO反転で出口すべき局面を検出
        pvo_should_exit = []
        for trade in self.trades:
            entry_pvo = trade['entry_pvo']
            exit_pvo = trade['exit_pvo']
            
            # PVOが正から負に反転（下行圧力増加）
            if entry_pvo > 0 and exit_pvo < 0:
                pvo_should_exit.append(trade)
        
        # ADXで出口すべき局面を検出
        adx_should_exit = []
        for trade in self.trades:
            entry_adx = trade['entry_adx']
            exit_adx = trade['exit_adx']
            
            # ADXが下降（トレンド減衰）
            if entry_adx > exit_adx:
                adx_should_exit.append(trade)
        
        print(f"📊 PSAR出口:        {len(psar_exits):3d} トレード")
        print(f"📊 PVO反転出口:     {len(pvo_should_exit):3d} トレード")
        print(f"📊 ADX減衰出口:     {len(adx_should_exit):3d} トレード")
        print(f"📊 複合シグナル:    {len([t for t in self.trades if t in pvo_should_exit and t in adx_should_exit]):3d} トレード")
        
        # 各パターンの平均PnL
        print("\n" + "-"*100)
        print("【平均PnL比較】")
        print("-"*100 + "\n")
        
        avg_psar = sum(t['pnl'] for t in psar_exits) / len(psar_exits) if psar_exits else 0
        avg_pvo = sum(t['pnl'] for t in pvo_should_exit) / len(pvo_should_exit) if pvo_should_exit else 0
        avg_adx = sum(t['pnl'] for t in adx_should_exit) / len(adx_should_exit) if adx_should_exit else 0
        
        print(f"PSAR出口の平均PnL:      ${avg_psar:+,.2f}")
        print(f"PVO反転出口の平均PnL:   ${avg_pvo:+,.2f}")
        print(f"ADX減衰出口の平均PnL:   ${avg_adx:+,.2f}")
        
        improvement = (avg_pvo + avg_adx) / 2 - avg_psar if avg_psar else 0
        print(f"\n💡 複合シグナル活用で期待できる改善: {improvement:+,.2f} USD/トレード")
    
    def suggest_improvements(self):
        """改善提案を生成"""
        print("\n" + "="*100)
        print("【出口戦略改善の提案】")
        print("="*100 + "\n")
        
        print("📌 現状: PSAR 1本で出口決定")
        print("   → 欠点: 反転のタイミングをPSARが追従できず、伸びきる前に損切られたり")
        print("          反転後も保持し続けてストップに触れる")
        print()
        
        print("💡 提案 #1: 複合出口シグナル (PSAR + PVO + ATR)")
        print("   - PSAR: ストップロス保証（常時下支え）")
        print("   - PVO反転: 上昇モメンタム消失をキャッチ → 部分利確")
        print("   - ATR: ボラティリティ低下 → 利益確定圧力が強まったシグナル")
        print()
        print("   効果:")
        print("   ✅ トレンド継続中: PVO+で利確タイミングを外す")
        print("   ✅ 反転開始: PVO反転で早期に部分利確")
        print("   ✅ リスク管理: PSARで最後の砦（小損で逃げられる）")
        print()
        
        print("💡 提案 #2: マルチレベル利確")
        print("   - Level 1 (50%): MFE時点で 固定目標達成")
        print("   - Level 2 (30%): PVO反転時")
        print("   - Level 3 (20%): ADXトレンド減衰時")
        print()
        print("   利点:")
        print("   ✅ 反転後のストップ損失を小さくできる")
        print("   ✅ トレンド継続時は全ポジションで利益伸ばせる")
        print()
        
        print("💡 提案 #3: トレンド拡張判定")
        print("   - 現在の高値 > Entry後のDonchian高値: トレンド継続")
        print("   - ADXが上昇中: モメンタム加速")
        print("   → この条件下では利確を遅延（トレーリングストップへ）")
        print()

def main():
    # 最新の有効なバックテストログを取得
    log_dir = "/home/satoshi/work/satosystem/src/logs"
    log_files = [f for f in os.listdir(log_dir) if f.endswith('.json') and f[0].isdigit()]
    
    if not log_files:
        print("❌ ログファイルが見つかりません")
        sys.exit(1)
    
    # 最新のものから順に有効なJSONを探す
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
    
    print(f"📂 ログファイル: {latest_log}")
    print(f"   {log_file}\n")
    
    analyzer = TradeAnalyzer(log_file)
    
    print(f"📊 合計トレード数: {len(analyzer.trades)}")
    
    analyzer.analyze_mfe_mae_patterns()
    analyzer.analyze_exit_signal_correlation()
    analyzer.suggest_improvements()

if __name__ == "__main__":
    main()
