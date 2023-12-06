import os
import json
import zipfile
import pandas as pd
from datetime import datetime
import logging
import openpyxl
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.chart import LineChart, Reference
from bybit_exchange import BybitExchange
from config import Config

class Util:
    def extract_and_export_logs(self, log_directory, num_logs, output_excel_file):
        """
        指定された数の圧縮ログファイルを読み込み、エクセルファイルにデータとグラフを出力します。

        Args:
            log_directory (str): 圧縮ログファイルが格納されているディレクトリ
            num_logs (int): 読み込むログファイルの数
            output_excel_file (str): 出力するエクセルファイルの名前
        """
        # 圧縮ログファイルのリストを作成
        log_files = []
        for root, _, files in os.walk(log_directory):
            for file in files:
                if file.endswith(".zip") or file.endswith(".json"):
                    log_files.append(os.path.join(root, file))

        # 新しいものから指定された数のログファイルを選択
        selected_log_files = sorted(log_files, reverse=True)[:num_logs]

        # データを格納するためのリスト
        data = []
        proccess_num_logs = min(num_logs, len(selected_log_files))

        # 選択されたログファイルからデータを抽出
        for i, log_file in enumerate(reversed(selected_log_files)):  # 逆順に処理
            print(f"Processing file {i + 1}/{proccess_num_logs}: {log_file}")  # 処理中のファイルを表示
            if log_file.endswith(".zip"):
                with zipfile.ZipFile(log_file, "r") as log_zip:
                    with log_zip.open(log_zip.namelist()[0]) as log_json:
                        log_data = pd.read_json(log_json)
                        data.append(log_data)
            elif log_file.endswith(".json"):
                with open(log_file, "r") as log_json:
                    log_data = pd.read_json(log_json)
                    data.append(log_data)

        # データを連結
        combined_data = pd.concat(data, ignore_index=True)

        # エクセルファイルに出力
        output_excel_file_path = os.path.join(log_directory, output_excel_file)
        workbook = Workbook()
        writer = pd.ExcelWriter(output_excel_file_path, engine='openpyxl')
        writer.book = workbook

        # カラムの選択
        selected_columns = [
            "real_time",
            "close_time_dt",
            "open_price",
            "high_price",
            "low_price",
            "close_price",
            "Volume",
            "stop_price",
            "position_size",
            "total_size",
            "profit_and_loss",
            "volatility",
            "stop_offset",
            "stop_psar_stop_offset",
            "stop_price_surge_stop_offset",
            "pvo_val",
            "decision",
            "side",
            "order_type",
            "dc_h",
            "dc_l",
            "donchian",
            "pvo",
            "positions"
        ]

        # 選択したカラムでデータをフィルタリング
        combined_data = combined_data[selected_columns]

        # 選択したカラムの順番に並べ替え
        combined_data = combined_data[[
            "close_time_dt",
            "real_time",
            "high_price",
            "low_price",
            "close_price",
            "stop_price",
            "dc_h",
            "dc_l",
            "Volume",
            "volatility",
            "decision",
            "side",
            "position_size",
            "profit_and_loss",
            "donchian",
            "pvo",
            "stop_offset",
            "stop_psar_stop_offset",
            "stop_price_surge_stop_offset",
        ]]

        # データをエクセルに書き込み
        combined_data.to_excel(writer, sheet_name='Data', index=False)

        column_name = "グラフ"
        chart_sheet = workbook.create_sheet(title=f"Graph")
        self.generate_line_chart(combined_data, column_name, chart_sheet)

        # エクセルファイルを保存
        writer.save()
        writer.close()
        print("Export completed!")
        
    def generate_line_chart(self, data, column_name, chart_sheet):
        """
        データから指定されたカラムの折れ線グラフを生成し、指定されたシートに追加します。

        Args:
            data (DataFrame): グラフを生成するデータ
            column_name (str): グラフを生成するカラムの名前
            chart_sheet (Worksheet): グラフを追加するシート
        """
        chart = LineChart()
        chart.title = column_name
        chart.y_axis.title = column_name
        chart.x_axis.title = "chart_time"

        data_rows = list(dataframe_to_rows(data, index=False, header=True))
        labels = Reference(chart_sheet, min_col=1, min_row=2, max_row=len(data_rows), max_col=1)
        values = Reference(chart_sheet, min_col=2, min_row=1, max_row=len(data_rows), max_col=len(data_rows[0]))

        chart.add_data(values, titles_from_data=True)
        chart.set_categories(labels)

        chart_sheet.add_chart(chart, f"D{len(data_rows) + 3}")

    def fetch_ohlcv_and_save_to_json(self, exchange, output_directory="ohlcv_json_data", output_filename="ohlcv_data.json"):
        start_epoch = Config.get_start_epoch()
        end_epoch = Config.get_end_epoch()
        #start_time = datetime.strptime(start_epoch, "%Y/%m/%d %H:%M")
        #end_time = datetime.strptime(end_epoch, "%Y/%m/%d %H:%M")
                
        print(f"start_epoch: {start_epoch} end_epoch: {end_epoch} ")
        ohlcv_data = exchange.fetch_ohlcv_by_minutes(start_epoch, end_epoch)

        if not os.path.exists(output_directory):
            os.makedirs(output_directory)

        output_filepath = os.path.join(output_directory, output_filename)

        with open(output_filepath, 'w') as json_file:
            json.dump(ohlcv_data, json_file)
            

        print(f"OHLCVデータをJSONファイルに保存しました: {output_filepath}")

if __name__ == "__main__":
    # Loggerクラスの初期化
    util = Util()

    # 使用例
    log_directory = "logs"  # ログファイルのディレクトリ
    #log_directory = "../test/test_data"  # ログファイルのディレクトリ
    num_logs_to_read = 1  # 読み込むログファイルの数
    output_excel_file = "combined_logs.xlsx"  # 出力エクセルファイルの名前
    
    util.extract_and_export_logs(log_directory, num_logs_to_read, output_excel_file)

    # 1分足の指定ログ取得
    # exchange = BybitExchange(Config.get_api_key(), Config.get_api_secret())
    # util.fetch_ohlcv_and_save_to_json(exchange)