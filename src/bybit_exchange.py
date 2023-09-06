"""
BybitExchange クラス (Exchange クラスを継承):

Bybit 取引所との連携を行うためのクラスです。Exchange クラスを継承し、Bybit 取引所に特有の設定や操作を追加しています。

Attributes:
    api_key (str): ユーザーごとの API キー
    api_secret (str): ユーザーごとの API シークレット
    exchange (ccxt.Exchange): ccxt ライブラリの Bybit 取引所インスタンス

Methods:
    get_account_balance(self):
        口座の残高情報を取得します。

    execute_order(self, symbol, side, quantity, price, order_type):
        注文を発行します。

Raises:
    ValueError: 無効な order_type が指定された場合に発生します。

Usage:
    # ユーザーごとの API キーと API シークレットを設定
    api_key = 'YOUR_API_KEY'
    api_secret = 'YOUR_API_SECRET'

    # BybitExchange クラスを初期化
    exchange = BybitExchange(api_key, api_secret)

    # 口座残高情報を取得
    balance = exchange.get_account_balance()
    print("口座残高:", balance)

    # 注文を発行 (例: BTC/USD マーケットで1BTC を買う)
    order_response = exchange.execute_order('BTC/USD', 'buy', 1, None, 'market')
    print("注文結果:", order_response)
"""
import ccxt
from config import Config
from exchange import Exchange  # Exchange モジュールをインポート

class BybitExchange(Exchange):
    def __init__(self, api_key, api_secret):
        """
        BybitExchange クラスの初期化

        Args:
            api_key (str): ユーザーごとの API キー
            api_secret (str): ユーザーごとの API シークレット
        """
        super().__init__(api_key, api_secret)

        self.api_key = api_key
        self.api_secret = api_secret

        self.exchange = ccxt.bybit({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
        })

    def get_account_balance(self):
        """
        口座の残高情報を取得します.

        Returns:
            dict: 口座の残高情報
        """
        balance = self.exchange.fetchBalance()
        return balance

    def execute_order(self, symbol, side, quantity, price, order_type):
        """
        注文を発行します.

        Args:
            symbol (str): トレードするペアのシンボル (例: 'BTC/USD')
            side (str): 注文のタイプ ('buy' または 'sell')
            quantity (float): 注文数量
            price (float or None): 注文価格 (市場注文の場合は None)
            order_type (str): 注文タイプ ('limit' または 'market')

        Returns:
            dict: 注文の実行結果
        """
        if order_type == 'limit':
            order = self.exchange.create_limit_order(
                symbol=symbol,
                side=side,
                amount=quantity,
                price=price
            )
        elif order_type == 'market':
            order = self.exchange.create_market_order(
                symbol=symbol,
                side=side,
                amount=quantity
            )
        else:
            raise ValueError("Invalid order_type. Use 'limit' or 'market'.")

        response = self.exchange.create_order(
            symbol=order['symbol'],
            side=order['side'],
            type=order['type'],
            quantity=order['amount'],
            price=order['price']
        )

        return response

if __name__ == "__main__":
    # BybitExchange クラスを初期化F
    exchange = BybitExchange(Config.get_api_key(), Config.get_api_secret())

    # 口座残高情報を取得
    balance = exchange.get_account_balance()
    print("口座残高:", balance)

    # 注文を発行 (例: BTC/USD マーケットで1BTC を買う)
    order_response = exchange.execute_order('BTCUSD', 'buy', 1, None, 'market')
    print("注文結果:", order_response)
