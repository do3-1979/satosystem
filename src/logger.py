"""
Loggerクラス:

ログ情報を収集し、記録するためのクラスです。ボットの動作やトレードの履歴を記録します。

このサンプルコードでは、Loggerクラスがログファイルへの保存とコンソールへの出力を管理します。
ログフォーマット、ログのレベル、ファイルへの保存などが設定されています。
Loggerクラスのインスタンスを作成し、log() メソッドと log_error() メソッドを使用してログメッセージを出力できます。
必要に応じてログレベルやフォーマットをカスタマイズすることができます。
"""
import os
import json
import zipfile
import pandas as pd
from datetime import datetime
import time
import logging

class Logger:
    _instance = None  # シングルトンインスタンスを格納するクラス変数

    def __new__(cls, log_file='log.txt', log_directory="logs"):
        """
        シングルトンインスタンスを生成または既存のインスタンスを返します。

        Args:
            log_file (str): ログを保存するファイル名

        Returns:
            Logger: Loggerクラスの唯一のインスタンス
        """
        if cls._instance is None:
            cls._instance = super(Logger, cls).__new__(cls)
            cls._instance._initialize(log_file, log_directory)
        return cls._instance

    def _initialize(self, log_file, log_directory):
        """
        Loggerクラスを初期化します。

        Args:
            log_file (str): ログを保存するファイル名
        """
        self.log_file = log_file
        self.logger = logging.getLogger('bot_logger')
        self.logger.setLevel(logging.DEBUG)
        self.log_directory = log_directory
        self.current_log_file = None
        self.open_log_file()

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
        
    def open_log_file(self):
        current_time = datetime.now()
        log_filename = current_time.strftime("%Y%m%d%H%M%S.json")
        log_filepath = os.path.join(self.log_directory, log_filename)
        self.current_log_file = open(log_filepath, "w")
        self.current_log_file.write("[\n")

    def close_log_file(self):
        if self.current_log_file:
            self.current_log_file.write("\n]")
            self.current_log_file.close()
            self.current_log_file = None

    def log_trade_data(self, trade_data):
        if self.current_log_file:
            json.dump(trade_data, self.current_log_file, indent=2)
            self.current_log_file.write(",\n")

    def rotate_logs(self):
        self.close_log_file()
        self.open_log_file()

    def compress_logs(self):
        current_time = datetime.now()
        log_count = 0  # 圧縮済みログファイルのカウント
        log_zip_filename = current_time.strftime("%Y%m%d%H%M%S")  # ファイル名のベース部分

        while True:
            log_zip_filepath = os.path.join(self.log_directory, f"{log_zip_filename}_{log_count}.zip")

            # ファイルが存在しない場合に圧縮を行います
            if not os.path.exists(log_zip_filepath):
                with zipfile.ZipFile(log_zip_filepath, "w", zipfile.ZIP_DEFLATED) as log_zip:
                    for root, _, files in os.walk(self.log_directory):
                        for file in files:
                            if file.endswith(".json"):
                                log_file_path = os.path.join(root, file)
                                log_zip.write(log_file_path, os.path.relpath(log_file_path, self.log_directory))
                                os.remove(log_file_path)  # 圧縮後に元ファイルを削除
                break
            else:
                log_count += 1

    def extract_and_export_logs(self,log_directory, num_logs, output_excel_file):
        """
        指定された数の圧縮ログファイルを読み込み、エクセルファイルにデータを出力します。

        Args:
            log_directory (str): 圧縮ログファイルが格納されているディレクトリ
            num_logs (int): 読み込むログファイルの数
            output_excel_file (str): 出力するエクセルファイルの名前
        """
        # 圧縮ログファイルのリストを作成
        log_files = []
        for root, _, files in os.walk(log_directory):
            for file in files:
                if file.endswith(".zip"):
                    log_files.append(os.path.join(root, file))

        # 新しいものから指定された数のログファイルを選択
        selected_log_files = sorted(log_files, reverse=True)[:num_logs]

        # データを格納するためのリスト
        data = []

        # 選択されたログファイルからデータを抽出
        for log_file in selected_log_files:
            with zipfile.ZipFile(log_file, "r") as log_zip:
                with log_zip.open(log_zip.namelist()[0]) as log_json:
                    log_data = pd.read_json(log_json)
                    data.append(log_data)

        # データを連結
        combined_data = pd.concat(data, ignore_index=True)

        # エクセルファイルに出力
        combined_data.to_excel(output_excel_file, index=False)

if __name__ == "__main__":
    # Loggerクラスの初期化
    logger = Logger()

    """

    i = 1
    trade_data = {
        "chart_time": "2023-09-09 14:30:00",
        "time": "2023-09-09 14:31:00",
        "high_price": 150.0 + i,
        "low_price": 140.0 - i,
        "price": 145.0 + i,
        "stop_price": 140.0,
        "volume": 100,
        "total_quantity": 1000 + i,
        "position_quantity": 500,
        "side": "BUY",
        "donchian": {"signal": True, "value": 145.0},
        "pvo": {"signal": True, "side": "BUY"}
    }

    # 取引データを記録
    logger.log_trade_data(trade_data)

    # 1週間ごとにファイルを分けるかチェック
    current_time = datetime.now()
    #if current_time.strftime("%w") == "0":  # 0は日曜日を表す
    #logger.compress_logs()  # 圧縮

    time.sleep(1)

    # ログをローテート
    logger.rotate_logs()

    """

    # 使用例
    log_directory = "logs"  # ログファイルのディレクトリ
    num_logs_to_read = 5  # 読み込むログファイルの数
    output_excel_file = "combined_logs.xlsx"  # 出力エクセルファイルの名前

    logger.extract_and_export_logs(log_directory, num_logs_to_read, output_excel_file)
