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

    @classmethod
    def get_api_key(cls):
        """
        APIキーを取得します.

        Returns:
            str: APIキー
        """
        return cls.config['API']['api_key']

    @classmethod
    def get_api_secret(cls):
        """
        APIシークレットを取得します.

        Returns:
            str: APIシークレット
        """
        return cls.config['API']['api_secret']

    @classmethod
    def get_risk_percentage(cls):
        """
        リスク割合を取得します.

        Returns:
            float: リスク割合
        """
        return float(cls.config['RiskManagement']['risk_percentage'])
    
    @classmethod
    def get_account_balance(cls):
        """
        アカウント残高を取得します.

        Returns:
            float: アカウント残高
        """
        return float(cls.config['RiskManagement']['account_balance'])
    
    @classmethod
    def get_leverage(cls):
        """
        レバレッジを取得します.

        Returns:
            int: レバレッジ
        """
        return int(cls.config['RiskManagement']['leverage'])

    @classmethod
    def get_entry_times(cls):
        """
        エントリー回数を取得します.

        Returns:
            int: エントリー回数
        """
        return int(cls.config['RiskManagement']['entry_times'])

    @classmethod
    def get_entry_range(cls):
        """
        エントリー範囲を取得します.

        Returns:
            int: エントリー範囲
        """
        return int(cls.config['RiskManagement']['entry_range'])

    @classmethod
    def get_stop_range(cls):
        """
        ストップ範囲を取得します.

        Returns:
            int: ストップ範囲
        """
        return int(cls.config['RiskManagement']['stop_range'])

    @classmethod
    def get_stop_AF(cls):
        """
        ストップアンドリバースファクター（AF）を取得します.

        Returns:
            float: ストップアンドリバースファクター（AF）
        """
        return float(cls.config['RiskManagement']['stop_AF'])

    @classmethod
    def get_stop_AF_add(cls):
        """
        ストップアンドリバースファクター（AF）の追加値を取得します.

        Returns:
            float: ストップアンドリバースファクター（AF）の追加値
        """
        return float(cls.config['RiskManagement']['stop_AF_add'])

    @classmethod
    def get_stop_AF_max(cls):
        """
        ストップアンドリバースファクター（AF）の最大値を取得します.

        Returns:
            float: ストップアンドリバースファクター（AF）の最大値
        """
        return float(cls.config['RiskManagement']['stop_AF_max'])

    @classmethod
    def get_surge_follow_price_ratio(cls):
        """
        ストップ近傍のレートを取得します.

        Returns:
            float: ストップ近傍のレート
        """
        return float(cls.config['RiskManagement']['surge_follow_price_ratio'])
    
    @classmethod
    def get_market(cls):
        """
        マーケットを取得します.

        Returns:
            str: マーケット情報
        """
        return str(cls.config['Market']['market'])

    @classmethod
    def get_market_unit_pair(cls):
        """
        マーケットからユニットペアを取得します.

        Returns:
            str: マーケット情報から取得したユニットペア
        """
        market_info = cls.config['Market']['market']
        unit_pair = market_info[:3]  # マーケット情報から先頭の3文字を取得
        return unit_pair

    @classmethod
    def get_time_frame(cls):
        """
        時間軸を取得します.

        Returns:
            int: 時間軸[分]
        """
        return int(cls.config['Market']['time_frame'])

    @classmethod
    def get_start_time(cls):
        """
        開始時刻を取得します.

        Returns:
            str: 開始時刻 (フォーマット: "YYYY/M/D H:mm")
        """
        return cls.config['Period']['start_time']

    @classmethod
    def get_end_time(cls):
        """
        終了時刻を取得します.

        Returns:
            str: 終了時刻 (フォーマット: "YYYY/M/D H:mm")
        """
        return cls.config['Period']['end_time']

    @classmethod
    def get_start_epoch(cls):
        """
        開始時刻をepoch時間で取得します.

        Returns:
            datetime: 開始時刻 (epoch)
        """
        start_time_str = cls.config['Period']['start_time']
        start_time = datetime.strptime(start_time_str, "%Y/%m/%d %H:%M")
        #start_time = pytz.timezone('epoch').localize(start_time)
        start_unix = int(start_time.timestamp())
        return start_unix

    @classmethod
    def get_end_epoch(cls):
        """
        終了時刻をepoch時間で取得します.

        Returns:
            datetime: 終了時刻 (epoch)
        """
        end_unix = 9999999999
        end_time_str = cls.config['Period']['end_time']

        if (end_time_str == "None") or (end_time_str == ""):
            pass
        else:
            end_time = datetime.strptime(end_time_str, "%Y/%m/%d %H:%M")
            #end_time = pytz.timezone('epoch').localize(end_time)
            end_unix = int(end_time.timestamp())

        return end_unix
    
    @classmethod
    def get_volatility_term(cls):
        """
        ボラティリティ期間を取得します.

        Returns:
            int: ボラティリティ期間
        """
        return int(cls.config['Strategy']['volatility_term'])

    @classmethod
    def get_donchian_buy_term(cls):
        """
        ドンチャン買い期間を取得します.

        Returns:
            int: ドンチャン買い期間
        """
        return int(cls.config['Strategy']['donchian_buy_term'])

    @classmethod
    def get_donchian_sell_term(cls):
        """
        ドンチャン売り期間を取得します.

        Returns:
            int: ドンチャン売り期間
        """
        return int(cls.config['Strategy']['donchian_sell_term'])

    @classmethod
    def get_pvo_s_term(cls):
        """
        PVO短期間を取得します.

        Returns:
            int: PVO短期間
        """
        return int(cls.config['Strategy']['pvo_s_term'])

    @classmethod
    def get_pvo_l_term(cls):
        """
        PVO長期間を取得します.

        Returns:
            int: PVO長期間
        """
        return int(cls.config['Strategy']['pvo_l_term'])

    @classmethod
    def get_pvo_threshold(cls):
        """
        PVO閾値を取得します.

        Returns:
            int: PVO閾値
        """
        return int(cls.config['Strategy']['pvo_threshold'])

    @classmethod
    def get_lot_limit_lower(cls):
        """
        最小ロット数計算倍率を取得します.

        Returns:
            float: 最小ロット数計算倍率
        """
        return float(cls.config['Potfolio']['lot_limit_lower'])

    @classmethod
    def get_balance_tether_limit(cls):
        """
        最小証拠金を取得します.

        Returns:
            float: 最小証拠金
        """
        return float(cls.config['Potfolio']['balance_tether_limit'])

    @classmethod
    def get_server_retry_wait(cls):
        """
        サーバーのリトライ待機時間を取得します.

        Returns:
            int: リトライ待機時間 (秒)
        """
        return int(cls.config['Setting']['server_retry_wait'])

    @classmethod
    def get_bot_operation_cycle(cls):
        """
        ボットの動作サイクル時間を取得します.

        Returns:
            int: ボットの動作サイクル時間 (秒)
        """
        cyctime = 0
        
        if cls.get_back_test_mode == 0:
            cyctime = int(cls.config['Setting']['bot_operation_cycle'])
        
        return cyctime
    
    @classmethod
    def get_test_initial_max_term(cls):
        """
        テストに必要な初期化期間を取得します

        Returns:
            int: 期間
        """
        v_term = int(cls.config['Strategy']['volatility_term'])
        d_b_term = int(cls.config['Strategy']['donchian_buy_term'])
        d_s_term = int(cls.config['Strategy']['donchian_sell_term'])
        pv_s_term = int(cls.config['Strategy']['pvo_s_term'])
        
        max_term = max(v_term, d_b_term, d_s_term, pv_s_term)

        return max_term

    @classmethod
    def get_log_file_name(cls):
        """
        """
        return cls.config['Log']['log_file']
    
    @classmethod
    def get_log_dir_name(cls):
        """
        """
        return cls.config['Log']['log_directory']
    
    @classmethod
    def get_back_test_mode(cls):
        """
        """
        return cls.config['Backtest']['back_test']

    def __str__(self):
        """
        コンフィグ内容を可読性よく文字列として表現するメソッドです。
        """
        config_str = f"\nRisk Percentage: {self.get_risk_percentage()}\n"
        config_str += f"Account Balance: {self.get_account_balance()}\n"
        config_str += f"Leverage: {self.get_leverage()}\n"
        config_str += f"Entry Times: {self.get_entry_times()}\n"
        config_str += f"Entry Range: {self.get_entry_range()}\n"
        config_str += f"Stop Range: {self.get_stop_range()}\n"
        config_str += f"Stop AF: {self.get_stop_AF()}\n"
        config_str += f"Stop AF Add: {self.get_stop_AF_add()}\n"
        config_str += f"Stop AF Max: {self.get_stop_AF_max()}\n"
        config_str += f"surge follow price ratio: {self.get_surge_follow_price_ratio()}\n"
        config_str += f"Lot Limit Lower: {self.get_lot_limit_lower()}\n"
        config_str += f"Balance Tether Limit: {self.get_balance_tether_limit()}\n"
        config_str += f"Market: {self.get_market()}\n"
        config_str += f"Market Unit: {self.get_market_unit_pair()}\n"
        config_str += f"Time Frame: {self.get_time_frame()}\n"
        config_str += f"Start Time: {self.get_start_time()}\n"
        config_str += f"End Time: {self.get_end_time()}\n"
        config_str += f"Start Time (epoch): {self.get_start_epoch()}\n"
        config_str += f"End Time (epoch): {self.get_end_epoch()}\n"
        config_str += f"Volatility Term: {self.get_volatility_term()}\n"
        config_str += f"Donchian Buy Term: {self.get_donchian_buy_term()}\n"
        config_str += f"Donchian Sell Term: {self.get_donchian_sell_term()}\n"
        config_str += f"PVO Short Term: {self.get_pvo_s_term()}\n"
        config_str += f"PVO Long Term: {self.get_pvo_l_term()}\n"
        config_str += f"PVO Threshold: {self.get_pvo_threshold()}\n"
        config_str += f"Server Retry Wait: {self.get_server_retry_wait()}\n"
        config_str += f"Bot Operation Cycle: {self.get_bot_operation_cycle()}\n"
        config_str += f"Back Test Mode: {self.get_back_test_mode()}"

        return config_str

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
