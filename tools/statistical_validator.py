"""
フェーズ3: 統計的有効性検証フレームワーク
Bootstrap信頼区間、Chi-square検定、効果量分析を実施
"""

import json
import numpy as np
from scipy import stats
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Tuple
import sys

@dataclass
class BootstrapResult:
    """Bootstrap検証結果"""
    metric: str
    original_value: float
    mean_estimate: float
    std_error: float
    ci_lower: float
    ci_upper: float
    ci_width: float

@dataclass
class ChiSquareResult:
    """カイ二乗検定結果"""
    contingency_table: List[List[int]]
    chi2_statistic: float
    p_value: float
    is_significant: bool
    effect_size_cramers_v: float

class StatisticalValidator:
    """統計的検証エンジン"""
    
    def __init__(self, trades_file: str, bootstrap_samples: int = 1000):
        self.trades = self._load_trades(trades_file)
        self.bootstrap_samples = bootstrap_samples
        self.results = {}
        
    def _load_trades(self, filepath: str) -> List[Dict]:
        """トレードJSONを読み込む"""
        with open(filepath, 'r') as f:
            data = json.load(f)
            if isinstance(data, dict) and 'trades' in data:
                return data['trades']
            return data if isinstance(data, list) else []
    
    def calculate_bootstrap_ci(self, values: List[float], 
                               ci: float = 0.95) -> BootstrapResult:
        """
        Bootstrap信頼区間を計算
        
        Args:
            values: データ値リスト
            ci: 信頼度（0.95 = 95%）
        
        Returns:
            BootstrapResult
        """
        original = np.mean(values)
        bootstrap_means = []
        
        np.random.seed(42)
        for _ in range(self.bootstrap_samples):
            sample = np.random.choice(values, size=len(values), replace=True)
            bootstrap_means.append(np.mean(sample))
        
        bootstrap_means = np.array(bootstrap_means)
        std_error = np.std(bootstrap_means)
        alpha = 1 - ci
        ci_lower = np.percentile(bootstrap_means, (alpha/2) * 100)
        ci_upper = np.percentile(bootstrap_means, (1 - alpha/2) * 100)
        
        return BootstrapResult(
            metric="mean_pnl",
            original_value=original,
            mean_estimate=np.mean(bootstrap_means),
            std_error=std_error,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            ci_width=ci_upper - ci_lower
        )
    
    def run_chi_square_test(self, passing_trades: int, passing_wins: int,
                           failing_trades: int, failing_wins: int) -> ChiSquareResult:
        """
        カイ二乗独立性検定
        フィルター合否と勝敗が独立か検定
        
        Args:
            passing_trades, passing_wins: 合格時の総数と勝利数
            failing_trades, failing_wins: 不合格時の総数と勝利数
        """
        # 分割表を構築
        contingency = [
            [passing_wins, passing_trades - passing_wins],
            [failing_wins, failing_trades - failing_wins]
        ]
        
        chi2, p_value, dof, expected = stats.chi2_contingency(np.array(contingency))
        
        # Cramér's V (効果量)
        n = passing_trades + failing_trades
        cramers_v = np.sqrt(chi2 / (n * (min(2, 2) - 1)))
        
        return ChiSquareResult(
            contingency_table=contingency,
            chi2_statistic=chi2,
            p_value=p_value,
            is_significant=p_value < 0.05,
            effect_size_cramers_v=cramers_v
        )
    
    def analyze_loss_patterns(self) -> Dict:
        """損失パターンの統計分析"""
        
        # パターン検出
        patterns = {
            'low_pvo': [],
            'short_hold': [],
            'consecutive_loss': []
        }
        
        loss_trades = [t for t in self.trades if t.get('result', {}).get('pnl_usd', 0) < 0]
        
        # Pattern 1: 低PVO（<50）
        low_pvo = [t for t in loss_trades if t.get('entry', {}).get('filters', {}).get('pvo', {}).get('value', 0) < 50]
        patterns['low_pvo'] = low_pvo
        
        # Pattern 2: 短期保有（1-2 bars）
        short_hold = [t for t in loss_trades if t.get('result', {}).get('bars_held', 0) <= 2]
        patterns['short_hold'] = short_hold
        
        # Pattern 3: 連続損失（前後3トレード中2個以上が損失）
        consecutive_loss = []
        for i, trade in enumerate(self.trades):
            if trade.get('result', {}).get('pnl_usd', 0) < 0:
                window = self.trades[max(0, i-1):min(len(self.trades), i+2)]
                loss_count = sum(1 for t in window if t.get('result', {}).get('pnl_usd', 0) < 0)
                if loss_count >= 2:
                    consecutive_loss.append(trade)
        patterns['consecutive_loss'] = consecutive_loss
        
        # 統計計算
        results = {}
        for pattern_name, pattern_trades in patterns.items():
            if pattern_trades:
                pnls = [t.get('result', {}).get('pnl_usd', 0) for t in pattern_trades]
                results[pattern_name] = {
                    'count': len(pattern_trades),
                    'frequency_pct': (len(pattern_trades) / len(loss_trades)) * 100,
                    'cumulative_pnl': sum(pnls),
                    'avg_pnl': np.mean(pnls),
                    'std_pnl': np.std(pnls),
                    'win_count': sum(1 for t in pattern_trades if t.get('result', {}).get('pnl_usd', 0) >= 0),
                    'win_rate': (sum(1 for t in pattern_trades if t.get('result', {}).get('pnl_usd', 0) >= 0) / len(pattern_trades)) * 100 if pattern_trades else 0
                }
        
        return results
    
    def validate_improvement_hypotheses(self) -> Dict:
        """改善仮説の検証"""
        
        results = {}
        
        # Hypothesis A: PVO > 10 → > 50 に引き上げ
        pvo_high = [t for t in self.trades if t.get('entry', {}).get('filters', {}).get('pvo', {}).get('value', 0) >= 50]
        pvo_low = [t for t in self.trades if t.get('entry', {}).get('filters', {}).get('pvo', {}).get('value', 0) < 50]
        
        if pvo_high:
            pnl_high = [t.get('result', {}).get('pnl_usd', 0) for t in pvo_high]
            results['pvo_threshold_50'] = {
                'description': 'PVO > 50 時のパフォーマンス',
                'sample_size': len(pvo_high),
                'total_pnl': sum(pnl_high),
                'avg_pnl': np.mean(pnl_high),
                'win_rate': (sum(1 for p in pnl_high if p >= 0) / len(pnl_high)) * 100,
                'bootstrapped_ci': self.calculate_bootstrap_ci(pnl_high)
            }
        
        if pvo_low:
            pnl_low = [t.get('result', {}).get('pnl_usd', 0) for t in pvo_low]
            excluded_improvement = sum(1 for p in pnl_low if p < 0) * np.mean([p for p in pnl_low if p < 0])
            results['pvo_exclusion_impact'] = {
                'description': 'PVO < 50 エントリー除外による損失削減',
                'excluded_trades': len(pvo_low),
                'excluded_loss_reduction': abs(excluded_improvement)
            }
        
        # Hypothesis B: ADX >= 31 → >= 40 に引き上げ
        adx_high = [t for t in self.trades if t.get('entry', {}).get('filters', {}).get('adx', {}).get('value', 0) >= 40]
        adx_medium = [t for t in self.trades if 30 <= t.get('entry', {}).get('filters', {}).get('adx', {}).get('value', 0) < 40]
        
        if adx_high:
            pnl_high = [t.get('result', {}).get('pnl_usd', 0) for t in adx_high]
            results['adx_threshold_40'] = {
                'description': 'ADX >= 40 時のパフォーマンス',
                'sample_size': len(adx_high),
                'total_pnl': sum(pnl_high),
                'avg_pnl': np.mean(pnl_high),
                'win_rate': (sum(1 for p in pnl_high if p >= 0) / len(pnl_high)) * 100,
                'bootstrapped_ci': self.calculate_bootstrap_ci(pnl_high)
            }
        
        return results
    
    def run_full_validation(self) -> Dict:
        """全体の統計検証を実施"""
        
        print("=" * 70)
        print("フェーズ3: 統計的有効性検証")
        print("=" * 70)
        
        # 基本統計
        all_pnls = [t.get('result', {}).get('pnl_usd', 0) for t in self.trades]
        wins = sum(1 for p in all_pnls if p >= 0)
        losses = len(all_pnls) - wins
        
        print(f"\n【基本統計】 (n={len(self.trades)} trades)")
        print(f"  勝利: {wins} ({wins/len(self.trades)*100:.1f}%)")
        print(f"  損失: {losses} ({losses/len(self.trades)*100:.1f}%)")
        print(f"  総PnL: {sum(all_pnls):.2f} USD")
        print(f"  平均PnL: {np.mean(all_pnls):.2f} USD")
        print(f"  中央値PnL: {np.median(all_pnls):.2f} USD")
        print(f"  標準偏差: {np.std(all_pnls):.2f} USD")
        
        # Bootstrap信頼区間
        print(f"\n【Bootstrap信頼区間】 ({self.bootstrap_samples} samples)")
        ci_result = self.calculate_bootstrap_ci(all_pnls)
        print(f"  平均PnL: {ci_result.original_value:.2f} USD")
        print(f"  標準誤差: {ci_result.std_error:.2f} USD")
        print(f"  95% CI: [{ci_result.ci_lower:.2f}, {ci_result.ci_upper:.2f}]")
        print(f"  信頼区間幅: {ci_result.ci_width:.2f} USD")
        
        # 損失パターン分析
        print(f"\n【損失パターン分析】")
        pattern_results = self.analyze_loss_patterns()
        for pattern_name, stats_data in pattern_results.items():
            print(f"\n  {pattern_name}:")
            print(f"    発生件数: {stats_data['count']} ({stats_data['frequency_pct']:.1f}%)")
            print(f"    累積PnL: {stats_data['cumulative_pnl']:.2f} USD")
            print(f"    平均PnL: {stats_data['avg_pnl']:.2f} USD")
            print(f"    勝率: {stats_data['win_rate']:.1f}%")
        
        # 改善仮説検証
        print(f"\n【改善仮説検証】")
        hyp_results = self.validate_improvement_hypotheses()
        for hyp_name, hyp_data in hyp_results.items():
            print(f"\n  {hyp_name}:")
            print(f"    説明: {hyp_data.get('description', 'N/A')}")
            print(f"    サンプル: {hyp_data.get('sample_size', 'N/A')}")
            print(f"    総PnL: {hyp_data.get('total_pnl', 'N/A'):.2f} USD" if 'total_pnl' in hyp_data else "")
            print(f"    平均PnL: {hyp_data.get('avg_pnl', 'N/A'):.2f} USD" if 'avg_pnl' in hyp_data else "")
            print(f"    勝率: {hyp_data.get('win_rate', 'N/A'):.1f}%" if 'win_rate' in hyp_data else "")
            if 'excluded_loss_reduction' in hyp_data:
                print(f"    損失削減: {hyp_data['excluded_loss_reduction']:.2f} USD")
        
        # Chi-square検定
        print(f"\n【フィルター効果の統計検定】")
        
        # PVO効果検定
        pvo_pass = [t for t in self.trades if t.get('entry', {}).get('filters', {}).get('pvo', {}).get('pass', False)]
        pvo_fail = [t for t in self.trades if not t.get('entry', {}).get('filters', {}).get('pvo', {}).get('pass', False)]
        
        if pvo_pass and pvo_fail:
            pvo_pass_wins = sum(1 for t in pvo_pass if t.get('result', {}).get('pnl_usd', 0) >= 0)
            pvo_fail_wins = sum(1 for t in pvo_fail if t.get('result', {}).get('pnl_usd', 0) >= 0)
            
            pvo_chi = self.run_chi_square_test(len(pvo_pass), pvo_pass_wins, 
                                               len(pvo_fail), pvo_fail_wins)
            print(f"\n  PVO Filter:")
            print(f"    Chi2統計量: {pvo_chi.chi2_statistic:.4f}")
            print(f"    p値: {pvo_chi.p_value:.6f} {'✓ 有意' if pvo_chi.is_significant else '✗ 非有意'}")
            print(f"    Cramér's V: {pvo_chi.effect_size_cramers_v:.4f}")
            print(f"    効果の大きさ: {'小' if pvo_chi.effect_size_cramers_v < 0.1 else '中' if pvo_chi.effect_size_cramers_v < 0.3 else '大'}")
        
        # ADX効果検定
        adx_pass = [t for t in self.trades if t.get('entry', {}).get('filters', {}).get('adx', {}).get('pass', False)]
        adx_fail = [t for t in self.trades if not t.get('entry', {}).get('filters', {}).get('adx', {}).get('pass', False)]
        
        if adx_pass and adx_fail:
            adx_pass_wins = sum(1 for t in adx_pass if t.get('result', {}).get('pnl_usd', 0) >= 0)
            adx_fail_wins = sum(1 for t in adx_fail if t.get('result', {}).get('pnl_usd', 0) >= 0)
            
            adx_chi = self.run_chi_square_test(len(adx_pass), adx_pass_wins, 
                                               len(adx_fail), adx_fail_wins)
            print(f"\n  ADX Filter:")
            print(f"    Chi2統計量: {adx_chi.chi2_statistic:.4f}")
            print(f"    p値: {adx_chi.p_value:.6f} {'✓ 有意' if adx_chi.is_significant else '✗ 非有意'}")
            print(f"    Cramér's V: {adx_chi.effect_size_cramers_v:.4f}")
            print(f"    効果の大きさ: {'小' if adx_chi.effect_size_cramers_v < 0.1 else '中' if adx_chi.effect_size_cramers_v < 0.3 else '大'}")
        
        print("\n" + "=" * 70)
        
        return {
            'basic_stats': {
                'total_trades': len(self.trades),
                'wins': wins,
                'losses': losses,
                'win_rate': wins / len(self.trades),
                'total_pnl': sum(all_pnls),
                'mean_pnl': np.mean(all_pnls),
                'std_pnl': np.std(all_pnls)
            },
            'bootstrap_ci': {
                'metric': ci_result.metric,
                'original_value': ci_result.original_value,
                'mean_estimate': ci_result.mean_estimate,
                'std_error': ci_result.std_error,
                'ci_lower': ci_result.ci_lower,
                'ci_upper': ci_result.ci_upper
            },
            'loss_patterns': pattern_results,
            'improvement_hypotheses': hyp_results
        }

if __name__ == "__main__":
    # デフォルトトレードファイル
    default_file = "/home/satoshi/work/satosystem/docs/analysis/trades/trades_comprehensive_55.json"
    
    trade_file = sys.argv[1] if len(sys.argv) > 1 else default_file
    
    if not Path(trade_file).exists():
        print(f"Error: {trade_file} not found")
        sys.exit(1)
    
    validator = StatisticalValidator(trade_file)
    results = validator.run_full_validation()
    
    # 結果をJSONで保存
    output_file = "/home/satoshi/work/satosystem/docs/analysis/statistical_validation_results.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n✓ 結果保存: {output_file}")
