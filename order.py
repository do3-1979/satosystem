import ccxt
import config_rt
#import config
import time

# -------ログ機能--------
from logc import *

bybit = ccxt.bybit()		  # 取引所の定義
bybit.apiKey = config_rt.apiKey # APIキーを設定
bybit.secret = config_rt.secret # APIシークレットを設定

#------------注文を管理する関数--------------

# 売買注文の約定確認を行う関数
def create_order( flag, symbol, type, side, amount, price=None ):
	is_back_test = flag["param"]["is_back_test"]
	order_retry_times = flag["param"]["order_retry_times"]
	wait = flag["param"]["wait"]
	is_line_ntfied = False
	"""
	引数
	symbol(str) : 'BTC/USD'
	type(str) : 'Limit' -> 指値　/ 'Market' -> 成行
	side(str) : 'Buy' -> 買い / 'Sell' -> 売り
	amount(float/int) -> 注文枚数
	price(float/int) -> 注文価格(成行の場合は省略可)
	"""
	if is_back_test is True:
		return 0

	while True:
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
			log = "create_orderでエラー発生 : " + str(e)
			out_log(log, flag)
			out_log("注文の通信が失敗しました。{0}秒後に再トライします\n".format(wait*order_retry_times), flag)
			if is_line_ntfied == False:
				line_notify(log)
				is_line_ntfied = True
			time.sleep(wait*order_retry_times)

	if is_line_ntfied == True:
		line_notify("create_orderでエラー復帰")

	return create_order

# 売買注文の約定確認を行う関数
def check_order(flag):
	is_back_test = flag["param"]["is_back_test"]
	order_retry_times = flag["param"]["order_retry_times"]
	wait = flag["param"]["wait"]
	"""
	引数 : なし
	戻り値 : 未約定の注文ID
	"""
	if is_back_test is True:
		return 0

	while True:
		try:
			out_log("約定を確認します\n", flag)

			orders = []
			order_id = []
			len_orders = 0
			orders = bybit.fetch_open_orders()

			if len(orders) > 0:
				len_orders = len(orders)
				out_log("ID = {0} が残っています\n".format(len_orders), flag)

				for i in orders:
					order_id.append(i['info']['orderID'])

			elif orders == []:
				out_log("残っている注文はありません\n", flag)
				order_id = 0

			return order_id

		except ccxt.BaseError as e:
			out_log("bybitのAPIでエラー発生 = {0}\n".format(e), flag)
			out_log("売買注文の約定確認が失敗しました。{0}秒後に再トライします\n".format(wait*order_retry_times), flag)
			time.sleep(wait*order_retry_times)

# 売買注文のキャンセルを行う関数
def cancel_order(order_id, flag):
	order_retry_times = flag["param"]["order_retry_times"]
	wait = flag["param"]["wait"]
	"""
	引数 : なし
	戻り値 : キャンセルの結果（全部成功=1、それ以外=0）
	"""
	while True:
		try:
			out_log("オーダーキャンセル実施\n", flag)

			cancel_order = []

			if order_id != 0:
				for i in order_id:
					cancel_result = bybit.cancel_order(i)
					cancel_order.append(cancel_result['info']['ordStatus'])


			return cancel_order

		except ccxt.BaseError as e:
			out_log("bybitのAPIでエラー発生 = {0}\n".format(e), flag)
			out_log("売買注文キャンセルが失敗しました。{0}秒後に再トライします\n".format(wait*order_retry_times), flag)
			time.sleep(wait*order_retry_times)

# 口座残高を取得する関数
def get_collateral(flag):
	order_retry_times = flag["param"]["order_retry_times"]
	wait = flag["param"]["wait"]
	is_line_ntfied = False
	result = {}
	"""
	引数 : なし
	戻り値
		result['total'] # 証拠金総額
		result['used'] # 拘束中証拠金
		result['free'] # 使用可能証拠金
	"""

	while True:

		try:
			# 口座残高を取得
			collateral = bybit.fetchBalance()

			# 総額
			result['total'] = collateral['total']['BTC']
			# 拘束中
			result['used'] = collateral['used']['BTC']
			# 使用可能
			result['free'] = collateral['free']['BTC']
			break

		except ccxt.BaseError as e:
			log = "get_collateralでエラー発生 : " + str(e)
			out_log(log, flag)
			out_log("口座残高取得が失敗しました。{0}秒後に再トライします\n".format(wait*order_retry_times), flag)
			if is_line_ntfied == False:
				line_notify(log)
				is_line_ntfied = True
			time.sleep(wait*order_retry_times)

	if is_line_ntfied == True:
		line_notify("get_collateralでエラー復帰")

	return result

# ポジション情報を取得する関数
def get_position(flag):
	order_retry_times = flag["param"]["order_retry_times"]
	wait = flag["param"]["wait"]
	symbol_type = flag["param"]["symbol_type"]
	is_line_ntfied = False
	result = {}
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
		symbol = 'BTCUSD' # symbolはPrivate命令では/を除く。
	else:
		symbol = 'None'

	while True:
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
			break
		except ccxt.BaseError as e:
			log = "get_positionでエラー発生 : " + str(e)
			out_log(log, flag)
			out_log("ポジション情報取得が失敗しました。{0}秒後に再トライします\n".format(wait*order_retry_times), flag)
			if is_line_ntfied == False:
				line_notify(log)
				is_line_ntfied = True
			time.sleep(wait*order_retry_times)

	if is_line_ntfied == True:
		line_notify("get_positionでエラー復帰")

	return result
