from datetime import datetime
import time
from pprint import pprint
import pandas as pd
import config
import json

# -------パラメータ------
from param import *
# -------資金管理機能--------
from pos_mng import *
# -------主制御----------
from daemon import daemon
# -------バックテスト機能-----
from backtest import backtest
# -------バックテスト用パラメータ------
from param_bt import *

# バックテスト用にパラメタ書き換え
is_back_test = True       # back test フラグ
is_total_test = True       # back test フラグ

prog_cnt = 0

# テストごとの各パラメーターの組み合わせと結果を記録する配列を準備
param_buy_term  = []
param_sell_term = []
param_pivot_term = []
param_sma1_term = []
param_sma2_term = []
param_volatility_term = []
param_stop_range = []
param_trade_risk = []
param_entry_times = []
param_entry_range = []
param_chart_sec = []
param_judge_price = []
param_judge_line = []
param_judge_signal = []
param_judge_volatility_ratio = []
param_stop_AF = []
param_stop_AF_add = []
param_stop_AF_max = []
param_lot_limit_lower = []
param_start_period = []
param_end_period = []


result_count = []
result_winRate = []
result_returnRate = []
result_drawdown = []
result_profitFactor = []
result_gross = []

# テスト数修正
total_test_num *= len(period_list)

# 期間ごとにパラメタ演算
for period in period_list:

	flag_tmp = {
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
			"wait":wait,
		}
	}

	start_period = period["START"]
	end_period = period["END"]

	# バックテストに必要な時間軸のチャートをすべて取得
	price_list = {}
	price_tmp = []
	price = []
	for chart_sec in chart_sec_list:
		#file_path = "../price_data/price_btcusd_" + str(chart_sec) + ".json"
		#price_list[ chart_sec ] = get_price_from_file(chart_sec,file_path,flag_tmp, start_period, end_period )
		price_tmp = get_price(chart_sec,flag_tmp,after=1451606400)
		print("-----期間 {0}～{1}の{2}分軸の価格データをファイルから取得中-----".format( start_period, end_period, int(chart_sec/60) ))
		#time.sleep(10)

		start_unix = 0
		end_unix = 9999999999

		if start_period:
			start_period = datetime.strptime(start_period,"%Y/%m/%d %H:%M")
			start_unix = int(start_period.timestamp())
		if end_period:
			end_period = datetime.strptime( end_period,"%Y/%m/%d %H:%M")
			end_unix = int(end_period.timestamp())

		for i in range( len( price_tmp ) ):
			unix_time = price_tmp[i]["close_time"]
			if ( start_unix < unix_time ) and ( end_unix > unix_time ):
				price.append( price_tmp[i] )

		price_list[ chart_sec ] = price

	# 総当たりのためのfor文の準備
	combinations = [(chart_sec,
					 buy_term,
					 sell_term,
					 pivot_term,
					 sma1_term,
					 sma2_term,
					 volatility_term,
					 stop_range,
					 trade_risk,
					 entry_times,
					 entry_range,
					 judge_line,
					 judge_price,
					 judge_signal,
					 judge_volatility_ratio,
					 stop_AF,
					 stop_AF_add,
					 stop_AF_max,
					 lot_limit_lower)
		for chart_sec in chart_sec_list
		for buy_term  in buy_term_list
		for sell_term in sell_term_list
		for pivot_term in pivot_term_list
		for sma1_term in sma1_term_list
		for sma2_term in sma2_term_list
		for volatility_term in volatility_term_list
		for stop_range in stop_range_list
		for trade_risk in trade_risk_list
		for entry_times in entry_times_list
		for entry_range in entry_range_list
		for judge_line in judge_line_list
		for judge_price in judge_price_list
		for judge_signal in judge_signal_list
		for judge_volatility_ratio in judge_volatility_ratio_list
		for stop_AF in stop_AF_list
		for stop_AF_add in stop_AF_add_list
		for stop_AF_max in stop_AF_max_list
		for lot_limit_lower in lot_limit_lower_list
		]

	for chart_sec, \
		buy_term, \
		sell_term, \
		pivot_term, \
		sma1_term, \
		sma2_term, \
		volatility_term, \
		stop_range, \
		trade_risk, \
		entry_times, \
		entry_range, \
		judge_list, \
		judge_price, \
		judge_signal, \
		judge_volatility_ratio, \
		stop_AF, \
		stop_AF_add, \
		stop_AF_max, \
		lot_limit_lower in combinations:

		price = price_list[ chart_sec ]
		last_data = []
		need_term = max(buy_term,sell_term,volatility_term,pivot_term,sma1_term,sma2_term)

		# 進捗率
		prog_cnt += 1

		# フラグ変数の初期化
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
			    "judge_line":judge_line,
			    "judge_price":judge_price,
	    		"judge_signal":judge_signal,
				"judge_volatility_ratio":judge_volatility_ratio,
			    "volatility_term":volatility_term,
				"sma1_term":sma1_term,
				"sma2_term":sma2_term,
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
				"SMA2":[]
			},
		}

		#-------- メインループ(バックテストでは抜ける) ---------
		daemon( price, last_data, flag, need_term, chart_log )

		print("-----------------------------------")
		print("期間                : " + str(price[0]["close_time_dt"]) + "～" + str(price[-1]["close_time_dt"]))
		print("時間軸              : " + str(int(chart_sec/60)) + "分足で検証")
		print("パラメータ１～２    : " + str(buy_term)  + "期間 / 買い " + str(sell_term) + "期間 / 売り" )
		print("パラメータ３        : " + str(pivot_term) + "期間 / PIVOT" )
		print("パラメータＸ        : " + str(sma1_term) + "SMA / " + str(sma2_term) + "SMA DC/GC" )
		print("パラメータ４        : " + str(volatility_term)  + "期間" )
		print("パラメータ５        : " + str(stop_range) + "ストップレンジ" )
		print("パラメータ６        : " + str(trade_risk) + "％" )
		print("パラメータ７～８    : " + str(entry_times) + "分割 " + str(entry_range) + "追加ポジション" )
		print("パラメータ９～１１  : " + str(stop_AF) + "加速係数 " + str(stop_AF_add) + "増加度 " + str(stop_AF_max) + "上限" )
		print("パラメータ１２      : " + str(lot_limit_lower) + "注文lot数の下限" )
		print(str(len(price)) + "件のローソク足データで検証")
		print("-----------------------------------")

		result = backtest( flag, last_data, chart_log )

		print("-----------------------------------")
		print("テスト進捗率         : " + str(prog_cnt)+ "/" + str(total_test_num) + "件 [" + str(round( ( (prog_cnt * 100) / total_test_num ) ,1 ) ) + "％]")
		print("-----------------------------------")

		# 今回のループで使ったパラメータの組み合わせを配列に記録する
		param_start_period.append( start_period )
		param_end_period.append( end_period )
		param_buy_term.append( buy_term )
		param_sell_term.append( sell_term )
		param_pivot_term.append( pivot_term )
		param_sma1_term.append( sma1_term )
		param_sma2_term.append( sma2_term )
		param_volatility_term.append( volatility_term )
		param_stop_range.append( stop_range )
		param_trade_risk.append( trade_risk )
		param_entry_times.append( entry_times )
		param_entry_range.append( entry_range )
		param_chart_sec.append( chart_sec )
		if judge_line["BUY"] == "S2":
			param_judge_line.append( "S2/R2" )
		else:
			param_judge_line.append( "S1/R1" )
		if judge_price["BUY"] == "high_price":
			param_judge_price.append( "高値/安値" )
		else:
			param_judge_price.append( "終値/終値" )
		if judge_signal["BUY"] == "donchian":
			param_judge_signal.append( "ドンチャン" )
		elif judge_signal["BUY"] == "pivot":
			param_judge_signal.append( "PIVOT" )
		elif judge_signal["BUY"] == "sma_cross":
			param_judge_signal.append( "SMA DC/GC" )
		param_judge_volatility_ratio.append( judge_volatility_ratio )
		param_stop_AF.append( stop_AF )
		param_stop_AF_add.append( stop_AF_add )
		param_stop_AF_max.append( stop_AF_max )
		param_lot_limit_lower.append( lot_limit_lower )

		# 今回のループのバックテスト結果を配列に記録する
		result_count.append( result["トレード回数"] )
		result_winRate.append( result["勝率"] )
		result_returnRate.append( result["平均リターン"] )
		result_drawdown.append( result["最大ドローダウン"] )
		result_profitFactor.append( result["プロフィットファクタ―"] )
		result_gross.append( result["最終損益"] )

		# 全てのパラメータによるバックテスト結果をPandasで１つの表にする
		df = pd.DataFrame({
			"開始"				     :  param_start_period,
			"終了"				     :  param_end_period,
			"時間軸"                 :  param_chart_sec,
			"買い期間"               :  param_buy_term,
			"売り期間"               :  param_sell_term,
			#"PIVOT期間"              :  param_pivot_term,
			#"SMA1期間"               :  param_sma1_term,
			#"SMA2期間"               :  param_sma2_term,
			"ボラティリティ期間"      :  param_volatility_term,
			"ストップレンジ"          :  param_stop_range,
			"トレードリスク"          :  param_trade_risk,
			"分割回数"               :  param_entry_times,
			"追加ポジション"          :  param_entry_range,
			#"判定ライン"             :  param_judge_line,
			#"判定基準"               :  param_judge_price,
			"ボラティリティ終値比"    :  param_judge_volatility_ratio,
			#"判定シグナル"           :  param_judge_signal,
			"加速係数"               :  param_stop_AF,
			"加速係数AF"             :  param_stop_AF_add,
			"加速係数MAX"            :  param_stop_AF_max,
			"注文lot数の下限"        :  param_lot_limit_lower,
			"トレード回数"  :  result_count,
			"勝率"          :  result_winRate,
			"平均リターン"  :  result_returnRate,
			"ドローダウン"  :  result_drawdown,
			"PF"            :  result_profitFactor,
			"最終損益"      :  result_gross
		})

		# 列の順番を固定する
		df = df[[ "開始",
				  "終了",
				  "時間軸",
				  "買い期間",
				  "売り期間",
				  #"PIVOT期間",
				  #"SMA1期間",
				  #"SMA2期間",
				  "ボラティリティ期間",
				  "ストップレンジ",
				  "トレードリスク",
				  "分割回数",
				  "追加ポジション",
				  #"判定ライン",
				  #"判定基準",
				  "ボラティリティ終値比",
				  #"判定シグナル",
				  "加速係数",
				  "加速係数AF",
				  "加速係数MAX",
				  "注文lot数の下限",
				  "トレード回数",
				  "勝率",
				  "平均リターン",
				  "ドローダウン",
				  "PF",
				  "最終損益"  ]]

# トレード回数が0は消す → 不要なエントリーを削るので回数を見直す
df.drop( df[ df["トレード回数"] < 1].index, inplace=True )
# PFが1.0以下は消す。利益が出ないのは無駄
df.drop( df[ df["PF"] <= 1.0].index, inplace=True )

df.to_csv("./backtest/result-partial-{}.csv".format(datetime.now().strftime("%Y-%m-%d-%H-%M")) )
