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
		"side" : "",
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
		"line_notify_time_hour":line_notify_time_hour
	}
}

"""
create_order(
    flag,
    symbol = symbol_type,
    type='Market',
    side='Buy',
    amount=result["lots"])
"""

def bybit_test():

    #pprint(bybit.has)

    #pprint(bybit.api)

    symbol = 'ETH/USD'
    #symbol = 'BTC/USD'

    # get_collateral
    print("-----------------------------------")
    print("get_collateral test")
    print("-----------------------------------")
    get_collateral()

    print("-----------------------------------")
    print("createOrder BUY test")
    print("-----------------------------------")
    flag = {}
    """
    create_order(
        flag,
        symbol = symbol,
        type='Market',
        side='Buy',
        amount=10
    )
    """

    print("-----------------------------------")
    print("createOrder BUY test")
    print("-----------------------------------")
    """
    create_order(
        flag,
        symbol = symbol,
        type='Market',
        side='Sell',
        amount=10
    )
    """

    print("-----------------------------------")
    print("get position test")
    print("-----------------------------------")
    get_position()

    time.sleep(1)


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
            pprint(result)

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

    symbol = 'ETH/USD'

    if symbol_type == 'BTC/USD':
        symbol = 'BTCUSD' # symbolはPrivateでは/を除く。
    elif symbol_type == 'ETH/USD':
        symbol = 'ETHUSD' # symbolはPrivateでは/を除く。
    else:
        symbol = 'None'

    while True:
        result = {}
        try:

            position = bybit.v2_private_get_position_list({
                'symbol' : symbol
            })
            if position == []:
                result['side'] = 'NONE'
                result['lots'] = 0
            else:
                result['lots'] = position['result']['size']

                if position['result']['side'] == 'Sell':
                    result['side'] = 'SELL'
                elif position['result']['side'] == 'Buy':
                    result['side'] = 'BUY'
                else:
                    result['side'] = 'NONE'
            # debug
            pprint(result)

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
    symbol(str) : 'BTC/USD'
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

is_line_notified = 1

"""
while(1):
    line_notify_time_hour = flag['param']['line_notify_time_hour']

    # 稼働状況をLINE通知
    time.sleep(1)

    dt = datetime.now()
    print('{}:{}:{}>'.format(dt.hour,dt.minute,dt.second))

    # 通知時間で初回なら
    for i in range(len(line_notify_time_hour)):
        if (line_notify_time_hour[i] == dt.second) and (is_line_notified == 1):
            is_line_notified = 0

    if is_line_notified == 0:
        # LINE通知メッセージ作成
        result_pos = get_position()
        result_col = get_collateral()
        #line_text =  "\n時間： " + str(datetime.fromtimestamp(new_price["close_time"]).strftime('%Y/%m/%d %H:%M')) + "\n高値： " + str(new_price["high_price"]) + "\n安値： " + str(new_price["low_price"]) + "\n終値： " + str(new_price["close_price"]) + "\n"
        #line_text = line_text + "\nポジション:{}\nロット:{}\n拘束中証拠金:{}\n使用可能証拠金:{}\n".format(result_pos["side"],result_pos["lots"],round(result_col["used"],4),round(result_col["free"],4))
        # 現在の時間、ポジション数、証拠金
        line_notify(dt)
        is_line_notified = 1
"""

bybit_test()

#EOF