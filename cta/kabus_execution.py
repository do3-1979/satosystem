"""実発注の執行層（三菱UFJ eスマート証券・kabuステーションAPI・東証ETF現物）。

cta/execution.py の Order/Fill をそのまま使い、Bitget版(live_execution.py)・
moomoo版(moomoo_execution.py)と同じインターフェースを提供する。
呼び出し側(live_trader.py)から見て差し替えられる。

■kabuステーションAPIの前提
  - kabuステーション(Windowsアプリ)を起動するとローカルにAPIサーバが立つ。
    本番 http://localhost:18080/kabusapi / 検証 http://localhost:18081/kabusapi
    **Windows専用**。RPi(aarch64)では動かないためWindowsタスクスケジューラで回す。
  - 認証は2段階。POST /token でAPIパスワードからトークンを取り、以降は
    ヘッダ X-API-KEY に載せる。トークンはkabuステーション終了・ログアウト・
    早朝の強制ログアウトで無効になるため、失効時は自動で取り直す。
  - 発注には別途「注文パスワード」が要る（トークンとは別物）。

■【最重要】Client Order ID が無い
  kabuステーションAPIの /sendorder にはクライアント側で採番する注文IDが無く、
  **取引所側で重複を弾いてくれない**（Bitgetの clientOid とは違う）。
  そのため「発注前に当日の注文を照会し、同じ銘柄の注文が無いことを確認してから
  発注する」という自前の冪等性で守る。本戦略は月次リバランスで
  1銘柄あたり1日1注文しか出さないため、この単位で十分に一意になる。
  照会と発注の間の競合はcron側のロックで防ぐ（tools/run_etf_wsl.sh の flock）。

■執行条件は「寄成」を使う
  FrontOrderType=13（寄成・前場）＝翌営業日の寄付の板で成行約定。
  バックテストの「判定はバー終値、約定は次足始値」と**同じ意味**になる。
  成行(10)を場中に出すとバックテストと約定タイミングが食い違うため使わない。
"""
import datetime as dt
import time
import urllib.error
import urllib.request
import json as _json

from . import execution as ex

# /sendorder の定義値（kabu_STATION_API.yaml より）
EXCHANGE_TOSHO = 1          # 東証
SECURITY_TYPE_STOCK = 1     # 株式（ETFもこれ）
SIDE_SELL, SIDE_BUY = "1", "2"
CASH_MARGIN_SPOT = 1        # 現物
DELIV_TYPE_NONE = 0         # 現物売はこれ
DELIV_TYPE_DEPOSIT = 2      # 現物買は「お預り金」
FUND_TYPE_SELL = "  "       # 現物売は半角スペース2つ
FUND_TYPE_PROTECT = "02"    # 現物買は「保護」
ACCOUNT_TYPE_SPECIFIC = 4   # 特定口座
FRONT_ORDER_TYPE_OPEN_MARKET = 13   # 寄成（前場）
PRODUCT_STOCK = 1

# 注文状態(State): 5=終了(取消・失効含む)。それ未満は生きている注文
STATE_DONE = 5


class KabusOrderError(RuntimeError):
    pass


class KabusExecutor:
    def __init__(self, api_password, order_password, base_url=None,
                 sandbox=False, account_type=ACCOUNT_TYPE_SPECIFIC,
                 exchange=EXCHANGE_TOSHO, opener=None, timeout=15):
        port = 18081 if sandbox else 18080
        self.base = (base_url or f"http://localhost:{port}/kabusapi").rstrip("/")
        self._api_password = api_password
        self._order_password = order_password
        self.account_type = account_type
        self.exchange = exchange
        self.timeout = timeout
        self._token = None
        self._opener = opener      # テストでフェイクを注入する口

    # --- 通信 ---------------------------------------------------------
    def _raw(self, method, path, body=None, token=None):
        url = f"{self.base}{path}"
        data = _json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json"}
        if token:
            headers["X-API-KEY"] = token
        if self._opener is not None:
            return self._opener(method, url, body, headers)
        req = urllib.request.Request(url, data=data, headers=headers,
                                     method=method)
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return _json.loads(r.read().decode() or "{}")

    def ensure_token(self, force=False):
        """APIトークンを取得する。失効時は取り直す。"""
        if self._token and not force:
            return self._token
        r = self._raw("POST", "/token", {"APIPassword": self._api_password})
        if r.get("ResultCode") != 0 or not r.get("Token"):
            raise KabusOrderError(f"トークン取得に失敗: {r}")
        self._token = r["Token"]
        return self._token

    def _call(self, method, path, body=None):
        """トークン付きで呼ぶ。401/403なら1度だけ取り直して再試行する。"""
        try:
            return self._raw(method, path, body, token=self.ensure_token())
        except urllib.error.HTTPError as e:
            if e.code not in (401, 403):
                raise
            return self._raw(method, path, body, token=self.ensure_token(True))

    # --- 照会 ---------------------------------------------------------
    def fetch_trading_unit(self, symbol):
        """売買単位(TradingUnit)。configのlot_sizesと必ず突き合わせること。

        東証ETFは1口/10口が銘柄ごとに異なり、思い込みで固定すると
        発注が通らないか意図しない数量になる。
        """
        r = self._call("GET", f"/symbol/{_code(symbol)}@{self.exchange}")
        unit = r.get("TradingUnit")
        if not unit:
            raise KabusOrderError(f"{symbol}: 売買単位を取得できない: {r}")
        return int(unit)

    def verify_lot_sizes(self, cfg):
        """configの売買単位が取引所の実値と一致するか検証する。

        ここがずれたまま発注すると数量が桁違いになるため、
        実発注の前に必ず通すこと。Returns: 不一致のdict（空なら健全）。
        """
        bad = {}
        for sym in cfg.symbols:
            real = self.fetch_trading_unit(sym)
            if real != cfg.lot_size(sym):
                bad[sym] = {"config": cfg.lot_size(sym), "exchange": real}
        return bad

    def _live_orders_for(self, symbol):
        """当日の生きている注文（取消・失効を除く）を返す。冪等性の要。"""
        r = self._call("GET", f"/orders?product={PRODUCT_STOCK}"
                              f"&symbol={_code(symbol)}")
        rows = r if isinstance(r, list) else []
        today = dt.datetime.now().strftime("%Y%m%d")
        out = []
        for o in rows:
            recv = str(o.get("RecvTime") or "")
            if recv and not recv.replace("-", "").startswith(today):
                continue
            if int(o.get("State") or 0) >= STATE_DONE and \
               float(o.get("CumQty") or 0) <= 0:
                continue          # 取消・失効で約定ゼロのものは無かった扱い
            out.append(o)
        return out

    def fetch_positions(self, symbols):
        r = self._call("GET", f"/positions?product={PRODUCT_STOCK}")
        rows = r if isinstance(r, list) else []
        out = {s: 0.0 for s in symbols}
        for row in rows:
            sym = _to_symbol(row.get("Symbol"))
            if sym in out:
                # 現物のみ運用（long_only）。売建は扱わない
                out[sym] += float(row.get("LeavesQty") or 0)
        return out

    def reconcile_positions(self, symbols, internal_positions):
        real = self.fetch_positions(symbols)
        mism = {}
        for s in symbols:
            r, i = real.get(s, 0.0), internal_positions.get(s, 0.0)
            if abs(r - i) > 1e-9:
                mism[s] = {"exchange": r, "internal": i, "diff": r - i}
        return {"exchange_positions": real, "mismatches": mism}

    def fetch_available_usd(self):
        """現物買付可能額（円）。名前はUSDだが口座通貨＝円。"""
        r = self._call("GET", "/wallet/cash")
        v = r.get("StockAccountWallet")
        if v is None:
            raise KabusOrderError(f"買付余力を取得できない: {r}")
        return float(v)

    def fetch_price(self, symbol):
        r = self._call("GET", f"/board/{_code(symbol)}@{self.exchange}")
        for k in ("CurrentPrice", "PreviousClose"):
            if r.get(k):
                return float(r[k])
        raise KabusOrderError(f"{symbol}: 現在値を取得できない")

    def fetch_equity_usd(self, symbols=None):
        """時価評価額（円）= 買付余力 + 保有の時価。

        現物long_onlyなので信用余力は見ない。価格が取れない保有があれば
        黙って0扱いにせず落とす（equity過小評価はサーキットブレーカーの
        誤作動につながる。cta/execution.py の Portfolio.equity と同じ思想）。
        """
        eq = self.fetch_available_usd()
        r = self._call("GET", f"/positions?product={PRODUCT_STOCK}")
        for row in (r if isinstance(r, list) else []):
            qty = float(row.get("LeavesQty") or 0)
            if qty == 0:
                continue
            sym = _to_symbol(row.get("Symbol"))
            px = row.get("CurrentPrice") or row.get("Price")
            if not px:
                px = self.fetch_price(sym)
            eq += qty * float(px)
        return eq

    # --- 発注 ---------------------------------------------------------
    def place_order(self, order: ex.Order, bar_epoch, min_notional_usd=1.0,
                    lot_size=1):
        """寄成注文を出しFillを返す。既に当日の注文があれば再送しない。

        kabuステーションAPIは重複を弾かないため、この事前照会が唯一の防御。
        """
        qty = abs(order.qty)
        lot = max(1, int(lot_size or 1))
        if qty < lot or qty % lot != 0:
            raise KabusOrderError(
                f"{order.symbol}: 数量{qty}が売買単位{lot}の整数倍でない")
        if qty * order.signal_price < min_notional_usd:
            raise KabusOrderError(f"{order.symbol}: ノーショナルが最小未満")

        existing = self._live_orders_for(order.symbol)
        if existing:
            return self._fill_from_order(order, existing[0])

        body = {
            "Password": self._order_password,
            "Symbol": _code(order.symbol),
            "Exchange": self.exchange,
            "SecurityType": SECURITY_TYPE_STOCK,
            "Side": SIDE_BUY if order.qty > 0 else SIDE_SELL,
            "CashMargin": CASH_MARGIN_SPOT,
            "DelivType": DELIV_TYPE_DEPOSIT if order.qty > 0 else DELIV_TYPE_NONE,
            "FundType": FUND_TYPE_PROTECT if order.qty > 0 else FUND_TYPE_SELL,
            "AccountType": self.account_type,
            "Qty": int(qty),
            "FrontOrderType": FRONT_ORDER_TYPE_OPEN_MARKET,
            "Price": 0,          # 寄成なので0
            "ExpireDay": 0,      # 当日
        }
        try:
            r = self._call("POST", "/sendorder", body)
        except Exception as e:
            # 通信断でも届いている可能性がある。再送せず照会して確かめる
            found = self._live_orders_for(order.symbol)
            if found:
                return self._fill_from_order(order, found[0])
            raise KabusOrderError(f"{order.symbol}: 発注に失敗: {e}") from e
        if r.get("Result") != 0:
            found = self._live_orders_for(order.symbol)
            if found:
                return self._fill_from_order(order, found[0])
            raise KabusOrderError(f"{order.symbol}: 発注が拒否された: {r}")
        return self._fill_from_order(order, {"ID": r.get("OrderId")})

    def _fill_from_order(self, order, row):
        """寄成は発注時点では未約定。約定価格は判明後に埋まる。

        ここで signal_price を仮置きするのは、翌朝の寄付までは真の約定価格が
        存在しないため。実約定は次回実行時の reconcile_positions で
        取引所の実ポジションとして反映される。
        """
        filled = float(row.get("CumQty") or 0) or abs(order.qty)
        price = float(row.get("Price") or 0) or order.signal_price
        signed = filled if order.qty > 0 else -filled
        return ex.Fill(symbol=order.symbol, qty=signed,
                       signal_price=order.signal_price,
                       ref_price=price, fill_price=price,
                       fee_usd=0.0,      # 手数料は約定後に口座へ反映される
                       reason=order.reason, ts=time.time())


# --- 補助 --------------------------------------------------------------

def _code(symbol):
    """'1306.T' → '1306'（kabuステーションは4桁コードのみ）"""
    return str(symbol).split(".")[0]


def _to_symbol(code):
    """'1306' → '1306.T'（社内表記へ戻す）"""
    c = str(code or "")
    return f"{c}.T" if c and not c.endswith(".T") else c
