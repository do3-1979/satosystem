#!/usr/bin/env python3
"""
Phase 1 레지업 검출 효과 테스트
Adaptive vs Baseline 설정을 각각 실행하고 결과를 비교
"""
import os
import sys
import shutil
import json
from datetime import datetime

sys.path.insert(0, 'src')

from config import Config
from price_data_management import PriceDataManagement
from logger import Logger
from bybit_exchange import BybitExchange
from trading_strategy import TradingStrategy
from risk_management import RiskManagement
from portfolio import Portfolio
from indicator_service import IndicatorService
from bot import Bot

def run_single_backtest(config_file: str, label: str) -> dict:
    """단일 백테스트 실행 및 결과 반환"""
    print(f"\n{'='*70}")
    print(f"▶ Running: {label}")
    print(f"  Config: {config_file}")
    print(f"{'='*70}")
    
    # API 키 로드
    api_key = api_secret = "YOUR_API_KEY"
    try:
        with open('src/.api_key', 'r') as f:
            for line in f:
                if line.startswith('API_KEY='): 
                    api_key = line.split('=', 1)[1].strip()
                elif line.startswith('API_SECRET='): 
                    api_secret = line.split('=', 1)[1].strip()
    except:
        pass
    
    # 임시 설정 파일 생성
    temp_config = 'config_temp.ini'
    if os.path.exists(temp_config):
        os.remove(temp_config)
    
    shutil.copy(config_file, temp_config)
    with open(temp_config, 'r', encoding='utf-8') as f:
        content = f.read()
    
    content = content.replace("YOUR_API_KEY", api_key).replace("YOUR_API_SECRET", api_secret)
    with open(temp_config, 'w', encoding='utf-8') as f:
        f.write(content)
    
    # 설정 로드
    Config.set_config_file(temp_config)
    Config.reload_config()
    
    # 싱글톤 리셋
    PriceDataManagement.reset_instance()
    Logger.reset_instance()
    
    # Bot 초기화 및 실행
    exchange = BybitExchange(Config.get_api_key(), Config.get_api_secret())
    portfolio = Portfolio()
    indicator_service = IndicatorService()
    price_data_management = PriceDataManagement(indicator_service=indicator_service)
    risk_management = RiskManagement(price_data_management, portfolio, indicator_service=indicator_service)
    strategy = TradingStrategy(price_data_management, risk_management, portfolio)
    bot = Bot(exchange, strategy, risk_management, price_data_management, portfolio)
    
    print(f"  regime_detection_enabled: {Config.config['Strategy'].getboolean('regime_detection_enabled', fallback=False)}")
    print(f"  Starting backtest...\n")
    
    bot.run()
    
    # 정리
    if os.path.exists(temp_config):
        os.remove(temp_config)
    
    # 최근 결과 파일 읽기
    try:
        summary_files = []
        if os.path.exists('report'):
            import glob
            summary_files = sorted(glob.glob('report/backtest_summary_*.json'), 
                                  key=os.path.getmtime, reverse=True)
        
        if summary_files:
            with open(summary_files[0]) as f:
                results = json.load(f)
            
            print(f"\n✅ {label} Results:")
            print(f"   PnL: {results.get('total_pnl', 'N/A'):.2f} BTC")
            print(f"   Trades: {results.get('trades', 'N/A')}")
            print(f"   Win Rate: {results.get('win_rate', 'N/A'):.2f}%")
            
            regime_stats = results.get('regime_stats', {})
            if regime_stats:
                sideways_pct = regime_stats.get('regime_percentages', {}).get('SIDEWAYS', 0)
                print(f"   SIDEWAYS Rate: {sideways_pct:.1f}%")
                print(f"   Regime Changes: {regime_stats.get('regime_change_count', 0)}")
            
            return results
        else:
            print(f"⚠️  No results file found for {label}")
            return {}
    
    except Exception as e:
        print(f"❌ Error reading results: {e}")
        return {}

def main():
    print("\n" + "="*70)
    print("Phase 1 Regime Detection Test")
    print("="*70)
    
    # 2024 Q1 비교
    print("\n📊 2024 Q1 Comparison:")
    adaptive_2024 = run_single_backtest('output_configs/adaptive_2024_q1.ini', 'Adaptive 2024 Q1')
    baseline_2024 = run_single_backtest('output_configs/baseline_2024_q1.ini', 'Baseline 2024 Q1')
    
    # 결과 비교
    if adaptive_2024 and baseline_2024:
        print("\n" + "="*70)
        print("📈 COMPARISON RESULTS:")
        print("="*70)
        
        pnl_diff = adaptive_2024.get('total_pnl', 0) - baseline_2024.get('total_pnl', 0)
        trades_diff = adaptive_2024.get('trades', 0) - baseline_2024.get('trades', 0)
        
        print(f"\nAdaptive (with SIDEWAYS filtering):")
        print(f"  PnL: {adaptive_2024.get('total_pnl', 0):.2f} BTC")
        print(f"  Trades: {adaptive_2024.get('trades', 0)}")
        
        print(f"\nBaseline (no filtering):")
        print(f"  PnL: {baseline_2024.get('total_pnl', 0):.2f} BTC")
        print(f"  Trades: {baseline_2024.get('trades', 0)}")
        
        print(f"\nDifference:")
        print(f"  PnL Impact: {pnl_diff:+.2f} BTC ({pnl_diff/baseline_2024.get('total_pnl', 1)*100:+.1f}%)")
        print(f"  Trade Reduction: {trades_diff} trades ({trades_diff/baseline_2024.get('trades', 1)*100:+.1f}%)")
        
        if abs(pnl_diff) < 0.5:  # 0.5 BTC 이하 차이
            print("\n⚠️  Phase 1 Impact: MINIMAL")
            print("    결론: SIDEWAYS 필터링은 거의 효과가 없음")
        elif pnl_diff > 0:
            print("\n✅ Phase 1 Impact: POSITIVE")
            print("    결론: SIDEWAYS 필터링으로 수익성 개선됨")
        else:
            print("\n❌ Phase 1 Impact: NEGATIVE")
            print("    결론: SIDEWAYS 필터링으로 수익성 악화됨")

if __name__ == '__main__':
    main()
