#!/usr/bin/env python3
"""順次四半期適応型バックテスト

用途:
  2024年以降の各四半期を (Q1→Q2→Q3→Q4→...) の順でバックテストし、
  四半期終了後に `trend_trades_*.json` を用いて k2/k3 推奨値を計算し、
  次四半期の classification_k2/k3 に反映します。

注意:
  現状 classification_k2/k3 は事後分類専用でエントリー/EXIT判定には未使用のため、
  適用によるPnL変化は発生しません。本スクリプトは『適応パイプラインの流れ』を確認する目的です。

Usage:
  python tools/sequential_quarterly_adaptive_backtest.py --years 2024 --src-root .
  python tools/sequential_quarterly_adaptive_backtest.py --years 2024,2025 --src-root .
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

QUARTERS = {
    'Q1': (1, 3),  # inclusive months
    'Q2': (4, 6),
    'Q3': (7, 9),
    'Q4': (10, 12)
}

class SequentialQuarterlyAdaptiveBacktest:
    def __init__(self, src_root: Path):
        self.src_root = src_root
        self.report_dir = src_root / 'report'
        self.config_path = src_root / 'config.ini'
        self.tools_dir = src_root / 'tools'
        self.baseline_k2 = 2.2
        self.baseline_k3 = 1.6

    def _write_config_period(self, start: str, end: str):
        with open(self.config_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        out = []
        for line in lines:
            if line.strip().startswith('start_time'):
                out.append(f'start_time = {start}\n')
            elif line.strip().startswith('end_time') and not line.strip().startswith('#'):
                out.append(f'end_time = {end}\n')
            else:
                out.append(line)
        with open(self.config_path, 'w', encoding='utf-8') as f:
            f.writelines(out)

    def _write_config_thresholds(self, k2: float, k3: float):
        with open(self.config_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        out = []
        for line in lines:
            if line.strip().startswith('classification_k2'):
                out.append(f'classification_k2 = {k2:.1f}\n')
            elif line.strip().startswith('classification_k3'):
                out.append(f'classification_k3 = {k3:.1f}\n')
            else:
                out.append(line)
        with open(self.config_path, 'w', encoding='utf-8') as f:
            f.writelines(out)

    def _quarter_start_end(self, year: int, quarter: str) -> Tuple[str, str]:
        m_start, m_end = QUARTERS[quarter]
        # month end day naive
        def last_day(y: int, m: int) -> int:
            if m in (1,3,5,7,8,10,12):
                return 31
            if m in (4,6,9,11):
                return 30
            return 29 if y % 4 == 0 else 28
        start = f"{year}/{m_start:02d}/01 0:00"
        end = f"{year}/{m_end:02d}/{last_day(year, m_end)} 23:59"
        return start, end

    def _run_backtest(self, label: str) -> Dict:
        print(f"[RUN] Backtest {label}")
        cmd = ['bash', 'bot_run.sh', 'run']
        r = subprocess.run(cmd, cwd=self.src_root, capture_output=True, text=True)
        if r.returncode != 0:
            print(f"  ⚠️ backtest failed: {r.stderr[:200]}")
            return {}
        summaries = sorted(self.report_dir.glob('backtest_summary_*.json'), reverse=True)
        if not summaries:
            print("  ⚠️ no summary file")
            return {}
        with open(summaries[0], 'r', encoding='utf-8') as f:
            return json.load(f)

    def _latest_trend_trades(self) -> Path | None:
        files = sorted(self.report_dir.glob('trend_trades_*.json'), reverse=True)
        return files[0] if files else None

    def _optimize_thresholds(self, input_file: Path) -> Tuple[float, float, str]:
        out_json = self.report_dir / f"adaptive_opt_{input_file.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        cmd = [
            sys.executable,
            str(self.tools_dir / 'dynamic_classification_optimizer.py'),
            '--input', str(input_file),
            '--output', str(out_json),
            '--current-k2', str(self.baseline_k2),
            '--current-k3', str(self.baseline_k3)
        ]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(f"  ⚠️ optimizer failed: {r.stderr[:200]}")
            return self.baseline_k2, self.baseline_k3, 'optimizer_error'
        with open(out_json, 'r', encoding='utf-8') as f:
            data = json.load(f)
        rec = data.get('recommendation', {})
        k2 = rec.get('k2', self.baseline_k2)
        k3 = rec.get('k3', self.baseline_k3)
        rationale = rec.get('rationale', '')
        print(f"  [OPT] recommended k2={k2:.1f}, k3={k3:.1f} | {rationale}")
        return k2, k3, rationale

    def run(self, years: List[int]) -> Dict:
        # backup config
        backup = self.config_path.with_suffix('.adaptive_seq_backup')
        backup.write_text(self.config_path.read_text(encoding='utf-8'), encoding='utf-8')
        print("="*70)
        print("Sequential Quarterly Adaptive Backtest (classification thresholds)")
        print("="*70)
        applied_k2 = self.baseline_k2
        applied_k3 = self.baseline_k3
        results: List[Dict] = []
        for year in years:
            for quarter in ['Q1','Q2','Q3','Q4']:
                start, end = self._quarter_start_end(year, quarter)
                print(f"\n{'-'*60}\n[Quarter] {year} {quarter} {start} -> {end}\nCurrent thresholds k2={applied_k2:.1f}, k3={applied_k3:.1f}")
                # apply current thresholds
                self._write_config_thresholds(applied_k2, applied_k3)
                self._write_config_period(start, end)
                summary = self._run_backtest(f"{year}_{quarter}")
                pnl = summary.get('total_pnl', 0.0)
                pf = summary.get('profit_factor', 0.0)
                trades = summary.get('trades', 0)
                # optimize for next quarter
                trend_file = self._latest_trend_trades()
                if trend_file:
                    k2_new, k3_new, rationale = self._optimize_thresholds(trend_file)
                else:
                    k2_new, k3_new, rationale = applied_k2, applied_k3, 'no_trend_file'
                results.append({
                    'year': year,
                    'quarter': quarter,
                    'period_start': start,
                    'period_end': end,
                    'pnl': pnl,
                    'profit_factor': pf,
                    'trades': trades,
                    'k2_used': applied_k2,
                    'k3_used': applied_k3,
                    'k2_next': k2_new,
                    'k3_next': k3_new,
                    'rationale': rationale
                })
                applied_k2, applied_k3 = k2_new, k3_new  # carry forward
        # restore config
        self.config_path.write_text(backup.read_text(encoding='utf-8'), encoding='utf-8')
        print("\n[RESTORE] config.ini restored")
        return {'runs': results}

    def save(self, data: Dict):
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        out_json = self.report_dir / f'seq_quarterly_adaptive_{ts}.json'
        out_md = out_json.with_suffix('.md')
        with open(out_json, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        with open(out_md, 'w', encoding='utf-8') as md:
            md.write('# 順次四半期適応型バックテスト結果 (classification thresholds)\n\n')
            md.write(f"**生成日時**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            md.write('| 年 | Q | k2使用 | k3使用 | PnL | PF | Trades | 次k2 | 次k3 | 根拠 |\n')
            md.write('|---|---|-------|-------|-----|----|-------|------|------|------|\n')
            for r in data['runs']:
                md.write(f"| {r['year']} | {r['quarter']} | {r['k2_used']:.1f} | {r['k3_used']:.1f} | {r['pnl']:.2f} | {r['profit_factor']:.2f} | {r['trades']} | {r['k2_next']:.1f} | {r['k3_next']:.1f} | {r['rationale']} |\n")
            md.write('\n**注意**: k2/k3 は現状分析専用のため PnL へ直接影響なし。将来的にエントリー品質フィルタへ統合することで効果検証可能。\n')
        print(f"[SAVE] {out_json.name}, {out_md.name}")


def main():
    parser = argparse.ArgumentParser(description='Sequential quarterly adaptive backtest')
    parser.add_argument('--years', type=str, default='2024', help='カンマ区切り年リスト')
    parser.add_argument('--src-root', type=str, default='.', help='src ルート')
    args = parser.parse_args()
    years = [int(y.strip()) for y in args.years.split(',') if y.strip()]
    runner = SequentialQuarterlyAdaptiveBacktest(Path(args.src_root))
    data = runner.run(years)
    runner.save(data)
    print('\n✅ 完了')

if __name__ == '__main__':
    main()
