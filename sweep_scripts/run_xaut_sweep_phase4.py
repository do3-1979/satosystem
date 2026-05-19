"""
H-XAUT-02: Phase4 - 実効フィルター最適化スイープ

Phase1-3の結果分析：
  - PVO フィルター: XAUT出来高は常に高 → PVO > 0 は常に成立（非バインド）
  - Volatility フィルター: XAUT ATR ≈ 7-17 USD << 閾値2500 → 非バインド
  - ADX フィルター: 20-26 が同一結果 → 26以下で実効なし
  - RangeBreakoutEnhanced: 「出来高不足」で多数ブロック ← 主要ブロッカー
  - FundingRate フィルター: FR≥0.05%でBUYブロック ← 金強気時に逆効果の疑い

【フォーカスパラメータ】
  (A) relative_volume_threshold: 1.0 / 1.2 / 1.5(現在) / 2.0 / 2.5
  (B) funding_rate_buy_threshold: 0.001 / 0.002 / 0.005 / 無効(0.1)
  (C) A×B 最良組み合わせ確認

ベースライン: donchian=40, adx=26, stop=1.0, rvol=1.5, fr_buy=0.0005
              PnL= +220 USD, MaxDD= 45.8%, Trades= 54

最適化期間: 2024/01/01 ～ 2026/03/31
"""

import subprocess
import re
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "src", "config_xaut.ini")

OPT_START = "2024/01/01 00:00"
OPT_END   = "2026/03/31 23:59"

_ORIGINAL_CONFIG = None

def read_config() -> str:
    with open(CONFIG_PATH, "r") as f:
        return f.read()

def write_config(content: str):
    with open(CONFIG_PATH, "w") as f:
        f.write(content)

def save_original():
    global _ORIGINAL_CONFIG
    _ORIGINAL_CONFIG = read_config()

def restore_original():
    if _ORIGINAL_CONFIG is not None:
        write_config(_ORIGINAL_CONFIG)

def make_config(
    rvol: float = 1.5,
    fr_buy: float = 0.0005,
    fr_sell: float = -0.0005,
    donchian: int = 40,
    adx_thr: float = 26,
    stop_range: float = 1.0,
) -> str:
    c = read_config()
    c = re.sub(r'(start_time\s*=).*',               rf'\g<1> {OPT_START}',  c)
    c = re.sub(r'(end_time\s*=).*',                 rf'\g<1> {OPT_END}',    c)
    c = re.sub(r'(donchian_buy_term\s*=).*',        rf'\g<1> {donchian}',   c)
    c = re.sub(r'(donchian_sell_term\s*=).*',       rf'\g<1> {donchian}',   c)
    c = re.sub(r'(adx_filter_threshold\s*=).*',     rf'\g<1> {adx_thr}',   c)
    c = re.sub(r'(stop_range\s*=).*',               rf'\g<1> {stop_range}', c)
    c = re.sub(r'(relative_volume_threshold\s*=).*', rf'\g<1> {rvol}',      c)
    c = re.sub(r'(funding_rate_buy_threshold\s*=).*', rf'\g<1> {fr_buy}',   c)
    c = re.sub(r'(funding_rate_sell_threshold\s*=).*', rf'\g<1> {fr_sell}', c)
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
    pnl_m = re.search(r'最終損益:\s*([+-]?[\d,]+\.?\d*)\s*\[', output)
    dd_m  = re.search(r'最大ドローダウン率:\s*([\d.]+)\s*\[%\]', output)
    tr_m  = re.search(r'Trades:\s*(\d+)', output)

    return {
        "pnl":    float(pnl_m.group(1).replace(",", "")) if pnl_m else None,
        "max_dd": float(dd_m.group(1))                   if dd_m  else None,
        "trades": int(tr_m.group(1))                     if tr_m  else None,
        "error":  None,
    }

def fmt(r, label, bp=None, bd=None):
    p, d, t = r["pnl"], r["max_dd"], r["trades"]
    if p is None:
        return f"{label:<40} ⚠️ 失敗"
    dp = f"Δ{p-bp:+.1f}" if bp else ""
    dd_ = f"Δ{d-bd:+.1f}%" if bd else ""
    ok = "✅" if (bp and bd and p > bp and d <= bd*1.1) else ("📈" if (bp and p > bp) else "❌")
    return f"{label:<40} PnL={p:+8.1f} {dp:<8}  MaxDD={d:5.1f}% {dd_:<8}  Tr={t:3d}  {ok}"

# ══════════════════════════════════════════════
if __name__ == "__main__":
    save_original()

    print("=" * 76)
    print("H-XAUT-02: Phase4 実効フィルター最適化スイープ")
    print(f"最適化期間: {OPT_START} ～ {OPT_END}")
    print("=" * 76)

    # ─── ベースライン（現在設定）
    print("\n[BASELINE] rvol=1.5, fr_buy=0.0005")
    base_r = run_backtest(make_config())
    BP, BD = base_r["pnl"], base_r["max_dd"]
    print(fmt(base_r, "BASELINE"))
    print()

    # ─── (A) 相対出来高閾値スイープ
    print("-" * 76)
    print("Phase4A: relative_volume_threshold スイープ (fr_buy=0.0005 固定)")
    print("-" * 76)
    RVOL_VALS = [1.0, 1.2, 1.5, 2.0, 2.5]
    best_rvol = 1.5
    best_rvol_pnl = BP

    for rvol in RVOL_VALS:
        r = run_backtest(make_config(rvol=rvol))
        label = f"rvol_thr={rvol:.1f}"
        if r["pnl"] is not None and r["pnl"] > best_rvol_pnl:
            best_rvol_pnl = r["pnl"]
            best_rvol = rvol
            print(" ★", fmt(r, label, BP, BD))
        else:
            print("  ", fmt(r, label, BP, BD))

    print(f"\n>>> Phase4A 最良: rvol_thr={best_rvol}, PnL={best_rvol_pnl:+.1f}")

    # ─── (B) FundingRate閾値スイープ（rvol固定）
    print()
    print("-" * 76)
    print(f"Phase4B: funding_rate_buy_threshold スイープ (rvol={best_rvol} 固定)")
    print("-" * 76)
    FR_VALS = [0.0005, 0.001, 0.002, 0.005, 0.1]  # 0.1 = effectively disabled
    best_fr = 0.0005
    best_fr_pnl = best_rvol_pnl

    for fr in FR_VALS:
        r = run_backtest(make_config(rvol=best_rvol, fr_buy=fr, fr_sell=-fr))
        label = f"fr_buy={fr:.4f}({'OFF' if fr>=0.1 else f'{fr*100:.3f}%'})"
        if r["pnl"] is not None and r["pnl"] > best_fr_pnl:
            best_fr_pnl = r["pnl"]
            best_fr = fr
            print(" ★", fmt(r, label, BP, BD))
        else:
            print("  ", fmt(r, label, BP, BD))

    print(f"\n>>> Phase4B 最良: fr_buy={best_fr}, PnL={best_fr_pnl:+.1f}")

    # ─── (C) 最良組み合わせ最終確認
    print()
    print("-" * 76)
    print(f"Phase4C: 最良組み合わせ確認 (rvol={best_rvol}, fr_buy={best_fr})")
    print("-" * 76)
    final_r = run_backtest(make_config(rvol=best_rvol, fr_buy=best_fr, fr_sell=-best_fr))
    print(fmt(final_r, f"BEST: rvol={best_rvol}, fr={best_fr:.4f}", BP, BD))

    # ─── 総合サマリー
    print()
    print("=" * 76)
    print("📊 Phase4 最適化結果サマリー")
    print("=" * 76)
    print(f"{'ベースライン':<40} PnL={BP:+8.1f}  MaxDD={BD:.1f}%")
    if final_r["pnl"] is not None:
        delta = final_r["pnl"] - BP
        print(f"{'最良設定':<40} PnL={final_r['pnl']:+8.1f}  MaxDD={final_r['max_dd']:.1f}%  Trades={final_r['trades']}")
        print()
        if delta > 0:
            print(f"✅ Phase4改善: +{delta:.1f} USD (+{delta/abs(BP)*100:.1f}%)")
            print(f"   relative_volume_threshold = {best_rvol}")
            print(f"   funding_rate_buy_threshold = {best_fr}")
            print(f"   funding_rate_sell_threshold = {-best_fr}")
        else:
            print("⚠️ Phase4での改善なし → rvol=1.5, fr=0.0005 が最適")

    restore_original()
    print("\n✅ 設定ファイルを元に戻しました")
