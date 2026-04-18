"""
コストモデルクラス

バックテストに実取引のコスト（手数料・スリッページ・約定遅延）を織り込むためのモジュール。

機能:
- 手数料計算（Maker手数料、Taker手数料）
- スリッページ計算（買いは不利に、売りは不利に）
- 約定遅延（指定した足数後の価格で約定）
"""

from typing import Tuple, Dict
from config import Config


class CostModel:
    """
    取引コストモデル

    バックテストにおいて、実取引で発生するコストをシミュレートします：
    - 手数料（Maker/Taker）
    - スリッページ（買いは不利に、売りは不利に）
    - 約定遅延（指定した足数後の価格で約定）
    """
    
    def __init__(self):
        """
        コストモデルを初期化
        
        config.iniから以下のパラメータを読み込み:
        - maker_fee: メイカー手数料率（%）
        - taker_fee: テイカー手数料率（%）
        - slippage_rate: スリッページ率（%）
        - execution_delay_candles: 約定遅延（足数）
        """
        self.maker_fee = Config.get_maker_fee()  # 例: 0.02%
        self.taker_fee = Config.get_taker_fee()  # 例: 0.05%
        self.slippage_rate = Config.get_slippage_rate()  # 例: 0.02%
        self.execution_delay = Config.get_execution_delay_candles()  # 例: 1足
        
        # 本番モード/ダミーモード/バックテストモードでの使い分け
        self.is_enabled = Config.get_cost_model_enabled()
        self.funding_rate_holding_enabled = Config.get_funding_rate_holding_enabled()
    
    def calculate_entry_cost(self, side: str, quantity: float, signal_price: float, 
                            execution_price: float = None, is_market_order: bool = True) -> Tuple[float, float, Dict]:
        """
        エントリー時のコストを計算
        
        Args:
            side: 'buy' または 'sell'
            quantity: 注文数量
            signal_price: シグナル発生時の価格
            execution_price: 実際の約定価格（Noneの場合は計算）
            is_market_order: True=成行（Taker手数料）、False=指値（Maker手数料）
        
        Returns:
            (実約定価格, 総コスト, コスト詳細)
        """
        if not self.is_enabled:
            return signal_price, 0.0, {}
        
        # 実約定価格を計算（スリッページ適用）
        if execution_price is None:
            execution_price = self._apply_slippage(signal_price, side)
        
        # 手数料を計算
        fee_rate = self.taker_fee if is_market_order else self.maker_fee
        fee_cost = execution_price * quantity * (fee_rate / 100.0)
        
        # スリッページコスト（シグナル価格と実約定価格の差）
        slippage_cost = abs(execution_price - signal_price) * quantity
        
        # 総コスト
        total_cost = fee_cost + slippage_cost
        
        cost_details = {
            'fee_cost': fee_cost,
            'slippage_cost': slippage_cost,
            'signal_price': signal_price,
            'execution_price': execution_price,
            'fee_rate': fee_rate,
            'slippage_rate': self.slippage_rate
        }
        
        return execution_price, total_cost, cost_details
    
    def calculate_exit_cost(self, side: str, quantity: float, signal_price: float, 
                           execution_price: float = None, is_market_order: bool = True) -> Tuple[float, float, Dict]:
        """
        イグジット時のコストを計算
        
        Args:
            side: 'buy' または 'sell'（イグジット方向）
            quantity: 注文数量
            signal_price: シグナル発生時の価格
            execution_price: 実際の約定価格（Noneの場合は計算）
            is_market_order: True=成行（Taker手数料）、False=指値（Maker手数料）
        
        Returns:
            (実約定価格, 総コスト, コスト詳細)
        """
        # エントリーと同じロジック
        return self.calculate_entry_cost(side, quantity, signal_price, execution_price, is_market_order)
    
    def _apply_slippage(self, price: float, side: str) -> float:
        """
        スリッページを適用した価格を計算
        
        Args:
            price: 基準価格
            side: 'buy' または 'sell'
        
        Returns:
            float: スリッページ適用後の価格
        """
        slippage_factor = self.slippage_rate / 100.0
        
        if side.lower() == 'buy':
            # 買いは不利に（価格上昇）
            return price * (1.0 + slippage_factor)
        elif side.lower() == 'sell':
            # 売りは不利に（価格下落）
            return price / (1.0 + slippage_factor)
        else:
            return price

    def calculate_funding_cost(self, side: str, quantity: float, price: float, funding_rate: float) -> float:
        """
        ポジション保有中のファンディングレートコストを計算
        
        Bybitのファンディングレート:
        - BUY(ロング) + 正のFR → ロングがショートに支払う（コスト）
        - BUY(ロング) + 負のFR → ショートがロングに支払う（収入）
        - SELL(ショート) + 正のFR → ロングがショートに支払う（収入）
        - SELL(ショート) + 負のFR → ショートがロングに支払う（コスト）
        
        Args:
            side: 'BUY' または 'SELL'
            quantity: ポジション数量
            price: 現在価格
            funding_rate: ファンディングレート（例: 0.0001 = 0.01%）
        
        Returns:
            float: ファンディングコスト（正=コスト、負=収入）
        """
        if not self.is_enabled or not self.funding_rate_holding_enabled:
            return 0.0
        
        position_value = quantity * price
        
        if side.upper() == 'BUY':
            # ロング: 正のFR → 支払い（コスト）、負のFR → 受取（収入）
            return position_value * funding_rate
        elif side.upper() == 'SELL':
            # ショート: 正のFR → 受取（収入）、負のFR → 支払い（コスト）
            return -(position_value * funding_rate)
        return 0.0
    
    def get_execution_delay(self) -> int:
        """
        約定遅延（足数）を取得
        
        Returns:
            int: 約定遅延（足数）
        """
        return self.execution_delay
    
    def get_cost_summary(self) -> Dict:
        """
        コストモデルの設定サマリを取得
        
        Returns:
            dict: コスト設定の詳細
        """
        return {
            'enabled': self.is_enabled,
            'maker_fee': self.maker_fee,
            'taker_fee': self.taker_fee,
            'slippage_rate': self.slippage_rate,
            'execution_delay_candles': self.execution_delay
        }


# モジュールテスト
if __name__ == "__main__":
    # コストモデル初期化
    cost_model = CostModel()
    
    print("コストモデル設定:")
    print(cost_model.get_cost_summary())
    
    # エントリーコスト計算例
    side = 'buy'
    quantity = 0.01
    signal_price = 100000.0
    
    execution_price, total_cost, cost_details = cost_model.calculate_entry_cost(
        side=side,
        quantity=quantity,
        signal_price=signal_price,
        is_market_order=True
    )
    
    print(f"\nエントリーコスト計算例:")
    print(f"  シグナル価格: {signal_price}")
    print(f"  実約定価格: {execution_price}")
    print(f"  手数料: {cost_details['fee_cost']:.2f} USD")
    print(f"  スリッページ: {cost_details['slippage_cost']:.2f} USD")
    print(f"  総コスト: {total_cost:.2f} USD")
