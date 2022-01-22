#--- システムパラメタ --------------------
is_back_test = False       # back test フラグ
is_total_test = False     # back test フラグ
#start_period = None      # back test フラグ
start_period = "2021/12/1 0:00"       # back test フラグ
#end_period = None                     # back test フラグ
end_period = "2022/2/1 23:00"         # back test フラグ


#--- 可変パラメタ --------------------

#--- 時間軸 --------------------

#chart_sec = 60          #  1分足を使用
#chart_sec = 300         #  5分足を使用
#chart_sec = 1800        # 30分足を使用
chart_sec = 7200         # 2時間足を使用
#chart_sec = 3600        # 1時間足を使用

#--- エントリー判定 --------------------

buy_term =	16           # 買いエントリーのブレイク期間の設定
sell_term = 16           # 売りエントリーのブレイク期間の設定
volatility_term = 5	     # 平均ボラティリティの計算に使う期間

pivot_term = 1           # PIVOTの期間設定
sma1_term = 9            # 移動平均線１（早い）期間の設定
sma2_term = 180          # 移動平均線２（遅い）期間の設定

vroc_term = 50           # 出来高の変化率の設
                         # VROC＝（最新の足の出来高 － n本前の足の出来高）÷ n本前の足の出来高 × 100
                         # https://manabu-blog.com/fx-volime-rate-of-change
vroc_thrsh = 200         # 出来高変化率の閾値(%)

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
lot_limit_lower = 0.090  # 注文できる最小lot数計算倍率

#--- ピラミッディング制御 --------------------

trade_risk = 1.90        # 1トレードあたり口座の何％まで損失を許容するか
entry_times = 6         # 何回に分けて追加ポジションを取るか
entry_range = 2          # 何レンジごとに追加ポジションを取るか

#--- ストップ制御 --------------------

stop_range = 4           # 何レンジ幅にストップを入れるか
stop_AF = 0.01           # 加速係数
stop_AF_add = 0.15       # 加速係数を増やす度合
stop_AF_max = 0.20       # 加速係数の上限


#--- 固定パラメタ --------------------

symbol_type = "BTC/USD"     # 扱う通貨ペア
#symbol_type = "ETH/USD"     # 扱う通貨ペア
log_unit = "USD"            # 単位
balance_limit = 10          # 注文できる最小証拠金[USD]

levarage = 100              # レバレッジ倍率の設定
start_funds = 0.040 * 43000 # シミュレーション時の初期資金[USD]

wait = 60                   # ループの待機時間
order_retry_times = 2       # オーダー時の待機時間倍率
slippage = 0.001            # 手数料・スリッページ

stop_neighbor = 300         # リミット超過時の追従用閾値[usd]


line_notify_time_hour = [11] # LINE通知する時刻（配列可）[時] ※11時前後が変動が多い
line_notify_profit_rate = 20 # 利益が資産の一定割合以上出たらLINE通知する[%]

#EOF
