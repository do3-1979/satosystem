"""
Portfolioクラス:

ポートフォリオの状態を管理します。保有している仮想通貨の数量、資金残高などの情報を追跡します。
取引が行われるたびに、ポートフォリオの状態が更新されます。

このサンプルコードでは、Portfolioクラスがポートフォリオ内の各通貨の保有数量を保持し、
get_asset_quantity() メソッドで保有数量を取得し、update_asset_quantity() メソッドで
保有数量を更新できるようになっています。
また、サンプルとしてポートフォリオにBTC/USDとETH/USDの保有数量を追加し、
取得して表示する例も示しています。ポートフォリオ全体を文字列として表示することも可能です。
必要に応じて、このクラスを拡張してポートフォリオに関連する他の情報を追加できます。

"""
from config import Config  # Config クラスのインポート

# Portfolio クラスの定義
class Portfolio:
    def __init__(self):
        self.positions = {"BTC/USD": {"quantity": 0, "side": None, "position_price": 0 }, "ETH/USD": {"quantity": 0, "side": None, "position_price": 0}}  # ポートフォリオ内の各通貨の保有ポジション量
        self.market_type = Config.get_market()

    def get_position_quantity(self):
        """
        指定した通貨の保有ポジション量を取得
        """
        if self.market_type in self.positions:
            return self.positions[self.market_type]
        return 0

    def get_position_side(self):
        """
        指定した通貨の保有ポジション量を取得
        """
        if self.market_type in self.positions:
            return self.positions[self.market_type]["side"]
        return None

    def get_position_price(self):
        """
        指定した通貨の保有ポジション量を取得
        """
        if self.market_type in self.positions:
            return self.positions[self.market_type]["position_price"]
        return None

    def add_position_quantity(self, quantity, side, price):
        """
        通貨の保有ポジション量を更新
        """
        # TODO sideのチェック
        # TODO position_price を平均取得単価で計算しなおし
        # 既存のquantity * position_price + 取得したquantity * position_price / 総quantity
        # TODO 最後にquantity の更新
        self.positions[self.market_type]["quantity"] = quantity
        self.positions[self.market_type]["side"] = side
        self.positions[self.market_type]["position_price"] = 0

    def clear_position_quantity(self):
        """
        通貨の保有ポジション量を更新
        """
        self.positions[self.market_type]["quantity"] = 0
        self.positions[self.market_type]["side"] = None
        self.positions[self.market_type]["position_price"] = 0

    def get_position_quantity_with_symbol(self, symbol):
        """
        指定した通貨の保有ポジション量を取得
        """
        if symbol in self.positions:
            return self.positions[symbol]
        return 0

    def get_position_side_with_symbol(self, symbol):
        """
        指定した通貨の保有ポジション量を取得
        """
        if symbol in self.positions:
            return self.positions[symbol]["side"]
        return None

    def update_position_quantity_with_symbol(self, symbol, quantity, side):
        """
        通貨の保有ポジション量を更新
        """
        self.positions[symbol]["quantity"] = quantity
        self.positions[symbol]["side"] = side

    def __str__(self):
        portfolio_str = "Portfolio:\n"
        for symbol, detail in self.positions.items():
            portfolio_str += f"{symbol}: {detail}\n"
        return portfolio_str

# ポートフォリオのサンプル
if __name__ == "__main__":
    # ポートフォリオクラスを初期化
    portfolio = Portfolio()

    portfolio.update_position_quantity_with_symbol("BTC/USD", 1000, "BUY")
    
    btc = portfolio.get_position_quantity_with_symbol('BTC/USD')

    print(f"BTC/USD position quantity: {btc['quantity']} side: {btc['side']}")

    portfolio.update_position_quantity(2000, "BUY")
    
    btc = portfolio.get_position_quantity()

    print(f"BTC/USD position quantity: {btc['quantity']} side: {btc['side']}")

    # ポートフォリオ全体を表示
    print(portfolio)
