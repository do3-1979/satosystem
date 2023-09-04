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
    def __init__(self, log_file='log.txt'):
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
        """ログメッセージを出力する"""
        self.logger.info(message)

    def log_error(self, message):
        """エラーメッセージを出力する"""
        self.logger.error(message)

if __name__ == "__main__":
    # ログを保存するファイル名
    log_file = 'bot.log'

    # Loggerクラスの初期化
    logger = Logger(log_file)

    # ログメッセージを出力
    logger.log('This is an informational message.')
    logger.log_error('This is an error message.')

    # ログファイルの内容を表示
    if os.path.exists(log_file):
        with open(log_file, 'r') as log_file_contents:
            print('Log File Contents:')
            print(log_file_contents.read())
    else:
        print(f'Log file "{log_file}" does not exist.')

