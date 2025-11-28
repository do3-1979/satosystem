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
from indicator_service import IndicatorService
from path_utils import PathManager, load_api_keys_from_file


def create_temp_config(logging_interval=1, fast_summary=0, start_time=None, end_time=None):
    """
    テンポラリ config ファイルを作成
    
    Args:
        logging_interval (int): ロギング間隔
        fast_summary (int): 高速サマリモード (0=OFF, 1=ON)
        start_time (str): 開始時刻 (format: "YYYY/MM/DD HH:MM")
        end_time (str): 終了時刻 (format: "YYYY/MM/DD HH:MM")
    
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
        
        # 期間を設定
        if start_time and end_time:
            import re
            # start_time を置換
            content = re.sub(
                r'start_time = .+',
                f'start_time = {start_time}',
                content
            )
            # end_time を置換
            content = re.sub(
                r'end_time = .+',
                f'end_time = {end_time}',
                content
            )
        
        tmp.write(content)
        return tmp.name


def run_backtest(logging_interval=1, start_time=None, end_time=None, fast_summary=0, log_file=None):
    """
    バックテストを実行
    
    Args:
        logging_interval (int): ロギング間隔（1=全出力, 100=100回毎, etc）
        start_time (str): 開始時刻 (format: "YYYY/MM/DD HH:MM")
        end_time (str): 終了時刻 (format: "YYYY/MM/DD HH:MM")
        fast_summary (int): 高速サマリモード (0=OFF, 1=ON)
        log_file (str): 可視化用ログファイル指定
    """
    # テンポラリ config を作成
    temp_config = create_temp_config(logging_interval, fast_summary, start_time, end_time)
    
    try:
        # Config に设定ファイルを指定してキャッシュをクリア
        Config.set_config_file(temp_config)
        # 新しい config ファイルを読み込む
        Config.reload_config()
        
        # 期間を上書き（既に config に反映済み）
        if start_time and end_time:
            print(f"[INFO] 期間を指定: {start_time} ～ {end_time}")
        
        print(f"[INFO] ロギング間隔: {logging_interval}")
        print(f"[INFO] 高速サマリモード: {'ON' if fast_summary else 'OFF'}")
        
        # バックテスト実行（bot.py の本来の初期化パターンに準拠）
        config_instance = Config()
        
        # APIキーを .api_key ファイルから読み込む（優先度高）
        api_key_file = PathManager.get_api_key_file()
        api_key = None
        api_secret = None
        
        if api_key_file.exists():
            print(f"[INFO] Loading API keys from: {api_key_file}")
            api_key, api_secret = load_api_keys_from_file()
        
        # .api_key から取得できない場合は Config から取得
        if not api_key or not api_secret:
            api_key = config_instance.get_api_key()
            api_secret = config_instance.get_api_secret()
        
        # APIキーが有効か確認
        if api_key == "YOUR_API_KEY" or api_secret == "YOUR_API_SECRET":
            print("[ERROR] Please create src/.api_key with API credentials")
            return
        
        # .api_key から読み込めた場合は、既存の temp_config に APIキーを追加反映
        if api_key and api_secret and temp_config:
            print("[INFO] Injecting API keys into temp config")
            try:
                with open(temp_config, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # APIキーを置換
                content = content.replace("YOUR_API_KEY", api_key)
                content = content.replace("YOUR_API_SECRET", api_secret)
                
                with open(temp_config, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                # Config をリロード
                Config.reload_config()
                print("[INFO] Config reloaded with API keys from .api_key file")
            except Exception as e:
                print(f"[WARN] Failed to inject API keys: {e}")
        
        # Exchange
        exchange = BybitExchange(api_key, api_secret)

        # 資産管理クラスを初期化
        portfolio = Portfolio()
        
        # IndicatorServiceを初期化（PriceDataManagementとRiskManagementで共有）
        indicator_service = IndicatorService()
        
        # 価格情報クラスを初期化
        price_data_management = PriceDataManagement(indicator_service=indicator_service)

        # リスク戦略クラスを初期化
        risk_management = RiskManagement(price_data_management, portfolio, indicator_service=indicator_service)

        # 取引戦略クラスを初期化
        strategy = TradingStrategy(price_data_management, risk_management, portfolio)
        
        # Bot
        bot = Bot(exchange, strategy, risk_management, price_data_management, portfolio)
        
        # logging_interval を Botに反映させる（Config リロード後）
        bot._logging_interval = Config.get_logging_interval()
        
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
        '--log-file',
        metavar='LOG_FILE',
        help='可視化に使用するログファイルを指定 (例: "logs/20251126182303.zip")'
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
    # NOTE: デフォルトでは fast_summary_mode=0（グラフ出力ON）
    # ユーザーが --fast-summary を指定した場合のみ fast_summary_mode=1（グラフ出力OFF）
    fast_summary = 1 if args.fast_summary else 0
    
    # ログファイル指定
    log_file = args.log_file if hasattr(args, 'log_file') else None
    
    # バックテスト実行
    run_backtest(
        logging_interval=logging_interval,
        start_time=start_time,
        end_time=end_time,
        fast_summary=fast_summary,
        log_file=log_file
    )


if __name__ == '__main__':
    main()
