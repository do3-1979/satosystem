#!/usr/bin/env python3
"""
ホットテスト + ダミー取引 3 分実行テスト

fetch_ticker() の呼び出し回数を検証
"""

import os
import sys
import time
import json
from datetime import datetime
from pathlib import Path

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
from bot import Bot
from logger import Logger


def test_hot_trading_3min():
    """
    ホットテスト + ダミー取引を 3 分実行
    fetch_ticker() の呼び出し回数を検証
    """
    
    print("=" * 80)
    print("🔥 ホットテスト + ダミー取引 3 分実行テスト")
    print("=" * 80)
    
    # config.ini を確認
    back_test_mode = Config.get_back_test_mode()
    hot_test_dummy_mode = Config.get_hot_test_dummy_mode()
    bot_operation_cycle = Config.get_bot_operation_cycle()
    
    print(f"\n📋 現在の設定:")
    print(f"   - back_test: {back_test_mode}")
    print(f"   - hot_test_dummy_mode: {hot_test_dummy_mode}")
    print(f"   - bot_operation_cycle: {bot_operation_cycle} 秒")
    
    # ホットテスト + ダミー取引の確認
    if back_test_mode == 1:
        print("\n❌ エラー: バックテストモードが有効です")
        print("   テストを実行するには config.ini の [Backtest] back_test = 0 に設定してください")
        return False
    
    if hot_test_dummy_mode != 1:
        print("\n⚠️  警告: ダミーモードが無効です")
        print("   テストを実行するには config.ini の [Backtest] hot_test_dummy_mode = 1 に設定してください")
    
    print(f"\n✅ ホットテスト + ダミー取引モード で実行します")
    
    # 取引所クラスの初期化（fetch_ticker() 呼び出し監視用）
    exchange = BybitExchange(Config.get_api_key(), Config.get_api_secret())
    
    # fetch_ticker() の呼び出し回数をカウント
    original_fetch_ticker = exchange.fetch_ticker
    fetch_ticker_count = {"count": 0}
    
    def monitored_fetch_ticker():
        fetch_ticker_count["count"] += 1
        # API キーエラー対策: ダミー価格を返す
        try:
            return original_fetch_ticker()
        except Exception as e:
            print(f"\n   [注意] fetch_ticker() API呼び出しエラー: {str(e)[:50]}...")
            # ダミー価格を返す（最後に取得した価格 or キャッシュから）
            return 100000.0
    
    # fetch_ticker() をモニタリング対象にする
    exchange.fetch_ticker = monitored_fetch_ticker
    
    # その他のクラスを初期化
    portfolio = Portfolio()
    price_data_management = PriceDataManagement()
    risk_management = RiskManagement(price_data_management, portfolio)
    strategy = TradingStrategy(price_data_management, risk_management, portfolio)
    
    # ボットを初期化
    bot = Bot(exchange, strategy, risk_management, price_data_management, portfolio)
    
    # 3 分のタイマーを設定
    print(f"\n⏱️  ホットテスト開始（3 分間実行）...")
    start_time = time.time()
    timeout = 3 * 60  # 3 分
    
    loop_count = 0
    last_ticker_count = 0
    
    try:
        while time.time() - start_time < timeout:
            loop_count += 1
            
            # ボットの 1 ループを実行
            try:
                # 価格情報を更新（fetch_ticker() が呼ばれる）
                price_data_management.update_price_data()
                
                # 取引戦略を実行
                trade_decision = strategy.make_trade_decision()
                
                # 現在の fetch_ticker() 呼び出し回数を表示（毎 10 ループ）
                if loop_count % 10 == 0:
                    elapsed = time.time() - start_time
                    print(f"   [{int(elapsed):3d}s] ループ: {loop_count:3d}, fetch_ticker() 呼び出し: {fetch_ticker_count['count']:2d}")
                
                # 次のループまで待機
                time.sleep(bot_operation_cycle)
            
            except KeyboardInterrupt:
                print("\n\n⚠️  ユーザーにより中断されました")
                break
            except Exception as e:
                print(f"\n❌ エラーが発生しました: {e}")
                break
    
    except KeyboardInterrupt:
        pass
    
    # 実行結果
    elapsed_time = time.time() - start_time
    print(f"\n" + "=" * 80)
    print(f"📊 3 分間実行結果")
    print(f"=" * 80)
    print(f"\n実行時間: {elapsed_time:.2f} 秒（{elapsed_time/60:.2f} 分）")
    print(f"ボットループ数: {loop_count}")
    print(f"fetch_ticker() 呼び出し回数: {fetch_ticker_count['count']}")
    print(f"\n平均呼び出し回数（1ループあたり）: {fetch_ticker_count['count'] / loop_count:.2f} 回")
    
    # 判定
    print(f"\n" + "-" * 80)
    success = fetch_ticker_count["count"] >= 2
    
    if success:
        print(f"✅ PASS: fetch_ticker() が 2 回以上呼び出されました")
        print(f"   期待値: >= 2 回")
        print(f"   実績: {fetch_ticker_count['count']} 回")
    else:
        print(f"❌ FAIL: fetch_ticker() が 2 回未満の呼び出しです")
        print(f"   期待値: >= 2 回")
        print(f"   実績: {fetch_ticker_count['count']} 回")
    
    print(f"=" * 80)
    
    # 結果を JSON で保存
    result = {
        "test_name": "hot_trading_3min",
        "timestamp": datetime.now().isoformat(),
        "config": {
            "back_test": back_test_mode,
            "hot_test_dummy_mode": hot_test_dummy_mode,
            "bot_operation_cycle": bot_operation_cycle,
        },
        "results": {
            "elapsed_time_seconds": elapsed_time,
            "loop_count": loop_count,
            "fetch_ticker_count": fetch_ticker_count["count"],
            "avg_calls_per_loop": fetch_ticker_count["count"] / loop_count if loop_count > 0 else 0,
            "pass": success,
        }
    }
    
    # 結果ファイルを保存
    result_dir = os.path.join(WORKSPACE_ROOT, "docs/regression_test_results")
    os.makedirs(result_dir, exist_ok=True)
    result_file = os.path.join(result_dir, "hot_trading_3min_result.json")
    
    with open(result_file, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"\n📁 結果を保存しました: {result_file}")
    
    return success


if __name__ == "__main__":
    success = test_hot_trading_3min()
    sys.exit(0 if success else 1)
