# PROGRESS.json - 進捗管理システム

## 概要

`PROGRESS.json`はsatosystem gen2プロジェクトの進捗状況を一元管理するファイルです。

## ファイル構造

```json
{
  "project": {           // プロジェクト基本情報
    "name": "...",
    "baseline_performance": { ... }
  },
  "latest_commit": {     // 最新コミット情報
    "hash": "...",
    "message": "..."
  },
  "current_status": {    // 現在の状態
    "active_tasks": {
      "in_progress": [], // 作業中タスク
      "next_priority": [] // 次の優先タスク
    },
    "recently_completed": [] // 最近完了したタスク（最新5件）
  },
  "documentation": { ... }, // ドキュメント情報
  "test_suite": { ... },    // テスト情報
  "configuration": { ... }, // 設定情報
  "next_actions": { ... },  // 次のアクション
  "performance_goals_2026": { ... } // 2026年目標
}
```

## 更新方法

### 1. 手動更新（直接編集）

`PROGRESS.json`を直接編集して更新します。

### 2. スクリプトによる自動更新

#### 最新コミット情報を更新

```bash
python3 tools/update_progress.py --commit
```

#### タスク完了を記録

```bash
python3 tools/update_progress.py \
  --task-complete "39b" \
  --description "Two-Tier Entry System実装完了"
```

実行結果：
- `in_progress`または`next_priority`から該当タスクを削除
- `recently_completed`に追加（最新5件のみ保持）

#### タスク開始を記録

```bash
python3 tools/update_progress.py \
  --task-start "39c" \
  --description "Multi-Timeframe Integration実装開始" \
  --priority "★★★★★"
```

実行結果：
- `next_priority`から該当タスクを削除
- `in_progress`に追加

#### 複合実行

```bash
# タスク完了 + コミット情報更新
python3 tools/update_progress.py \
  --task-complete "39b" \
  --description "Two-Tier Entry System実装完了" \
  --commit
```

## ワークフロー統合

### コミット時に自動更新

`.git/hooks/post-commit`に以下を追加（オプション）：

```bash
#!/bin/bash
python3 tools/update_progress.py --commit
```

### タスク完了時の標準フロー

1. タスク実装完了
2. レグレッションテスト実施
3. コミット実行
4. PROGRESS.json更新:
   ```bash
   python3 tools/update_progress.py \
     --task-complete "タスクID" \
     --description "完了内容" \
     --commit
   ```
5. `ACTION_LIST.json`のtasks.doneセクション更新

### タスク開始時の標準フロー

1. PROGRESS.json更新:
   ```bash
   python3 tools/update_progress.py \
     --task-start "タスクID" \
     --description "実装内容"
   ```
2. `ACTION_LIST.json`のtasks.progressセクション更新
3. 実装開始

## 使用例

### 例1: Task 39b完了

```bash
# 1. 実装完了・テスト完了
git add src/
git commit -m "feat: Task 39b - Two-Tier Entry System実装完了"

# 2. PROGRESS.json更新
python3 tools/update_progress.py \
  --task-complete "39b" \
  --description "高確度/中確度の二段階エントリー実装。バックテスト結果: +$450改善" \
  --commit

# 3. ACTION_LIST.json手動更新（tasks.doneセクション）
```

### 例2: Task 39c開始

```bash
# 1. PROGRESS.json更新
python3 tools/update_progress.py \
  --task-start "39c" \
  --description "Multi-Timeframe Integration実装開始 - 1h/4h/1d三重確認" \
  --priority "★★★★★"

# 2. ACTION_LIST.json手動更新（tasks.progressセクション）
```

### 例3: コミット情報のみ更新

```bash
# 最新コミット後に実行
python3 tools/update_progress.py --commit
```

## ファイル配置

```
satosystem/
├── PROGRESS.json              # 進捗管理ファイル（本体）
├── tools/
│   ├── update_progress.py     # 更新スクリプト
│   └── README_PROGRESS.md     # このファイル
└── docs/
    ├── ACTION_LIST.json       # タスク一覧（詳細管理）
```

## 関連ドキュメント

- `ACTION_LIST.json` - タスク詳細管理（TODO/PROGRESS/DONE）
- `DEVELOPMENT_RULES.json` - 開発ルール・ワークフロー
- `docs/ARCHITECTURE_OVERVIEW.md` - システムアーキテクチャ

## 注意事項

1. **手動編集時**：JSON形式を壊さないよう注意
2. **スクリプト使用時**：Git作業ディレクトリから実行すること
3. **コミット前**：PROGRESS.json更新後は`git add PROGRESS.json`を忘れずに
4. **ACTION_LIST.jsonとの同期**：両方を更新してプロジェクト状態を正確に保つ

## トラブルシューティング

### エラー: "PROGRESS.json が見つかりません"

プロジェクトルートから実行してください：
```bash
cd /home/satoshi/work/satosystem
python3 tools/update_progress.py --commit
```

### Git情報取得エラー

Gitリポジトリ内で実行されているか確認：
```bash
git status
```

### タスクが見つからない警告

- タスクIDが`in_progress`または`next_priority`に存在するか確認
- PROGRESS.jsonを直接編集して追加
