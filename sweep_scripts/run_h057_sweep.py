#!/usr/bin/env python3
"""
H-057: 2段階スケールアウト 検証スクリプト

仮説:
  Stage-1スケールアウト（1.0×ATR, 50%利確）に加え、
  Stage-2スケールアウト（N×ATR, さらにM%利確）を追加する
  → 大トレンドで残りポジションの一部をより高値で利確し、PnLを改善

【狙ったトレードと期待効果】
  - 利益が大きく乗った（2×ATR以上移動した）トレード
  - 期待: Stage-2で追加利確 → PnLが底上げされる
  - 代償: 残ポジションが減るため、大相場での最終利益が減る可能性

【標準化分析】
  ATR標準化PnL = pnl_pct / (atr / entry_price * 100)
  Stage-1/Stage-2 発動トレードを抽出し、
  発動前後のATR標準化PnLの変化を検証する

ベースライン(H-056 ScaleIn採用後): PnL=+3,417 USD / MaxDD=22.80%
採用基準: PnL >= +3,417 USD かつ MaxDD <= 22.80% (両指標維持 or 改善)
"""

import subprocess
import configparser
import re
import json
import os
import glob

CONFIG_PATH = "src/config.ini"
BASELINE_PNL   = 3417.0
BASELINE_MAXDD = 22.80

# スイープパターン: (stage2_trigger_multiplier, stage2_quantity_pct)
SWEEP_PATTERNS = [
    (0,   0.0),   # OFF（ベースライン）
    (2.0, 0.3),
    (2.0, 0.5),
    (3.0, 0.3),
    (3.0, 0.5),
]


def read_config():
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_PATH)
    return cfg

def write_config(cfg):
    with open(CONFIG_PATH, 'w') as f:
        cfg.write(f)

def set_scale_out_2(enabled: int, trigger: float, qty_pct: float):
    cfg = read_config()
    if 'ScaleOut' not in cfg:
        cfg['ScaleOut'] = {}
    cfg['ScaleOut']['scale_out_2_enabled']            = str(enabled)
    cfg['ScaleOut']['scale_out_2_trigger_multiplier'] = str(trigger)
    cfg['ScaleOut']['scale_out_2_quantity_pct']       = str(qty_pct)
    write_config(cfg)

def run_backtest():
    result = subprocess.run(
        ["python3", "bot.py"],
        capture_output=True, text=True, cwd="src"
    )
    return result.stdout + result.stderr

def parse_results(output):
    pnl = max_dd = trades = None
    for pattern in [r"最終損益:\s*([+-]?[\d,]+\.?\d*)\s*\[", r"損益累計:([+-]?[\d,]+\.?\d*)\s*\["]:
        m = re.search(pattern, output)
        if m:
            try:
                pnl = float(m.group(1).replace(',', ''))
                break
            except ValueError:
                pass
    for pattern in [r"最大ドローダウン率:\s*([0-9]+\.?[0-9]*)\s*\[%\]"]:
        m = re.search(pattern, output)
        if m:
            max_dd = float(m.group(1))
            break
    m = re.search(r"Trades:\s*(\d+)", output)
    if m:
        trades = int(m.group(1))
    return pnl, max_dd, trades

def get_latest_trade_log(log_dir="src/logs"):
    pattern = os.path.join(log_dir, "trade_log_*.json")
    files = sorted(glob.glob(pattern))
    return files[-1] if files else None

def load_trade_log(path):
    if not path or not os.path.exists(path):
        return []
    try:
        with open(path, 'r') as f:
            data = json.load(f)
        # {"metadata": ..., "trades": [...]} 形式に対応
        if isinstance(data, dict) and 'trades' in data:
            return data['trades']
        if isinstance(data, list):
            return data
        return []
    except Exception:
        return []

def compute_normalized_pnl(trade):
    """ATR標準化PnL = pnl_usd / ATR (ATRはvolatilityで代替)
    = トレード1ATR動いた場合の利益を1とした標準化値
    価格帯の違いを排除してトレードの質を比較できる"""
    entry = trade.get('entry', {})
    result = trade.get('result', {})
    pnl_usd = result.get('pnl_usd', None)
    # ATRはvolatilityフィルターの値で代替
    atr = entry.get('filters', {}).get('volatility', {}).get('value') or 0
    if atr <= 0 or pnl_usd is None:
        return None
    return pnl_usd / atr

def analyze_trades(trades, label):
    """トレード分析: Stage-2発動トレードの抽出・評価"""
    completed = [t for t in trades if t.get('result')]
    if not completed:
        print(f"  [{label}] トレードデータなし")
        return {}

    # Stage-2発動トレードを抽出
    so2_trades = [t for t in completed
                  if any(e.get('type') == 'SCALE_OUT_2'
                         for e in t.get('scale_events', []))]

    norm_all  = [x for x in (compute_normalized_pnl(t) for t in completed) if x is not None]
    norm_so2  = [x for x in (compute_normalized_pnl(t) for t in so2_trades) if x is not None]
    avg_all   = sum(norm_all)  / len(norm_all)  if norm_all  else 0
    avg_so2   = sum(norm_so2)  / len(norm_so2)  if norm_so2  else None

    total_pnl = sum(t.get('result', {}).get('pnl_usd', 0) for t in completed)

    print(f"\n  [{label}]")
    print(f"    全体: {len(completed)}件  合計PnL={total_pnl:+.1f} USD  ATR標準化平均={avg_all:+.3f}ATR")
    if so2_trades:
        print(f"    Stage-2発動: {len(so2_trades)}件  ATR標準化平均={avg_so2:+.3f}ATR")
    else:
        print(f"    Stage-2発動: 0件")

    return {
        'total': len(completed),
        'so2_count': len(so2_trades),
        'avg_norm': avg_all,
        'avg_norm_so2': avg_so2,
        'total_pnl': total_pnl,
    }

def compare_so2_trades(base_trades, h_trades, label):
    """Stage-2が発動したトレードの個別PnL比較"""
    def trade_key(t):
        return t.get('entry', {}).get('close_time_dt', '')

    base_by_key = {trade_key(t): t for t in base_trades if t.get('result')}
    h_by_key    = {trade_key(t): t for t in h_trades    if t.get('result')}

    # H-057でStage-2が発動したトレードを特定
    so2_keys = {trade_key(t) for t in h_trades
                if any(e.get('type') == 'SCALE_OUT_2' for e in t.get('scale_events', []))}

    changed = []
    for k in sorted(so2_keys):
        if k not in base_by_key or k not in h_by_key:
            continue
        bt = base_by_key[k]
        ht = h_by_key[k]
        base_pnl = bt.get('result', {}).get('pnl_usd', 0)
        h_pnl    = ht.get('result', {}).get('pnl_usd', 0)
        diff     = h_pnl - base_pnl

        changed.append({
            'date':      k,
            'side':      bt.get('entry', {}).get('side', ''),
            'price':     bt.get('entry', {}).get('price', 0),
            'base_pnl':  base_pnl,
            'h_pnl':     h_pnl,
            'diff':      diff,
            'norm_base': compute_normalized_pnl(bt),
            'norm_h':    compute_normalized_pnl(ht),
        })

    if not changed:
        print(f"\n  [{label}] Stage-2発動トレード: 0件")
        return changed

    improved = [c for c in changed if c['diff'] > 0.5]
    worsened = [c for c in changed if c['diff'] < -0.5]
    print(f"\n  [{label}] Stage-2発動={len(changed)}件  改善={len(improved)}件  悪化={len(worsened)}件")
    print(f"  {'日時':24s} {'側':4s}  {'BASE':>8s}  {'H057':>8s}  {'差':>8s}  {'BASE標準化':>10s}  {'H057標準化':>10s}")
    for c in sorted(changed, key=lambda x: abs(x['diff']), reverse=True)[:10]:
        nb = f"{c['norm_base']:+.2f}ATR" if c['norm_base'] is not None else "N/A"
        nh = f"{c['norm_h']:+.2f}ATR"    if c['norm_h']    is not None else "N/A"
        mark = "✅" if c['diff'] > 0.5 else ("⚠️" if c['diff'] < -0.5 else "  ")
        print(f"  {c['date']:24s} {c['side']:4s}  {c['base_pnl']:+8.1f}  {c['h_pnl']:+8.1f}  {c['diff']:+8.1f}  {nb:>10s}  {nh:>10s}  {mark}")

    return changed


def main():
    print("=" * 70)
    print("H-057: 2段階スケールアウト 検証")
    print(f"ベースライン: PnL={BASELINE_PNL:+.0f} USD / MaxDD={BASELINE_MAXDD:.2f}%")
    print(f"スイープパターン (trigger×ATR, qty_pct): {SWEEP_PATTERNS}")
    print("=" * 70)

    results    = {}
    trade_logs = {}

    for (trigger, qty) in SWEEP_PATTERNS:
        if trigger == 0:
            label = "OFF(ベースライン)"
            set_scale_out_2(0, 2.0, 0.3)
        else:
            label = f"trigger={trigger} qty={qty}"
            set_scale_out_2(1, trigger, qty)

        print(f"\n[{label}] 実行中...")
        out = run_backtest()
        pnl, dd, tr = parse_results(out)
        key = (trigger, qty)
        results[key]    = {'pnl': pnl, 'dd': dd, 'tr': tr, 'label': label}
        log_path        = get_latest_trade_log()
        trade_logs[key] = load_trade_log(log_path)
        print(f"  結果: PnL={pnl:+.0f} USD  MaxDD={dd:.2f}%  Trades={tr}")

    # 設定をOFFに戻す
    set_scale_out_2(0, 2.0, 0.3)

    # ---- トレード詳細分析 ----
    print("\n" + "=" * 70)
    print("【トレード詳細分析】")
    print("=" * 70)
    analyses = {}
    for key in SWEEP_PATTERNS:
        label = results[key]['label']
        analyses[key] = analyze_trades(trade_logs[key], label)

    # ---- Stage-2発動トレードの個別比較 ----
    print("\n" + "=" * 70)
    print("【Stage-2発動トレードの個別比較】")
    print("(H-057でStage-2が発動したトレードのベースライン比較)")
    print("=" * 70)
    base_key = (0, 0.0)
    for key in SWEEP_PATTERNS[1:]:
        label = results[key]['label']
        compare_so2_trades(trade_logs[base_key], trade_logs[key], label)

    # ---- スイープ結果サマリ ----
    print("\n" + "=" * 70)
    print("【スイープ結果サマリ】")
    print("=" * 70)
    print(f"  {'設定':<26s}  {'PnL':>10s}  {'Δ':>8s}  {'MaxDD':>8s}  {'Δ':>8s}  {'Trades':>6s}  {'採用?'}")
    print("  " + "-" * 80)
    for key in SWEEP_PATTERNS:
        r = results[key]
        pnl = r['pnl'] or 0
        dd  = r['dd']  or 0
        tr  = r['tr']  or 0
        dpnl = pnl - BASELINE_PNL
        ddd  = dd  - BASELINE_MAXDD
        label = r['label']
        pnl_ok = pnl >= BASELINE_PNL
        dd_ok  = dd  <= BASELINE_MAXDD
        if pnl_ok and dd_ok:
            adopt = "✅ 採用候補"
        elif dd_ok:
            adopt = "⚠️ DD改善のみ"
        elif pnl_ok:
            adopt = "⚠️ PnL改善のみ"
        else:
            adopt = "❌ 非採用"
        print(f"  {label:<26s}  {pnl:>+10.0f}  {dpnl:>+8.0f}  {dd:>8.2f}%  {ddd:>+8.2f}%  {tr:>6d}  {adopt}")

    # ---- ATR標準化比較 ----
    print("\n" + "=" * 70)
    print("【ATR標準化PnL比較（Stage-2の質）】")
    print("=" * 70)
    for key in SWEEP_PATTERNS:
        trades = trade_logs[key]
        completed = [t for t in trades if t.get('result')]
        norm_all = [x for x in (compute_normalized_pnl(t) for t in completed) if x is not None]
        avg_all  = sum(norm_all) / len(norm_all) if norm_all else 0
        so2_trades = [t for t in completed
                      if any(e.get('type') == 'SCALE_OUT_2' for e in t.get('scale_events', []))]
        norm_so2 = [x for x in (compute_normalized_pnl(t) for t in so2_trades) if x is not None]
        avg_so2  = sum(norm_so2) / len(norm_so2) if norm_so2 else None
        label = results[key]['label']
        so2_str = f"Stage-2発動平均={avg_so2:+.3f}ATR ({len(so2_trades)}件)" if avg_so2 is not None else "Stage-2=0件"
        print(f"  [{label:26s}]  全体平均={avg_all:+.3f}ATR  {so2_str}")

    # ---- 最終判定 ----
    print("\n" + "=" * 70)
    print("【最終判定と考察】")
    print("=" * 70)

    best = None
    best_pnl = BASELINE_PNL - 0.01
    for key in SWEEP_PATTERNS[1:]:
        r = results[key]
        pnl = r['pnl'] or 0
        dd  = r['dd']  or 0
        if pnl >= BASELINE_PNL and dd <= BASELINE_MAXDD and pnl > best_pnl:
            best = key
            best_pnl = pnl

    if best:
        br = results[best]
        print(f"  最適パターン: {br['label']}")
        print(f"  結果: PnL={br['pnl']:+.0f} USD ({br['pnl']-BASELINE_PNL:+.0f})  "
              f"MaxDD={br['dd']:.2f}% ({br['dd']-BASELINE_MAXDD:+.2f}%)")
        print(f"  判定: ✅ 採用")
    else:
        print(f"  採用基準を満たすパターンなし → ❌ H-057 非採用")
        best_dd_key = min(SWEEP_PATTERNS[1:], key=lambda k: results[k]['dd'] or 999)
        br = results[best_dd_key]
        print(f"  参考（最DD改善）: {br['label']}  PnL={br['pnl']:+.0f}  MaxDD={br['dd']:.2f}%")

    # 考察
    print(f"\n【考察】")
    base_analysis = analyses[(0, 0.0)]
    so2_total_across = sum(analyses[k].get('so2_count', 0) for k in SWEEP_PATTERNS[1:])
    so2_per_pattern  = so2_total_across // max(len(SWEEP_PATTERNS) - 1, 1)
    print(f"  Stage-2発動件数（平均）: 約{so2_per_pattern}件 / {base_analysis.get('total', 0)}トレード")

    if best:
        so2_count = analyses[best].get('so2_count', 0)
        avg_norm  = analyses[best].get('avg_norm_so2')
        base_norm = analyses[(0, 0.0)].get('avg_norm', 0)
        diff_norm = (avg_norm - base_norm) if avg_norm is not None else None
        if diff_norm is not None:
            direction = "改善" if diff_norm > 0 else "悪化"
            print(f"  Stage-2発動トレードのATR標準化PnL変化: {diff_norm:+.3f}ATR ({direction})")
        print(f"  Stage-2は{so2_count}件のトレードに作用 → 大トレンド時の段階的利確として有効")
    else:
        so2_counts = [analyses[k].get('so2_count', 0) for k in SWEEP_PATTERNS[1:]]
        if max(so2_counts) == 0:
            print(f"  Stage-2発動件数0件 → trigger×ATRに達するトレードが少ない")
            print(f"  → より低いtrigger値（1.5等）でのテストを推奨")
        else:
            print(f"  Stage-2は発動するが全体PnL or MaxDDが悪化")
            print(f"  → 残ポジションの削減によるフラッグシップトレードの利益減少が原因の可能性")

    print("\n設定をOFF（デフォルト=0）に戻しました")
    print("=" * 70)


if __name__ == "__main__":
    main()
