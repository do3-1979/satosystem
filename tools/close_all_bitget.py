#!/usr/bin/env python3
"""Bitgetの全ポジションを成行で決済する運用ツール（撤退・緊急停止用）。

■なぜ必要か
  Bitgetは2026-08-03に日本居住者向けサービスの終了を発表した。
    2026-11-01 11:00 JST クローズオンリー化（新規建て不可＝BOT機能停止）
    2026-12-31 11:00 JST 残ポジションを強制決済（決済価格を選べない）
  期限までに自分の意思で決済し、資金を出金しきる必要がある。

■設計方針
  発注経路は run_live.py と**完全に同じ**ものを使う。
    decision.plan_flatten_orders() で注文を組み立て、
    BitgetLiveExecutor.place_order() で送る（clientOidによる冪等性も同じ）。
  ここで独自の発注処理を書くと、gen2で起きた「経路が二つに分かれて
  片方だけ挙動が違う」事故を再発させるため、絶対に書かない。

■安全装置
  run_live.py と同じく --live と --i-understand-this-uses-real-money の
  両方が無ければドライラン（発注APIを一切呼ばない）。

  python tools/close_all_bitget.py                    # 決済計画の表示のみ
  python tools/close_all_bitget.py --live --i-understand-this-uses-real-money
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cta import decision
from cta.config import load_config
from cta.live_execution import BitgetLiveExecutor


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/live.ini")
    ap.add_argument("--api-key-file",
                    default="/home/satoshi/work/satosystem/src/.api_key")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--i-understand-this-uses-real-money", action="store_true",
                    dest="confirm")
    args = ap.parse_args()

    live = args.live and args.confirm
    if args.live and not args.confirm:
        print("[中止] --live には --i-understand-this-uses-real-money が必要です",
              file=sys.stderr)
        return 2

    cfg = load_config(args.config)
    keys = json.load(open(args.api_key_file))
    ex = BitgetLiveExecutor(keys["api_bitget_key"], keys["api_bitget_secret"],
                            keys["api_bitget_passphrase"])

    equity = ex.fetch_equity_usd()
    # 取引所の実ポジションが唯一の真実。内部帳簿は参照しない
    real_pos = ex.reconcile_positions(cfg.symbols, {})["exchange_positions"]
    open_pos = {s: q for s, q in real_pos.items() if q}

    # 決済は成行なので、キャッシュのバー終値ではなく板の現在値を基準にする
    prices = {}
    for sym in open_pos:
        prices[sym] = float(ex.exchange.fetch_ticker(sym)["last"])

    orders = decision.plan_flatten_orders(open_pos, prices, reason="japan_exit")

    print(f"口座評価額: ${equity:.2f}   保有: {len(open_pos)}銘柄")
    print(f"モード    : {'★実発注★' if live else 'ドライラン（発注しません）'}")
    print(f"{'銘柄':<24}{'現在数量':>14}{'決済':>6}{'数量':>14}{'概算USD':>10}")
    total = 0.0
    for od in orders:
        n = abs(od.qty) * od.signal_price
        total += n
        print(f"{od.symbol:<24}{open_pos[od.symbol]:>+14.8f}"
              f"{'買戻' if od.qty > 0 else '売り':>6}{od.qty:>+14.8f}{n:>10.2f}")
    print(f"{'合計ノーショナル':<24}{'':>34}{total:>10.2f}")

    if not orders:
        print("\n決済すべきポジションはありません。")
        return 0
    if not live:
        print("\n実行するには --live --i-understand-this-uses-real-money を付けてください。")
        return 0

    bar = int(time.time())
    fills, errors = [], []
    for od in orders:
        try:
            f = ex.place_order(od, bar_epoch=bar,
                               min_notional_usd=cfg.min_notional_usd)
            fills.append(f)
            print(f"  約定 {f.symbol:<22} {f.qty:+.8f} @ {f.fill_price:.4f}")
        except Exception as e:
            errors.append(f"{od.symbol}: {e}")
            print(f"  失敗 {od.symbol:<22} {e}")

    after = ex.reconcile_positions(cfg.symbols, {})["exchange_positions"]
    left = {s: q for s, q in after.items() if q}
    print(f"\n決済後の残ポジション: {left or 'なし'}")
    print(f"口座評価額: ${ex.fetch_equity_usd():.2f}  "
          f"利用可能: ${ex.fetch_available_usd():.2f}")
    if errors or left:
        print("\n【要手動確認】決済しきれていません:", errors)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
