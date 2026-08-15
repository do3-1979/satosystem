#!/usr/bin/env python3
"""東証ETFの価格データを「同じ資産を追う別系列」と突き合わせて検証する。

■なぜ必要か（cta/jp_repair.py だけでは足りない理由）
  jp_repair は「1日で2.5倍以上動いた」段差しか直せない。
  ところがYahooのデータには**それ未満の恒久的な水準シフト**も混ざる。
  実例: 1306.T は 2015-07-10 に +16.8% 跳ねてそのまま戻らない。
        同じTOPIXを追う 1305/1308/1348 は同日 +1.6%/+0.3%/+1.7% しか動いておらず、
        1306だけのデータ欠陥と確定した。これを含めると Sharpe が 0.82→0.87 に
        水増しされる（結論を変えるほどではないが、無自覚に使ってはいけない）。

  単日の閾値では捕まらないので、**同じ資産の別系列との相対乖離**で見る。

■使い方
  python tools/validate_jp_data.py --config config/etf_jp.ini
  異常があれば銘柄と日付を出す。対処は「その銘柄を同資産の別銘柄へ差し替える」。

■注意
  海外ETFを参照にする場合は必ず円換算し、lag+1で比較すること
  （東証15:00終値はNY前日終値を反映する）。これを忘れると為替と時差の
  ぶんが乖離として出て、健全な銘柄を誤って欠陥と判定する。
"""
import argparse
import os
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd

from cta import jp_repair
from cta.config import load_config

# 対象銘柄 -> (同資産の参照, 円換算が必要か)
#
# ★東証どうし(in_jpy=False)の比較だけが「合否判定」に使える。
#   同じ市場・同じ時刻・同じ通貨で同じ指数を追うため、乖離＝データ欠陥と言い切れる。
# ★海外参照(in_jpy=True)は**参考値**にとどめる。為替・時差・ロール手法の違いで
#   健全な銘柄でも数%の乖離が日常的に出るため、これで欠陥と判定すると誤検知になる。
#   （実際 1542/1671 を海外参照で判定させたら健全なのに警告が出た）
#
# 参照に使う銘柄自体が壊れていないことも前提。2558.Tは2026-06に桁化けがあるため
# 参照から外している。
PEERS = {
    "1306.T": (["1305.T", "1308.T", "1348.T"], False),
    "1308.T": (["1305.T", "1348.T"], False),
    "1305.T": (["1308.T", "1348.T"], False),
    "1547.T": (["1655.T"], False),
    "1655.T": (["1547.T"], False),
    "1540.T": (["1328.T"], False),
    "1326.T": (["1540.T", "1328.T"], False),
    "1542.T": (["SLV"], True),
    "1541.T": (["PPLT"], True),
    "1671.T": (["1699.T"], False),
    "1343.T": (["1476.T", "1488.T"], False),
}
# データ欠陥ではなく**実在の市場イベント**と確認済みの乖離。
# ここに載せないと毎回警告が出て、本物の欠陥が埋もれる（狼少年になる）。
# 追加するときは必ず「なぜ実在と言えるか」を書くこと。
VERIFIED_REAL = {
    # 2020年3〜4月の原油暴落。WTI先物がマイナス価格をつけた局面で、
    # 1671と1699はロール方法が違うため実際に乖離した（両者ともNAV乖離も発生）。
    # 価格系列そのものは壊れていない。
    ("1671.T", "2020-03-09"), ("1671.T", "2020-03-10"),
    ("1671.T", "2020-04-22"), ("1671.T", "2020-04-23"),
}

DAILY_THRESHOLD = 0.08     # 同資産どうしでこれ以上の単日乖離は異常
CUMULATIVE_WARN = 0.05     # 累積影響がこれを超えたら差し替えを検討
# 海外参照は市場差のノイズが乗るため、参考表示のみで合否には使わない
CROSS_MARKET_THRESHOLD = 0.15


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/etf_jp.ini")
    ap.add_argument("--start", default="2010-11-01")
    ap.add_argument("--threshold", type=float, default=DAILY_THRESHOLD)
    args = ap.parse_args()

    import yfinance as yf
    cfg = load_config(args.config)
    targets = [s for s in cfg.symbols if s in PEERS]
    skipped = [s for s in cfg.symbols if s not in PEERS]
    need = set(targets)
    fx_needed = False
    for s in targets:
        peers, in_jpy = PEERS[s]
        need.update(peers)
        fx_needed |= in_jpy
    if fx_needed:
        need.add("JPY=X")

    raw = yf.download(sorted(need), start=args.start, progress=False,
                      auto_adjust=True, threads=False)["Close"]
    fixed = {}
    for c in raw.columns:
        s = raw[c].dropna()
        if len(s) > 300:
            fixed[c], _ = jp_repair.repair_close_series(s)
    f = pd.DataFrame(fixed)
    usdjpy = f["JPY=X"] if "JPY=X" in f.columns else None

    print(f"{'銘柄':<9}{'参照':<20}{'異常日数':>9}{'最大乖離日':>13}{'乖離':>8}{'累積影響':>10}  判定")
    ng = []
    for sym in targets:
        peers, in_jpy = PEERS[sym]
        ps = [p for p in peers if p in f.columns]
        if sym not in f.columns or not ps:
            print(f"{sym:<9}参照データ不足のため検証できず")
            continue
        ref = f[ps].mean(axis=1)
        if in_jpy and usdjpy is not None:
            ref = ref * usdjpy
        sub = pd.concat([f[sym], ref], axis=1).dropna()
        sub.columns = ["s", "r"]
        r = np.log(sub).diff().dropna()
        # 海外参照は東証15時との時差があるため1日ずらして比べる
        dv = (r["s"] - r["r"].shift(1)) if in_jpy else (r["s"] - r["r"])
        dv = dv.dropna()
        thr = CROSS_MARKET_THRESHOLD if in_jpy else args.threshold
        big = dv[dv.abs() > thr]
        known = [d for d in big.index if (sym, str(d.date())) in VERIFIED_REAL]
        big = big.drop(known)          # 実在イベントと確認済みのものは除く
        cum = float(np.expm1(big.sum()))
        worst = dv.abs().idxmax() if len(dv) else None
        # 合否を出せるのは同市場の参照だけ。海外参照は参考表示にとどめる
        bad = (not in_jpy) and abs(cum) > CUMULATIVE_WARN
        if bad:
            ng.append((sym, cum))
        verdict = "★要差し替え検討" if bad else ("参考(市場が違う)" if in_jpy else "OK")
        print(f"{sym:<9}{'+'.join(ps):<20}{len(big):>9}"
              f"{str(worst.date()) if worst is not None else '-':>13}"
              f"{dv[worst] * 100:>+7.1f}%{cum * 100:>+9.1f}%  {verdict}")
        if bad:
            for d, v in big.items():
                print(f"          {d.date()} {v * 100:+.1f}%")

    if skipped:
        print(f"\n参照未定義（未検証）: {', '.join(skipped)}")
        print("  PEERS に同資産の別銘柄を追加すれば検証できます。")
    print("\n判定:", "★要対処" if ng else "OK")
    return 1 if ng else 0


if __name__ == "__main__":
    sys.exit(main())
