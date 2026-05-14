#!/usr/bin/env python3
"""
H-059: スケールアウト後ブレイクイーブンストップ 検証スクリプト

仮説:
  スケールアウト（部分利確）発動後、残りポジションのストップを
  エントリー価格に移動 → 以後の損失トレードを「ほぼゼロ損益」に変換

【狙ったトレードと期待効果】
  - スケールアウトが発動したが最終的にストップヒットで損失になったトレード
  - 期待: ストップ移動により、それらのトレードのPnLが≈0に改善（下限保証）
  - 代償: 価格が一時的にエントリー価格近辺まで戻った後に再上昇したケースでは
          早期ストップアウトにより利益を取り損ねる可能性

【標準化分析】
  ATR標準化PnL = pnl_pct / (atr / entry_price * 100)
  = エントリー時ATRを1単位とした場合の損益倍数
  これにより価格帯に依存しないトレードの質を比較する

ベースライン(H-056 ScaleIn採用後): PnL=+3,417 USD / MaxDD=22.80%
採用基準: PnL >= +3,417 USD かつ MaxDD <= 22.80% (両指標維持 or 改善)
"""

import subprocess
import configparser
import re
import json
import os
import glob
from datetime import datetime

CONFIG_PATH = "src/config.ini"
BASELINE_PNL   = 3417.0
BASELINE_MAXDD = 22.80


def read_config():
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_PATH)
    return cfg

def write_config(cfg):
    with open(CONFIG_PATH, 'w') as f:
        cfg.write(f)

def set_break_even(enabled: int):
    cfg = read_config()
    cfg['ScaleOut']['break_even_after_scale_out'] = str(enabled)
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
    for pattern in [r"最大ドローダウン率:\s*([0-9]+\.?[0-9]*)\s*\[%\]", r"最大ドローダウン率[:\s]+([0-9]+\.?[0-9]*)"]:
        m = re.search(pattern, output)
        if m:
            max_dd = float(m.group(1))
            break
    m = re.search(r"Trades:\s*(\d+)", output)
    if m:
        trades = int(m.group(1))
    return pnl, max_dd, trades

def get_latest_trade_log(log_dir="src/logs"):
    """最新のtrade_log JSONファイルを返す"""
    pattern = os.path.join(log_dir, "trade_log_*.json")
    files = sorted(glob.glob(pattern))
    return files[-1] if files else None

def load_trade_log(filepath):
    if not filepath or not os.path.exists(filepath):
        return []
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('trades', [])

def compute_normalized_pnl(trade):
    """
    ATR標準化PnL = pnl_usd / ATR
    ATRはvolatilityフィルターの値で代替
    = 1ATR分の利益を基準にした標準化値（価格帯の影響なし）
    """
    entry = trade.get('entry', {})
    result = trade.get('result', {})
    if not result:
        return None
    atr = entry.get('filters', {}).get('volatility', {}).get('value', 0)
    pnl_usd = result.get('pnl_usd', None)
    if atr <= 0 or pnl_usd is None:
        return None
    return pnl_usd / atr

def analyze_trade_log(trades, label):
    """個別トレード分析"""
    completed = [t for t in trades if t.get('result') is not None]
    if not completed:
        print(f"  [{label}] 完了トレードなし")
        return {}

    # スケールイベント分析
    trades_with_scale_out = [t for t in completed if any(
        e['type'] == 'SCALE_OUT' for e in t.get('scale_events', [])
    )]
    trades_with_scale_in  = [t for t in completed if any(
        e['type'] == 'SCALE_IN' for e in t.get('scale_events', [])
    )]
    trades_scale_out_then_stop = [t for t in trades_with_scale_out
        if t.get('exit', {}).get('reason') == 'STOP_LOSS']
    trades_scale_out_winner = [t for t in trades_with_scale_out
        if t.get('result', {}).get('win', False)]

    # ATR標準化PnL
    norm_pnls = [compute_normalized_pnl(t) for t in completed]
    norm_pnls = [x for x in norm_pnls if x is not None]
    avg_norm = sum(norm_pnls) / len(norm_pnls) if norm_pnls else 0
    min_norm = min(norm_pnls) if norm_pnls else 0
    max_norm = max(norm_pnls) if norm_pnls else 0

    # スケールアウト→ストップのATR標準化PnL
    norm_so_stop = [compute_normalized_pnl(t) for t in trades_scale_out_then_stop]
    norm_so_stop = [x for x in norm_so_stop if x is not None]
    avg_so_stop = sum(norm_so_stop) / len(norm_so_stop) if norm_so_stop else None

    print(f"\n  [{label}] 全{len(completed)}トレード分析:")
    print(f"    ATR標準化PnL  平均={avg_norm:+.2f}ATR  最小={min_norm:+.2f}ATR  最大={max_norm:+.2f}ATR")
    print(f"    スケールアウト発動: {len(trades_with_scale_out)}件")
    print(f"      うちストップヒット: {len(trades_scale_out_then_stop)}件  "
          f"ATR標準化PnL平均={'N/A' if avg_so_stop is None else f'{avg_so_stop:+.2f}ATR'}")
    print(f"      うち勝ちトレード: {len(trades_scale_out_winner)}件")
    print(f"    スケールイン発動: {len(trades_with_scale_in)}件")

    return {
        'total': len(completed),
        'scale_out_count': len(trades_with_scale_out),
        'scale_out_then_stop': len(trades_scale_out_then_stop),
        'scale_in_count': len(trades_with_scale_in),
        'avg_norm_pnl': avg_norm,
        'min_norm_pnl': min_norm,
        'max_norm_pnl': max_norm,
        'avg_so_stop_norm': avg_so_stop,
        'trades_with_scale_out': trades_with_scale_out,
        'trades_scale_out_then_stop': trades_scale_out_then_stop,
    }

def compare_affected_trades(base_trades, h059_trades):
    """
    スケールアウト後にストップヒットしたトレードを突き合わせ比較
    エントリー日時でマッチング
    """
    def trade_key(t):
        return t.get('entry', {}).get('close_time_dt', '')

    base_by_key = {trade_key(t): t for t in base_trades if t.get('result')}
    h059_by_key = {trade_key(t): t for t in h059_trades if t.get('result')}
    common_keys = set(base_by_key.keys()) & set(h059_by_key.keys())

    changed = []
    for k in sorted(common_keys):
        bt = base_by_key[k]
        ht = h059_by_key[k]
        base_pnl = bt.get('result', {}).get('pnl_usd', 0)
        h059_pnl = ht.get('result', {}).get('pnl_usd', 0)
        diff = h059_pnl - base_pnl
        if abs(diff) > 0.5:  # 0.5 USD以上の差がある場合
            changed.append({
                'date': k,
                'side': bt.get('entry', {}).get('side', ''),
                'entry_price': bt.get('entry', {}).get('price', 0),
                'base_pnl': base_pnl,
                'h059_pnl': h059_pnl,
                'diff': diff,
                'base_exit': bt.get('exit', {}).get('reason', ''),
                'h059_exit': ht.get('exit', {}).get('reason', ''),
                'base_so': any(e['type'] == 'SCALE_OUT' for e in bt.get('scale_events', [])),
                'atr': bt.get('entry', {}).get('filters', {}).get('volatility', {}).get('value', 0),
                'norm_diff': compute_normalized_pnl(ht) - compute_normalized_pnl(bt)
                             if compute_normalized_pnl(ht) is not None and compute_normalized_pnl(bt) is not None
                             else None,
            })

    return changed


def main():
    print("=" * 70)
    print("H-059: スケールアウト後ブレイクイーブンストップ 検証")
    print(f"ベースライン: PnL={BASELINE_PNL:+.0f} USD / MaxDD={BASELINE_MAXDD:.2f}%")
    print("=" * 70)

    # ---- ベースライン（OFF） ----
    print("\n[1/2] ベースライン（break_even_after_scale_out=OFF）実行中...")
    set_break_even(0)
    base_output = run_backtest()
    base_pnl, base_dd, base_tr = parse_results(base_output)
    base_log_path = get_latest_trade_log()
    base_trades = load_trade_log(base_log_path)
    print(f"  結果: PnL={base_pnl:+.0f} USD  MaxDD={base_dd:.2f}%  Trades={base_tr}")

    base_analysis = analyze_trade_log(base_trades, "ベースライン OFF")

    # ---- H-059（ON） ----
    print("\n[2/2] H-059（break_even_after_scale_out=ON）実行中...")
    set_break_even(1)
    h059_output = run_backtest()
    h059_pnl, h059_dd, h059_tr = parse_results(h059_output)
    h059_log_path = get_latest_trade_log()
    h059_trades = load_trade_log(h059_log_path)
    print(f"  結果: PnL={h059_pnl:+.0f} USD  MaxDD={h059_dd:.2f}%  Trades={h059_tr}")

    h059_analysis = analyze_trade_log(h059_trades, "H-059 ON")

    # 設定を戻す
    set_break_even(0)

    # ---- トレード変化の比較 ----
    print("\n" + "=" * 70)
    print("【影響を受けたトレードの個別分析】")
    print("(ATR標準化: pnl / (atr/entry_price*100) = ATR倍数)")
    print("=" * 70)

    changed = compare_affected_trades(base_trades, h059_trades)

    if not changed:
        print("  PnLに差異のあるトレードはありませんでした")
    else:
        print(f"  PnL差異あり: {len(changed)}トレード\n")
        improved = [c for c in changed if c['diff'] > 0]
        worsened = [c for c in changed if c['diff'] < 0]

        print(f"  改善（PnL増加）: {len(improved)}件  悪化（PnL減少）: {len(worsened)}件")
        print()

        print("  ─── 改善トレード（BreakEvenが機能した） ───")
        for c in sorted(improved, key=lambda x: x['diff'], reverse=True)[:10]:
            so_mark = "✓SO" if c['base_so'] else "   "
            norm_str = f"{c['norm_diff']:+.2f}ATR" if c['norm_diff'] is not None else "N/A"
            print(f"  {c['date']} {c['side']:4s} @{c['entry_price']:,.0f}  "
                  f"[{so_mark}]  {c['base_exit']:15s} → {c['h059_exit']:15s}  "
                  f"PnL: {c['base_pnl']:+.1f} → {c['h059_pnl']:+.1f} USD ({c['diff']:+.1f})  "
                  f"ATR標準化差: {norm_str}")

        if worsened:
            print()
            print("  ─── 悪化トレード（早期ストップで機会損失） ───")
            for c in sorted(worsened, key=lambda x: x['diff'])[:5]:
                so_mark = "✓SO" if c['base_so'] else "   "
                norm_str = f"{c['norm_diff']:+.2f}ATR" if c['norm_diff'] is not None else "N/A"
                print(f"  {c['date']} {c['side']:4s} @{c['entry_price']:,.0f}  "
                      f"[{so_mark}]  {c['base_exit']:15s} → {c['h059_exit']:15s}  "
                      f"PnL: {c['base_pnl']:+.1f} → {c['h059_pnl']:+.1f} USD ({c['diff']:+.1f})  "
                      f"ATR標準化差: {norm_str}")

    # ---- ATR標準化サマリ比較 ----
    print("\n" + "=" * 70)
    print("【ATR標準化PnL分布比較】")
    print("=" * 70)
    ba = base_analysis
    ha = h059_analysis
    print(f"  平均ATR標準化PnL:     BASE={ba.get('avg_norm_pnl',0):+.3f}  H059={ha.get('avg_norm_pnl',0):+.3f}  "
          f"差={ha.get('avg_norm_pnl',0)-ba.get('avg_norm_pnl',0):+.3f}")
    print(f"  最小ATR標準化PnL:     BASE={ba.get('min_norm_pnl',0):+.3f}  H059={ha.get('min_norm_pnl',0):+.3f}")
    if ba.get('avg_so_stop_norm') is not None or ha.get('avg_so_stop_norm') is not None:
        b_so_str = f"{ba['avg_so_stop_norm']:+.3f}" if ba.get('avg_so_stop_norm') is not None else "N/A"
        h_so_str = f"{ha['avg_so_stop_norm']:+.3f}" if ha.get('avg_so_stop_norm') is not None else "N/A"
        print(f"  SO後ストップPnL平均:  BASE={b_so_str}  H059={h_so_str}")

    # ---- 最終判定 ----
    print("\n" + "=" * 70)
    print("【最終判定】")
    print("=" * 70)
    pnl_diff  = (h059_pnl or 0) - BASELINE_PNL
    dd_diff   = (h059_dd or 0) - BASELINE_MAXDD

    print(f"  PnL変化:   {BASELINE_PNL:+.0f} → {h059_pnl or 0:+.0f} USD  ({pnl_diff:+.0f}  {'✅' if pnl_diff >= 0 else '⚠️'})")
    print(f"  MaxDD変化: {BASELINE_MAXDD:.2f}% → {h059_dd or 0:.2f}%   ({dd_diff:+.2f}%  {'✅' if dd_diff <= 0 else '⚠️'})")

    pnl_pass = (h059_pnl or 0) >= BASELINE_PNL
    dd_pass  = (h059_dd or 0) <= BASELINE_MAXDD

    if pnl_pass and dd_pass:
        verdict = "✅ 採用"
        reason  = "PnL維持 + MaxDD改善"
    elif dd_pass and not pnl_pass:
        verdict = "⚠️ 要検討"
        reason  = "MaxDD改善だがPnL低下 — DDリスク優先なら採用余地あり"
    elif pnl_pass and not dd_pass:
        verdict = "⚠️ 要検討"
        reason  = "PnL改善だがMaxDD悪化"
    else:
        verdict = "❌ 非採用"
        reason  = "PnL・MaxDDともに悪化"

    print(f"\n  判定: {verdict}")
    print(f"  理由: {reason}")

    # 考察
    n_improved = len([c for c in changed if c['diff'] > 0]) if changed else 0
    n_worsened = len([c for c in changed if c['diff'] < 0]) if changed else 0
    n_so_count = base_analysis.get('scale_out_count', 0)
    n_so_stop  = base_analysis.get('scale_out_then_stop', 0)

    print(f"\n【考察】")
    print(f"  スケールアウト発動総数: {n_so_count}件")
    print(f"  スケールアウト後ストップヒット: {n_so_stop}件 "
          f"({'%.0f' % (n_so_stop/n_so_count*100 if n_so_count else 0)}%)")
    print(f"  BreakEvenで改善したトレード: {n_improved}件")
    print(f"  BreakEvenで悪化したトレード: {n_worsened}件 (早期ストップ)")

    if n_so_stop == 0:
        print("  → スケールアウト後にストップヒットするトレードがほぼ存在しないため、")
        print("     BreakEvenストップが発動する機会が少なく効果が限定的")
    elif n_improved > n_worsened:
        print(f"  → BreakEvenは主に損失削減に機能している（改善{n_improved} > 悪化{n_worsened}）")
    else:
        print(f"  → BreakEvenによる早期ストップが機会損失を生んでいる可能性あり")

    print("\n設定をOFF（ベースライン）に戻しました")
    print("=" * 70)


if __name__ == "__main__":
    main()
