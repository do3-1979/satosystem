import ccxt

class Exchange:
    """
    Exchangeクラス:

    このクラスは仮想通貨の取引所との通信を担当します。APIキーの認証、注文の発行、口座残高の取得などの機能を提供します。
    各取引所に対するサブクラスを作成して、取引所固有の実装を処理できます。たとえば、BinanceExchange、CoinbaseExchangeなどのサブクラスを考えることができます。
    """
    def __init__(self, api_key, api_secret):
        """
        Exchangeクラスを初期化します。

        Args:
            api_key (str): 取引所のAPIキー
            api_secret (str): 取引所のAPIシークレット
        """
        self.api_key = api_key
        self.api_secret = api_secret

    def get_account_balance(self):
        """
        口座の残高情報を取得します。
        
        Returns:
            dict: 口座の残高情報
        """
        raise NotImplementedError("Subclasses must implement this method.")

    def execute_order(self, symbol, side, quantity, price, order_type):
        """
        注文を発行します。

        Args:
            symbol (str): トレード対象の通貨ペア（例: 'BTC/USD'）
            side (str): 注文の種類（'buy'または'sell'）
            quantity (float): 注文数量
            price (float or None): 注文価格（市場価格注文の場合はNone）
            order_type (str): 注文のタイプ（'limit'または'market'）

        Returns:
            dict: 注文の実行結果
        """
        raise NotImplementedError("Subclasses must implement this method.")
