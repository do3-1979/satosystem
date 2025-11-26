# Task 18: Phase 3 スケジューラ統合 - Cron 設定ドキュメント

**作成日**: 2025-11-26  
**ステータス**: ✅ 完了  
**優先度**: H (High)  
**期限**: 1週間以内  

---

## 概要

Phase 3 では、Task 7（環境自動判定）、Task 10（動的基準学習）、Task 11（パフォーマンス監視）を Linux cron スケジューラで定期実行し、システムの自動化を実現します。

## 実装内容

### 1. Cron スケジュール設定

| タスク | スクリプト | 実行時刻 | 頻度 | 用途 |
|--------|-----------|--------|------|------|
| **Task 11** | `src/realtime_performance_monitor.py` | 00:00 UTC | 毎日 | 日次パフォーマンス監視（PnL/勝率/Sharpe比など） |
| **Task 7** | `src/environment_auto_judge.py` | 00:00 UTC | 毎週月曜日 | 過去30日のレジーム分析 → Phase 2 適用判定 |
| **Task 10** | `src/dynamic_threshold_learning.py` | 00:00 UTC | 毎月1日 | 過去30日データから最適閾値を動的学習 |

### 2. Crontab エントリ

```bash
# Task 11: 毎日 00:00 UTC で実行
0 0 * * * cd /home/satoshi/work/satosystem && python3 src/realtime_performance_monitor.py >> logs/task11.log 2>&1

# Task 7: 毎週月曜日 00:00 UTC で実行
0 0 * * 1 cd /home/satoshi/work/satosystem && python3 src/environment_auto_judge.py >> logs/task7.log 2>&1

# Task 10: 毎月1日 00:00 UTC で実行
0 0 1 * * cd /home/satoshi/work/satosystem && python3 src/dynamic_threshold_learning.py >> logs/task10.log 2>&1
```

### 3. ログ構成

各タスクの実行ログは `logs/` ディレクトリに保存されます：

- `logs/task11.log` - 日次パフォーマンス監視ログ（毎日追記）
- `logs/task7.log` - 週次環境自動判定ログ（毎週月曜追記）
- `logs/task10.log` - 月次動的学習ログ（毎月1日追記）

### 4. 結果レポート

各タスクは実行結果を JSON 形式で `work_reports/` ディレクトリに保存します：

- `work_reports/realtime_monitor_YYYYMMDD_HHMMSS.json` - Task 11 レポート
- `work_reports/environment_auto_judgement_YYYYMMDD_HHMMSS.json` - Task 7 レポート
- `work_reports/dynamic_threshold_learning_YYYYMMDD_HHMMSS.json` - Task 10 レポート

## 検証結果

### ✅ スクリプト実行テスト

全タスクが正常に実行可能であることを確認：

#### Task 7: 環境自動判定
```
実行結果: ✅ 成功
出力: 環境分析レポート（レジーム分布、推奨判定）
```

#### Task 10: 動的基準学習
```
実行結果: ✅ 成功
出力: 学習レポート（最適閾値、効果予測）
```

#### Task 11: パフォーマンス監視
```
実行結果: ✅ 成功
出力: 監視レポート（PnL、勝率、アラート）
```

### ✅ Crontab 登録

crontab への登録確認：
```
$ crontab -l
# 3つのエントリが正しく登録されていることを確認
```

## 運用ガイド

### 定期チェックポイント

1. **毎日 00:05 UTC**
   - `logs/task11.log` を確認してパフォーマンスアラートをチェック

2. **毎週月曜日 00:05 UTC**
   - `logs/task7.log` を確認して環境判定結果をレビュー
   - 必要に応じて `config.ini` の `regime_detection_enabled` を調整

3. **毎月1日 00:05 UTC**
   - `logs/task10.log` を確認して学習結果をレビュー
   - 必要に応じて `config.ini` の閾値パラメータを更新

### トラブルシューティング

#### Cron ジョブが実行されない場合

1. Cron デーモンの確認
   ```bash
   service cron status
   ```

2. Crontab の確認
   ```bash
   crontab -l
   ```

3. ログファイルの確認
   ```bash
   cat /var/log/syslog | grep CRON
   ```

#### Python スクリプトの実行エラー

1. 仮想環境の確認
   ```bash
   which python3
   python3 --version
   ```

2. 必要なモジュールの確認
   ```bash
   cd /home/satoshi/work/satosystem && python3 -c "import src.environment_auto_judge"
   ```

3. スクリプトの直接実行テスト
   ```bash
   cd /home/satoshi/work/satosystem && python3 src/environment_auto_judge.py
   ```

## 次のステップ

### Task 19: 4週間ホットテスト運用
- 開始予定: 2025-11-27
- 期間: 4週間（実際パフォーマンス検証）
- 監視対象: Phase 2 の実装効果（+10.34% PnL 改善の確認）
- 使用スクリプト: `run_quarterly_backtest_simple.py` + Task 11 自動監視
- 報告頻度: 毎週金曜日（進捗レポート）

## 参考資料

- [ACTION_LIST.md](./ACTION_LIST.md) - プロジェクト全体進捗
- [ARCHITECTURE_OVERVIEW.md](./ARCHITECTURE_OVERVIEW.md) - システムアーキテクチャ
- crontab_entries.txt - Cron エントリ定義ファイル
