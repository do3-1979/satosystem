"""
Orderクラス:

注文情報を格納するクラスです。注文のタイプ（買い/売り）、通貨ペア、数量、価格などの情報を保持します。

このサンプルコードでは、Orderクラスが注文に関連する情報を保持し、
to_dict() メソッドを使用して注文情報を辞書形式で取得できるようになっています。
また、サンプルとしてLimit注文とMarket注文の作成例も示しています。
注文情報を辞書形式で取得することで、取引所APIに注文を送信する際に便利です。
必要に応じて、このクラスを拡張して注文に関連する他の情報を追加することができます。

"""
class Order:
    def __init__(self, symbol, side, quantity, price=None, order_type='limit'):
        self.symbol = symbol  # 通貨ペア (例: 'BTC/USD')
        self.side = side  # 注文の方向 ('buy'または'sell')
        self.quantity = quantity  # 注文数量
        self.price = price  # 注文価格 (limit注文の場合にのみ指定)
        self.order_type = order_type  # 注文タイプ ('limit'または'market')

    def to_dict(self):
        order_dict = {
            'symbol': self.symbol,
            'side': self.side,
            'quantity': self.quantity,
            'order_type': self.order_type,
        }
        if self.order_type == 'limit':
            order_dict['price'] = self.price
        return order_dict

    def __str__(self):
        return f"Order: {self.side} {self.quantity} {self.symbol} at {self.price} ({self.order_type})"

# 注文のサンプル
if __name__ == "__main__":
    # Limit注文
    limit_order = Order(symbol='BTC/USD', side='buy', quantity=1, price=45000)
    print(limit_order)

    # Market注文
    market_order = Order(symbol='ETH/USD', side='sell', quantity=5, order_type='market')
    print(market_order)

    # 注文情報を辞書形式で取得
    order_info = limit_order.to_dict()
    print(order_info)
