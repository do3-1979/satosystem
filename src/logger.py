"""
Loggerクラス:

ログ情報を収集し、記録するためのクラスです。ボットの動作やトレードの履歴を記録します。

このサンプルコードでは、Loggerクラスがログファイルへの保存とコンソールへの出力を管理します。
ログフォーマット、ログのレベル、ファイルへの保存などが設定されています。
Loggerクラスのインスタンスを作成し、log() メソッドと log_error() メソッドを使用してログメッセージを出力できます。
必要に応じてログレベルやフォーマットをカスタマイズすることができます。
"""
import os
import logging

class Logger:
    _instance = None  # シングルトンインスタンスを格納するクラス変数

    def __new__(cls, log_file='log.txt'):
        """
        シングルトンインスタンスを生成または既存のインスタンスを返します。

        Args:
            log_file (str): ログを保存するファイル名

        Returns:
            Logger: Loggerクラスの唯一のインスタンス
        """
        if cls._instance is None:
            cls._instance = super(Logger, cls).__new__(cls)
            cls._instance._initialize(log_file)
        return cls._instance

    def _initialize(self, log_file):
        """
        Loggerクラスを初期化します。

        Args:
            log_file (str): ログを保存するファイル名
        """
        self.log_file = log_file
        self.logger = logging.getLogger('bot_logger')
        self.logger.setLevel(logging.DEBUG)

        # ログフォーマット
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

        # コンソールハンドラの設定
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        # ファイルハンドラの設定
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

    def log(self, message):
        """
        ログメッセージを出力します。

        Args:
            message (str): 出力するログメッセージ
        """
        self.logger.info(message)

    def log_error(self, message):
        """
        エラーメッセージを出力します。

        Args:
            message (str): 出力するエラーメッセージ
        """
        self.logger.error(message)
