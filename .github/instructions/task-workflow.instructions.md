---
description: タスクの開始・完了・コミット記録のワークフロースキル。「タスク開始」「タスク完了」「進捗更新」「コミット記録」を依頼されたときに使用する。
applyTo: "**"
---

# タスク管理・進捗更新ワークフロースキル

## 目的

`ACTION_LIST.json` と `PROGRESS.json` を使ってタスクの進捗を記録し、プロジェクトの状態を常に最新に保つ。

## コマンド早見表

| 操作 | コマンド |
|---|---|
| タスク開始記録 | `./commands/prj-update task-start <ID>` |
| タスク完了記録 | `./commands/prj-update task-complete <ID>` |
| コミット情報反映 | `./commands/prj-update commit` |
| 現在の状況確認 | `./commands/prj-update status` |

## タスク開始フロー

### 1. TODO確認

```bash
./commands/prj-action-list
```

### 2. 開始記録

```bash
./commands/prj-update task-start <タスクID>
```

例: `./commands/prj-update task-start 40b`

### 3. ACTION_LIST.json を手動更新

`ACTION_LIST.json` の `tasks.todo` から該当タスクを見つけ、`tasks.progress` に移動する。

```json
// tasks.progress に追加する形式
{
  "id": "40b",
  "title": "コストモデル bot 統合",
  "priority": "★★★★☆",
  "status": "in_progress",
  "started_date": "YYYY-MM-DD",
  "description": "..."
}
```

## タスク完了フロー

### 1. レグレッションテストを実行・全PASS確認

```bash
./commands/prj-run-regression
```

### 2. 完了記録

```bash
./commands/prj-update task-complete <タスクID>
```

例: `./commands/prj-update task-complete 40b`

### 3. ACTION_LIST.json を手動更新

`tasks.progress` から該当タスクを `tasks.done` に移動する。

```json
// tasks.done に追加する形式
{
  "id": "40b",
  "title": "コストモデル bot 統合",
  "completed_date": "YYYY-MM-DD",
  "description": "実装完了"
}
```

### 4. `tasks.summary` を更新

```json
"summary": {
  "todo": <件数>,
  "progress": <件数>,
  "done": <件数>
}
```

### 5. ユーザーにコミット許可を求める

変更ファイルを `git status` で確認し、ユーザーへ報告してから承認を得る。

```bash
git status
git diff --stat
```

### 6. コミット後にPROGRESS.json を更新

```bash
./commands/prj-update commit
```

## コミットメッセージ規約

```
<type>: <description>

type:
  feat     新機能追加
  fix      バグ修正
  refactor リファクタリング
  docs     ドキュメント更新
  test     テスト追加・修正
  chore    ビルド・設定変更
```

例:
```
feat: Task 40b - コストモデル bot 統合完了
fix: exit_strategy.pyのPSAR判定バグ修正
docs: ACTION_LIST更新 - Task 40b完了記録
```

## 注意事項

- **コミット・プッシュは必ずユーザー許可後に実行する**
- 複数の変更を一度にコミットしない（ファイルごと・機能ごとに分割）
- テスト未実施の状態でプッシュしない

## ACTION_LIST.json の構造

```json
{
  "summary": { "todo": N, "progress": N, "done": N },
  "tasks": {
    "todo": [ { "id": "...", "title": "...", "priority": N, ... } ],
    "progress": [ { "id": "...", "title": "...", "status": "in_progress", ... } ],
    "done": [ { "id": "...", "title": "...", "completed_date": "YYYY-MM-DD", ... } ]
  }
}
```

優先度は `1〜5` の数値（大きいほど高優先度）または `★` 記号で表す。
