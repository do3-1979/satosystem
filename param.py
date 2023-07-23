#--- システムパラメタ --------------------
is_back_test = True      # back test フラグ
is_total_test = False     # back test フラグ
#start_period = None      # back test フラグ
start_period = "2023/2/1 0:00"       # back test フラグ
#end_period = None                     # back test フラグ
end_period = "2023/3/30 21:00"         # back test フラグ
# TODO 6/4 end_period が現実時間より後だとget_last_priceの応答が帰らない

#--- 可変パラメタ --------------------

#--- 時間軸 --------------------

#chart_sec = 60          #  1分足を使用
#chart_sec = 300         #  5分足を使用
#chart_sec = 1800        # 30分足を使用
chart_sec = 7200         # 2時間足を使用
#chart_sec = 3600        # 1時間足を使用

#--- エントリー判定 --------------------
# TODO ボラティリティ、ストップ幅、分割数は上昇期、下降期で異なる。毎月見直すのが有効
buy_term =	16           # 買いエントリーのブレイク期間の設定
sell_term = 16           # 売りエントリーのブレイク期間の設定
volatility_term = 6     # 平均ボラティリティの計算に使う期間

pivot_term = 1           # PIVOTの期間設定
sma1_term = 9            # 移動平均線１（早い）期間の設定
sma2_term = 180          # 移動平均線２（遅い）期間の設定

vroc_term = 50           # 出来高の変化率の設
                         # VROC＝（最新の足の出来高 － n本前の足の出来高）÷ n本前の足の出来高 × 100
                         # https://manabu-blog.com/fx-volime-rate-of-change
vroc_thrsh = 200         # 出来高変化率の閾値(%)

pvo_s_term = 5           # 出来高オシレータのEMA（短)の期間
pvo_l_term = 70          # 出来高オシレータのEMA（長)の期間
pvo_thrsh = 20          # 出来高オシレータの閾値(%)

# TODO 2023/5/30 出来高は、bybitとcryptowatchでまったく違う > DONE
# cryptowatchから価格取得するのをbybitからに変更したほうがいい
# cryptowatchとbybitの価格取得部分をIF化して今のAPIを維持を検討する
# cryptowatchで見ても、2023/4月以前と以後で出来高がぜんぜん違う
# bybitとcryptowatchの出来高は相関がない　交換所ごとに傾向が違うと思われる

# TODO 2023/7/23 基本的な戦略の見直し方
# ・トレンドフォローであること
# ・パラボリックSARでストップをフォローし、利益を確保すること
# ・ストップ値は1min単位で最新値を取得し判断している
# ・エントリー、追加ポジ取得は2hごとに判断している > エントリ前に動ききってしまい、
# 　エントリー直後に反転した場合に大損するリスクがある
# TODO エントリーを1min単位で判断する
# ・判断するためには毎回シグナルの計算が必要

# TODO 2023/7/23 長期間(6か月)で大トレンドだけ拾えるようなシグナルのフィルタが必要
# どうやって？
# ＞各パラメタ調整の意味から考える
# buy_temr, sell_term → 期間が長くなるほど、静　→　動　の変化を検出する
# volatilyty_term = 期間が長くなるほど、出来高の変化を受けにくい　出来高が大きい時ほど小さなエントリになる
# trade_risk = 高くするほど、フォロー失敗したときの損失が大きく、削られる
# entry_time = 分割するほど、フォロー失敗したときのリスクが減る
# vroc = 大きくするほど、出来高変化率をフィルタできる
#
# 

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
lot_limit_lower = 0.0001  # 注文できる最小lot数計算倍率

#--- ピラミッディング制御 --------------------

trade_risk = 3.00        # 1トレードあたり口座の何％まで損失を許容するか
entry_times = 18         # 何回に分けて追加ポジションを取るか
entry_range = 2          # 何レンジごとに追加ポジションを取るか

#--- ストップ制御 --------------------

stop_range = 1           # 何レンジ幅にストップを入れるか
stop_AF = 0.01           # 加速係数
stop_AF_add = 0.07       # 加速係数を増やす度合
stop_AF_max = 0.40       # 加速係数の上限


#--- 固定パラメタ --------------------

symbol_type = "BTC/USD"     # 扱う通貨ペア
#symbol_type = "ETH/USD"     # 扱う通貨ペア
log_unit = "USD"            # 単位
balance_limit = 10          # 注文できる最小証拠金[USD]

levarage = 100              # レバレッジ倍率の設定
start_funds = 0.007 * 25000 # シミュレーション時の初期資金[USD]

wait = 60                   # ループの待機時間
order_retry_times = 2       # オーダー時の待機時間倍率
slippage = 0.001            # 手数料・スリッページ

stop_neighbor = 300         # リミット超過時の追従用閾値[usd]


line_notify_time_hour = [11] # LINE通知する時刻（配列可）[時] ※11時前後が変動が多い
line_notify_profit_rate = 100 # 利益が資産の一定割合以上出たらLINE通知する[%]

#EOF
