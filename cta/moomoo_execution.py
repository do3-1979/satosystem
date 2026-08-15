"""実発注の執行層（moomoo証券・米国ETF）。

cta/execution.py の Order/Fill をそのまま使い、Bitget版(live_execution.py)と
同じインターフェースを提供する。呼び出し側(live_trader.py)から見て
両者を差し替えられるようにしてある。

■moomoo固有の制約（問い合わせで確認済み・2026-08-14）
  - **Client Order ID / Idempotency Key に非対応**。取引所側では重複を弾けない。
    → `remark` に決定的なIDを入れ、発注前に当日の注文一覧を照会して
      同じremarkが無いことを確認してから発注する（自前の冪等性）。
      Bitget版はclientOidで取引所が弾いてくれたが、こちらは弾いてくれない。
      照会と発注の間の競合は cron のロックで防ぐ（run_etf_live.py 側）。
  - **発注レート制限**: 同一acc_idで30秒に最大15回、連続間隔0.02秒以上。
    → 19銘柄を一度に出すと超過するため、15件ごとに30秒待つ。
  - **端数株のAPI発注に非対応** → 1株単位（config の integer_shares=true）。
  - OpenD(ゲートウェイ)の常時起動が前提。**ARM64非対応**のためRPiでは動かない。
"""
import datetime as dt
import hashlib
import time

from . import execution as ex

# レート制限（moomoo回答値。安全側に少し余裕を持たせる）
MAX_ORDERS_PER_WINDOW = 15
RATE_WINDOW_SEC = 30.0
MIN_ORDER_INTERVAL_SEC = 0.05      # 回答は0.02秒以上。倍以上の余裕を取る


class MoomooOrderError(RuntimeError):
    pass


def order_tag(symbol, bar_date):
    """remarkに入れる決定的なID。同じ意図の注文は必ず同じ文字列になる。

    moomooのremarkは長さ制限があるため短く保つ。symbol+日付から生成し、
    衝突を避けるためハッシュを付ける。"""
    raw = f"cta-{symbol}-{bar_date}"
    return "cta" + hashlib.sha1(raw.encode()).hexdigest()[:16]


class MoomooExecutor:
    """OpenD経由でmoomoo証券に発注する。

    trade_ctx: moomoo.OpenSecTradeContext 相当。テストではフェイクを注入する。
    trd_env  : 'REAL'(本番) / 'SIMULATE'(模擬)
    """

    def __init__(self, trade_ctx, acc_id=0, trd_env="REAL", unlock_password=None,
                 session="RTH"):
        self.ctx = trade_ctx
        self.acc_id = acc_id
        self.trd_env = trd_env
        self.session = session
        self._unlocked = False
        self._unlock_password = unlock_password
        self._order_times = []          # レート制限の追跡用

    # --- 前処理 -------------------------------------------------------
    def ensure_unlocked(self):
        """取引ロックを解除する。moomooは発注前にunlock_tradeが必要。"""
        if self._unlocked or not self._unlock_password:
            return
        ret, data = self.ctx.unlock_trade(password=self._unlock_password)
        if ret != 0:
            raise MoomooOrderError(f"取引ロック解除に失敗: {data}")
        self._unlocked = True

    def _respect_rate_limit(self):
        """30秒15回・間隔0.05秒を守る。超えそうなら待つ。

        19銘柄を一度に発注すると上限を超えるため、必ずこれを通すこと。
        超過するとエラーで一部銘柄だけ約定し、ポジションが中途半端になる。"""
        now = time.time()
        self._order_times = [t for t in self._order_times
                             if now - t < RATE_WINDOW_SEC]
        if len(self._order_times) >= MAX_ORDERS_PER_WINDOW:
            wait = RATE_WINDOW_SEC - (now - self._order_times[0]) + 0.5
            if wait > 0:
                time.sleep(wait)
                now = time.time()
                self._order_times = [t for t in self._order_times
                                     if now - t < RATE_WINDOW_SEC]
        if self._order_times:
            gap = time.time() - self._order_times[-1]
            if gap < MIN_ORDER_INTERVAL_SEC:
                time.sleep(MIN_ORDER_INTERVAL_SEC - gap)
        self._order_times.append(time.time())

    # --- 照会 ---------------------------------------------------------
    def _find_existing(self, tag):
        """同じremarkの注文が既に存在しないか確認する（冪等性の要）。

        moomooはClient Order IDに非対応なので、これが唯一の重複防止手段。
        発注前と、タイムアウト後の再送前に必ず呼ぶこと。"""
        ret, data = self.ctx.order_list_query(acc_id=self.acc_id,
                                              trd_env=self.trd_env)
        if ret != 0:
            # 照会できないときは「無い」と断定できないので発注しない
            raise MoomooOrderError(f"注文一覧を取得できず重複確認ができない: {data}")
        for row in _rows(data):
            if str(row.get("remark") or "") == tag:
                return row
        return None

    def fetch_positions(self, symbols):
        ret, data = self.ctx.position_list_query(acc_id=self.acc_id,
                                                 trd_env=self.trd_env)
        if ret != 0:
            raise MoomooOrderError(f"ポジション取得に失敗: {data}")
        out = {s: 0.0 for s in symbols}
        for row in _rows(data):
            code = _to_symbol(row.get("code"))
            if code in out:
                qty = float(row.get("qty") or 0)
                # moomooは空売り時に負のqtyを返す想定。方向情報があれば優先する
                side = str(row.get("position_side") or "").upper()
                out[code] = -abs(qty) if side == "SHORT" else qty
        return out

    def reconcile_positions(self, symbols, internal_positions):
        """live_trader.py と同じ形式で返す（Bitget版と互換）。"""
        real = self.fetch_positions(symbols)
        mism = {}
        for s in symbols:
            r, i = real.get(s, 0.0), internal_positions.get(s, 0.0)
            if abs(r - i) > 1e-9:
                mism[s] = {"exchange": r, "internal": i, "diff": r - i}
        return {"exchange_positions": real, "mismatches": mism}

    def fetch_equity_usd(self):
        ret, data = self.ctx.accinfo_query(acc_id=self.acc_id,
                                           trd_env=self.trd_env,
                                           currency="USD")
        if ret != 0:
            raise MoomooOrderError(f"口座情報の取得に失敗: {data}")
        rows = _rows(data)
        if not rows:
            raise MoomooOrderError("口座情報が空")
        r = rows[0]
        for key in ("total_assets", "net_cash_power", "cash"):
            v = r.get(key)
            if v not in (None, ""):
                return float(v)
        raise MoomooOrderError("口座評価額を判定できない")

    def fetch_available_usd(self):
        ret, data = self.ctx.accinfo_query(acc_id=self.acc_id,
                                           trd_env=self.trd_env,
                                           currency="USD")
        if ret != 0:
            return 0.0
        rows = _rows(data)
        if not rows:
            return 0.0
        for key in ("power", "net_cash_power", "cash"):
            v = rows[0].get(key)
            if v not in (None, ""):
                return float(v)
        return 0.0

    # --- 発注 ---------------------------------------------------------
    def place_order(self, order: ex.Order, bar_epoch, min_notional_usd=1.0):
        """成行注文を出し、Fillを返す。

        既に同じremarkの注文があれば再送せずそれを使う。
        moomooは取引所側で重複を弾かないため、この事前照会が唯一の防御。
        """
        self.ensure_unlocked()
        bar_date = dt.datetime.utcfromtimestamp(bar_epoch).strftime("%Y%m%d")
        tag = order_tag(order.symbol, bar_date)

        existing = self._find_existing(tag)
        if existing is not None:
            return self._fill_from_row(order, existing)

        qty = abs(order.qty)
        if qty < 1:                       # 端数株はAPI非対応。1株未満は出せない
            raise MoomooOrderError(
                f"{order.symbol}: 数量{qty}が1株未満のため発注しない")
        notional = qty * order.signal_price
        if notional < min_notional_usd:
            raise MoomooOrderError(
                f"{order.symbol}: ノーショナル{notional:.2f}USDが最小未満")

        self._respect_rate_limit()
        try:
            ret, data = self.ctx.place_order(
                price=order.signal_price,       # 成行でも参照価格が要る
                qty=qty,
                code=_to_code(order.symbol),
                trd_side="BUY" if order.qty > 0 else "SELL",
                order_type="MARKET",
                trd_env=self.trd_env,
                acc_id=self.acc_id,
                remark=tag,                    # ← 冪等性のための決定的ID
                session=self.session,
            )
        except Exception as e:
            # 通信断でも取引所には届いている可能性がある。再送せず照会する
            found = self._find_existing(tag)
            if found is not None:
                return self._fill_from_row(order, found)
            raise MoomooOrderError(f"{order.symbol}: 発注に失敗: {e}") from e

        if ret != 0:
            found = self._find_existing(tag)
            if found is not None:
                return self._fill_from_row(order, found)
            raise MoomooOrderError(f"{order.symbol}: 発注が拒否された: {data}")
        rows = _rows(data)
        return self._fill_from_row(order, rows[0] if rows else {})

    def _fill_from_row(self, order, row):
        filled = float(row.get("dealt_qty") or row.get("qty") or abs(order.qty))
        price = float(row.get("dealt_avg_price") or row.get("price")
                      or order.signal_price)
        signed = filled if order.qty > 0 else -filled
        return ex.Fill(symbol=order.symbol, qty=signed,
                       signal_price=order.signal_price,
                       ref_price=price, fill_price=price,
                       fee_usd=0.0,                 # 手数料は後から口座に反映される
                       reason=order.reason, ts=time.time())


# --- 補助 --------------------------------------------------------------

def _rows(data):
    """SDKはpandas.DataFrameを返す。listやdictでも動くようにしておく。"""
    if data is None:
        return []
    if hasattr(data, "to_dict"):
        return data.to_dict("records")
    if isinstance(data, dict):
        return [data]
    return list(data)


def _to_code(symbol):
    """'SPY' → 'US.SPY'（moomooの銘柄コード形式）"""
    return symbol if "." in symbol else f"US.{symbol}"


def _to_symbol(code):
    """'US.SPY' → 'SPY'"""
    return str(code).split(".")[-1] if code else ""
