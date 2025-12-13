#!/usr/bin/env python3
"""
ホットテスト + ダミー取引ログ分析テスト
ログに記録された fetch_ticker() 呼び出しを検証
"""

import os
import sys
import time
import json
import re
from datetime import datetime

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


def test_hot_trading_log_analysis():
    """
    ホットテスト + ダミー取引を実行しログを分析
    リアルタイム価格取得（fetch_ticker）が 2 回以上実行されたか確認
    """
    
    print("=" * 80)
    print("🔥 ホットテスト + ダミー取引 ログ分析テスト")
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
        return False
    
    print(f"\n✅ ホットテスト + ダミー取引モード で実行します")
    
    # ログファイルをクリア
    log_file = "logs/log.txt"
    if os.path.exists(log_file):
        os.remove(log_file)
    
    # 初期化
    exchange = BybitExchange(Config.get_api_key(), Config.get_api_secret())
    portfolio = Portfolio()
    price_data_management = PriceDataManagement()
    risk_management = RiskManagement(price_data_management, portfolio)
    strategy = TradingStrategy(price_data_management, risk_management, portfolio)
    bot = Bot(exchange, strategy, risk_management, price_data_management, portfolio)
    
    # 3 分のタイマーを設定
    print(f"\n⏱️  ホットテスト開始（3 分間実行）...")
    start_time = time.time()
    timeout = 3 * 60  # 3 分
    
    loop_count = 0
    
    try:
        while time.time() - start_time < timeout:
            loop_count += 1
            
            try:
                # 価格情報を更新（fetch_ticker() が呼ばれる）
                price_data_management.update_price_data()
                
                # 取引戦略を実行
                trade_decision = strategy.make_trade_decision()
                
                # 進捗表示
                elapsed = time.time() - start_time
                if loop_count % 2 == 0:  # 2 ループごと
                    print(f"   [{int(elapsed):3d}s] Loop: {loop_count:2d}")
                
                # 次のループまで待機
                time.sleep(bot_operation_cycle)
            
            except KeyboardInterrupt:
                print("\n\n⚠️  ユーザーにより中断されました")
                break
            except Exception as e:
                print(f"\n❌ エラー: {e}")
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
    
    # ログファイル分析
    print(f"\n📋 ログファイル分析:")
    if not os.path.exists(log_file):
        print(f"❌ ログファイルが見つかりません: {log_file}")
        return False
    
    # ログを読み込み
    with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
        log_content = f.read()
    
    # ログから以下を検索:
    # 1. リアルタイム価格取得（fetch_ticker）の実行回数
    # 2. OHLCV データ更新（fetch_ohlcv）の実行回数
    
    # ホットテスト時にリアルタイムデータを取得したかを確認
    # PriceDataManagement.update_price_data() で以下が呼ばれる:
    # - fetch_latest_ohlcv() (15分足)
    # - fetch_ohlcv() (120分足)
    # - fetch_ticker() (リアルタイム価格)
    
    # update_price_data() の呼び出しログから判定
    pattern_update = r"データの更新|OHLCV|fetch|ティック"
    matches = re.findall(pattern_update, log_content, re.IGNORECASE)
    
    # より正確には、ホットテスト時にリアルタイム価格が取得されたかを確認
    # ログのタイムスタンプパターン: 2025-12-13 16:XX:XX,XXX
    timestamps = re.findall(r'(\d{2}:\d{2}:\d{2})', log_content)
    
    print(f"\n   - ログ総行数: {len(log_content.splitlines())}")
    print(f"   - ログ内のタイムスタンプ数: {len(timestamps)}")
    
    # リアルタイム価格取得が複数回実行されたか確認
    # ホットテスト時は毎ループで update_price_data() が呼ばれ、
    # その内部で fetch_ticker() が呼ばれるはず
    
    # ログに含まれる「時刻:」のパターン数をカウント（各ループで 1 行ずつ出力）
    trade_log_lines = [line for line in log_content.splitlines() if "時刻:" in line]
    
    print(f"\n   - 取引ログ行数（時刻:） : {len(trade_log_lines)}")
    
    # 判定
    print(f"\n" + "-" * 80)
    success = len(trade_log_lines) >= 2
    
    if success:
        print(f"✅ PASS: リアルタイム価格取得が複数回実行されました")
        print(f"   期待値: >= 2 ループ")
        print(f"   実績: {len(trade_log_lines)} ループ")
    else:
        print(f"❌ FAIL: リアルタイム価格取得が 2 ループ未満です")
        print(f"   期待値: >= 2 ループ")
        print(f"   実績: {len(trade_log_lines)} ループ")
    
    print(f"=" * 80)
    
    # 最初の数行のログを表示
    print(f"\n📝 ログサンプル（最初の 10 行）:")
    print("-" * 80)
    for i, line in enumerate(log_content.splitlines()[:10], 1):
        print(f"{i:2d}: {line[:100]}")
    
    # 結果を JSON で保存
    result = {
        "test_name": "hot_trading_3min_log_analysis",
        "timestamp": datetime.now().isoformat(),
        "config": {
            "back_test": back_test_mode,
            "hot_test_dummy_mode": hot_test_dummy_mode,
            "bot_operation_cycle": bot_operation_cycle,
        },
        "results": {
            "elapsed_time_seconds": elapsed_time,
            "loop_count": loop_count,
            "trade_log_lines": len(trade_log_lines),
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
    success = test_hot_trading_log_analysis()
    sys.exit(0 if success else 1)
