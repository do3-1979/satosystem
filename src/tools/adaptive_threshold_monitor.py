#!/usr/bin/env python3
"""適応型分類閾値モニター: 四半期ごとの自動最適化とアラート

Usage:
  python tools/adaptive_threshold_monitor.py --check
  python tools/adaptive_threshold_monitor.py --apply-recommendations

機能:
  1. 最新のtrend_tradesを自動検出
  2. dynamic_classification_optimizerを実行
  3. ドリフト検出時に自動アラート
  4. --apply-recommendationsで config.ini を自動更新
  5. 月次/四半期レポート生成
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional


class AdaptiveThresholdMonitor:
    """適応型分類閾値モニタリングシステム"""
    
    def __init__(self, src_root: Path):
        self.src_root = Path(src_root)
        self.report_dir = self.src_root / 'report'
        self.tools_dir = self.src_root / 'tools'
        self.config_path = self.src_root / 'config.ini'
        
    def find_latest_trend_trades(self) -> Optional[Path]:
        """最新のtrend_trades JSONを検索"""
        trade_files = sorted(self.report_dir.glob('trend_trades_*.json'), reverse=True)
        if not trade_files:
            print("⚠️ trend_trades ファイルが見つかりません")
            return None
        return trade_files[0]
    
    def get_current_thresholds(self) -> Dict[str, float]:
        """config.iniから現在のk2, k3を読み取り"""
        k2, k3 = 2.2, 1.6  # デフォルト値
        
        if not self.config_path.exists():
            return {'k2': k2, 'k3': k3}
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip().startswith('classification_k2'):
                    k2 = float(line.split('=')[1].strip())
                elif line.strip().startswith('classification_k3'):
                    k3 = float(line.split('=')[1].strip())
        
        return {'k2': k2, 'k3': k3}
    
    def run_optimizer(self, trade_file: Path, current_thresholds: Dict) -> Dict:
        """dynamic_classification_optimizerを実行"""
        output_json = self.report_dir / f'classification_drift_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        
        cmd = [
            sys.executable,
            str(self.tools_dir / 'dynamic_classification_optimizer.py'),
            '--input', str(trade_file),
            '--output', str(output_json),
            '--current-k2', str(current_thresholds['k2']),
            '--current-k3', str(current_thresholds['k3']),
            '--drift-threshold', '15.0'
        ]
        
        print(f"🔍 分類最適化実行中...")
        print(f"   入力: {trade_file.name}")
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"❌ 最適化実行エラー:\n{result.stderr}")
            return {}
        
        # 結果読み込み
        with open(output_json, 'r', encoding='utf-8') as f:
            analysis = json.load(f)
        
        return analysis
    
    def check_and_alert(self) -> Dict:
        """チェック実行とアラート"""
        print("=" * 70)
        print("適応型分類閾値モニター: チェック実行")
        print("=" * 70)
        
        # 1. 最新データ検索
        trade_file = self.find_latest_trend_trades()
        if not trade_file:
            return {}
        
        print(f"\n✅ 最新トレードデータ: {trade_file.name}")
        
        # 2. 現在の閾値取得
        current = self.get_current_thresholds()
        print(f"   現在の設定: k2={current['k2']}, k3={current['k3']}")
        
        # 3. 最適化実行
        analysis = self.run_optimizer(trade_file, current)
        
        if not analysis:
            return {}
        
        # 4. 結果表示
        drift = analysis.get('drift_detection', {})
        rec = analysis.get('recommendation', {})
        
        print("\n" + "=" * 70)
        print("📊 分析結果")
        print("=" * 70)
        print(f"トレード数: {analysis.get('total_trades', 0)}")
        print(f"\n【推奨閾値】")
        print(f"  k2: {rec.get('k2', 0):.1f} (現在: {current['k2']})")
        print(f"  k3: {rec.get('k3', 0):.1f} (現在: {current['k3']})")
        print(f"\n【ドリフト】")
        print(f"  k2乖離: {drift.get('drift', {}).get('k2_pct', 0):.1f}%")
        print(f"  k3乖離: {drift.get('drift', {}).get('k3_pct', 0):.1f}%")
        print(f"\n【判定】 {drift.get('message', '')}")
        
        if drift.get('alert', False):
            print("\n⚠️⚠️⚠️ 再最適化推奨 ⚠️⚠️⚠️")
            print("\n次のコマンドで設定を適用:")
            print(f"  python tools/adaptive_threshold_monitor.py --apply-recommendations")
        else:
            print("\n✅ 現在の閾値は適切です")
        
        print("=" * 70)
        
        return analysis
    
    def apply_recommendations(self, analysis: Dict) -> bool:
        """推奨値をconfig.iniに適用"""
        if not analysis:
            print("⚠️ 分析データがありません。先に --check を実行してください")
            return False
        
        rec = analysis.get('recommendation', {})
        k2_new = rec.get('k2', 2.2)
        k3_new = rec.get('k3', 1.6)
        
        print(f"\n📝 config.ini を更新中...")
        print(f"   k2: {k2_new:.1f}")
        print(f"   k3: {k3_new:.1f}")
        
        # config.ini読み込み
        with open(self.config_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # k2, k3を更新
        updated_lines = []
        for line in lines:
            if line.strip().startswith('classification_k2'):
                updated_lines.append(f'classification_k2 = {k2_new:.1f}\n')
            elif line.strip().startswith('classification_k3'):
                updated_lines.append(f'classification_k3 = {k3_new:.1f}\n')
            else:
                updated_lines.append(line)
        
        # バックアップ
        backup_path = self.config_path.with_suffix('.ini.backup_threshold')
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        print(f"   バックアップ: {backup_path.name}")
        
        # 書き込み
        with open(self.config_path, 'w', encoding='utf-8') as f:
            f.writelines(updated_lines)
        
        print(f"✅ config.ini 更新完了")
        
        return True
    
    def generate_quarterly_report(self) -> Path:
        """四半期レポート生成"""
        # 過去3ヶ月のdrift分析を集約
        drift_files = sorted(self.report_dir.glob('classification_drift_*.json'), reverse=True)
        recent_drifts = drift_files[:12]  # 直近12回分
        
        report_path = self.report_dir / f'threshold_quarterly_report_{datetime.now().strftime("%Y%m%d")}.md'
        
        with open(report_path, 'w', encoding='utf-8') as md:
            md.write("# 適応型分類閾値 - 四半期レポート\n\n")
            md.write(f"**生成日時**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            md.write("## 直近の推奨値推移\n\n")
            md.write("| 日時 | トレード数 | 推奨k2 | 推奨k3 | ドリフト警告 |\n")
            md.write("|------|-----------|--------|--------|-------------|\n")
            
            for drift_file in recent_drifts:
                with open(drift_file, 'r') as f:
                    data = json.load(f)
                
                timestamp = data.get('timestamp', '')
                total = data.get('total_trades', 0)
                rec = data.get('recommendation', {})
                drift = data.get('drift_detection', {})
                alert = '⚠️' if drift.get('alert', False) else '✅'
                
                md.write(f"| {timestamp} | {total} | {rec.get('k2', 0):.1f} | {rec.get('k3', 0):.1f} | {alert} |\n")
            
            md.write("\n## 推奨アクション\n\n")
            md.write("- 四半期ごとに `--check` を実行\n")
            md.write("- ドリフト警告時は `--apply-recommendations` で更新\n")
            md.write("- バックテストで新閾値の効果を検証\n\n")
        
        print(f"📄 四半期レポート生成: {report_path.name}")
        return report_path


def main():
    parser = argparse.ArgumentParser(description="適応型分類閾値モニター")
    parser.add_argument('--check', action='store_true',
                        help='最新データで閾値チェックを実行')
    parser.add_argument('--apply-recommendations', action='store_true',
                        help='推奨値をconfig.iniに適用')
    parser.add_argument('--quarterly-report', action='store_true',
                        help='四半期レポートを生成')
    parser.add_argument('--src-root', type=str, default='.',
                        help='srcディレクトリのルートパス')
    args = parser.parse_args()
    
    monitor = AdaptiveThresholdMonitor(Path(args.src_root))
    
    if args.check:
        analysis = monitor.check_and_alert()
        
        # 分析結果を一時保存（apply用）
        temp_analysis_path = monitor.report_dir / '.latest_analysis.json'
        with open(temp_analysis_path, 'w') as f:
            json.dump(analysis, f)
    
    elif args.apply_recommendations:
        # 最新の分析結果を読み込み
        temp_analysis_path = monitor.report_dir / '.latest_analysis.json'
        if not temp_analysis_path.exists():
            print("⚠️ 先に --check を実行してください")
            sys.exit(1)
        
        with open(temp_analysis_path, 'r') as f:
            analysis = json.load(f)
        
        if monitor.apply_recommendations(analysis):
            print("\n✅ 適用完了。次のステップ:")
            print("  1. バックテストで効果を検証")
            print("  2. 問題なければコミット")
    
    elif args.quarterly_report:
        monitor.generate_quarterly_report()
    
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
