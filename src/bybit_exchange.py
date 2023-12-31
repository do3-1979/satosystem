"""
BybitExchange クラス (Exchange クラスを継承):

Bybit 取引所との連携を行うためのクラスです。Exchange クラスを継承し、Bybit 取引所に特有の設定や操作を追加しています。

Attributes:
    api_key (str): ユーザーごとの API キー
    api_secret (str): ユーザーごとの API シークレット
    exchange (ccxt.Exchange): ccxt ライブラリの Bybit 取引所インスタンス

Methods:
    get_account_balance(self):
        口座の残高情報を取得します。

    execute_order(self, symbol, side, quantity, price, order_type):
        注文を発行します。

Raises:
    ValueError: 無効な order_type が指定された場合に発生します。

Usage:
    # ユーザーごとの API キーと API シークレットを設定
    api_key = 'YOUR_API_KEY'
    api_secret = 'YOUR_API_SECRET'

    # BybitExchange クラスを初期化
    exchange = BybitExchange(api_key, api_secret)

    # 口座残高情報を取得
    balance = exchange.get_account_balance()
    print("口座残高:", balance)

    # 注文を発行 (例: BTC/USD マーケットで1BTC を買う)
    order_response = exchange.execute_order('BTC/USD', 'buy', 1, None, 'market')
    print("注文結果:", order_response)
"""
import ccxt
import time
from datetime import datetime
from datetime import timedelta
from config import Config
from logger import Logger
from exchange import Exchange

class BybitExchange(Exchange):
    def __init__(self, api_key, api_secret):
        """
        BybitExchange クラスの初期化

        Args:
            api_key (str): ユーザーごとの API キー
            api_secret (str): ユーザーごとの API シークレット
        """
        super().__init__(api_key, api_secret)

        self.api_key = api_key
        self.api_secret = api_secret
        self.logger = Logger()

        # 設定可能なパラメタ：1,3,5,15,30,60,120,240,360,720,D,M,W
        time_frame = Config.get_time_frame()
        if time_frame == 60:
            self.timeframe = '1h'
        elif time_frame == 120:
            self.timeframe = '2h'

        # マーケット変換
        market_type = Config.get_market()
        if market_type == 'BTC/USD':
            self.market = "BTCUSD"
        elif market_type == 'ETH/USD':
            self.market = "ETHUSD"

        self.exchange = ccxt.bybit({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
        })

    def get_account_balance(self):
        """
        口座の残高情報を取得します.

        Returns:
            dict: 口座の残高情報
        """
        server_retry_wait = Config.get_server_retry_wait()
        err_occuerd = False
        
        while True:
            try:
                balance = self.exchange.fetchBalance()
                break
            except ccxt.BaseError as e:
                if err_occuerd == False:
                    self.logger.log_error(f"口座の残高情報エラー:{str(e)}")
                    err_occuerd = True
                time.sleep(server_retry_wait)

        if err_occuerd == True:
            self.logger.log_error("口座の残高情報エラー復帰")

        return balance
    
    def get_account_balance_total(self):
        """
        口座上の使用可能な証拠金残高を取得します.

        Returns:
            int: 口座上の使用可能な証拠金残高
        """
        server_retry_wait = Config.get_server_retry_wait()
        err_occuerd = False
        
        while True:
            try:
                balance = self.exchange.fetchBalance()
                break
            except ccxt.BaseError as e:
                if err_occuerd == False:
                    self.logger.log_error(f"口座の使用可能な証拠金残高エラー:{str(e)}")
                    err_occuerd = True
                time.sleep(server_retry_wait)

        if err_occuerd == True:
            self.logger.log_error("口座の使用可能な証拠金残高エラー復帰")

        usd_balance = balance['BTC']['total']

        return usd_balance

    def execute_order(self, side, quantity, price, order_type):
        """
        注文を発行します.

        Args:
            side (str): 注文のタイプ ('buy' または 'sell')
            quantity (float): 注文数量
            price (float or None): 注文価格 (市場注文の場合は None)
            order_type (str): 注文タイプ ('limit' または 'market')

        Returns:
            dict: 注文の実行結果
        """
        server_retry_wait = Config.get_server_retry_wait()
        err_occuerd = False
        
        if order_type == 'limit':
            while True:
                try:
                    order = self.exchange.create_limit_order(
                        symbol=self.market,
                        side=side,
                        amount=quantity,
                        price=price
                    )
                    break
                except ccxt.BaseError as e:
                    if err_occuerd == False:
                        self.logger.log_error(f"指値注文エラー:{str(e)}")
                        err_occuerd = True
                    time.sleep(server_retry_wait)

            if err_occuerd == True:
                self.logger.log_error("指値注文エラー復帰")

        elif order_type == 'market':
            while True:
                try:
                    order = self.exchange.create_market_order(
                        symbol=self.market,
                        side=side,
                        amount=quantity
                    )
                    break
                except ccxt.BaseError as e:
                    if err_occuerd == False:
                        self.logger.log_error(f"成行注文エラー:{str(e)}")
                        err_occuerd = True
                    time.sleep(server_retry_wait)

            if err_occuerd == True:
                self.logger.log_error("成行注文エラー復帰")

        else:
            raise ValueError("Invalid order_type. Use 'limit' or 'market'.")

        # テストでは常に成功
        if Config.get_back_test_mode() == 1:
            response = True
        else:
            response = self.exchange.create_order(
                symbol=order['symbol'],
                side=order['side'],
                type=order['type'],
                quantity=order['amount'],
                price=order['price']
            )

        return response

    def get_nearest_epoch_time(self, end_epoch):
        """_summary_

        Args:
            end_epoch (_type_): _description_

        Returns:
            _type_: _description_
        """
        # 現在のローカル時刻を取得
        #current_local_time = datetime(2023, 5, 1, 0, 1, 30, 2000)
        current_local_time = datetime.now()
        current_local_epoch = int(current_local_time.timestamp())
        
        # 古い時刻を採用
        if end_epoch < current_local_epoch:
            target_epoch = end_epoch
            target_time = datetime.fromtimestamp(target_epoch)
        else:
            target_epoch = current_local_epoch
            target_time = current_local_time
        
        # 指定された時刻リスト
        target_near_times = [1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23]
        
        # 現在の時刻から分と秒を0に設定
        target_time = target_time.replace(minute=0, second=0)
        
        # 最も近い時刻を選択
        year = target_time.year
        month = target_time.month
        
        for i in range(len(target_near_times)):
            if target_time.hour == 23:
                nearest_time = 23
                day = target_time.day
                break
            elif target_time.hour == 0:
                nearest_time = 23
                day = (target_time - timedelta(days=1)).day
                year = (target_time - timedelta(days=1)).year
                month = (target_time - timedelta(days=1)).month
                break
            else:
                if target_time.hour < target_near_times[i]:
                    nearest_time = target_near_times[i-1]
                    day = target_time.day
                    break
        
        # 選択した時刻でepoch時間を作成
        epoch_time_str = datetime(year, month, day, nearest_time, 0, 0)
        epoch_time = int(epoch_time_str.timestamp())

        return epoch_time

    def fetch_ohlcv(self, start_epoch, end_epoch, time_frame):
        """
        取引情報を取得

        Returns:
            list: 価格データのリスト
        """
        err_occuerd = False
        ohlcv_data = []

        back_test_mode = Config.get_back_test_mode()
        server_retry_wait = Config.get_server_retry_wait()
        
        # 終端時間の計算
        end_epoch_fixed = self.get_nearest_epoch_time(end_epoch)
        total_progress = int((end_epoch_fixed - start_epoch) / 60) + 1  # 1分足なので1分ごとに進捗

        get_time = start_epoch
        while get_time < end_epoch_fixed:
            # 価格取得
            while True:
                try:
                    ohlcv = self.exchange.fetch_ohlcv(
                        symbol = self.market,
                        timeframe = time_frame,
                        since = int(get_time * 1000), # bybitはミリ秒なので1000倍
                    )
                    break
                except ccxt.BaseError as e:
                    if err_occuerd == False:
                        self.logger.log_error(f"価格取得エラー:{str(e)}")
                        err_occuerd = True
                    time.sleep(server_retry_wait)

            if err_occuerd == True:
                self.logger.log_error("価格取得エラー復帰")
            # データ成型
            for i in range(len(ohlcv)):
                # 終端時間を超えないかぎり取得
                # volumeは0もありうるので除外する
                tmp_time = ohlcv[i][0] / 1000 
                if tmp_time < end_epoch_fixed:
                    if ohlcv[i][1] != 0 and \
                    ohlcv[i][2] != 0 and \
                    ohlcv[i][3] != 0 and \
                    ohlcv[i][4] != 0:
                        ohlcv_data.append({ "close_time" : tmp_time,
                        "close_time_dt" : datetime.fromtimestamp(tmp_time).strftime('%Y/%m/%d %H:%M'),
                        "open_price" : ohlcv[i][1],
                        "high_price" : ohlcv[i][2],
                        "low_price" : ohlcv[i][3],
                        "close_price": ohlcv[i][4],
                        "Volume" : ohlcv[i][5]})
                else:
                    break
            get_time = tmp_time
            
            if back_test_mode == 1:
                progress = int((get_time - start_epoch) / 60)
                start_date = datetime.fromtimestamp(start_epoch).strftime('%Y/%m/%d %H:%M:%S')
                end_date = datetime.fromtimestamp(end_epoch_fixed).strftime('%Y/%m/%d %H:%M:%S')
                get_date = datetime.fromtimestamp(get_time).strftime('%Y/%m/%d %H:%M:%S')
                print(f"進捗：{progress}/{total_progress} 開始: {start_date} 終了：{end_date} 処理中: {get_date}", end='\r')

        if back_test_mode == 1:
            print("")
        # TODO 取得データ確認（抜け漏れ、ダブり）

        return ohlcv_data

    def fetch_latest_ohlcv(self, time_frame):
        """
        最新取引情報を取得

        Returns:
            list: 価格データのリスト
        """
        err_occuerd = False
        ohlcv_data = []

        server_retry_wait = Config.get_server_retry_wait()

        while True:
            try:
                ohlcv = self.exchange.fetch_ohlcv(
                    symbol = self.market,
                    timeframe = time_frame,
                )
                break
            except ccxt.BaseError as e:
                if err_occuerd == False:
                    self.logger.log_error(f"最新価格取得エラー:{str(e)}")    
                    err_occuerd = True
                time.sleep(server_retry_wait)

        if err_occuerd == True:
            self.logger.log_error("最新価格取得エラー復帰")
        
        latest_ohlcv = ohlcv[-1]
        tmp_time = latest_ohlcv[0] / 1000 
        ohlcv_data.append({ "close_time" : tmp_time,
            "close_time_dt" : datetime.fromtimestamp(tmp_time).strftime('%Y/%m/%d %H:%M'),
            "open_price" : latest_ohlcv[1],
            "high_price" : latest_ohlcv[2],
            "low_price" : latest_ohlcv[3],
            "close_price": latest_ohlcv[4],
            "Volume" : latest_ohlcv[5]})
        
        return ohlcv_data

    def fetch_ticker(self):
        """
        指定されたペアの最新の価格情報を取得します.

        Args:
            symbol (str): 取得するペアのシンボル (例: 'BTC/USD')

        Returns:
            dict: 最新の価格情報
        """        
        # マーケット変換
        market_type = Config.get_market()
        if market_type == 'BTC/USD':
            symbol = "BTCUSD"
        elif market_type == 'ETH/USD':
            symbol = "ETHUSD"
        
        ticker = self.exchange.fetch_ticker(symbol)
        price = ticker["last"]
                           
        return price


if __name__ == "__main__":
    # BybitExchange クラスを初期化
    exchange = BybitExchange(Config.get_api_key(), Config.get_api_secret())

    print("----------")
    print("口座残高情報を取得")
    print("----------")
    start_balance_time = time.time()
    balance = exchange.get_account_balance()
    end_balance_time = time.time()
    # BTCのused、free、total情報を表示
    usd_balance = balance['BTC']
    print("USD Used: ", usd_balance['used'])
    print("USD Free: ", usd_balance['free'])
    print("USD Total: ", usd_balance['total'])
    
    print("----------")
    print("口座残高総合取得")
    print("----------")
    balance = exchange.get_account_balance_total()
    print(f"balance : {balance}")

    print(f"{Config.get_market()} の最新価格情報")
    price = exchange.fetch_ticker()
    print(f"価格: {price}")
    balance_tether = round(price * balance)
    print(f"資産[BTC/USD]: {balance_tether}")
    print("----------")

    print("最新価格データ 2h を取得")
    print("----------")
    start_price_time = time.time()
    ohlcv_data = exchange.fetch_latest_ohlcv(120)
    end_price_time = time.time()
    entry = ohlcv_data[0]
    print(f"生データ: {ohlcv_data}")
    print(f"時刻: {entry['close_time_dt']}")
    print(f"開始価格: {entry['open_price']}")
    print(f"最高価格: {entry['high_price']}")
    print(f"最低価格: {entry['low_price']}")
    print(f"終値: {entry['close_price']}")
    print(f"出来高: {entry['Volume']}")
    print("----------")

    print("最新価格データ 15m を取得")
    print("----------")
    start_price_time = time.time()
    ohlcv_data = exchange.fetch_latest_ohlcv(15)
    end_price_time = time.time()
    entry = ohlcv_data[0]
    print(f"時刻: {entry['close_time_dt']}")
    print(f"開始価格: {entry['open_price']}")
    print(f"最高価格: {entry['high_price']}")
    print(f"最低価格: {entry['low_price']}")
    print(f"終値: {entry['close_price']}")
    print(f"出来高: {entry['Volume']}")
    print("----------")
    
    print("最新価格データ 1m を取得")
    print("----------")
    start_price_time = time.time()
    ohlcv_data = exchange.fetch_latest_ohlcv(1)
    end_price_time = time.time()
    entry = ohlcv_data[0]
    print(f"時刻: {entry['close_time_dt']}")
    print(f"開始価格: {entry['open_price']}")
    print(f"最高価格: {entry['high_price']}")
    print(f"最低価格: {entry['low_price']}")
    print(f"終値: {entry['close_price']}")
    print(f"出来高: {entry['Volume']}")
    print("----------")

    print("価格データを取得 2h")
    print("----------")
    start_price_time = time.time()
    start_epoch = Config.get_start_epoch()
    end_epoch = Config.get_end_epoch()
    ohlcv_data = exchange.fetch_ohlcv(start_epoch,end_epoch,120)
    end_price_time = time.time()
    
    data_num = len(ohlcv_data)
    print(f"データ数: {data_num}")
    
    # 表示するエントリーのインデックスを指定
    selected_entries = [0, -1]  # 最初と最後

    # 選択したエントリーを表示
    for index in selected_entries:
        entry = ohlcv_data[index]
        print(f"選択した価格データ:{index}")
        print(f"時刻: {entry['close_time_dt']}")
        print(f"開始価格: {entry['open_price']}")
        print(f"最高価格: {entry['high_price']}")
        print(f"最低価格: {entry['low_price']}")
        print(f"終値: {entry['close_price']}")
        print(f"出来高: {entry['Volume']}")
        print("----------")

    print("口座残高情報取得にかかった時間: {:.2f}秒".format(end_balance_time - start_balance_time))
    print("価格データ取得にかかった時間: {:.2f}秒".format(end_price_time - start_price_time))
    print("----------")
    print("価格データを取得 15 min")
    print("----------")
    start_price_time = time.time()
    start_epoch = Config.get_start_epoch()
    end_epoch = Config.get_end_epoch()
    ohlcv_data = exchange.fetch_ohlcv(start_epoch,end_epoch,15)
    end_price_time = time.time()

    data_num = len(ohlcv_data)
    print(f"データ数: {data_num}")
    
    # 表示するエントリーのインデックスを指定
    selected_entries = [0, -1]  # 最初と最後

    # 選択したエントリーを表示
    for index in selected_entries:
        entry = ohlcv_data[index]
        print(f"選択した価格データ:{index}")
        print(f"時刻: {entry['close_time_dt']}")
        print(f"開始価格: {entry['open_price']}")
        print(f"最高価格: {entry['high_price']}")
        print(f"最低価格: {entry['low_price']}")
        print(f"終値: {entry['close_price']}")
        print(f"出来高: {entry['Volume']}")
        print("----------")

    print("口座残高情報取得にかかった時間: {:.2f}秒".format(end_balance_time - start_balance_time))
    print("価格データ取得にかかった時間: {:.2f}秒".format(end_price_time - start_price_time))

    # 注文を発行 (例: BTC/USD マーケットで1BTC を買う)
    # order_response = exchange.execute_order('BTCUSD', 'buy', 1, None, 'market')
    # print("注文結果:", order_response)
