# DEVELOPMENT RULES

このプロジェクトでは、すべての開発作業において下記ルールを厳守し、ドキュメントと実装の齟齬をなくします。

## ドキュメント管理の前提
1. `docs` フォルダ配下に以下のファイルを必ず保持する。
   - `DEVELOPMENT_RULES.md`: 本ルールを収録し、すべてのメンバーが参照する。
   - `ARCHITECTURE_OVERVIEW.md`: プロジェクト全体の概要および主要コンポーネントの役割を記述。
   - `ACTION_LIST.md`: TODO / PROGRESS / DONE のセクションを含み、作業課題と進捗を常に更新する。
2. 設計変更を伴う作業では、まず上記3つのドキュメントを読み、必要であれば内容を更新してから作業を始める。
3. ソースコードを変更する前に、`docs/analysis` にある分析成果物（JSON）を読み込み、現行実装との整合性を確認する。

## 一時レポート運用
- 一時的な調査レポートや検証結果は、`report_tmp/` 以下にカテゴリ別フォルダを作成して保存する。
- `report_tmp/` は Git 管理対象外とし、不要になった報告書は随時削除する。
- 有用な情報は `ARCHITECTURE_OVERVIEW.md` に転記し、追加で対応が必要な課題は `ACTION_LIST.md` に追記する。

## 中期目標に基づく実施フロー
1. **gen2ブランチの完全な分析**：現行コードの構成と既知の不具合を明らかにし、その結果を `docs/analysis/*.json` と `ARCHITECTURE_OVERVIEW.md` に記録。
2. **課題管理**：`ACTION_LIST.md` に必要な変更・レビュー項目を記録し、優先度付きで整理。ユーザー指定の順に一件ずつ、レビュー・修正・テスト・検証を実施。
3. **マスターコミットのレビューと移植**：`nextarch`（および master 相当）のコミットを逐次レビューし、必要な修正を `gen2` に移植する前にレグレッションテストを導入・実行し、不具合が再発しないことを確認。

## テスト/品質管理
- プロジェクトの主要機能を網羅するレグレッションテストを設計し、変更を取り込む前には必ず通す。
- テスト結果は `report_tmp/` に一時保存し、まとめるべき内容は `ARCHITECTURE_OVERVIEW.md` に記載。

## コミュニケーション
- ドキュメント更新や課題追加は必ず `ACTION_LIST.md` を通じて記録し、レビューで明示的に取り上げる。進捗は `TODO → PROGRESS → DONE` のステータスで明示する。
- 設計・修正のレビュー依頼時には、`docs/analysis` の JSON を根拠資料として提示する。

---

## 実行モード管理

### 概要

satosystem は 3つの異なる実行モードをサポートしています：

| モード | back_test | hot_test_dummy_mode | 用途 | 取引 | データ |
|--------|-----------|-------------------|------|------|--------|
| **バックテスト** | 1 | 1 | 過去データで戦略検証 | ✅ ダミー | 過去 |
| **ペーパートレード** | 0 | 1 | ライブ市場で検証 | ✅ ダミー | ライブ |
| **本番取引** | 0 | 0 | 実際の取引実行 | 🚀 実取引 | ライブ |

### 設定方法

`src/config.ini` の `[Backtest]` セクションで設定：

```ini
[Backtest]
# 実行モード: 1=バックテスト, 0=ホットテスト
back_test = 1

# ホットテスト時の取引モード: 1=ダミー取引（ペーパーテスト）, 0=本番取引
hot_test_dummy_mode = 1

# バックテスト後にインタラクティブグラフを自動生成
generate_interactive_graph = 1
```

### 実行方法

```bash
# config.ini を設定後、以下いずれかで実行
bash src/bot_run.sh      # 推奨: モードに応じて自動分岐
python src/bot.py        # 直接実行
```

### ロジック

**bot_run.sh の分岐ロジック:**
- `back_test == 1` → バックテストモード（ダミー取引）
- `back_test == 0 && hot_test_dummy_mode == 1` → ペーパートレード（ダミー取引）
- `back_test == 0 && hot_test_dummy_mode == 0` → 本番取引（実取引、確認プロンプト有）

**bybit_exchange.py のダミーモード判定:**
```python
is_dummy_mode = (back_test == 1) or (back_test == 0 and hot_test_dummy_mode == 1)
```

### ログファイル

| モード | ログファイル |
|--------|------------|
| バックテスト | `src/logs/latest_backtest.log` |
| ペーパートレード | `src/logs/latest_hot_test_dummy.log` |
| 本番取引 | `src/logs/latest_hot_test_live.log` |

### 推奨フロー

1. **バックテストモード** (`back_test=1`) → 戦略開発フェーズ
2. **ペーパートレード** (`back_test=0, hot_test_dummy_mode=1`) → ライブ検証フェーズ
3. **本番取引** (`back_test=0, hot_test_dummy_mode=0`) → 運用開始フェーズ

本番取引では確認プロンプトが表示されます：
```
⚠️  WARNING: 本番取引モードで実行します。注意してください！
本当に実行しますか？ (yes/no): yes
```

---

