from datetime import datetime
import time
from pprint import pprint

import ccxt
import config_rt
#import config
# -------パラメータ------
from param import *
# -------ログ機能--------
from logc import *
# -------資金管理機能--------
from pos_mng import *

bybit = ccxt.bybit()		  # 取引所の定義
bybit.apiKey = config_rt.apiKey # APIキーを設定
bybit.secret = config_rt.secret # APIシークレットを設定

# -------ログ機能--------
from logc import *
# -------オーダー機能----
from order import *
# -------解析機能--------
from anlyz import *

# bybit用処理
def get_ohlcv(flag, start_time, end_time):
    # 制御用パラメタ初期化
    wait = flag["param"]["wait"]
    symbol_type = flag["param"]["symbol_type"]
    allowance_remaining = 0

    err_occuerd = False

    price = []

    # 設定可能なパラメタ：1,3,5,15,30,60,120,240,360,720,D,M,W
    # Bybitは分単位なのでsec -> micに変換する
    chart_unit = (flag["param"]["chart_sec"]) / 60
    if chart_unit == 60:
        timeframe = '1h'
    elif chart_unit == 120:
        timeframe = '2h'
    
    if symbol_type == 'BTC/USD':
        market = "BTCUSD"
    elif symbol_type == 'ETH/USD':
        market = "ETHUSD"

    get_time = start_time
    while get_time < end_time:

        # 価格取得
        while True:
            try:
                ohlcv = bybit.fetch_ohlcv(
                    symbol = market,
                    timeframe = timeframe,
                    since = int(get_time * 1000), # bybitはミリ秒なので1000倍
                )
                break
            except ccxt.BaseError as e:
                log = "Bybitの価格取得でエラー発生 : " + str(e)
                out_log(log, flag)
                out_log("{0}秒待機してやり直します".format(wait), flag)
                if err_occuerd == False:
                    err_occuerd = True
                time.sleep(wait)

        if err_occuerd == True:
            out_log("Bybitの価格取得 復帰", flag)

        # bybit時はallowanceは0固定
        allowance_remaining = 0

        # データ成型
        for i in range(len(ohlcv)):
            # 終端時間を超えないかぎり取得
            tmp_time = ohlcv[i][0] / 1000 
            if tmp_time < end_time:
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
                    "Volume" : ohlcv[i][5],
                    "QuoteVolume" : 0,
                    "allowance_remaining" : allowance_remaining})
            else:
                break
        get_time = tmp_time

    if price is not None:
        return price
    else:
        out_log("データが存在しません", flag)
        return None

def get_last_ohlcv(flag):
    # 制御用パラメタ初期化
    wait = flag["param"]["wait"]
    symbol_type = flag["param"]["symbol_type"]
    allowance_remaining = 0

    err_occuerd = False

    price = []

    # 設定可能なパラメタ：1,3,5,15,30,60,120,240,360,720,D,M,W
    # Bybitは分単位なのでsec -> micに変換する
    chart_unit = (flag["param"]["chart_sec"]) / 60
    if chart_unit == 60:
        timeframe = '1h'
    elif chart_unit == 120:
        timeframe = '2h'
    
    if symbol_type == 'BTC/USD':
        market = "BTCUSD"
    elif symbol_type == 'ETH/USD':
        market = "ETHUSD"

    # 価格取得
    while True:
        try:
            ohlcv = bybit.fetch_ohlcv(
                symbol = market,
                timeframe = timeframe,
            )
            break
        except ccxt.BaseError as e:
            log = "Bybitの最新価格取得でエラー発生 : " + str(e)
            out_log(log, flag)
            out_log("{0}秒待機してやり直します".format(wait), flag)
            if err_occuerd == False:
                err_occuerd = True
            time.sleep(wait)

    if err_occuerd == True:
        out_log("Bybitの最新価格取得 復帰", flag)

    # bybit時はallowanceは0固定
    allowance_remaining = 0

    # データ成型
    for i in range(len(ohlcv)):
        # 終端時間を超えないかぎり取得
        tmp_time = ohlcv[i][0] / 1000 
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
            "Volume" : ohlcv[i][5],
            "QuoteVolume" : 0,
            "allowance_remaining" : allowance_remaining})

    if price is not None:
        return price
    else:
        out_log("データが存在しません", flag)
        return None

# EOF