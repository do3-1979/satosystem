#!/usr/bin/env python3
"""
四半期別バックテスト実施ガイド
2025-11-26 実装

【概要】
修正したストップロス計算（stop_range調整）が各期間・パターンでどのような影響を与えるか定量的に評価
"""

# ===========================================================================
# 実装内容
# ===========================================================================
"""
1. quarterly_backtest_2024_2025.py
   - 2024 Q1～Q4、2025 Q1～Q3 (8期間) × 4パターンのバックテスト設定生成
   - 4パターン:
     * baseline_old: Phase 1 OFF, stop_range=2.0（修正前・ベースライン）
     * baseline_new: Phase 1 OFF, stop_range=4.0（ストップのみ改善）
     * phase1_old: Phase 1 ON, stop_range=2.0（Phase 1のみ効果）
     * phase1_new: Phase 1 ON, stop_range=4.0（両方改善）
   
   - 期待される分析結果:
     * stop_range 修正の全期間への影響度
     * Phase 1 の有効性の再評価
     * Q別の戦略効果の差異

2. quarterly_backtest_scheduler.py
   - 優先度指定で効率的に実行
   - 優先度 HIGH (5期間):
     * 2024 Q1, Q2, Q3
     * 2025 Q1, Q3
   - 優先度 MEDIUM (2期間):
     * 2024 Q4, 2025 Q2
   
   - 実行進捗を JSON で保存
   - 中断・再開時の状態管理

3. test/run_all_checks.py
   - レポート出力先を work_reports/YYYY-MM-DD/ に統一
   - ドキュメント管理ルール（docs/README.md）に準拠

4. docs/ACTION_LIST.md
   - 四半期バックテスト計画を記載
   - 実行方法・期待結果を記載
"""

# ===========================================================================
# 実行手順
# ===========================================================================
"""
【ステップ1】コンフィグファイルの生成（確認済み）
  $ cd /home/satoshi/work/satosystem
  $ ls -la output_configs/quarterly_* | wc -l
  → 28 ファイル生成確認（8期間 × 4パターン - 4ファイルが既存）

【ステップ2】優先度 HIGH で実行（推奨）
  $ python3 quarterly_backtest_scheduler.py --priority high
  
  実行対象:
  - 2024 Q1 (4 パターン) → 2024 Q2 → 2024 Q3 → 2025 Q1 → 2025 Q3
  - 計 20 バックテスト
  - 推定時間: 3～5 時間

【ステップ3】結果確認
  $ ls -la work_reports/YYYY-MM-DD/quarterly_backtest_*.json
  → 日付別ディレクトリに結果が保存
  
  JSON フォーマット:
  {
    "2024_Q1": {
      "baseline_old": {"pnl": -100, "trades": 40, "win_rate": 45.0, ...},
      "baseline_new": {"pnl": -50, "trades": 50, "win_rate": 48.0, ...},
      "phase1_old": {...},
      "phase1_new": {...}
    },
    ...
  }

【ステップ4】全期間で実行（オプション）
  $ python3 quarterly_backtest_scheduler.py --priority all
  
  実行対象: 8期間 × 4パターン = 32 バックテスト
  推定時間: 8～12 時間
"""

# ===========================================================================
# 期待される分析結果
# ===========================================================================
"""
【stop_range 修正の影響（baseline_old vs baseline_new）】

成功シナリオ:
- PnL が改善（特に Q2/Q3）
- トレード数の減少なし（または減少が軽微）
- Win Rate の向上

失敗シナリオ:
- PnL 悪化が続く
- トレード数が大幅減少
- stop_range=4.0 でも不十分

【Phase 1 の有効性再評価（baseline_old vs phase1_old）】

効果がある場合:
- STRONG_TREND時のトレード選別で PnL 向上
- Q別の効果差異が明確

効果がない場合:
- PnL 大幅悪化（レジーム判定ミス）
- Phase 1 導入延期を検討

【両方の改善（phase1_new）】

最適シナリオ:
- stop_range と Phase 1 の相乗効果で PnL 向上
- 2024 年の赤字基調が改善
- 2025 年後期でも安定パフォーマンス
"""

# ===========================================================================
# 実装の検証（2025-11-26 完了）
# ===========================================================================
"""
✅ quarterly_backtest_2024_2025.py
   - 構文検証: OK
   - コンフィグ生成: 28/28 完了
   - 期間形式: YYYY/MM/DD HH:MM 統一
   - stop_range パラメータ: 2.0, 4.0 で設定

✅ quarterly_backtest_scheduler.py
   - 優先度指定: --priority {high, medium, all}
   - 進捗保存: JSON 形式
   - レポート出力: work_reports/YYYY-MM-DD/

✅ ドキュメント管理
   - docs/README.md: ドキュメント管理ルール記載
   - test/README.md: レポート出力先を日付ディレクトリに統一
   - ACTION_LIST.md: 四半期バックテスト計画記載

✅ テスト体制
   - test/run_all_checks.py: 日付ディレクトリへの自動保存実装
   - test/sample_test_runner.py: 同上
   - test/test_config.py: ドキュメント管理構造検証テスト追加
"""

# ===========================================================================
# 次のステップ
# ===========================================================================
"""
1. 優先度 HIGH で実行 → 結果確認（推定: 3～5時間）
2. 結果分析:
   - stop_range=4.0 での改善度
   - Phase 1 の有効性判定
   - Q別の傾向分析
3. 改善方針決定:
   - stop_range 最適値（4.0 or 6.0 or その他）
   - Phase 1 導入判定（ON/OFF）
   - Phase 2 段階的フィルタリングとの組み合わせ
4. ACTION_LIST.md に結果を記載
5. 本番導入方針の確定
"""

if __name__ == '__main__':
    print(__doc__)
