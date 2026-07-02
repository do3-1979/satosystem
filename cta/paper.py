"""ペーパートレーダー — バックテストと構造的に同一のコードパスでフォワード検証する。

gen2の教訓への対応:
  - シグナル計算は strategy.target_weights()、約定/コストは execution.* を
    バックテストとそのまま共有（本モジュールに独自の約定式は存在しない）
  - signal価格（判定バー終値）と ref価格（発注時live mid）と fill価格を
    全取引で記録し、backtest⇔live乖離を初日から観測可能にする
  - サーキットブレーカー状態は永続化され、halt後は人手で解除するまで再開しない

実発注コードは存在しない（Phase 5でユーザーの明示的承認後に実装する）。
"""
import csv
import datetime as dt
import json
import os
import time

import numpy as np

from . import data as data_mod
from . import execution as ex
from . import strategy as st

STATE_FILE = "state/paper_state.json"
TRADES_CSV = "state/paper_trades.csv"
EQUITY_CSV = "state/paper_equity.csv"


class PaperTrader:
    def __init__(self, cfg, base_dir=".", exchange_id="bybit"):
        self.cfg = cfg
        self.base = base_dir
        self.exchange_id = exchange_id
        self.state_path = os.path.join(base_dir, STATE_FILE)
        self.trades_path = os.path.join(base_dir, TRADES_CSV)
        self.equity_path = os.path.join(base_dir, EQUITY_CSV)
        os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
        self.cost_model = ex.CostModel(cfg.fee_rate, cfg.slip_rate,
                                       cfg.min_notional_usd)
        self._load_state()

    # --- 状態管理 -------------------------------------------------
    def _load_state(self):
        if os.path.exists(self.state_path):
            with open(self.state_path) as f:
                s = json.load(f)
            self.pf = ex.Portfolio(s["cash_usd"], s["positions"])
            self.breaker = st.CircuitBreaker(self.cfg.dd_soft, self.cfg.dd_hard)
            self.breaker.peak = s["peak"]
            self.breaker.halted = s["halted"]
            self.last_bar = s.get("last_bar", 0)
        else:
            self.pf = ex.Portfolio(cash_usd=self.cfg.init_capital_usd)
            self.breaker = st.CircuitBreaker(self.cfg.dd_soft, self.cfg.dd_hard)
            self.last_bar = 0

    def _save_state(self):
        with open(self.state_path, "w") as f:
            json.dump({"cash_usd": self.pf.cash_usd,
                       "positions": self.pf.positions,
                       "peak": self.breaker.peak,
                       "halted": self.breaker.halted,
                       "last_bar": self.last_bar,
                       "updated": dt.datetime.now(dt.timezone.utc).isoformat()},
                      f, indent=1)

    def _log_fill(self, fill):
        new = not os.path.exists(self.trades_path)
        with open(self.trades_path, "a", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["ts_utc", "symbol", "qty", "signal_price",
                            "ref_price", "fill_price", "fee_usd",
                            "slippage_usd", "signal_deviation_usd", "reason"])
            w.writerow([dt.datetime.utcfromtimestamp(fill.ts).isoformat(),
                        fill.symbol, f"{fill.qty:.8f}",
                        fill.signal_price, fill.ref_price, fill.fill_price,
                        f"{fill.fee_usd:.6f}", f"{fill.slippage_usd:.6f}",
                        f"{fill.signal_deviation_usd:.6f}", fill.reason])

    def _log_equity(self, ts, equity, gross, scale):
        new = not os.path.exists(self.equity_path)
        with open(self.equity_path, "a", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["ts_utc", "equity_usd", "gross_notional_usd",
                            "vol_scale", "halted"])
            w.writerow([dt.datetime.utcfromtimestamp(ts).isoformat(),
                        f"{equity:.4f}", f"{gross:.4f}", scale,
                        self.breaker.halted])

    # --- データ取得 -----------------------------------------------
    def refresh_cache(self, lookback_days=3):
        since = time.time() - lookback_days * 86400
        for sym in self.cfg.symbols:
            data_mod.fetch_and_cache(self.cfg.db_path, sym,
                                     self.cfg.timeframe_min, since,
                                     time.time(), self.exchange_id)

    def live_mid(self, symbol):
        import ccxt
        ex_ = getattr(ccxt, self.exchange_id)({"enableRateLimit": True})
        t = ex_.fetch_ticker(symbol)
        bid, ask = t.get("bid"), t.get("ask")
        if bid and ask:
            return (bid + ask) / 2
        return t["last"]

    # --- 1サイクル ------------------------------------------------
    def run_once(self, refresh=True, price_fn=None, now=None):
        """4H足確定後に1回呼ぶ（cron想定）。price_fn/nowはテスト用フック。"""
        cfg = self.cfg
        if refresh:
            self.refresh_cache()
        times, opens_df, closes_df = data_mod.load_universe(
            cfg.db_path, cfg.symbols, cfg.timeframe_min)
        closes = closes_df.to_numpy(float)
        now = now or time.time()
        t = int(np.searchsorted(times, now, side="right")) - 1
        if t < 0:
            raise RuntimeError("no completed bar in cache")

        # 1) 時価評価とブレーカーを最優先で判定する。
        #    バーが未更新（API障害等）でも暴落時のキルスイッチは作動させる。
        price_fn = price_fn or self.live_mid
        prices = {}
        for j, sym in enumerate(cfg.symbols):
            try:
                prices[sym] = price_fn(sym)
            except Exception:
                px = closes[t, j]
                if not np.isnan(px):
                    prices[sym] = float(px)
        eq = self.pf.equity(prices)
        vol_scale = self.breaker.update(eq)

        fills = []
        if self.breaker.halted:
            # キルスイッチ: 全クローズのみ実行
            for sym, q in list(self.pf.positions.items()):
                if q != 0.0 and sym in prices:
                    od = ex.Order(sym, -q, closes[t, cfg.symbols.index(sym)],
                                  reason="circuit_breaker")
                    fills.append(ex.execute_order(od, prices[sym],
                                                  self.cost_model, ts=now))
        elif times[t] <= self.last_bar:
            self._log_equity(now, eq, self.pf.gross_notional(prices), vol_scale)
            self._save_state()
            return {"skipped": "bar already processed", "bar": float(times[t]),
                    "equity": eq, "halted": False}
        else:
            bpd, bpy = cfg.bars_per_day, cfg.bars_per_year
            logc = np.log(closes)
            rets = np.vstack([np.full((1, closes.shape[1]), np.nan),
                              np.diff(logc, axis=0)])
            horizons = [(f * bpd, s * bpd) for f, s in cfg.horizons_days]
            sig_t = np.array([st.trend_signal(logc[:t + 1, j], horizons)[-1]
                              for j in range(closes.shape[1])])
            vol_t = np.array([st.trailing_vol(rets[:t + 1, j],
                                              cfg.vol_window_days * bpd, bpy)[-1]
                              for j in range(closes.shape[1])])
            w = st.target_weights(sig_t, vol_t,
                                  rets[t - cfg.vol_window_days * bpd:t],
                                  cfg.target_vol * vol_scale, cfg.max_gross, bpy)
            for j, sym in enumerate(cfg.symbols):
                if sym not in prices or np.isnan(closes[t, j]):
                    continue
                od = ex.plan_rebalance(sym, self.pf.positions.get(sym, 0.0),
                                       w[j] * eq, closes[t, j], eq,
                                       self.cost_model, cfg.no_trade_band_pct)
                if od is not None:
                    # ref価格=発注時のlive mid（backtestでは次足始値に相当）
                    fills.append(ex.execute_order(od, prices[sym],
                                                  self.cost_model, ts=now))

        for f in fills:
            self.pf.apply_fill(f)
            self._log_fill(f)
        eq_after = self.pf.equity(prices)
        self._log_equity(now, eq_after, self.pf.gross_notional(prices),
                         vol_scale)
        self.last_bar = float(times[t])
        self._save_state()
        return {"bar": float(times[t]), "equity": eq_after,
                "n_fills": len(fills), "vol_scale": vol_scale,
                "halted": self.breaker.halted,
                "positions": dict(self.pf.positions)}
