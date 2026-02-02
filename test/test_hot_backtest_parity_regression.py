"""
ホットテスト（60秒ごと更新）とバックテスト（1本足ごと）の
シグナル計算が同一OHLCV入力に対して一致することを検証するレグレッションテスト。

目的:
- ホットテスト側の update_price_data() と、バックテスト側の update_price_data_backtest() が
  同等の確定足系列を入力した場合に、Donchian/PVO の計算結果が一致することを確認する。

注意:
- 本テストは「検証」のため、ロジック自体は変更しない。
- もし不一致が検出された場合はテストを失敗させ、差分を詳細に出力する。
"""

import os
import sys
import json
import copy
from datetime import datetime

# sys.path 設定
WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(WORKSPACE_ROOT, "src")
sys.path.insert(0, SRC_DIR)


class FakeExchange:
    """PriceDataManagement が呼ぶ最小限のAPIを提供するフェイク取引所。"""

    def __init__(self, candles_by_tf, time_frame):
        self._candles_by_tf = candles_by_tf
        self._time_frame = time_frame
        self._index = 0

    def set_index(self, idx):
        self._index = max(0, min(idx, len(self._candles_by_tf[self._time_frame]) - 1))

    def get_market_symbol(self):
        return "TEST/USDT"

    def fetch_ohlcv(self, start_epoch, end_epoch, time_frame):
        data = self._candles_by_tf[time_frame]
        # update_price_data は最後の要素を参照するため、少なくとも1件返す
        return data[: self._index + 1]

    def fetch_latest_ohlcv(self, time_frame):
        data = self._candles_by_tf[time_frame]
        return [data[self._index]]

    def fetch_ticker(self):
        # テストでは「確定足終値」をtickerとして返す（バックテストと比較可能にする）
        data = self._candles_by_tf[self._time_frame]
        return float(data[self._index]["close_price"])


def _build_synthetic_candles(time_frame_minutes, n=30, start_epoch=1704067200):
    """単純な上昇→下落を含む合成OHLCVを生成して、BUY/SELL両方の発火可能性を作る。"""
    candles = []

    # close_time は「足の確定時刻」を想定して等間隔で作る
    step = time_frame_minutes * 60

    # 価格系列: 前半上昇、後半下落
    closes = []
    price = 100.0
    for i in range(n):
        if i < n // 2:
            price += 2.0
        else:
            price -= 3.0
        closes.append(price)

    for i in range(n):
        ct = start_epoch + i * step
        close = float(closes[i])

        # wick なし（high=low=close）にして Donchian の判定を単純化
        candle = {
            "close_time": int(ct),
            "open_price": close,
            "high_price": close,
            "low_price": close,
            "close_price": close,
            "Volume": float(1000 + i * 10),
        }
        candles.append(candle)

    return candles


def _patch_config_for_test(Config, back_test_mode):
    """Config.config を直接書き換えて、短い系列でも計算可能にする。"""
    # ConfigParser は存在しないsectionへの set が落ちるため、必要なら作る
    def ensure(section):
        if not Config.config.has_section(section):
            Config.config.add_section(section)

    ensure("Backtest")
    ensure("Market")
    ensure("RiskManagement")
    ensure("Strategy")
    ensure("EntryFilters")
    ensure("Period")
    ensure("Setting")

    Config.config.set("Backtest", "back_test", str(int(back_test_mode)))
    # hot_test_dummy_mode は本テストでは意味を持たないが、参照され得るため安全にセット
    Config.config.set("Backtest", "hot_test_dummy_mode", "1")

    # 時間足（小さくしてテストを軽量化）
    Config.config.set("Market", "time_frame", "60")
    Config.config.set("RiskManagement", "psar_time_frame", "60")

    # 期間（バックテスト初期化で参照される）
    Config.config.set("Period", "start_time", "2024/01/01 00:00")
    Config.config.set("Period", "end_time", "2024/01/02 00:00")

    # 指標の期間を短く
    Config.config.set("Strategy", "volatility_term", "3")
    Config.config.set("Strategy", "donchian_buy_term", "3")
    Config.config.set("Strategy", "donchian_sell_term", "3")
    Config.config.set("Strategy", "pvo_s_term", "3")
    Config.config.set("Strategy", "pvo_l_term", "5")
    Config.config.set("Strategy", "pvo_threshold", "0")

    # update_price_data が参照
    Config.config.set("Setting", "server_retry_wait", "1")


def test_hot_vs_backtest_signal_parity():
    """同一OHLCV入力で Donchian/PVO の結果が一致することを検証。"""
    try:
        from config import Config
        import price_data_management as pdm_mod
        from price_data_management import PriceDataManagement

        # 元の設定を退避
        original_config_snapshot = copy.deepcopy(Config.config)

        # 合成データ
        time_frame = 60
        candles = _build_synthetic_candles(time_frame_minutes=time_frame, n=40)
        candles_by_tf = {time_frame: candles}

        # --- ホットテスト側 ---
        _patch_config_for_test(Config, back_test_mode=0)

        hot_exchange = FakeExchange(candles_by_tf, time_frame)
        pdm_mod.BybitExchange = lambda *args, **kwargs: hot_exchange
        pdm_mod.BitgetExchange = lambda *args, **kwargs: hot_exchange

        PriceDataManagement._instance = None
        hot_pdm = PriceDataManagement()

        # time.time を price_data_management モジュール内だけ差し替え
        orig_time_func = pdm_mod.time.time

        hot_signals = []
        hot_meta = []
        # 初回は初期化のみなのでスキップし、2回目以降から比較対象にする
        for i in range(0, len(candles)):
            hot_exchange.set_index(i)
            pdm_mod.time.time = lambda _ct=candles[i]["close_time"]: float(_ct)
            ok = hot_pdm.update_price_data()
            if not ok:
                return False, f"❌ ホット側 update_price_data が False を返しました (i={i})"
            if i == 0:
                continue
            hot_signals.append(copy.deepcopy(hot_pdm.get_signals()))
            try:
                hl = hot_pdm.get_latest_ohlcv()
                hot_meta.append({"close_time": hl.get("close_time"), "close_price": hl.get("close_price")})
            except Exception:
                hot_meta.append({"close_time": None, "close_price": None})

        # time を復元
        pdm_mod.time.time = orig_time_func

        # --- バックテスト側 ---
        _patch_config_for_test(Config, back_test_mode=1)

        back_exchange = FakeExchange(candles_by_tf, time_frame)
        pdm_mod.BybitExchange = lambda *args, **kwargs: back_exchange
        pdm_mod.BitgetExchange = lambda *args, **kwargs: back_exchange

        PriceDataManagement._instance = None
        back_pdm = PriceDataManagement()

        # back_test_ohlcv_data を手動で埋める（Bot本体の初期化処理の代替）
        if not hasattr(back_pdm, "back_test_ohlcv_data"):
            return False, "❌ back_test_ohlcv_data が初期化されていません（back_test_mode=1の反映に失敗）"

        for entry in back_pdm.back_test_ohlcv_data:
            entry["data"] = candles
            entry["prev_index"] = 0

        back_signals = []
        back_meta = []

        # 初回は初期化のみでシグナル計算が走らないためスキップ
        back_exchange.set_index(0)
        done = back_pdm.update_price_data_backtest()
        if done:
            return False, "❌ バックテスト側が初回で終了しました（データ不足の可能性）"

        # 2回目以降でシグナルが計算される想定
        for _ in range(1, len(candles)):
            done = back_pdm.update_price_data_backtest()
            if done:
                break
            back_signals.append(copy.deepcopy(back_pdm.get_signals()))
            try:
                bl = back_pdm.get_latest_ohlcv()
                back_meta.append({"close_time": bl.get("close_time"), "close_price": bl.get("close_price")})
            except Exception:
                back_meta.append({"close_time": None, "close_price": None})

        # --- 比較 ---
        # hot_signals と back_signals は同じ長さになる想定だが、安全に短い方に合わせる
        m = min(len(hot_signals), len(back_signals))
        if m == 0:
            return False, "❌ 比較対象のシグナルが生成されませんでした"

        diffs = []
        for idx in range(m):
            hs = hot_signals[idx]
            bs = back_signals[idx]

            # Donchian
            if hs["donchian"]["signal"] != bs["donchian"]["signal"] or hs["donchian"]["side"] != bs["donchian"]["side"]:
                diffs.append((idx, "donchian", hs["donchian"], bs["donchian"]))

            # info(最高/最安)
            if hs["donchian"]["info"] != bs["donchian"]["info"]:
                diffs.append((idx, "donchian.info", hs["donchian"]["info"], bs["donchian"]["info"]))

            # PVO
            if hs["pvo"]["signal"] != bs["pvo"]["signal"]:
                diffs.append((idx, "pvo", hs["pvo"], bs["pvo"]))

            hv = float(hs["pvo"]["info"]["value"])
            bv = float(bs["pvo"]["info"]["value"])
            if abs(hv - bv) > 1e-9:
                diffs.append((idx, "pvo.value", hv, bv))

        # Config 復元
        Config.config = original_config_snapshot

        if diffs:
            # 先頭の差分だけでも詳細に出す（大量になるため）
            head = diffs[0]

            # 追加の診断情報（差分が出たステップのメタ情報）
            hot_step_meta = hot_meta[head[0]] if head[0] < len(hot_meta) else None
            back_step_meta = back_meta[head[0]] if head[0] < len(back_meta) else None

            return (
                False,
                "❌ ホット vs バックテストでシグナル差分を検出\n"
                f"  first_diff_index={head[0]}\n"
                f"  field={head[1]}\n"
                f"  hot={head[2]}\n"
                f"  back={head[3]}\n"
                f"  hot_step={hot_step_meta}\n"
                f"  back_step={back_step_meta}\n"
                f"  total_diffs={len(diffs)}\n"
                "※ ロジック修正が必要な場合はユーザー指示を仰いでください"
            )

        return True, f"✅ ホット vs バックテストのDonchian/PVO計算が一致しました (n={m})"

    except Exception as e:
        return False, f"❌ テスト実行エラー: {e}"


def run_all_tests():
    tests = [
        ("ホット/バックテスト シグナル一致検証", test_hot_vs_backtest_signal_parity),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            passed, message = test_func()
            results.append({
                "name": test_name,
                "passed": passed,
                "message": message,
                "timestamp": datetime.now().isoformat(),
            })
            print(message)
        except Exception as e:
            results.append({
                "name": test_name,
                "passed": False,
                "message": f"❌ テスト実行エラー: {e}",
                "timestamp": datetime.now().isoformat(),
            })
            print(f"❌ テスト実行エラー ({test_name}): {e}")

    return results


if __name__ == "__main__":
    print("=" * 70)
    print("🧪 hot vs backtest parity レグレッションテスト")
    print("=" * 70)
    results = run_all_tests()

    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(results)

    print()
    print(f"📊 結果: {passed_count}/{total_count} 成功")

    RESULTS_DIR = os.path.join(WORKSPACE_ROOT, "docs/regression_test_results")
    os.makedirs(RESULTS_DIR, exist_ok=True)

    with open(os.path.join(RESULTS_DIR, "test_hot_backtest_parity_regression.json"), "w", encoding="utf-8") as f:
        json.dump({
            "file": "hot_vs_backtest_parity",
            "total": total_count,
            "passed": passed_count,
            "results": results,
            "timestamp": datetime.now().isoformat(),
        }, f, ensure_ascii=False, indent=2)

    sys.exit(0 if passed_count == total_count else 1)
