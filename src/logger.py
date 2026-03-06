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
from datetime import datetime
import logging
from config import Config

# latest_status.json のローリングバッファサイズ
MAX_CANDLE_HISTORY = 60
MAX_ERROR_HISTORY  = 20
LATEST_STATUS_FILE = "latest_status.json"


class Logger:
    _instance = None  # シングルトンインスタンスを格納するクラス変数

    def __new__(cls):
        """
        シングルトンインスタンスを生成または既存のインスタンスを返します。

        Args:
            log_file (str): ログを保存するファイル名

        Returns:
            Logger: Loggerクラスの唯一のインスタンス
        """
        if cls._instance is None:
            cls._instance = super(Logger, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """
        Loggerクラスを初期化します。

        Args:
            log_file (str): ログを保存するファイル名
        """
        self.log_file = Config.get_log_file_name()
        self.logger = logging.getLogger('bot_logger')
        self.logger.setLevel(logging.DEBUG)
        self.log_directory = Config.get_log_dir_name()

        # ディレクトリが存在しない場合は作成
        if not os.path.exists(self.log_directory):
            os.makedirs(self.log_directory)

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
        file_handler = logging.FileHandler(self.log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

        # latest_status.json 用のローリングバッファ
        self._latest_candles: list  = []   # 最新 MAX_CANDLE_HISTORY 件
        self._recent_errors: list   = []   # 最新 MAX_ERROR_HISTORY 件
        self._error_count: int      = 0
        self._backtest_result       = None
        # バックテスト / キャッシュベースホットテスト時は latest_status.json を書かない
        _bt = Config.get_back_test_mode()
        _cht = (
            _bt == 0
            and Config.get_hot_test_dummy_mode() == 1
            and Config.get_use_cached_data_for_hot_test() == 1
        )
        self._is_fast_mode: bool = (_bt == 1) or _cht  # 高速ループ時はスキップ

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
        # エラーを latest_status.json にも記録（高速モード除く）
        if not self._is_fast_mode:
            self._recent_errors.append({
                "ts": datetime.now().strftime('%Y/%m/%d %H:%M:%S'),
                "msg": str(message)
            })
            if len(self._recent_errors) > MAX_ERROR_HISTORY:
                self._recent_errors = self._recent_errors[-MAX_ERROR_HISTORY:]
            self._error_count += 1
            self._write_latest_status()

    # ──────────────────────────────────────────────────
    #  latest_status.json 関連
    # ──────────────────────────────────────────────────

    def _build_candle_entry(self, td: dict) -> dict:
        """trade_data から latest_status.json 用のエントリを構築"""
        pos = td.get('positions', {})
        return {
            "ts":            td.get('real_time', ''),
            "high":          td.get('high_price', 0),
            "low":           td.get('low_price', 0),
            "close":         td.get('close_price', 0),
            "buy_price":     pos.get('position_price', td.get('position_price', 0)),
            "stop":          td.get('stop_price', 0),
            "volatility":    td.get('volatility', 0),
            "volume":        td.get('Volume', 0),
            "decision":      str(td.get('decision', '')),
            "side":          str(td.get('side', '')),
            "position_size": td.get('position_size', 0),
            "asset":         pos.get('quantity', td.get('position_quantity', 0)),
            "position_side": pos.get('side', ''),
            "pnl":           td.get('profit_and_loss', 0),
            "total_pnl":     td.get('total_profit_and_loss', 0),
            "pvo_val":       td.get('pvo_val', 0),
            "adx":           td.get('adx', 0),
            "psar":          td.get('psar', 0),
            "dc_h":          td.get('dc_h', 0),
            "dc_l":          td.get('dc_l', 0),
        }

    def _write_latest_status(self, extra: dict = None):
        """latest_status.json を上書きして最新状態をモニター用に保存"""
        latest = self._latest_candles[-1] if self._latest_candles else {}
        status = {
            "updated_at":      datetime.now().strftime('%Y/%m/%d %H:%M:%S'),
            "latest":          latest,
            "candles":         self._latest_candles,
            "recent_errors":   self._recent_errors,
            "error_count":     self._error_count,
            "backtest_result": self._backtest_result,
        }
        if extra:
            status.update(extra)
        try:
            filepath = os.path.join(self.log_directory, LATEST_STATUS_FILE)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(status, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"latest_status.json 書き込みエラー: {e}")

    def set_backtest_result(self, result: dict):
        """バックテスト / ホットテスト終了時の結果を記録してモニターに反映"""
        self._backtest_result = result
        self._write_latest_status()

    def open_log_file(self):
        current_time = datetime.now()
        log_filename = current_time.strftime("%Y%m%d%H%M%S.json")
        log_filepath = os.path.join(self.log_directory, log_filename)
        self.current_log_file = open(log_filepath, "w", encoding='utf-8')
        self.current_log_file.write("[\n")

    def close_log_file(self):
        if self.current_log_file:
            # ファイルに , を削除して ] を出力
            self.current_log_file.seek(self.current_log_file.tell() - 2)  # カーソルを後ろに移動
            self.current_log_file.write("]\n")
            self.current_log_file.close()
            self.current_log_file = None

    def log_trade_data(self, trade_data):
        """JSON ファイルに trade_data を記録し、latest_status.json も更新"""
        if self.current_log_file:
            json.dump(trade_data, self.current_log_file, indent=2)
            self.current_log_file.write(",\n")
        # 高速モード（バックテスト / キャッシュHotTest）時は latest_status.json をスキップ
        if not self._is_fast_mode:
            candle = self._build_candle_entry(trade_data)
            self._latest_candles.append(candle)
            if len(self._latest_candles) > MAX_CANDLE_HISTORY:
                self._latest_candles = self._latest_candles[-MAX_CANDLE_HISTORY:]
            self._write_latest_status()

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

if __name__ == "__main__":
    # Loggerクラスの初期化
    logger = Logger()

    trade_data = {
            "close_time": 1695549600.0,
            "close_time_dt": "2023/09/24 19:00",
            "open_price": 26586.0,
            "high_price": 26586.5,
            "low_price": 26576.0,
            "close_price": 26579.5,
            "Volume": 25.59252078,
            "real_time": "2023/09/24 20:13:02",
            "stop_price": 0,
            "position_size": 0,
            "total_size": 0,
            "profit_and_loss": 0,
            "volatility": 28,
            "decision": None,
            "side": None,
            "order_type": "Market",
            "donchian": {
                "signal": False,
                "side": None
            },
            "pvo": {
                "signal": False,
                "side": None
            }
        }

    # 取引データを記録
    logger.log_trade_data(trade_data)

    logger.close_log_file()
    
    logger.compress_logs()
