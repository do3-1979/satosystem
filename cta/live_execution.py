"""実発注の執行層（Bitget、ccxt経由）。

gen2の教訓+今回の追加調査で判明した課題への対応:
  - gen2の`retry_with_backoff`はタイムアウト時に無条件で同じ注文を再送しており、
    「注文は実際には通っていたが応答だけがタイムアウトした」場合に二重発注し得た。
    本モジュールは Bitget の `clientOid`（クライアント側注文ID）を
    シンボル+バー時刻から決定的に生成し、リトライ前に必ず「そのclientOidの注文が
    既に存在しないか」を確認してから初めて発注する。同じclientOidでの再送は
    取引所側で重複排除されるため、ネットワーク起因の二重発注が構造的に起こらない。
  - 発注後は取引所への実残高・実ポジション照会を必ず信頼できる情報源(source of truth)とし、
    内部の帳簿（Portfolio）を鵜呑みにしない（gen2の「静かな乖離」の再発防止）。
  - 【実機検証(2026-07-05)で発覚】アカウントがBitgetの**ヘッジモード**（同一銘柄で
    ロング/ショートを同時に別legとして保有できるモード）だったため、単純な
    buy/sell発注だけでは「ロング決済」ではなく「新規ショート建玉」になってしまい、
    テストで実際にロング+ショートが両方残る事故が発生した（実損は僅少、手動で復旧済）。
    本モジュールの戦略は常に銘柄ごとの単一の符号付き純ポジションを想定しているため、
    発注前に必ず逆側legの有無を確認し、逆legがあれば`reduceOnly`で先に縮小してから
    残数量を新規開設する（_execute_hedge_aware）。

cta/execution.py の Order/Fill をそのまま使い、バックテスト・ペーパーと
同じデータ構造で実発注の結果を扱えるようにしている。
"""
import hashlib
import time

import ccxt

from . import execution as ex

RETRYABLE = (ccxt.NetworkError, ccxt.RequestTimeout, ccxt.ExchangeNotAvailable,
             ccxt.DDoSProtection)
NON_RETRYABLE = (ccxt.InsufficientFunds, ccxt.InvalidOrder, ccxt.BadSymbol,
                 ccxt.AuthenticationError, ccxt.PermissionDenied)


def client_order_id(symbol, bar_epoch):
    """symbol+バー時刻から決定的なIDを生成。同じ意図の注文は常に同じIDになる
    → 取引所側でのクライアント注文ID重複チェックにより二重発注を防ぐ。"""
    raw = f"cta-{symbol}-{int(bar_epoch)}"
    return "cta" + hashlib.sha1(raw.encode()).hexdigest()[:28]


class OrderPlacementError(RuntimeError):
    pass


class BitgetLiveExecutor:
    def __init__(self, api_key, api_secret, passphrase, max_attempts=5,
                initial_delay=2.0, backoff_multiplier=2.0, max_delay=30.0):
        self.exchange = ccxt.bitget({
            'apiKey': api_key,
            'secret': api_secret,
            'password': passphrase,
            'enableRateLimit': True,
            'options': {'defaultType': 'swap', 'fetchCurrencies': False},
        })
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.backoff_multiplier = backoff_multiplier
        self.max_delay = max_delay

    def _round_amount(self, symbol, amount):
        """取引所の最小刻みに丸める。ccxtは丸めた結果が0になる量を渡すと
        InvalidOrderを投げる仕様のため、その場合は0.0として扱う（発注しない）。"""
        if amount <= 0.0:
            return 0.0
        try:
            return float(self.exchange.amount_to_precision(symbol, amount))
        except ccxt.InvalidOrder:
            return 0.0

    def _position_legs(self, symbol):
        """ヘッジモードのlong/short両legの数量を返す（無ければ0.0）。"""
        positions = self.exchange.fetch_positions([symbol])
        legs = {'long': 0.0, 'short': 0.0}
        for p in positions:
            side = p.get('side')
            contracts = p.get('contracts') or 0.0
            if side in legs and contracts:
                legs[side] = contracts
        return legs

    def _submit(self, symbol, side, amount, coid, ref_price, reduce_only, hold_side):
        """1件の発注をclientOid付きで実行する（リトライ・二重発注防止込み）。"""
        existing = self._find_existing(symbol, coid)
        if existing is not None:
            return existing

        params = {'clientOid': coid, 'holdSide': hold_side}
        if reduce_only:
            params['reduceOnly'] = True
        if side == 'buy' and not reduce_only:
            params['price'] = ref_price  # Bitget成行買いはコスト計算にpriceが必要

        delay = self.initial_delay
        last_exc = None
        for attempt in range(self.max_attempts):
            try:
                return self.exchange.create_order(
                    symbol=symbol, type='market', side=side,
                    amount=amount, params=params)
            except NON_RETRYABLE as e:
                raise OrderPlacementError(f"{symbol}: リトライ不可エラー: {e}") from e
            except RETRYABLE as e:
                last_exc = e
                found = self._find_existing(symbol, coid)
                if found is not None:
                    return found
                if attempt == self.max_attempts - 1:
                    break
                time.sleep(delay)
                delay = min(delay * self.backoff_multiplier, self.max_delay)
        raise OrderPlacementError(
            f"{symbol}: {self.max_attempts}回リトライ後も失敗: {last_exc}") from last_exc

    def _find_existing(self, symbol, coid):
        """指定clientOidの注文が既に存在しないか確認する（発注前・リトライ前に必ず呼ぶ）。

        gen2にはこの確認ステップが無く、タイムアウト後の再送が二重発注になり得た。
        見つかった場合はそのまま返し、再発注は絶対に行わない。"""
        try:
            open_orders = self.exchange.fetch_open_orders(symbol)
            for o in open_orders:
                if o.get('clientOrderId') == coid:
                    return o
        except ccxt.BaseError:
            pass
        try:
            closed = self.exchange.fetch_closed_orders(symbol, limit=20)
            for o in closed:
                if o.get('clientOrderId') == coid:
                    return o
        except ccxt.BaseError:
            pass
        return None

    def place_order(self, order: ex.Order, bar_epoch, min_notional_usd=5.0):
        """market注文を発注し、実約定情報から Fill を返す。

        戦略側は銘柄ごとの単一の符号付き純ポジションしか想定していないため、
        アカウントがヘッジモードの場合は「逆側legをreduceOnlyで先に縮小
        →残数量を新規開設」の2段階に分けて、常に単一方向の純ポジションへ
        収束させる（2026-07-05の実機検証で判明した必須の対応）。

        既に同じclientOidの注文が存在する場合は再送せずその結果を使う
        （cronの二重起動・タイムアウト後の手動リトライ双方に対して安全）。
        """
        symbol = order.symbol
        side = 'buy' if order.qty > 0 else 'sell'
        # 取引所の最小刻み幅に事前に丸める。丸めずに逆leg縮小/新規開設へ分割すると
        # 端数(例: 0.00014 - 0.0001 = 0.00004)が最小刻み未満になり発注が拒否される
        # （2026-07-05の実機検証で実際に発生：reduceOnly分は成功したがremainder分が
        #   InvalidOrderで失敗。フラット確認済みで実害は無かったが、再発防止する）。
        amount = self._round_amount(symbol, abs(order.qty))
        coid_base = client_order_id(symbol, bar_epoch)

        ticker = self.exchange.fetch_ticker(symbol)
        ref_price = ticker['last']
        notional = amount * ref_price
        if amount <= 0.0 or notional < min_notional_usd:
            raise OrderPlacementError(
                f"{symbol}: ノーショナル{notional:.2f}USDが最小{min_notional_usd}USD未満のため発注しない")

        legs = self._position_legs(symbol)
        opposite = 'short' if side == 'buy' else 'long'
        own_side = 'long' if side == 'buy' else 'short'
        reduce_amt = self._round_amount(symbol, min(amount, legs.get(opposite, 0.0)))
        remaining = self._round_amount(symbol, max(amount - reduce_amt, 0.0))

        results = []
        if reduce_amt > 0.0:
            r = self._submit(symbol, side, reduce_amt, coid_base + "r",
                             ref_price, reduce_only=True, hold_side=opposite)
            results.append(r)
        if remaining > 0.0:
            r = self._submit(symbol, side, remaining, coid_base + "o",
                             ref_price, reduce_only=False, hold_side=own_side)
            results.append(r)

        return self._fill_from_ccxt_orders(order, results, ref_price)

    def _fill_from_ccxt_orders(self, order, ccxt_orders, ref_price=None):
        """reduceOnly分+新規開設分など複数の実約定を、数量加重平均の1件のFillにまとめる。"""
        total_qty = 0.0
        notional = 0.0
        total_fee = 0.0
        ts = 0.0
        for co in ccxt_orders:
            q = co.get('filled') or 0.0
            p = co.get('average') or co.get('price') or ref_price or 0.0
            total_qty += q
            notional += q * p
            fee = co.get('fee') or {}
            total_fee += float(fee.get('cost') or 0.0)
            ts = max(ts, (co.get('timestamp') or 0) / 1000.0)
        if total_qty <= 1e-12:
            total_qty = abs(order.qty)
            avg_price = ref_price
        else:
            avg_price = notional / total_qty
        signed_qty = total_qty if order.qty > 0 else -total_qty
        return ex.Fill(symbol=order.symbol, qty=signed_qty,
                       signal_price=order.signal_price,
                       ref_price=ref_price if ref_price is not None else avg_price,
                       fill_price=avg_price, fee_usd=total_fee,
                       reason=order.reason, ts=ts)

    def reconcile_positions(self, symbols, internal_positions):
        """取引所の実ポジションを正として内部帳簿と比較する。

        ヘッジモードではlong/short両legが同時に存在し得るため、同一銘柄の
        複数legは加算する（上書きしない）。戦略側は単一の純ポジションしか
        想定していないため、この合算値が「実質的な純エクスポージャー」になる。
        gen2最大の教訓（内部状態と実態が静かに乖離）を踏まえ、自動修正はせず
        差分をそのまま返す。呼び出し側でロギング・アラートに使うこと。"""
        real = {}
        try:
            positions = self.exchange.fetch_positions(symbols)
            for p in positions:
                sym = p.get('symbol')
                contracts = p.get('contracts') or 0.0
                side = p.get('side')
                signed = contracts if side == 'long' else -contracts
                if sym:
                    real[sym] = real.get(sym, 0.0) + signed
        except ccxt.BaseError as e:
            raise OrderPlacementError(f"ポジション照会失敗: {e}") from e

        mismatches = {}
        for sym in symbols:
            r = real.get(sym, 0.0)
            i = internal_positions.get(sym, 0.0)
            if abs(r - i) > 1e-9:
                mismatches[sym] = {'exchange': r, 'internal': i, 'diff': r - i}
        return {'exchange_positions': real, 'mismatches': mismatches}
