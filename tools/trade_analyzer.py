#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
trade_analyzer.py

抽出されたトレード情報を分析し、
損失パターン、因果関係、改善提案を生成します。
"""

import pandas as pd
import json
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass
from collections import defaultdict
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))


@dataclass
class LossPattern:
    """損失パターン"""
    pattern_id: str
    description: str
    condition: Dict  # 該当条件
    affected_trades: int
    avg_loss_usd: float
    avg_loss_pct: float
    frequency_pct: float
    severity_score: float  # 0-100 (高いほど危険)


@dataclass
class ImprovementHypothesis:
    """改善仮説"""
    hypothesis_id: str
    title: str
    description: str
    target_pattern: str
    expected_loss_reduction: float
    expected_win_rate_improvement: float
    implementation_complexity: str  # LOW/MEDIUM/HIGH
    risk_level: str  # LOW/MEDIUM/HIGH


class TradeAnalyzer:
    """トレード分析エンジン"""
    
    def __init__(self, trades_csv_path: str):
        self.df = pd.read_csv(trades_csv_path)
        self.loss_patterns: List[LossPattern] = []
        self.hypotheses: List[ImprovementHypothesis] = []
    
    def identify_loss_patterns(self) -> List[LossPattern]:
        """損失パターンを特定"""
        
        patterns = []
        lose_df = self.df[self.df['pnl_usd'] < 0]
        total_trades = len(self.df)
        
        # パターン 1: ADX が低い場合
        low_adx = lose_df[lose_df['adx_value'] < 20]
        if len(low_adx) > 0:
            pattern = LossPattern(
                pattern_id="P001",
                description="ADX が低い (< 20) 時のエントリー",
                condition={"adx": "< 20"},
                affected_trades=len(low_adx),
                avg_loss_usd=low_adx['pnl_usd'].mean(),
                avg_loss_pct=low_adx['pnl_pct'].mean(),
                frequency_pct=(len(low_adx) / total_trades * 100),
                severity_score=self._calculate_severity(low_adx)
            )
            patterns.append(pattern)
        
        # パターン 2: PVO が低い場合
        low_pvo = lose_df[lose_df['pvo_value'] < 50]
        if len(low_pvo) > 0:
            pattern = LossPattern(
                pattern_id="P002",
                description="PVO が低い (< 50) 時のエントリー",
                condition={"pvo": "< 50"},
                affected_trades=len(low_pvo),
                avg_loss_usd=low_pvo['pnl_usd'].mean(),
                avg_loss_pct=low_pvo['pnl_pct'].mean(),
                frequency_pct=(len(low_pvo) / total_trades * 100),
                severity_score=self._calculate_severity(low_pvo)
            )
            patterns.append(pattern)
        
        # パターン 3: RANGING での損失
        ranging_loss = lose_df[lose_df['market_regime'] == 'RANGING']
        if len(ranging_loss) > 0:
            pattern = LossPattern(
                pattern_id="P003",
                description="RANGING (ボックス相場) での損失",
                condition={"market_regime": "RANGING"},
                affected_trades=len(ranging_loss),
                avg_loss_usd=ranging_loss['pnl_usd'].mean(),
                avg_loss_pct=ranging_loss['pnl_pct'].mean(),
                frequency_pct=(len(ranging_loss) / total_trades * 100),
                severity_score=self._calculate_severity(ranging_loss)
            )
            patterns.append(pattern)
        
        # パターン 4: Strategy 不一致
        mismatch = lose_df[lose_df['strategy_match'] == False]
        if len(mismatch) > 0:
            pattern = LossPattern(
                pattern_id="P004",
                description="Strategy と Donchian が矛盾している",
                condition={"strategy_match": False},
                affected_trades=len(mismatch),
                avg_loss_usd=mismatch['pnl_usd'].mean(),
                avg_loss_pct=mismatch['pnl_pct'].mean(),
                frequency_pct=(len(mismatch) / total_trades * 100),
                severity_score=self._calculate_severity(mismatch)
            )
            patterns.append(pattern)
        
        # パターン 5: 高ボラティリティ
        high_vol = lose_df[lose_df['volatility_value'] > 2.0]
        if len(high_vol) > 0:
            pattern = LossPattern(
                pattern_id="P005",
                description="高ボラティリティ (> 2.0) での損失",
                condition={"volatility": "> 2.0"},
                affected_trades=len(high_vol),
                avg_loss_usd=high_vol['pnl_usd'].mean(),
                avg_loss_pct=high_vol['pnl_pct'].mean(),
                frequency_pct=(len(high_vol) / total_trades * 100),
                severity_score=self._calculate_severity(high_vol)
            )
            patterns.append(pattern)
        
        # 重要度でソート
        patterns.sort(key=lambda p: p.severity_score, reverse=True)
        self.loss_patterns = patterns
        
        return patterns
    
    def generate_hypotheses(self) -> List[ImprovementHypothesis]:
        """改善仮説を生成"""
        
        hypotheses = []
        win_df = self.df[self.df['pnl_usd'] > 0]
        lose_df = self.df[self.df['pnl_usd'] < 0]
        
        # 仮説 1: ADX 閾値を上げる
        if len(lose_df[lose_df['adx_value'] < 20]) > 5:
            hypotheses.append(ImprovementHypothesis(
                hypothesis_id="H001",
                title="ADX 閾値を 20 → 30 に引き上げ",
                description="トレンド判定を厳しくして、弱いトレンドでのエントリーを避ける",
                target_pattern="P001",
                expected_loss_reduction=500.0,
                expected_win_rate_improvement=5.0,
                implementation_complexity="LOW",
                risk_level="LOW"
            ))
        
        # 仮説 2: PVO 閾値を上げる
        if len(lose_df[lose_df['pvo_value'] < 50]) > 5:
            hypotheses.append(ImprovementHypothesis(
                hypothesis_id="H002",
                title="PVO 閾値を 10 → 100 に引き上げ",
                description="モメンタムが弱いシグナルを除外",
                target_pattern="P002",
                expected_loss_reduction=300.0,
                expected_win_rate_improvement=3.0,
                implementation_complexity="LOW",
                risk_level="MEDIUM"
            ))
        
        # 仮説 3: RANGING でのエントリー禁止
        if len(lose_df[lose_df['market_regime'] == 'RANGING']) > 5:
            hypotheses.append(ImprovementHypothesis(
                hypothesis_id="H003",
                title="RANGING でのエントリー禁止",
                description="ボックス相場ではトレードしない",
                target_pattern="P003",
                expected_loss_reduction=450.0,
                expected_win_rate_improvement=8.0,
                implementation_complexity="MEDIUM",
                risk_level="MEDIUM"
            ))
        
        # 仮説 4: Strategy 不一致時のエントリー禁止
        if len(lose_df[lose_df['strategy_match'] == False]) > 5:
            hypotheses.append(ImprovementHypothesis(
                hypothesis_id="H004",
                title="Strategy 不一致時のエントリー禁止",
                description="複数シグナルが矛盾している場合は見送る",
                target_pattern="P004",
                expected_loss_reduction=200.0,
                expected_win_rate_improvement=4.0,
                implementation_complexity="LOW",
                risk_level="LOW"
            ))
        
        self.hypotheses = hypotheses
        return hypotheses
    
    def create_causality_matrix(self) -> pd.DataFrame:
        """因果関係マトリックスを生成"""
        
        conditions = [
            ('pvo_value', [0, 50, 100, 500, 1000]),  # PVO 値
            ('adx_value', [0, 20, 30, 50]),  # ADX 値
            ('volatility_value', [0, 1.0, 2.0, 3.0]),  # ボラティリティ
            ('market_regime', ['RANGING', 'TRENDING_UP', 'TRENDING_DOWN']),  # 市場体制
        ]
        
        matrix_data = []
        
        for col_name, ranges in conditions:
            if col_name == 'market_regime':
                for regime in ranges:
                    subset = self.df[self.df[col_name] == regime]
                    row = self._calculate_metrics(subset, regime)
                    matrix_data.append(row)
            else:
                for i in range(len(ranges) - 1):
                    low, high = ranges[i], ranges[i + 1]
                    subset = self.df[(self.df[col_name] >= low) & (self.df[col_name] < high)]
                    if len(subset) > 0:
                        label = f"{col_name}: {low} - {high}"
                        row = self._calculate_metrics(subset, label)
                        matrix_data.append(row)
        
        return pd.DataFrame(matrix_data)
    
    def _calculate_severity(self, loss_df: pd.DataFrame) -> float:
        """損失の深刻度スコアを計算 (0-100)"""
        if len(loss_df) == 0:
            return 0.0
        
        avg_loss = abs(loss_df['pnl_usd'].mean())
        frequency = len(loss_df) / len(self.df)
        
        # 損失 + 頻度 の加重平均
        severity = min(100, (avg_loss / 100) + (frequency * 50))
        return severity
    
    def _calculate_metrics(self, subset: pd.DataFrame, label: str) -> Dict:
        """サブセットのメトリクスを計算"""
        
        total = len(subset)
        wins = len(subset[subset['pnl_usd'] > 0])
        losses = len(subset[subset['pnl_usd'] < 0])
        
        win_rate = (wins / total * 100) if total > 0 else 0
        avg_pnl = subset['pnl_usd'].mean() if total > 0 else 0
        
        return {
            'condition': label,
            'total_trades': total,
            'wins': wins,
            'losses': losses,
            'win_rate_pct': win_rate,
            'avg_pnl_usd': avg_pnl,
            'total_pnl_usd': subset['pnl_usd'].sum(),
        }
    
    def generate_html_report(self, output_path: str):
        """HTML レポートを生成"""
        
        html_content = f"""
        <!DOCTYPE html>
        <html lang="ja">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>損失トレード分析レポート</title>
            <style>
                * {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }}
                body {{ margin: 20px; background: #f5f5f5; }}
                h1 {{ color: #333; border-bottom: 3px solid #007bff; padding-bottom: 10px; }}
                h2 {{ color: #555; margin-top: 30px; }}
                table {{ border-collapse: collapse; width: 100%; background: white; margin: 10px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 10px; text-align: left; }}
                th {{ background: #007bff; color: white; }}
                tr:hover {{ background: #f9f9f9; }}
                .pattern {{ background: #fff3cd; padding: 10px; margin: 10px 0; border-left: 4px solid #ff6b6b; }}
                .hypothesis {{ background: #d4edda; padding: 10px; margin: 10px 0; border-left: 4px solid #28a745; }}
                .severity-high {{ color: #ff4444; font-weight: bold; }}
                .severity-medium {{ color: #ff9933; font-weight: bold; }}
                .severity-low {{ color: #44aa44; font-weight: bold; }}
            </style>
        </head>
        <body>
            <h1>🔍 損失トレード分析レポート</h1>
            <p>生成時刻: {pd.Timestamp.now()}</p>
            
            <h2>📊 トレード統計</h2>
            <table>
                <tr>
                    <th>指標</th>
                    <th>値</th>
                </tr>
                <tr>
                    <td>総トレード数</td>
                    <td>{len(self.df)}</td>
                </tr>
                <tr>
                    <td>勝ちトレード</td>
                    <td>{len(self.df[self.df['pnl_usd'] > 0])}</td>
                </tr>
                <tr>
                    <td>負けトレード</td>
                    <td>{len(self.df[self.df['pnl_usd'] < 0])}</td>
                </tr>
                <tr>
                    <td>勝率</td>
                    <td>{len(self.df[self.df['pnl_usd'] > 0]) / len(self.df) * 100:.1f}%</td>
                </tr>
                <tr>
                    <td>総利益</td>
                    <td>{self.df['pnl_usd'].sum():.2f} USD</td>
                </tr>
            </table>
            
            <h2>⚠️ 検出された損失パターン</h2>
        """
        
        for pattern in self.loss_patterns[:10]:  # Top 10
            severity_class = self._get_severity_class(pattern.severity_score)
            html_content += f"""
            <div class="pattern">
                <h3>[{pattern.pattern_id}] {pattern.description}</h3>
                <p>
                    <strong>影響度:</strong> <span class="{severity_class}">{pattern.severity_score:.1f}/100</span><br>
                    <strong>該当トレード:</strong> {pattern.affected_trades} ({pattern.frequency_pct:.1f}%)<br>
                    <strong>平均損失:</strong> {pattern.avg_loss_usd:.2f} USD ({pattern.avg_loss_pct:.2f}%)<br>
                </p>
            </div>
            """
        
        html_content += "<h2>💡 改善仮説</h2>"
        for hyp in self.hypotheses[:10]:
            html_content += f"""
            <div class="hypothesis">
                <h3>[{hyp.hypothesis_id}] {hyp.title}</h3>
                <p>{hyp.description}</p>
                <p>
                    <strong>期待される損失削減:</strong> {hyp.expected_loss_reduction:.0f} USD<br>
                    <strong>期待される勝率向上:</strong> {hyp.expected_win_rate_improvement:.1f}%<br>
                    <strong>実装難易度:</strong> {hyp.implementation_complexity}<br>
                    <strong>リスク:</strong> {hyp.risk_level}<br>
                </p>
            </div>
            """
        
        html_content += """
        </body>
        </html>
        """
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"✓ HTML レポート生成: {output_path}")
    
    def _get_severity_class(self, score: float) -> str:
        if score >= 70:
            return 'severity-high'
        elif score >= 40:
            return 'severity-medium'
        else:
            return 'severity-low'


def main():
    """メイン処理"""
    
    csv_path = Path(__file__).parent.parent / 'analysis' / 'trades_with_metadata.csv'
    
    if not csv_path.exists():
        print(f"✗ トレード CSV が見つかりません: {csv_path}")
        print("  まず trade_extractor.py を実行してください")
        return
    
    print(f"📖 トレードデータを読み込み中: {csv_path}")
    
    analyzer = TradeAnalyzer(str(csv_path))
    
    print("\n🔍 損失パターンを特定中...")
    patterns = analyzer.identify_loss_patterns()
    
    print(f"✓ {len(patterns)} 個のパターンを検出")
    for pattern in patterns:
        print(f"  [{pattern.pattern_id}] {pattern.description}")
        print(f"      影響度: {pattern.severity_score:.1f}/100, 該当: {pattern.affected_trades} 件")
    
    print("\n💡 改善仮説を生成中...")
    hypotheses = analyzer.generate_hypotheses()
    
    print(f"✓ {len(hypotheses)} 個の仮説を提案")
    for hyp in hypotheses:
        print(f"  [{hyp.hypothesis_id}] {hyp.title}")
    
    print("\n📊 因果関係マトリックスを生成中...")
    matrix_df = analyzer.create_causality_matrix()
    
    # CSV で保存
    matrix_path = Path(__file__).parent.parent / 'analysis' / 'causality_matrix.csv'
    matrix_df.to_csv(matrix_path, index=False, encoding='utf-8')
    print(f"✓ マトリックス保存: {matrix_path}")
    
    # HTML レポート生成
    html_path = Path(__file__).parent.parent / 'analysis' / 'loss_trade_analysis_report.html'
    analyzer.generate_html_report(str(html_path))


if __name__ == '__main__':
    main()
