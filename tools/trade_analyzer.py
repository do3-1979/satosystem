#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
trade_analyzer.py

抽出したトレードメタデータを分析し、因果関係マトリックスと損失パターンを検出。

フェーズ2実装：損失トレード分析の根本原因特定
"""

import json
import csv
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
from statistics import mean, stdev, median
from datetime import datetime
import sys

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent))

from trade_extractor import Trade, EntryPoint, ExitPoint, TradeResult


@dataclass
class FilterCondition:
    """フィルター条件の集計"""
    filter_name: str
    pass_count: int  # フィルター合格したトレード数
    fail_count: int  # フィルター不合格のトレード数
    
    # フィルター合格時の成績
    pass_win_count: int
    pass_lose_count: int
    pass_win_rate: float
    pass_avg_pnl: float
    pass_pf: float  # Profit Factor
    
    # フィルター不合格時の成績
    fail_win_count: int
    fail_lose_count: int
    fail_win_rate: float
    fail_avg_pnl: float
    fail_pf: float
    
    # 効果（合格時PnLと不合格時PnLの差）
    improvement_usd: float


@dataclass
class LossPattern:
    """損失パターン"""
    pattern_id: str
    pattern_description: str
    matching_trades: List[str]  # trade_id リスト
    occurrence_count: int
    occurrence_rate: float  # 全トレードに対する割合
    
    # パターンが発生した場合の成績
    total_pnl: float
    avg_pnl: float
    worst_pnl: float
    win_rate: float


class CausalityMatrix:
    """因果関係マトリックス生成"""
    
    def __init__(self, trades: List[Trade]):
        self.trades = trades
        self.matrix: Dict[str, FilterCondition] = {}
    
    def build(self) -> Dict[str, FilterCondition]:
        """因果関係マトリックスを構築"""
        filters = [
            ('pvo_filter_pass', 'PVO Filter (>10)'),
            ('adx_filter_pass', 'ADX Filter (>=31)'),
            ('volume_filter_pass', 'Volume Filter'),
            ('volatility_filter_pass', 'Volatility Filter (<100)'),
        ]
        
        for filter_key, filter_name in filters:
            # フィルター合格/不合格でトレード分類
            pass_trades = [t for t in self.trades if getattr(t.entry, filter_key, False)]
            fail_trades = [t for t in self.trades if not getattr(t.entry, filter_key, False)]
            
            # 合格時の成績
            pass_wins = [t for t in pass_trades if t.result.pnl_usd > 0]
            pass_loses = [t for t in pass_trades if t.result.pnl_usd < 0]
            pass_win_rate = len(pass_wins) / len(pass_trades) * 100 if pass_trades else 0
            pass_avg_pnl = mean([t.result.pnl_usd for t in pass_trades]) if pass_trades else 0
            pass_pf = self._calculate_pf(pass_trades)
            
            # 不合格時の成績
            fail_wins = [t for t in fail_trades if t.result.pnl_usd > 0]
            fail_loses = [t for t in fail_trades if t.result.pnl_usd < 0]
            fail_win_rate = len(fail_wins) / len(fail_trades) * 100 if fail_trades else 0
            fail_avg_pnl = mean([t.result.pnl_usd for t in fail_trades]) if fail_trades else 0
            fail_pf = self._calculate_pf(fail_trades)
            
            # 改善効果
            improvement = pass_avg_pnl - fail_avg_pnl
            
            condition = FilterCondition(
                filter_name=filter_name,
                pass_count=len(pass_trades),
                fail_count=len(fail_trades),
                pass_win_count=len(pass_wins),
                pass_lose_count=len(pass_loses),
                pass_win_rate=pass_win_rate,
                pass_avg_pnl=pass_avg_pnl,
                pass_pf=pass_pf,
                fail_win_count=len(fail_wins),
                fail_lose_count=len(fail_loses),
                fail_win_rate=fail_win_rate,
                fail_avg_pnl=fail_avg_pnl,
                fail_pf=fail_pf,
                improvement_usd=improvement
            )
            
            self.matrix[filter_key] = condition
        
        return self.matrix
    
    def _calculate_pf(self, trades: List[Trade]) -> float:
        """Profit Factor を計算"""
        if not trades:
            return 0
        
        wins = sum(t.result.pnl_usd for t in trades if t.result.pnl_usd > 0)
        loses = abs(sum(t.result.pnl_usd for t in trades if t.result.pnl_usd < 0))
        
        if loses == 0:
            return 99.99 if wins > 0 else 0
        
        return wins / loses
    
    def print_matrix(self):
        """マトリックスをテーブル表示"""
        print("\n📊 因果関係マトリックス")
        print("=" * 120)
        print(f"{'Filter':<25} | {'Pass':<8} | {'Fail':<8} | {'Pass WR%':<10} | {'Fail WR%':<10} | {'Improvement USD':<15}")
        print("-" * 120)
        
        for condition in self.matrix.values():
            print(f"{condition.filter_name:<25} | {condition.pass_count:<8} | {condition.fail_count:<8} | "
                  f"{condition.pass_win_rate:>8.1f}% | {condition.fail_win_rate:>8.1f}% | {condition.improvement_usd:>+14.2f}")


class PatternDetector:
    """損失パターン検出"""
    
    def __init__(self, trades: List[Trade]):
        self.trades = trades
        self.patterns: List[LossPattern] = []
    
    def detect(self) -> List[LossPattern]:
        """損失パターンを検出"""
        patterns = []
        
        # パターン1: PVO信号がない時の損失
        patterns.append(self._detect_low_pvo_pattern())
        
        # パターン2: ADX が低い時の損失
        patterns.append(self._detect_low_adx_pattern())
        
        # パターン3: ドローダウンが深い時の損失
        patterns.append(self._detect_deep_drawdown_pattern())
        
        # パターン4: 短期保有での損失
        patterns.append(self._detect_short_hold_pattern())
        
        # パターン5: 連続損失パターン
        patterns.append(self._detect_consecutive_loss_pattern())
        
        self.patterns = [p for p in patterns if p is not None]
        return self.patterns
    
    def _detect_low_pvo_pattern(self) -> Optional[LossPattern]:
        """PVO値が閾値以下の場合の損失パターン"""
        matching_trades = [t for t in self.trades if t.entry.pvo_filter_value < 50 and t.result.pnl_usd < 0]
        
        if len(matching_trades) < 2:
            return None
        
        return LossPattern(
            pattern_id='low_pvo',
            pattern_description='PVO < 50 での損失（シグナル弱い）',
            matching_trades=[t.entry.timestamp for t in matching_trades],
            occurrence_count=len(matching_trades),
            occurrence_rate=len(matching_trades) / len(self.trades) * 100,
            total_pnl=sum(t.result.pnl_usd for t in matching_trades),
            avg_pnl=mean([t.result.pnl_usd for t in matching_trades]),
            worst_pnl=min([t.result.pnl_usd for t in matching_trades]),
            win_rate=len([t for t in matching_trades if t.result.pnl_usd > 0]) / len(matching_trades) * 100
        )
    
    def _detect_low_adx_pattern(self) -> Optional[LossPattern]:
        """ADX値が閾値以下の場合の損失パターン"""
        matching_trades = [t for t in self.trades if t.entry.adx_filter_value < 25 and t.result.pnl_usd < 0]
        
        if len(matching_trades) < 2:
            return None
        
        return LossPattern(
            pattern_id='low_adx',
            pattern_description='ADX < 25 での損失（トレンド弱い）',
            matching_trades=[t.entry.timestamp for t in matching_trades],
            occurrence_count=len(matching_trades),
            occurrence_rate=len(matching_trades) / len(self.trades) * 100,
            total_pnl=sum(t.result.pnl_usd for t in matching_trades),
            avg_pnl=mean([t.result.pnl_usd for t in matching_trades]),
            worst_pnl=min([t.result.pnl_usd for t in matching_trades]),
            win_rate=len([t for t in matching_trades if t.result.pnl_usd > 0]) / len(matching_trades) * 100
        )
    
    def _detect_deep_drawdown_pattern(self) -> Optional[LossPattern]:
        """深いドローダウンが発生した時の損失パターン"""
        matching_trades = [t for t in self.trades if t.result.max_drawdown_pct <= -1.0 and t.result.pnl_usd < 0]
        
        if len(matching_trades) < 2:
            return None
        
        return LossPattern(
            pattern_id='deep_drawdown',
            pattern_description='ドローダウン > 1% での損失（大きい変動）',
            matching_trades=[t.entry.timestamp for t in matching_trades],
            occurrence_count=len(matching_trades),
            occurrence_rate=len(matching_trades) / len(self.trades) * 100,
            total_pnl=sum(t.result.pnl_usd for t in matching_trades),
            avg_pnl=mean([t.result.pnl_usd for t in matching_trades]),
            worst_pnl=min([t.result.pnl_usd for t in matching_trades]),
            win_rate=len([t for t in matching_trades if t.result.pnl_usd > 0]) / len(matching_trades) * 100
        )
    
    def _detect_short_hold_pattern(self) -> Optional[LossPattern]:
        """短期保有での損失パターン"""
        matching_trades = [t for t in self.trades if t.result.bars_held <= 2 and t.result.pnl_usd < 0]
        
        if len(matching_trades) < 2:
            return None
        
        return LossPattern(
            pattern_id='short_hold',
            pattern_description='短期保有（1-2bars）での損失（タイミング悪い）',
            matching_trades=[t.entry.timestamp for t in matching_trades],
            occurrence_count=len(matching_trades),
            occurrence_rate=len(matching_trades) / len(self.trades) * 100,
            total_pnl=sum(t.result.pnl_usd for t in matching_trades),
            avg_pnl=mean([t.result.pnl_usd for t in matching_trades]),
            worst_pnl=min([t.result.pnl_usd for t in matching_trades]),
            win_rate=len([t for t in matching_trades if t.result.pnl_usd > 0]) / len(matching_trades) * 100
        )
    
    def _detect_consecutive_loss_pattern(self) -> Optional[LossPattern]:
        """連続損失パターン"""
        # 連続して3回以上損失しているトレード列を検出
        consecutive_losses = []
        current_loss_streak = []
        
        for trade in self.trades:
            if trade.result.pnl_usd < 0:
                current_loss_streak.append(trade)
            else:
                if len(current_loss_streak) >= 3:
                    consecutive_losses.extend(current_loss_streak)
                current_loss_streak = []
        
        if len(current_loss_streak) >= 3:
            consecutive_losses.extend(current_loss_streak)
        
        if not consecutive_losses:
            return None
        
        return LossPattern(
            pattern_id='consecutive_loss',
            pattern_description='連続損失パターン（3回以上連続）',
            matching_trades=[t.entry.timestamp for t in consecutive_losses],
            occurrence_count=len(consecutive_losses),
            occurrence_rate=len(consecutive_losses) / len(self.trades) * 100,
            total_pnl=sum(t.result.pnl_usd for t in consecutive_losses),
            avg_pnl=mean([t.result.pnl_usd for t in consecutive_losses]),
            worst_pnl=min([t.result.pnl_usd for t in consecutive_losses]),
            win_rate=len([t for t in consecutive_losses if t.result.pnl_usd > 0]) / len(consecutive_losses) * 100
        )
    
    def print_patterns(self):
        """損失パターンをテーブル表示"""
        print("\n🔴 損失パターン検出")
        print("=" * 100)
        
        for pattern in self.patterns:
            print(f"\n【{pattern.pattern_id.upper()}】{pattern.pattern_description}")
            print(f"  発生件数: {pattern.occurrence_count} / {len(self.trades)} ({pattern.occurrence_rate:.1f}%)")
            print(f"  累計PnL: {pattern.total_pnl:+.2f} USD")
            print(f"  平均PnL: {pattern.avg_pnl:+.2f} USD")
            print(f"  最悪PnL: {pattern.worst_pnl:+.2f} USD")
            print(f"  勝率: {pattern.win_rate:.1f}%")


class ImprovementSuggestion:
    """改善案生成"""
    
    @staticmethod
    def generate(matrix: Dict[str, FilterCondition], patterns: List[LossPattern], 
                 trades: List[Trade]) -> List[Dict]:
        """改善案を自動生成"""
        suggestions = []
        
        # 改善案1: PVO フィルター強化
        pvo_condition = matrix.get('pvo_filter_pass')
        if pvo_condition and pvo_condition.improvement_usd > 0:
            suggestions.append({
                'id': 'A1',
                'title': 'PVO 閾値引き上げ',
                'description': f'PVO > 10 → PVO > 50 に引き上げ',
                'expected_improvement_usd': pvo_condition.improvement_usd * pvo_condition.pass_count,
                'implementation_effort': 'LOW',
                'risk': 'MEDIUM',
                'impact': f'{pvo_condition.improvement_usd:.2f} USD/trade 改善',
                'notes': f'合格時勝率: {pvo_condition.pass_win_rate:.1f}% → 不合格時: {pvo_condition.fail_win_rate:.1f}%'
            })
        
        # 改善案2: ADX フィルター強化
        adx_condition = matrix.get('adx_filter_pass')
        if adx_condition and adx_condition.improvement_usd > 0:
            suggestions.append({
                'id': 'A2',
                'title': 'ADX 閾値引き上げ',
                'description': f'ADX >= 31 → ADX >= 40 に引き上げ',
                'expected_improvement_usd': adx_condition.improvement_usd * adx_condition.pass_count,
                'implementation_effort': 'LOW',
                'risk': 'MEDIUM',
                'impact': f'{adx_condition.improvement_usd:.2f} USD/trade 改善',
                'notes': f'合格時勝率: {adx_condition.pass_win_rate:.1f}% → 不合格時: {adx_condition.fail_win_rate:.1f}%'
            })
        
        # 改善案3: 低PVO時エントリー禁止
        low_pvo_pattern = next((p for p in patterns if p.pattern_id == 'low_pvo'), None)
        if low_pvo_pattern:
            suggestions.append({
                'id': 'B1',
                'title': 'PVO < 50 時のエントリー禁止',
                'description': 'PVO値が低い相場では取引をスキップ',
                'expected_improvement_usd': abs(low_pvo_pattern.total_pnl),
                'implementation_effort': 'MEDIUM',
                'risk': 'LOW',
                'impact': f'{abs(low_pvo_pattern.total_pnl):.2f} USD 損失削減',
                'notes': f'発生率: {low_pvo_pattern.occurrence_rate:.1f}%, 勝率: {low_pvo_pattern.win_rate:.1f}%'
            })
        
        # 改善案4: 低ADX時エントリー禁止
        low_adx_pattern = next((p for p in patterns if p.pattern_id == 'low_adx'), None)
        if low_adx_pattern:
            suggestions.append({
                'id': 'B2',
                'title': 'ADX < 25 時のエントリー禁止',
                'description': 'トレンドが形成されていない相場では取引をスキップ',
                'expected_improvement_usd': abs(low_adx_pattern.total_pnl),
                'implementation_effort': 'MEDIUM',
                'risk': 'LOW',
                'impact': f'{abs(low_adx_pattern.total_pnl):.2f} USD 損失削減',
                'notes': f'発生率: {low_adx_pattern.occurrence_rate:.1f}%, 勝率: {low_adx_pattern.win_rate:.1f}%'
            })
        
        # 優先度付け（期待改善額でソート）
        suggestions.sort(key=lambda x: x['expected_improvement_usd'], reverse=True)
        
        return suggestions
    
    @staticmethod
    def print_suggestions(suggestions: List[Dict]):
        """改善案をテーブル表示"""
        print("\n💡 改善案（優先度順）")
        print("=" * 130)
        print(f"{'ID':<5} | {'Title':<30} | {'Expected USD':<15} | {'Effort':<10} | {'Risk':<10} | {'Impact':<30}")
        print("-" * 130)
        
        for suggestion in suggestions:
            print(f"{suggestion['id']:<5} | {suggestion['title']:<30} | {suggestion['expected_improvement_usd']:>+14.2f} | "
                  f"{suggestion['implementation_effort']:<10} | {suggestion['risk']:<10} | {suggestion['impact']:<30}")


class TradeAnalyzer:
    """メイン分析エンジン"""
    
    def __init__(self, trades_json_path: str):
        self.trades_json_path = Path(trades_json_path)
        self.trades: List[Trade] = []
        self._load_trades()
    
    def _load_trades(self):
        """JSON から Trade オブジェクトを再構築"""
        with open(self.trades_json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        for trade_data in data.get('trades', []):
            entry_data = trade_data['entry']
            exit_data = trade_data['exit']
            result_data = trade_data['result']
            
            entry = EntryPoint(**entry_data)
            exit_point = ExitPoint(**exit_data)
            result = TradeResult(**result_data)
            
            trade = Trade(
                trade_id=trade_data['trade_id'],
                entry=entry,
                exit=exit_point,
                result=result
            )
            
            self.trades.append(trade)
    
    def analyze(self):
        """総合分析を実行"""
        print(f"\n{'='*120}")
        print(f"🔍 トレード分析開始")
        print(f"{'='*120}")
        print(f"対象トレード数: {len(self.trades)}")
        
        # 因果関係マトリックス構築
        print("\n【Step 1】因果関係マトリックス構築...")
        matrix = CausalityMatrix(self.trades)
        matrix.build()
        matrix.print_matrix()
        
        # 損失パターン検出
        print("\n【Step 2】損失パターン検出...")
        detector = PatternDetector(self.trades)
        patterns = detector.detect()
        detector.print_patterns()
        
        # 改善案生成
        print("\n【Step 3】改善案生成...")
        suggestions = ImprovementSuggestion.generate(matrix.matrix, patterns, self.trades)
        ImprovementSuggestion.print_suggestions(suggestions)
        
        # 結果を JSON 保存
        self._save_analysis_results(matrix, patterns, suggestions)
        
        return matrix, patterns, suggestions
    
    def _save_analysis_results(self, matrix: CausalityMatrix, patterns: List[LossPattern], 
                               suggestions: List[Dict]):
        """分析結果を JSON 保存"""
        output_dir = Path(__file__).parent.parent / 'docs' / 'analysis'
        output_dir.mkdir(exist_ok=True, parents=True)
        
        analysis_data = {
            'metadata': {
                'analysis_timestamp': datetime.now().isoformat(),
                'total_trades': len(self.trades),
                'source_file': str(self.trades_json_path),
            },
            'causality_matrix': [
                {
                    'filter_name': condition.filter_name,
                    'pass_count': condition.pass_count,
                    'pass_win_rate': round(condition.pass_win_rate, 2),
                    'pass_avg_pnl': round(condition.pass_avg_pnl, 2),
                    'fail_count': condition.fail_count,
                    'fail_win_rate': round(condition.fail_win_rate, 2),
                    'fail_avg_pnl': round(condition.fail_avg_pnl, 2),
                    'improvement_usd': round(condition.improvement_usd, 2),
                }
                for condition in matrix.matrix.values()
            ],
            'loss_patterns': [
                {
                    'pattern_id': pattern.pattern_id,
                    'description': pattern.pattern_description,
                    'occurrence_count': pattern.occurrence_count,
                    'occurrence_rate': round(pattern.occurrence_rate, 2),
                    'total_pnl': round(pattern.total_pnl, 2),
                    'avg_pnl': round(pattern.avg_pnl, 2),
                    'worst_pnl': round(pattern.worst_pnl, 2),
                    'win_rate': round(pattern.win_rate, 2),
                }
                for pattern in patterns
            ],
            'improvement_suggestions': suggestions
        }
        
        output_path = output_dir / 'trade_analysis_results.json'
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(analysis_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n✓ 分析結果保存: {output_path}")


def main():
    """メイン処理"""
    # 最新の抽出トレード JSON を取得
    analysis_dir = Path(__file__).parent.parent / 'docs' / 'analysis' / 'trades'
    
    if not analysis_dir.exists():
        print(f"✗ 抽出トレード JSON が見つかりません: {analysis_dir}")
        return
    
    trade_json_files = sorted(analysis_dir.glob('trades_*.json'), reverse=True)
    
    if not trade_json_files:
        print(f"✗ トレード JSON ファイルが見つかりません")
        return
    
    trades_json = trade_json_files[0]
    print(f"📖 トレードメタデータ読み込み: {trades_json.name}")
    
    try:
        analyzer = TradeAnalyzer(str(trades_json))
        analyzer.analyze()
        
        print(f"\n{'='*120}")
        print(f"✅ 分析完了")
        print(f"{'='*120}")
        
    except Exception as e:
        print(f"✗ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
