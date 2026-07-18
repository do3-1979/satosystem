#!/usr/bin/env python3
"""ペーパートレード実行（実発注は一切行わない）。

想定運用: 4H足確定の数分後にcronで `python run_paper.py --once` を実行。
例 (UTC): 5 0,4,8,12,16,20 * * *  cd .../satosystem && python3 run_paper.py --once

異常時（実行エラー・サーキットブレーカー新規発動）はメール通知する
（cta/notify.py、設定は `.gmail` が無ければ静かにスキップする）。
"""
import argparse
import json
import traceback

from cta.config import load_config
from cta.notify import send_alert
from cta.paper import PaperTrader


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/default.ini")
    ap.add_argument("--once", action="store_true", default=True)
    ap.add_argument("--no-refresh", action="store_true",
                    help="キャッシュ更新をスキップ（テスト用）")
    args = ap.parse_args()

    cfg = load_config(args.config)
    trader = PaperTrader(cfg)
    was_halted = trader.breaker.halted

    try:
        result = trader.run_once(refresh=not args.no_refresh)
    except Exception as e:
        send_alert("run_paper.py 実行エラー",
                  f"ペーパートレードのサイクル実行中に例外が発生しました。\n\n"
                  f"{traceback.format_exc()}")
        raise

    if not was_halted and result.get("halted"):
        send_alert("サーキットブレーカー発動（新規）",
                  f"ペーパートレードのサーキットブレーカーが発動しました。\n"
                  f"人手で確認するまで自動再開しません。\n\n"
                  f"{json.dumps(result, indent=1, ensure_ascii=False)}")

    print(json.dumps(result, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
