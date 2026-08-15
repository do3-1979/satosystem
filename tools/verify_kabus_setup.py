#!/usr/bin/env python3
"""kabuステーションAPIの疎通と設定の妥当性を検証する（発注は一切しない）。

実発注を始める前に必ず通すこと。確認するのは以下:
  1. kabuステーションが起動しAPIサーバが応答するか
  2. APIトークンを取得できるか
  3. 全銘柄の**売買単位(TradingUnit)**を取得し、configの lot_sizes と一致するか
     → ここがずれたまま発注すると数量が桁違いになる。yfinanceは売買単位を
       持たないため、取引所の値が唯一の正解。
  4. その売買単位で、現在の資金で全銘柄を保有できるか（分散が崩れないか）
  5. 買付余力と保有ポジション

使い方（Windows側のWSLから。kabuステーションを起動しておくこと）:
  python tools/verify_kabus_setup.py --config config/etf_jp.ini
  python tools/verify_kabus_setup.py --config config/etf_jp.ini --sandbox
"""
import argparse
import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cta.config import load_config
from cta.kabus_execution import KabusExecutor, KabusOrderError


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/etf_jp.ini")
    ap.add_argument("--sandbox", action="store_true",
                    help="検証環境(ポート18081)に接続する")
    ap.add_argument("--base-url", default=None)
    args = ap.parse_args()

    cfg = load_config(args.config)
    api_pw = os.environ.get("KABUS_API_PASSWORD") or \
        getpass.getpass("APIパスワード: ")

    ex = KabusExecutor(api_pw, order_password="",  # 照会のみなので注文PWは不要
                       base_url=args.base_url, sandbox=args.sandbox)

    print(f"接続先: {ex.base}")
    try:
        ex.ensure_token()
        print("① 疎通・トークン取得: OK")
    except Exception as e:
        print(f"① 疎通・トークン取得: 失敗 -> {e}")
        print("   kabuステーションが起動しているか、APIの利用申込が済んでいるか確認")
        return 1

    print("\n② 売買単位の照合")
    units, ng = {}, {}
    for sym in cfg.symbols:
        try:
            units[sym] = ex.fetch_trading_unit(sym)
        except KabusOrderError as e:
            print(f"   {sym}: 取得失敗 {e}")
            continue
        want = cfg.lot_size(sym)
        mark = "OK" if units[sym] == want else "★不一致"
        if units[sym] != want:
            ng[sym] = {"config": want, "exchange": units[sym]}
        print(f"   {sym:<10} 取引所={units[sym]:<4} config={want:<4} {mark}")
    if ng:
        print("\n   ★configの lot_sizes を次の値に直してください:")
        print("     lot_sizes = " +
              ", ".join(f"{s}:{v['exchange']}" for s, v in ng.items()))

    print("\n③ 資金と分散の成立性")
    try:
        cash = ex.fetch_available_usd()
    except Exception as e:
        cash = float(cfg.init_capital_usd)
        print(f"   買付余力の取得に失敗({e})のためconfigの{cash:,.0f}円で試算")
    n = len(cfg.symbols)
    per = cash / n if n else 0.0
    print(f"   買付余力 {cash:,.0f}円 / {n}銘柄 = 1銘柄あたり {per:,.0f}円")
    need, unaffordable = 0.0, []
    for sym in cfg.symbols:
        try:
            px = ex.fetch_price(sym)
        except Exception:
            continue
        lot_cost = px * units.get(sym, cfg.lot_size(sym))
        need = max(need, lot_cost * n)
        ok = lot_cost <= per
        if not ok:
            unaffordable.append((sym, lot_cost))
        print(f"   {sym:<10} 1単位={lot_cost:>12,.0f}円  {'OK' if ok else '★買えない'}")
    if unaffordable:
        print(f"\n   ★{len(unaffordable)}銘柄が1単位すら買えません。分散が崩れ、"
              f"戦略の前提（低相関資産の分散）が失われます。")
        print(f"   全銘柄を均等保有するのに必要な資金の目安: {need:,.0f}円")
        print("   対処: 資金を積む / 買えない銘柄を外す / 同資産の低価格銘柄へ置換")

    print("\n④ 保有ポジション")
    pos = ex.fetch_positions(cfg.symbols)
    held = {s: q for s, q in pos.items() if q}
    print(f"   {held or 'なし'}")

    print("\n判定:", "★要対処" if (ng or unaffordable) else "OK（実発注の前提を満たす）")
    return 1 if (ng or unaffordable) else 0


if __name__ == "__main__":
    sys.exit(main())
