from datetime import datetime, timedelta
from logging import DEBUG
import time
import config_rt

# -------ログ機能--------
from logc import *
# -------資金管理機能--------
from pos_mng import *
# -------オーダー機能----
from order import *
# -------分析機能----
from anlyz import *

def daemon( price, last_data, flag, need_term, chart_log ):
    # パラメタ展開
    is_back_test = flag["param"]["is_back_test"]
    chart_sec = flag["param"]["chart_sec"]
    wait = flag["param"]["wait"]
    line_notify_time_hour = flag["param"]["line_notify_time_hour"]
    line_notify_profit_rate = flag["param"]["line_notify_profit_rate"]
    slippage = flag["param"]["slippage"]

    i = 0
    is_line_notified = False
    is_line_notify_time = False

    profit_notified = False
    is_need_update = False
    is_init_price = False
    prev_close_time = datetime.now()

    max_profit = 0

    #dbgflg = False

    while ( ( is_back_test == False ) or ( i < len(price) ) ):

        last_data_idx = 0

        if is_back_test is True:
            time_wait = 0
        else:
            time_wait = wait

        # ドンチャンの判定に使う期間分の安値・高値データを準備する
        if len(last_data) < need_term:
            if is_back_test is True:
                last_data.append(price[i])
                flag = log_price(price[i],flag)
                i += 1
                continue
            else:
                last_data_idx = -1 * (need_term - i + 1)
                last_data.append(price[last_data_idx])
                flag = log_price(price[last_data_idx],flag)
                i += 1
                continue

        # 価格を取得
        if is_back_test is True:
            data = price[i]  # バックテスト用
            new_price = data # バックテスト用
        else:
            # period経過したらget_priceで足を取得
            # period未満はwaitで規定の間隔で最新値のみ取得してストップ値と比較
            # allowanceは1分に1回までならチェック可能
            now_time = datetime.now()
            next_time = prev_close_time + timedelta( seconds = chart_sec )
            if now_time > next_time:
                is_need_update = True

            if is_need_update == True or is_init_price == False:
                data = get_price(chart_sec, flag)
                new_price = data[-2] # data[-1]は未確定の最新値
                stop_chk_price = data[-1]
                # 最新のclose_timeを保持
                prev_close_time = datetime.fromtimestamp( new_price["close_time"] )
                # 初回のみohlcを取得する
                if is_init_price == False:
                    is_init_price = True
            else:
                # 最新値を更新
                data = get_latest_price(chart_sec, flag)
                stop_chk_price = data[-1]

            ### YMDDBG デバッグ用初期状態設定
            """----------------------------------------------
            if dbgflg == False:
                flag["add-position"]["count"] = 1
                flag["position"]["lot"],flag["position"]["stop"] = 0.3356221, 500
                flag["position"]["exist"] = True
                flag["position"]["side"] = "BUY"
                flag["position"]["price"] = stop_chk_price["close_price"] - 2000
                dbgflg = True
            """
            #-----------------------------
            # 指定した時間になったらLINE通知
            #-----------------------------
            dt = datetime.now()
            is_line_notify_time = False
            for i in range(len(line_notify_time_hour)):
                if line_notify_time_hour[i] == dt.hour:
                    is_line_notify_time = True

            if (is_line_notify_time == True) and (is_line_notified == False):
                # 現在の時間、ポジション数、証拠金をLINEメッセージにする
                result_pos = get_position(flag)
                result_col = get_collateral(flag)
                line_text = "\n現在時刻： " + str(dt.strftime('%m/%d %H:%M'))
                line_text = line_text + "\n終値時刻： " + str(datetime.fromtimestamp(new_price["close_time"]).strftime('%H:%M')) + "\n高値： " + str(new_price["high_price"]) + "\n安値： " + str(new_price["low_price"]) + "\n終値： " + str(new_price["close_price"]) + "\n"
                line_text = line_text + "\nポジション:{}\nロット:{}\n拘束中証拠金:{}\n使用可能証拠金:{}\n".format(result_pos["side"],result_pos["lots"],round(result_col["used"],4),round(result_col["free"],4))
                # LINE通知
                line_notify(line_text)
                is_line_notified = True

            # 通知時間でなかったら通知済フラグをクリア
            if (is_line_notify_time == False) and (is_line_notified == True):
                is_line_notified = False

            #-----------------------------
            # ストップと利幅をチェックする
            #-----------------------------
            if flag["position"]["exist"]:
                ### 利幅を計算し、一定以上大きければ最新値にstop値を追従させる

                # 利益計算
                latest_price = stop_chk_price["close_price"]
                entry_price = int(round(flag["position"]["price"] * flag["position"]["lot"]))
                exit_price = int(round(latest_price * flag["position"]["lot"]))

                # 値幅の計算
                trade_cost = round( exit_price * slippage )
                buy_profit = 0
                sell_profit = 0
                if flag["position"]["side"] == "BUY":
                    buy_profit = exit_price - entry_price - trade_cost
                if flag["position"]["side"] == "SELL":
                    sell_profit = entry_price - exit_price - trade_cost
                profit = max(buy_profit, sell_profit)

                # 利益の記録
                max_profit = max(max_profit, profit)

                # 通知の判断[全資産の%]が閾値を超えたら通知する
                result = get_collateral(flag)
                balance = round(result['total'] * latest_price, 6)

                # 閾値と比較
                # balanceは利益も含んでるため、総資産からエントリ前の資産を引く必要がある
                # 総資産 = 総lot数 x 現在の価格
                # 利益 = 購入したlot数 x (現在の価格 - 平均取得単価)
                # エントリ時の資産 = 総資産 - 利益
                # 利益率 = ( 利益 / エントリ時の資産 ) x 100 [%]
                notify_thresh = round(profit * 100 / (balance - profit))

                out_log("時間：{}  現在利益：{:.2f} USD  現在資産：{:.2f} USD  利益率：{} %  瞬間最大利益：{:.2f} USD \n".format(str(datetime.now().strftime('%Y/%m/%d %H:%M')), profit, balance, notify_thresh, max_profit), flag)
                if notify_thresh >= line_notify_profit_rate:
                    # stop値を閾値に更新
                    flag = trail_stop_neighbor( stop_chk_price, last_data, flag )
                    log_price( stop_chk_price, flag ) 

                    # 初回のみ通知
                    if profit_notified == False:
                        line_text = "\nポジション： " + str(flag["position"]["side"])
                        line_text = line_text + "\n現在の利益率： " + str(notify_thresh) +" %"
                        line_text = line_text + "\n利益： " + str(round(profit))
                        # LINE通知
                        line_notify(line_text)
                        out_log(line_text, flag)
                        # 通知済フラグ ON
                        profit_notified = True
                
                # 更新したstop値で決済判定
                flag = stop_position( stop_chk_price,last_data,flag )

            else:
                # ポジション解消で通知フラグをクリア
                profit_notified = False
                max_profit = 0

            #-----------------------------
            # 値更新されるまでループする
            #-----------------------------
            # new_priceの時刻が前回と同じ場合があるため、保存済の最新値と時刻が同じなら再取得する
            if is_need_update == False:
                time.sleep(time_wait)
                continue
            else:
                # 保存済の最新地のclose timeと今回のclose timeが一致していたら再取得
                new_close_time = datetime.fromtimestamp( new_price["close_time"] )
                last_close_time = datetime.fromtimestamp( last_data[-1]["close_time"] )
        
                if new_close_time == last_close_time:
                    out_log("時刻未更新検出。再取得\n", flag)
                    time.sleep(time_wait)
                    continue
        
                # 更新フラグ初期化
                is_need_update = False

        flag = log_price(new_price,flag)

        # ポジションがある場合
        if flag["position"]["exist"] == True:
            flag = trail_stop( new_price,last_data,flag )
            flag = stop_position( new_price,last_data,flag )
            flag = close_position( new_price,last_data,flag )
            flag = add_position( new_price,last_data,flag )

        # ポジションがない場合
        else:
            flag = entry_signal( new_price,last_data,flag )

        # チャート用ログ
        if is_back_test == True:
            chart_log["records"]["date"].append(new_price["close_time_dt"])
            chart_log["records"]["close_price"].append(new_price["close_price"])
            if (flag["position"]["side"] == "BUY") and (flag["position"]["exist"] == True):
                position_price = flag["position"]["price"]
                stop_price = flag["position"]["price"] - flag["position"]["stop"]
            elif (flag["position"]["side"] == "SELL") and (flag["position"]["exist"] == True):
                position_price = flag["position"]["price"]
                stop_price = flag["position"]["price"] + flag["position"]["stop"]
            else:
                position_price = 0
                stop_price = 0

            chart_log["records"]["position_price"].append(position_price)
            chart_log["records"]["stop_price"].append(stop_price)
            chart_log["records"]["price_ohlc"].append(new_price)
            chart_log["records"]["Volume"].append(new_price["Volume"])
            chart_log["records"]["QuoteVolume"].append(new_price["QuoteVolume"])
            # SMAパラメタ
            sma1_term = flag["param"]["sma1_term"]
            sma2_term = flag["param"]["sma2_term"]
            sma1 = calc_sma( sma1_term, last_data, new_price["close_price"])
            sma2 = calc_sma( sma2_term, last_data, new_price["close_price"])
            chart_log["records"]["SMA1"].append(sma1)
            chart_log["records"]["SMA2"].append(sma2)
            # vrocパラメタ
            vroc_term = flag["param"]["vroc_term"]
            vroc = calc_vroc( vroc_term, last_data, new_price["Volume"])
            chart_log["records"]["vroc"].append(vroc)
            chart_log["records"]["vroc_thrsh"].append(flag["param"]["vroc_thrsh"])
            # PVO
            s_term = flag["param"]["pvo_s_term"]
            l_term = flag["param"]["pvo_l_term"]
            pvo = calc_pvo( s_term, l_term, last_data, data )
            chart_log["records"]["pvo"].append(pvo)
            chart_log["records"]["pvo_thrsh"].append(flag["param"]["pvo_thrsh"])
            # donchianパラメタ計算
            buy_term = flag["param"]["buy_term"]
            sell_term = flag["param"]["sell_term"]
            highest = max(i["high_price"] for i in last_data[ (-1* buy_term): ])
            lowest = min(i["low_price"] for i in last_data[ (-1* sell_term): ])
            chart_log["records"]["donchian_h"].append(highest)
            chart_log["records"]["donchian_l"].append(lowest)
            # PIVOTパラメタ
            PIVOT,R3,R2,R1,S1,S2,S3 = calc_pivot( last_data, flag )
            chart_log["records"]["R3"].append(R3)
            chart_log["records"]["R2"].append(R2)
            chart_log["records"]["R1"].append(R1)
            chart_log["records"]["S3"].append(S3)
            chart_log["records"]["S2"].append(S2)
            chart_log["records"]["S1"].append(S1)
            chart_log["records"]["PIVOT"].append(PIVOT)

        last_data.append( new_price )
        i += 1
        if is_back_test is False:
            del last_data[0]
        time.sleep(time_wait)
