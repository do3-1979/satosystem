"""
Orderクラス:

注文情報を格納するクラスです。注文のタイプ（買い/売り）、通貨ペア、数量、価格などの情報を保持します。

Args:
    symbol (str): 通貨ペア (例: 'BTC/USD')
    side (str|Side): 注文の方向（内部表記 'BUY'/'SELL'/'NONE'）
    quantity (float): 注文数量
    price (float|None): 注文価格（limit注文で使用、market時は無視）
    order_type (str): 注文タイプ ('limit' または 'market')
"""

from side import normalize_side


class Order:
    def __init__(self, symbol, side, quantity, price=None, order_type='limit', context='entry', timeout_sec=None):
        """
        Orderクラスを初期化します。

        Args:
            symbol (str): 通貨ペア (例: 'BTC/USD')
            side (str|Side): 注文の方向 ('BUY' または 'SELL')
            quantity (float): 注文数量
            price (float, optional): 注文価格 (limit注文の場合にのみ指定). Defaults to None.
            order_type (str, optional): 注文タイプ ('limit'または'market'). Defaults to 'limit'.
            context (str, optional): 注文のコンテキスト ('entry', 'pyramiding', 'partial_exit', 
                                    'stoploss', 'trailing_stop', 'time_exit'). Defaults to 'entry'.
            timeout_sec (int, optional): Limit注文のタイムアウト秒数. Defaults to None.
        """
        self.symbol = symbol
        self.side = normalize_side(side)
        self.quantity = quantity
        self.price = price
        self.context = context
        self.timeout_sec = timeout_sec
        # コンテキストに応じて注文タイプを決定
        self.order_type = self._determine_order_type(context, order_type)
        # トレード指標用フィールド（約定時）
        self.entry_price = price if side in ('BUY','SELL') else None
        self.mfe = 0.0  # 最大含み益幅
        self.mae = 0.0  # 最大含み損幅
        self.bars_held = 0
        self.atr_at_entry = 0.0
        self.classification = 'UNCLASSIFIED'
        self.capture_ratio = 0.0
        self.loss_containment_ratio = 0.0

    def _determine_order_type(self, context, fallback_type):
        """
        コンテキストに応じた注文タイプを自動決定します。

        Args:
            context (str): 注文のコンテキスト
            fallback_type (str): フォールバック（明示的に指定された注文タイプ）

        Returns:
            str: 決定された注文タイプ ('limit' or 'market')
        """
        # コンテキストに基づいて推奨される注文タイプ
        context_order_type = {
            'entry': 'market',           # エントリーは成行（確実性優先）
            'pyramiding': 'limit',       # ピラミッティングは指値（効率性優先）
            'partial_exit': 'limit',     # 部分利確は指値（価格指定）
            'stoploss': 'market',        # 損切は成行（速度優先）
            'trailing_stop': 'market',   # トレーリングストップは成行（速度優先）
            'time_exit': 'limit',        # 時間ベースは指値（初期段階）
        }
        
        # コンテキストに応じた注文タイプを返却
        if context in context_order_type:
            return context_order_type[context]
        
        # 未知のコンテキストの場合はフォールバック
        return fallback_type

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
            'context': self.context,
        }
        if self.order_type == 'limit':
            order_dict['price'] = self.price
        else:
            order_dict['price'] = 0
        if self.timeout_sec is not None:
            order_dict['timeout_sec'] = self.timeout_sec
        return order_dict

    def __str__(self):
        return f"Order: {self.side} {self.quantity} {self.symbol} at {self.price} ({self.order_type})"
