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

    def show_trade_data(self, trade_data):
        self.logger.log(f"時刻: {trade_data['real_time']}"
            f"  高値: {trade_data['high_price']:>5.0f}"
            f"  安値: {trade_data['low_price']:>5.0f}"
            f"  終値: {trade_data['close_price']:>5.0f}"
            f"  購入価格: {trade_data['positions']['position_price']:>5.0f}"
            f"  STOP: {trade_data['stop_price']:>5.0f}"
            f"  ボラ: {trade_data['volatility']:>7.2f}"
            f"  出来高: {trade_data['Volume']:>7.2f}"
            f"  SIGNAL: {trade_data['decision']}"
            f" -> {trade_data['side']}"
            f"  購入量: {trade_data['position_size']:.4f}"
            f"  資産: {trade_data['positions']['quantity']:.4f}"
            f"  ポジ: {trade_data['positions']['side']}"
            f"  みなし損益: {trade_data['profit_and_loss']:>4.0f}"
            f"  累計損益: {trade_data['total_profit_and_loss']:>4.0f}"
            #f"  総量: {trade_data['total_size']}"
            #f"  DCH: {trade_data['dc_h']}"
            #f"  DCL: {trade_data['dc_l']}"
            #f"  PVO: {trade_data['pvo_val']}"
            #f"  出来高: {trade_data['stop_offset']}"
            #f"  出来高: {trade_data['stop_psar_stop_offset']}"
            #f"  出来高: {trade_data['stop_price_surge_stop_offset']}"
        )
        return

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

        # TODO tryはエラーなくなるまで未実装 → 各処理側で実装する
        while True:
        #    try:
            log_zipped = False
            trade_executed = False
            # --------------------------------------------
            # 最初に価格情報の更新
            # --------------------------------------------
            if back_test_mode == 1:
                is_end = self.price_data_management.update_price_data_backtest()
                # バックテスト終端だったら抜ける
                if is_end == True:
                    self.logger.log("-------------------------------------------------------")
                    self.logger.log(f"最終ポートフォリオ: {self.portfolio.get_position_quantity()}")
                    self.logger.log(f"最終損益: {self.portfolio.get_profit_and_loss():>4.0f} [BTC/USD]")
                    self.logger.close_log_file()
                    self.logger.log("--- BOT END -------------------------------------------")
                    break
            else:
                self.price_data_management.update_price_data()
            
            # 取得情報を表示
            # self.price_data_management.show_latest_ohlcv()
            # 最新価格を取得
            price = self.price_data_management.get_ticker()

            # 取引所から口座残高を取得
            if back_test_mode == 1:
                balance_tether = config_instance.get_account_balance() * price + self.portfolio.get_profit_and_loss()
            else:
                balance = self.exchange.get_account_balance_total()
                balance_tether = balance * price
                # TODO シミュレーション用　口座0円のため
                balance_tether = config_instance.get_account_balance() * price + self.portfolio.get_profit_and_loss()

            # --------------------------------------------
            # 取引戦略に口座残高を渡してトレード判断を取得
            # --------------------------------------------
            trade_decision = self.strategy.make_trade_decision()
            # --------------------------------------------
            # 取引決定の場合
            # --------------------------------------------
            if trade_decision["decision"] != 'NONE' and trade_executed == False:
                # --------------------------------------------
                # 決定状態を表示
                #self.logger.log(f"シグナル発生: {strategy}")
                
                # 初回の分割ポジション計算
                if trade_decision["decision"] == "ENTRY":
                    position_size = self.risk_management.calculate_position_size(balance_tether)
                    quantity = position_size
                # 追加時は初回の分割サイズを踏襲
                elif trade_decision["decision"] == "ADD":
                    position_size = self.risk_management.get_position_size()
                    quantity = position_size
                # 清算時は全ポジション
                elif trade_decision["decision"] == "EXIT":
                    # 保有資産を取得
                    position_size = self.portfolio.get_position_quantity()
                    quantity = position_size['quantity']
                else:
                    raise

                # 注文クラス作成
                order = Order(config_instance.get_market(),
                              trade_decision["side"],
                              quantity,
                              price,
                              trade_decision["order_type"])

                #self.logger.log(order.to_dict())
                order_response = self.execute_order(order.to_dict())
                #self.logger.log(f"注文実行: {order_response}")
                # TODO エラー処理

                # --------------------------------------------
                # portfolio更新
                # --------------------------------------------
                if trade_decision["decision"] == "EXIT":
                    self.portfolio.clear_position_quantity(price)
                elif trade_decision["decision"] == "ENTRY" or trade_decision["decision"] == "ADD":
                    self.portfolio.add_position_quantity(quantity, trade_decision["side"], price)
                    # 前回のエントリ価格を更新
                    self.risk_management.update_last_entry_price(price)
                #self.logger.log(f"ポートフォリオ更新: {self.portfolio.get_position_quantity()}")
                #self.logger.log(f"損益: {self.portfolio.get_profit_and_loss()} [BTC/USD]")
                
                trade_executed = True
            else:
                trade_executed = False

            # --------------------------------------------
            # リスク制御を更新
            # --------------------------------------------
            self.risk_management.update_risk_status()

            # --------------------------------------------
            # ログに記録
            # --------------------------------------------
            trade_data = self.price_data_management.get_latest_ohlcv()
            # バックテスト時はclose priceをシミュレータ値に更新
            if back_test_mode == 1:
                trade_data['real_time'] = self.price_data_management.get_latest_close_time_dt()
                trade_data['close_price'] = price
            else:
                dt_now = datetime.now()
                trade_data['real_time'] = dt_now.strftime('%Y/%m/%d %H:%M:%S')
            trade_data['stop_price'] = self.risk_management.get_stop_price()
            trade_data['position_price'] = self.portfolio.get_position_price()
            trade_data['position_size'] = self.risk_management.get_position_size()
            position_size = self.portfolio.get_position_quantity()
            quantity = position_size['quantity']
            trade_data['position_quantity'] = quantity
            profit, loss = self.portfolio.calc_position_quantity(price)
            trade_data['profit_and_loss'] = profit - loss
            trade_data['total_profit_and_loss'] = self.portfolio.get_profit_and_loss()
            trade_data['volatility'] = self.price_data_management.get_volatility()
            trade_data['stop_offset'] = self.risk_management.get_stop_offset()
            trade_data['stop_psar_stop_offset'] = self.risk_management.get_psar_stop_offset()
            trade_data['stop_price_surge_stop_offset'] = self.risk_management.get_price_surge_stop_offset()
            
            # signal info
            signals = self.price_data_management.get_signals()
            trade_data['dc_h'] = signals['donchian']['info']['highest']
            trade_data['dc_l'] = signals['donchian']['info']['lowest']
            trade_data['pvo_val'] = signals['pvo']['info']['value']
            
            trade_data.update(trade_decision)
            trade_data.update(signals)

            # portfolio
            trade_data['positions'] = self.portfolio.get_position_quantity()

            # 取引データを表示
            # if back_test_mode == 0:
            self.show_trade_data(trade_data)
            
            # 取引データを記録
            self.logger.log_trade_data(trade_data)
        
            # イベント初期化
            self.strategy.initialize_trade_decision()
        
            # 一定の待ち時間を設けてループを繰り返す
            if back_test_mode == 0:
                time.sleep(self.bot_operation_cycle)

            # 2時間ごとにファイルを分けるかチェック
            if back_test_mode == 0:
                current_time = datetime.now()
            else:
                current_time = datetime.fromtimestamp(self.price_data_management.get_latest_close_time())

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
        order_response = 0
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
