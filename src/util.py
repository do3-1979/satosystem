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
                if file.endswith(".zip"):
                    log_files.append(os.path.join(root, file))

        # 新しいものから指定された数のログファイルを選択
        selected_log_files = sorted(log_files, reverse=True)[:num_logs]

        # データを格納するためのリスト
        data = []
        proccess_num_logs = min(num_logs, len(selected_log_files))

        # 選択されたログファイルからデータを抽出
        for i, log_file in enumerate(reversed(selected_log_files)):  # 逆順に処理
            print(f"Processing file {i + 1}/{proccess_num_logs}: {log_file}")  # 処理中のファイルを表示
            with zipfile.ZipFile(log_file, "r") as log_zip:
                with log_zip.open(log_zip.namelist()[0]) as log_json:
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
            "pvo_val",
            "decision",
            "side",
            "order_type",
            "dc_h",
            "dc_l",
            "donchian",
            "pvo"
        ]

        # 選択したカラムでデータをフィルタリング
        combined_data = combined_data[selected_columns]

        # 選択したカラムの順番に並べ替え
        combined_data = combined_data[[
            "real_time",
            "close_time_dt",
            "Volume",
            "high_price",
            "low_price",
            "close_price",
            "dc_h",
            "dc_l",
            "volatility",
            "decision",
            "side",
            "stop_price",
            "position_size",
            "profit_and_loss",
            "donchian",
            "pvo"
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

if __name__ == "__main__":
    # Loggerクラスの初期化
    util = Util()

    # 使用例
    #log_directory = "logs"  # ログファイルのディレクトリ
    log_directory = "../test/test_data"  # ログファイルのディレクトリ
    num_logs_to_read = 33  # 読み込むログファイルの数
    output_excel_file = "combined_logs.xlsx"  # 出力エクセルファイルの名前

    util.extract_and_export_logs(log_directory, num_logs_to_read, output_excel_file)
