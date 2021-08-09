from logging import getLogger,Formatter,StreamHandler,FileHandler,INFO
from datetime import datetime
import time
import requests
import config_rt

logger = getLogger(__name__)
handlerSh = StreamHandler()
handlerFile = FileHandler(config_rt.log_file_name) # ログファイルの出力先とファイル名を指定
handlerSh.setLevel(INFO)
handlerFile.setLevel(INFO)
logger.setLevel(INFO)
logger.addHandler(handlerSh)
logger.addHandler(handlerFile)


#-------------補助ツールの関数--------------

def out_log(log_msg, flag):
	# パラメタ展開
	is_total_test = flag["param"]["is_total_test"]

	# print出力 ※logger .infoなら要らない
	# print(log_msg.strip("\n"))

	if is_total_test == False:
		# ログ出力
		logger.info(log_msg.strip("\n"))

	# ファイル出力
	flag["records"]["log"].append(log_msg)

# LINEに通知する関数
def line_notify( text ):
	url = "https://notify-api.line.me/api/notify"
	data = {"message" : text}
	headers = {"Authorization": "Bearer " + config_rt.line_token}
	requests.post(url, data=data, headers=headers)

def out_log_with_line(log_msg, flag):
	# パラメタ展開
	is_back_test = flag["param"]["is_back_test"]
	is_total_test = flag["param"]["is_total_test"]

	# print出力 ※logger .infoなら要らない
	# print(log_msg.strip("\n"))

	if is_total_test == False:
		# ログ出力
		logger.info(log_msg.strip("\n"))

	# LINE通知
	if is_back_test is False:
		line_notify("\n" + log_msg)

	# ファイル出力
	flag["records"]["log"].append(log_msg)

# 時間と高値・安値をログに記録する関数
def log_price( data, flag ):
	log =  "時間： " + str(datetime.fromtimestamp(data["close_time"]).strftime('%Y/%m/%d %H:%M')) + \
			" 高値： " + str(data["high_price"]) + \
			" 安値： " + str(data["low_price"]) + \
			" 終値： " + str(data["close_price"]) +\
			" 出来高： " + str(round(data["Volume"])) + "\n"
	out_log(log, flag)
	return flag

# 各トレードのパフォーマンスを記録する関数
def records(flag,data,close_price,close_type=None):
	slippage = flag["param"]["slippage"]
	# 取引手数料等の計算
	entry_price = int(round(flag["position"]["price"] * flag["position"]["lot"]))
	exit_price = int(round(close_price * flag["position"]["lot"]))
	"""
	out_log("position_price = {}\n".format(flag["position"]["price"]), flag)
	out_log("lot            = {}\n".format(flag["position"]["lot"]), flag)
	out_log("entry_price    = {}\n".format(entry_price), flag)
	out_log("close_price    = {}\n".format(close_price), flag)
	out_log("exit_price     = {}\n".format(exit_price), flag)
	"""
	trade_cost = round( exit_price * slippage )
	log = "スリッページ・手数料として " + str(round( trade_cost, 4)) + "USDを考慮します\n"
	out_log(log, flag)

	flag["records"]["slippage"].append(trade_cost)

	# 手仕舞った日時と保有期間を記録
	flag["records"]["date"].append(data["close_time_dt"])
	flag["records"]["holding-periods"].append( flag["position"]["count"] )

	# 損切りにかかった回数をカウント
	if close_type == "STOP":
		flag["records"]["stop-count"].append(1)
	else:
		flag["records"]["stop-count"].append(0)

	# 値幅の計算
	buy_profit = exit_price - entry_price - trade_cost
	sell_profit = entry_price - exit_price - trade_cost

	# 利益が出てるかの計算
	if flag["position"]["side"] == "BUY":
		flag["records"]["side"].append( "BUY" )
		flag["records"]["profit"].append( buy_profit )
		flag["records"]["return"].append( round( buy_profit / entry_price * 100, 4 ))
		#out_log("before_funds = {}\n".format(flag["records"]["funds"]), flag)
		flag["records"]["funds"] = flag["records"]["funds"] + buy_profit
		#out_log("after_funds = {}\n".format(flag["records"]["funds"]), flag)
		if buy_profit  > 0:
			log = str(buy_profit) + "USDの利益です\n"
		else:
			log = str(buy_profit) + "USDの損失です\n"
		out_log_with_line(log, flag)

	if flag["position"]["side"] == "SELL":
		flag["records"]["side"].append( "SELL" )
		flag["records"]["profit"].append( sell_profit )
		flag["records"]["return"].append( round( sell_profit / entry_price * 100, 4 ))
		#out_log("before_funds = {}\n".format(flag["records"]["funds"]), flag)
		flag["records"]["funds"] = flag["records"]["funds"] + sell_profit
		#out_log("after_funds = {}\n".format(flag["records"]["funds"]), flag)
		if sell_profit > 0:
			log = str(sell_profit) + "USDの利益です\n"
		else:
			log = str(sell_profit) + "USDの損失です\n"
		out_log_with_line(log, flag)

	return flag
