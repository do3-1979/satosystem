from datetime import datetime
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
            data = get_price(chart_sec, flag)
            new_price = data[-2] # data[-1]は未確定の最新値
            stop_chk_price = data[-1]
            prev_price = last_data[-1]

            # 指定した時間になったらLINE通知
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

            # ストップと利幅をチェックする
            if flag["position"]["exist"]:
                flag = stop_position( stop_chk_price,last_data,flag )

                # 利益計算
                latest_price = stop_chk_price["close_price"]
                entry_price = int(round(flag["position"]["price"] * flag["position"]["lot"]))
                exit_price = int(round(latest_price * flag["position"]["lot"]))

                # 値幅の計算
                trade_cost = round( exit_price * slippage )
                buy_profit = exit_price - entry_price - trade_cost
                sell_profit = entry_price - exit_price - trade_cost
                profit = max(buy_profit, sell_profit)

                # 通知の判断[全資産の%]が閾値を超えたら通知する
                result = get_collateral(flag)
                balance = round(result['total'] * latest_price, 6)

                # 閾値と比較
                notify_thresh = round(profit * 100 / balance)
                if notify_thresh >= line_notify_profit_rate:
                    # 初回のみ通知
                    if profit_notified == False:
                        line_text = "\nポジション: " + flag["position"]["side"]
                        line_text = line_text + "\n現在の利益率: " + str(notify_thresh) +" %"
                        line_text = line_text + "\n利益: " + str(round(profit))
                        # LINE通知
                        line_notify(line_text)
                        # 通知済フラグ ON
                        profit_notified = True
            else:
                # ポジション解消で通知フラグをクリア
                profit_notified = False

            # 値更新されるまでループする
            if new_price["close_time"] == prev_price["close_time"]:
                time.sleep(time_wait)
                continue

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
