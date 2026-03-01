"""
risk_overlay.py のレグレッションテスト

RiskOverlay クラスのキルスイッチ動作確認
"""

import os
import sys
import configparser

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(WORKSPACE_ROOT, "src")
sys.path.insert(0, SRC_DIR)

from config import Config
from risk_overlay import RiskOverlay


def _make_mock_config(enabled='1', max_dd='50.0', daily='20.0', consec='5', auto='1', balance='100'):
    """テスト用Configモックを作成してConfigに注入"""
    c = configparser.ConfigParser()
    c['RiskOverlay'] = {
        'enabled': enabled,
        'max_drawdown_pct': max_dd,
        'daily_loss_limit_pct': daily,
        'consecutive_losses_limit': consec,
        'auto_resume_next_day': auto,
    }
    c['RiskManagement'] = {'account_balance': balance}
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


def run_all_tests():
    tests = [
        test_risk_overlay_disabled,
        test_risk_overlay_dd_stop,
        test_risk_overlay_consecutive_losses,
        test_risk_overlay_daily_loss,
        test_risk_overlay_win_resets_consecutive,
        test_risk_overlay_get_status,
    ]
    success = 0
    for test in tests:
        try:
            test()
            success += 1
        except Exception as e:
            print(f"  ❌ {test.__name__}: {e}")
    print(f"\n  結果: {success}/{len(tests)} 成功")
    return success == len(tests)


if __name__ == "__main__":
    print("[Test] RiskOverlay キルスイッチ動作確認")
    ok = run_all_tests()
    exit(0 if ok else 1)
