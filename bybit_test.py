import requests
from datetime import datetime
import time
from pprint import pprint
import json

import ccxt
import config_rt
#import config
# -------パラメータ------
from param import *
# -------ログ機能--------
from logc import *
# -------資金管理機能--------
from pos_mng import *
# -------bybit test--------
from bybit import *

bybit = ccxt.bybit()		  # 取引所の定義
bybit.apiKey = config_rt.apiKey # APIキーを設定
bybit.secret = config_rt.secret # APIシークレットを設定


# -------ログ機能--------
from logc import *
# -------オーダー機能----
from order import *
# -------解析機能--------
from anlyz import *

# チャートを取得
flag = {
	"position":{
		"exist" : False,
		"side" : "SELL",
		"price": 0,
		"stop":0,
		"stop-AF": stop_AF,
		"stop-EP":0,
		"ATR":0,
		"lot":0,
		"count":0
	},
	"order":{
		"exist" : False,
		"side" : "",
		"count" : 0
	},
	"add-position":{
		"count":0,
		"first-entry-price":0,
		"last-entry-price":0,
		"unit-range":0,
		"unit-size":0,
		"stop":0
	},
	"sma-value":{
		"prev-sma1":0,
		"prev-sma2":0
	},
	"records":{
		"date":[],
		"profit":[],
		"return":[],
		"side":[],
		"stop-count":[],
		"funds" : start_funds,
		"holding-periods":[],
		"slippage":[],
		"log":[]
	},
	"param":{
		"is_back_test":is_back_test,
		"is_total_test":is_total_test,
	    "symbol_type":symbol_type,
	    "log_unit":log_unit,
	    "lot_limit_lower":lot_limit_lower,
	    "balance_limit":balance_limit,
	    "chart_sec":chart_sec,
	    "buy_term":buy_term,
	    "sell_term":sell_term,
	    "pivot_term":pivot_term,
	    "sma1_term":sma1_term,
	    "sma2_term":sma2_term,
	    "judge_line":judge_line,
	    "judge_price":judge_price,
	    "judge_signal":judge_signal,
	    "volatility_term":volatility_term,
	    "stop_range":stop_range,
	    "trade_risk":trade_risk,
	    "levarage":levarage,
	    "start_funds":start_funds,
	    "entry_times":entry_times,
	    "entry_range":entry_range,
	    "stop_AF":stop_AF,
	    "stop_AF_add":stop_AF_add,
	    "stop_AF_max":stop_AF_max,
		"wait":wait,
		"order_retry_times":order_retry_times,
		"slippage":slippage,
		"stop_neighbor":stop_neighbor,
		"line_notify_time_hour":line_notify_time_hour
	}
}

# -------ログ機能--------
from logc import *

def bybit_test_data_generate(flag):
    start_unix = 0
    end_unix = 9999999999

    start_period = "2023/8/1 0:00"       # back test フラグ
    end_period = "2023/9/1 21:00"         # back test フラグ

    if start_period:
        start_period = datetime.strptime(start_period,"%Y/%m/%d %H:%M")
        start_unix = int(start_period.timestamp())
    if end_period:
        end_period = datetime.strptime( end_period,"%Y/%m/%d %H:%M")
        end_unix = int(end_period.timestamp())

    price_tmp = get_price(flag, start_unix, end_unix)
    price = []

    for i in range( len(price_tmp) ):
        unix_time = price_tmp[i]["close_time"]
        if ( start_unix < unix_time ) and ( end_unix > unix_time ):
            price.append(price_tmp[i])

    # priceをJSON形式で書き出す
    with open('price_data2.json', 'w', encoding='utf-8') as json_file:
        json.dump(price, json_file, ensure_ascii=False, indent=4)

def bybit_test(flag):

    symbol_type = 'BTC/USD'

    if symbol_type == 'BTC/USD':
        symbol = 'BTCUSD' # symbolはPrivateでは/を除く。
    elif symbol_type == 'ETH/USD':
        symbol = 'ETHUSD' # symbolはPrivateでは/を除く。
    else:
        symbol = 'None'

    print("-----------------------------------")
    print("get position test")
    print("-----------------------------------")
    pprint( get_position() )

    print("-----------------------------------")
    print("get_collateral test")
    print("-----------------------------------")
    pprint( get_collateral() )

    print("-----------------------------------")
    print("createOrder BUY test")
    print("-----------------------------------")
    """
    create_order(
        flag,
        symbol,
        type='Market',
        side='Buy',
        amount=1
    )
    """
    
    print("-----------------------------------")
    print("createOrder SELL test")
    print("-----------------------------------")

    """
    create_order(
        flag,
        symbol,
        type='Market',
        side='Sell',
        amount=1
    )
    """

def get_collateral():
    order_retry_times = 3
    wait = 10
    """
    引数 : なし
    戻り値
        result['total'] # 証拠金総額
        result['used'] # 拘束中証拠金
        result['free'] # 使用可能証拠金
    """

    while True:
        result = {}
        try:
            # 口座残高を取得
            collateral = bybit.fetchBalance()

            # 総額
            result['total'] = collateral['total']['BTC']
            # 拘束中
            result['used'] = collateral['used']['BTC']
            # 使用可能
            result['free'] = collateral['free']['BTC']

            # debug
            # pprint(result)

            return result

        except ccxt.BaseError as e:
            out_log("bybitのAPIでエラー発生 = {0}\n".format(e), flag)
            out_log("口座残高取得が失敗しました。{0}秒後に再トライします\n".format(wait*order_retry_times), flag)
            time.sleep(wait*order_retry_times)

# ポジション情報を取得する関数
def get_position():
    order_retry_times = 3
    wait = 10
    symbol_type = 'BTC/USD'
    """
    引数 : なし
    戻り値
        result['side'] # None->ノーポジ、BUY->ロング、SELL->ショート
        result['used'] # 拘束中証拠金
        result['free'] # 使用可能証拠金
        result['lots'] # ロットサイズ
        result['averageprice'] # 全ロットの平均価格
    """

    if symbol_type == 'BTC/USD':
        symbol = 'BTCUSD' # symbolはPrivateでは/を除く。
    elif symbol_type == 'ETH/USD':
        symbol = 'ETHUSD' # symbolはPrivateでは/を除く。
    else:
        symbol = 'None'

    while True:
        result = {}
        try:
            position = bybit.fetch_positions(symbol)

            if position == []:
                result['side'] = 'NONE'
                result['lots'] = 0
            else:
                result['lots'] = position[0]['info']['size']

                # position[0]のinfoメンバから取り出す
                if position[0]['info']['side'] == 'Sell':
                    result['side'] = 'SELL'
                elif position[0]['info']['side'] == 'Buy':
                    result['side'] = 'BUY'
                else: #include 'None'
                    result['side'] = 'NONE'

            #debug
            # pprint(position[0]['info'])
            # pprint(result)

            return result

        except ccxt.BaseError as e:
            out_log("bybitのAPIでエラー発生 = {0}\n".format(e), flag)
            out_log("ポジション情報取得が失敗しました。{0}秒後に再トライします\n".format(wait*order_retry_times), flag)
            time.sleep(wait*order_retry_times)

            return result

# 売買注文の約定確認を行う関数
def create_order( flag, symbol, type, side, amount, price=None ):
    is_back_test = False
    order_retry_times = 3
    wait = 10
    #out_log("#-------------create_order start----------------\n", flag)
    """
    引数
    symbol(str) : 'BTCUSD'
    type(str) : 'Limit' -> 指値　/ 'Market' -> 成行
    side(str) : 'Buy' -> 買い / 'Sell' -> 売り
    amount(float/int) -> 注文枚数
    price(float/int) -> 注文価格(成行の場合は省略可)
    """
    if is_back_test is True:
        #out_log("#-------------create_order end----------------\n", flag)
        return 0

    while True:
        result = {}
        try:
            create_order = bybit.createOrder(
                symbol,     # symbol　BTC/USD
                type,       # type market/limit
                side,       # side Buy/Sell
                amount,
                price
            )
            break
        except ccxt.BaseError as e:
            out_log("bybitのAPIでエラー発生 = {0}\n".format(e), flag)
            out_log("注文の通信が失敗しました。{0}秒後に再トライします\n".format(wait*order_retry_times), flag)
            time.sleep(wait*order_retry_times)

    #out_log("#-------------create_order end----------------\n", flag)

    return create_order

# LINEに通知する関数
def line_notify( text ):
	url = "https://notify-api.line.me/api/notify"
	data = {"message" : text}
	headers = {"Authorization": "Bearer " + config_rt.line_token}
	requests.post(url, data=data, headers=headers)

#--------------------------------------------------------------
# main 処理
#--------------------------------------------------------------

#bybit_test( flag )
bybit_test_data_generate( flag )

#EOF