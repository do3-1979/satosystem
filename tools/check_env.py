#!/usr/bin/env python3
"""実行環境の照合ツール。

開発環境(WSL)と本番環境(RPi)でライブラリのバージョンが食い違うと、
片方でだけ壊れるバグが生まれる。実際に2回発生している:

  1. pandas 2.x(ns) / 3.x(us) の差で epoch秒が1000倍ずれた (2026-08-11)
  2. ccxt 4.2 / 4.5 の差で Bitgetのヘッジモード発注が全件拒否された (2026-08-15)
     → WSLでは成功、RPiでは全滅。本番機で実弾検証しなければ気づけなかった

使い方:
    python3 tools/check_env.py              # 現在の環境を表示
    python3 tools/check_env.py --expect production   # 本番想定と照合

【重要】WSL(Ubuntu22.04/Python3.10)とRPi(Ubuntu24.04/Python3.12)では
numpy2.5・pandas3.0がPython3.11以上を要求するため、そもそも同一版に
できない。**最終確認は必ず本番機(RPi)で行うこと。**
"""
import argparse
import importlib.metadata as md
import platform
import sys

# 本番(RPi)で実際に動いているバージョン。ここを唯一の基準とする
PRODUCTION = {
    "python": "3.12",          # メジャー.マイナーのみ比較
    "numpy": "2.5.0",
    "pandas": "3.0.3",
    "ccxt": "4.5.63",
    "yfinance": "1.5.2",
    "pytest": "9.1.1",
}

# 差異が実害を生んだ実績のあるパッケージ（食い違ったら強く警告する）
CRITICAL = {"pandas", "ccxt", "numpy"}


def current():
    out = {"python": ".".join(platform.python_version_tuple()[:2])}
    for pkg in PRODUCTION:
        if pkg == "python":
            continue
        try:
            out[pkg] = md.version(pkg)
        except md.PackageNotFoundError:
            out[pkg] = None
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--expect", choices=["production"], default=None)
    args = ap.parse_args()

    cur = current()
    print(f"実行環境: {platform.system()} {platform.machine()} / "
          f"Python {platform.python_version()}")
    print(f"{'パッケージ':>12s} {'現在':>12s} {'本番(RPi)':>12s}")
    diffs = []
    for pkg, want in PRODUCTION.items():
        got = cur.get(pkg)
        same = (got == want)
        mark = "  一致" if same else ("  ★要注意" if pkg in CRITICAL else "  差異")
        print(f"{pkg:>12s} {str(got):>12s} {want:>12s}{mark}")
        if not same:
            diffs.append((pkg, got, want))

    if not diffs:
        print("\n本番環境と一致しています。")
        return 0

    crit = [d for d in diffs if d[0] in CRITICAL]
    print(f"\n{len(diffs)}件の差異（うち実害実績あり: {len(crit)}件）")
    if crit:
        print("差異のあるパッケージは過去に片方だけ壊れるバグを起こしている。")
        print("**この環境でのテスト通過は本番の動作を保証しない。**")
        print("実発注に関わる変更は必ず本番機(RPi)で実弾検証すること。")
    return 1 if args.expect else 0


if __name__ == "__main__":
    sys.exit(main())
