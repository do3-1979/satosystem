"""
risk_overlay.py のレグレッションテスト

RiskOverlay クラスのキルスイッチ動作確認
"""

import os
import sys
import json
import configparser
from datetime import datetime

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(WORKSPACE_ROOT, "src")
sys.path.insert(0, SRC_DIR)

from config import Config
from risk_overlay import RiskOverlay


def _make_mock_config(enabled='1', max_dd='50.0', daily='20.0', consec='5', auto='1', balance='100', dd_resume_bars='0'):
    """テスト用Configモックを作成してConfigに注入"""
    c = configparser.ConfigParser()
    c['RiskOverlay'] = {
        'enabled': enabled,
        'max_drawdown_pct': max_dd,
        'daily_loss_limit_pct': daily,
        'consecutive_losses_limit': consec,
        'auto_resume_next_day': auto,
        'dd_resume_bars': dd_resume_bars,
    }
    c['RiskManagement'] = {'account_balance': balance}
    c['Market'] = {'time_frame': '240'}
    Config.config = c


class _MockPortfolio:
    """テスト用Portfolioスタブ"""
    def __init__(self, dd_rate=0.0):
        self._dd_rate = dd_rate

    def get_drawdown_rate(self):
        return self._dd_rate


def test_risk_overlay_disabled():
    """enabled=0のとき、常に取引可能を返す"""
    _make_mock_config(enabled='0')
    overlay = RiskOverlay()
    can, reason = overlay.check_can_trade(_MockPortfolio(dd_rate=99.0))
    assert can is True, f"disabled時はTrueのはず: {reason}"
    print("  ✅ disabled時はバイパス確認")


def test_risk_overlay_dd_stop():
    """最大DD超過で取引停止になる"""
    _make_mock_config(enabled='1', max_dd='50.0')
    overlay = RiskOverlay()
    # DD未満 → OK
    can, _ = overlay.check_can_trade(_MockPortfolio(dd_rate=49.9))
    assert can is True, "DD未満はOKのはず"
    # DD到達 → 停止
    can, reason = overlay.check_can_trade(_MockPortfolio(dd_rate=50.0))
    assert can is False, f"DD超過で停止のはず: {reason}"
    assert "DD_STOP" in reason
    print("  ✅ 最大DD50%超過でDD_STOP確認")


def test_risk_overlay_consecutive_losses():
    """連続損失N回で取引停止になる"""
    _make_mock_config(enabled='1', consec='3', daily='99.0')  # 日次上限を高くして干渉しない
    overlay = RiskOverlay()
    # 2連敗 → まだOK
    overlay.notify_trade_result(-5.0)
    overlay.notify_trade_result(-5.0)
    can, _ = overlay.check_can_trade(_MockPortfolio())
    assert can is True, "2連敗はOKのはず"
    # 3連敗 → 停止
    overlay.notify_trade_result(-5.0)
    can, reason = overlay.check_can_trade(_MockPortfolio())
    assert can is False, f"3連敗で停止のはず: {reason}"
    assert "CONSEC_STOP" in reason
    print("  ✅ 連続損失3回でCONSEC_STOP確認")


def test_risk_overlay_daily_loss():
    """日次損失上限超過で当日取引停止になる"""
    _make_mock_config(enabled='1', daily='20.0', balance='100')
    overlay = RiskOverlay()
    # 19USD損失 → OK
    overlay.notify_trade_result(-19.0)
    can, _ = overlay.check_can_trade(_MockPortfolio())
    assert can is True, "19USD損失はOKのはず（上限20%=20USD）"
    # さらに2USD → 21USD合計 → 停止
    overlay.notify_trade_result(-2.0)
    can, reason = overlay.check_can_trade(_MockPortfolio())
    assert can is False, f"日次損失上限超過で停止のはず: {reason}"
    assert "DAILY_STOP" in reason
    print("  ✅ 日次損失20%超過でDAILY_STOP確認")


def test_risk_overlay_win_resets_consecutive():
    """勝ちトレードで連続損失カウントがリセットされる"""
    _make_mock_config(enabled='1', consec='5')
    overlay = RiskOverlay()
    overlay.notify_trade_result(-10.0)
    overlay.notify_trade_result(-10.0)
    assert overlay._consecutive_losses == 2
    # 勝ち → リセット
    overlay.notify_trade_result(5.0)
    assert overlay._consecutive_losses == 0, "勝ちでリセットされるはず"
    print("  ✅ 勝ちトレードで連続損失カウントリセット確認")


def test_risk_overlay_get_status():
    """get_status()が正しい辞書を返す"""
    _make_mock_config(enabled='1')
    overlay = RiskOverlay()
    status = overlay.get_status()
    assert 'enabled' in status
    assert 'dd_stop' in status
    assert 'consecutive_losses' in status
    assert 'daily_loss_usd' in status
    print("  ✅ get_status()の構造確認")


def test_risk_overlay_dd_resume_bars():
    """H-033b: dd_resume_bars > 0 のとき、指定バー数経過後にDD停止が解除される"""
    # time_frame=240分, dd_resume_bars=2 → 2バー=480分=28800秒経過で再開
    _make_mock_config(enabled='1', max_dd='50.0', dd_resume_bars='2')
    overlay = RiskOverlay()

    portfolio = _MockPortfolio(dd_rate=55.0)  # DD 55% > 閾値50%
    t0 = 1000000

    # DD超過直後は停止
    can, reason = overlay.check_can_trade(portfolio, current_epoch=t0)
    assert not can, "DD超過直後は停止すべき"
    assert "DD_STOP" in reason

    # 1バー経過（まだ停止中）
    t1 = t0 + 240 * 60 * 1  # 1バー分
    can, reason = overlay.check_can_trade(portfolio, current_epoch=t1)
    assert not can, "1バー後はまだ停止すべき"

    # 2バー経過（再開）
    t2 = t0 + 240 * 60 * 2  # 2バー分
    can, reason = overlay.check_can_trade(portfolio, current_epoch=t2)
    assert can, f"2バー後は再開すべき: {reason}"
    print("  ✅ DD停止後の自動再開（dd_resume_bars=2）")


def test_risk_overlay_dd_resume_bars_zero():
    """dd_resume_bars=0（デフォルト）のとき、DD停止は永続する"""
    _make_mock_config(enabled='1', max_dd='50.0', dd_resume_bars='0')
    overlay = RiskOverlay()

    portfolio = _MockPortfolio(dd_rate=55.0)
    t0 = 1000000

    overlay.check_can_trade(portfolio, current_epoch=t0)

    # 1000バー後も停止継続
    t_far = t0 + 240 * 60 * 1000
    can, reason = overlay.check_can_trade(portfolio, current_epoch=t_far)
    assert not can, "dd_resume_bars=0では永続停止すべき"
    print("  ✅ dd_resume_bars=0で永続停止確認")


def run_all_tests():
    tests = [
        test_risk_overlay_disabled,
        test_risk_overlay_dd_stop,
        test_risk_overlay_consecutive_losses,
        test_risk_overlay_daily_loss,
        test_risk_overlay_win_resets_consecutive,
        test_risk_overlay_get_status,
        test_risk_overlay_dd_resume_bars,
        test_risk_overlay_dd_resume_bars_zero,
    ]
    success = 0
    for test in tests:
        try:
            test()
            success += 1
        except Exception as e:
            print(f"  ❌ {test.__name__}: {e}")
    print(f"\n  結果: {success}/{len(tests)} 成功")
    return success, len(tests)


if __name__ == "__main__":
    print("[Test] RiskOverlay キルスイッチ動作確認")
    passed_count, total_count = run_all_tests()

    WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    RESULTS_DIR = os.path.join(WORKSPACE_ROOT, "docs/regression_test_results")
    os.makedirs(RESULTS_DIR, exist_ok=True)

    with open(os.path.join(RESULTS_DIR, "test_risk_overlay_regression.json"), "w", encoding="utf-8") as f:
        json.dump({
            "test": "test_risk_overlay_regression",
            "total": total_count,
            "passed": passed_count,
            "timestamp": datetime.now().isoformat()
        }, f, ensure_ascii=False, indent=2)

    exit(0 if passed_count == total_count else 1)
