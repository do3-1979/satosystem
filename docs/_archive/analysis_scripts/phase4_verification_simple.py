#!/usr/bin/env python3
"""
Phase 4: 簡易版効果測定（設定確認）

フルバックテストなしに、現在の設定状態での指標が正常に動作しているか確認。
"""

import sys
sys.path.insert(0, '/home/satoshi/work/satosystem/src')

import json
from datetime import datetime
from config import Config
from price_data_management import PriceDataManagement
from portfolio import Portfolio
from risk_management import RiskManagement
from trading_strategy import TradingStrategy

def verify_phase4_baseline():
    """
    Baseline (新指標OFF) での動作確認
    """
    print("=" * 70)
    print("Phase 4: Baseline 設定確認")
    print("=" * 70)
    
    try:
        price_data_management = PriceDataManagement()
        portfolio = Portfolio()
        
        # バックテストモード初期化
        if Config.get_back_test_mode() == 1:
            price_data_management.initialise_back_test_ohlcv_data()
            price_data_management.update_price_data_backtest()
        
        risk_manager = RiskManagement(price_data_management, portfolio)
        strategy = TradingStrategy(price_data_management, risk_manager, portfolio)
        
        print(f"\n✓ Baseline 初期化完了")
        
        # 既存ロジック（PVO + ドンチャン）の動作確認
        signals = price_data_management.get_signals()
        print(f"\n📊 既存指標（Baseline）:")
        print(f"  PVO Signal: {signals.get('pvo', {}).get('signal', 'N/A')}")
        print(f"  Donchian Side: {signals.get('donchian', {}).get('side', 'N/A')}")
        
        # evaluate_entry 実行
        strategy.evaluate_entry()
        print(f"\n  Entry Decision: {strategy.trade_decision.get('decision', 'N/A')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Baseline 検証失敗: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def verify_phase4_new_strategies():
    """
    新指標Strategy (A/B/C) での動作確認
    """
    print(f"\n" + "=" * 70)
    print("Phase 4: 新指標Strategy 設定確認")
    print("=" * 70)
    
    try:
        price_data_management = PriceDataManagement()
        portfolio = Portfolio()
        
        # バックテストモード初期化
        if Config.get_back_test_mode() == 1:
            price_data_management.initialise_back_test_ohlcv_data()
            price_data_management.update_price_data_backtest()
        
        risk_manager = RiskManagement(price_data_management, portfolio)
        strategy = TradingStrategy(price_data_management, risk_manager, portfolio)
        
        # すべてのStrategy設定を表示
        print(f"\n✓ 新指標Strategy 設定:")
        print(f"  Strategy A (ADX): {'有効' if risk_manager.enable_strategy_a_adx else '無効'}")
        print(f"  Strategy B (BB+RSI+SMA): {'有効' if risk_manager.enable_strategy_b_bb_rsi_sma else '無効'}")
        print(f"  Strategy C (Combined): {'有効' if risk_manager.enable_strategy_c_combined else '無効'}")
        
        # Strategy 評価
        all_strategies = risk_manager.evaluate_all_strategies()
        print(f"\n📊 Strategy 評価結果:")
        print(f"  Strategy A Signal: {all_strategies.get('strategy_a', {}).get('signal', 'N/A')}")
        print(f"  Strategy B Signal: {all_strategies.get('strategy_b', {}).get('signal', 'N/A')}")
        print(f"  Strategy C Signal: {all_strategies.get('strategy_c', {}).get('signal', 'N/A')}")
        
        # _evaluate_new_indicator_strategy 実行
        strategy_result = strategy._evaluate_new_indicator_strategy()
        if strategy_result:
            print(f"\n  統合結果: {strategy_result.get('signal', 'N/A')} ({strategy_result.get('strategy', 'N/A')})")
        
        return True
        
    except Exception as e:
        print(f"❌ 新指標Strategy 検証失敗: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def generate_phase4_report():
    """
    Phase 4 レポートを生成
    """
    print(f"\n" + "=" * 70)
    print("Phase 4: テスト結果レポート")
    print("=" * 70)
    
    report = {
        'timestamp': datetime.now().isoformat(),
        'phase': 4,
        'title': '新指標統合効果測定',
        'status': 'テスト環境での検証完了',
        'notes': [
            'Baseline (既存ロジック) での動作確認: ✅',
            '新指標Strategy (A/B/C) での動作確認: ✅',
            'エントリー判定統合: ✅',
            '次ステップ: フルバックテストによる効果測定が必要',
            '',
            '実行手順:',
            '1. python phase4_comparison.py で複数Strategyの比較実行',
            '2. baseline と各Strategy の損益/勝率/Sharpe比を比較',
            '3. 最適なStrategy設定を決定後、本番運用へ',
        ]
    }
    
    # レポートをファイルに保存
    try:
        import json
        report_file = '/home/satoshi/work/satosystem/report_tmp/phase4_test_report.json'
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n✓ レポートを {report_file} に保存しました")
    except Exception as e:
        print(f"\n⚠️ レポート保存エラー: {str(e)}")
    
    print(f"\n✅ Phase 4 検証完了")

if __name__ == "__main__":
    success = True
    
    # Baseline 検証
    if not verify_phase4_baseline():
        success = False
    
    # 新指標Strategy 検証
    if not verify_phase4_new_strategies():
        success = False
    
    # レポート生成
    if success:
        generate_phase4_report()
    
    sys.exit(0 if success else 1)
