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
from config import Config
from logger import Logger
from exchange import Exchange  # Exchange モジュールをインポート

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
        balance = self.exchange.fetchBalance()
        return balance

    def execute_order(self, symbol, side, quantity, price, order_type):
        """
        注文を発行します.

        Args:
            symbol (str): トレードするペアのシンボル (例: 'BTC/USD')
            side (str): 注文のタイプ ('buy' または 'sell')
            quantity (float): 注文数量
            price (float or None): 注文価格 (市場注文の場合は None)
            order_type (str): 注文タイプ ('limit' または 'market')

        Returns:
            dict: 注文の実行結果
        """
        if order_type == 'limit':
            order = self.exchange.create_limit_order(
                symbol=symbol,
                side=side,
                amount=quantity,
                price=price
            )
        elif order_type == 'market':
            order = self.exchange.create_market_order(
                symbol=symbol,
                side=side,
                amount=quantity
            )
        else:
            raise ValueError("Invalid order_type. Use 'limit' or 'market'.")

        response = self.exchange.create_order(
            symbol=order['symbol'],
            side=order['side'],
            type=order['type'],
            quantity=order['amount'],
            price=order['price']
        )

        return response

    def get_price(self):
        """
        取引情報を取得

        Returns:
            list: 価格データのリスト
        """
        err_occuerd = False
        price = []

        # 設定可能なパラメタ：1,3,5,15,30,60,120,240,360,720,D,M,W
        time_frame = Config.get_time_frame()
        if time_frame == 60:
            timeframe = '1h'
        elif time_frame == 120:
            timeframe = '2h'

        # マーケット変換
        market_type = Config.get_market()
        if market_type == 'BTC/USD':
            market = "BTCUSD"
        elif market_type == 'ETH/USD':
            market = "ETHUSD"

        # 期間指定
        start_utc = Config.get_start_utc()
        end_utc = Config.get_end_utc()

        server_retry_wait = Config.get_server_retry_wait()

        get_time = start_utc
        while get_time < end_utc:

            # 価格取得
            while True:
                try:
                    ohlcv = self.exchange.fetch_ohlcv(
                        symbol = market,
                        timeframe = timeframe,
                        since = int(get_time * 1000), # bybitはミリ秒なので1000倍
                    )
                    break
                except ccxt.BaseError as e:
                    log_error(f"価格取得エラー:{str(e)}")
                    if err_occuerd == False:
                        err_occuerd = True
                    time.sleep(server_retry_wait)

            if err_occuerd == True:
                log_error("価格取得エラー復帰")

            # データ成型
            for i in range(len(ohlcv)):
                # 終端時間を超えないかぎり取得
                tmp_time = ohlcv[i][0] / 1000 
                if tmp_time < end_utc:
                    if ohlcv[i][1] != 0 and \
                    ohlcv[i][2] != 0 and \
                    ohlcv[i][3] != 0 and \
                    ohlcv[i][4] != 0 and \
                    ohlcv[i][5] != 0:
                        price.append({ "close_time" : tmp_time,
                        "close_time_dt" : datetime.fromtimestamp(tmp_time).strftime('%Y/%m/%d %H:%M'),
                        "open_price" : ohlcv[i][1],
                        "high_price" : ohlcv[i][2],
                        "low_price" : ohlcv[i][3],
                        "close_price": ohlcv[i][4],
                        "Volume" : ohlcv[i][5]})
                else:
                    break
            get_time = tmp_time

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

    # ETHのused、free、total情報を表示
    eth_balance = balance['ETH']
    print("----------")
    print("ETH Used: ", eth_balance['used'])
    print("ETH Free: ", eth_balance['free'])
    print("ETH Total: ", eth_balance['total'])

    print("----------")
    print("価格データを取得")
    print("----------")
    start_price_time = time.time()
    price_data = exchange.get_price()
    end_price_time = time.time()
    
    # 表示するエントリーのインデックスを指定
    selected_entries = [0, -1]  # 最初と最後

    # 選択したエントリーを表示
    for index in selected_entries:
        entry = price_data[index]
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
