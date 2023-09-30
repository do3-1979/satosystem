"""
Orderクラス:

注文情報を格納するクラスです。注文のタイプ（買い/売り）、通貨ペア、数量、価格などの情報を保持します。

Args:
    symbol (str): 通貨ペア (例: 'BTC/USD')
    side (str): 注文の方向 ('buy'または'sell')
    quantity (float): 注文数量
    price (float, optional): 注文価格 (limit注文の場合にのみ指定). Defaults to None.
    order_type (str, optional): 注文タイプ ('limit'または'market'). Defaults to 'limit'.
"""

class Order:
    def __init__(self, symbol, side, quantity, order_type, price=None):
        """
        Orderクラスを初期化します。

        Args:
            symbol (str): 通貨ペア (例: 'BTC/USD')
            side (str): 注文の方向 ('buy'または'sell')
            quantity (float): 注文数量
            price (float, optional): 注文価格 (limit注文の場合にのみ指定). Defaults to None.
            order_type (str, optional): 注文タイプ ('limit'または'market'). Defaults to 'limit'.
        """
        self.symbol = symbol
        self.side = side
        self.quantity = quantity
        self.price = price
        self.order_type = order_type

    def to_dict(self):
        """
        注文情報を辞書形式で取得します。

        Returns:
            dict: 注文情報の辞書
        """
        order_dict = {
            'symbol': self.symbol,
            'side': self.side,
            'quantity': self.quantity,
            'order_type': self.order_type,
        }
        if self.order_type == 'limit':
            order_dict['price'] = self.price
        else:
            order_dict['price'] = 0
        return order_dict

    def __str__(self):
        return f"Order: {self.side} {self.quantity} {self.symbol} at {self.price} ({self.order_type})"
