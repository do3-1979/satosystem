# BybitExchange.py

import ccxt
from Exchange import Exchange  # Exchangeモジュールをインポート

class BybitExchange(Exchange):
    def __init__(self, api_key, api_secret):
        super().__init__(api_key, api_secret)

        self.api_key = api_key
        self.api_secret = api_secret

        self.exchange = ccxt.bybit({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
        })

    def get_account_balance(self):
        balance = self.exchange.fetch_balance()
        return balance

    def execute_order(self, symbol, side, quantity, price, order_type):
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

# ユーザーごとのAPIキーとAPIシークレットを設定
api_key = 'YOUR_API_KEY'
api_secret = 'YOUR_API_SECRET'

# BybitExchangeクラスを初期化
exchange = BybitExchange(api_key, api_secret)

# 口座残高情報を取得
balance = exchange.get_account_balance()
print("口座残高:", balance)

# 注文を発行 (例: BTC/USD マーケットで1BTCを買う)
order_response = exchange.execute_order('BTC/USD', 'buy', 1, None, 'market')
print("注文結果:", order_response)