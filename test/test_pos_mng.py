from param import *
from pos_mng import get_price,get_latest_price
from datetime import datetime
import json

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
		"pvo_s_term":pvo_s_term,
		"pvo_l_term":pvo_l_term,
		"pvo_thrsh":pvo_thrsh,
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
		"stop_neighbor":stop_neighbor,
		"line_notify_time_hour":line_notify_time_hour,
		"line_notify_profit_rate":line_notify_profit_rate
	}
}

def test_get_price():
	start_period = "2023/8/1 0:00"
	end_period = "2023/9/1 21:00"

	if start_period:
		start_period = datetime.strptime(start_period,"%Y/%m/%d %H:%M")
		start_unix = int(start_period.timestamp())
	if end_period:
		end_period = datetime.strptime( end_period,"%Y/%m/%d %H:%M")
		end_unix = int(end_period.timestamp())

	### 開始・終了指定
	file = open("/home/satoshi/work/satosystem/test/test_data/price_data.json","r",encoding="utf-8")
	price_data = json.load(file)

	assert get_price(flag, start_unix, end_unix) == price_data

def test_get_latest_price():

	### 2h足(7200)
	expect_hour_list = [1,3,5,7,9,11,13,15,17,19,21,23,24]

	# 現在の期待する終値を特定
	now_time = datetime.now()
	for i in range(len(expect_hour_list)-1):
		if (now_time.hour >= expect_hour_list[i]) and \
		   (now_time.hour < expect_hour_list[i+1]) :
			expect_hour = expect_hour_list[i]
			print(f"i : {i} now_time.hour: {now_time.hour} expect_hour_list[{i}]: {expect_hour_list[i]}")

	# データ取得
	data7200 = get_latest_price(flag, 7200)
	latest_close_time = datetime.fromtimestamp( data7200[-1]["close_time"] )

	print(f"int(expect_hour){int(expect_hour)} int(latest_close_time.hour){int(latest_close_time.hour)}")

	assert expect_hour == latest_close_time.hour

	### 1分足(60)
	# 取得した時刻の分が最新値と一致する
	data60 = get_latest_price(flag, 60)
	print(data60)

	now_time = datetime.now()
	latest_close_time = datetime.fromtimestamp( data60[-1]["close_time"] )

	assert now_time.minute == latest_close_time.minute