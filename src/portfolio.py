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
        self.positions = {"BTC/USD": {"quantity": 0, "side": None}, "ETH/USD": {"quantity": 0, "side": None}}  # ポートフォリオ内の各通貨の保有ポジション量

    def get_position_quantity(self, symbol):
        """
        指定した通貨の保有ポジション量を取得
        """
        if symbol in self.positions:
            return self.positions[symbol]
        return 0

    def update_position_quantity(self, symbol, quantity, side):
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

    portfolio.update_position_quantity("BTC/USD", 1000, "BUY")
    
    btc = portfolio.get_position_quantity('BTC/USD')

    print(f"BTC/USD position quantity: {btc['quantity']} side: {btc['side']}")

    # ポートフォリオ全体を表示
    print(portfolio)
