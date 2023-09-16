"""
Bot クラス:

メインのボットクラスです。Exchange、TradingStrategy、Portfolio、RiskManagement などのクラスを組み合わせて、トレードの実行と監視を行います。
メインループを持ち、定期的に取引を実行し、ポートフォリオの状態を更新します。

このサンプルコードでは、Bot クラスが取引所と取引戦略との連携を行っています。
Bot クラスは定期的に口座残高を取得し、取引戦略に渡してトレード判断を取得します。
トレード判断に基づいて注文を実行し、一定の待ち時間を設けてループを繰り返します。

また、取引戦略については YourStrategy() の部分にあなたの取引戦略クラスを指定してください。
取引戦略クラスは、口座残高や市場データを分析し、トレード判断を返すロジックを実装する必要があります。
"""
import os
import time
from logger import Logger
from config import Config
from price_data_management import PriceDataManagement
from bybit_exchange import BybitExchange
from trading_strategy import TradingStrategy
from risk_management import RiskManagement

class Bot:
    def __init__(self, exchange, strategy, risk_management, price_data_management):
        """
        Bot クラスの初期化

        Args:
            exchange (Exchange): 取引所クラスのインスタンス
            strategy (TradingStrategy): 取引戦略クラスのインスタンス
        """
        self.exchange = exchange
        self.strategy = strategy
        self.risk_management = risk_management
        self.price_data_management = price_data_management
        self.logger = Logger()

        self.bot_operation_cycle = Config.get_bot_operation_cycle()

    def run(self):
        """
        ボットのメインループを実行します。口座残高を取得し、取引戦略に基づいてトレードを実行します。
        """
        self.logger.log("--- BOT START -----------------------------------------")
        config_instance = Config()
        self.logger.log(str(config_instance))
        self.logger.log("-------------------------------------------------------")

        while True:
            try:
                # --------------------------------------------
                # 最初に価格情報の更新
                # --------------------------------------------
                self.price_data_management.update_price_data()
                
                # 取得情報を表示
                self.price_data_management.show_latest_ohlcv()
                # 最新価格を取得
                price = self.price_data_management.get_ticker()
                # ボラティリティを取得
                volatility = self.price_data_management.get_volatility()

                # 取引所から口座残高を取得
                #balance = self.exchange.get_account_balance_total()
                balance = 10000

                # --------------------------------------------
                # 取引戦略に口座残高を渡してトレード判断を取得
                # TODO trade_decisionは辞書型　Orderクラスを作ったが活用してない
                # --------------------------------------------
                trade_decision = self.strategy.make_trade_decision(balance)

                # --------------------------------------------
                # 取引戦略からの判断に基づいて注文を実行
                # --------------------------------------------
                position_size = self.risk_management.calculate_position_size(balance, price, volatility)
                quantity = position_size * price

                if trade_decision:
                    order_response = self.execute_order(trade_decision)
                    print("注文実行:", order_response)

                # --------------------------------------------
                # TODO portfolio更新
                # --------------------------------------------                    

                # TODO 出口判断を取得
                
                # TODO 出口取引を決定
                if trade_decision:
                    order_response = self.execute_order(trade_decision)
                    print("清算実行:", order_response)

                # --------------------------------------------
                # TODO portfolio更新
                # --------------------------------------------                    

                # 一定の待ち時間を設けてループを繰り返す
                time.sleep(self.bot_operation_cycle)

            except Exception as e:
                print("エラー発生:", str(e))
                time.sleep(self.bot_operation_cycle)

    def execute_order(self, trade_decision):
        """
        注文を実行します。

        Args:
            trade_decision (dict): トレード判断に基づいた注文情報

        Returns:
            dict: 注文の実行結果
        """
        symbol = trade_decision['symbol']
        side = trade_decision['side']
        quantity = trade_decision['quantity']
        price = trade_decision['price']
        order_type = trade_decision['order_type']
        order_response = self.exchange.execute_order(symbol, side, quantity, price, order_type)
        return order_response

if __name__ == "__main__":
    # 取引所クラスを初期化
    exchange = BybitExchange(Config.get_api_key(), Config.get_api_secret())

    # 取引戦略クラスを初期化
    strategy = TradingStrategy()

    # 取引戦略クラスを初期化
    risk_management = RiskManagement(exchange)

    # 価格情報クラスを初期化
    price_data_management = PriceDataManagement()

    # Bot クラスを初期化
    bot = Bot(exchange, strategy, risk_management, price_data_management)

    # ボットを実行
    bot.run()
