import numpy as np

# -------ログ機能--------
from logc import *
# -------オーダー機能----
from order import get_collateral

# 平均ボラティリティを計算する関数
def calculate_volatility( last_data, flag ):
	volatility_term = flag["param"]["volatility_term"]
	log_unit = flag["param"]["log_unit"]
	high_sum = sum(i["high_price"] for i in last_data[-1 * volatility_term :])
	low_sum	 = sum(i["low_price"]  for i in last_data[-1 * volatility_term :])
	volatility = round((high_sum - low_sum) / volatility_term)
	out_log("現在の{0}期間の平均ボラティリティは{1}{2}です\n".format( volatility_term, volatility, log_unit ), flag)
	return volatility

# XBTからUSDに変換する関数
def XBTtuXBTUSD( data, xbtval, flag ):
	xbtusdval = round( data["close_price"] * xbtval, 6 )
	out_log("現在レート {} なので {} [XBT] は {} [USD] です\n".format( data["close_price"], round(xbtval,6), xbtusdval ), flag)
	return xbtusdval, flag

# ロットを発注量に変換する関数
def lot_to_amount( data, lot, flag ):
	amount = round( data["close_price"] * lot )
	out_log("現在レート {} なので {} [lot] は {} [USD] です\n".format( data["close_price"], round(lot,6), amount ), flag)
	return amount, flag

# ロットを発注量に変換する関数
def calc_min_lot( data, flag ):
	lot_limit_lower = flag["param"]["lot_limit_lower"]
	lot = lot_limit_lower

	return lot

# ストップ値を決定関数
def calc_stop( data, flag ):
	#return calc_stop_sma( data, flag )
	return calc_stop_AF( data, flag )

# ストップ値を移動平均線で決定関数
def calc_stop_sma( data, flag ):
	sma2 = flag["sma-value"]["prev-sma2"]
	stop = flag["position"]["stop"]

	# SMAをトレイリングストップとして使う
	# stop幅は、現在の終値とSMAとの差分 
	if flag["position"]["side"] == "BUY":
		# SMA2 < ポジション値の場合、ポジション値 - SMA2がstop幅
		# SMA2 > ポジション値の場合、エントリー時のlot数を維持する(stopを変えない)
		#if sma2 < flag["position"]["price"]:
		stop = round( flag["position"]["price"] - sma2 )
	elif flag["position"]["side"] == "SELL":
		# SMA2 > ポジション値の場合、SMA2 - ポジション値がstop幅
		# SMA2 < ポジション値の場合、エントリー時のlot数を維持する(stopを変えない)
		#if sma2 > flag["position"]["price"]:
		stop = round( sma2 - flag["position"]["price"] )

	return stop, flag

# ストップ値を決定関数
def calc_stop_AF( data, flag ):
	entry_times = flag["param"]["entry_times"]
	stop_AF_add = flag["param"]["stop_AF_add"]
	stop_AF_max = flag["param"]["stop_AF_max"]
	stop = flag["position"]["stop"] 

	# TODO ポジション追加中でも発動させる
	#out_log("#-------------trail_stop start----------------\n", flag)
	# まだ追加ポジションの取得中であれば何もしない
	#if flag["add-position"]["count"] < entry_times:
	#	#out_log("#-------------trail_stop end----------------\n", flag)
	#	return stop, flag

	# 高値／安値がエントリー価格からいくら離れたか計算
	if flag["position"]["side"] == "BUY":
		moved_range = round( data["high_price"] - flag["position"]["price"] )
	if flag["position"]["side"] == "SELL":
		moved_range = round( flag["position"]["price"] - data["low_price"] )

	# 最高値・最安値を更新したか調べる
	if moved_range < 0 or flag["position"]["stop-EP"] >= moved_range:
		#out_log("#-------------trail_stop end----------------\n", flag)
		#out_log("### STOP stay moved_range = {} stop-EP = {} stop = {}\n".format(moved_range, flag["position"]["stop-EP"], stop), flag)	
		return stop, flag
	else:
		flag["position"]["stop-EP"] = moved_range

	# 加速係数に応じて損切りラインを動かす
	flag["position"]["stop"] = round(flag["position"]["stop"] - ( moved_range + flag["position"]["stop"] ) * flag["position"]["stop-AF"])


	# 加速係数を更新
	flag["position"]["stop-AF"] = round( flag["position"]["stop-AF"] + stop_AF_add ,2 )
	if flag["position"]["stop-AF"] >= stop_AF_max:
		flag["position"]["stop-AF"] = stop_AF_max

	# ログ出力
	if flag["position"]["side"] == "BUY":
		out_log("トレイリングストップの発動：ストップ位置を{}USDに動かして、加速係数を{}に更新します\n".format( round(flag["position"]["price"] - flag["position"]["stop"]) , flag["position"]["stop-AF"] ), flag)
	else:
		out_log("トレイリングストップの発動：ストップ位置を{}USDに動かして、加速係数を{}に更新します\n".format( round(flag["position"]["price"] + flag["position"]["stop"]) , flag["position"]["stop-AF"] ), flag)

	#out_log("#-------------trail_stop end----------------\n", flag)

	#out_log("### STOP change moved_range = {} stop-EP = {} stop = {}\n".format(moved_range, flag["position"]["stop-EP"], stop), flag)	

	return stop, flag

# トレイリングストップの関数
def trail_stop( data,flag ):

	stop, flag = calc_stop( data, flag )

	"""
	if flag["position"]["side"] == "BUY":
		flag["position"]["stop"] = stop
		out_log("トレイリングストップ　{}USDに更新します\n".format( round( flag["position"]["price"] - stop ) ), flag)
	elif flag["position"]["side"] == "SELL":
		flag["position"]["stop"] = stop
		out_log("トレイリングストップ　{}USDに更新します\n".format( round( flag["position"]["price"] + stop ) ), flag)
	"""

	return flag

# 注文ロットを計算する関数
def calculate_lot( last_data,data,flag ):
	is_back_test = flag["param"]["is_back_test"]
	balance_limit = flag["param"]["balance_limit"]
	stop_range = flag["param"]["stop_range"]
	trade_risk = flag["param"]["trade_risk"]
	entry_times = flag["param"]["entry_times"]
	entry_range = flag["param"]["entry_range"]
	levarage = flag["param"]["levarage"]

	# 口座残高を取得する
	if is_back_test is True:
		balance = flag["records"]["funds"]
	else:
		result = get_collateral(flag)
		# 証拠金をXBTからUSDに変換する
		balance, flag = XBTtuXBTUSD(data, result['total'], flag)

	# 口座残高が最低額を下回ったら、lot=0で抜ける
	if balance < balance_limit:

		volatility = calculate_volatility( last_data, flag )
		stop = stop_range * volatility

		out_log("証拠金{0}が最低額{1}を下回ったので発注できません\n".format( round(balance,4), balance_limit ), flag)

		lot = 0

		return lot,stop,flag

	# 最初のエントリーの場合
	if flag["add-position"]["count"] == 0:

		# １回の注文単位（ロット数）と、追加ポジの基準レンジを計算する
		volatility = calculate_volatility( last_data, flag )
		stop = stop_range * volatility
		# 四捨五入 np.round()
		# 切り捨て np.trunc()
		# 切り捨て np.floor()
		# 切り上げ np.ceil()
		# ゼロに近いほうに丸める np.fix()
		# calc_lot = np.floor( balance * trade_risk * 100 / stop ) / 100
		calc_lot = round( ( balance * 100 * trade_risk / stop / 100 ), 7 )

		#print("volatility = {}\nstop = {}\ncalc_lot = {}\n".format(volatility, stop, calc_lot))
		#print("entry_times = {}\nunit-size = {}\n".format( entry_times, (np.floor( calc_lot * 100 / entry_times  ) / 100)  ) )
		#print("calc_lot * 100 = {}\n".format( calc_lot * 100 ) )	
		#print("calc_lot * 100 / entry_times = {}\n".format( calc_lot * 100 / entry_times ) )		
		#print("np.floor( calc_lot * 100 / entry_times  ) = {}\n".format( np.floor( calc_lot * 100 / entry_times  ) ) )		
		#print("(np.floor( calc_lot * 100 / entry_times  ) / 100)  ) = {}\n".format( (np.floor( calc_lot * 100 / entry_times  ) / 100) )	)	

		#flag["add-position"]["unit-size"] = np.floor( calc_lot * 100 / entry_times  ) / 100
		flag["add-position"]["unit-size"] = round( ( calc_lot * 100 / entry_times / 100 ) , 7 )
		flag["add-position"]["unit-range"] = round( volatility * entry_range )
		flag["add-position"]["stop"] = stop
		flag["position"]["ATR"] = round( volatility )

		out_log("現在のアカウント残高は{0}USDです\n".format( round(balance,2) ), flag)
		out_log("許容リスクから購入できる枚数は最大{0}lotまでです\n".format( round(calc_lot,4) ), flag)
		out_log("{0}回に分けて{1}lotずつ注文します\n".format( entry_times, round(flag["add-position"]["unit-size"],7 ) ), flag)

	# ２回目以降のエントリーの場合
	else:
		# 現在の証拠金から購入済枚数費用を引いた額
		# 証拠金 - 枚数に必要な証拠金数 / レバレッジ
		balance = round( balance - flag["position"]["price"] * flag["position"]["lot"] / levarage )

	# ストップ幅には、最初のエントリー時に計算したボラティリティを使う
	stop = flag["add-position"]["stop"]

	# 実際に購入可能な枚数を計算する
	#able_lot = np.floor( balance * levarage  * 100 / data["close_price"] ) / 100
	able_lot = round( ( balance * levarage  * 100 / data["close_price"] / 100 ) , 7 )
	out_log("証拠金から購入できる枚数は最大{0}lotまでです\n".format( able_lot ), flag)
	lot = min(able_lot, flag["add-position"]["unit-size"])
	#print("lot = {}, able_lot = {}, unit-size = {} \n".format(lot, able_lot, flag["add-position"]["unit-size"]))
	out_log("枚数は最大{0}lotに決定しました\n".format( lot ), flag)
	return lot,stop,flag

#-------------売買ロジックの部分の関数--------------
def check_signal( data, last_data, flag ):
	judge_signal = flag["param"]["judge_signal"]

	signal = {"side":None , "price":0}

	# シグナルを取得
	if (judge_signal["BUY"] == "pivot") or (judge_signal["SELL"] == "pivot"):
		signal_pivot = pivot( data, last_data, flag )
	if (judge_signal["BUY"] == "donchian") or (judge_signal["SELL"] == "donchian"):
		signal_donchian = donchian( data, last_data, flag )
	if (judge_signal["BUY"] == "sma_cross") or (judge_signal["SELL"] == "sma_cross"):
		signal_sma_cross = sma_cross( data, last_data, flag )

	# 指定したシグナルが発生しているかチェック
	if ( (judge_signal["BUY"] == "donchian") and (signal_donchian["side"] == "BUY") ) or ( (judge_signal["SELL"] == "donchian") and (signal_donchian["side"] == "SELL") ):
		signal = signal_donchian
	elif ( (judge_signal["BUY"] == "pivot") and (signal_pivot["side"] == "BUY") ) or ( (judge_signal["SELL"] == "pivot") and (signal_pivot["side"] == "SELL") ):
		signal = signal_pivot
	elif ( (judge_signal["BUY"] == "sma_cross") and (signal_sma_cross["side"] == "BUY") ) or ( (judge_signal["SELL"] == "sma_cross") and (signal_sma_cross["side"] == "SELL") ):
		signal = signal_sma_cross

	return signal

#-------------ボラティリティが閾値より小さくなっているか判定--------------
def check_volatility( data, last_data, flag ):
	judge = False
	# パラメタテーブルからボラティリティ終値比の閾値を取得
	judge_ratio = flag["param"]["judge_volatility_ratio"]

	# ボラティリティの終値比を計算
	volatility = calculate_volatility( last_data, flag )
	ratio = round( ( volatility * 100 / data["close_price"] / 100 ) , 7 )

	out_log("ボラティリティ比閾値{0}に対し現在の比は{1}でした\n".format( round(judge_ratio,7 ), round(ratio,7) ), flag)

	# ボラティリティ/終値の比が閾値よりも小さければYES
	if ratio <= judge_ratio:
		judge = True
		out_log("閾値を下回ったので判定ONです\n", flag)
	else:
		judge = False
		out_log("閾値を超えているので判定OFFです\n", flag)

	return judge

#-------------出来高変化率が閾値より大きくなっているか判定--------------
def check_vroc( data, last_data, flag ):
	judge = False
	# パラメタテーブルからボラティリティ終値比の閾値を取得
	term = flag["param"]["vroc_term"]
	thrsh = flag["param"]["vroc_thrsh"]

	# ボラティリティの終値比を計算
	vroc = calc_vroc( term, last_data, data["Volume"])

	out_log("{}前の出来高変化率の閾値{}に対し現在の値は{}でした\n".format( term, round(thrsh,1 ), round(vroc,1) ), flag)

	# ボラティリティ/終値の比が閾値よりも小さければYES
	if vroc <= thrsh:
		judge = False
		out_log("閾値を下回ったので判定OFFです\n", flag)
	else:
		judge = True
		out_log("閾値を超えているので判定ONです\n", flag)

	return judge

# SMAによるゴールデンクロス・デッドクロスを判定する関数
def sma_cross( data, last_data, flag ):
	judge_price = flag["param"]["judge_price"]
	sma1_term = flag["param"]["sma1_term"]
	sma2_term = flag["param"]["sma2_term"]
	prev_sma1 = flag["sma-value"]["prev-sma1"]
	prev_sma2 = flag["sma-value"]["prev-sma2"]

	new_data = data["close_price"]

	sma1 = calc_sma( sma1_term, last_data, new_data ) # 鋭いほう
	sma2 = calc_sma( sma2_term, last_data, new_data ) # 鈍いほう

	# 今回のSMAをバックアップ
	flag["sma-value"]["prev-sma1"] = sma1
	flag["sma-value"]["prev-sma2"] = sma2

	# 初回(初期値が0)はシグナルなし
	if ( prev_sma1 == 0 ) or ( prev_sma2 == 0 ):
		return {"side" : None , "price":0}
	# SMA1 が SMA2を下回った　= デッドクロス　売りサイン
	elif (prev_sma1 >= prev_sma2) and (sma1 < sma2):
		out_log("SMA{0}がSMA{1}を下回るデッドクロスが発生しました\n".format(sma1_term, sma2_term), flag)
		return {"side":"SELL","price":new_data}
	# SMA1 が SMA2を上回った　= ゴールデンクロス　買いサイン
	elif (prev_sma1 <= prev_sma2) and (sma1 > sma2):
		out_log("SMA{0}がSMA{1}を上回るゴールデンクロスが発生しました\n".format(sma1_term, sma2_term), flag)
		return {"side":"BUY","price":new_data}

	return {"side" : None , "price":0}

# SMAを計算する関数
def calc_sma( term, last_data, new_data ):
	sum_value = sum(i["close_price"] for i in last_data[-1 * (term - 1) :]) + new_data # 最新データも反映させる
	sma_value = round( sum_value / term )
	return sma_value

# 出来高の変化率を計算する関数
# VROC＝（最新の足の出来高 － n本前の足の出来高）÷ n本前の足の出来高 × 10#
def calc_vroc( term, last_data, new_data ):
	prev_data = last_data[-1 * (term - 1)]
	vroc_value = (new_data - prev_data["Volume"] ) * 100 / prev_data["Volume"]
	vroc_value = round( vroc_value, 2 )
	if vroc_value > 500:
		vroc_value = 500
	elif vroc_value < -200:
		vroc_value = -200
	#print("new_data {} last_vol {} vroc {}".format(new_data, prev_data["Volume"], vroc_value))
	return vroc_value

# ドンチャンブレイクを判定する関数
def donchian( data,last_data, flag ):
	buy_term = flag["param"]["buy_term"]
	sell_term = flag["param"]["sell_term"]
	judge_price = flag["param"]["judge_price"]

	highest = max(i["high_price"] for i in last_data[ (-1* buy_term): ])
	if data[ judge_price["BUY"] ] > highest:
		out_log("過去{0}足の最高値{1}USDを、直近の価格が{2}USDでブレイクしました\n".format(buy_term,highest,data[judge_price["BUY"]]), flag)
		return {"side":"BUY","price":highest}

	lowest = min(i["low_price"] for i in last_data[ (-1* sell_term): ])
	if data[ judge_price["SELL"] ] < lowest:
		out_log("過去{0}足の最安値{1}USDを、直近の価格が{2}USDでブレイクしました\n".format(sell_term,lowest,data[judge_price["SELL"]]), flag)
		return {"side":"SELL","price":lowest}

	return {"side" : None , "price":0}

def pivot( data, last_data, flag ):
	pivot_term = flag["param"]["pivot_term"]
	judge_line = flag["param"]["judge_line"]

	# PIVOT値取得
	PIVOT,R3,R2,R1,S1,S2,S3 = calc_pivot( last_data, flag )
	# エントリーシグナル選択
	if judge_line["BUY"] == "S2":
		buy_value = S2
	elif judge_line["BUY"] == "S1":
		buy_value = S1

	# 買い判定 サポートブレイクだがS3までは到達していない
	if (data["close_price"] <= buy_value) and (data["close_price"] > S3):
		out_log("過去{0}足のサポート{1}USDを、直近の価格が{2}USDでブレイクしました\n".format(pivot_term,buy_value,data["close_price"]), flag)
		return {"side":"BUY", "price":data[ "close_price"]}

	# 売りシグナル選択
	if judge_line["SELL"] == "R2":
		sell_value = R2
	elif judge_line["SELL"] == "R1":
		sell_value = R1

	# 売り判定 レジスタンスブレイクだがR3までは到達していない
	if (data["close_price"] >= sell_value) and (data["close_price"] < R3):
		out_log("過去{0}足のレジスタンス{1}USDを、直近の価格が{2}USDでブレイクしました\n".format(pivot_term,sell_value,data["close_price"]), flag)
		return {"side":"SELL", "price":data[ "close_price"]}

	return {"side" : None , "price":0}

# Pivotを計算する関数
def calc_pivot( last_data, flag ):
	pivot_term = flag["param"]["pivot_term"]
	R3_sum = R2_sum = R1_sum = PIVOT_sum = PIVOT_tmp = S3_sum = S2_sum = S1_sum = 0
	for i in range(pivot_term):
		Last1D = last_data[-1 * (i + 1)]
		HIGH = Last1D["high_price"]
		LOW = Last1D["low_price"]
		CLOSE = Last1D["close_price"]
		PIVOT_tmp = (HIGH+LOW+CLOSE)/3
		PIVOT_sum += PIVOT_tmp
		R3_sum += HIGH + 2 * (PIVOT_tmp - LOW)
		R2_sum += PIVOT_tmp + (HIGH - LOW)
		R1_sum += (2 * PIVOT_tmp) - LOW
		S1_sum += (2 * PIVOT_tmp) - HIGH
		S2_sum += PIVOT_tmp - (HIGH - LOW)
		S3_sum += LOW - 2 * (HIGH - PIVOT_tmp)
	PIVOT = round(PIVOT_sum / pivot_term,1)
	R3 = round(R3_sum / pivot_term)
	R2 = round(R2_sum / pivot_term)
	R1 = round(R1_sum / pivot_term)
	S3 = round(S3_sum / pivot_term)
	S2 = round(S2_sum / pivot_term)
	S1 = round(S1_sum / pivot_term)

	return PIVOT,R3,R2,R1,S1,S2,S3
