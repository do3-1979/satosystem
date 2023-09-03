from TradingStrategy import TradingStrategy

# エントリー条件の関数例
def entry_condition(price_data):
    return price_data["close_price"] > price_data["sma"]

# エグジット条件の関数例
def exit_condition(price_data):
    return price_data["close_price"] < price_data["sma"]

def test_evaluate_entry():
    # TradingStrategyクラスの初期化
    strategy = TradingStrategy(entry_condition, exit_condition)

    # エントリー条件を満たす価格データ
    price_data_entry = {"close_price": 105.0, "sma": 100.0}

    # エントリー条件を評価
    assert strategy.evaluate_entry(price_data_entry) is True

    # エントリー条件を満たさない価格データ
    price_data_no_entry = {"close_price": 95.0, "sma": 100.0}

    # エントリー条件を評価
    assert strategy.evaluate_entry(price_data_no_entry) is False

def test_evaluate_exit():
    # TradingStrategyクラスの初期化
    strategy = TradingStrategy(entry_condition, exit_condition)

    # エグジット条件を満たす価格データ
    price_data_exit = {"close_price": 95.0, "sma": 100.0}

    # エグジット条件を評価
    assert strategy.evaluate_exit(price_data_exit) is True

    # エグジット条件を満たさない価格データ
    price_data_no_exit = {"close_price": 105.0, "sma": 100.0}

    # エグジット条件を評価
    assert strategy.evaluate_exit(price_data_no_exit) is False
