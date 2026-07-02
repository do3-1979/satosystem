#!/usr/bin/env python3
"""ペーパートレード実行（実発注は一切行わない）。

想定運用: 4H足確定の数分後にcronで `python run_paper.py --once` を実行。
例 (UTC): 5 0,4,8,12,16,20 * * *  cd .../satosystem && python3 run_paper.py --once
"""
import argparse
import json

from cta.config import load_config
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
    result = trader.run_once(refresh=not args.no_refresh)
    print(json.dumps(result, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
