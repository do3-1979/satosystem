import numpy as np
import param as prm

# デフォルトのパラメータはparam.pyから取得
#---------------------------------------------------------------------------------------------
chart_sec_list        = [ prm.chart_sec ] 		                # 時間軸
buy_term_list         = [ prm.buy_term ]                        # 上値ブレイクアウトの期間
sell_term_list        = [ prm.sell_term ]                       # 下値ブレイクアウトの期間
volatility_term_list  = [ prm.volatility_term ] 				# ボラティリティの期間
stop_range_list       = [ prm.stop_range ]				  	    # ストップレンジの幅
trade_risk_list       = [ prm.trade_risk ] 				 	    # 1トレード当たりの損失許容の幅
entry_times_list      = [ prm.entry_times ] 					# 分割回数の幅
entry_range_list      = [ prm.entry_range ]						# 追加ポジションの幅
pivot_term_list       = [ prm.pivot_term ]		 			    # PIVOTの期間設定
sma1_term_list        = [ prm.sma1_term ]					  	# 移動平均線（速） 
sma2_term_list        = [ prm.sma2_term ]					    # 移動平均線（遅）
vroc_term_list        = [ prm.vroc_term ]					    # 出来高変化率の期間
vroc_thrsh_list       = [ prm.vroc_thrsh ]					    # 出来高変化率の閾値
pvo_s_term_list       = [ prm.pvo_s_term ]					    # 出来高オシレータの短期間
pvo_l_term_list       = [ prm.pvo_l_term ]					    # 出来高オシレータの長期間
pvo_thrsh_list        = [ prm.pvo_thrsh ]					    # 出来高オシレータの閾値
judge_volatility_ratio_list = [ prm.judge_volatility_ratio ]    # ボラティリティ終値比
stop_AF_list          = [ prm.stop_AF ] 						# 加速係数
stop_AF_add_list      = [ prm.stop_AF_add ]						# 加速係数を増やす度合
stop_AF_max_list      = [ prm.stop_AF_max ]				    	# 加速係数の上限
lot_limit_lower_list  = [ prm.lot_limit_lower ]					# 最低注文lot数

# バックテストのパラメーター設定(コメントアウトを外して使う)
#---------------------------------------------------------------------------------------------
#chart_sec_list  = { 7200, 3600, 300 } 		    # テストに使う時間軸
#buy_term_list   = np.arange( 3, 30, 1 )     	# テストに使う上値ブレイクアウトの期間
#sell_term_list  = np.arange( 3, 30, 1 ) 	    # テストに使う下値ブレイクアウトの期間
#volatility_term_list  = np.arange( 5, 30, 1 ) 	# テストに使うボラティリティの期間
#stop_range_list  = np.arange( 1,10,1 )		    # テストに使うストップレンジの幅
#trade_risk_list  = np.arange( 0.10, 2.05, 0.05 ) 	# テストに使う1トレード当たりの損失許容の幅
#entry_times_list  = np.arange( 10,50,2 ) 	    # テストに使う分割回数の幅
#entry_range_list  = np.arange( 1,6,1 )		    # テストに使う追加ポジションの幅
#pivot_term_list  = np.arange( 1,10,1 ) 		# PIVOTの期間設定
#sma1_term_list = np.arange( 5,15,1 )		    # 移動平均線（速） 
#sma2_term_list = np.arange( 100,200,10 )		# 移動平均線（遅）
#vroc_term_list = np.arange( 10,100,10 )			# 出来高変化率の期間
#vroc_thrsh_list = np.arange( 150,250,30 )		# 出来高変化率の閾値
#pvo_s_term_list = np.arange( 1,20,1 )			# 出来高オシレータの短期間
#pvo_l_term_list = np.arange( 50,150,10 )		# 出来高オシレータの長期間
#pvo_thrsh_list = np.arange( 20,150,10 )		# 出来高オシレータの閾値
judge_line_list = [
	{"BUY":"S2","SELL":"R2"},				    # サポートに第2ラインを使用
#	{"BUY":"S1","SELL":"R1"},				    # サポートに第1ラインを使用
] 
judge_price_list = [
	{"BUY":"close_price","SELL":"close_price"},	# ブレイクアウト判定に終値を使用
#	{"BUY":"low_price","SELL":"high_price"},	# ブレイクアウト判定に終値を使用
]
judge_signal_list = [
	{"BUY":"donchian","SELL":"donchian"},		# シグナルはドンチャンチャンネル
#	{"BUY":"pivot","SELL":"pivot"},				# シグナルはPIVOT
#	{"BUY":"sma_cross","SELL":"sma_cross"}		# シグナルは移動平均線によるDC/GC
]
#judge_volatility_ratio_list = np.arange( 0.0050,0.0250,0.0010 )    # ボラティリティ終値比
#stop_AF_list = np.arange( 0.01,0.02,0.001) 		# 加速係数
stop_AF_add_list = np.arange( 0.01,0.20,0.005) 	# 加速係数を増やす度合
stop_AF_max_list = np.arange( 0.15,0.90,0.05) 	# 加速係数の上限

#lot_limit_lower_list = np.arange( 0.030,0.100,0.010)

"""
	{"START":"2018/7/1 0:00","END":"2018/8/1 0:00"},
	{"START":"2018/8/1 0:00","END":"2018/9/1 0:00"},
	{"START":"2018/9/1 0:00","END":"2018/10/1 0:00"},
	{"START":"2018/10/1 0:00","END":"2018/11/1 0:00"},
	{"START":"2018/11/1 0:00","END":"2018/12/1 0:00"},
	{"START":"2018/12/1 0:00","END":"2019/1/1 0:00"},
	{"START":"2019/1/1 0:00","END":"2019/2/1 0:00"},
	{"START":"2019/2/1 0:00","END":"2019/3/1 0:00"},
	{"START":"2019/3/1 0:00","END":"2019/4/1 0:00"},
	{"START":"2019/4/1 0:00","END":"2019/5/1 0:00"},
	{"START":"2019/5/1 0:00","END":"2019/6/1 0:00"},
	{"START":"2019/6/1 0:00","END":"2019/7/1 0:00"},
	{"START":"2019/7/1 0:00","END":"2019/8/1 0:00"},
	{"START":"2019/8/1 0:00","END":"2019/9/1 0:00"},
	{"START":"2019/9/1 0:00","END":"2019/10/1 0:00"},
	{"START":"2019/10/1 0:00","END":"2019/11/1 0:00"},
	{"START":"2019/11/1 0:00","END":"2019/12/1 0:00"},
	{"START":"2019/12/1 0:00","END":"2020/1/1 0:00"},
	{"START":"2020/1/1 0:00","END":"2020/2/1 0:00"},
	{"START":"2020/2/1 0:00","END":"2020/3/1 0:00"},
"""
#	{"START":"2019/11/1 0:00","END":"2020/3/11 23:00"},
#	{"START":"2019/11/1 0:00","END":"2020/3/11 23:00"},
period_list = [
	{"START":"2023/1/1 0:00","END":"2023/8/14 21:00"},
]

# テスト総数
chart_sec_len = len(chart_sec_list)
buy_term_len = len(buy_term_list)
sell_term_len = len(sell_term_list)
volatility_term_len = len(volatility_term_list)
stop_range_len = len(stop_range_list)
trade_risk_len = len(trade_risk_list)
entry_times_len = len(entry_times_list)
entry_range_len = len(entry_range_list)
pivot_term_len = len(pivot_term_list)
sma1_term_len = len(sma1_term_list)
sma2_term_len = len(sma2_term_list)
vroc_term_len = len(vroc_term_list)
vroc_thrsh_len = len(vroc_thrsh_list)
pvo_s_term_len = len(pvo_s_term_list)
pvo_l_term_len = len(pvo_l_term_list)
pvo_thrsh_len = len(pvo_thrsh_list)
judge_line_len = len(judge_line_list)
judge_price_len = len(judge_price_list)
judge_signal_len = len(judge_signal_list)
judge_volatility_ratio_len = len(judge_volatility_ratio_list)
stop_AF_max_len = len(stop_AF_max_list)
stop_AF_len = len(stop_AF_list)
stop_AF_add_len = len(stop_AF_add_list)
lot_limit_lower_len = len(lot_limit_lower_list)

total_test_num = \
	chart_sec_len * \
	buy_term_len * \
	sell_term_len * \
	volatility_term_len * \
	stop_range_len * \
	trade_risk_len * \
	entry_times_len * \
	entry_range_len * \
	pivot_term_len * \
	sma1_term_len * \
	sma2_term_len * \
	vroc_term_len * \
	vroc_thrsh_len * \
	pvo_s_term_len * \
	pvo_l_term_len * \
	pvo_thrsh_len * \
	judge_line_len * \
	judge_price_len * \
	judge_signal_len * \
	judge_volatility_ratio_len * \
	stop_AF_max_len * \
	stop_AF_len * \
	stop_AF_add_len * \
	lot_limit_lower_len

#---------------------------------------------------------------------------------------------
