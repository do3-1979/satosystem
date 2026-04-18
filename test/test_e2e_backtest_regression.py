"""
E2Eバックテスト検証テスト

bot.pyをサブプロセスで実行し、以下を検証する：
1. バックテストが正常に完走する（exit code 0）
2. backtest_summary JSONが出力され、必須キーを含む
3. メトリクス値が妥当な範囲にある
4. 同一入力で再実行すると同一結果（決定論的再現性）
"""

import os
import sys
import json
import glob
import subprocess
import time

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(WORKSPACE_ROOT, "src")
LOGS_DIR = os.path.join(WORKSPACE_ROOT, "logs")
sys.path.insert(0, SRC_DIR)

# テスト期間: キャッシュに確実に存在する短期間（ドンチャン30期間分のウォームアップ含む）
TEST_START = "2024-06-01"
TEST_END = "2024-06-15"

# backtest_summary JSON の必須キー
REQUIRED_KEYS = [
    "total_pnl", "profit_factor", "max_drawdown", "max_drawdown_rate",
    "sharpe", "sortino", "recovery_factor", "win_rate", "payoff_ratio",
    "expectancy", "max_consec_losses", "trades", "samples",
]

# テスト間で共有するキャッシュ
_cached_summary = None


def _get_cached_summary():
    """キャッシュされたサマリを返す。未実行なら最初に1回実行する"""
    global _cached_summary
    if _cached_summary is None:
        summary, info = _run_backtest()
        _cached_summary = summary
    return _cached_summary


def _run_backtest(start=TEST_START, end=TEST_END, timeout=300):
    """bot.pyをサブプロセスで実行し、結果JSONを返す"""
    result = subprocess.run(
        ["python3", "src/bot.py", "test", start, end],
        cwd=WORKSPACE_ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        return None, f"exit code {result.returncode}: {result.stderr[:300]}"

    # 最新のサマリJSONを取得
    pattern = os.path.join(LOGS_DIR, "backtest_summary_*.json")
    files = glob.glob(pattern)
    if not files:
        return None, "backtest_summary JSONが生成されませんでした"

    latest = max(files, key=os.path.getmtime)
    with open(latest) as f:
        summary = json.load(f)

    return summary, latest


def test_backtest_completes():
    """バックテストが正常に完走し、サマリJSONが出力される"""
    try:
        summary, info = _run_backtest()
        if summary is None:
            return False, f"❌ バックテスト失敗: {info}"
        return True, f"✅ バックテスト完走: {os.path.basename(info)}"
    except subprocess.TimeoutExpired:
        return False, "❌ バックテストがタイムアウト（300秒）"
    except Exception as e:
        return False, f"❌ エラー: {e}"


def test_summary_has_required_keys():
    """サマリJSONが必須キーを全て含む"""
    try:
        summary = _get_cached_summary()
        if summary is None:
            return False, "❌ キャッシュされたサマリがありません"

        missing = [k for k in REQUIRED_KEYS if k not in summary]
        if missing:
            return False, f"❌ 欠落キー: {missing}"
        return True, f"✅ 全必須キー({len(REQUIRED_KEYS)}個)が存在"
    except Exception as e:
        return False, f"❌ エラー: {e}"


def test_metrics_valid_ranges():
    """メトリクス値が妥当な範囲にある"""
    try:
        summary = _get_cached_summary()
        if summary is None:
            return False, "❌ キャッシュされたサマリがありません"

        errors = []

        # samples > 0 (データが処理された)
        if summary.get("samples", 0) <= 0:
            errors.append(f"samples={summary.get('samples')} (>0 が期待)")

        # max_drawdown >= 0 (ドローダウンは非負)
        if summary.get("max_drawdown", -1) < 0:
            errors.append(f"max_drawdown={summary.get('max_drawdown')} (>=0 が期待)")

        # max_drawdown_rate: 0〜100% の範囲
        dd_rate = summary.get("max_drawdown_rate", -1)
        if dd_rate < 0 or dd_rate > 100:
            errors.append(f"max_drawdown_rate={dd_rate} (0〜100 が期待)")

        # win_rate: 0〜100% の範囲（トレード0の場合は0.0）
        wr = summary.get("win_rate", -1)
        if wr < 0 or wr > 100:
            errors.append(f"win_rate={wr} (0〜100 が期待)")

        # trades >= 0
        if summary.get("trades", -1) < 0:
            errors.append(f"trades={summary.get('trades')} (>=0 が期待)")

        # profit_factor >= 0
        if summary.get("profit_factor", -1) < 0:
            errors.append(f"profit_factor={summary.get('profit_factor')} (>=0 が期待)")

        if errors:
            return False, f"❌ 範囲外: {'; '.join(errors)}"
        return True, f"✅ メトリクス値が妥当 (samples={summary['samples']}, trades={summary['trades']}, pnl={summary['total_pnl']:.2f})"
    except Exception as e:
        return False, f"❌ エラー: {e}"


def test_deterministic_reproducibility():
    """同一入力で2回実行した結果が一致する（決定論的再現性）"""
    try:
        summary1 = _get_cached_summary()
        if summary1 is None:
            return False, "❌ 1回目のサマリがありません"

        summary2, info2 = _run_backtest()
        if summary2 is None:
            return False, f"❌ 2回目失敗: {info2}"

        # 比較対象キー（全必須キー）
        diffs = {}
        for key in REQUIRED_KEYS:
            v1 = summary1.get(key)
            v2 = summary2.get(key)
            if isinstance(v1, float) and isinstance(v2, float):
                if abs(v1 - v2) > 1e-6:
                    diffs[key] = (v1, v2)
            elif v1 != v2:
                diffs[key] = (v1, v2)

        if diffs:
            return False, f"❌ 再現性なし: {diffs}"
        return True, f"✅ 2回実行で同一結果（PnL={summary1['total_pnl']:.2f}, trades={summary1['trades']}）"
    except Exception as e:
        return False, f"❌ エラー: {e}"


def test_samples_match_period():
    """サンプル数が期間に対して妥当（4H足の場合、14日間 ≈ 84バー）"""
    try:
        summary = _get_cached_summary()
        if summary is None:
            return False, "❌ キャッシュされたサマリがありません"

        samples = summary.get("samples", 0)
        # 14日間 × 6バー/日 = 84バー（±10バーの余裕）
        expected_min = 70
        expected_max = 100

        if samples < expected_min or samples > expected_max:
            return False, f"❌ samples={samples} (期待: {expected_min}〜{expected_max})"
        return True, f"✅ samples={samples} (14日間の4H足として妥当)"
    except Exception as e:
        return False, f"❌ エラー: {e}"


# ========================================
# テスト実行
# ========================================

def run_all_tests():
    """全テストを実行"""
    # 最初に1回バックテストを実行し、結果をキャッシュ
    # （各テストが_run_backtest()を呼ぶが、再現性テスト以外は同じ結果を使えるよう最適化可能）
    tests = [
        ("バックテスト完走", test_backtest_completes),
        ("サマリJSON必須キー", test_summary_has_required_keys),
        ("メトリクス値範囲", test_metrics_valid_ranges),
        ("決定論的再現性", test_deterministic_reproducibility),
        ("サンプル数妥当性", test_samples_match_period),
    ]

    print("=" * 70)
    print("🧪 E2Eバックテスト検証テスト")
    print(f"   期間: {TEST_START} 〜 {TEST_END}")
    print("=" * 70)

    passed = 0
    failed = 0

    # 効率化: 1回実行した結果を共有（再現性テスト以外）
    cached_summary = None
    cached_info = None

    for name, test_func in tests:
        success, message = test_func()
        status = "✅" if success else "❌"
        print(f"{status} {message}")
        if success:
            passed += 1
        else:
            failed += 1

    print(f"\n📊 結果: {passed}/{passed + failed} 成功")

    # レグレッションスイート用JSON出力
    results_dir = os.path.join(WORKSPACE_ROOT, "docs", "regression_test_results")
    os.makedirs(results_dir, exist_ok=True)
    result_file = os.path.join(results_dir, "test_e2e_backtest_regression.json")
    with open(result_file, "w") as f:
        json.dump({"passed": passed, "total": passed + failed}, f)

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    run_all_tests()
