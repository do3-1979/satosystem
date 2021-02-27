#--- システムパラメタ --------------------
is_back_test = True       # back test フラグ
is_total_test = False     # back test フラグ
#start_period = None      # back test フラグ
#start_period = "2019/10/28 0:00"      # back test フラグ
#start_period = "2020/7/28 0:00"       # back test フラグ
start_period = "2020/12/1 0:00"       # back test フラグ
#end_period = None                     # back test フラグ
end_period = "2021/2/26 23:00"         # back test フラグ


#--- 可変パラメタ --------------------

#--- 時間軸 --------------------

#chart_sec = 60          #  1分足を使用
#chart_sec = 300         #  5分足を使用
#chart_sec = 1800        # 30分足を使用
chart_sec = 7200         # 2時間足を使用
#chart_sec = 3600        # 1時間足を使用

#--- エントリー判定 --------------------

buy_term =	17           # 買いエントリーのブレイク期間の設定
sell_term = 30           # 売りエントリーのブレイク期間の設定
volatility_term = 8	     # 平均ボラティリティの計算に使う期間

pivot_term = 1           # PIVOTの期間設定
sma1_term = 7            # 移動平均線１（早い）期間の設定
sma2_term = 180          # 移動平均線２（遅い）期間の設定
judge_line={
  "BUY" : "S2",          # ブレイク判断　PiVOT S2で買い
  "SELL": "R2"	         # ブレイク判断　PiVOT R2で売り
}

judge_price={
  "BUY" : "close_price", # ブレイク判断　高値（high_price)か終値（close_price）を使用
  "SELL": "close_price"	 # ブレイク判断　安値 (low_price)か終値（close_price）を使用
}

judge_signal={
#  "BUY" : "pivot",      # 買い判断シグナル
  "BUY" : "donchian",    # 買い判断シグナル
#  "BUY" : "sma_cross",  # 買い判断シグナル
#  "SELL": "pivot"       # 売り判断シグナル
  "SELL": "donchian"     # 売り判断シグナル
#  "SELL": "sma_cross"   # 売り判断シグナル
}

judge_volatility_ratio = 0.1000 # ボラティリティの終値比の下限値。下回った場合のみエントリ
lot_limit_lower = 0.030  # 注文できる最小lot数計算倍率

#--- ピラミッディング制御 --------------------

trade_risk = 0.50        # 1トレードあたり口座の何％まで損失を許容するか
entry_times = 10         # 何回に分けて追加ポジションを取るか
entry_range = 2          # 何レンジごとに追加ポジションを取るか

#--- ストップ制御 --------------------

stop_range = 4           # 何レンジ幅にストップを入れるか
stop_AF = 0.02           # 加速係数
stop_AF_add = 0.02       # 加速係数を増やす度合
stop_AF_max = 0.30       # 加速係数の上限

#--- 固定パラメタ --------------------

symbol_type = "BTC/USD"     # 扱う通貨ペア
log_unit = "USD"            # 単位
balance_limit = 10          # 注文できる最小証拠金[USD]

levarage = 100              # レバレッジ倍率の設定
start_funds = 0.017 * 30000 # シミュレーション時の初期資金[USD]
#start_funds = 0.10 * 12000 # シミュレーション時の初期資金[USD]

wait = 300                  # ループの待機時間
order_retry_times = 3       # オーダー時の待機時間倍率
slippage = 0.001            # 手数料・スリッページ

line_notify_time_hour = [6,13,21] # 6時、13時、21時にLINE通知

#EOF
