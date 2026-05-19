"""
H-XAUT-03: Phase5 - TSMOM + rvol 組み合わせによる MaxDD 改善

Phase4の課題：
  rvol=1.0, fr=0.002 → PnL=+237 (+7.7%) だが MaxDD が 45.8% → 63.1% に悪化
  
仮説：
  TSMOM（時系列モメンタム）フィルターを有効にすることで、
  rvol緩和で増えたトレードのうち悪手を排除し、MaxDDを抑制しつつPnL改善を維持できる

テスト設計：
  [Phase5A] TSMOM lookback × rvol グリッドサーチ (4×3 = 12 runs)
    tsmom_lookback ∈ {50, 100, 150, 200}
    rvol ∈ {1.0, 1.2, 1.5}

  [Phase5B] 最良Phase5A × funding_rate確認 (3 runs)
    fr_buy ∈ {0.0005, 0.001, 0.002}

採用基準（強化）:
  PnL > baseline AND MaxDD < baseline × 1.2 (55% 以内)
  --- これが難しければ ---  
  PnL > baseline × 1.1 AND MaxDD < 60%

ベースライン: PnL=+220, MaxDD=45.8%, Trades=54
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

def read_config():
    with open(CONFIG_PATH) as f:
        return f.read()

def write_config(c):
    with open(CONFIG_PATH, "w") as f:
        f.write(c)

def save_original():
    global _ORIGINAL_CONFIG
    _ORIGINAL_CONFIG = read_config()

def restore_original():
    if _ORIGINAL_CONFIG is not None:
        write_config(_ORIGINAL_CONFIG)

def make_config(rvol=1.5, fr_buy=0.0005, tsmom_en=0, tsmom_lb=100):
    c = read_config()
    c = re.sub(r'(start_time\s*=).*',               rf'\g<1> {OPT_START}', c)
    c = re.sub(r'(end_time\s*=).*',                 rf'\g<1> {OPT_END}',   c)
    c = re.sub(r'(relative_volume_threshold\s*=).*', rf'\g<1> {rvol}',     c)
    c = re.sub(r'(funding_rate_buy_threshold\s*=).*', rf'\g<1> {fr_buy}',  c)
    c = re.sub(r'(funding_rate_sell_threshold\s*=).*', rf'\g<1> {-fr_buy}',c)
    c = re.sub(r'(tsmom_filter_enabled\s*=).*',      rf'\g<1> {tsmom_en}', c)
    c = re.sub(r'(tsmom_filter_lookback\s*=).*',     rf'\g<1> {tsmom_lb}', c)
    return c

def run_backtest(config_content):
    orig = read_config()
    write_config(config_content)
    try:
        r = subprocess.run(
            [sys.executable, "bot.py", "--config", "config_xaut.ini"],
            capture_output=True, text=True,
            cwd=os.path.join(BASE_DIR, "src"), timeout=180
        )
    except subprocess.TimeoutExpired:
        return {"pnl": None, "max_dd": None, "trades": None}
    finally:
        write_config(orig)
    out = r.stderr + r.stdout
    pm = re.search(r'最終損益:\s*([+-]?[\d,]+\.?\d*)\s*\[', out)
    dm = re.search(r'最大ドローダウン率:\s*([\d.]+)\s*\[%\]', out)
    tm = re.search(r'Trades:\s*(\d+)', out)
    return {
        "pnl":    float(pm.group(1).replace(",","")) if pm else None,
        "max_dd": float(dm.group(1))                 if dm else None,
        "trades": int(tm.group(1))                   if tm else None,
    }

def fmt(r, label, bp, bd):
    p, d, t = r["pnl"], r["max_dd"], r["trades"]
    if p is None:
        return f"{label:<45} ⚠️ 失敗"
    dp  = f"Δ{p-bp:+.0f}"
    dd_ = f"Δ{d-bd:+.1f}%"
    # 判定：PnL改善 AND MaxDD ≤ baseline*1.2
    ok = "✅" if (p > bp and d <= bd * 1.2) else \
         "📈" if (p > bp) else \
         "🔵" if (p >= bp * 0.95 and d < bd) else "❌"
    return (f"{label:<45} PnL={p:+7.0f} {dp:<6}  MaxDD={d:5.1f}% {dd_:<8}"
            f"  Tr={t:3d}  {ok}")

# ══════════════════════════════════════════════
if __name__ == "__main__":
    save_original()

    print("=" * 80)
    print("H-XAUT-03: Phase5 TSMOM × rvol グリッドサーチ（MaxDD改善）")
    print(f"最適化期間: {OPT_START} ～ {OPT_END}")
    print("採用基準: PnL > +220 USD かつ MaxDD ≤ 45.8% × 1.2 = 55%")
    print("=" * 80)

    # ベースライン
    base_r = run_backtest(make_config())
    BP, BD = base_r["pnl"], base_r["max_dd"]
    print(f"\n[BASELINE] PnL={BP:+.0f} USD  MaxDD={BD:.1f}%  Trades={base_r['trades']}")
    print()

    # ─── Phase5A: TSMOM × rvol グリッド
    print("-" * 80)
    print("Phase5A: TSMOM lookback × relative_volume_threshold")
    print("-" * 80)
    TSMOM_LBs = [50, 100, 150, 200]
    RVOL_VALS = [1.0, 1.2, 1.5]

    # Header
    print(f"{'':20}", end="")
    for rvol in RVOL_VALS:
        print(f"   rvol={rvol:.1f}     ", end="")
    print()
    print("-" * 80)

    p5a_results = {}
    best_p5a_score = -9999
    best_p5a = {"tsmom_lb": None, "rvol": 1.5, "pnl": BP, "dd": BD}

    for lb in TSMOM_LBs:
        print(f"TSMOM_LB={lb:3d}:", end="")
        row = {}
        for rvol in RVOL_VALS:
            r = run_backtest(make_config(rvol=rvol, tsmom_en=1, tsmom_lb=lb))
            p, d = r["pnl"], r["max_dd"]
            row[rvol] = r
            if p is not None:
                # スコア: PnL を最大化しつつ、MaxDD > 55% にはペナルティ
                penalty = max(0, d - 55) * 3 if d else 0
                score = p - penalty
                if score > best_p5a_score:
                    best_p5a_score = score
                    best_p5a = {"tsmom_lb": lb, "rvol": rvol, "pnl": p, "dd": d,
                                "trades": r["trades"]}
                dd_str = f"MaxDD={d:.0f}%"
                pnl_mark = "★" if (p > BP and d <= BD * 1.2) else \
                           "◎" if (p > BP) else \
                           "△" if (p >= BP * 0.9) else " "
                print(f"  {p:+5.0f}/{dd_str}{pnl_mark}", end="", flush=True)
            else:
                print(f"  ERROR       ", end="", flush=True)
        p5a_results[lb] = row
        print()

    print()
    if best_p5a["tsmom_lb"] is not None:
        print(f">>> Phase5A 最良: TSMOM_LB={best_p5a['tsmom_lb']}, rvol={best_p5a['rvol']}, "
              f"PnL={best_p5a['pnl']:+.0f}, MaxDD={best_p5a['dd']:.1f}%")
    else:
        print(">>> Phase5A: 採用基準を満たす組み合わせなし")

    # ─── Phase5B: 最良TSMOM×rvol + funding rate
    print()
    print("-" * 80)
    tsmom_lb = best_p5a["tsmom_lb"] if best_p5a["tsmom_lb"] else 100
    rvol_best = best_p5a["rvol"]
    print(f"Phase5B: funding_rate確認 (tsmom_lb={tsmom_lb}, rvol={rvol_best})")
    print("-" * 80)
    FR_VALS = [0.0005, 0.001, 0.002]
    best_p5b_pnl = BP
    best_p5b = {"fr": 0.0005}

    for fr in FR_VALS:
        r = run_backtest(make_config(rvol=rvol_best, fr_buy=fr, tsmom_en=1, tsmom_lb=tsmom_lb))
        label = f"fr={fr*100:.3f}%"
        if r["pnl"] is not None and r["pnl"] > best_p5b_pnl and r["max_dd"] <= BD * 1.2:
            best_p5b_pnl = r["pnl"]
            best_p5b = {"fr": fr}
            print(" ★", fmt(r, label, BP, BD))
        else:
            print("  ", fmt(r, label, BP, BD))

    # ─── 総合サマリー
    print()
    print("=" * 80)
    print("📊 全フェーズ 最適化サマリー")
    print("=" * 80)
    print(f"{'  ベースライン(現在設定)':<45} PnL={BP:+7.0f}  MaxDD={BD:.1f}%  Trades={base_r['trades']}")

    # Phase1-3 最良
    cfg_p13 = make_config()  # donchian=40, adx=20, stop=2.0 →  P1-3最良
    c_tmp = read_config()
    # inline modify for P1-3 best
    mod = re.sub(r'(start_time\s*=).*', f'start_time = {OPT_START}', c_tmp)
    mod = re.sub(r'(end_time\s*=).*',   f'end_time = {OPT_END}', mod)
    mod = re.sub(r'(adx_filter_threshold\s*=).*', 'adx_filter_threshold = 20', mod)
    mod = re.sub(r'(stop_range\s*=).*', 'stop_range = 2.0', mod)
    r_p13 = run_backtest(mod)
    print(f"{'  Phase1-3最良(adx=20,stop=2.0)':<45} PnL={r_p13['pnl']:+7.0f}  "
          f"MaxDD={r_p13['max_dd']:.1f}%  Trades={r_p13['trades']}")

    # Phase5 最良
    best_fr_val = best_p5b["fr"]
    r_p5best = run_backtest(make_config(rvol=rvol_best, fr_buy=best_fr_val,
                                        tsmom_en=1, tsmom_lb=tsmom_lb))
    print(f"{'  Phase5最良(TSMOM+rvol+fr)':<45} PnL={r_p5best['pnl']:+7.0f}  "
          f"MaxDD={r_p5best['max_dd']:.1f}%  Trades={r_p5best['trades']}")

    print()
    print("【最終推奨パラメータ候補】")
    print(f"  donchian_buy_term / sell_term = 40   (変更なし)")
    print(f"  adx_filter_threshold = 26            (変更なし)")
    print(f"  stop_range = 1.0                     (変更なし)")
    print(f"  relative_volume_threshold = {rvol_best}")
    print(f"  tsmom_filter_enabled = 1")
    print(f"  tsmom_filter_lookback = {tsmom_lb}")
    print(f"  funding_rate_buy_threshold = {best_fr_val}")

    restore_original()
    print("\n✅ 設定ファイルを元に戻しました")
