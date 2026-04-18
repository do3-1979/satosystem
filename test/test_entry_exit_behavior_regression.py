"""
エントリー/エグジット条件の動作テスト

構造テストではなく、実際のシグナル評価ロジックを検証する：
- Donchianブレイクアウト + PVO + ADXフィルターの組み合わせ
- ストップロスによるEXIT判定
- ファンディングレートフィルターの動作
- コストモデルのファンディングコスト計算
"""

import os
import sys
import json
from datetime import datetime
from unittest.mock import MagicMock, patch, PropertyMock

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(WORKSPACE_ROOT, "src")
sys.path.insert(0, SRC_DIR)


def _make_mock_config(**overrides):
    """テスト用Config設定のモックパッチを返す"""
    defaults = {
        'get_back_test_mode': 1,
        'get_market': 'BTC/USDT:USDT',
        'get_time_frame': 240,
        'get_leverage': 10,
        'get_donchian_period': 30,
        'get_pvo_threshold': 0,
        'get_adx_filter_threshold': 31,
        'get_enable_pvo_filter': True,
        'get_enable_adx_filter': True,
        'get_enable_volume_filter': False,
        'get_enable_volatility_filter': False,
        'get_volume_filter_threshold': 0,
        'get_volatility_filter_threshold': 99999,
        'get_sma_direction_filter_enabled': False,
        'get_rsi_direction_filter_enabled': False,
        'get_macd_direction_filter_enabled': False,
        'get_tsmom_filter_enabled': False,
        'get_adx_slope_filter_enabled': False,
        'get_funding_rate_filter_enabled': False,
        'get_funding_rate_buy_threshold': 0.0005,
        'get_funding_rate_sell_threshold': -0.0005,
        'get_weekend_filter_enabled': False,
        'get_enable_range_breakout_enhanced': False,
        'get_enable_market_regime_detection': False,
        'get_enable_mean_reversion_strategy': False,
        'get_config_bool': lambda section, key, default=0: default,
        'get_config_int': lambda section, key, default=0: default,
        'get_cost_model_enabled': False,
        'get_funding_rate_holding_enabled': False,
        'get_maker_fee': 0.02,
        'get_taker_fee': 0.06,
        'get_slippage_rate': 0.05,
        'get_execution_delay_candles': 1,
        'get_account_balance': 100.0,
        'get_log_dir_name': '/tmp',
        'get_start_epoch': 0,
        'get_end_epoch': 0,
        'get_atr_period': 14,
        'get_atr_ma_period': 20,
        'get_swing_lookback_period': 20,
        # ExitStrategyV2 設定
        'get_enable_time_based_exit': False,
        'get_max_holding_hours': 72.0,
        'get_enable_chandelier_exit': False,
        'get_chandelier_period': 22,
        'get_chandelier_mult': 3.0,
        'get_chandelier_replaces_psar': False,
        'get_enable_profit_step_lock': False,
        'get_enable_volume_climax_exit': False,
        'get_volume_climax_threshold': 3.0,
        'get_volume_climax_lookback': 20,
        'get_volume_climax_min_profit_pct': 0.005,
        'get_enable_composite_score_exit': False,
        'get_composite_exit_adx_drop': 5.0,
        'get_composite_exit_pvo_threshold': 0.0,
        'get_composite_exit_volume_ratio': 0.8,
        'get_composite_exit_min_score': 2,
        'get_composite_exit_min_profit_pct': 0.005,
    }
    defaults.update(overrides)
    return defaults


def _create_strategy_with_mocks(config_overrides=None):
    """モック済みTradingStrategyを作成（パッチは呼び出し元で停止すること）"""
    from trading_strategy import TradingStrategy

    config_vals = _make_mock_config(**(config_overrides or {}))

    # Config パッチを start() で永続化
    patches = [
        patch('trading_strategy.Config'),
        patch('portfolio.Config'),
        patch('cost_model.Config'),
    ]
    mocks = [p.start() for p in patches]

    for mock_cfg in mocks:
        for key, val in config_vals.items():
            if callable(val) and not isinstance(val, MagicMock):
                setattr(mock_cfg, key, MagicMock(side_effect=val))
            else:
                setattr(mock_cfg, key, MagicMock(return_value=val))

    # PriceDataManagement モック
    pdm = MagicMock()
    pdm.get_signals.return_value = {
        'pvo': {'signal': False, 'info': {'value': 0}},
        'donchian': {'signal': False, 'side': 'NONE', 'info': {'highest': 0, 'lowest': 0}},
    }
    pdm.get_ticker.return_value = 100000.0
    pdm.get_latest_close_time.return_value = 1700000000
    pdm.get_latest_close_time_dt.return_value = '2024/01/01 00:00:00'
    pdm.get_ohlcv_data_by_time_frame.return_value = []
    pdm.get_volatility.return_value = 1000.0
    pdm.get_latest_volume.return_value = 100.0
    pdm.get_latest_ohlcv.return_value = {
        'close_price': 100000.0, 'high_price': 101000.0, 'low_price': 99000.0,
        'timestamp': 1700000000, 'close_time': 1700000000, 'Volume': 100.0,
    }
    pdm.get_funding_rate.return_value = 0.0001

    # RiskManagement モック
    rm = MagicMock()
    rm.get_adx.return_value = 35.0
    rm.get_donchian_high.return_value = 105000.0
    rm.get_donchian_low.return_value = 95000.0
    rm.get_stop_price.return_value = 97000.0
    rm.get_psar.return_value = 98000.0
    rm.get_add_range.return_value = 5000.0
    rm.get_last_entry_price.return_value = 100000.0
    rm.enable_strategy_a_adx = False
    rm.enable_strategy_b_bb_rsi_sma = False
    rm.enable_strategy_c_combined = False

    # Portfolio モック
    portfolio = MagicMock()
    portfolio.get_position_quantity.return_value = {'quantity': 0, 'side': 'NONE', 'position_price': 0}
    portfolio.get_position_side.return_value = 'NONE'
    portfolio.get_position_price.return_value = 0

    strategy = TradingStrategy(pdm, rm, portfolio)

    def cleanup():
        for p in patches:
            p.stop()

    return strategy, pdm, rm, portfolio, cleanup


def _run_test(test_func_body):
    """テスト関数をラップしてcleanupを保証"""
    strategy, pdm, rm, portfolio, cleanup = None, None, None, None, None
    try:
        return test_func_body()
    finally:
        patch.stopall()
        portfolio = MagicMock()
        portfolio.get_position_quantity.return_value = {'quantity': 0, 'side': 'NONE', 'position_price': 0}
        portfolio.get_position_side.return_value = 'NONE'
        portfolio.get_position_price.return_value = 0

        strategy = TradingStrategy(pdm, rm, portfolio)

    return strategy, pdm, rm, portfolio


# ========================================
# テスト関数群
# ========================================

def test_entry_donchian_pvo_adx_pass():
    """Donchian BUYブレイク + PVO > 0 + ADX >= 31 → ENTRY許可"""
    try:
        strategy, pdm, rm, portfolio, cleanup = _create_strategy_with_mocks()

        # シグナル設定: Donchian BUY ブレイク + PVO有効
        pdm.get_signals.return_value = {
            'pvo': {'signal': True, 'info': {'value': 15.0}},
            'donchian': {'signal': True, 'side': 'BUY', 'info': {'highest': 105000, 'lowest': 95000}},
        }
        rm.get_adx.return_value = 35.0  # ADX >= 31

        strategy.initialize_trade_decision()
        strategy.evaluate_entry()

        result = strategy.trade_decision
        if result['decision'] == 'ENTRY' and result['side'] == 'BUY':
            return True, f"✅ Donchian+PVO+ADX → ENTRY BUY: 正常"
        else:
            return False, f"❌ 期待: ENTRY BUY, 実際: {result['decision']} {result['side']}"
    except Exception as e:
        return False, f"❌ エラー: {e}"
    finally:
        patch.stopall()


def test_entry_donchian_sell_breakout():
    """Donchian SELLブレイク + PVO + ADX → ENTRY SELL"""
    try:
        strategy, pdm, rm, portfolio, cleanup = _create_strategy_with_mocks()

        pdm.get_signals.return_value = {
            'pvo': {'signal': True, 'info': {'value': 12.0}},
            'donchian': {'signal': True, 'side': 'SELL', 'info': {'highest': 105000, 'lowest': 95000}},
        }
        rm.get_adx.return_value = 40.0

        strategy.initialize_trade_decision()
        strategy.evaluate_entry()

        result = strategy.trade_decision
        if result['decision'] == 'ENTRY' and result['side'] == 'SELL':
            return True, f"✅ Donchian SELL ブレイク → ENTRY SELL: 正常"
        else:
            return False, f"❌ 期待: ENTRY SELL, 実際: {result['decision']} {result['side']}"
    except Exception as e:
        return False, f"❌ エラー: {e}"
    finally:
        patch.stopall()


def test_entry_blocked_by_low_adx():
    """ADX < 31 → エントリー拒否"""
    try:
        strategy, pdm, rm, portfolio, cleanup = _create_strategy_with_mocks()

        pdm.get_signals.return_value = {
            'pvo': {'signal': True, 'info': {'value': 15.0}},
            'donchian': {'signal': True, 'side': 'BUY', 'info': {'highest': 105000, 'lowest': 95000}},
        }
        rm.get_adx.return_value = 25.0  # ADX < 31 → 拒否

        strategy.initialize_trade_decision()
        strategy.evaluate_entry()

        result = strategy.trade_decision
        if result['decision'] == 'NONE':
            return True, f"✅ ADX低 (25.0 < 31) → エントリー拒否: 正常"
        else:
            return False, f"❌ 期待: NONE, 実際: {result['decision']} {result['side']}"
    except Exception as e:
        return False, f"❌ エラー: {e}"
    finally:
        patch.stopall()


def test_entry_blocked_by_low_pvo():
    """PVO signal=False → エントリーなし（Donchian評価に到達しない）"""
    try:
        strategy, pdm, rm, portfolio, cleanup = _create_strategy_with_mocks()

        pdm.get_signals.return_value = {
            'pvo': {'signal': False, 'info': {'value': -5.0}},
            'donchian': {'signal': True, 'side': 'BUY', 'info': {'highest': 105000, 'lowest': 95000}},
        }

        strategy.initialize_trade_decision()
        strategy.evaluate_entry()

        result = strategy.trade_decision
        if result['decision'] == 'NONE':
            return True, f"✅ PVO無効 → エントリーなし: 正常"
        else:
            return False, f"❌ 期待: NONE, 実際: {result['decision']}"
    except Exception as e:
        return False, f"❌ エラー: {e}"
    finally:
        patch.stopall()


def test_entry_blocked_no_donchian_breakout():
    """Donchian signal=False → エントリーなし"""
    try:
        strategy, pdm, rm, portfolio, cleanup = _create_strategy_with_mocks()

        pdm.get_signals.return_value = {
            'pvo': {'signal': True, 'info': {'value': 15.0}},
            'donchian': {'signal': False, 'side': 'NONE', 'info': {'highest': 105000, 'lowest': 95000}},
        }

        strategy.initialize_trade_decision()
        strategy.evaluate_entry()

        result = strategy.trade_decision
        if result['decision'] == 'NONE':
            return True, f"✅ Donchianブレイクなし → エントリーなし: 正常"
        else:
            return False, f"❌ 期待: NONE, 実際: {result['decision']}"
    except Exception as e:
        return False, f"❌ エラー: {e}"
    finally:
        patch.stopall()


def test_exit_stop_loss_buy_position():
    """BUYポジション保有中、安値 <= ストップ価格 → EXIT"""
    try:
        strategy, pdm, rm, portfolio, cleanup = _create_strategy_with_mocks()

        # BUYポジション保有中
        portfolio.get_position_quantity.return_value = {'quantity': 0.01, 'side': 'BUY', 'position_price': 100000}
        portfolio.get_position_side.return_value = 'BUY'
        portfolio.get_position_price.return_value = 100000

        # ストップ価格
        rm.get_stop_price.return_value = 97000.0

        # 安値がストップを下回る
        pdm.get_latest_ohlcv.return_value = {
            'close_price': 96500.0, 'high_price': 98000.0, 'low_price': 96000.0,
            'timestamp': 1700001000, 'close_time': 1700001000, 'Volume': 150.0,
        }

        strategy.initialize_trade_decision()
        strategy.evaluate_exit()

        result = strategy.trade_decision
        if result['decision'] == 'EXIT' and result['side'] == 'SELL':
            return True, f"✅ BUYストップロス (low <= stop) → EXIT SELL: 正常"
        else:
            return False, f"❌ 期待: EXIT SELL, 実際: {result['decision']} {result['side']}"
    except Exception as e:
        return False, f"❌ エラー: {e}"
    finally:
        patch.stopall()


def test_exit_stop_loss_sell_position():
    """SELLポジション保有中、高値 >= ストップ価格 → EXIT"""
    try:
        strategy, pdm, rm, portfolio, cleanup = _create_strategy_with_mocks()

        portfolio.get_position_quantity.return_value = {'quantity': 0.01, 'side': 'SELL', 'position_price': 100000}
        portfolio.get_position_side.return_value = 'SELL'
        portfolio.get_position_price.return_value = 100000

        rm.get_stop_price.return_value = 103000.0

        # 高値がストップを超える
        pdm.get_latest_ohlcv.return_value = {
            'close_price': 103500.0, 'high_price': 104000.0, 'low_price': 102000.0,
            'timestamp': 1700001000, 'close_time': 1700001000, 'Volume': 150.0,
        }

        strategy.initialize_trade_decision()
        strategy.evaluate_exit()

        result = strategy.trade_decision
        if result['decision'] == 'EXIT' and result['side'] == 'BUY':
            return True, f"✅ SELLストップロス (high >= stop) → EXIT BUY: 正常"
        else:
            return False, f"❌ 期待: EXIT BUY, 実際: {result['decision']} {result['side']}"
    except Exception as e:
        return False, f"❌ エラー: {e}"
    finally:
        patch.stopall()


def test_no_exit_when_price_within_range():
    """価格がストップ範囲内 → EXIT発生しない"""
    try:
        strategy, pdm, rm, portfolio, cleanup = _create_strategy_with_mocks()

        portfolio.get_position_quantity.return_value = {'quantity': 0.01, 'side': 'BUY', 'position_price': 100000}
        portfolio.get_position_side.return_value = 'BUY'
        portfolio.get_position_price.return_value = 100000

        rm.get_stop_price.return_value = 97000.0

        # 安値はストップより上
        pdm.get_latest_ohlcv.return_value = {
            'close_price': 101000.0, 'high_price': 102000.0, 'low_price': 99000.0,
            'timestamp': 1700001000, 'close_time': 1700001000, 'Volume': 150.0,
        }

        strategy.initialize_trade_decision()
        strategy.evaluate_exit()

        result = strategy.trade_decision
        if result['decision'] == 'NONE':
            return True, f"✅ 価格がストップ範囲内 → EXIT不発: 正常"
        else:
            return False, f"❌ 期待: NONE, 実際: {result['decision']}"
    except Exception as e:
        return False, f"❌ エラー: {e}"
    finally:
        patch.stopall()


def test_funding_rate_filter_blocks_buy():
    """Funding Rate が高すぎる → BUYエントリー拒否"""
    try:
        strategy, pdm, rm, portfolio, cleanup = _create_strategy_with_mocks(
            config_overrides={'get_funding_rate_filter_enabled': True},
        )

        pdm.get_signals.return_value = {
            'pvo': {'signal': True, 'info': {'value': 15.0}},
            'donchian': {'signal': True, 'side': 'BUY', 'info': {'highest': 105000, 'lowest': 95000}},
        }
        rm.get_adx.return_value = 35.0
        pdm.get_funding_rate.return_value = 0.001  # 0.1% > threshold 0.05%

        strategy.initialize_trade_decision()
        strategy.evaluate_entry()

        result = strategy.trade_decision
        if result['decision'] == 'NONE':
            return True, f"✅ Funding Rate高 → BUYエントリー拒否: 正常"
        else:
            return False, f"❌ 期待: NONE, 実際: {result['decision']}"
    except Exception as e:
        return False, f"❌ エラー: {e}"
    finally:
        patch.stopall()


def test_funding_rate_filter_allows_normal():
    """Funding Rate が正常範囲 → エントリー許可"""
    try:
        strategy, pdm, rm, portfolio, cleanup = _create_strategy_with_mocks(
            config_overrides={'get_funding_rate_filter_enabled': True},
        )

        pdm.get_signals.return_value = {
            'pvo': {'signal': True, 'info': {'value': 15.0}},
            'donchian': {'signal': True, 'side': 'BUY', 'info': {'highest': 105000, 'lowest': 95000}},
        }
        rm.get_adx.return_value = 35.0
        pdm.get_funding_rate.return_value = 0.0001  # 0.01% < threshold 0.05%

        strategy.initialize_trade_decision()
        strategy.evaluate_entry()

        result = strategy.trade_decision
        if result['decision'] == 'ENTRY' and result['side'] == 'BUY':
            return True, f"✅ Funding Rate正常 → BUYエントリー許可: 正常"
        else:
            return False, f"❌ 期待: ENTRY BUY, 実際: {result['decision']} {result['side']}"
    except Exception as e:
        return False, f"❌ エラー: {e}"
    finally:
        patch.stopall()


def test_funding_cost_calculation_long():
    """CostModel: ロングポジション + 正FR → コスト（正の値）"""
    try:
        from cost_model import CostModel
        with patch('cost_model.Config') as MockConfig:
            MockConfig.get_cost_model_enabled.return_value = True
            MockConfig.get_funding_rate_holding_enabled.return_value = True
            MockConfig.get_maker_fee.return_value = 0.02
            MockConfig.get_taker_fee.return_value = 0.06
            MockConfig.get_slippage_rate.return_value = 0.05
            MockConfig.get_execution_delay_candles.return_value = 1

            cm = CostModel()
            # BUY + 正FR → コスト（正）
            cost = cm.calculate_funding_cost('BUY', 0.01, 100000.0, 0.0001)
            # position_value * funding_rate = 0.01 * 100000 * 0.0001 = 0.1
            expected = 0.1
            if abs(cost - expected) < 0.001:
                return True, f"✅ ロング+正FR → コスト {cost:.4f} (期待: {expected}): 正常"
            else:
                return False, f"❌ 期待: {expected}, 実際: {cost}"
    except Exception as e:
        return False, f"❌ エラー: {e}"
    finally:
        patch.stopall()


def test_funding_cost_calculation_short():
    """CostModel: ショートポジション + 正FR → 収入（負の値）"""
    try:
        from cost_model import CostModel
        with patch('cost_model.Config') as MockConfig:
            MockConfig.get_cost_model_enabled.return_value = True
            MockConfig.get_funding_rate_holding_enabled.return_value = True
            MockConfig.get_maker_fee.return_value = 0.02
            MockConfig.get_taker_fee.return_value = 0.06
            MockConfig.get_slippage_rate.return_value = 0.05
            MockConfig.get_execution_delay_candles.return_value = 1

            cm = CostModel()
            # SELL + 正FR → 収入（負）
            cost = cm.calculate_funding_cost('SELL', 0.01, 100000.0, 0.0001)
            expected = -0.1
            if abs(cost - expected) < 0.001:
                return True, f"✅ ショート+正FR → 収入 {cost:.4f} (期待: {expected}): 正常"
            else:
                return False, f"❌ 期待: {expected}, 実際: {cost}"
    except Exception as e:
        return False, f"❌ エラー: {e}"
    finally:
        patch.stopall()


def test_funding_cost_disabled():
    """CostModel: funding_rate_holding_enabled=False → コスト0"""
    try:
        from cost_model import CostModel
        with patch('cost_model.Config') as MockConfig:
            MockConfig.get_cost_model_enabled.return_value = True
            MockConfig.get_funding_rate_holding_enabled.return_value = False
            MockConfig.get_maker_fee.return_value = 0.02
            MockConfig.get_taker_fee.return_value = 0.06
            MockConfig.get_slippage_rate.return_value = 0.05
            MockConfig.get_execution_delay_candles.return_value = 1

            cm = CostModel()
            cost = cm.calculate_funding_cost('BUY', 0.01, 100000.0, 0.0001)
            if cost == 0.0:
                return True, f"✅ FR保有コスト無効 → 0.0: 正常"
            else:
                return False, f"❌ 期待: 0.0, 実際: {cost}"
    except Exception as e:
        return False, f"❌ エラー: {e}"
    finally:
        patch.stopall()


def test_portfolio_apply_funding_cost():
    """Portfolio: ファンディングコスト正を損失に計上"""
    try:
        from portfolio import Portfolio
        with patch('portfolio.Config') as MockConfig, \
             patch('cost_model.Config') as MockCostConfig:
            MockConfig.get_market.return_value = 'BTC/USDT:USDT'
            MockConfig.get_cost_model_enabled.return_value = False
            MockConfig.get_funding_rate_holding_enabled.return_value = False
            MockConfig.get_log_dir_name.return_value = '/tmp'
            MockCostConfig.get_cost_model_enabled.return_value = False
            MockCostConfig.get_funding_rate_holding_enabled.return_value = False
            MockCostConfig.get_maker_fee.return_value = 0.02
            MockCostConfig.get_taker_fee.return_value = 0.06
            MockCostConfig.get_slippage_rate.return_value = 0.05
            MockCostConfig.get_execution_delay_candles.return_value = 1

            p = Portfolio(100.0)
            initial_pnl = p.get_profit_and_loss()

            # 正のファンディングコスト → 損失
            p.apply_funding_cost(0.5)
            pnl_after = p.get_profit_and_loss()

            if abs(pnl_after - (initial_pnl - 0.5)) < 0.001:
                return True, f"✅ ファンディングコスト0.5 → PnL減少: 正常 ({pnl_after:.2f})"
            else:
                return False, f"❌ 期待: {initial_pnl - 0.5}, 実際: {pnl_after}"
    except Exception as e:
        return False, f"❌ エラー: {e}"
    finally:
        patch.stopall()


def test_portfolio_apply_funding_income():
    """Portfolio: ファンディングコスト負を収入に計上"""
    try:
        from portfolio import Portfolio
        with patch('portfolio.Config') as MockConfig, \
             patch('cost_model.Config') as MockCostConfig:
            MockConfig.get_market.return_value = 'BTC/USDT:USDT'
            MockConfig.get_cost_model_enabled.return_value = False
            MockConfig.get_funding_rate_holding_enabled.return_value = False
            MockConfig.get_log_dir_name.return_value = '/tmp'
            MockCostConfig.get_cost_model_enabled.return_value = False
            MockCostConfig.get_funding_rate_holding_enabled.return_value = False
            MockCostConfig.get_maker_fee.return_value = 0.02
            MockCostConfig.get_taker_fee.return_value = 0.06
            MockCostConfig.get_slippage_rate.return_value = 0.05
            MockCostConfig.get_execution_delay_candles.return_value = 1

            p = Portfolio(100.0)
            initial_pnl = p.get_profit_and_loss()

            # 負のファンディングコスト → 収入
            p.apply_funding_cost(-0.3)
            pnl_after = p.get_profit_and_loss()

            if abs(pnl_after - (initial_pnl + 0.3)) < 0.001:
                return True, f"✅ ファンディング収入-0.3 → PnL増加: 正常 ({pnl_after:.2f})"
            else:
                return False, f"❌ 期待: {initial_pnl + 0.3}, 実際: {pnl_after}"
    except Exception as e:
        return False, f"❌ エラー: {e}"
    finally:
        patch.stopall()


def test_make_trade_decision_no_position():
    """make_trade_decision: ポジション無し → evaluate_entryが呼ばれる"""
    try:
        strategy, pdm, rm, portfolio, cleanup = _create_strategy_with_mocks()

        # ポジション無し（デフォルト）
        pdm.get_signals.return_value = {
            'pvo': {'signal': True, 'info': {'value': 15.0}},
            'donchian': {'signal': True, 'side': 'BUY', 'info': {'highest': 105000, 'lowest': 95000}},
        }
        rm.get_adx.return_value = 35.0

        result = strategy.make_trade_decision()

        if result['decision'] == 'ENTRY' and result['side'] == 'BUY':
            return True, f"✅ make_trade_decision(ポジション無し) → ENTRY: 正常"
        else:
            return False, f"❌ 期待: ENTRY, 実際: {result['decision']}"
    except Exception as e:
        return False, f"❌ エラー: {e}"
    finally:
        patch.stopall()


def test_make_trade_decision_with_position():
    """make_trade_decision: ポジション有り → evaluate_exit/addが呼ばれる"""
    try:
        strategy, pdm, rm, portfolio, cleanup = _create_strategy_with_mocks()

        # ポジション有り
        portfolio.get_position_quantity.return_value = {'quantity': 0.01, 'side': 'BUY', 'position_price': 100000}
        portfolio.get_position_side.return_value = 'BUY'
        portfolio.get_position_price.return_value = 100000

        rm.get_stop_price.return_value = 97000.0

        # 安値がストップ以下
        pdm.get_latest_ohlcv.return_value = {
            'close_price': 96000.0, 'high_price': 98000.0, 'low_price': 96000.0,
            'timestamp': 1700001000, 'close_time': 1700001000, 'Volume': 150.0,
        }

        result = strategy.make_trade_decision()

        if result['decision'] == 'EXIT':
            return True, f"✅ make_trade_decision(ポジション有り+ストップ) → EXIT: 正常"
        else:
            return False, f"❌ 期待: EXIT, 実際: {result['decision']}"
    except Exception as e:
        return False, f"❌ エラー: {e}"
    finally:
        patch.stopall()


# ========================================
# テスト実行
# ========================================

def run_all_tests():
    """全テストを実行"""
    tests = [
        ("Donchian+PVO+ADX → ENTRY BUY", test_entry_donchian_pvo_adx_pass),
        ("Donchian SELL ブレイク → ENTRY SELL", test_entry_donchian_sell_breakout),
        ("ADX低 → エントリー拒否", test_entry_blocked_by_low_adx),
        ("PVO無効 → エントリーなし", test_entry_blocked_by_low_pvo),
        ("Donchianブレイクなし → エントリーなし", test_entry_blocked_no_donchian_breakout),
        ("BUYストップロス → EXIT", test_exit_stop_loss_buy_position),
        ("SELLストップロス → EXIT", test_exit_stop_loss_sell_position),
        ("価格範囲内 → EXIT不発", test_no_exit_when_price_within_range),
        ("FundingRate高 → BUY拒否", test_funding_rate_filter_blocks_buy),
        ("FundingRate正常 → BUY許可", test_funding_rate_filter_allows_normal),
        ("FRコスト計算: ロング+正FR", test_funding_cost_calculation_long),
        ("FRコスト計算: ショート+正FR", test_funding_cost_calculation_short),
        ("FR保有コスト無効時 → 0", test_funding_cost_disabled),
        ("Portfolio: FRコスト損失計上", test_portfolio_apply_funding_cost),
        ("Portfolio: FR収入計上", test_portfolio_apply_funding_income),
        ("make_trade_decision: ポジション無し", test_make_trade_decision_no_position),
        ("make_trade_decision: ポジション有り", test_make_trade_decision_with_position),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            passed, message = test_func()
            results.append({
                "name": test_name,
                "passed": passed,
                "message": message,
                "timestamp": datetime.now().isoformat()
            })
            print(message)
        except Exception as e:
            results.append({
                "name": test_name,
                "passed": False,
                "message": f"❌ テスト実行エラー: {e}",
                "timestamp": datetime.now().isoformat()
            })
            print(f"❌ テスト実行エラー ({test_name}): {e}")

    return results


if __name__ == "__main__":
    print("=" * 70)
    print("🧪 エントリー/エグジット条件 動作テスト")
    print("=" * 70)
    results = run_all_tests()

    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(results)

    print()
    print(f"📊 結果: {passed_count}/{total_count} 成功")

    # 結果を JSON で保存
    RESULTS_DIR = os.path.join(WORKSPACE_ROOT, "docs/regression_test_results")
    os.makedirs(RESULTS_DIR, exist_ok=True)
    output_path = os.path.join(RESULTS_DIR, "test_entry_exit_behavior_regression.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "file": "entry_exit_behavior",
            "total": total_count,
            "passed": passed_count,
            "results": results,
            "timestamp": datetime.now().isoformat()
        }, f, ensure_ascii=False, indent=2)

    sys.exit(0 if passed_count == total_count else 1)
