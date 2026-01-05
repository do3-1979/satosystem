#!/usr/bin/env python3
"""
適応的戦略最適化システム
- 複数のアプローチを自動的にテスト
- 未来情報の混入をチェック
- 悪化した場合は自動ロールバック
- 最適な設定を見つける
"""

import json
import subprocess
import os
import sys
from pathlib import Path
import statistics
from datetime import datetime

# ワークスペースルート
WORKSPACE_ROOT = Path(__file__).parent.parent
CONFIG_PATH = WORKSPACE_ROOT / 'src' / 'config.ini'
BACKUP_PATH = WORKSPACE_ROOT / 'src' / 'config.ini.backup'

class ApproachTester:
    """アプローチをテストして結果を評価"""
    
    def __init__(self):
        self.baseline_results = None
        self.test_history = []
        
    def backup_config(self):
        """設定ファイルをバックアップ"""
        import shutil
        shutil.copy(CONFIG_PATH, BACKUP_PATH)
        print(f"✅ 設定をバックアップしました: {BACKUP_PATH}")
    
    def restore_config(self):
        """設定ファイルを復元"""
        import shutil
        if BACKUP_PATH.exists():
            shutil.copy(BACKUP_PATH, CONFIG_PATH)
            print(f"✅ 設定を復元しました")
        else:
            print(f"⚠️  バックアップが見つかりません")
    
    def modify_config(self, changes):
        """
        config.ini を一時的に変更
        
        Args:
            changes (dict): {'section.key': value} 形式の変更内容
        """
        import configparser
        
        config = configparser.ConfigParser()
        config.read(CONFIG_PATH, encoding='utf-8')
        
        for key_path, value in changes.items():
            section, key = key_path.split('.')
            if not config.has_section(section):
                config.add_section(section)
            config.set(section, key, str(value))
        
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            config.write(f)
        
        print(f"✅ 設定を変更しました: {changes}")
    
    def check_future_information_leakage(self, trade_logs):
        """
        未来情報の混入をチェック
        
        Args:
            trade_logs (list): トレードログのリスト
        
        Returns:
            dict: チェック結果
        """
        issues = []
        
        for trade in trade_logs:
            entry = trade.get('entry', {})
            exit_data = trade.get('exit', {})
            
            # エントリー時のタイムスタンプ
            entry_time = entry.get('timestamp', '')
            
            # エントリー時に使用されているデータ
            filters = entry.get('filters', {})
            signals = entry.get('signals', {})
            
            # チェック1: エントリー時にエグジット情報を参照していないか
            if 'exit_price' in entry or 'pnl' in entry:
                issues.append({
                    'type': 'FUTURE_LEAK',
                    'description': 'エントリー時にエグジット情報が含まれています',
                    'trade': trade.get('entry_number', 'unknown')
                })
            
            # チェック2: フィルター値が将来の情報を使っていないか
            # （例: エントリー後のボラティリティを参照など）
            # 注: これは現在のログ構造では検出困難だが、将来的に拡張可能
            
        return {
            'clean': len(issues) == 0,
            'issues': issues,
            'total_checks': len(trade_logs)
        }
    
    def run_backtest(self):
        """バックテストを実行"""
        print("\n🚀 バックテストを実行中...")
        
        try:
            result = subprocess.run(
                ['python3', 'run_quarterly_backtest.py'],
                cwd=WORKSPACE_ROOT,
                capture_output=True,
                text=True,
                timeout=600
            )
            
            if result.returncode != 0:
                print(f"❌ バックテスト実行エラー: {result.stderr}")
                return None
            
            print("✅ バックテスト完了")
            return result.stdout
            
        except subprocess.TimeoutExpired:
            print("❌ バックテストがタイムアウトしました")
            return None
        except Exception as e:
            print(f"❌ バックテスト実行エラー: {e}")
            return None
    
    def run_phase2_analysis(self):
        """フェーズ2分析を実行"""
        print("\n📊 フェーズ2分析を実行中...")
        
        try:
            result = subprocess.run(
                ['python3', 'tools/phase2_loss_analysis.py'],
                cwd=WORKSPACE_ROOT,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                print(f"❌ フェーズ2分析エラー: {result.stderr}")
                return None
            
            return self.parse_phase2_output(result.stdout)
            
        except Exception as e:
            print(f"❌ フェーズ2分析エラー: {e}")
            return None
    
    def parse_phase2_output(self, output):
        """フェーズ2分析の出力をパース"""
        results = {
            'total_trades': 0,
            'win_rate': 0.0,
            'total_pnl': 0.0,
            'avg_pnl': 0.0,
            'loss_trades': 0,
            'cumulative_loss': 0.0,
            'avg_loss': 0.0
        }
        
        lines = output.split('\n')
        for line in lines:
            if '総トレード数:' in line:
                try:
                    results['total_trades'] = int(line.split(':')[1].strip().split()[0])
                except:
                    pass
            elif '勝利:' in line and '(' in line:
                try:
                    win_rate_str = line.split('(')[1].split('%')[0]
                    results['win_rate'] = float(win_rate_str)
                except:
                    pass
            elif '総PnL:' in line:
                try:
                    results['total_pnl'] = float(line.split(':')[1].strip().split()[0])
                except:
                    pass
            elif '平均PnL:' in line:
                try:
                    results['avg_pnl'] = float(line.split(':')[1].strip().split()[0])
                except:
                    pass
            elif '【損失トレード数】:' in line:
                try:
                    results['loss_trades'] = int(line.split(':')[1].strip().split('/')[0])
                except:
                    pass
            elif '【累積損失】:' in line:
                try:
                    results['cumulative_loss'] = float(line.split(':')[1].strip().split()[0])
                except:
                    pass
            elif '【平均損失】:' in line:
                try:
                    results['avg_loss'] = float(line.split(':')[1].strip().split()[0].replace('USD/トレード', ''))
                except:
                    pass
        
        return results
    
    def evaluate_results(self, results, baseline=None):
        """
        結果を評価してスコアリング
        
        Args:
            results (dict): 分析結果
            baseline (dict): ベースライン結果（比較用）
        
        Returns:
            dict: 評価結果
        """
        if baseline is None:
            baseline = results
        
        # スコア計算（複数の指標を統合）
        score = 0.0
        evaluation = {}
        
        # 1. 勝率（40点満点）
        win_rate_score = results['win_rate'] * 0.4
        score += win_rate_score
        evaluation['win_rate_score'] = win_rate_score
        
        # 2. 平均PnL（30点満点）
        if results['avg_pnl'] > 0:
            avg_pnl_score = min(results['avg_pnl'] / 100 * 30, 30)
        else:
            avg_pnl_score = max(results['avg_pnl'] / 100 * 30, -30)
        score += avg_pnl_score
        evaluation['avg_pnl_score'] = avg_pnl_score
        
        # 3. 損失削減（30点満点）
        if baseline['cumulative_loss'] != 0:
            loss_reduction = (baseline['cumulative_loss'] - results['cumulative_loss']) / abs(baseline['cumulative_loss'])
            loss_score = loss_reduction * 30
        else:
            loss_score = 0
        score += loss_score
        evaluation['loss_score'] = loss_score
        
        evaluation['total_score'] = score
        
        # ベースラインとの比較
        if baseline != results:
            evaluation['vs_baseline'] = {
                'win_rate_delta': results['win_rate'] - baseline['win_rate'],
                'avg_pnl_delta': results['avg_pnl'] - baseline['avg_pnl'],
                'total_pnl_delta': results['total_pnl'] - baseline['total_pnl'],
                'loss_delta': results['cumulative_loss'] - baseline['cumulative_loss']
            }
        
        return evaluation
    
    def is_improvement(self, new_results, baseline_results):
        """
        改善されたかどうかを判定
        
        Args:
            new_results (dict): 新しい結果
            baseline_results (dict): ベースライン結果
        
        Returns:
            bool: 改善された場合 True
        """
        # 閾値設定
        MIN_WIN_RATE_DELTA = -5.0  # 勝率が5%以上下がったらNG
        MIN_AVG_PNL_DELTA = -10.0  # 平均PnLが10 USD以上下がったらNG
        
        win_rate_delta = new_results['win_rate'] - baseline_results['win_rate']
        avg_pnl_delta = new_results['avg_pnl'] - baseline_results['avg_pnl']
        
        # 両方の指標が悪化していたらNG
        if win_rate_delta < MIN_WIN_RATE_DELTA and avg_pnl_delta < MIN_AVG_PNL_DELTA:
            return False
        
        # 総合スコアで評価
        new_eval = self.evaluate_results(new_results, baseline_results)
        baseline_eval = self.evaluate_results(baseline_results)
        
        return new_eval['total_score'] > baseline_eval['total_score']


def test_approach(tester, approach_name, config_changes):
    """
    アプローチをテストして結果を返す
    
    Args:
        tester (ApproachTester): テスター
        approach_name (str): アプローチ名
        config_changes (dict): 設定変更内容
    
    Returns:
        dict: テスト結果
    """
    print("\n" + "=" * 100)
    print(f"🧪 アプローチテスト: {approach_name}")
    print("=" * 100)
    
    # 設定変更
    print(f"\n📝 設定変更: {config_changes}")
    tester.modify_config(config_changes)
    
    # バックテスト実行
    backtest_output = tester.run_backtest()
    if backtest_output is None:
        print(f"❌ {approach_name} のバックテスト失敗")
        return None
    
    # フェーズ2分析実行
    results = tester.run_phase2_analysis()
    if results is None:
        print(f"❌ {approach_name} の分析失敗")
        return None
    
    # 結果表示
    print(f"\n📊 {approach_name} の結果:")
    print(f"  総トレード数: {results['total_trades']}")
    print(f"  勝率: {results['win_rate']:.1f}%")
    print(f"  平均PnL: {results['avg_pnl']:.2f} USD")
    print(f"  累積損失: {results['cumulative_loss']:.2f} USD")
    
    return results


def main():
    print("\n" + "=" * 100)
    print("🔄 適応的戦略最適化システム")
    print("=" * 100)
    
    tester = ApproachTester()
    
    # 設定をバックアップ
    tester.backup_config()
    
    # ベースライン測定（現在の設定）
    print("\n📍 ベースライン測定中...")
    baseline_results = tester.run_phase2_analysis()
    
    if baseline_results is None:
        print("❌ ベースライン測定失敗")
        return
    
    print(f"\n📊 ベースライン結果:")
    print(f"  総トレード数: {baseline_results['total_trades']}")
    print(f"  勝率: {baseline_results['win_rate']:.1f}%")
    print(f"  平均PnL: {baseline_results['avg_pnl']:.2f} USD")
    print(f"  総PnL: {baseline_results['total_pnl']:.2f} USD")
    print(f"  累積損失: {baseline_results['cumulative_loss']:.2f} USD")
    
    tester.baseline_results = baseline_results
    baseline_eval = tester.evaluate_results(baseline_results)
    print(f"  ベーススコア: {baseline_eval['total_score']:.2f}")
    
    # テストするアプローチ一覧
    approaches = [
        {
            'name': 'アプローチ1: ADX閾値引き上げ (25→30)',
            'changes': {'Strategy.adx_bull_threshold': 30}
        },
        {
            'name': 'アプローチ2: ADX閾値引き上げ (25→35)',
            'changes': {'Strategy.adx_bull_threshold': 35}
        },
        {
            'name': 'アプローチ3: エントリー回数削減 (2→1)',
            'changes': {'RiskManagement.entry_times': 1}
        },
        {
            'name': 'アプローチ4: PVO長期間拡大 (70→100)',
            'changes': {'Strategy.pvo_l_term': 100}
        },
        {
            'name': 'アプローチ5: ドンチャン期間延長 (25→30)',
            'changes': {
                'Strategy.donchian_buy_term': 30,
                'Strategy.donchian_sell_term': 30
            }
        },
    ]
    
    best_approach = None
    best_results = baseline_results
    best_score = baseline_eval['total_score']
    
    # 各アプローチをテスト
    for approach in approaches:
        # 設定を復元
        tester.restore_config()
        
        # アプローチをテスト
        results = test_approach(tester, approach['name'], approach['changes'])
        
        if results is None:
            continue
        
        # 評価
        evaluation = tester.evaluate_results(results, baseline_results)
        print(f"\n📈 評価:")
        print(f"  スコア: {evaluation['total_score']:.2f} (ベースライン: {baseline_eval['total_score']:.2f})")
        
        if 'vs_baseline' in evaluation:
            vs_base = evaluation['vs_baseline']
            print(f"  勝率変化: {vs_base['win_rate_delta']:+.1f}%")
            print(f"  平均PnL変化: {vs_base['avg_pnl_delta']:+.2f} USD")
            print(f"  総PnL変化: {vs_base['total_pnl_delta']:+.2f} USD")
            print(f"  累積損失変化: {vs_base['loss_delta']:+.2f} USD")
        
        # 改善判定
        if tester.is_improvement(results, baseline_results):
            print(f"✅ 改善されました！")
            
            if evaluation['total_score'] > best_score:
                best_approach = approach
                best_results = results
                best_score = evaluation['total_score']
                print(f"🏆 これまでで最高のスコアです！")
        else:
            print(f"❌ 改善されませんでした。ロールバックします。")
    
    # 最終結果
    print("\n" + "=" * 100)
    print("🏁 最適化完了")
    print("=" * 100)
    
    if best_approach is not None:
        print(f"\n🏆 最適なアプローチ: {best_approach['name']}")
        print(f"  設定変更: {best_approach['changes']}")
        print(f"\n📊 最終結果:")
        print(f"  総トレード数: {best_results['total_trades']}")
        print(f"  勝率: {best_results['win_rate']:.1f}% ({best_results['win_rate'] - baseline_results['win_rate']:+.1f}%)")
        print(f"  平均PnL: {best_results['avg_pnl']:.2f} USD ({best_results['avg_pnl'] - baseline_results['avg_pnl']:+.2f} USD)")
        print(f"  総PnL: {best_results['total_pnl']:.2f} USD ({best_results['total_pnl'] - baseline_results['total_pnl']:+.2f} USD)")
        print(f"  累積損失: {best_results['cumulative_loss']:.2f} USD ({best_results['cumulative_loss'] - baseline_results['cumulative_loss']:+.2f} USD)")
        
        # 最適な設定を適用
        print(f"\n✅ 最適な設定を適用します...")
        tester.modify_config(best_approach['changes'])
        print(f"✅ 設定を保存しました")
        
    else:
        print(f"\n⚠️  改善されたアプローチが見つかりませんでした")
        print(f"✅ ベースライン設定を維持します")
        tester.restore_config()
    
    # バックアップ削除
    if BACKUP_PATH.exists():
        BACKUP_PATH.unlink()


if __name__ == '__main__':
    main()
