"""
Configクラス:

ボットの設定情報を格納するクラスです。APIキー、トレードの間隔、戦略の選択などの設定を保持します。

このサンプルコードでは、Configクラスが設定ファイル（config.iniなど）から
APIキー、APIシークレット、および他の設定情報を読み込むメソッドを提供しています。
設定情報の読み込みにはPythonの標準ライブラリであるconfigparserを使用しています。
"""

import configparser

class Config:
    config = configparser.ConfigParser()
    config.read('config.ini')

    @classmethod
    def get_api_key(cls):
        return cls.config['API']['api_key']

    @classmethod
    def get_api_secret(cls):
        return cls.config['API']['api_secret']

    @classmethod
    def get_risk_percentage(cls):
        return float(cls.config['RiskManagement']['risk_percentage'])

    @classmethod
    def get_account_balance(cls):
        return float(cls.config['RiskManagement']['account_balance'])


if __name__ == "__main__":
    # Configクラスの初期化は不要です
    # 設定ファイルの名前
    config_file = 'config.ini'

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
