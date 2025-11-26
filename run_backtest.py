#!/usr/bin/env python3
"""
バックテスト実行用ヘルパースクリプト

使用例:
  python3 run_backtest.py                          # デフォルト（高速）
  python3 run_backtest.py --full-logging           # 全ログ出力（グラフ分析用）
  python3 run_backtest.py --logging-interval 100   # カスタム間隔
  python3 run_backtest.py --period "2025/11/01" "2025/11/25"  # 期間指定
  python3 run_backtest.py --fast-summary           # 高速サマリモード（Excel/レポート スキップ）
"""

import sys
import os
import argparse
import tempfile
import shutil
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from config import Config
from bybit_exchange import BybitExchange
from price_data_management import PriceDataManagement
from trading_strategy import TradingStrategy
from risk_management import RiskManagement
from portfolio import Portfolio
from bot import Bot


def create_temp_config(logging_interval=1, fast_summary=0):
    """
    テンポラリ config ファイルを作成
    
    Args:
        logging_interval (int): ロギング間隔
        fast_summary (int): 高速サマリモード (0=OFF, 1=ON)
    
    Returns:
        str: テンポラリ config ファイルパス
    """
    # 元の config を読み込み
    base_config_path = os.path.join(os.path.dirname(__file__), 'src', 'config.ini')
    
    # テンポラリファイルを作成
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False, encoding='utf-8') as tmp:
        with open(base_config_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # logging_interval を置換
        if 'logging_interval' in content:
            import re
            content = re.sub(
                r'logging_interval = \d+',
                f'logging_interval = {logging_interval}',
                content
            )
        else:
            # [Log] セクションに追加
            if '[Log]' in content:
                content = content.replace(
                    '[Log]',
                    f'[Log]\nlogging_interval = {logging_interval}'
                )
        
        # fast_summary_mode を設定
        if 'fast_summary_mode' in content:
            import re
            content = re.sub(
                r'fast_summary_mode = \d+',
                f'fast_summary_mode = {fast_summary}',
                content
            )
        else:
            # [Backtest] セクションに追加
            if '[Backtest]' in content:
                content = content.replace(
                    '[Backtest]',
                    f'[Backtest]\nfast_summary_mode = {fast_summary}'
                )
        
        tmp.write(content)
        return tmp.name


def run_backtest(logging_interval=1, start_time=None, end_time=None, fast_summary=0):
    """
    バックテストを実行
    
    Args:
        logging_interval (int): ロギング間隔（1=全出力, 100=100回毎, etc）
        start_time (str): 開始時刻 (format: "YYYY/MM/DD HH:MM")
        end_time (str): 終了時刻 (format: "YYYY/MM/DD HH:MM")
        fast_summary (int): 高速サマリモード (0=OFF, 1=ON)
    """
    # テンポラリ config を作成
    temp_config = create_temp_config(logging_interval, fast_summary)
    
    try:
        # Config に设定ファイルを指定
        Config.set_config_file(temp_config)
        
        # 期間を上書き
        if start_time and end_time:
            print(f"[INFO] 期間を指定: {start_time} ～ {end_time}")
            # Note: この部分は実装例。実際の期間上書きは Config に依存
        
        print(f"[INFO] ロギング間隔: {logging_interval}")
        print(f"[INFO] 高速サマリモード: {'ON' if fast_summary else 'OFF'}")
        
        # バックテスト実行（既存の初期化コード）
        config_instance = Config()
        
        # Exchange
        exchange = BybitExchange(is_test=True)
        
        # Price Data Management
        price_data_management = PriceDataManagement(exchange)
        
        # Strategy, Risk Management, Portfolio
        trading_strategy = TradingStrategy(price_data_management, None, None)
        risk_management = RiskManagement()
        portfolio = Portfolio()
        
        # Bot
        bot = Bot(exchange, trading_strategy, risk_management, price_data_management, portfolio)
        
        # Run
        print("[INFO] バックテスト開始...")
        bot.run()
        print("[INFO] バックテスト完了")
        
    finally:
        # テンポラリファイルをクリーンアップ
        if os.path.exists(temp_config):
            os.remove(temp_config)
            print(f"[INFO] テンポラリ config を削除: {temp_config}")


def main():
    parser = argparse.ArgumentParser(
        description='バックテスト実行 - ロギング制御オプション付き',
        epilog='例: python3 run_backtest.py --full-logging'
    )
    
    parser.add_argument(
        '--full-logging',
        action='store_true',
        help='全ログ出力モード (logging_interval=1) - グラフ分析用'
    )
    
    parser.add_argument(
        '--logging-interval',
        type=int,
        metavar='N',
        help='ロギング間隔を指定 (1=毎回, 100=100回毎, etc)'
    )
    
    parser.add_argument(
        '--period',
        nargs=2,
        metavar=('START', 'END'),
        help='バックテスト期間を指定 (例: "2025/11/01 00:00" "2025/11/25 23:59")'
    )
    
    parser.add_argument(
        '--fast-summary',
        action='store_true',
        help='高速サマリモード - Excel/レポート/可視化をスキップ'
    )
    
    args = parser.parse_args()
    
    # ロギング間隔を決定
    if args.full_logging:
        logging_interval = 1
        print("[INFO] フル ロギングモード: logging_interval=1")
    elif args.logging_interval:
        logging_interval = args.logging_interval
        print(f"[INFO] カスタム ロギング間隔: {logging_interval}")
    else:
        logging_interval = Config.get_logging_interval()
        print(f"[INFO] デフォルト ロギング間隔: {logging_interval}")
    
    # 期間
    start_time = args.period[0] if args.period else None
    end_time = args.period[1] if args.period else None
    
    # 高速サマリモード
    fast_summary = 1 if args.fast_summary else 0
    
    # バックテスト実行
    run_backtest(
        logging_interval=logging_interval,
        start_time=start_time,
        end_time=end_time,
        fast_summary=fast_summary
    )


if __name__ == '__main__':
    main()
