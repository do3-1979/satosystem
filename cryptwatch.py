import requests
from datetime import datetime
import time

import json

# -------ログ機能--------
from logc import *
# -------オーダー機能----
from order import *
# -------解析機能--------
from anlyz import *

# CryptowatchのAPIを使用する関数
def get_ohlcv(flag, before=0, after=0):
	wait = flag["param"]["wait"]
	price = []
	min = flag["param"]["chart_sec"]
	params = {"periods" : min }
	symbol_type = flag["param"]["symbol_type"]
	allowance_remaining = 0

	is_line_ntfied = False

	if before != 0:
		params["before"] = before
	if after != 0:
		params["after"] = after

	while True:
		try:
			if symbol_type == 'BTC/USD':
				response = requests.get("https://api.cryptowat.ch/markets/binance/btcusdt/ohlc", params, timeout = 5)
			elif symbol_type == 'ETH/USD':
				response = requests.get("https://api.cryptowat.ch/markets/binance/ethusdt/ohlc", params, timeout = 5)
			response.raise_for_status()
			data = response.json()
			break
		except requests.exceptions.RequestException as e:
			log = "Cryptowatchの価格取得でエラー発生 : " + str(e)
			out_log(log, flag)
			out_log("{0}秒待機してやり直します".format(wait), flag)
			if is_line_ntfied == False:
				line_notify(log)
				is_line_ntfied = True
			time.sleep(wait)

	if is_line_ntfied == True:
		line_notify("Cryptowatchの価格取得 復帰")

	# API残credit取得
	allowance_remaining = data["allowance"]["remaining"]

	if data["result"][str(min)] is not None:
		for i in data["result"][str(min)]:
			if i[1] != 0 and i[2] != 0 and i[3] != 0 and i[4] != 0 and i[5] != 0 and i[6] != 0:
				price.append({ "close_time" : i[0],
					"close_time_dt" : datetime.fromtimestamp(i[0]).strftime('%Y/%m/%d %H:%M'),
					"open_price" : i[1],
					"high_price" : i[2],
					"low_price" : i[3],
					"close_price": i[4],
					"Volume" : i[5],
					"QuoteVolume" : i[6],
					"allowance_remaining" : allowance_remaining})
		return price

	else:
		out_log("データが存在しません", flag)
		return None

def get_last_ohlcv(flag, before=0, after=0):
	wait = flag["param"]["wait"]
	price = []
	min = flag["param"]["chart_sec"]
	params = {"periods" : min }
	symbol_type = flag["param"]["symbol_type"]
	allowance_remaining = 0

	is_line_ntfied = False

	if before != 0:
		params["before"] = before
	if after != 0:
		params["after"] = after

	while True:
		try:
			if symbol_type == 'BTC/USD':
				response = requests.get("https://api.cryptowat.ch/markets/binance/btcusdt/summary", params, timeout = 5)
			elif symbol_type == 'ETH/USD':
				response = requests.get("https://api.cryptowat.ch/markets/binance/ethusdt/summary", params, timeout = 5)
			response.raise_for_status()
			data = response.json()
			break
		except requests.exceptions.RequestException as e:
			log = "Cryptowatchのlatest価格取得でエラー発生 : " + str(e)
			out_log(log, flag)
			out_log("{0}秒待機してやり直します".format(wait), flag)
			if is_line_ntfied == False:
				line_notify(log)
				is_line_ntfied = True
			time.sleep(wait)

	if is_line_ntfied == True:
		line_notify("Cryptowatchのlatest価格取得 復帰")

	# API残credit取得
	allowance_remaining = data["allowance"]["remaining"]

	if data["result"]["price"] is not None:
		if data["result"]["price"]["last"] != 0:
			last_price = data["result"]["price"]["last"]
			price.append({ "close_time" : round(time.time()),
			"close_time_dt" : datetime.now().strftime('%Y/%m/%d %H:%M'),
			"open_price" : last_price,
			"high_price" : last_price,
			"low_price" : last_price,
			"close_price": last_price,
			"Volume" : 0,
			"QuoteVolume" : 0,
			"allowance_remaining" : allowance_remaining})
			return price
		else:
			out_log("データが存在しません", flag)
			return None


# 価格ファイルからローソク足データを読み込む関数
def get_price_from_file( min, path,flag,start_period = None, end_period = None ):
	file = open(path,"r",encoding="utf-8")
	data = json.load(file)

	start_unix = 0
	end_unix = 9999999999

	if start_period:
		start_period = datetime.strptime(start_period,"%Y/%m/%d %H:%M")
		start_unix = int(start_period.timestamp())
	if end_period:
		end_period = datetime.strptime( end_period,"%Y/%m/%d %H:%M")
		end_unix = int(end_period.timestamp())

	price = []
	for i in data["result"][str(min)]:
		if i[0] >= start_unix and i[0] <= end_unix:
			if i[1] != 0 and i[2] != 0 and i[3] != 0 and i[4] != 0:
				price.append({ "close_time" : i[0],
					"close_time_dt" : datetime.fromtimestamp(i[0]).strftime('%Y/%m/%d %H:%M'),
					"open_price" : i[1],
					"high_price" : i[2],
					"low_price" : i[3],
					"close_price": i[4] })

	return price

# EOF