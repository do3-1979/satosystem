from datetime import datetime
import time
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
#import mpl_finance
import pandas as pd
import numpy as np
from pprint import pprint

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

#------------バックテストの部分の関数--------------

# バックテストの集計用の関数
def backtest(flag, last_data, chart_log):
	start_funds = flag["param"]["start_funds"]
	is_total_test = flag["param"]["is_total_test"]

	# 成績を記録したpandas DataFrameを作成
	records = pd.DataFrame({
		"Date"	   :  pd.to_datetime(flag["records"]["date"]),
		"Profit"   :  flag["records"]["profit"],
		"Side"	   :  flag["records"]["side"],
		"Rate"	   :  flag["records"]["return"],
		"Stop"	   :  flag["records"]["stop-count"],
		"Periods"  :  flag["records"]["holding-periods"],
		"Slippage" :  flag["records"]["slippage"]
	})

	# チャートを記録したデータフレームを作成
	chart = pd.DataFrame({
		"Date"	   :  pd.to_datetime(chart_log["records"]["date"]),
		"Close_price"   :  chart_log["records"]["close_price"],
		"Position_price"   :  chart_log["records"]["position_price"],
		"Stop_price"   :  chart_log["records"]["stop_price"],
		"Price_ohlc"   :  chart_log["records"]["price_ohlc"],
		"Donchian_h"   :  chart_log["records"]["donchian_h"],
		"Donchian_l"   :  chart_log["records"]["donchian_l"],
		"Volume"   :  chart_log["records"]["Volume"],
		"QuoteVolume"   :  chart_log["records"]["QuoteVolume"],
		"PIVOT"   :  chart_log["records"]["PIVOT"],
		"R3"   :  chart_log["records"]["R3"],
		"R2"   :  chart_log["records"]["R2"],
		"R1"   :  chart_log["records"]["R1"],
		"S3"   :  chart_log["records"]["S3"],
		"S2"   :  chart_log["records"]["S2"],
		"S1"   :  chart_log["records"]["S1"],
		"SMA1"   :  chart_log["records"]["SMA1"],
		"SMA2"   :  chart_log["records"]["SMA2"],
		"vroc"   :  chart_log["records"]["vroc"],
		"vroc_thrsh"   :  chart_log["records"]["vroc_thrsh"]
	})

	# 連敗回数をカウントする
	consecutive_defeats = []
	defeats = 0
	consecutive_defeats.append( defeats )
	for p in flag["records"]["profit"]:
		if p < 0:
			defeats += 1
		else:
			consecutive_defeats.append( defeats )
			defeats = 0

	# テスト日数を集計
	time_period = datetime.fromtimestamp(last_data[-1]["close_time"]) - datetime.fromtimestamp(last_data[0]["close_time"])
	time_period = int(time_period.days)

	# 総損益の列を追加する
	records["Gross"] = records.Profit.cumsum()

	# 資産推移の列を追加する
	records["Funds"] = records.Gross + start_funds

	# 最大ドローダウンの列を追加する
	records["Drawdown"] = records.Funds.cummax().subtract(records.Funds)
	records["DrawdownRate"] = round(records.Drawdown / records.Funds.cummax() * 100,1)

	# 買いエントリーと売りエントリーだけをそれぞれ抽出する
	buy_records = records[records.Side.isin(["BUY"])]
	sell_records = records[records.Side.isin(["SELL"])]

	# 月別のデータを集計する
	records["月別集計"] = pd.to_datetime( records.Date.apply(lambda x: x.strftime('%Y/%m')))
	grouped = records.groupby("月別集計")

	month_records = pd.DataFrame({
		"Number"   :  grouped.Profit.count(),
		"Gross"	   :  grouped.Profit.sum(),
		"Funds"	   :  grouped.Funds.last(),
		"Rate"	   :  round(grouped.Rate.mean(),2),
		"Drawdown" :  grouped.Drawdown.max(),
		"Periods"  :  grouped.Periods.mean()
		})

	# 勝率を計算
	buy_win_rate = 0
	sell_win_rate = 0
	win_rate = 0
	draw_down_max_usd = 0
	draw_down_max_per = 0
	last_funds = 0
	trade_result = 0
	profit_factor = 0
	growth_per_year = 0
	mar_ratio = 0
	sharp_ratio = 0
	input_and_output_ratio = 0

	if len(buy_records) > 0:
		buy_win_rate = round(len(buy_records[buy_records.Profit>0]) / len(buy_records) * 100,1)

	if len(sell_records) > 0:
		sell_win_rate = round(len(sell_records[sell_records.Profit>0]) / len(sell_records) * 100,1)

	if ( len(records) > 0 ) and (records.Rate.std() > 0 ):
		win_rate = round(len(records[records.Profit>0]) / len(records) * 100,1)
		draw_down_max_usd = -1 * records.Drawdown.max()
		draw_down_max_per = -1 * records.DrawdownRate.loc[records.Drawdown.idxmax()]
		last_funds = records.Funds.iloc[-1]
		trade_result = round(records.Funds.iloc[-1] / start_funds * 100,2)
		profit_factor = round( -1 * (records[records.Profit>0].Profit.sum() / records[records.Profit<0].Profit.sum()) ,2)
		mar_ratio  = round( (records.Funds.iloc[-1] / start_funds -1)*100 / records.DrawdownRate.max(),2 )

		sharp_ratio = round(records.Rate.mean()/records.Rate.std(),2)
		input_and_output_ratio = round( records[records.Profit>0].Rate.mean()/abs(records[records.Profit<0].Rate.mean()) ,2)

		if time_period > 0:
			growth_per_year = round((records.Funds.iloc[-1] / start_funds)**(  365 / time_period ) * 100 - 100,2)


	print("バックテストの結果")
	if is_total_test == False:
		print("-----------------------------------")
		print("買いエントリの成績")
		print("-----------------------------------")
		print("トレード回数       :  {}回".format( len(buy_records) ))
		print("勝率               :  {}％".format(buy_win_rate))
		print("平均リターン       :  {}％".format(round(buy_records.Rate.mean(),2)))
		print("総損益             :  {}USD".format( buy_records.Profit.sum() ))
		print("平均保有期間       :  {}足分".format( round(buy_records.Periods.mean(),1) ))
		print("損切りの回数       :  {}回".format( buy_records.Stop.sum() ))

		print("-----------------------------------")
		print("売りエントリの成績")
		print("-----------------------------------")
		print("トレード回数       :  {}回".format( len(sell_records) ))
		print("勝率               :  {}％".format(sell_win_rate))
		print("平均リターン       :  {}％".format(round(sell_records.Rate.mean(),2)))
		print("総損益             :  {}USD".format( sell_records.Profit.sum() ))
		print("平均保有期間       :  {}足分".format( round(sell_records.Periods.mean(),1) ))
		print("損切りの回数       :  {}回".format( sell_records.Stop.sum() ))

	print("-----------------------------------")
	print("総合の成績")
	print("-----------------------------------")
	print("全トレード数       :  {}回".format(len(records) ))
	print("勝率               :  {}％".format(win_rate))
	print("平均リターン       :  {}％".format(round(records.Rate.mean(),2)))
	print("平均保有期間       :  {}足分".format( round(records.Periods.mean(),1) ))
	print("損切りの回数       :  {}回".format( records.Stop.sum() ))
	print("")
	print("最大の勝ちトレード :  {}USD".format(records.Profit.max()))
	print("最大の負けトレード :  {}USD".format(records.Profit.min()))
	print("最大連敗回数       :  {}回".format( max(consecutive_defeats) ))
	print("最大ドローダウン   :  {0}USD / {1}％".format(draw_down_max_usd, draw_down_max_per ))
	print("利益合計           :  {}USD".format( records[records.Profit>0].Profit.sum() ))
	print("損失合計           :  {}USD".format( records[records.Profit<0].Profit.sum() ))
	print("最終損益           :  {}USD".format( records.Profit.sum() ))
	print("")
	print("初期資金           :  {}USD".format( start_funds ))
	print("最終資金           :  {}USD".format( last_funds ))
	print("運用成績           :  {}％".format( trade_result ))
	print("手数料合計         :  {}USD".format( -1 * records.Slippage.sum() ))

	print("-----------------------------------")
	print("各成績指標")
	print("-----------------------------------")
	print("CAGR(年間成長率)         :  {}％".format( growth_per_year ))
	print("MARレシオ                :  {}".format( mar_ratio ))
	print("シャープレシオ           :  {}".format( sharp_ratio ))
	print("プロフィットファクター   :  {}".format( profit_factor ))
	print("損益レシオ               :  {}".format( input_and_output_ratio ))
	if is_total_test == False:
		print("-----------------------------------")
		print("月別の成績")

		for index , row in month_records.iterrows():
			print("-----------------------------------")
			print( "{0}年{1}月の成績".format( index.year, index.month ) )
			print("-----------------------------------")
			print("トレード数         :  {}回".format( row.Number.astype(int) ))
			print("月間損益           :  {}USD".format( row.Gross.astype(int) ))
			print("平均リターン       :  {}％".format( row.Rate ))
			print("継続ドローダウン   :  {}USD".format( -1 * row.Drawdown.astype(int) ))
			print("月末資金           :  {}USD".format( row.Funds.astype(int) ))


		# 際立った損益を表示
		n = 10
		print("------------------------------------------")
		print("＋{}%を超えるトレードの回数  :  {}回".format(n,len(records[records.Rate>n]) ))
		print("------------------------------------------")
		for index,row in records[records.Rate>n].iterrows():
			print( "{0}  |  {1}％  |  {2}".format(row.Date,round(row.Rate,2),row.Side ))
		print("------------------------------------------")
		print("－{}%を下回るトレードの回数  :  {}回".format(n,len(records[records.Rate< n*-1]) ))
		print("------------------------------------------")
		for index,row in records[records.Rate < n*-1].iterrows():
			print( "{0}  |  {1}％  |  {2}".format(row.Date,round(row.Rate,2),row.Side  ))

	# バックテストの計算結果を返す
	result = {
		"トレード回数"     : len(records),
		"勝率"             : win_rate,
		"平均リターン"     : round(records.Rate.mean(),2),
		"最大ドローダウン" : draw_down_max_usd,
		"最終損益"         : last_funds,
		"プロフィットファクタ―" : profit_factor
	}

	if is_total_test == False:
		# ログファイルの出力
		file =	open("./{0}-log.txt".format(datetime.now().strftime("%Y-%m-%d-%H-%M")),'wt',encoding='utf-8')
		file.writelines(flag["records"]["log"])

		# 損益曲線をプロット
		plt.plot( records.Date, records.Funds )
		plt.xlabel("Date")
		plt.ylabel("Balance")
		plt.xticks(rotation=50) # X軸の目盛りを50度回転

		# グラフ画像保存
		file_name = str(format(datetime.now().strftime("%Y-%m-%d-%H-%M"))) + "-gain_curve.png"
		plt.savefig(file_name)

		# 価格情報をプロット
		plt.clf()

		# サイズの解像度をあげる
		plt.figure(figsize=(16, 9), dpi=500)

		# 出来高もグラフに追加
		plt.subplot2grid((5, 5), (0, 0), colspan = 5, rowspan = 3)

		# pivot
		if (flag["param"]["judge_signal"]["BUY"] == "pivot") or (flag["param"]["judge_signal"]["SELL"] == "pivot"):
			plt.plot(chart.Date, chart.R3, color = "lime", label = "R3_" + str(flag["param"]["pivot_term"]), linestyle = "--", linewidth = "1")
			plt.plot(chart.Date, chart.R2, color = "yellow", label = "R2_eq.R3 term", linestyle = "--", linewidth = "1")
			plt.plot(chart.Date, chart.R1, color = "orange", label = "R1_eq.R3 term", linestyle = "--", linewidth = "1")
			plt.plot(chart.Date, chart.S3, color = "lime", label = "S3_eq.R3 term", linestyle = "--", linewidth = "1")
			plt.plot(chart.Date, chart.S2, color = "yellow", label = "S2_eq.R3 term", linestyle = "--", linewidth = "1")
			plt.plot(chart.Date, chart.S1, color = "orange", label = "S1_eq.R3 term", linestyle = "--", linewidth = "1")
		# donchian
		if (flag["param"]["judge_signal"]["BUY"] == "donchian") or (flag["param"]["judge_signal"]["SELL"] == "donchian"):
			plt.plot(chart.Date, chart.Donchian_h, color = "blue",label ="dc_h_" + str(flag["param"]["buy_term"]), linestyle = "--", linewidth = "1")
			plt.plot(chart.Date, chart.Donchian_l, color = "blue",label ="dc_l_" + str(flag["param"]["sell_term"]), linestyle = "--", linewidth = "1")
		# SMA
		plt.plot(chart.Date, chart.SMA1, color = "yellow",label ="SMA_" + str(flag["param"]["sma1_term"]), linestyle = "-", linewidth = "2")
		plt.plot(chart.Date, chart.SMA2, color = "green",label ="SMA_" + str(flag["param"]["sma2_term"]), linestyle = "-", linewidth = "2")
		# Close_price
		plt.plot(chart.Date, chart.Close_price, color = "red" , label ="close_price", linestyle = "-", linewidth = "2" )
		#mpl_finance.candlestick_ohlc(ax, chart.Price_ohlc, width=2, alpha=0.5, colorup='r', colordown='b')
		# position
		plt.plot(chart.Date, chart.Position_price, color = "black",label ="position_price", linestyle = "-", linewidth = "1")
		plt.plot(chart.Date, chart.Stop_price, color = "grey",label ="stop_price", linestyle = ":", linewidth = "1")


		#plt.plot( chart.Date, chart.Close_price )
		#plt.plot( chart.Date, chart.Position_price )
		plt.ylabel("Price")
		plt.ylim([chart.Close_price.min(), chart.Close_price.max()])    # y方向の描画範囲を指定
		plt.legend(loc=0)


		# 出来高もグラフに追加
		plt.subplot2grid((5, 5), (3, 0), colspan = 5, rowspan = 1)
		plt.bar(chart.Date, chart.Volume,label ="Volume",width=0.05)
		plt.subplot2grid((5, 5), (4, 0), colspan = 5, rowspan = 1)
		plt.plot(chart.Date, chart.vroc, color = "blue",label ="VROC", linestyle = "-", linewidth = "1")
		plt.plot(chart.Date, chart.vroc_thrsh, color = "red",label ="VROC_THRESHOLD", linestyle = "-", linewidth = "1")

		# グラフ画像保存
		file_name = str(format(datetime.now().strftime("%Y-%m-%d-%H-%M"))) + "-price_graph.png"
		plt.savefig(file_name)
		
		# リターン分布の相対度数表を作る
		plt.clf()

		plt.subplot(1,1,1)
		plt.hist( records.Rate,50,rwidth=0.9)
		plt.axvline( x=0,linestyle="dashed",label="Return = 0" )
		plt.axvline( records.Rate.mean(), color="orange", label="AverageReturn" )
		plt.legend() # 凡例を表示
		#plt.show()

		# グラフ描画
		#plt.show()

		# グラフ画像保存
		file_name = str(format(datetime.now().strftime("%Y-%m-%d-%H-%M"))) + "-plot.png"
		plt.savefig(file_name)

	return result
