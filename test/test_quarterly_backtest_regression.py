"""
四半期バックテスト レグレッションテスト（BTC 9Q + XAUT 12Q）

【高速チェック】保存済みの quarterly_results_*.json を読み込み、
ベースラインと比較する。再バックテスト不要。

検証項目:
  - 累積 PnL がベースラインの 90% 以上（10% 劣化まで許容）
  - 四半期数が期待通り（BTC: 9, XAUT: 12）
  - 年次 PnL（「通年テスト」相当）が合理的な範囲にある
    - BTC 2024, 2025: 正であること
    - XAUT 2025: 正であること（2024 は取引数が少なく -50 USD 未満でなければ OK）
"""

import os
import sys
import json
import glob
from datetime import datetime

# パス設定
WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(WORKSPACE_ROOT, "src")
RESULTS_DIR = os.path.join(WORKSPACE_ROOT, "docs/regression_test_results")
QUARTERLY_RESULTS_DIR = os.path.join(WORKSPACE_ROOT, "docs/quarterly_backtest_results")
os.makedirs(RESULTS_DIR, exist_ok=True)

# ── ベースライン設定 ────────────────────────────────────────────────────
# BTC: BASELINE_BTC_3062.87USD_H056_20260515.json
BTC_BASELINE_PNL = 3062.87
BTC_BASELINE_TOLERANCE = 0.90   # 10% 劣化まで許容
BTC_EXPECTED_QUARTERS = 9

# XAUT: BASELINE_XAUT_81.21USD_FundingRateFix_20260519.json
XAUT_BASELINE_PNL = 81.21
XAUT_BASELINE_TOLERANCE = 0.90  # 10% 劣化まで許容
XAUT_EXPECTED_QUARTERS = 12


# ── ヘルパー ────────────────────────────────────────────────────────────
def _get_latest_quarterly_results(symbol: str) -> dict:
    """最新の quarterly_results_*.json を返す（見つからなければ空 dict）"""
    pattern = os.path.join(QUARTERLY_RESULTS_DIR, symbol, "quarterly_results_*.json")
    files = sorted(glob.glob(pattern))
    if not files:
        return {}
    with open(files[-1], encoding="utf-8") as f:
        return json.load(f)


def _quarterly_cumulative_pnl(results: dict) -> float:
    quarters = results.get("quarterly", [])
    return sum(q["metrics"]["total_pnl"] for q in quarters)


# ── BTC テスト ──────────────────────────────────────────────────────────
def test_btc_quarterly_results_exist():
    """BTC quarterly_results_*.json が存在し、期待四半期数を満たすこと"""
    results = _get_latest_quarterly_results("BTC")
    if not results:
        return False, "❌ BTC quarterly_results_*.json が見つかりません"
    quarters = results.get("quarterly", [])
    if len(quarters) < BTC_EXPECTED_QUARTERS:
        return False, f"❌ BTC 四半期数不足: {len(quarters)} < {BTC_EXPECTED_QUARTERS}"
    ts = results.get("generated_at", "unknown")
    return True, f"✅ BTC quarterly results 存在: {len(quarters)} 四半期 (generated_at={ts[:10]})"


def test_btc_quarterly_pnl_vs_baseline():
    """BTC 9Q 累積 PnL ≥ ベースライン × 90%"""
    results = _get_latest_quarterly_results("BTC")
    if not results:
        return False, "❌ BTC quarterly results が見つかりません"
    total = _quarterly_cumulative_pnl(results)
    threshold = BTC_BASELINE_PNL * BTC_BASELINE_TOLERANCE
    ok = total >= threshold
    mark = "✅" if ok else "❌"
    return ok, (
        f"{mark} BTC 累積PnL: {total:+.2f} USD "
        f"(ベースライン {BTC_BASELINE_PNL:.2f} × {BTC_BASELINE_TOLERANCE:.0%} "
        f"= {threshold:.2f} 以上 {'✓' if ok else '✗'})"
    )


def test_btc_annual_2024_pnl():
    """BTC 通年テスト 2024: 年次 PnL > 0"""
    results = _get_latest_quarterly_results("BTC")
    if not results:
        return False, "❌ BTC quarterly results が見つかりません"
    pnl = results.get("annual", {}).get("2024", {}).get("total_pnl", 0)
    trades = results.get("annual", {}).get("2024", {}).get("total_trades", 0)
    ok = pnl > 0
    mark = "✅" if ok else "❌"
    return ok, f"{mark} BTC 2024 年次損益: {pnl:+.2f} USD (取引数={trades})"


def test_btc_annual_2025_pnl():
    """BTC 通年テスト 2025: 年次 PnL > 0"""
    results = _get_latest_quarterly_results("BTC")
    if not results:
        return False, "❌ BTC quarterly results が見つかりません"
    pnl = results.get("annual", {}).get("2025", {}).get("total_pnl", 0)
    trades = results.get("annual", {}).get("2025", {}).get("total_trades", 0)
    ok = pnl > 0
    mark = "✅" if ok else "❌"
    return ok, f"{mark} BTC 2025 年次損益: {pnl:+.2f} USD (取引数={trades})"


def test_btc_annual_quarters_count():
    """BTC: 全四半期のトレード数合計が 0 より大きいこと"""
    results = _get_latest_quarterly_results("BTC")
    if not results:
        return False, "❌ BTC quarterly results が見つかりません"
    quarters = results.get("quarterly", [])
    total_trades = sum(q["metrics"].get("trades", 0) for q in quarters)
    ok = total_trades > 0
    mark = "✅" if ok else "❌"
    return ok, f"{mark} BTC 9Q 総トレード数: {total_trades} 件"


# ── XAUT テスト ─────────────────────────────────────────────────────────
def test_xaut_quarterly_results_exist():
    """XAUT quarterly_results_*.json が存在し、期待四半期数を満たすこと"""
    results = _get_latest_quarterly_results("XAUT")
    if not results:
        return False, "❌ XAUT quarterly_results_*.json が見つかりません"
    quarters = results.get("quarterly", [])
    if len(quarters) < XAUT_EXPECTED_QUARTERS:
        return False, f"❌ XAUT 四半期数不足: {len(quarters)} < {XAUT_EXPECTED_QUARTERS}"
    ts = results.get("generated_at", "unknown")
    return True, f"✅ XAUT quarterly results 存在: {len(quarters)} 四半期 (2023Q2〜2026Q1, generated_at={ts[:10]})"


def test_xaut_quarterly_pnl_vs_baseline():
    """XAUT 12Q 累積 PnL ≥ ベースライン × 90%"""
    results = _get_latest_quarterly_results("XAUT")
    if not results:
        return False, "❌ XAUT quarterly results が見つかりません"
    total = _quarterly_cumulative_pnl(results)
    threshold = XAUT_BASELINE_PNL * XAUT_BASELINE_TOLERANCE
    ok = total >= threshold
    mark = "✅" if ok else "❌"
    return ok, (
        f"{mark} XAUT 累積PnL: {total:+.2f} USD "
        f"(ベースライン {XAUT_BASELINE_PNL:.2f} × {XAUT_BASELINE_TOLERANCE:.0%} "
        f"= {threshold:.2f} 以上 {'✓' if ok else '✗'})"
    )


def test_xaut_annual_2024_pnl():
    """XAUT 通年テスト 2024: 年次 PnL > -50 USD（取引数少/初期データ混在のため緩め基準）"""
    results = _get_latest_quarterly_results("XAUT")
    if not results:
        return False, "❌ XAUT quarterly results が見つかりません"
    pnl = results.get("annual", {}).get("2024", {}).get("total_pnl", 0)
    trades = results.get("annual", {}).get("2024", {}).get("total_trades", 0)
    ok = pnl > -50
    mark = "✅" if ok else "❌"
    return ok, f"{mark} XAUT 2024 年次損益: {pnl:+.2f} USD (取引数={trades}, 閾値 > -50 USD)"


def test_xaut_annual_2025_pnl():
    """XAUT 通年テスト 2025: 年次 PnL > 0（XAUT 最良年）"""
    results = _get_latest_quarterly_results("XAUT")
    if not results:
        return False, "❌ XAUT quarterly results が見つかりません"
    pnl = results.get("annual", {}).get("2025", {}).get("total_pnl", 0)
    trades = results.get("annual", {}).get("2025", {}).get("total_trades", 0)
    ok = pnl > 0
    mark = "✅" if ok else "❌"
    return ok, f"{mark} XAUT 2025 年次損益: {pnl:+.2f} USD (取引数={trades})"


def test_xaut_annual_quarters_count():
    """XAUT: 全四半期のトレード数合計が 0 より大きいこと"""
    results = _get_latest_quarterly_results("XAUT")
    if not results:
        return False, "❌ XAUT quarterly results が見つかりません"
    quarters = results.get("quarterly", [])
    total_trades = sum(q["metrics"].get("trades", 0) for q in quarters)
    ok = total_trades > 0
    mark = "✅" if ok else "❌"
    return ok, f"{mark} XAUT 12Q 総トレード数: {total_trades} 件"


# ── エントリーポイント ───────────────────────────────────────────────────
def run_all_tests():
    tests = [
        # BTC 9Q
        ("btc_quarterly_results_exist",   test_btc_quarterly_results_exist),
        ("btc_quarterly_pnl_vs_baseline", test_btc_quarterly_pnl_vs_baseline),
        ("btc_annual_2024_pnl",           test_btc_annual_2024_pnl),
        ("btc_annual_2025_pnl",           test_btc_annual_2025_pnl),
        ("btc_annual_quarters_count",     test_btc_annual_quarters_count),
        # XAUT 12Q
        ("xaut_quarterly_results_exist",   test_xaut_quarterly_results_exist),
        ("xaut_quarterly_pnl_vs_baseline", test_xaut_quarterly_pnl_vs_baseline),
        ("xaut_annual_2024_pnl",           test_xaut_annual_2024_pnl),
        ("xaut_annual_2025_pnl",           test_xaut_annual_2025_pnl),
        ("xaut_annual_quarters_count",     test_xaut_annual_quarters_count),
    ]

    passed = 0
    total = len(tests)
    results_detail = []

    for name, fn in tests:
        try:
            ok, msg = fn()
        except Exception as e:
            ok, msg = False, f"❌ 例外: {e}"
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}: {msg}")
        if ok:
            passed += 1
        results_detail.append({"name": name, "passed": ok, "detail": msg})

    # 結果を JSON に保存
    summary = {
        "test_file": "test_quarterly_backtest_regression",
        "passed": passed,
        "total": total,
        "timestamp": datetime.now().isoformat(),
        "details": results_detail,
    }
    with open(
        os.path.join(RESULTS_DIR, "test_quarterly_backtest_regression.json"),
        "w", encoding="utf-8"
    ) as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    return passed, total


if __name__ == "__main__":
    os.chdir(SRC_DIR)
    print("=" * 65)
    print("🧪 四半期バックテスト レグレッションテスト (BTC 9Q + XAUT 12Q)")
    print("=" * 65)
    passed, total = run_all_tests()
    print(f"\n{'✅' if passed == total else '❌'} {passed}/{total} テスト合格")
    sys.exit(0 if passed == total else 1)
