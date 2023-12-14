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
from logger import Logger
from config import Config  # Config クラスのインポート

# Portfolio クラスの定義
class Portfolio:
    def __init__(self):
        self.logger = Logger()
        self.positions = {'BTC/USD': {'quantity': 0, 'side': 'NONE', 'position_price': 0 }}  # ポートフォリオ内の各通貨の保有ポジション量
        self.market_type = Config.get_market()
        self.profit = 0
        self.loss = 0
        self.add_num = 0
        

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

    def get_profit_and_loss(self):
        """
        利益と損失を取得します。単位は[BTC/USD]
        """
        return self.profit - self.loss

    def add_position_quantity(self, quantity, side, price):
        """
        通貨の保有ポジション量を更新
        """
        current_quantity = self.positions[self.market_type]["quantity"]
        current_position_price = self.positions[self.market_type]["position_price"]
        current_side = self.positions[self.market_type]["side"]
        
        if current_quantity == 0 or current_side != side:
            # 初回の追加購入または既存ポジションとのsideが異なる場合
            self.positions[self.market_type]["quantity"] = quantity
            self.positions[self.market_type]["side"] = side
            self.positions[self.market_type]["position_price"] = price
            self.add_num = 1
        else:
            # 既存のポジションがある場合、平均取得単価を計算しなおす
            new_quantity = current_quantity + quantity
            new_position_price = ((current_quantity * current_position_price) + (quantity * price)) / new_quantity
            
            self.positions[self.market_type]["quantity"] = new_quantity
            self.positions[self.market_type]["side"] = side
            self.positions[self.market_type]["position_price"] = new_position_price
            
            self.add_num += 1

        return

    # 価格に対する現在のポジションの利益計算
    def calc_position_quantity(self, price):
        profit = 0
        loss = 0
        
        # 購入時の価格
        purchase_price = self.positions[self.market_type]["position_price"]

        # 購入量
        quantity = self.positions[self.market_type]["quantity"]

        # 買いまたは売りの判定
        side = self.get_position_side()
        if side == 'BUY':
            # 買いの場合は purchase_price - price が利益
            diff = (price - purchase_price) * quantity

        elif side == 'SELL':
            # 売りの場合は price - purchase_price が利益
            diff = (purchase_price - price) * quantity
        else:
            diff = 0  # 未保有の場合は利益・損失なし
            
        if diff >= 0:
            profit = diff
        else:
            loss = diff * (-1)

        return profit, loss

    def clear_position_quantity(self, price):
        """
        通貨の保有ポジション量を更新し、利益または損失を計算します。

        Args:
            price (float): 売却時の価格
        """
        profit = 0
        loss = 0

        # 利益と損失の合算
        profit, loss = self.calc_position_quantity(price)
        self.profit += profit
        self.loss += loss
        
        self.logger.log(f"今回の損益:{(profit - loss):.2f} [{self.market_type}] 利益累計:{self.profit:.2f} [{self.market_type}] 損失累計:{self.loss:.2f} [{self.market_type}] 損益累計:{(self.profit - self.loss):.2f} [{self.market_type}]です")

        # ポジション情報のクリア
        self.positions[self.market_type]["quantity"] = 0
        self.positions[self.market_type]["side"] = 'NONE'
        self.positions[self.market_type]["position_price"] = 0
        
        self.add_num = 0
        
        return

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
        portfolio_str += f"profit_and_loss: {round(self.profit - self.loss)}"
        return portfolio_str

    def get_addition_num(self):
        """
        追加購入回数を返す
        """
        return self.add_num

# ポートフォリオのサンプル
if __name__ == "__main__":
    # ポートフォリオクラスを初期化
    portfolio = Portfolio()

    portfolio.add_position_quantity(0.01, "BUY", 20000)
    portfolio.add_position_quantity(0.01, "BUY", 20000)
    btc = portfolio.get_position_quantity()
    print(portfolio)
    print(f"add num = {portfolio.get_addition_num()}")

    portfolio.clear_position_quantity(30000)
    print(portfolio)
    print(f"add num = {portfolio.get_addition_num()}")
    
    portfolio.add_position_quantity(0.02, "SELL", 20000)
    btc = portfolio.get_position_quantity()
    print(portfolio)
    print(f"add num = {portfolio.get_addition_num()}")
    portfolio.clear_position_quantity(40000)
    print(portfolio)
    print(f"add num = {portfolio.get_addition_num()}")

    portfolio.add_position_quantity(0.04, "BUY", 20000)
    btc = portfolio.get_position_quantity()
    print(portfolio)
    print(f"add num = {portfolio.get_addition_num()}")
    portfolio.clear_position_quantity(40000)
    print(portfolio)
    print(f"add num = {portfolio.get_addition_num()}")
    