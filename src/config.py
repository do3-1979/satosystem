"""
Config クラス:

ボットの設定情報を格納するクラスです。APIキー、トレードの間隔、戦略の選択などの設定を保持します。

このサンプルコードでは、Config クラスが設定ファイル（config.ini など）から
APIキー、APIシークレット、および他の設定情報を読み込むメソッドを提供しています。
設定情報の読み込みには Python の標準ライブラリである configparser を使用しています。
"""

import configparser
from datetime import datetime
import pytz

class Config:
    config = configparser.ConfigParser()
    config.read('config.ini',encoding="utf-8_sig")
    
    # Configuration cache (initialized on first access)
    _cache = None
    
    @classmethod
    def reload_config(cls):
        """Reload configuration from config.ini file and clear cache."""
        cls.config = configparser.ConfigParser()
        cls.config.read('config.ini', encoding="utf-8_sig")
        cls._cache = None
    
    @classmethod
    def _initialize_cache(cls):
        """Initialize configuration cache for performance optimization."""
        if cls._cache is not None:
            return
        
        cls._cache = {
            # API
            'api_key': cls.config['API']['api_key'],
            'api_secret': cls.config['API']['api_secret'],
            # RiskManagement
            'risk_percentage': float(cls.config['RiskManagement']['risk_percentage']),
            'account_balance': float(cls.config['RiskManagement']['account_balance']),
            'leverage': int(cls.config['RiskManagement']['leverage']),
            'entry_times': int(cls.config['RiskManagement']['entry_times']),
            'entry_range': float(cls.config['RiskManagement']['entry_range']),
            'stop_range': float(cls.config['RiskManagement']['stop_range']),
            'stop_AF': float(cls.config['RiskManagement']['stop_AF']),
            'stop_AF_add': float(cls.config['RiskManagement']['stop_AF_add']),
            'stop_AF_max': float(cls.config['RiskManagement']['stop_AF_max']),
            'surge_follow_price_ratio': float(cls.config['RiskManagement']['surge_follow_price_ratio']),
            'psar_time_frame': int(cls.config['RiskManagement']['psar_time_frame']),
            # Market
            'market': str(cls.config['Market']['market']),
            'time_frame': int(cls.config['Market']['time_frame']),
            # Period
            'start_time': cls.config['Period']['start_time'],
            'end_time': cls.config['Period']['end_time'],
            # Strategy
            'volatility_term': int(cls.config['Strategy']['volatility_term']),
            'donchian_buy_term': int(cls.config['Strategy']['donchian_buy_term']),
            'donchian_sell_term': int(cls.config['Strategy']['donchian_sell_term']),
            'keltner_ema_period': int(cls.config['Strategy']['keltner_ema_period']),
            'keltner_atr_multiplier': float(cls.config['Strategy']['keltner_atr_multiplier']),
            'keltner_enabled': cls.config['Strategy'].getboolean('keltner_enabled', fallback=True),
            'pvo_s_term': int(cls.config['Strategy']['pvo_s_term']),
            'pvo_l_term': int(cls.config['Strategy']['pvo_l_term']),
            'pvo_threshold': int(cls.config['Strategy']['pvo_threshold']),
            # Classification (trend labeling)
            'classification_k2': float(cls.config['Strategy'].get('classification_k2', 1.5)),
            'classification_k3': float(cls.config['Strategy'].get('classification_k3', 1.2)),
            # Partial Exit parameters
            'partial_exit_enabled': cls.config['Strategy'].getboolean('partial_exit_enabled', fallback=False),
            'partial_exit_profit_rate': float(cls.config['Strategy'].get('partial_exit_profit_rate', 0.10)),
            'partial_exit_ratio': float(cls.config['Strategy'].get('partial_exit_ratio', 0.5)),
            'partial_exit_min_bars': int(cls.config['Strategy'].get('partial_exit_min_bars', 0)),
            # Portfolio
            'lot_limit_lower': float(cls.config['Potfolio']['lot_limit_lower']),
            'balance_tether_limit': float(cls.config['Potfolio']['balance_tether_limit']),
            # Setting
            'server_retry_wait': int(cls.config['Setting']['server_retry_wait']),
            'bot_operation_cycle': int(cls.config['Setting']['bot_operation_cycle']),
            'run_timeout_seconds': int(cls.config['Setting'].get('run_timeout_seconds', 300)),
            'api_request_timeout_seconds': int(cls.config['Setting'].get('api_request_timeout_seconds', 20)),
            'api_max_retry_seconds': int(cls.config['Setting'].get('api_max_retry_seconds', 120)),
            # Log
            'log_file': cls.config['Log']['log_file'],
            'log_directory': cls.config['Log']['log_directory'],
            'logging_interval': int(cls.config['Log'].get('logging_interval', 1)),
            'report_directory': cls.config['Log'].get('report_directory', 'report'),
            # Backtest
            'back_test': int(cls.config['Backtest']['back_test']),
        }
        
        # Derived values
        cls._cache['market_unit_pair'] = cls._cache['market'][:3]
        
        # Epoch times
        start_time_str = cls._cache['start_time']
        start_time = datetime.strptime(start_time_str, "%Y/%m/%d %H:%M")
        cls._cache['start_epoch'] = int(start_time.timestamp())
        
        end_time_str = cls._cache['end_time']
        if end_time_str == "None" or end_time_str == "":
            cls._cache['end_epoch'] = 9999999999
        else:
            end_time = datetime.strptime(end_time_str, "%Y/%m/%d %H:%M")
            cls._cache['end_epoch'] = int(end_time.timestamp())
        
        # Max term: 各インジケータが安定計算に必要な最長期間を集約
        # 余裕を持たせるため +2 本をウォームアップとして追加
        cls._cache['test_initial_max_term'] = (
            max(
                cls._cache['volatility_term'],
                cls._cache['donchian_buy_term'],
                cls._cache['donchian_sell_term'],
                cls._cache['keltner_ema_period'],
                cls._cache['pvo_l_term']  # 長期EMAも考慮
            ) + 2
        )

    @classmethod
    def get_api_key(cls):
        """
        APIキーを取得します.

        Returns:
            str: APIキー
        """
        cls._initialize_cache()
        return cls._cache['api_key']

    @classmethod
    def get_api_secret(cls):
        """
        APIシークレットを取得します.

        Returns:
            str: APIシークレット
        """
        cls._initialize_cache()
        return cls._cache['api_secret']

    @classmethod
    def get_risk_percentage(cls):
        """
        リスク割合を取得します.

        Returns:
            float: リスク割合
        """
        cls._initialize_cache()
        return cls._cache['risk_percentage']
    
    @classmethod
    def get_account_balance(cls):
        """
        アカウント残高を取得します.

        Returns:
            float: アカウント残高
        """
        cls._initialize_cache()
        return cls._cache['account_balance']
    
    @classmethod
    def get_leverage(cls):
        """
        レバレッジを取得します.

        Returns:
            int: レバレッジ
        """
        cls._initialize_cache()
        return cls._cache['leverage']

    @classmethod
    def get_entry_times(cls):
        """
        エントリー回数を取得します.

        Returns:
            int: エントリー回数
        """
        cls._initialize_cache()
        return cls._cache['entry_times']

    @classmethod
    def get_entry_range(cls):
        """
        エントリー範囲を取得します.

        Returns:
            int: エントリー範囲
        """
        cls._initialize_cache()
        return cls._cache['entry_range']

    @classmethod
    def get_stop_range(cls):
        """
        ストップ範囲を取得します.

        Returns:
            int: ストップ範囲
        """
        cls._initialize_cache()
        return cls._cache['stop_range']

    @classmethod
    def get_stop_AF(cls):
        """
        ストップアンドリバースファクター（AF）を取得します.

        Returns:
            float: ストップアンドリバースファクター（AF）
        """
        cls._initialize_cache()
        return cls._cache['stop_AF']

    @classmethod
    def get_stop_AF_add(cls):
        """
        ストップアンドリバースファクター（AF）の追加値を取得します.

        Returns:
            float: ストップアンドリバースファクター（AF）の追加値
        """
        cls._initialize_cache()
        return cls._cache['stop_AF_add']

    @classmethod
    def get_stop_AF_max(cls):
        """
        ストップアンドリバースファクター（AF）の最大値を取得します.

        Returns:
            float: ストップアンドリバースファクター（AF）の最大値
        """
        cls._initialize_cache()
        return cls._cache['stop_AF_max']

    @classmethod
    def get_surge_follow_price_ratio(cls):
        """
        ストップ近傍のレートを取得します.

        Returns:
            float: ストップ近傍のレート
        """
        cls._initialize_cache()
        return cls._cache['surge_follow_price_ratio']

    @classmethod
    def get_psar_time_frame(cls):
        """
        PSAR用の時間軸を取得します.

        Returns:
            int: 時間軸[分]
        """
        cls._initialize_cache()
        return cls._cache['psar_time_frame']

    @classmethod
    def get_market(cls):
        """
        マーケットを取得します.

        Returns:
            str: マーケット情報
        """
        cls._initialize_cache()
        return cls._cache['market']

    @classmethod
    def get_market_unit_pair(cls):
        """
        マーケットからユニットペアを取得します.

        Returns:
            str: マーケット情報から取得したユニットペア
        """
        cls._initialize_cache()
        return cls._cache['market_unit_pair']

    @classmethod
    def get_time_frame(cls):
        """
        時間軸を取得します.

        Returns:
            int: 時間軸[分]
        """
        cls._initialize_cache()
        return cls._cache['time_frame']

    @classmethod
    def get_start_time(cls):
        """
        開始時刻を取得します.

        Returns:
            str: 開始時刻 (フォーマット: "YYYY/M/D H:mm")
        """
        cls._initialize_cache()
        return cls._cache['start_time']

    @classmethod
    def get_end_time(cls):
        """
        終了時刻を取得します.

        Returns:
            str: 終了時刻 (フォーマット: "YYYY/M/D H:mm")
        """
        cls._initialize_cache()
        return cls._cache['end_time']

    @classmethod
    def get_start_epoch(cls):
        """
        開始時刻をepoch時間で取得します.

        Returns:
            datetime: 開始時刻 (epoch)
        """
        cls._initialize_cache()
        return cls._cache['start_epoch']

    @classmethod
    def get_end_epoch(cls):
        """
        終了時刻をepoch時間で取得します.

        Returns:
            datetime: 終了時刻 (epoch)
        """
        cls._initialize_cache()
        return cls._cache['end_epoch']
    
    @classmethod
    def get_volatility_term(cls):
        """
        ボラティリティ期間を取得します.

        Returns:
            int: ボラティリティ期間
        """
        cls._initialize_cache()
        return cls._cache['volatility_term']

    @classmethod
    def get_donchian_buy_term(cls):
        """
        ドンチャン買い期間を取得します.

        Returns:
            int: ドンチャン買い期間
        """
        cls._initialize_cache()
        return cls._cache['donchian_buy_term']

    @classmethod
    def get_donchian_sell_term(cls):
        """
        ドンチャン売り期間を取得します.

        Returns:
            int: ドンチャン売り期間
        """
        cls._initialize_cache()
        return cls._cache['donchian_sell_term']

    @classmethod
    def get_keltner_ema_period(cls):
        """
        ケルトナーチャネルのEMA期間を取得します.

        Returns:
            int: ケルトナーEMA期間
        """
        cls._initialize_cache()
        return cls._cache['keltner_ema_period']

    @classmethod
    def get_keltner_atr_multiplier(cls):
        """
        ケルトナーチャネルのATR乗数を取得します.

        Returns:
            float: ケルトナーATR乗数
        """
        cls._initialize_cache()
        return cls._cache['keltner_atr_multiplier']

    @classmethod
    def get_keltner_enabled(cls):
        """
        Keltnerフィルタ有効化フラグを取得します.

        Returns:
            bool: Keltner有効化フラグ
        """
        cls._initialize_cache()
        return cls._cache['keltner_enabled']

    @classmethod
    def get_classification_k2(cls):
        cls._initialize_cache()
        return cls._cache['classification_k2']

    @classmethod
    def get_classification_k3(cls):
        cls._initialize_cache()
        return cls._cache['classification_k3']

    @classmethod
    def get_partial_exit_enabled(cls):
        cls._initialize_cache()
        return cls._cache['partial_exit_enabled']

    @classmethod
    def get_partial_exit_profit_rate(cls):
        cls._initialize_cache()
        return cls._cache['partial_exit_profit_rate']

    @classmethod
    def get_partial_exit_ratio(cls):
        cls._initialize_cache()
        return cls._cache['partial_exit_ratio']

    @classmethod
    def get_partial_exit_min_bars(cls):
        cls._initialize_cache()
        return cls._cache['partial_exit_min_bars']

    @classmethod
    def get_pvo_s_term(cls):
        """
        PVO短期間を取得します.

        Returns:
            int: PVO短期間
        """
        cls._initialize_cache()
        return cls._cache['pvo_s_term']

    @classmethod
    def get_pvo_l_term(cls):
        """
        PVO長期間を取得します.

        Returns:
            int: PVO長期間
        """
        cls._initialize_cache()
        return cls._cache['pvo_l_term']

    @classmethod
    def get_pvo_threshold(cls):
        """
        PVO閉値を取得します.

        Returns:
            int: PVO閉値
        """
        cls._initialize_cache()
        return cls._cache['pvo_threshold']

    @classmethod
    def get_lot_limit_lower(cls):
        """
        最小ロット数計算倍率を取得します.

        Returns:
            float: 最小ロット数計算倍率
        """
        cls._initialize_cache()
        return cls._cache['lot_limit_lower']

    @classmethod
    def get_balance_tether_limit(cls):
        """
        最小証拠金を取得します.

        Returns:
            float: 最小証拠金
        """
        cls._initialize_cache()
        return cls._cache['balance_tether_limit']

    @classmethod
    def get_server_retry_wait(cls):
        """
        サーバーのリトライ待機時間を取得します.

        Returns:
            int: リトライ待機時間 (秒)
        """
        cls._initialize_cache()
        return cls._cache['server_retry_wait']

    @classmethod
    def get_bot_operation_cycle(cls):
        """
        ボットの動作サイクル時間を取得します.

        Returns:
            int: ボットの動作サイクル時間 (秒)
        """
        cls._initialize_cache()
        return cls._cache['bot_operation_cycle']

    @classmethod
    def get_run_timeout_seconds(cls) -> int:
        """全体実行のタイムアウト（秒）。未設定時は 300 を既定にする。"""
        cls._initialize_cache()
        return cls._cache['run_timeout_seconds']

    @classmethod
    def get_api_request_timeout_seconds(cls) -> int:
        """API リクエストのHTTPタイムアウト秒数。未設定時は 20 を既定にする。"""
        cls._initialize_cache()
        return cls._cache['api_request_timeout_seconds']

    @classmethod
    def get_api_max_retry_seconds(cls) -> int:
        """API エラー時の最大再試行秒数。未設定時は 120 を既定にする。"""
        cls._initialize_cache()
        return cls._cache['api_max_retry_seconds']
    
    @classmethod
    def get_test_initial_max_term(cls):
        """
        テストに必要な初期化期間を取得します

        Returns:
            int: 期間
        """
        cls._initialize_cache()
        return cls._cache['test_initial_max_term']

    @classmethod
    def get_log_file_name(cls):
        """
        """
        cls._initialize_cache()
        return cls._cache['log_file']
    
    @classmethod
    def get_log_dir_name(cls):
        """
        ログディレクトリ名を取得します.

        Returns:
            str: ログディレクトリ名
        """
        cls._initialize_cache()
        return cls._cache['log_directory']
    
    @classmethod
    def get_logging_interval(cls):
        """
        ログ出力間隔（イテレーション数）を取得します.

        Returns:
            int: ログ出力間隔（デフォルト: 1 = 毎回ログ出力）
        """
        cls._initialize_cache()
        return cls._cache['logging_interval']
    
    @classmethod
    def get_report_dir_name(cls):
        """レポートの出力ディレクトリ名（未設定時は 'report'）。"""
        cls._initialize_cache()
        return cls._cache['report_directory']
    
    @classmethod
    def get_back_test_mode(cls):
        """
        """
        cls._initialize_cache()
        return cls._cache['back_test']

    def __str__(self):
        """
        コンフィグ内容を可読性よく文字列として表現するメソッドです。
        """
        config_str = f"\nRisk Percentage: {self.get_risk_percentage()}\r\n"
        config_str += f"Account Balance: {self.get_account_balance()}\r\n"
        config_str += f"Leverage: {self.get_leverage()}\r\n"
        config_str += f"Entry Times: {self.get_entry_times()}\r\n"
        config_str += f"Entry Range: {self.get_entry_range()}\r\n"
        config_str += f"Stop Range: {self.get_stop_range()}\r\n"
        config_str += f"Stop AF: {self.get_stop_AF()}\r\n"
        config_str += f"Stop AF Add: {self.get_stop_AF_add()}\r\n"
        config_str += f"Stop AF Max: {self.get_stop_AF_max()}\r\n"
        config_str += f"surge follow price ratio: {self.get_surge_follow_price_ratio()}\r\n"
        config_str += f"Lot Limit Lower: {self.get_lot_limit_lower()}\r\n"
        config_str += f"Balance Tether Limit: {self.get_balance_tether_limit()}\r\n"
        config_str += f"Psar Time Frame: {self.get_psar_time_frame()}\r\n"
        config_str += f"Market: {self.get_market()}\r\n"
        config_str += f"Market Unit: {self.get_market_unit_pair()}\r\n"
        config_str += f"Time Frame: {self.get_time_frame()}\r\n"
        config_str += f"Start Time: {self.get_start_time()}\r\n"
        config_str += f"End Time: {self.get_end_time()}\r\n"
        config_str += f"Start Time (epoch): {self.get_start_epoch()}\r\n"
        config_str += f"End Time (epoch): {self.get_end_epoch()}\r\n"
        config_str += f"Volatility Term: {self.get_volatility_term()}\r\n"
        config_str += f"Donchian Buy Term: {self.get_donchian_buy_term()}\r\n"
        config_str += f"Donchian Sell Term: {self.get_donchian_sell_term()}\r\n"
        config_str += f"PVO Short Term: {self.get_pvo_s_term()}\r\n"
        config_str += f"PVO Long Term: {self.get_pvo_l_term()}\r\n"
        config_str += f"PVO Threshold: {self.get_pvo_threshold()}\r\n"
        config_str += f"Server Retry Wait: {self.get_server_retry_wait()}\r\n"
        config_str += f"Bot Operation Cycle: {self.get_bot_operation_cycle()}\r\n"
        config_str += f"Back Test Mode: {self.get_back_test_mode()}"

        return config_str

    def to_dict(self):
        """
        Convert Config parameters to a dictionary.
        """
        return {
            "Risk Percentage": self.get_risk_percentage(),
            "Account Balance": self.get_account_balance(),
            "Leverage": self.get_leverage(),
            "Entry Times": self.get_entry_times(),
            "Entry Range": self.get_entry_range(),
            "Stop Range": self.get_stop_range(),
            "Stop AF": self.get_stop_AF(),
            "Stop AF Add": self.get_stop_AF_add(),
            "Stop AF Max": self.get_stop_AF_max(),
            "surge follow price ratio": self.get_surge_follow_price_ratio(),
            "Lot Limit Lower": self.get_lot_limit_lower(),
            "Balance Tether Limit": self.get_balance_tether_limit(),
            "Psar Time Frame": self.get_psar_time_frame(),
            "Market": self.get_market(),
            "Market Unit": self.get_market_unit_pair(),
            "Time Frame": self.get_time_frame(),
            "Start Time": self.get_start_time(),
            "End Time": self.get_end_time(),
            "Start Time (epoch)": self.get_start_epoch(),
            "End Time (epoch)": self.get_end_epoch(),
            "Volatility Term": self.get_volatility_term(),
            "Donchian Buy Term": self.get_donchian_buy_term(),
            "Donchian Sell Term": self.get_donchian_sell_term(),
            "PVO Short Term": self.get_pvo_s_term(),
            "PVO Long Term": self.get_pvo_l_term(),
            "PVO Threshold": self.get_pvo_threshold(),
            "Server Retry Wait": self.get_server_retry_wait(),
            "Bot Operation Cycle": self.get_bot_operation_cycle(),
            "Back Test Mode": self.get_back_test_mode()
        }

if __name__ == "__main__":
    # APIキーとAPIシークレットを取得
    api_key = Config.get_api_key()
    api_secret = Config.get_api_secret()

    print(f'API Key: {api_key}')
    print(f'API Secret: {api_secret}')

    # 他の設定情報を取得
    risk_percentage = Config.get_risk_percentage()
    account_balance = Config.get_account_balance()
    leverage = Config.get_leverage()
    entry_times = Config.get_entry_times()
    entry_range = Config.get_entry_range()
    stop_range = Config.get_stop_range()
    stop_AF = Config.get_stop_AF()
    stop_AF_add = Config.get_stop_AF_add()
    stop_AF_max = Config.get_stop_AF_max()
    surge_follow_price_ratio = Config.get_surge_follow_price_ratio()
    lot_limit_lower = Config.get_lot_limit_lower()
    balance_tether_limit = Config.get_balance_tether_limit()
    psar_time_frame = Config.get_psar_time_frame()
    print(f'Risk Percentage: {risk_percentage}')
    print(f'Account Balance: {account_balance}')
    print(f'Leverage: {leverage}')
    print(f'Entry Times: {entry_times}')
    print(f'Entry Range: {entry_range}')
    print(f'Stop Range: {stop_range}')
    print(f'Stop AF: {stop_AF}')
    print(f'Stop AF Add: {stop_AF_add}')
    print(f'Stop AF Max: {stop_AF_max}')
    print(f'surge follow price ratio: {surge_follow_price_ratio}')
    print(f'Lot Limit Lower: {lot_limit_lower}')
    print(f'Balance Thther Limit: {balance_tether_limit}')
    print(f'Psar Time Frame: {psar_time_frame}')

    # Market セクションの情報を取得
    market = Config.get_market()
    time_frame = Config.get_time_frame()
    market_unit_pair = Config.get_market_unit_pair()
    print(f'Market: {market}')
    print(f'Market Unit: {market_unit_pair}')
    print(f'Time Frame: {time_frame}')

    # Period セクションの情報を取得
    start_time = Config.get_start_time()
    end_time = Config.get_end_time()
    print(f'Start Time: {start_time}')
    print(f'End Time: {end_time}')

    # Period セクションの情報を取得 (epoch時間)
    start_epoch = Config.get_start_epoch()
    end_epoch = Config.get_end_epoch()
    print(f'Start Time (epoch): {start_epoch}')
    print(f'End Time (epoch): {end_epoch}')

    # Strategy セクションの情報を取得
    volatility_term = Config.get_volatility_term()
    donchian_buy_term = Config.get_donchian_buy_term()
    donchian_sell_term = Config.get_donchian_sell_term()
    pvo_s_term = Config.get_pvo_s_term()
    pvo_l_term = Config.get_pvo_l_term()
    pvo_threshold = Config.get_pvo_threshold()
    max_term = Config.get_test_initial_max_term()
    print(f'Volatility Term: {volatility_term}')
    print(f'Donchian Buy Term: {donchian_buy_term}')
    print(f'Donchian Sell Term: {donchian_sell_term}')
    print(f'PVO Short Term: {pvo_s_term}')
    print(f'PVO Long Term: {pvo_l_term}')
    print(f'PVO Threshold: {pvo_threshold}')
    print(f'[Test] Max_term: {max_term}')

    # Setting セクションの情報を取得
    server_retry_wait = Config.get_server_retry_wait()
    bot_operation_cycle = Config.get_bot_operation_cycle()
    print(f'Server Retry Wait: {server_retry_wait}')
    print(f'Bot Operation Cycle: {bot_operation_cycle}')

    # コンフィグ一覧表示
    config_instance = Config()
    print("----------")
    print(str(config_instance))
