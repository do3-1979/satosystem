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
def calc_stop( data, last_data, flag ):

	#return calc_stop_sma( data, flag )
	#return calc_stop_AF( data, flag )
	return calc_stop_psar( data, last_data, flag )

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

# ストップ値をパラボリックASRにする関数
# ポジションのBUY/SELLに応じてパラボリックSARの値をストップポジションとする
def calc_stop_psar( data, last_data, flag ):
	stop = flag["position"]["stop"] 
	position_price = flag["position"]["price"]

	tmp_data = []
	tmp_data = last_data.copy()
	tmp_data.append(data)
	#print("last_data len {}, tmp_data len {}, last_data[-1] {} tmp_data[-1] {}".format(len(last_data), len(tmp_data), last_data[-1], tmp_data[-1]))

	sar_result = calc_parabolic_sar( tmp_data, flag )
	psarbull = sar_result["psarbull"][-1]
	psarbear = sar_result["psarbear"][-1]

	#print("psarbull {} psarbear {}".format(psarbull,psarbear))

	tmp_stop = flag["position"]["stop"]

	# BUYの時は現在値からpsarbullの差をstopとする。SELLはpserbear
	if flag["position"]["side"] == "BUY" and psarbull != None:
		tmp_stop = round(position_price - psarbull)
	if flag["position"]["side"] == "SELL" and psarbear != None:
		tmp_stop = round(psarbear - position_price)
	
	# 現在のstopより大きければ維持
	stop = min( tmp_stop, stop )
	flag["position"]["stop"] = stop

	return stop, flag

# ストップ値を現在の値から固定値分のみずらした値に置く関数
# TODO 300USD固定をやめる 現在価格の0.011程度にするべき
def trail_stop_neighbor( data, last_data, flag ):
	# ストップ値は「ポジションの取得単価」に対する差額。ポジション取得単価より高い場合は負値。
	# 現在の終値との差額を求めてから新しいストップ値を求める
	prev_stop = new_stop = flag["position"]["stop"] 
	stop_neighbor = flag["param"]["stop_neighbor"]
	latest_close_price = data["close_price"]
	position_price = flag["position"]["price"]

	# 終値とストップ値の差額を出す
	if flag["position"]["side"] == "BUY":
		diff_price = latest_close_price - ( position_price - prev_stop )
		# 終値との差分が固定値を超えていたらストップ値が固定値以下になるようにする
		if diff_price > stop_neighbor:
			# 新ストップ値はポジション取得単価と目標価格との差額
			new_stop = position_price - ( latest_close_price - stop_neighbor )

	if flag["position"]["side"] == "SELL":
		diff_price = ( position_price + prev_stop ) - latest_close_price
		# 終値との差分が固定値を超えていたらストップ値が固定値以下になるようにする
		if diff_price > stop_neighbor:
			# 新ストップ値 = 目標値 ( = 現在の終値 + 固定値) とポジション取得単価の差額
			new_stop = ( latest_close_price + stop_neighbor ) - position_price

	# 前回のストップ値より小さければ更新する(負値の場合は小さいほど終値に近い)
	tmp_stop = min( prev_stop, new_stop )
	flag["position"]["stop"] = tmp_stop

	#print("diff {} prev_stop {} new_stop {} stop {}".format(diff_price, prev_stop, new_stop, tmp_stop))

	return flag

# パラボリックSARを計算する関数
def calc_parabolic_sar( data, flag ):
	iaf = flag["param"]["stop_AF_add"]
	maxaf = flag["param"]["stop_AF_max"]

	# データ成型
	high = []
	low = []
	close = []
	psar = []

	datalen = len(data)

	for i in range(0,datalen):
		high.append(data[i]['high_price'])
		low.append(data[i]['low_price'])
		close.append(data[i]['close_price'])
		psar = close

	length = len(close)

	psarbull = [None] * length
	psarbear = [None] * length
	bull = True
	af = iaf
	ep = low[0]
	hp = high[0]
	lp = low[0]

	# 過去データからPSARを計算
	for i in range(2,length):
		if bull:
			psar[i] = psar[i - 1] + af * (hp - psar[i - 1])
			#print("{} psar[{}]:{:.2f}, af:{:.2f} hp:{:.2f} psar[{}]:{:.2f} last_data[{}]:{:.2f}".format(data[i]["close_time_dt"],i,psar[i],af,hp,i,psar[i-1],i,data[i]["close_price"]))
		else:
			psar[i] = psar[i - 1] + af * (lp - psar[i - 1])
			#print("{} psar[{}]:{:.2f}, af:{:.2f} lp:{:.2f} psar[{}]:{:.2f} last_data[{}]:{:.2f}".format(data[i]["close_time_dt"],i,psar[i],af,lp,i,psar[i-1],i,data[i]["close_price"]))

		reverse = False

		if bull:
			if low[i] < psar[i]:
				bull = False
				reverse = True
				psar[i] = hp
				lp = low[i]
				af = iaf
		else:
			if high[i] > psar[i]:
				bull = True
				reverse = True
				psar[i] = lp
				hp = high[i]
				af = iaf

		if not reverse:
			if bull:
				if high[i] > hp:
					hp = high[i]
					af = min(af + iaf, maxaf)
				if low[i - 1] < psar[i]:
					psar[i] = low[i - 1]
				if low[i - 2] < psar[i]:
					psar[i] = low[i - 2]
			else:
				if low[i] < lp:
					lp = low[i]
					af = min(af + iaf, maxaf)
				if high[i - 1] > psar[i]:
					psar[i] = high[i - 1]
				if high[i - 2] > psar[i]:
					psar[i] = high[i - 2]
		
		if bull:
			psarbull[i] = psar[i]
		else:
			psarbear[i] = psar[i]

	return {"psar":psar, "psarbear":psarbear, "psarbull":psarbull}

# トレイリングストップの関数
def trail_stop( data, last_data, flag ):

	stop, flag = calc_stop( data, last_data, flag )

	return flag

# 注文ロットを計算する関数
# TODO 注文ロットのボラ計算外して資産からの割合のみにする
# ボラティリティからリスクを考慮したロット数にしているがボラティリティがそこまで有効とは思えない
# ボラティリティ期間は現在35で固定。一定期間値動きがなかったら小さくなる。値動きが大きいと大きくなる
# ボラティリティは2hだと70hなのでおよそ3日分
# ロット数を低く抑えて分割数を多くするか、ロット数を高くして分割数を減らすか。
# ロット数が高いと、エントリ失敗したときのダメージが高くなる？
# ロット数を低くすると、急な変化で1回しか積めない場合、利益が少ない？　→　追加時に複数lot積めるか？
# →　できそう create order後にwaitが必要かもしれない
# →　ロット数の幅と、分割数のみでシミュレートしてみる
# ATRをパラボリックで計算するためにボラティリティは必要
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
		# 従来だと4 x 100～1000で、300くらい　→ 1200usdがストップ幅
		stop = stop_range * volatility
		# 四捨五入 np.round()
		# 切り捨て np.trunc()
		# 切り捨て np.floor()
		# 切り上げ np.ceil()
		# ゼロに近いほうに丸める np.fix()
		# calc_lot = np.floor( balance * trade_risk * 100 / stop ) / 100
		# stop = stop_range * lot_ratio * balance
		# TODO calc_lotの戦略の見直し
		# trade_liskをそのまま活用する
		# calc_lot = 1トレードで購入するロットサイズ
		# unit-size = 1トレードで購入する分割ロットサイズ
		#  = 総資産 x トレードリスク / 分割数
		# 失っていい資産 x レバレッジ / ストップ幅で変動する可能性のある幅　が、購入資産
		# 値動きが少ないと、ロット数が大きくなる
		# 値動きが激しいと、ロット数が少なくなる
		# → 変動がなかった場合に大きく購入し、変動中は小さくする戦略となっている
		# stop幅を小さくし、分割数を増やすとどうなるか。
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

# check percentage volume osciilator
def check_pvo( data, last_data, flag ):
	judge = False
	# パラメタテーブルからボラティリティ終値比の閾値を取得
	s_term = flag["param"]["pvo_s_term"]
	l_term = flag["param"]["pvo_l_term"]
	thrsh = flag["param"]["pvo_thrsh"]

	# ボラティリティの終値比を計算
	pvo = calc_pvo( s_term, l_term, last_data, data )

	out_log("PVO shrot {} long {} の閾値{}%に対し現在の値は{}%でした\n".format( s_term, l_term, round(thrsh,1 ), round(pvo,1) ), flag)

	# PVOの閾値チェック
	if pvo <= thrsh:
		judge = False
		out_log("PVO判定=OFF\n", flag)
	else:
		judge = True
		out_log("PVO判定=ON\n", flag)

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

# EMAを得る
# Exponential Moving Average（指数平滑移動平均）。MACDを算出する際に使ったり結構多用します。
# 過去よりも現在の方が影響が強いという考えを入れた移動平均値で、現在に近いレートほど重みをつけて計算します。
# 計算式は
# E(t) = E(t-1) + 2/(n+1)(直近の終値 – E(t-1))
# data : price list
# n    : period
def calc_ema( term, data ):
	i=0
	chk_1=0
	chk_1_sum=0
	et_1=0
	result = []
	for p in data:
		i = len(result)
		if i <= (term - 1):
			#SMA
			chk_1_sum = sum(result)
			chk_1 = (float(chk_1_sum) + float(p)) / (i + 1)
			result += [chk_1]
		else:
			#EMA
			et_1 = result[-1]
			result += [float(et_1 + 2 / (term + 1) * (float(p) - et_1))]
	return result[-1]

# SMAを計算する関数
def calc_sma( term, last_data, new_data ):
	sum_value = sum(i["close_price"] for i in last_data[-1 * (term - 1) :]) + new_data # 最新データも反映させる
	sma_value = round( sum_value / term )
	return sma_value

# Percentage Volume Oscillator (PVO)は、出来高を対象としたモメンタムオシレーターです。
# PVOは、2つのボリュームベースの移動平均の差を、大きい方の移動平均に対する割合として測定します。
# MACDやPercentage Price Oscillator (PPO)と同様に、シグナルライン、ヒストグラム、センターラインで表示されます。
# PVOは、短い方の出来高EMAが長い方の出来高EMAを上回っている場合は正の値を示し、短い方の出来高EMAが下回っている場合は
# 負の値を示します。この指標は、出来高の上昇と下降を定義するために使用することができ、その後、他のシグナルを確認
# または否定するために使用することができます。一般的には、PVOが上昇または正の値を示したときに、ブレイクアウトまたは
# サポートブレークが成立します。
# ( ( 出来高のshort_term日EMA ー 出来高のlong_term日EMA ) / 出来高のlong_term日EMA ) × 100
def calc_pvo( s_term, l_term, last_data, new_data ):
	volume_data = []
	
	data_len = max( s_term, l_term )
	# 出来高の必要数を配列に格納
	for i in last_data[ (-1* data_len): ]:
		volume_data.append(i["Volume"])
	
	# 最新の値も追加する
	volume_data.append(new_data["Volume"])
	# 短いほうのEMAを計算
	short_ema = calc_ema( s_term, volume_data )
	# 長いほうのEMAを計算
	long_ema = calc_ema( l_term, volume_data )
	# PVOを計算
	pvo_value = ( ( short_ema - long_ema ) * 100 / long_ema )
	#print("pvo_value = {}\n".format(pvo_value))

	return pvo_value

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
