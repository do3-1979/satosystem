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
from datetime import datetime
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
        config_instance = Config()
        back_test_mode = config_instance.get_back_test_mode()
        
        if back_test_mode == 1:
            self.logger.log("--- BOT START (BACK TEST MODE)-------------------------")
            self.price_data_management.initialise_back_test_ohlcv_data()
        else:
            self.logger.log("--- BOT START -----------------------------------------")

        self.logger.log(str(config_instance))
        self.logger.log("-------------------------------------------------------")

        # TODO tryはエラーなくなるまで未実装
        while True:
        #    try:
            log_zipped = False
            trade_executed = False
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
            if back_test_mode == 1:
                balance_tether = config_instance.get_account_balance() * price + self.portfolio.get_profit_and_loss()
            else:
                balance = self.exchange.get_account_balance_total()
                balance_tether = balance * price

            # --------------------------------------------
            # 取引戦略に口座残高を渡してトレード判断を取得
            # --------------------------------------------
            trade_decision = self.strategy.make_trade_decision()
            # --------------------------------------------
            # 取引決定の場合
            # --------------------------------------------
            if trade_decision["decision"] != 'NONE' and trade_executed == False:
                # --------------------------------------------
                # シグナル発生
                self.price_data_management.show_latest_signals()
                # 決定状態を表示
                self.logger.log(f"シグナル発生: {strategy}")
                
                # 清算時は全ポジション
                if trade_decision["decision"] == "EXIT":
                    # 保有資産を取得
                    position_size = self.portfolio.get_position_quantity(self.market_type)
                # リスクからポジションサイズ決定
                else: # TODO "ADD" の場合、連続追加発注を検討するべき
                    position_size = self.risk_management.calculate_position_size(balance_tether)
                # ベースに帰着
                quantity = position_size

                self.logger.log(f"購入量: {position_size} 市場価格：{position_size * price} [BTC/USD]")

                # 注文クラス作成
                order = Order(trade_decision["side"],
                                quantity,
                                price,
                                trade_decision["order_type"])

                self.logger.log("order:", order)
                order_response = self.execute_order(order)
                self.logger.log("注文実行:", order_response)
                # TODO エラー処理

                # --------------------------------------------
                # portfolio更新
                # --------------------------------------------
                self.risk_management.update_last_entry_price(price)
                
                if trade_decision["decision"] == "EXIT":
                    self.portfolio.clear_position_quantity(price)
                elif trade_decision["decision"] == "ENTRY" or trade_decision["decision"] == "ADD":
                    self.portfolio.add_position_quantity(quantity, trade_decision["side"], price)
                    
                # イベント初期化
                self.strategy.initialize_trade_decision()
                trade_executed = True
            else:
                trade_executed = False

            # --------------------------------------------
            # ログに記録
            # --------------------------------------------
            trade_data = self.price_data_management.get_latest_ohlcv()
            dt_now = datetime.now()
            trade_data['real_time'] = dt_now.strftime('%Y/%m/%d %H:%M:%S')
            trade_data['stop_price'] = self.risk_management.get_stop_price()
            trade_data['position_size'] = self.risk_management.get_position_size()
            trade_data['total_size'] = self.risk_management.get_total_size()
            trade_data['profit_and_loss'] = self.portfolio.get_profit_and_loss()
            trade_data['volatility'] = self.price_data_management.get_volatility()   
            
            # signal info
            signals = self.price_data_management.get_signals()
            trade_data['dc_h'] = signals['donchian']['info']['highest']
            trade_data['dc_l'] = signals['donchian']['info']['lowest']
            trade_data['pvo_val'] = signals['pvo']['info']['value']
            
            trade_data.update(trade_decision)
            trade_data.update(signals)

            # portfolio
            trade_data['positions'] = self.portfolio.get_position_quantity()

            # 取引データを記録
            self.logger.log_trade_data(trade_data)

            # 一定の待ち時間を設けてループを繰り返す
            if back_test_mode == 0:
                time.sleep(self.bot_operation_cycle)

                # 2時間ごとにファイルを分けるかチェック
                current_time = datetime.now()
                if log_zipped == False and int(current_time.strftime("%H")) % 2 == 0 and int(current_time.strftime("%M")) == 0:
                    # ログをローテート
                    self.logger.close_log_file()
                    self.logger.compress_logs()  # 圧縮
                    self.logger.open_log_file()
                    log_zipped = True
                else:
                    log_zipped = False

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
        symbol = order['symbol'] # execute orderには使わない
        side = order['side']
        quantity = order['quantity']
        order_type = order['order_type']
        if order_type == 'limit':
            price = order['price']
        else:
            price = 0

        # TODO テスト処理
        #order_response = self.exchange.execute_order(side, quantity, price, order_type)
        return order_response

if __name__ == "__main__":
    # bot class test flag
    bot_order_test = False
    
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

    # Bot クラスを初期化
    bot = Bot(exchange, strategy, risk_management, price_data_management, portfolio)

    if bot_order_test == True:
        # 注文クラス作成
        price = price_data_management.get_ticker()
        order = Order("BTC/USD", "buy", 1, price, "market")

        print(f"order test: {order}")
        order_response = bot.execute_order(order.to_dict())
        print(f"注文実行:{order_response}")
    else:
        # ボットを実行
        bot.run()
