import os
import shutil
import time
import sys
from configparser import ConfigParser
from config import Config
from price_data_management import PriceDataManagement
from bybit_exchange import BybitExchange
from trading_strategy import TradingStrategy
from risk_management import RiskManagement
from portfolio import Portfolio
from order import Order
from bot import Bot  # Assuming the Bot class is in a separate file named bot.py

def find_config_files(directory):
    """
    指定したディレクトリ内のconfig_*.ini ファイルのリストを取得します。

    Args:
        directory (str): 検索対象のディレクトリパス

    Returns:
        list: config_*.ini ファイルのリスト
    """
    config_files = [f for f in os.listdir(directory) if f.startswith("config_") and f.endswith(".ini")]
    return [os.path.join(directory, config_file) for config_file in config_files]

def main():
    total_start_time = time.time()

    # 1. バックアップとしてconfig.iniをconfig_bak.iniにリネームする
    shutil.copy("config.ini", "config_bak.ini")

    # 2. output_configs以下のconfig_*.ini ファイルからファイルリストを作成
    config_files = find_config_files("output_configs")

    # 3. ファイルリストから一つずつconfig.iniにコピーしてbot.pyを実行する
    for idx, config_file in enumerate(config_files):
        # コピーしてconfig.iniに変更
        shutil.copy(config_file, "config.ini")
    
        # Replace API_KEY and API_SECRET in config.ini using replace_api_key.sh
        os.system("./replace_api_key.sh")
    
        # 取引所クラスを初期化
        exchange = BybitExchange(Config.get_api_key(), Config.get_api_secret())
        # 資産管理クラスを初期化（唯一であること TODO シングルトン化）
        portfolio = Portfolio()
        # 価格情報クラスを初期化
        price_data_management = PriceDataManagement()
        # リスク戦略クラスを初期化
        risk_management = RiskManagement(price_data_management, portfolio)
        # 取引戦略クラスを初期化
        strategy = TradingStrategy(price_data_management, risk_management, portfolio)
        # ボットのインスタンスを作成
        bot = Bot(exchange, strategy, risk_management, price_data_management, portfolio)

        # ボットを実行
        start_time = time.time()
        bot.run()
        elapsed_time = time.time() - start_time

        # 処理中のconfigファイルの名前と進捗率を表示
        progress = (idx + 1) / len(config_files) * 100
        print(f"Processing: {config_file}, Progress: {progress:.2f}%, Elapsed Time: {format_elapsed_time(elapsed_time)}")
        
    total_elapsed_time = time.time() - total_start_time
    print(f"Total Elapsed Time: {format_elapsed_time(total_elapsed_time)}")

    # 4. バックアップしたconfig_bak.iniをconfig.iniに戻す(config.iniに上書きして戻す)
    shutil.move("config_bak.ini", "config.ini")

def format_elapsed_time(seconds):
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return "{:02}:{:02}:{:02}".format(int(hours), int(minutes), int(seconds))

if __name__ == "__main__":
    main()
