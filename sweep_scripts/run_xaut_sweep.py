"""
H-XAUT-01: XAUTパラメータ最適化スイープ

【仮説】
現在のXAUT設定 (donchian=40, adx=26, pvo_l=70, stop=1.0) を最適化し、
2024/01/01 ～ 2026/03/31 の通年パフォーマンスを改善する。

【Phase 1】 Donchian期間 × ADX閾値 グリッドサーチ (5×5 = 25 runs)
  donchian_buy_term = donchian_sell_term ∈ {20, 30, 40, 50, 60}
  adx_filter_threshold ∈ {20, 24, 26, 28, 30}

【Phase 2】 最良Phase1 × PVO長期 (5 runs)
  pvo_l_term ∈ {50, 60, 70, 80, 100}

【Phase 3】 最良Phase2 × ストップ幅 (5 runs)
  stop_range ∈ {0.5, 0.75, 1.0, 1.5, 2.0}

【採用基準】
  PnL > ベースライン かつ MaxDD <= ベースライン

【最適化期間】
  2024/01/01 ～ 2026/03/31 (27ヶ月)
  ※ BybitネイティブXAUT/USDT:USDTまたはPAXGプロキシの安定期間

最終検証: 最良パラメータで quarterly backtest (2023Q2 ～ 2026Q1) を確認
"""

import subprocess
import re
import os
import sys
import copy

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "src", "config_xaut.ini")

OPT_START = "2024/01/01 00:00"
OPT_END   = "2026/03/31 23:59"

# ──────────────────────────────────────────────
def read_config() -> str:
    with open(CONFIG_PATH, "r") as f:
        return f.read()

def write_config(content: str):
    with open(CONFIG_PATH, "w") as f:
        f.write(content)

_ORIGINAL_CONFIG = None

def save_original():
    global _ORIGINAL_CONFIG
    _ORIGINAL_CONFIG = read_config()

def restore_original():
    if _ORIGINAL_CONFIG is not None:
        write_config(_ORIGINAL_CONFIG)

# ──────────────────────────────────────────────
def make_config(
    donchian: int = 40,
    adx_thr: float = 26,
    pvo_l: int = 70,
    stop_range: float = 1.0,
) -> str:
    c = read_config()
    c = re.sub(r'(start_time\s*=).*',       rf'\g<1> {OPT_START}',       c)
    c = re.sub(r'(end_time\s*=).*',         rf'\g<1> {OPT_END}',         c)
    c = re.sub(r'(donchian_buy_term\s*=).*', rf'\g<1> {donchian}',       c)
    c = re.sub(r'(donchian_sell_term\s*=).*', rf'\g<1> {donchian}',      c)
    c = re.sub(r'(adx_filter_threshold\s*=).*', rf'\g<1> {adx_thr}',    c)
    c = re.sub(r'(pvo_l_term\s*=).*',       rf'\g<1> {pvo_l}',          c)
    c = re.sub(r'(stop_range\s*=).*',       rf'\g<1> {stop_range}',     c)
    return c

def run_backtest(config_content: str) -> dict:
    orig = read_config()
    write_config(config_content)
    try:
        result = subprocess.run(
            [sys.executable, "bot.py", "--config", "config_xaut.ini"],
            capture_output=True, text=True,
            cwd=os.path.join(BASE_DIR, "src"),
            timeout=180
        )
    except subprocess.TimeoutExpired:
        return {"pnl": None, "max_dd": None, "trades": None, "error": "timeout"}
    finally:
        write_config(orig)

    output = result.stderr + result.stdout
    pnl_m   = re.search(r'最終損益:\s*([+-]?[\d,]+\.?\d*)\s*\[', output)
    dd_m    = re.search(r'最大ドローダウン率:\s*([\d.]+)\s*\[%\]',  output)
    tr_m    = re.search(r'Trades:\s*(\d+)',                         output)

    return {
        "pnl":    float(pnl_m.group(1).replace(",", "")) if pnl_m else None,
        "max_dd": float(dd_m.group(1))                   if dd_m  else None,
        "trades": int(tr_m.group(1))                     if tr_m  else None,
        "error":  None,
    }

# ──────────────────────────────────────────────
def print_separator(char="=", width=76):
    print(char * width)

def fmt_result(r: dict, label: str, base_pnl=None, base_dd=None) -> str:
    pnl = r["pnl"]
    dd  = r["max_dd"]
    tr  = r["trades"]
    if pnl is None:
        return f"{label:<35} ⚠️  取得失敗 ({r.get('error','')})"
    dpnl = f"Δ{pnl-base_pnl:+.2f}" if base_pnl is not None else ""
    ddd  = f"Δ{dd-base_dd:+.1f}%"   if base_dd  is not None else ""
    ok   = "✅" if (base_pnl and base_dd and pnl > base_pnl and dd <= base_dd) else \
           "📈" if (base_pnl and pnl > base_pnl) else "❌"
    return (f"{label:<35} PnL={pnl:+8.2f} USD {dpnl:<9}  "
            f"MaxDD={dd:5.1f}% {ddd:<8}  Trades={tr:3d}  {ok}")

# ══════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════
if __name__ == "__main__":
    save_original()

    print_separator("=")
    print("H-XAUT-01: XAUTパラメータ最適化スイープ")
    print(f"最適化期間: {OPT_START} ～ {OPT_END}")
    print_separator("=")

    # ─────────────────────────────
    # ベースライン
    # ─────────────────────────────
    print("\n[BASELINE] donchian=40, adx=26, pvo_l=70, stop=1.0")
    base_cfg = make_config(donchian=40, adx_thr=26, pvo_l=70, stop_range=1.0)
    base_r = run_backtest(base_cfg)
    if base_r["pnl"] is None:
        print("ベースライン取得失敗。中断します。")
        restore_original()
        sys.exit(1)

    BASE_PNL = base_r["pnl"]
    BASE_DD  = base_r["max_dd"]
    BASE_TR  = base_r["trades"]
    print(fmt_result(base_r, "BASELINE"))
    print()

    # ─────────────────────────────
    # Phase 1: Donchian × ADX グリッド
    # ─────────────────────────────
    print_separator("-")
    print("Phase 1: Donchian × ADX グリッドサーチ (5×5 = 25 runs)")
    print_separator("-")
    DONCHIAN_VALS = [20, 30, 40, 50, 60]
    ADX_VALS      = [20, 24, 26, 28, 30]

    print(f"{'':20}", end="")
    for adx in ADX_VALS:
        print(f"  ADX≥{adx:2d}  ", end="")
    print()
    print("-" * 76)

    phase1_results = {}
    best_p1_pnl = BASE_PNL
    best_p1 = {"donchian": 40, "adx": 26}

    for dc in DONCHIAN_VALS:
        print(f"DC={dc:2d}:", end="")
        row_results = {}
        for adx in ADX_VALS:
            cfg = make_config(donchian=dc, adx_thr=adx)
            r = run_backtest(cfg)
            pnl = r["pnl"]
            dd  = r["max_dd"]
            mark = ""
            if pnl is not None:
                if pnl > best_p1_pnl and dd is not None and dd <= BASE_DD * 1.1:
                    best_p1_pnl = pnl
                    best_p1 = {"donchian": dc, "adx": adx}
                    mark = "★"
                elif pnl > BASE_PNL:
                    mark = "◎"
                elif pnl > BASE_PNL * 0.9:
                    mark = "△"
                else:
                    mark = " "
                print(f" {pnl:+7.1f}{mark} ", end="", flush=True)
            else:
                print(f"  ERROR   ", end="", flush=True)
            row_results[adx] = r
        phase1_results[dc] = row_results
        print()

    print()
    print(f">>> Phase 1 最良: donchian={best_p1['donchian']}, adx={best_p1['adx']}, PnL={best_p1_pnl:+.2f}")

    # 詳細表示
    print("\nPhase 1 Top 5 combinations:")
    all_p1 = [
        (dc, adx, phase1_results[dc][adx])
        for dc in DONCHIAN_VALS for adx in ADX_VALS
        if phase1_results[dc][adx]["pnl"] is not None
    ]
    all_p1.sort(key=lambda x: x[2]["pnl"] or -9999, reverse=True)
    for dc, adx, r in all_p1[:5]:
        label = f"DC={dc:2d}, ADX≥{adx:2d}"
        print(" ", fmt_result(r, label, BASE_PNL, BASE_DD))

    # ─────────────────────────────
    # Phase 2: PVO長期スイープ
    # ─────────────────────────────
    print()
    print_separator("-")
    print(f"Phase 2: PVO長期スイープ (donchian={best_p1['donchian']}, adx={best_p1['adx']} 固定)")
    print_separator("-")
    PVO_L_VALS = [50, 60, 70, 80, 100]

    best_p2_pnl = best_p1_pnl
    best_p2 = {**best_p1, "pvo_l": 70}

    for pvo in PVO_L_VALS:
        cfg = make_config(donchian=best_p1["donchian"], adx_thr=best_p1["adx"], pvo_l=pvo)
        r = run_backtest(cfg)
        label = f"pvo_l={pvo:3d}"
        if r["pnl"] is not None and r["pnl"] > best_p2_pnl:
            best_p2_pnl = r["pnl"]
            best_p2 = {**best_p1, "pvo_l": pvo}
            print(" ★", fmt_result(r, label, BASE_PNL, BASE_DD))
        else:
            print("  ", fmt_result(r, label, BASE_PNL, BASE_DD))

    print(f"\n>>> Phase 2 最良: {best_p2}, PnL={best_p2_pnl:+.2f}")

    # ─────────────────────────────
    # Phase 3: ストップ幅スイープ
    # ─────────────────────────────
    print()
    print_separator("-")
    print(f"Phase 3: ストップ幅スイープ (Phase2最良設定固定)")
    print(f"         donchian={best_p2['donchian']}, adx={best_p2['adx']}, pvo_l={best_p2['pvo_l']}")
    print_separator("-")
    STOP_VALS = [0.5, 0.75, 1.0, 1.5, 2.0]

    best_p3_pnl = best_p2_pnl
    best_p3 = {**best_p2, "stop_range": 1.0}

    for stop in STOP_VALS:
        cfg = make_config(
            donchian=best_p2["donchian"],
            adx_thr=best_p2["adx"],
            pvo_l=best_p2["pvo_l"],
            stop_range=stop,
        )
        r = run_backtest(cfg)
        label = f"stop={stop:.2f}"
        dd  = r["max_dd"]
        if r["pnl"] is not None and r["pnl"] > best_p3_pnl and (dd is None or dd <= BASE_DD * 1.1):
            best_p3_pnl = r["pnl"]
            best_p3 = {**best_p2, "stop_range": stop}
            print(" ★", fmt_result(r, label, BASE_PNL, BASE_DD))
        else:
            print("  ", fmt_result(r, label, BASE_PNL, BASE_DD))

    print(f"\n>>> Phase 3 最良: {best_p3}, PnL={best_p3_pnl:+.2f}")

    # ─────────────────────────────
    # 総合結果
    # ─────────────────────────────
    print()
    print_separator("=")
    print("📊 最適化結果サマリー")
    print_separator("=")
    print(f"{'ベースライン':<30} PnL={BASE_PNL:+8.2f} USD  MaxDD={BASE_DD:.1f}%  Trades={BASE_TR}")
    cfg_final = make_config(
        donchian=best_p3["donchian"],
        adx_thr=best_p3["adx"],
        pvo_l=best_p3["pvo_l"],
        stop_range=best_p3["stop_range"],
    )
    final_r = run_backtest(cfg_final)
    print(f"{'最良設定（最終確認）':<30} PnL={final_r['pnl']:+8.2f} USD  "
          f"MaxDD={final_r['max_dd']:.1f}%  Trades={final_r['trades']}")
    print()
    print("【採用推奨パラメータ】")
    print(f"  donchian_buy_term  = donchian_sell_term = {best_p3['donchian']}")
    print(f"  adx_filter_threshold = {best_p3['adx']}")
    print(f"  pvo_l_term = {best_p3['pvo_l']}")
    print(f"  stop_range = {best_p3['stop_range']}")

    if final_r["pnl"] is not None and final_r["pnl"] > BASE_PNL:
        delta = final_r["pnl"] - BASE_PNL
        print(f"\n✅ PnL改善: +{delta:.2f} USD (+{delta/abs(BASE_PNL)*100:.1f}%)")
    else:
        print("\n⚠️ ベースラインを超えるパラメータが見つかりませんでした")
        print("  → 現在の設定が既に最適に近い可能性があります")

    restore_original()
    print("\n✅ 設定ファイルを元に戻しました")
