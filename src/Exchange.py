import ccxt

"""
Exchangeクラス:

このクラスは仮想通貨の取引所との通信を担当します。APIキーの認証、注文の発行、口座残高の取得などの機能を提供します。
各取引所に対するサブクラスを作成して、取引所固有の実装を処理できます。たとえば、BinanceExchange、CoinbaseExchangeなどのサブクラスを考えることができます。
"""

class Exchange:
    def __init__(self, api_key, api_secret):
        self.api_key = api_key
        self.api_secret = api_secret

    def get_account_balance(self):
        raise NotImplementedError("Subclasses must implement this method.")

    def execute_order(self, symbol, side, quantity, price, order_type):
        raise NotImplementedError("Subclasses must implement this method.")
