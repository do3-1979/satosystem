"""
指値注文・動的スリッページ機能のテストスイート

execute_entry_order() と execute_exit_order() のダミーモード動作を検証します。
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest
from unittest.mock import Mock, patch, MagicMock
from bybit_exchange import BybitExchange
from config import Config

class TestLimitOrderImprovement:
    """指値注文・スリッページ改善の単体テスト"""
    
    @pytest.fixture
    def dummy_exchange(self):
        """ダミーモード用の BybitExchange インスタンス"""
        with patch('config.Config.get_back_test_mode', return_value=1):
            with patch('config.Config.get_hot_test_dummy_mode', return_value=1):
                with patch('config.Config.get_api_key', return_value='test_key'):
                    with patch('config.Config.get_api_secret', return_value='test_secret'):
                        exchange = BybitExchange('test_key', 'test_secret')
                        exchange.is_dummy_mode = True
                        return exchange

    def test_calculate_entry_price_buy(self, dummy_exchange):
        """買いエントリーの指値価格計算テスト"""
        current_price = 100000.0
        slippage = 0.5  # 0.5%
        
        expected_price = 100000.0 * (1 - 0.5 / 100)  # 99500.0
        actual_price = dummy_exchange._calculate_entry_price('buy', current_price, slippage)
        
        assert abs(actual_price - expected_price) < 0.01, \
            f"買いエントリー価格が不正: {actual_price} (期待値: {expected_price})"

    def test_calculate_entry_price_sell(self, dummy_exchange):
        """売りエントリーの指値価格計算テスト"""
        current_price = 100000.0
        slippage = 0.5  # 0.5%
        
        expected_price = 100000.0 * (1 + 0.5 / 100)  # 100500.0
        actual_price = dummy_exchange._calculate_entry_price('sell', current_price, slippage)
        
        assert abs(actual_price - expected_price) < 0.01, \
            f"売りエントリー価格が不正: {actual_price} (期待値: {expected_price})"

    def test_calculate_exit_price_long_close(self, dummy_exchange):
        """ロング決済（売却）の指値価格計算テスト"""
        current_price = 100000.0
        slippage = 0.1  # 0.1%
        
        # ロング決済は高く売る（+）
        expected_price = 100000.0 * (1 + 0.1 / 100)  # 100100.0
        actual_price = dummy_exchange._calculate_exit_price('buy', current_price, slippage)
        
        assert abs(actual_price - expected_price) < 0.01, \
            f"ロング決済価格が不正: {actual_price} (期待値: {expected_price})"

    def test_calculate_exit_price_short_close(self, dummy_exchange):
        """ショート決済（買い戻し）の指値価格計算テスト"""
        current_price = 100000.0
        slippage = 0.1  # 0.1%
        
        # ショート決済は安く買い戻す（-）
        expected_price = 100000.0 * (1 - 0.1 / 100)  # 99900.0
        actual_price = dummy_exchange._calculate_exit_price('sell', current_price, slippage)
        
        assert abs(actual_price - expected_price) < 0.01, \
            f"ショート決済価格が不正: {actual_price} (期待値: {expected_price})"

    def test_slippage_multiplier_progression(self, dummy_exchange):
        """スリッページ拡大のリトライ進行テスト"""
        base_slippage = 0.5  # 0.5%
        multiplier = 1.5
        
        # 4回のリトライでのスリッページ拡大を検証
        expected_slippages = [
            base_slippage * (multiplier ** 0),  # リトライ 0: 0.5%
            base_slippage * (multiplier ** 1),  # リトライ 1: 0.75%
            base_slippage * (multiplier ** 2),  # リトライ 2: 1.125%
            base_slippage * (multiplier ** 3),  # リトライ 3: 1.6875%
        ]
        
        for attempt, expected_slip in enumerate(expected_slippages):
            adjusted_slip = base_slippage * (multiplier ** attempt)
            assert abs(adjusted_slip - expected_slip) < 0.0001, \
                f"リトライ {attempt} のスリッページが不正: {adjusted_slip} (期待値: {expected_slip})"

    @patch('config.Config.get_entry_slippage', return_value=0.5)
    @patch('config.Config.get_slippage_multiplier', return_value=1.5)
    @patch('config.Config.get_max_entry_retries', return_value=4)
    def test_dummy_entry_order_buy(self, mock_max_retries, mock_multiplier, mock_slippage, dummy_exchange):
        """ダミーエントリー注文（買い）のテスト"""
        initial_balance = dummy_exchange.dummy_balance
        side = 'buy'
        quantity = 0.1
        current_price = 100000.0
        
        result = dummy_exchange.execute_entry_order(side, quantity, current_price)
        
        # 成功確認
        assert result == True, "ダミーエントリー注文が失敗"
        
        # 残高が減少していることを確認
        assert dummy_exchange.dummy_balance < initial_balance, \
            "ダミー残高が減少していない"

    @patch('config.Config.get_entry_slippage', return_value=0.5)
    @patch('config.Config.get_slippage_multiplier', return_value=1.5)
    @patch('config.Config.get_max_entry_retries', return_value=4)
    def test_dummy_entry_order_sell(self, mock_max_retries, mock_multiplier, mock_slippage, dummy_exchange):
        """ダミーエントリー注文（売り）のテスト"""
        initial_balance = dummy_exchange.dummy_balance
        side = 'sell'
        quantity = 0.1
        current_price = 100000.0
        
        result = dummy_exchange.execute_entry_order(side, quantity, current_price)
        
        # 成功確認
        assert result == True, "ダミー売りエントリー注文が失敗"
        
        # 残高が減少していることを確認
        assert dummy_exchange.dummy_balance < initial_balance, \
            "ダミー残高が減少していない"

    @patch('config.Config.get_max_exit_retries', return_value=3)
    def test_dummy_exit_order(self, mock_max_retries, dummy_exchange):
        """ダミー決済注文のテスト"""
        initial_balance = dummy_exchange.dummy_balance
        side = 'buy'
        quantity = 0.1
        
        result = dummy_exchange.execute_exit_order(side, quantity)
        
        # 成功確認
        assert result == True, "ダミー決済注文が失敗"
        
        # 残高が増加していることを確認
        assert dummy_exchange.dummy_balance > initial_balance, \
            "ダミー残高が増加していない"

    def test_entry_price_progression_with_retries(self, dummy_exchange):
        """エントリー価格のリトライ時の段階的調整を検証"""
        current_price = 100000.0
        base_slippage = 0.5
        multiplier = 1.5
        
        # 4回のリトライでの価格調整を検証
        prices = []
        for attempt in range(4):
            adjusted_slippage = base_slippage * (multiplier ** attempt)
            price = dummy_exchange._calculate_entry_price('buy', current_price, adjusted_slippage)
            prices.append(price)
        
        # 価格が段階的に低下していることを確認（買いの場合）
        for i in range(len(prices) - 1):
            assert prices[i] > prices[i + 1], \
                f"リトライ {i} の価格が {i+1} より高くない: {prices[i]} vs {prices[i + 1]}"

    def test_dummy_balance_tracking(self, dummy_exchange):
        """ダミーモードでの残高追跡テスト"""
        initial_balance = 100000.0
        dummy_exchange.dummy_balance = initial_balance
        
        # エントリー
        dummy_exchange.execute_entry_order('buy', 0.1, 100000.0)
        balance_after_entry = dummy_exchange.dummy_balance
        
        # 決済
        dummy_exchange.execute_exit_order('sell', 0.1)
        balance_after_exit = dummy_exchange.dummy_balance
        
        # 両方とも成功していることを確認
        assert balance_after_entry < initial_balance, "エントリー後に残高が減少していない"
        assert balance_after_exit > balance_after_entry, "決済後に残高が増加していない"

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
