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
from cost_model import CostModel  # Task 40b: コストモデル

# Portfolio クラスの定義
class Portfolio:
    def __init__(self, initial_balance=100.0):
        """初期化
        
        Args:
            initial_balance: 初期資産（デフォルト: 100.0 USD）
        """
        self.logger = Logger()
        self.market_type = Config.get_market()
        self.initial_balance = initial_balance  # 初期資産を保持
        
        # Task 40b: コストモデル初期化
        self.cost_model = CostModel()
        self.total_fees_paid = 0.0  # 累積手数料
        self.total_slippage_cost = 0.0  # 累積スリッページコスト
        self.total_funding_cost = 0.0  # 累積ファンディングコスト
        
        # 現在の market_type に基づいてポジションを初期化
        self.positions = {self.market_type: {'quantity': 0, 'side': 'NONE', 'position_price': 0}}
        self.profit = 0
        self.loss = 0
        self.funds = 0
        self.funds_max = 0
        self.add_num = 0
        self.drawdown = 0
        #records["Drawdown"] = records.Funds.cummax().subtract(records.Funds)
	    #records["DrawdownRate"] = round(records.Drawdown / records.Funds.cummax() * 100,1)

    def get_position_quantity(self):
        """
        指定した通貨の保有ポジション量を取得
        """
        if self.market_type in self.positions:
            return self.positions[self.market_type]
        return {'quantity': 0, 'side': 'NONE', 'position_price': 0}

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

    def get_profit_factor(self):
        """
        プロフィットファクターを取得します。
        """
        if self.loss > 0:
            profit_factor = round( (self.profit / self.loss) ,3)
        else:
            profit_factor = 0
        return profit_factor

    def get_drawdown(self):
        """
        ドローダウンを取得します。
        """
        return self.drawdown
    
    def get_drawdown_rate(self):
        """
        ドローダウン率を取得します（初期資産を含む総資産ベース）。
        """
        # ピーク資産 = 初期資産 + 累積損益のピーク
        peak_balance = self.initial_balance + self.funds_max
        
        # 現在の資産 = 初期資産 + 現在の累積損益
        current_balance = self.initial_balance + self.funds
        
        if peak_balance > 0:
            # ドローダウン率 = (ピーク資産 - 現在の資産) / ピーク資産 * 100
            drawdown_rate = round((peak_balance - current_balance) / peak_balance * 100, 1)
        else:
            drawdown_rate = 0
        
        return drawdown_rate

    def add_position_quantity(self, quantity, side, price, is_backtest=False):
        """
        通貨の保有ポジション量を更新
        
        Args:
            quantity: ポジション数量
            side: 'BUY' または 'SELL'
            price: エントリー価格
            is_backtest: バックテストモードかどうか
        """
        # Task 40b: バックテスト時のコスト計上
        actual_price = price  # デフォルトはシグナル価格
        if is_backtest and self.cost_model.is_enabled:
            actual_price, entry_cost, cost_details = self.cost_model.calculate_entry_cost(
                side=side.lower(),
                quantity=quantity,
                signal_price=price,
                is_market_order=True
            )
            # コスト累積
            self.total_fees_paid += cost_details.get('fee_cost', 0)
            self.total_slippage_cost += cost_details.get('slippage_cost', 0)
            self.loss += entry_cost
            
            self.logger.log(
                f"💰 エントリーコスト: "
                f"手数料={cost_details.get('fee_cost', 0):.4f} USD, "
                f"スリッページ={cost_details.get('slippage_cost', 0):.4f} USD, "
                f"合計={entry_cost:.4f} USD"
            )
        
        current_quantity = self.positions[self.market_type]["quantity"]
        current_position_price = self.positions[self.market_type]["position_price"]
        current_side = self.positions[self.market_type]["side"]
        
        if current_quantity == 0 or current_side != side:
            # 初回の追加購入または既存ポジションとのsideが異なる場合
            self.positions[self.market_type]["quantity"] = quantity
            self.positions[self.market_type]["side"] = side
            self.positions[self.market_type]["position_price"] = actual_price  # Task 40b: 実際の約定価格を使用
            self.add_num = 1
        else:
            # 既存のポジションがある場合、平均取得単価を計算しなおす
            new_quantity = current_quantity + quantity
            new_position_price = ((current_quantity * current_position_price) + (quantity * actual_price)) / new_quantity  # Task 40b: 実際の約定価格を使用
            
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

    def apply_funding_cost(self, funding_cost):
        """
        ファンディングレートコストを累積損益に反映

        Args:
            funding_cost (float): 正=コスト（loss加算）、負=収入（profit加算）
        """
        if funding_cost > 0:
            self.loss += funding_cost
        else:
            self.profit += abs(funding_cost)
        self.total_funding_cost += funding_cost
        # funds を更新（balance_tether 計算に反映させるため）
        self.funds = self.profit - self.loss

    def clear_position_quantity(self, price, is_backtest=False):
        """
        通貨の保有ポジション量を更新し、利益または損失を計算します。

        Args:
            price (float): 売却時の価格
            is_backtest (bool): バックテストモードかどうか
        """
        profit = 0
        loss = 0

        # 利益と損失の合算
        profit, loss = self.calc_position_quantity(price)
        
        # Task 40b: バックテスト時のイグジットコスト計上
        actual_price = price  # デフォルトはシグナル価格
        if is_backtest and self.cost_model.is_enabled:
            quantity = self.positions[self.market_type]["quantity"]
            side = self.get_position_side()
            
            # イグジットは逆方向の取引になる
            exit_side = 'sell' if side == 'BUY' else 'buy'
            
            actual_price, exit_cost, cost_details = self.cost_model.calculate_exit_cost(
                side=exit_side,
                quantity=quantity,
                signal_price=price,
                is_market_order=True
            )
            # コスト累積
            self.total_fees_paid += cost_details.get('fee_cost', 0)
            self.total_slippage_cost += cost_details.get('slippage_cost', 0)
            loss += exit_cost  # イグジットコストは損失として計上
            
            self.logger.log(
                f"💰 イグジットコスト: "
                f"手数料={cost_details.get('fee_cost', 0):.4f} USD, "
                f"スリッページ={cost_details.get('slippage_cost', 0):.4f} USD, "
                f"合計={exit_cost:.4f} USD"
            )
        
        # ドローダウンを計算
        prev_funds_max = self.funds_max
        # 現在の損益合計
        tmp_funds_max = self.funds_max + profit - loss
        # 資産の最大の更新
        self.funds_max = max(prev_funds_max, tmp_funds_max)
        
        self.profit += profit
        self.loss += loss
        
        # 現在の資産
        self.funds = self.profit - self.loss
        # ドローダウン：資産の最大値 - 現在の資産(最も利益が高かった状態から減らしてしまった量)
        self.drawdown = self.funds_max - self.funds
        
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

    portfolio.add_position_quantity(0.01, "BUY", 15000)
    portfolio.add_position_quantity(0.01, "BUY", 25000)
    portfolio.add_position_quantity(0.02, "BUY", 10000)
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
    