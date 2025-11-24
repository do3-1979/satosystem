#!/usr/bin/env python3
"""
Task 11: リアルタイムパフォーマンス監視システム
日次PnL、Win Rate、Profit Factor を監視し、環境劣化を自動検出
"""

import sys
import os
import json
from datetime import datetime, timedelta
from collections import deque

sys.path.insert(0, 'src')

from logger import Logger

class RealtimePerformanceMonitor:
    """
    取引パフォーマンスをリアルタイムで監視
    環境劣化を自動検出し、Phase 2 の有効/無効を動的に調整
    """
    
    def __init__(self, window_size=7):
        """
        Args:
            window_size: 監視ウィンドウ（日数）
        """
        self.logger = Logger()
        self.window_size = window_size
        
        # パフォーマンス履歴（deque で最新N日のみ保持）
        self.daily_pnl = deque(maxlen=window_size)
        self.daily_win_rate = deque(maxlen=window_size)
        self.daily_profit_factor = deque(maxlen=window_size)
        self.daily_regime = deque(maxlen=window_size)
        
        # アラートテンプレート
        self.alerts = []
        
        # 監視閾値
        self.wr_degradation_threshold = 0.10  # WR が10%低下でアラート
        self.pnl_negative_days_threshold = 5  # 連続5日赤字でアラート
        self.pf_low_threshold = 0.5  # PF < 0.5 でアラート
    
    def record_daily_performance(self, date, pnl, win_rate, profit_factor, regime):
        """日次パフォーマンスを記録"""
        
        self.daily_pnl.append({'date': date, 'value': pnl})
        self.daily_win_rate.append({'date': date, 'value': win_rate})
        self.daily_profit_factor.append({'date': date, 'value': profit_factor})
        self.daily_regime.append({'date': date, 'value': regime})
        
        # リアルタイム分析
        self._analyze_and_alert()
    
    def _analyze_and_alert(self):
        """パフォーマンス分析とアラート生成"""
        
        self.alerts = []
        
        if len(self.daily_win_rate) < 2:
            return
        
        # 1. Win Rate 低下検出
        current_wr = self.daily_win_rate[-1]['value']
        previous_wr = self.daily_win_rate[-2]['value']
        wr_change = current_wr - previous_wr
        
        if wr_change < -self.wr_degradation_threshold:
            self.alerts.append({
                'type': 'WR_DEGRADATION',
                'severity': 'HIGH',
                'message': f'Win Rate が {wr_change*100:.1f}% 低下しました（{previous_wr*100:.1f}% → {current_wr*100:.1f}%）',
                'action': '市場環境が悪化している可能性があります。Phase 2 を一時的に無効化することを検討してください。'
            })
        
        # 2. 連続赤字検出
        negative_days = sum(1 for d in list(self.daily_pnl)[-5:] if d['value'] < 0)
        if negative_days >= self.pnl_negative_days_threshold:
            self.alerts.append({
                'type': 'CONSECUTIVE_LOSSES',
                'severity': 'CRITICAL',
                'message': f'直近5日間で{negative_days}日赤字です',
                'action': 'トレード一時停止と戦略再検証を推奨します'
            })
        
        # 3. Profit Factor 低下検出
        current_pf = self.daily_profit_factor[-1]['value']
        if current_pf < self.pf_low_threshold:
            self.alerts.append({
                'type': 'LOW_PROFIT_FACTOR',
                'severity': 'MEDIUM',
                'message': f'Profit Factor が {current_pf:.2f} で低値です',
                'action': 'エントリー基準を厳しくするか、ポジションサイズを削減してください'
            })
        
        # 4. レジーム変化検出
        if len(self.daily_regime) >= 2:
            current_regime = self.daily_regime[-1]['value']
            previous_regime = self.daily_regime[-2]['value']
            
            if current_regime != previous_regime:
                self.alerts.append({
                    'type': 'REGIME_CHANGE',
                    'severity': 'MEDIUM',
                    'message': f'市場レジームが変化しました（{previous_regime} → {current_regime}）',
                    'action': 'Task 7（環境自動判定）を実行して、Phase 2 の有効/無効を再評価してください'
                })
    
    def get_recommended_phase2_status(self):
        """
        パフォーマンスに基づいて推奨される Phase 2 ステータス
        Returns: 'ENABLE' | 'DISABLE' | 'MONITOR'
        """
        
        if not self.alerts:
            return 'MONITOR'
        
        critical_alerts = [a for a in self.alerts if a['severity'] == 'CRITICAL']
        if critical_alerts:
            return 'DISABLE'
        
        high_alerts = [a for a in self.alerts if a['severity'] == 'HIGH']
        if high_alerts:
            # Win Rate 低下 → Phase 2 を無効化する価値あり
            for alert in high_alerts:
                if alert['type'] == 'WR_DEGRADATION':
                    return 'DISABLE'
        
        return 'MONITOR'
    
    def report(self, title="リアルタイム監視レポート"):
        """監視結果をレポート"""
        
        print("="*70)
        print(f"📊 {title}")
        print("="*70)
        print()
        
        if not self.daily_pnl:
            print("⚠️  監視データがまだ蓄積されていません")
            print()
            return
        
        # 統計情報
        print(f"【監視期間】直近 {len(self.daily_pnl)} 日間")
        print()
        
        print("【パフォーマンス統計】")
        pnl_values = [d['value'] for d in self.daily_pnl]
        wr_values = [d['value'] for d in self.daily_win_rate]
        pf_values = [d['value'] for d in self.daily_profit_factor]
        
        print(f"  総PnL:          ${sum(pnl_values):+.2f}")
        print(f"  平均日次PnL:    ${sum(pnl_values)/len(pnl_values):+.2f}")
        print(f"  平均Win Rate:   {sum(wr_values)/len(wr_values)*100:.1f}%")
        print(f"  平均Profit Factor: {sum(pf_values)/len(pf_values):.2f}")
        print()
        
        # アラート情報
        if self.alerts:
            print(f"【⚠️  アラート】({len(self.alerts)}件)")
            for i, alert in enumerate(self.alerts, 1):
                severity_icon = {
                    'CRITICAL': '🔴',
                    'HIGH': '🟠',
                    'MEDIUM': '🟡'
                }.get(alert['severity'], '⚪')
                
                print(f"\n  {severity_icon} [{alert['type']}]")
                print(f"    メッセージ: {alert['message']}")
                print(f"    推奨アクション: {alert['action']}")
        else:
            print("✅ アラートなし")
        print()
        
        # 推奨アクション
        phase2_status = self.get_recommended_phase2_status()
        print("【推奨Phase2ステータス】")
        if phase2_status == 'ENABLE':
            print("  ✅ Phase 2 を有効化してください")
        elif phase2_status == 'DISABLE':
            print("  ❌ Phase 2 を無効化することを推奨します")
        else:
            print("  🔍 継続監視（変化なし）")
        print()
        
        print("="*70)
    
    def export_metrics(self, filename=None):
        """メトリクスを JSON で出力"""
        
        if filename is None:
            filename = f"work_reports/realtime_monitor_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        os.makedirs('work_reports', exist_ok=True)
        
        data = {
            'timestamp': datetime.now().isoformat(),
            'monitoring_window_days': self.window_size,
            'daily_pnl': [{'date': d['date'].isoformat(), 'value': d['value']} 
                         for d in self.daily_pnl],
            'daily_win_rate': [{'date': d['date'].isoformat(), 'value': d['value']} 
                              for d in self.daily_win_rate],
            'daily_profit_factor': [{'date': d['date'].isoformat(), 'value': d['value']} 
                                   for d in self.daily_profit_factor],
            'alerts': self.alerts,
            'recommended_phase2_status': self.get_recommended_phase2_status()
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return filename


def main():
    """リアルタイム監視システムのデモ"""
    
    print("\n📊 Task 11: リアルタイムパフォーマンス監視システム\n")
    
    monitor = RealtimePerformanceMonitor(window_size=7)
    
    # シミュレーション: 過去7日分のデータを記録
    base_date = datetime.now()
    
    # パターン1: 正常な推移
    for i in range(5):
        date = (base_date - timedelta(days=5-i)).date()
        pnl = 50 + (i * 10)
        win_rate = 0.45 + (i * 0.01)
        pf = 0.8 + (i * 0.05)
        regime = 'WEAK_TREND' if i < 3 else 'STRONG_TREND'
        monitor.record_daily_performance(date, pnl, win_rate, pf, regime)
    
    # パターン2: Win Rate が急低下
    date = (base_date - timedelta(days=1)).date()
    monitor.record_daily_performance(date, 30, 0.30, 0.9, 'WEAK_TREND')  # WR が低下
    
    # パターン3: さらに低下
    date = base_date.date()
    monitor.record_daily_performance(date, -50, 0.20, 0.7, 'SIDEWAYS')  # 赤字＋WR低下
    
    # レポート出力
    monitor.report()
    
    # JSON 出力
    json_file = monitor.export_metrics()
    print(f"✅ メトリクスを保存: {json_file}\n")


if __name__ == '__main__':
    main()
