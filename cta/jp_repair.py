"""東証上場ETFの価格系列を修復する。

■なぜ必要か（2026-08-15の検証で発覚）
  yfinance(Yahoo)の日本銘柄データには2種類の破損がある。

    (a) 株式分割を splits に記録しないまま価格だけ 1/10 になる（調整漏れ）
        例: 1306.T は splits が空なのに 2015-01-05 と 2026-03-30 で価格が 1/10
    (b) 単日だけ桁が化け、翌日に戻る（一過性の異常値）
        例: 1326.T で「-99% → 翌日 +9,059%」が21回

  どちらも「1日で-99%」という実在しない値動きになり、トレンド判定・
  ボラ推定・サーキットブレーカーのすべてを狂わせる。
  実際、修復前のデータでは平均ペア相関が 0.143 と出たが、
  修復後の真値は 0.330 だった（結論が逆転する規模の差）。

■方針
  1. 単日スパイク（t日で跳ねt+1日で戻る）は、その日を欠損として除去
  2. 残った持続的な段差は未記録の分割とみなし、それ以前を係数で再スケール
     （常に「最新の価格スケール」に合わせる。発注数量は最新スケールで
       計算されるため、ここを基準にしないと数量が桁違いになる）

■検証方法（修復が正しいかを確かめた手順・再検証時も同じ手順を使うこと）
  対応する海外指標×USDJPY と突き合わせ、
    - 年率リターンが ±1〜3% 以内で一致すること
    - 海外資産連動ETFは lag+1 で相関が最大になること
      （東証15:00終値がNY前日終値を反映する時差。lag0が最大なら疑う）
  を確認する。相関の絶対値が低いことだけを根拠に破損と判断してはいけない。

【重要】この修復は系列全体を再スケールするため、部分的な追記では正しく動かない。
必ず全履歴を取得し直して INSERT OR REPLACE で上書きすること
（cta/etf_data.py の fetch_and_cache はその設計になっている）。
"""
import numpy as np

# ETFの日次変動がこれを超えることは実在しない（超えたら破損を疑う）
JUMP_LOG = np.log(2.5)
# 跳ねた翌日に戻ったとみなす許容幅
ROUNDTRIP_LOG = np.log(1.3)
# 未記録分割として認める比率の候補
SPLIT_RATIOS = np.array([1/100, 1/10, 1/5, 1/4, 1/3, 1/2, 2, 3, 4, 5, 10, 100], float)
# 候補比率からこれ以上ずれていたら分割と断定しない（放置してログに残す）
RATIO_TOLERANCE_LOG = np.log(1.25)
MAX_SPIKE_PASSES = 50


def repair_close_series(s):
    """終値Seriesを修復する。

    s: pandas.Series（index=日付昇順, value=終値）
    Returns: (修復後Series, 適用内容のリスト[str])
    """
    s = s.dropna().astype(float).copy()
    notes = []
    if len(s) < 3:
        return s, notes

    # --- 1. 単日スパイクの除去 ---
    for _ in range(MAX_SPIKE_PASSES):
        r = np.log(s / s.shift(1))
        idx = np.flatnonzero(np.abs(r.values) > JUMP_LOG)
        hit = None
        for i in idx:
            if i + 1 < len(r) and abs(r.values[i] + r.values[i + 1]) < ROUNDTRIP_LOG:
                hit = i
                break
        if hit is None:
            break
        notes.append(f"単日スパイク除去 {s.index[hit]} "
                     f"({np.expm1(r.values[hit]) * 100:+.0f}%)")
        s = s.drop(s.index[hit])

    # --- 2. 未記録の分割による段差を再スケール ---
    # 後ろから処理する。前を書き換えても後段の判定に影響しないため。
    r = np.log(s / s.shift(1))
    for i in np.flatnonzero(np.abs(r.values) > JUMP_LOG)[::-1]:
        ratio = s.iloc[i] / s.iloc[i - 1]
        f = SPLIT_RATIOS[np.argmin(np.abs(np.log(SPLIT_RATIOS) - np.log(ratio)))]
        if abs(np.log(ratio / f)) > RATIO_TOLERANCE_LOG:
            # 分割比に当てはまらない段差。勝手に直すと実在の急変を消しかねない
            notes.append(f"⚠未分類の段差 {s.index[i]} ratio={ratio:.3f}（未修正）")
            continue
        notes.append(f"分割調整 {s.index[i]} 以前を×{f:.4g}")
        s.iloc[:i] = s.iloc[:i] * f
    return s, notes


def residual_anomalies(s, max_daily=0.25):
    """修復後に残った異常変動を返す（健全性チェック用）。

    原油ETFの2020年など**実在する**急変も拾うため、
    ゼロでないこと自体は異常ではない。中身を見て判断すること。
    """
    r = s.pct_change().dropna()
    return r[r.abs() > max_daily]


def is_jp_symbol(symbol):
    """東証銘柄か（yfinanceの '.T' サフィックス）。修復対象の判定に使う。"""
    return str(symbol).upper().endswith(".T")
