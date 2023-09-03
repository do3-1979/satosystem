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
import BybitExchange  # BybitExchange クラスのインポート
import Config  # Config クラスのインポート

# Portfolio クラスの定義
class Portfolio:
    def __init__(self, exchange):
        self.assets = {}  # ポートフォリオ内の各通貨の保有数量
        self.exchange = exchange  # 取引所クラスのインスタンス

    def get_asset_quantity(self, symbol):
        """
        指定した通貨の保有数量を取得
        :param symbol: 通貨ペア (例: 'BTC/USD')
        :return: 保有数量
        """
        if symbol in self.assets:
            return self.assets[symbol]
        return 0

    def update_asset_quantity(self, symbol, quantity):
        """
        通貨の保有数量を更新
        :param symbol: 通貨ペア (例: 'BTC/USD')
        :param quantity: 更新後の数量
        """
        self.assets[symbol] = quantity

    def get_account_balance(self):
        """
        口座の資産残高を取得し、ポートフォリオに反映
        """
        balance = self.exchange.get_account_balance()
        for asset in balance['total']:
            if asset != 'USD':
                symbol = f"{asset}/USD"  # 通貨ペアを作成
                quantity = balance['total'][asset]
                self.update_asset_quantity(symbol, quantity)

    def __str__(self):
        portfolio_str = "Portfolio:\n"
        for symbol, quantity in self.assets.items():
            portfolio_str += f"{symbol}: {quantity}\n"
        return portfolio_str

# ポートフォリオのサンプル
if __name__ == "__main__":
    # 取引所クラスを初期化
    exchange = BybitExchange(Config.get_api_key(), Config.get_api_secret())

    # ポートフォリオクラスを初期化
    portfolio = Portfolio(exchange)

    # 口座の資産残高を取得し、ポートフォリオに反映
    portfolio.get_account_balance()

    # 保有数量を取得して表示
    btc_quantity = portfolio.get_asset_quantity('BTC/USD')
    eth_quantity = portfolio.get_asset_quantity('ETH/USD')
    print(f"BTC/USD quantity: {btc_quantity}")
    print(f"ETH/USD quantity: {eth_quantity}")

    # ポートフォリオ全体を表示
    print(portfolio)
