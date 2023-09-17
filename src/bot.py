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
from portfolio import Portfolio
from order import Order

class Bot:
    def __init__(self, exchange, strategy, risk_management, price_data_management, portfolio):
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
        self.portfolio = portfolio
        self.logger = Logger()

        self.market_type = Config.get_market()
        self.bot_operation_cycle = Config.get_bot_operation_cycle()

    def run(self):
        """
        ボットのメインループを実行します。口座残高を取得し、取引戦略に基づいてトレードを実行します。
        """
        self.logger.log("--- BOT START -----------------------------------------")
        config_instance = Config()
        self.logger.log(str(config_instance))
        self.logger.log("-------------------------------------------------------")

        # tryはエラーなくなるまで未実装
        while True:
        #    try:
            # --------------------------------------------
            # 最初に価格情報の更新
            # --------------------------------------------
            self.price_data_management.update_price_data()
            
            # 取得情報を表示
            self.price_data_management.show_latest_ohlcv()
            # 最新価格を取得
            price = self.price_data_management.get_ticker()

            # --------------------------------------------
            # リスク制御を更新
            # --------------------------------------------
            self.risk_management.update_risk_status()

            # 取引所から口座残高を取得
            #balance = self.exchange.get_account_balance_total()
            balance = 10000

            # --------------------------------------------
            # 取引戦略に口座残高を渡してトレード判断を取得
            # --------------------------------------------
            trade_decision = self.strategy.make_trade_decision()
            # --------------------------------------------
            # 取引決定の場合
            # --------------------------------------------
            if trade_decision["decision"] != None:
                # --------------------------------------------
                # シグナル発生
                self.price_data_management.show_latest_signals()
                
                # 清算時は全ポジション
                if trade_decision["decision"] == "EXIT":
                    # 保有資産を取得
                    position_size = self.portfolio.get_position_quantity(self.market_type)
                # リスクからポジションサイズ決定
                else:
                    position_size = self.risk_management.calculate_position_size(balance, price)
                # ベースに帰着
                quantity = position_size * price

                # 注文クラス作成
                order = Order(trade_decision["side"],
                                quantity,
                                price,
                                trade_decision["order_type"])

                print("order:", order)
                order_response = self.execute_order(order)
                print("注文実行:", order_response)
                # TODO エラー処理

                # --------------------------------------------
                # portfolio更新
                # --------------------------------------------
                self.portfolio.update_position_quantity(self.market_type, quantity, order.side)

            # 一定の待ち時間を設けてループを繰り返す
            time.sleep(self.bot_operation_cycle)

            #except Exception as e:
            #    print("エラー発生:", str(e))
            #   time.sleep(self.bot_operation_cycle)

    def execute_order(self, order):
        """
        注文を実行します。

        Args:
            trade_decision (dict): トレード判断に基づいた注文情報

        Returns:
            dict: 注文の実行結果
        """
        symbol = order['symbol']
        side = order['side']
        quantity = order['quantity']
        price = order['price']
        order_type = order['order_type']
        order_response = self.exchange.execute_order(symbol, side, quantity, price, order_type)
        return order_response

if __name__ == "__main__":
    # 取引所クラスを初期化
    exchange = BybitExchange(Config.get_api_key(), Config.get_api_secret())

    # 資産管理クラスを初期化（唯一であること TODO シングルトン化）
    portfolio = Portfolio()
    
    # 価格情報クラスを初期化（唯一であること TODO シングルトン化）
    price_data_management = PriceDataManagement()

    # リスク戦略クラスを初期化
    risk_management = RiskManagement(price_data_management)

    # 取引戦略クラスを初期化
    strategy = TradingStrategy(price_data_management, risk_management, portfolio)

    # Bot クラスを初期化
    bot = Bot(exchange, strategy, risk_management, price_data_management, portfolio)

    # ボットを実行
    bot.run()
