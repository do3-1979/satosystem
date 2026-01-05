"""
トレードログベースの統計的検証スクリプト

TradeLogger が出力した JSON を使用した、フェーズ3相当の統計検証
これが新しい分析パイプラインになります
"""

import json
import numpy as np
from scipy import stats
from pathlib import Path
from typing import Dict, List
import sys

class TradeLogStatisticalAnalyzer:
    """トレードログベースの統計分析"""
    
    def __init__(self, log_file: str, bootstrap_samples: int = 1000):
        """
        初期化
        
        Args:
            log_file: トレードログ JSON ファイルパス
            bootstrap_samples: Bootstrap サンプル数
        """
        self.log_file = log_file
        self.bootstrap_samples = bootstrap_samples
        self.trades = []
        self._load_trades()
    
    def _load_trades(self):
        """トレードログを読み込む"""
        with open(self.log_file, 'r') as f:
            data = json.load(f)
            self.trades = data.get('trades', [])
    
    def calculate_bootstrap_ci(self, values: List[float], ci: float = 0.95):
        """Bootstrap 信頼区間を計算"""
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
        
        return {
            'original_value': original,
            'mean_estimate': np.mean(bootstrap_means),
            'std_error': std_error,
            'ci_lower': ci_lower,
            'ci_upper': ci_upper,
            'ci_width': ci_upper - ci_lower,
            'contains_zero': ci_lower <= 0 <= ci_upper
        }
    
    def run_analysis(self):
        """全体分析を実行"""
        
        print("=" * 80)
        print("【トレードログベースの統計検証】")
        print("=" * 80)
        
        # PnL 抽出
        pnls = [t.get('result', {}).get('pnl_usd', 0) for t in self.trades if t.get('result') is not None]
        wins = sum(1 for p in pnls if p >= 0)
        losses = len(pnls) - wins
        
        print(f"\n【基本統計】")
        print(f"  総トレード数: {len(self.trades)}")
        print(f"  勝利: {wins} ({wins/len(self.trades)*100:.1f}%)")
        print(f"  損失: {losses} ({losses/len(self.trades)*100:.1f}%)")
        print(f"  総 PnL: {sum(pnls):,.2f} USD")
        print(f"  平均 PnL: {np.mean(pnls):.2f} USD")
        print(f"  中央値 PnL: {np.median(pnls):.2f} USD")
        print(f"  標準偏差: {np.std(pnls):.2f} USD")
        
        # Bootstrap 信頼区間
        print(f"\n【Bootstrap 信頼区間（95%）】")
        ci_result = self.calculate_bootstrap_ci(pnls)
        print(f"  平均 PnL: {ci_result['original_value']:.2f} USD")
        print(f"  標準誤差: {ci_result['std_error']:.2f} USD")
        print(f"  95% CI: [{ci_result['ci_lower']:.2f}, {ci_result['ci_upper']:.2f}] USD")
        print(f"  信頼区間幅: {ci_result['ci_width']:.2f} USD")
        print(f"  ⚠️ 0 を含む: {'はい（有意でない）' if ci_result['contains_zero'] else 'いいえ（有意）'}")
        
        # フィルター効果分析
        print(f"\n【フィルター効果分析】")
        
        # Volatility フィルター
        vola_pass = [t for t in self.trades if t.get('entry', {}).get('filters', {}).get('volatility', {}).get('pass', False)]
        vola_fail = [t for t in self.trades if not t.get('entry', {}).get('filters', {}).get('volatility', {}).get('pass', False)]
        
        if vola_pass:
            vola_pass_pnls = [t.get('result', {}).get('pnl_usd', 0) for t in vola_pass if t.get('result') is not None]
            vola_pass_wins = sum(1 for p in vola_pass_pnls if p >= 0)
            print(f"\n  Volatility PASS ({len(vola_pass)} trades):")
            print(f"    勝率: {vola_pass_wins/len(vola_pass_pnls)*100:.1f}%")
            print(f"    平均 PnL: {np.mean(vola_pass_pnls):.2f} USD")
        
        if vola_fail:
            vola_fail_pnls = [t.get('result', {}).get('pnl_usd', 0) for t in vola_fail if t.get('result') is not None]
            vola_fail_wins = sum(1 for p in vola_fail_pnls if p >= 0)
            print(f"\n  Volatility FAIL ({len(vola_fail)} trades):")
            print(f"    勝率: {vola_fail_wins/len(vola_fail_pnls)*100:.1f}%")
            print(f"    平均 PnL: {np.mean(vola_fail_pnls):.2f} USD")
            print(f"    ⚠️ Volatility が高い相場での成績: {np.mean(vola_fail_pnls):.2f} USD")
        
        # PVO フィルター
        pvo_pass = [t for t in self.trades if t.get('entry', {}).get('filters', {}).get('pvo', {}).get('pass', False)]
        pvo_fail = [t for t in self.trades if not t.get('entry', {}).get('filters', {}).get('pvo', {}).get('pass', False)]
        
        if pvo_pass:
            pvo_pass_pnls = [t.get('result', {}).get('pnl_usd', 0) for t in pvo_pass if t.get('result') is not None]
            pvo_pass_wins = sum(1 for p in pvo_pass_pnls if p >= 0)
            print(f"\n  PVO PASS ({len(pvo_pass)} trades):")
            print(f"    勝率: {pvo_pass_wins/len(pvo_pass_pnls)*100:.1f}%")
            print(f"    平均 PnL: {np.mean(pvo_pass_pnls):.2f} USD")
        
        if pvo_fail:
            pvo_fail_pnls = [t.get('result', {}).get('pnl_usd', 0) for t in pvo_fail if t.get('result') is not None]
            pvo_fail_wins = sum(1 for p in pvo_fail_pnls if p >= 0)
            print(f"\n  PVO FAIL ({len(pvo_fail)} trades):")
            print(f"    勝率: {pvo_fail_wins/len(pvo_fail_pnls)*100:.1f}%")
            print(f"    平均 PnL: {np.mean(pvo_fail_pnls):.2f} USD")
        
        # 市場体制別
        print(f"\n【市場体制別パフォーマンス】")
        regimes = {}
        for t in self.trades:
            regime = t.get('entry', {}).get('market', {}).get('regime', 'UNKNOWN')
            if regime not in regimes:
                regimes[regime] = []
            regimes[regime].append(t.get('result', {}).get('pnl_usd', 0))
        
        for regime, pnls_list in sorted(regimes.items()):
            wins = sum(1 for p in pnls_list if p >= 0)
            print(f"\n  {regime}:")
            print(f"    トレード数: {len(pnls_list)}")
            print(f"    勝率: {wins/len(pnls_list)*100:.1f}%")
            print(f"    平均 PnL: {np.mean(pnls_list):.2f} USD")
            print(f"    総 PnL: {sum(pnls_list):.2f} USD")
        
        print(f"\n【推奨事項】")
        print(f"  ✓ Volatility フィルターの効果を検証中")
        print(f"  ✓ 市場体制判定の改善を検討中")
        print(f"  ✓ Strategy 信号の統合を計画中")
        
        print("\n" + "=" * 80)
        
        return {
            'basic_stats': {
                'total_trades': len(self.trades),
                'wins': wins,
                'losses': losses,
                'win_rate': float(wins / len(self.trades)),
                'total_pnl': float(sum(pnls)),
                'mean_pnl': float(np.mean(pnls)),
                'std_pnl': float(np.std(pnls))
            },
            'bootstrap_ci': {
                'ci_lower': float(ci_result['ci_lower']),
                'ci_upper': float(ci_result['ci_upper']),
                'contains_zero': bool(ci_result['contains_zero']),
                'is_significant': bool(not ci_result['contains_zero'])
            },
            'filter_analysis': {
                'volatility': {
                    'pass_count': len(vola_pass),
                    'fail_count': len(vola_fail)
                }
            }
        }

if __name__ == "__main__":
    default_file = "/home/satoshi/work/satosystem/logs/trade_log_20260105082010.json"
    
    filepath = sys.argv[1] if len(sys.argv) > 1 else default_file
    
    if not Path(filepath).exists():
        print(f"Error: {filepath} not found")
        sys.exit(1)
    
    analyzer = TradeLogStatisticalAnalyzer(filepath)
    results = analyzer.run_analysis()
    
    # 結果を JSON で保存
    output_file = filepath.replace('trade_log_', 'statistical_analysis_')
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"✓ 統計分析結果保存: {output_file}")
