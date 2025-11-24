# ドキュメント管理ガイドライン

**最終更新**: 2025-11-24 22:30 JST  
**目的**: docs/ と work_reports/ の役割分離

---

## 📂 フォルダ構成の原則

### ✅ **docs/** フォルダ（永続管理）

**役割**: プロジェクトの公式ドキュメント（常に最新状態）

| ファイル | 更新頻度 | 削除 | 用途 |
|---------|---------|------|------|
| README.md | 月1回 | ❌ | ドキュメントガイド |
| ARCHITECTURE_OVERVIEW.md | 6ヶ月ごと | ❌ | システム設計書 |
| TRADING_STRATEGY_PLAN.md | 月1回 | ❌ | 戦略方針・成果 |
| ACTION_LIST.md | 週1回 | ❌ | 実行タスク一覧 |
| analysis/market_analysis.md | 毎週日曜 | ❌ | 市場環境分析 |
| analysis/strategy_performance.md | 毎日 | ❌ | パフォーマンス指標 |
| analysis/deployment_readiness.md | 必要時 | ❌ | 本番導入準備 |
| _archive/ | （参考用） | ❌ | 過去の分析ドキュメント |

**原則**:
- 常に最新の情報を保持
- 作業中に**読む対象**（参考に使用）
- **新しいレポート・一時ファイルは作成しない**

---

### ⏳ **work_reports/** フォルダ（一時管理）

**役割**: 作業進行中の一時レポート（作業完了後に削除可）

| ファイル種 | 保有期間 | 削除 | 用途 |
|-----------|---------|------|------|
| 実行レポート | 1日-1週間 | ✅ | バックテスト結果・実行ログ |
| 分析ノート | 1日-1週間 | ✅ | 作業中の考察・メモ |
| チェックリスト | 1日-1週間 | ✅ | 作業進捗追跡 |
| テスト結果 | 1日 | ✅ | デバッグ・検証結果 |
| 一時的なレポート | 1日-3日 | ✅ | COMPLETION_SUMMARY等 |

**原則**:
- 作業完了後は**削除して良い**
- docs/ に統合する情報だけ抽出して移行
- スペース節約のため不要な古いファイルは削除

---

## 🔄 ワークフロー

### パターン1: バックテスト実行 → ドキュメント更新

```
1. バックテスト実行
   ↓
2. 結果を work_reports/backtest_result_YYYYMMDD_HHMMSS.md に出力
   ↓
3. 結果を分析
   ↓
4. docs/analysis/strategy_performance.md に有意な情報を統合
   ↓
5. work_reports/ 内の一時ファイルは削除（必要に応じて）
```

### パターン2: 改善案提案 → テスト → ドキュメント更新

```
1. 改善案を ACTION_LIST.md に追加（docs/）
   ↓
2. 改善案の実装・テストを実施
   ↓
3. テスト結果を work_reports/improvement_test_YYYYMMDD.md に記録
   ↓
4. 結果を分析
   ↓
5. TRADING_STRATEGY_PLAN.md に結論を統合（docs/）
   ↓
6. work_reports/ の一時ファイルは削除
```

### パターン3: 本番導入前確認

```
1. ACTION_LIST.md の「本番導入チェックリスト」を確認（docs/）
   ↓
2. チェックリスト実施中の詳細ログを work_reports/deployment_checklist_YYYYMMDD.md に記録
   ↓
3. deployment_readiness.md を更新（docs/analysis/）
   ↓
4. チェックリスト完了後、work_reports/ の詳細ログは削除
```

---

## 📋 具体例

### ❌ **してはいけないこと**

```
docs/COMPLETION_SUMMARY.md  ← 作業レポート（一時的）
docs/TEST_RESULT_2025-11-24.md  ← テスト結果（一時的）
docs/BACKTEST_LOG_IMPROVEMENT1.md  ← 改善案のログ（一時的）
docs/MEETING_NOTES_20251124.md  ← 会議メモ（一時的）
```

**問題**: docs/ が一時ファイルで膨らみ、永続ドキュメントが埋もれる

---

### ✅ **すべきこと**

```
docs/
├─ README.md（ガイド）
├─ ARCHITECTURE_OVERVIEW.md（設計書）
├─ TRADING_STRATEGY_PLAN.md（戦略＆成果）
├─ ACTION_LIST.md（タスク）
├─ analysis/
│  ├─ market_analysis.md（市場分析・最新）
│  ├─ strategy_performance.md（パフォーマンス・最新）
│  ├─ deployment_readiness.md（導入準備・最新）
│  └─ _archive/（過去分析）
└─ _archive/（過去ドキュメント）

work_reports/（作業中のみ）
├─ backtest_result_20251124_153000.md（テスト結果）
├─ improvement_test_20251124.md（改善案検証）
└─ deployment_checklist_20251124.md（導入確認）
```

**メリット**:
- docs/ は常にクリーンで最新
- work_reports/ は一時的な作業スペース
- 必要な情報だけ docs/ に統合

---

## 🔍 docs/ ファイル読み込みルール

作業開始前に以下を確認してください:

### 毎回確認（5分）
- [ ] README.md で目的確認
- [ ] ACTION_LIST.md で実行タスク確認

### 環境判定が必要な場合（10分）
- [ ] analysis/market_analysis.md で直近環境確認
- [ ] analysis/strategy_performance.md で直近パフォーマンス確認

### 改善案提案の場合（15分）
- [ ] TRADING_STRATEGY_PLAN.md で過去の改善案と結果確認
- [ ] _archive/ で詳細技術情報確認（必要時）

### 本番導入関連（20分）
- [ ] analysis/deployment_readiness.md でチェックリスト確認
- [ ] ACTION_LIST.md で推奨タスク順序確認

---

## 📝 work_reports/ ファイル作成ルール

### ファイル命名規則

```
work_reports/<作業種>_<YYYYMMDDのHHMMSS>.md

例:
- backtest_result_20251124_153000.md
- improvement_test_20251124.md
- deployment_checklist_20251124_093000.md
- analysis_note_20251124.md
```

### 必須記載項目

```markdown
# <作業内容>

**作業日**: 2025-11-24 15:30  
**目的**: <何を確認・検証したか>  
**結果**: <簡潔な結論>

---

## 詳細

<詳細内容>

---

**作成者**: <自動/手動>  
**保持期間**: <1日/1週間/次の更新まで>  
**docs/ 統合**: <統合先ドキュメント>
```

### 削除タイミング

| 条件 | タイミング |
|------|----------|
| テスト終了後 | 1日以内 |
| 分析完了後 | 完了後即座 |
| 新しいレポート作成時 | 古いバージョンは即座削除 |
| 同一種類の複数ファイル | 最新1つのみ保持 |

---

## 🚀 実装例

### 実例1: バックテスト実行

```bash
# 1. docs/ から現況を読み込み
cat docs/analysis/market_analysis.md

# 2. バックテスト実行・ログを work_reports/ に出力
python src/backtest.py > work_reports/backtest_result_20251124_143000.md

# 3. 結果を分析
cat work_reports/backtest_result_20251124_143000.md

# 4. docs/analysis/strategy_performance.md に有意な情報を統合
# （手動更新）

# 5. 一時ファイルを削除
rm work_reports/backtest_result_20251124_143000.md
```

### 実例2: 改善案提案＆検証

```bash
# 1. docs/ACTION_LIST.md で過去の改善案確認
grep -A 10 "未実施（推奨優先順）" docs/ACTION_LIST.md

# 2. 改善案1をテスト
python test_improvement1.py > work_reports/improvement_test_20251124.md

# 3. 結果を docs/TRADING_STRATEGY_PLAN.md に統合
# （手動更新）

# 4. 一時ファイルを削除
rm work_reports/improvement_test_20251124.md
```

---

## ✅ チェックリスト（毎回実施）

作業開始時:
- [ ] work_reports/ に新しいファイルを作成する必要があるか判定
- [ ] docs/ から必要な背景情報を読み込む
- [ ] ACTION_LIST.md から実施内容を確認

作業完了時:
- [ ] docs/ に有意な情報を統合した
- [ ] work_reports/ の一時ファイルを削除した
- [ ] ACTION_LIST.md のタスク状態を更新した

---

## 📌 重要ポイント

### docs/ について
- **追記は許可**: 最新情報の追記（新しいパフォーマンス結果など）
- **修正は許可**: 既存情報の更新（パラメータ変更など）
- **削除は禁止**: 情報は常に蓄積（古い情報は _archive/ へ）
- **一時ファイルは禁止**: 作業レポートは work_reports/ へ

### work_reports/ について
- **何でも OK**: テスト結果、メモ、ログ、分析ノート何でも
- **削除推奨**: 作業完了後は削除して良い
- **スペース節約**: 不要な古いファイルは定期的に削除

---

**版**: v1.0  
**効力開始**: 2025-11-24  
**対象**: すべての作業者

