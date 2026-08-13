#!/usr/bin/env python3
"""実発注トレーダーの起動スクリプト（Bitget）。

安全のため、実発注には **--live と --i-understand-this-uses-real-money の
両方** が必要。どちらか欠けるとドライラン（発注APIを一切呼ばない）で動く。

  python run_live.py                    # ドライラン（既定・安全）
  python run_live.py --dry-run --verbose # 何を発注するか一覧表示
  python run_live.py --live --i-understand-this-uses-real-money
"""
import argparse
import json
import sys
import traceback

from cta.config import load_config
from cta.live_execution import BitgetLiveExecutor
from cta.live_trader import LiveTrader
from cta.notify import send_alert


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/default.ini")
    ap.add_argument("--api-key-file", default="/home/satoshi/work/satosystem/src/.api_key")
    ap.add_argument("--live", action="store_true", help="実発注を有効化")
    ap.add_argument("--i-understand-this-uses-real-money", action="store_true",
                    dest="confirm", help="--live と併用が必須")
    ap.add_argument("--dry-run", action="store_true",
                    help="全経路を通すが発注APIは呼ばない")
    ap.add_argument("--max-capital", type=float, default=None,
                    help="資金上限USD（既定はconfigのinit_capital_usd）")
    ap.add_argument("--no-refresh", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    live = args.live and args.confirm
    if args.live and not args.confirm:
        print("[中止] --live には --i-understand-this-uses-real-money が必要です",
              file=sys.stderr)
        return 2

    cfg = load_config(args.config)
    if cfg.is_etf:
        print("[中止] run_live.py はBitget(暗号資産)専用です。ETFはIBKR実装後に対応",
              file=sys.stderr)
        return 2

    keys = json.load(open(args.api_key_file))
    executor = BitgetLiveExecutor(keys["api_bitget_key"], keys["api_bitget_secret"],
                                  keys["api_bitget_passphrase"])
    trader = LiveTrader(cfg, executor, enable_live=live, dry_run=args.dry_run,
                        max_live_capital_usd=args.max_capital)

    mode = "★実発注★" if live and not args.dry_run else "ドライラン(発注しません)"
    print(f"=== モード: {mode} / config {cfg.config_sha1} ===")
    try:
        r = trader.run_once(refresh=not args.no_refresh)
    except Exception:
        send_alert("run_live.py 実行エラー", traceback.format_exc())
        raise
    print(json.dumps(r, indent=1, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
