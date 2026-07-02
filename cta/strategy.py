"""CTA戦略: マルチホライズントレンド + 逆vol配分 + volターゲティング + サーキットブレーカー。

自由パラメータは意図的に最小:
  - トレンドホライズン3組（10/40, 30/120, 60/240日）— time-series momentumの標準的な設定
  - vol推定窓（30日）
  - target_vol / max_gross / リバランス頻度
経済的根拠: TSMOM（時系列モメンタム）は投資家の行動バイアス（アンダーリアクション→
トレンド持続）に由来し、資産クラス横断で100年以上観測されている構造的エッジ。
volターゲティングはリスクを一定化しDDのテールを削る。

バックテストとペーパー/ライブは本モジュールの target_weights() を共有する。
"""
import numpy as np


def ewma(x, span):
    """NaN耐性EWMA（上場前NaNはスキップし、最初の有効値から開始）。"""
    a = 2.0 / (span + 1.0)
    out = np.full_like(x, np.nan, dtype=float)
    prev = np.nan
    for i in range(len(x)):
        v = x[i]
        if np.isnan(v):
            out[i] = prev
            continue
        prev = v if np.isnan(prev) else a * v + (1 - a) * prev
        out[i] = prev
    return out


def trend_signal(log_close, horizons_bars):
    """複数ホライズンのEWMA交差の符号平均 → [-1, 1]。

    上場直後の未成熟なEWMAで取引しないよう、各ホライズンは有効データが
    slowスパン分蓄積されるまでNaN（=取引対象外）とする。"""
    n_valid = np.cumsum(~np.isnan(log_close))
    sig = np.zeros(len(log_close))
    valid = np.zeros(len(log_close))
    for (f, s) in horizons_bars:
        ef, es = ewma(log_close, f), ewma(log_close, s)
        d = ef - es
        ok = (~np.isnan(d)) & (n_valid >= s)
        sig[ok] += np.sign(d[ok])
        valid[ok] += 1
    out = np.full(len(log_close), np.nan)
    ok = valid == len(horizons_bars)
    out[ok] = sig[ok] / len(horizons_bars)
    return out


def trailing_vol(rets, window, bars_per_year):
    """各時点の年率ボラ（過去window本、NaNは除外。有効本数が半分未満ならNaN）。"""
    T = len(rets)
    out = np.full(T, np.nan)
    for i in range(window, T):
        w = rets[i - window:i]
        w = w[~np.isnan(w)]
        if len(w) >= window // 2:
            out[i] = w.std() * np.sqrt(bars_per_year)
    return out


def portfolio_vol(weights, rets_window, bars_per_year):
    """重みベクトルとリターン窓から年率ポートフォリオvolを推定（サンプル共分散）。"""
    active = np.abs(weights) > 1e-12
    if not active.any():
        return 0.0
    w = weights[active]
    r = rets_window[:, active]
    ok = ~np.isnan(r).any(axis=1)
    r = r[ok]
    if len(r) < 10:
        return 0.0
    cov = np.cov(r, rowvar=False) * bars_per_year
    cov = np.atleast_2d(cov)
    return float(np.sqrt(max(w @ cov @ w, 0.0)))


def target_weights(sig_t, vol_t, rets_window, target_vol, max_gross, bars_per_year):
    """時点tの目標ウェイト（対equity比、符号付き）を返す。

    1. 逆volでシグナルを配分（リスク均等化）
    2. ポートフォリオvolがtarget_volになるようスケール
    3. グロスレバレッジをmax_grossでキャップ
    """
    N = len(sig_t)
    raw = np.zeros(N)
    for j in range(N):
        s, v = sig_t[j], vol_t[j]
        if not np.isnan(s) and not np.isnan(v) and v > 1e-6:
            raw[j] = s / v
    gross_raw = np.abs(raw).sum()
    if gross_raw < 1e-12:
        return np.zeros(N)
    w = raw / gross_raw  # gross=1に正規化
    pvol = portfolio_vol(w, rets_window, bars_per_year)
    if pvol < 1e-8:
        return np.zeros(N)
    w = w * (target_vol / pvol)
    gross = np.abs(w).sum()
    if gross > max_gross:
        w = w * (max_gross / gross)
    return w


class CircuitBreaker:
    """DDに応じたデレバレッジ/停止。backtest/liveで同一ロジックを共有。

    - drawdown >= dd_soft: target_volを半減（scale=0.5）
    - drawdown >= dd_hard: 全クローズしhalt（人手で解除するまで再開しない）
    """

    def __init__(self, dd_soft, dd_hard):
        self.dd_soft = dd_soft
        self.dd_hard = dd_hard
        self.peak = -np.inf
        self.halted = False

    def update(self, equity):
        """equity更新ごとに呼ぶ。現在のvolスケール（0.0/0.5/1.0）を返す。"""
        self.peak = max(self.peak, equity)
        dd = 1.0 - equity / self.peak if self.peak > 0 else 0.0
        if dd >= self.dd_hard:
            self.halted = True
        if self.halted:
            return 0.0
        if dd >= self.dd_soft:
            return 0.5
        return 1.0

    @property
    def state(self):
        return {"peak": self.peak, "halted": self.halted}
