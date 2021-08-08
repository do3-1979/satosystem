from datetime import datetime
import time
from pprint import pprint

# -------パラメータ------
from param import *
# -------資金管理機能--------
from pos_mng import *
# -------主制御----------
from daemon import daemon
# -------バックテスト機能-----
from backtest import backtest

#------------ここからメイン処理--------------

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
		"vroc_term":vroc_term,
		"vroc_thrsh":vroc_thrsh,
	    "judge_line":judge_line,
	    "judge_price":judge_price,
	    "judge_signal":judge_signal,
		"judge_volatility_ratio":judge_volatility_ratio,
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

# チャートを取得
chart_log = {
	"records":{
		"date":[],
		"close_price":[],
		"position_price":[],
		"stop_price":[],
		"price_ohlc":[],
		"Volume":[],
		"QuoteVolume":[],
		"volatility":[],
		"donchian_h":[],
		"donchian_l":[],
		"PIVOT":[],
		"R3":[],
		"R2":[],
		"R1":[],
		"S1":[],
		"S2":[],
		"S3":[],
		"SMA1":[],
		"SMA2":[],
		"vroc":[],
		"vroc_thrsh":[]
	},
}

if is_back_test is True:
	#file_path = "../price_data/price_btcusd_" + str(chart_sec) + ".json"
	#price = get_price_from_file(chart_sec, file_path, flag, start_period, end_period)
	price_tmp = get_price(chart_sec,flag,after=1451606400)

	start_unix = 0
	end_unix = 9999999999

	if start_period:
		start_period = datetime.strptime(start_period,"%Y/%m/%d %H:%M")
		start_unix = int(start_period.timestamp())
	if end_period:
		end_period = datetime.strptime( end_period,"%Y/%m/%d %H:%M")
		end_unix = int(end_period.timestamp())

	price = []

	for i in range( len(price_tmp) ):
		unix_time = price_tmp[i]["close_time"]
		if ( start_unix < unix_time ) and ( end_unix > unix_time ):
			price.append(price_tmp[i])

else:
	price = get_price(chart_sec,flag,after=1451606400)

last_data = []
need_term = max(buy_term,sell_term,volatility_term,pivot_term,sma1_term,sma2_term,vroc_term)

#-------- メインループ(バックテストでは抜ける) ---------
daemon( price, last_data, flag, need_term, chart_log )

print("-----------------------------------")
print("期間                : " + str(price[0]["close_time_dt"]) + "～" + str(price[-1]["close_time_dt"]))
print("時間軸              : " + str(int(chart_sec/60)) + "分足で検証")
print("パラメータ１～２    : " + str(buy_term)  + "期間 / 買い " + str(sell_term) + "期間 / 売り" )
print("パラメータ３        : " + str(pivot_term) + "期間 / PIVOT" )
print("パラメータ４        : " + str(volatility_term)  + "期間" )
print("パラメータ５        : " + str(stop_range) + "ストップレンジ" )
print("パラメータ６        : " + str(trade_risk) + "％" )
print("パラメータ７～８    : " + str(entry_times) + "分割 " + str(entry_range) + "追加ポジション" )
print("パラメータ９～１１  : " + str(stop_AF) + "加速係数 " + str(stop_AF_add) + "増加度 " + str(stop_AF_max) + "上限" )
print("パラメータ１２      : " + str(lot_limit_lower) + "注文lot数の下限" )
print(str(len(price)) + "件のローソク足データで検証")
print("-----------------------------------")

backtest(flag, last_data, chart_log)
