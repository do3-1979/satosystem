"""
Botクラス:

メインのボットクラスです。Exchange、TradingStrategy、Portfolio、RiskManagementなどのクラスを組み合わせて、トレードの実行と監視を行います。
メインループを持ち、定期的に取引を実行し、ポートフォリオの状態を更新します。

このサンプルコードでは、Botクラスが取引所と取引戦略との連携を行っています。
Botクラスは定期的に口座残高を取得し、取引戦略に渡してトレード判断を取得します。
トレード判断に基づいて注文を実行し、一定の待ち時間を設けてループを繰り返します。

また、取引戦略については YourStrategy() の部分にあなたの取引戦略クラスを指定してください。
取引戦略クラスは、口座残高や市場データを分析し、トレード判断を返すロジックを実装する必要があります。
"""
import time
import Config
import BybitExchange

class Bot:
    def __init__(self, exchange, strategy):
        self.exchange = exchange
        self.strategy = strategy
        self.api_key = Config.get_api_key()  # Config クラスから api_key を取得
        self.api_secret = Config.get_api_secret()  # Config クラスから api_secret を取得


    def run(self):
        while True:
            try:
                # 取引所から口座残高を取得
                balance = self.exchange.get_account_balance()

                # 取引戦略に口座残高を渡してトレード判断を取得
                trade_decision = self.strategy.make_trade_decision(balance)

                # 取引戦略からの判断に基づいて注文を実行
                if trade_decision:
                    order_response = self.execute_order(trade_decision)
                    print("注文実行:", order_response)

                # 一定の待ち時間を設けてループを繰り返す
                time.sleep(60)  # 例: 1分ごとに実行

            except Exception as e:
                print("エラー発生:", str(e))

    def execute_order(self, trade_decision):
        symbol = trade_decision['symbol']
        side = trade_decision['side']
        quantity = trade_decision['quantity']
        price = trade_decision['price']
        order_type = trade_decision['order_type']
        order_response = self.exchange.execute_order(symbol, side, quantity, price, order_type)
        return order_response

if __name__ == "__main__":
    # 取引所クラスを初期化
    exchange = BybitExchange()

    # 取引戦略クラスを初期化
    strategy = YourStrategy()

    # Botクラスを初期化
    bot = Bot(exchange, strategy)

    # ボットを実行
    bot.run()