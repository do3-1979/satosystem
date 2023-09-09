"""
Config クラス:

ボットの設定情報を格納するクラスです。APIキー、トレードの間隔、戦略の選択などの設定を保持します。

このサンプルコードでは、Config クラスが設定ファイル（config.ini など）から
APIキー、APIシークレット、および他の設定情報を読み込むメソッドを提供しています。
設定情報の読み込みには Python の標準ライブラリである configparser を使用しています。
"""

import configparser
from datetime import datetime
import pytz  # pytz ライブラリをインポート

class Config:
    config = configparser.ConfigParser()
    config.read('config2.ini')

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
    def get_market(cls):
        """
        マーケットを取得します.

        Returns:
            str: マーケット情報
        """
        return str(cls.config['Market']['market'])

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
    def get_start_utc(cls):
        """
        開始時刻をUTC時間で取得します.

        Returns:
            datetime: 開始時刻 (UTC)
        """
        start_time_str = cls.config['Period']['start_time']
        start_time = datetime.strptime(start_time_str, "%Y/%m/%d %H:%M")
        start_time = pytz.timezone('UTC').localize(start_time)
        start_unix = int(start_time.timestamp())
        return start_unix

    @classmethod
    def get_end_utc(cls):
        """
        終了時刻をUTC時間で取得します.

        Returns:
            datetime: 終了時刻 (UTC)
        """
        end_time_str = cls.config['Period']['end_time']
        end_time = datetime.strptime(end_time_str, "%Y/%m/%d %H:%M")
        end_time = pytz.timezone('UTC').localize(end_time)
        end_unix = int(end_time.timestamp())
        return end_unix

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
        return int(cls.config['Setting']['bot_operation_cycle'])

if __name__ == "__main__":
    # APIキーとAPIシークレットを取得
    api_key = Config.get_api_key()
    api_secret = Config.get_api_secret()

    print(f'API Key: {api_key}')
    print(f'API Secret: {api_secret}')

    # 他の設定情報を取得
    risk_percentage = Config.get_risk_percentage()
    account_balance = Config.get_account_balance()
    print(f'Risk Percentage: {risk_percentage}')
    print(f'Account Balance: {account_balance}')

    # Market セクションの情報を取得
    market = Config.get_market()
    time_frame = Config.get_time_frame()
    print(f'Market: {market}')
    print(f'Time Frame: {time_frame}')

    # Period セクションの情報を取得
    start_time = Config.get_start_time()
    end_time = Config.get_end_time()
    print(f'Start Time: {start_time}')
    print(f'End Time: {end_time}')

    # Period セクションの情報を取得 (UTC時間)
    start_utc = Config.get_start_utc()
    end_utc = Config.get_end_utc()
    print(f'Start Time (UTC): {start_utc}')
    print(f'End Time (UTC): {end_utc}')

    # Setting セクションの情報を取得
    server_retry_wait = Config.get_server_retry_wait()
    bot_operation_cycle = Config.get_bot_operation_cycle()
    print(f'Server Retry Wait: {server_retry_wait}')
    print(f'Bot Operation Cycle: {bot_operation_cycle}')