import os
import configparser
from bot import Bot

def run_bot_with_config(config_file):
    config = configparser.ConfigParser()
    config.read(config_file)

    # 取引所クラスを初期化
    exchange = BybitExchange(config.get('API', 'api_key'), config.get('API', 'api_secret'))

    # 資産管理クラスを初期化
    portfolio = Portfolio()
    
    # 価格情報クラスを初期化
    price_data_management = PriceDataManagement()

    # リスク戦略クラスを初期化
    risk_management = RiskManagement(price_data_management, portfolio)

    # 取引戦略クラスを初期化
    strategy = TradingStrategy(price_data_management, risk_management, portfolio)

    # Bot クラスを初期化
    bot = Bot(exchange, strategy, risk_management, price_data_management, portfolio)

    # パラメータを設定してBotを実行
    bot.run()

if __name__ == "__main__":
    config_folder = "backtest_config"

    # backtest_config フォルダ内の設定ファイルを取得
    config_files = [os.path.join(config_folder, filename) for filename in os.listdir(config_folder) if filename.endswith(".ini")]

    # 各設定ファイルを使用してBotを実行
    for config_file in config_files:
        run_bot_with_config(config_file)
