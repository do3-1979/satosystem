#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
multi_quarter_extractor.py

2024/Q1 ～ 2025/Q3 までのすべての四半期バックテストを実行し、
トレード情報を統合して抽出します。

フェーズ2拡張：複数四半期データの統合分析
"""

import os
import sys
import json
import subprocess
import glob
from pathlib import Path
from datetime import datetime
from dateutil.relativedelta import relativedelta
import time

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent))

from trade_extractor import Trade, EntryPoint, ExitPoint, TradeResult, TradeExtractor


class MultiQuarterExtractor:
    """複数四半期のバックテストトレード抽出"""
    
    def __init__(self, workspace_root: str = None):
        if workspace_root is None:
            workspace_root = str(Path(__file__).parent.parent)
        
        self.workspace_root = Path(workspace_root)
        self.src_dir = self.workspace_root / 'src'
        self.logs_dir = self.workspace_root / 'logs'
        self.config_file = self.src_dir / 'config.ini'
        
        self.all_trades: list = []
        self.quarters = []
    
    def get_quarters(self):
        """2024/Q1 から 2025/Q3 までの四半期リストを返す"""
        quarters = []
        start = datetime(2024, 1, 1)
        end = datetime(2025, 10, 1)  # 2025/Q3 まで
        
        current = start
        while current <= end:
            q = (current.month - 1) // 3 + 1
            year = current.year
            
            if not any(y == year and quarter == q for y, quarter in quarters):
                quarters.append((year, q))
            
            current += relativedelta(months=3)
        
        self.quarters = quarters
        return quarters
    
    def run_all_quarters(self):
        """すべての四半期のバックテストを実行"""
        quarters = self.get_quarters()
        
        print(f"\n{'='*80}")
        print(f"📊 複数四半期バックテスト実行開始")
        print(f"{'='*80}")
        print(f"対象四半期: 2024/Q1 ～ 2025/Q3 ({len(quarters)}四半期)")
        print()
        
        for idx, (year, q) in enumerate(quarters, 1):
            quarter_label = f"{year}/Q{q}"
            print(f"\n【{idx}/{len(quarters)}】 {quarter_label} のバックテスト実行中...")
            
            try:
                # 四半期用のバックテストログを実行
                self.run_backtest_for_quarter(year, q)
                
                # ログファイルを取得
                log_file = self._get_latest_log_file()
                if log_file:
                    print(f"  ✓ ログ取得: {log_file.name}")
                    
                    # トレード抽出
                    trades = self._extract_trades_from_log(log_file)
                    if trades:
                        print(f"  ✓ {len(trades)} トレード抽出")
                        self.all_trades.extend(trades)
                else:
                    print(f"  ⚠️  ログファイルが見つかりません")
                    
            except Exception as e:
                print(f"  ❌ エラー: {e}")
        
        print(f"\n{'='*80}")
        print(f"✅ バックテスト実行完了")
        print(f"{'='*80}")
        print(f"統合トレード数: {len(self.all_trades)}")
        
        return self.all_trades
    
    def run_backtest_for_quarter(self, year: int, q: int):
        """指定四半期のバックテストを実行"""
        # 日付計算
        start_month = (q - 1) * 3 + 1
        if q == 4:
            end_year = year + 1
            end_month = 1
            end_day = 1
            end_month_prev = 12
            end_day_prev = 31
        else:
            end_year = year
            end_month = start_month + 3
            end_month_prev = end_month - 1
            end_day_prev = 30
        
        start_str = f"{year}/{start_month:02d}/01 00:00"
        end_str = f"{year if q < 4 else end_year}/{end_month_prev if q < 4 else 12:02d}/{31 if end_month_prev in [1,3,5,7,8,10,12] else 30} 23:59"
        
        # config.ini を更新
        self._update_config_period(start_str, end_str)
        
        # バックテスト実行
        os.chdir(str(self.src_dir))
        result = subprocess.run(
            ['python3', 'bot.py'],
            capture_output=True,
            text=True,
            timeout=600
        )
        
        if result.returncode != 0:
            print(f"  ⚠️  バックテスト失敗")
            if result.stderr:
                print(f"  エラー: {result.stderr[:200]}")
        
        # 実行後の遅延（ファイル出力待ち）
        time.sleep(2)
    
    def _update_config_period(self, start_str: str, end_str: str):
        """config.ini の [Period] セクションを更新"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            new_lines = []
            in_period = False
            
            for line in lines:
                if '[Period]' in line:
                    in_period = True
                    new_lines.append(line)
                elif line.strip().startswith('[') and in_period:
                    in_period = False
                    new_lines.append(line)
                elif in_period and 'start_time' in line:
                    new_lines.append(f"start_time = {start_str}\n")
                elif in_period and 'end_time' in line:
                    new_lines.append(f"end_time = {end_str}\n")
                else:
                    new_lines.append(line)
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
        
        except Exception as e:
            print(f"  ⚠️  config.ini 更新失敗: {e}")
    
    def _get_latest_log_file(self):
        """最新のログファイルを取得"""
        try:
            log_files = list(self.logs_dir.glob('*.json'))
            if log_files:
                # backtest_summary_*.json を優先
                summary_logs = [f for f in log_files if 'summary' in f.name]
                if summary_logs:
                    return max(summary_logs, key=lambda x: x.stat().st_mtime)
                return max(log_files, key=lambda x: x.stat().st_mtime)
        except:
            pass
        return None
    
    def _extract_trades_from_log(self, log_file: Path):
        """ログファイルからトレードを抽出"""
        try:
            extractor = TradeExtractor(str(log_file))
            trades = extractor.extract_trades()
            return trades
        except Exception as e:
            print(f"  ⚠️  トレード抽出失敗: {e}")
            return []
    
    def save_aggregated_trades(self, output_path: str = None):
        """統合トレードを JSON/CSV で保存"""
        if not output_path:
            output_dir = self.workspace_root / 'docs' / 'analysis' / 'trades'
            output_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            output_path = str(output_dir / f'trades_all_quarters_{timestamp}')
        
        output_path = Path(output_path)
        
        # JSON で保存
        trades_data = {
            'metadata': {
                'total_trades': len(self.all_trades),
                'quarters_analyzed': f"2024/Q1 - 2025/Q3 ({len(self.quarters)} quarters)",
                'extraction_timestamp': datetime.now().isoformat(),
            },
            'trades': [
                {
                    'trade_id': t.trade_id,
                    'entry': json.loads(json.dumps({
                        k: v for k, v in t.entry.__dict__.items()
                    })),
                    'exit': json.loads(json.dumps({
                        k: v for k, v in t.exit.__dict__.items()
                    })),
                    'result': json.loads(json.dumps({
                        k: v for k, v in t.result.__dict__.items()
                    })),
                }
                for t in self.all_trades
            ]
        }
        
        json_path = f"{output_path}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(trades_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n✓ JSON 保存: {json_path}")
        
        # CSV で保存
        csv_path = f"{output_path}.csv"
        import csv
        
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            if self.all_trades:
                fieldnames = [
                    'trade_id', 'entry_timestamp', 'entry_side', 'entry_price',
                    'exit_timestamp', 'exit_price', 'exit_reason',
                    'pnl_usd', 'pnl_pct', 'max_drawdown_usd', 'max_drawdown_pct',
                    'duration_minutes', 'bars_held',
                    'donchian_signal', 'pvo_signal', 'adx_value', 'pvo_value',
                    'market_regime'
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                
                for trade in self.all_trades:
                    writer.writerow({
                        'trade_id': trade.trade_id,
                        'entry_timestamp': trade.entry.timestamp,
                        'entry_side': trade.entry.side,
                        'entry_price': f"{trade.entry.price:.2f}",
                        'exit_timestamp': trade.exit.timestamp,
                        'exit_price': f"{trade.exit.price:.2f}",
                        'exit_reason': trade.exit.reason,
                        'pnl_usd': f"{trade.result.pnl_usd:+.2f}",
                        'pnl_pct': f"{trade.result.pnl_pct:+.2f}%",
                        'max_drawdown_usd': f"{trade.result.max_drawdown_usd:+.2f}",
                        'max_drawdown_pct': f"{trade.result.max_drawdown_pct:+.2f}%",
                        'duration_minutes': trade.result.duration_minutes,
                        'bars_held': trade.result.bars_held,
                        'donchian_signal': trade.entry.donchian_signal,
                        'pvo_signal': trade.entry.pvo_signal,
                        'adx_value': f"{trade.entry.adx_filter_value:.1f}",
                        'pvo_value': f"{trade.entry.pvo_filter_value:.1f}",
                        'market_regime': trade.entry.market_regime,
                    })
        
        print(f"✓ CSV 保存: {csv_path}")
        
        return json_path, csv_path
    
    def print_statistics(self):
        """トレード統計を表示"""
        if not self.all_trades:
            print("トレードが抽出されていません")
            return
        
        wins = [t for t in self.all_trades if t.result.pnl_usd > 0]
        losses = [t for t in self.all_trades if t.result.pnl_usd < 0]
        
        total_pnl = sum(t.result.pnl_usd for t in self.all_trades)
        avg_pnl = total_pnl / len(self.all_trades) if self.all_trades else 0
        avg_win = sum(t.result.pnl_usd for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t.result.pnl_usd for t in losses) / len(losses) if losses else 0
        
        win_rate = len(wins) / len(self.all_trades) * 100 if self.all_trades else 0
        
        print(f"\n📊 統合トレード統計（全四半期）")
        print(f"{'='*60}")
        print(f"  総トレード数: {len(self.all_trades)}")
        print(f"  勝ちトレード: {len(wins)}")
        print(f"  負けトレード: {len(losses)}")
        print(f"  勝率: {win_rate:.1f}%")
        print(f"  総利益: {total_pnl:+.2f} USD")
        print(f"  平均利益: {avg_pnl:+.2f} USD")
        print(f"  平均勝利: {avg_win:+.2f} USD")
        print(f"  平均損失: {avg_loss:+.2f} USD")
        
        if losses:
            pf = sum(t.result.pnl_usd for t in wins) / abs(sum(t.result.pnl_usd for t in losses))
            print(f"  Profit Factor: {pf:.2f}")


def main():
    """メイン処理"""
    print("\n🔄 複数四半期バックテストトレード抽出ツール")
    print("="*80)
    
    extractor = MultiQuarterExtractor()
    
    # すべての四半期を実行
    trades = extractor.run_all_quarters()
    
    # 統計表示
    extractor.print_statistics()
    
    # 結果保存
    if trades:
        json_path, csv_path = extractor.save_aggregated_trades()
        print(f"\n✅ 抽出完了: {len(trades)} トレード")
        print(f"   JSON: {json_path}")
        print(f"   CSV: {csv_path}")
    else:
        print(f"\n⚠️  トレードが抽出されませんでした")


if __name__ == '__main__':
    main()
