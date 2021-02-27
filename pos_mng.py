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
def get_price(min, flag, before=0, after=0):
	wait = flag["param"]["wait"]
	price = []
	params = {"periods" : min }
	if before != 0:
		params["before"] = before
	if after != 0:
		params["after"] = after

	while True:
		try:
			response = requests.get("https://api.cryptowat.ch/markets/binance/btcusdt/ohlc", params, timeout = 5)
			response.raise_for_status()
			data = response.json()
			break
		except requests.exceptions.RequestException as e:
			log = "Cryptowatchの価格取得でエラー発生 : " + str(e)
			out_log(log, flag)
			out_log("{0}秒待機してやり直します".format(wait), flag)
			time.sleep(wait)

	if data["result"][str(min)] is not None:
		for i in data["result"][str(min)]:
			if i[1] != 0 and i[2] != 0 and i[3] != 0 and i[4] != 0:
				price.append({ "close_time" : i[0],
					"close_time_dt" : datetime.fromtimestamp(i[0]).strftime('%Y/%m/%d %H:%M'),
					"open_price" : i[1],
					"high_price" : i[2],
					"low_price" : i[3],
					"close_price": i[4] })
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


#-------------資金管理の関数--------------


# 複数回に分けて追加ポジションを取る関数
def add_position( data,last_data,flag ):
	is_back_test = flag["param"]["is_back_test"]
	entry_times = flag["param"]["entry_times"]
	entry_range = flag["param"]["entry_range"]
	slippage = flag["param"]["slippage"]
	symbol_type = flag["param"]["symbol_type"]

	#out_log("#-------------add_position start----------------\n", flag)
	# ポジションがない場合は何もしない
	if flag["position"]["exist"] == False:
		#out_log("#-------------add_position end----------------\n", flag)
		return flag

	# 最初（１回目）のエントリー価格を記録
	if flag["add-position"]["count"] == 0:
		flag["add-position"]["first-entry-price"] = flag["position"]["price"]
		flag["add-position"]["last-entry-price"] = flag["position"]["price"]
		flag["add-position"]["count"] += 1

	while True:

		# 以下の場合は、追加ポジションを取らない
		if flag["add-position"]["count"] >= entry_times:
			#out_log("#-------------add_position end----------------\n", flag)
			return flag

		# この関数の中で使う変数を用意
		first_entry_price = flag["add-position"]["first-entry-price"]
		last_entry_price = flag["add-position"]["last-entry-price"]
		unit_range = flag["add-position"]["unit-range"]
		current_price = data["close_price"]


		# 価格がエントリー方向に基準レンジ分だけ進んだか判定する
		should_add_position = False
		if flag["position"]["side"] == "BUY" and (current_price - last_entry_price) > unit_range:
			should_add_position = True
		elif flag["position"]["side"] == "SELL" and (last_entry_price - current_price) > unit_range:
			should_add_position = True
		else:
			break

		# 基準レンジ分進んでいれば追加注文を出す
		if should_add_position == True:
			out_log("前回のエントリー価格{0}USDからブレイクアウトの方向に{1}ATR（{2}USD）以上動きました\n".format( last_entry_price, entry_range, round( unit_range ) ), flag)
			out_log("{0}/{1}回目の追加注文を出します\n".format(flag["add-position"]["count"] + 1, entry_times), flag)

			# 注文サイズを計算
			lot,stop,flag = calculate_lot( last_data,data,flag )
			min_lot = round(calc_min_lot( data, flag ), 7)
			if lot < min_lot:
				out_log("注文可能枚数{}が、最低注文単位{}に満たなかったので注文を見送ります\n".format(lot, min_lot), flag)
				flag["add-position"]["count"] += 1
				#out_log("#-------------add_position end----------------\n", flag)
				return flag

			# 追加注文を出す
			if flag["position"]["side"] == "BUY":
				#entry_price = first_entry_price + (flag["add-position"]["count"] * unit_range) 2020/1/9 fix
				entry_price = data["close_price"]
				if is_back_test is True:
					entry_price = round((1 + slippage) * entry_price)

				out_log("現在のポジションに追加して、{0}USDで{1}lotの買い注文を出します\n".format(entry_price,lot), flag)
				order_lot, flag = lot_to_amount(data, lot, flag)

				# ここに買い注文のコードを入れる
				create_order(
					flag,
					symbol = symbol_type,
					type='Market',
					side='Buy',
					amount=order_lot)
				flag["order"]["exist"] = True
				flag["order"]["side"] = "BUY"

			if flag["position"]["side"] == "SELL":
				entry_price = data["close_price"]
				if is_back_test is True:
					entry_price = round((1 - slippage) * entry_price)

				out_log("現在のポジションに追加して、{0}USDで{1}lotの売り注文を出します\n".format(entry_price,lot), flag)
				order_lot, flag = lot_to_amount(data, lot, flag)

				# ここに売り注文のコードを入れる
				create_order(
					flag,
					symbol = symbol_type,
					type='Market',
					side='Sell',
					amount=order_lot)
				flag["order"]["exist"] = True
				flag["order"]["side"] = "SELL"

			# ポジション全体の情報を更新する
			new_position_price = int(round(( flag["position"]["price"] * flag["position"]["lot"] + entry_price * lot ) / ( flag["position"]["lot"] + lot )))
			#new_lot = np.round( (flag["position"]["lot"] + lot) * 100 ) / 100
			new_lot = round( ( ( (flag["position"]["lot"] + lot) * 100 ) / 100 ), 7 )
			# stopをSMAで計算する
			#new_stop, flag = calc_stop( data, flag )
			new_stop = stop
			flag["position"]["stop"] = new_stop
			flag["position"]["price"] = new_position_price
			flag["position"]["lot"] = new_lot

			if flag["position"]["side"] == "BUY":
				out_log("{0}USDの位置にストップを更新します\n".format(flag["position"]["price"] - new_stop), flag)
			elif flag["position"]["side"] == "SELL":
				out_log("{0}USDの位置にストップを更新します\n".format(flag["position"]["price"] + new_stop), flag)
			out_log("現在のポジションの取得単価は{}USDです\n".format(flag["position"]["price"]), flag)
			out_log("現在のポジションサイズは{}lotです\n".format(flag["position"]["lot"]), flag)

			flag["add-position"]["count"] += 1
			flag["add-position"]["last-entry-price"] = entry_price

	#out_log("#-------------add_position end----------------\n", flag)
	return flag

# エントリー注文を出す関数
def entry_signal( data, last_data, flag ):
	symbol_type = flag["param"]["symbol_type"]
	#out_log("#-------------entry_signal start----------------\n", flag)
	signal = check_signal( data, last_data, flag )

	if signal["side"] == "BUY":

		lot,stop,flag = calculate_lot( last_data,data,flag )
		min_lot = round(calc_min_lot( data, flag ), 7)
		#print("lot, {} min_lot {} \n".format(lot, min_lot))

		if lot >= min_lot:
			vola_check = check_volatility( data, last_data, flag )
			if vola_check == False:
				out_log("ボラティリティが閾値を下回っていないのでで注文を見送ります\n", flag)
			else:
				out_log("{0}USDで{1}lotの買い注文を出します\n".format(data["close_price"],lot), flag)
				order_lot, flag = lot_to_amount(data, lot, flag)

				# ここに買い注文のコードを入れる
				create_order(
					flag,
					symbol = symbol_type,
					type='Market',
					side='Buy',
					amount=order_lot)
				flag["order"]["exist"] = True
				flag["order"]["side"] = "BUY"

				# stopを計算する
				#new_stop, flag = calc_stop( data, flag )
				new_stop = stop

				out_log("{0}USDにストップを入れます\n".format(data["close_price"] - new_stop), flag)
				flag["position"]["lot"],flag["position"]["stop"] = lot,new_stop
				flag["position"]["exist"] = True
				flag["position"]["side"] = "BUY"
				flag["position"]["price"] = data["close_price"]
		else:
			out_log("注文可能枚数{}が、最低注文単位{}に満たなかったので注文を見送ります\n".format(lot, min_lot), flag)

	if signal["side"] == "SELL":

		lot,stop,flag = calculate_lot( last_data,data,flag )
		min_lot = round(calc_min_lot( data, flag ), 7)
		if lot >= min_lot:
			vola_check = check_volatility( data, last_data, flag )
			if vola_check == False:
				out_log("ボラティリティが閾値を下回っていないのでで注文を見送ります\n", flag)
			else:
				out_log("{0}USDで{1}lotの売り注文を出します\n".format(data["close_price"],lot), flag)
				order_lot, flag = lot_to_amount(data, lot, flag)

				# ここに売り注文のコードを入れる
				create_order(
					flag,
					symbol = symbol_type,
					type='Market',
					side='Sell',
					amount=order_lot)
				flag["order"]["exist"] = True
				flag["order"]["side"] = "SELL"

				# stopを計算する
				#new_stop, flag = calc_stop( data, flag )
				new_stop = stop

				out_log("{0}USDにストップを入れます\n".format(data["close_price"] + new_stop), flag)
				flag["position"]["lot"],flag["position"]["stop"] = lot,new_stop
				flag["position"]["exist"] = True
				flag["position"]["side"] = "SELL"
				flag["position"]["price"] = data["close_price"]
		else:
			out_log("注文可能枚数{}が、最低注文単位{}に満たなかったので注文を見送ります\n".format(lot, min_lot), flag)
	#out_log("#-------------entry_signal end----------------\n", flag)

	return flag



# 手仕舞いのシグナルが出たら決済の成行注文 + ドテン注文 を出す関数
# ドテン注文は外す
def close_position( data,last_data,flag ):
	is_back_test = flag["param"]["is_back_test"]
	symbol_type = flag["param"]["symbol_type"]
	stop_AF = flag["param"]["stop_AF"]
	#out_log("#-------------close_position start----------------\n", flag)
	if flag["position"]["exist"] == False:
		#out_log("#-------------close_position end----------------\n", flag)
		return flag

	flag["position"]["count"] += 1
	signal = check_signal( data,last_data,flag )

	if flag["position"]["side"] == "BUY":
		if signal["side"] == "SELL":
			out_log(str(data["close_price"]) + "USDあたりで成行注文を出してポジションを決済します\n", flag)

			# 決済の成行注文コードを入れる
			if is_back_test is True:
				result = {}
				result["side"] = flag["position"]["side"]
				result["lots"] = flag["position"]["lot"] * data["close_price"]
			else:
				result = get_position(flag)

			if (result["side"] == "BUY") and (result["lots"] > 0):
				create_order(
					flag,
					symbol = symbol_type,
					type='Market',
					side='Sell',
					amount=result["lots"])
				flag["order"]["exist"] = True
				flag["order"]["side"] = "SELL"

			# 約定時の値を入れる。-10usdくらいずれる

			records( flag,data,data["close_price"] )
			flag["position"]["exist"] = False
			flag["position"]["count"] = 0
			flag["position"]["stop-AF"] = stop_AF
			flag["position"]["stop-EP"] = 0
			flag["add-position"]["count"] = 0

			""" ドテン外し
			lot,stop,flag = calculate_lot( last_data,data,flag )
			min_lot = round(calc_min_lot( data, flag ), 7)
			if lot >= min_lot:
				out_log("{0}USDで{1}lotの売りの注文を入れてドテンします\n".format(data["close_price"],lot), flag)
				order_lot, flag = lot_to_amount(data, lot, flag)

				# ここに売り注文のコードを入れる
				create_order(
					flag,
					symbol = symbol_type,
					type='Market',
					side='Sell',
					amount=order_lot)
				flag["order"]["exist"] = True
				flag["order"]["side"] = "SELL"

				out_log("{0}USDにストップを入れます\n".format(data["close_price"] + stop), flag)
				flag["position"]["lot"],flag["position"]["stop"] = lot,stop
				flag["position"]["exist"] = True
				flag["position"]["side"] = "SELL"
				flag["position"]["price"] = data["close_price"]
			"""

	if flag["position"]["side"] == "SELL":
		if signal["side"] == "BUY":
			out_log(str(data["close_price"]) + "USDあたりで成行注文を出してポジションを決済します\n", flag)

			# 決済の成行注文コードを入れる
			if is_back_test is True:
				result = {}
				result["side"] = flag["position"]["side"]
				result["lots"] = flag["position"]["lot"] * data["close_price"]
			else:
				result = get_position(flag)

			if (result["side"] == "SELL") and (result["lots"] > 0):
				create_order(
					flag,
					symbol = symbol_type,
					type='Market',
					side='Buy',
					amount=result["lots"])
				flag["order"]["exist"] = True
				flag["order"]["side"] = "BUY"

			# 約定時の値を入れる。-10usdくらいずれる

			records( flag,data,data["close_price"] )
			flag["position"]["exist"] = False
			flag["position"]["count"] = 0
			flag["position"]["stop-AF"] = stop_AF
			flag["position"]["stop-EP"] = 0
			flag["add-position"]["count"] = 0

			""" ドテン外し
			lot,stop,flag = calculate_lot( last_data,data,flag )
			min_lot = round(calc_min_lot( data, flag ), 7)
			if lot >= min_lot:
				out_log("{0}USDで{1}lotの買いの注文を入れてドテンします\n".format(data["close_price"],lot), flag)
				order_lot, flag = lot_to_amount(data, lot, flag)

				# ここに買い注文のコードを入れる
				create_order(
					flag,
					symbol = symbol_type,
					type='Market',
					side='Buy',
					amount=order_lot)
				flag["order"]["exist"] = True
				flag["order"]["side"] = "BUY"

				out_log("{0}USDにストップを入れます\n".format(data["close_price"] - stop), flag)
				flag["position"]["lot"],flag["position"]["stop"] = lot,stop
				flag["position"]["exist"] = True
				flag["position"]["side"] = "BUY"
				flag["position"]["price"] = data["close_price"]
			"""

	#out_log("#-------------close_position end----------------\n", flag)
	return flag



# 損切ラインにかかったら成行注文で決済する関数
def stop_position( data,last_data,flag ):
	is_back_test = flag["param"]["is_back_test"]
	chart_sec = flag["param"]["chart_sec"]
	symbol_type = flag["param"]["symbol_type"]
	stop_AF = flag["param"]["stop_AF"]
	#out_log("#-------------stop_position start----------------\n", flag)
	# トレイリングストップを実行 ＞ トレイリングストップはポジションありの場合のみ実施のため
	# stop_position前に移動する
	#flag = trail_stop( data,flag )

	if flag["position"]["side"] == "BUY":
		stop_price = flag["position"]["price"] - flag["position"]["stop"]
		if data["low_price"] < stop_price:
			out_log("{0}USDの損切ラインを最安値{1}が割り込んだため決済します。\n".format( stop_price, data["low_price"] ), flag)
			stop_price = round( stop_price - 2 * calculate_volatility(last_data, flag) / ( chart_sec / 60))
			#out_log(str(stop_price) + "USDあたりで成行注文を出してポジションを決済します\n", flag)

			# 決済の成行注文コードを入れる

			if is_back_test is True:
				result = {}
				result["side"] = flag["position"]["side"]
				result["lots"] = flag["position"]["lot"] * data["low_price"]
			else:
				result = get_position(flag)

			if (result["side"] == "BUY") and (result["lots"] > 0):
				create_order(
					flag,
					symbol = symbol_type,
					type='Market',
					side='Sell',
					amount=result["lots"])
				flag["order"]["exist"] = True
				flag["order"]["side"] = "SELL"

			# stop値ではなく最安値を値を入れる。

			records( flag,data,data["low_price"],"STOP" )
			flag["position"]["exist"] = False
			flag["position"]["count"] = 0
			flag["position"]["stop-AF"] = stop_AF
			flag["position"]["stop-EP"] = 0
			flag["add-position"]["count"] = 0


	if flag["position"]["side"] == "SELL":
		stop_price = flag["position"]["price"] + flag["position"]["stop"]
		if data["high_price"] > stop_price:
			out_log("{0}USDの損切ラインを最高値{1}が超過したため決済します。\n".format( stop_price, data["high_price"] ), flag)
			stop_price = round( stop_price + 2 * calculate_volatility(last_data, flag) / (chart_sec / 60) )
			#out_log(str(stop_price) + "USDあたりで成行注文を出してポジションを決済します\n", flag)

			# 決済の成行注文コードを入れる
			if is_back_test is True:
				result = {}
				result["side"] = flag["position"]["side"]
				result["lots"] = flag["position"]["lot"] * data["high_price"]
			else:
				result = get_position(flag)

			if (result["side"] == "SELL") and (result["lots"] > 0):
				create_order(
					flag,
					symbol = symbol_type,
					type='Market',
					side='Buy',
					amount=result["lots"])
				flag["order"]["exist"] = True
				flag["order"]["side"] = "BUY"

			# stop値ではなく約定時の値を入れる。

			records( flag,data,data["high_price"],"STOP" )
			flag["position"]["exist"] = False
			flag["position"]["count"] = 0
			flag["position"]["stop-AF"] = stop_AF
			flag["position"]["stop-EP"] = 0
			flag["add-position"]["count"] = 0

	#out_log("#-------------stop_position end----------------\n", flag)
	return flag
