"""実発注トレーダー（Bitget）。

判断ロジックは cta/decision.py をペーパートレードと共有し、本モジュールは
「注文を実際に取引所へ出す」ことと「実弾ならではの安全ガード」だけを担う。

安全ガード:
  ①資金上限   : max_live_capital_usd を超える建玉を作らない
  ②取引所照合 : 毎サイクル実残高と内部帳簿を突合
                 - 通常時に不一致 → 発注せず停止（実態不明のまま新規建てしない）
                 - **緊急クローズ時は不一致でも取引所の実数量で決済を断行**
                   （止めるとブレーカーが損失を垂れ流すため）
  ③残高確認   : 実際のavailableが不足していたら発注しない
  ④単発上限   : 1注文がequityの一定割合を超えたら異常とみなし拒否
  ⑤明示有効化 : enable_live=True でなければ実発注APIを呼ばない
  ⑥ドライラン : dry_run=True で全経路を通すが発注だけしない
"""
import csv
import datetime as dt
import json
import os
import time

import numpy as np

from . import data as data_mod
from . import decision
from . import execution as ex
from . import strategy as st
from .live_execution import BitgetLiveExecutor, OrderPlacementError
from .notify import send_alert

STATE_FILE = "state/live_state.json"
TRADES_CSV = "state/live_trades.csv"
EQUITY_CSV = "state/live_equity.csv"


class LiveGuardError(RuntimeError):
    """安全ガードが発注を拒否したときに送出する。"""


class LiveTrader:
    def __init__(self, cfg, executor, base_dir=".", enable_live=False,
                 dry_run=False, max_live_capital_usd=None,
                 # max_gross=3.0 なので単一銘柄に全グロスが寄れば理論上3倍まで
                 # あり得る。逆vol配分の7銘柄では実際は1倍未満に収まるため、
                 # 1.5倍を「明らかな異常」の閾値とする（単位バグ等は桁で外れる）。
                 max_order_pct_of_equity=1.5):
        self.cfg = cfg
        self.executor = executor
        self.base = base_dir
        self.enable_live = enable_live
        self.dry_run = dry_run
        self.max_capital = max_live_capital_usd or cfg.init_capital_usd
        self.max_order_pct = max_order_pct_of_equity
        self.state_path = os.path.join(base_dir, STATE_FILE)
        self.trades_path = os.path.join(base_dir, TRADES_CSV)
        self.equity_path = os.path.join(base_dir, EQUITY_CSV)
        os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
        self.cost_model = ex.CostModel(cfg.fee_rate, cfg.slip_rate,
                                       cfg.min_notional_usd)
        self._load_state()

    # --- 状態管理 -----------------------------------------------------
    def _load_state(self):
        if os.path.exists(self.state_path):
            s = json.load(open(self.state_path))
            self.breaker = st.CircuitBreaker(self.cfg.dd_soft, self.cfg.dd_hard)
            self.breaker.peak = s.get("peak", -np.inf)
            self.breaker.halted = s.get("halted", False)
            self.last_bar = s.get("last_bar", 0)
            self.mismatch_halt = s.get("mismatch_halt", False)
        else:
            self.breaker = st.CircuitBreaker(self.cfg.dd_soft, self.cfg.dd_hard)
            self.last_bar = 0
            self.mismatch_halt = False

    def _save_state(self, equity=None, positions=None):
        json.dump({"peak": self.breaker.peak, "halted": self.breaker.halted,
                   "last_bar": self.last_bar,
                   "mismatch_halt": self.mismatch_halt,
                   "equity": equity, "positions": positions or {},
                   "updated": dt.datetime.now(dt.timezone.utc).isoformat()},
                  open(self.state_path, "w"), indent=1)

    def _log_fill(self, fill, mode):
        new = not os.path.exists(self.trades_path)
        with open(self.trades_path, "a", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["ts_utc", "mode", "symbol", "qty", "signal_price",
                            "ref_price", "fill_price", "fee_usd",
                            "slippage_usd", "signal_deviation_usd", "reason"])
            w.writerow([dt.datetime.utcfromtimestamp(fill.ts or time.time()).isoformat(),
                        mode, fill.symbol, f"{fill.qty:.8f}", fill.signal_price,
                        fill.ref_price, fill.fill_price, f"{fill.fee_usd:.6f}",
                        f"{fill.slippage_usd:.6f}",
                        f"{fill.signal_deviation_usd:.6f}", fill.reason])

    def _log_equity(self, ts, equity, gross, scale, note=""):
        new = not os.path.exists(self.equity_path)
        with open(self.equity_path, "a", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["ts_utc", "equity_usd", "gross_notional_usd",
                            "vol_scale", "halted", "note"])
            w.writerow([dt.datetime.utcfromtimestamp(ts).isoformat(),
                        f"{equity:.4f}", f"{gross:.4f}", scale,
                        self.breaker.halted, note])

    # --- 安全ガード ---------------------------------------------------
    def _check_order(self, order, price, equity):
        """発注前チェック。問題があればLiveGuardErrorを送出する。"""
        notional = abs(order.qty) * price
        if notional > equity * self.max_order_pct:
            raise LiveGuardError(
                f"ガード④: {order.symbol} の注文 ${notional:.2f} が "
                f"equityの{self.max_order_pct:.0%}(${equity*self.max_order_pct:.2f})を超過")
        return True

    def _check_capital(self, equity):
        if equity > self.max_capital * 1.5:
            raise LiveGuardError(
                f"ガード①: equity ${equity:.2f} が上限 ${self.max_capital:.2f} を"
                f"大きく超過。設定ミスの可能性があるため停止")

    # --- 1サイクル ----------------------------------------------------
    def run_once(self, refresh=True, now=None):
        cfg = self.cfg
        if refresh:
            for sym in cfg.symbols:
                data_mod.fetch_and_cache(cfg.db_path, sym, cfg.timeframe_min,
                                         time.time() - 3 * 86400, time.time(),
                                         "bybit")
        times, _, closes_df = data_mod.load_universe(
            cfg.db_path, cfg.symbols, cfg.timeframe_min)
        closes = closes_df.to_numpy(float)
        now = now or time.time()
        t = int(np.searchsorted(times, now, side="right")) - 1
        if t < 0:
            raise RuntimeError("確定バーがキャッシュにありません")

        # --- ガード②: 取引所の実ポジションを取得（これが唯一の真実） ---
        recon = self.executor.reconcile_positions(cfg.symbols, {})
        real_pos = recon["exchange_positions"]
        prices = {}
        for j, sym in enumerate(cfg.symbols):
            px = closes[t, j]
            if not np.isnan(px):
                prices[sym] = float(px)

        equity = self._fetch_equity()
        self._check_capital(equity)
        vol_scale = self.breaker.update(equity)
        signal_prices = {s: prices.get(s, 0.0) for s in cfg.symbols}

        mode = "dry_run" if (self.dry_run or not self.enable_live) else "live"
        fills, errors = [], []

        # --- 緊急クローズ: 照合不一致があっても断行する ---
        if self.breaker.halted:
            orders = decision.plan_flatten_orders(real_pos, signal_prices)
            for od in orders:
                try:
                    f = self._place(od, t, times, mode)
                    if f:
                        fills.append(f)
                except Exception as e:
                    errors.append(f"{od.symbol}: {e}")
            note = "circuit_breaker_flatten"
            if errors:
                send_alert("緊急クローズで発注エラー",
                           "サーキットブレーカー作動中の決済に失敗しました。\n"
                           "手動確認が必要です。\n\n" + "\n".join(errors))
            self._finish(now, equity, real_pos, vol_scale, note, fills)
            return {"mode": mode, "halted": True, "n_fills": len(fills),
                    "errors": errors, "equity": equity, "note": note}

        # --- 通常時: 照合不一致なら新規建てを止める ---
        internal = json.load(open(self.state_path)).get("positions", {}) \
            if os.path.exists(self.state_path) else {}
        mism = {s: {"exchange": real_pos.get(s, 0.0), "internal": internal.get(s, 0.0)}
                for s in cfg.symbols
                if abs(real_pos.get(s, 0.0) - internal.get(s, 0.0)) > 1e-9}
        if mism and internal:
            self.mismatch_halt = True
            send_alert("ポジション不一致を検知（発注を停止）",
                       "取引所の実ポジションと内部帳簿が一致しません。\n"
                       "自動修正はせず新規発注を停止しました。手動確認してください。\n"
                       "※緊急クローズが必要な場合は取引所の実数量で決済されます。\n\n"
                       + json.dumps(mism, indent=1))
            self._finish(now, equity, real_pos, vol_scale, "mismatch_halt", [])
            return {"mode": mode, "halted": False, "mismatch": mism,
                    "n_fills": 0, "equity": equity, "note": "mismatch_halt"}

        if times[t] <= self.last_bar:
            self._finish(now, equity, real_pos, vol_scale, "bar_already_done", [])
            return {"mode": mode, "skipped": "bar already processed",
                    "equity": equity, "halted": False}

        # --- 通常リバランス ---
        orders = decision.plan_orders(cfg, closes, t, real_pos, equity,
                                      vol_scale, self.cost_model, prices)
        # ガード③: 新規建てに必要な余力があるか（決済方向は余力を消費しない）
        available = self.executor.fetch_available_usd()
        need = sum(abs(o.qty) * prices[o.symbol] for o in orders
                   if abs(o.qty + real_pos.get(o.symbol, 0.0))
                   > abs(real_pos.get(o.symbol, 0.0)))
        if need > 0 and available <= 0:
            send_alert("発注余力なし（発注をスキップ）",
                       f"新規建てに ${need:.2f} 必要ですが、利用可能額が "
                       f"${available:.2f} です。発注しませんでした。")
            self._finish(now, equity, real_pos, vol_scale, "no_margin", [])
            return {"mode": mode, "halted": False, "n_fills": 0,
                    "equity": equity, "note": "no_margin"}

        for od in orders:
            try:
                self._check_order(od, prices[od.symbol], equity)
                f = self._place(od, t, times, mode)
                if f:
                    fills.append(f)
            except LiveGuardError as e:
                errors.append(str(e))
            except OrderPlacementError as e:
                errors.append(f"{od.symbol}: {e}")
        if errors:
            send_alert("発注ガード/エラー", "\n".join(errors))

        self.last_bar = float(times[t])
        after = self.executor.reconcile_positions(cfg.symbols, {})["exchange_positions"] \
            if mode == "live" else real_pos
        self._finish(now, equity, after, vol_scale, "rebalance", fills)
        planned = [{"symbol": o.symbol, "qty": round(o.qty, 8),
                    "price": round(prices[o.symbol], 6),
                    "notional_usd": round(abs(o.qty) * prices[o.symbol], 2),
                    "side": "buy" if o.qty > 0 else "sell"}
                   for o in orders]
        return {"mode": mode, "halted": False, "n_fills": len(fills),
                "n_planned": len(orders), "planned_orders": planned,
                "errors": errors, "equity": equity, "positions": after}

    def _place(self, order, t, times, mode):
        if mode != "live":
            return None                      # ガード⑤⑥: 実発注しない
        fill = self.executor.place_order(order, bar_epoch=times[t],
                                         min_notional_usd=self.cfg.min_notional_usd)
        self._log_fill(fill, mode)
        return fill

    def _fetch_equity(self):
        """取引所の実残高からequityを取得（内部帳簿を信用しない）。"""
        return self.executor.fetch_equity_usd()

    def _finish(self, now, equity, positions, vol_scale, note, fills):
        gross = sum(abs(v) for v in positions.values())
        self._log_equity(now, equity, gross, vol_scale, note)
        # ドライランは状態を書き換えない。
        # 【2026-08-15、実発注開始の直前に発覚】ドライランが last_bar を
        # 進めてしまい、直後の実発注が「処理済みバー」としてスキップされた。
        # 検証のための実行が本番の発注を妨げてはならない。
        if self.enable_live and not self.dry_run:
            self._save_state(equity, positions)
