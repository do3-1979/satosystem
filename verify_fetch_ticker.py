#!/usr/bin/env python3
"""
ホットテスト + ダミー取引 fetch_ticker() 検証

price_data_management.update_price_data() 呼び出しと 
fetch_ticker() 呼び出しの関係を検証
"""

import os
import sys
import time

# ワークスペースルート
WORKSPACE_ROOT = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(WORKSPACE_ROOT, "src")
os.chdir(SRC_DIR)
sys.path.insert(0, SRC_DIR)

from config import Config
from price_data_management import PriceDataManagement
from bybit_exchange import BybitExchange
from trading_strategy import TradingStrategy
from risk_management import RiskManagement
from portfolio import Portfolio

print("=" * 80)
print("🔍 fetch_ticker() 呼び出し検証")
print("=" * 80)

# config.ini 確認
back_test_mode = Config.get_back_test_mode()
print(f"\nConfig: back_test = {back_test_mode}")

if back_test_mode != 0:
    print("❌ ホットテストモードが有効ではありません")
    sys.exit(1)

print("✅ ホットテストモード（back_test = 0）")

# 取引所とその他クラスを初期化
exchange = BybitExchange(Config.get_api_key(), Config.get_api_secret())
portfolio = Portfolio()
price_data_management = PriceDataManagement()
risk_management = RiskManagement(price_data_management, portfolio)
strategy = TradingStrategy(price_data_management, risk_management, portfolio)

# モニタリング用カウント
counter = {"update_price_data": 0, "fetch_ticker": 0}

# 元の fetch_ticker を保存
original_fetch_ticker = exchange.fetch_ticker.__func__

def monitored_fetch_ticker(self):
    counter["fetch_ticker"] += 1
    print(f"  [fetch_ticker] 呼び出し #{counter['fetch_ticker']}")
    return original_fetch_ticker(self)

# fetch_ticker をモニタリング用にプレイス
exchange.fetch_ticker = monitored_fetch_ticker.__get__(exchange, type(exchange))

# 元の update_price_data を保存
original_update_price_data = price_data_management.update_price_data

def monitored_update_price_data():
    counter["update_price_data"] += 1
    print(f"\n📊 update_price_data() 呼び出し #{counter['update_price_data']}")
    return original_update_price_data()

# update_price_data をモニタリング用にプレイス
price_data_management.update_price_data = monitored_update_price_data

# 3 回のループを実行
print("\n" + "-" * 80)
print("🔄 3 ループ実行中...")
print("-" * 80)

for loop in range(3):
    try:
        print(f"\n【ループ #{loop + 1}】")
        
        # 価格データ更新（fetch_ticker が呼ばれるはず）
        price_data_management.update_price_data()
        
        # 取引判定
        trade_decision = strategy.make_trade_decision()
        
        print(f"  Decision: {trade_decision.get('decision')}")
        print(f"  現在のカウント - update: {counter['update_price_data']}, fetch_ticker: {counter['fetch_ticker']}")
        
        # 少し待機
        time.sleep(1)
    
    except Exception as e:
        print(f"  ❌ エラー: {e}")
        break

# 結果表示
print("\n" + "=" * 80)
print("📊 検証結果")
print("=" * 80)

print(f"\nupdate_price_data() 呼び出し数: {counter['update_price_data']}")
print(f"fetch_ticker() 呼び出し数: {counter['fetch_ticker']}")

# 判定
expected_min = 2
if counter["fetch_ticker"] >= expected_min:
    print(f"\n✅ PASS: fetch_ticker() が {counter['fetch_ticker']} 回呼び出されました")
    print(f"   期待値: >= {expected_min}")
else:
    print(f"\n❌ FAIL: fetch_ticker() が {counter['fetch_ticker']} 回（期待値: >= {expected_min}）")

print("=" * 80)
