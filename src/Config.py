import os
import configparser

"""
Configクラス:

ボットの設定情報を格納するクラスです。APIキー、トレードの間隔、戦略の選択などの設定を保持します。

このサンプルコードでは、Configクラスが設定ファイル（config.iniなど）から
APIキー、APIシークレット、および他の設定情報を読み込むメソッドを提供しています。
設定情報の読み込みにはPythonの標準ライブラリであるconfigparserを使用しています。
"""

class Config:
    def __init__(self, config_file='config.ini'):
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        self.config.read(config_file)

    def get_api_key(self):
        """
        APIキーを取得
        :return: APIキー
        """
        return self.config.get('API', 'api_key')

    def get_api_secret(self):
        """
        APIシークレットを取得
        :return: APIシークレット
        """
        return self.config.get('API', 'api_secret')

    def get_setting(self, section, key):
        """
        設定情報を取得
        :param section: セクション名
        :param key: キー名
        :return: 設定値
        """
        return self.config.get(section, key)

if __name__ == "__main__":
    # 設定ファイルの名前
    config_file = 'config.ini'

    # Configクラスの初期化
    config = Config(config_file)

    # APIキーとAPIシークレットを取得
    api_key = config.get_api_key()
    api_secret = config.get_api_secret()

    print(f'API Key: {api_key}')
    print(f'API Secret: {api_secret}')
    
    # 他の設定情報を取得
    setting_value = config.get_setting('SectionName', 'SettingKey')
    print(f'Setting Value: {setting_value}')
