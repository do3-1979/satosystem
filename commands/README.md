# Commands - プロジェクトコマンド集

このディレクトリには、satosystem gen2プロジェクトで使用する便利コマンドが格納されています。

## コマンド一覧

### 基本コマンド

#### ./commands/prj-init
プロジェクト初期化・開発ルール読み込み

```bash
./commands/prj-init
```

- DEVELOPMENT_RULES.jsonを読み込み
- 現在の進捗状況を表示
- 作業中タスクと次の優先タスクを表示

#### ./commands/prj-help
コマンド一覧とヘルプを表示

```bash
./commands/prj-help
```

- すべてのプロジェクトコマンドを表示
- 開発ツールの使い方を説明
- よく使うワークフローを提示

#### ./commands/prj-action-list
次のアクションプラン（TODO）を表示

```bash
./commands/prj-action-list
```

- ACTION_LIST.jsonのtasks.todoセクションを表示
- 進捗状況サマリーを表示
- 次のステップガイドを表示

### 分析・テストコマンド

#### ./commands/prj-load-analysis
プロジェクト分析ファイル(23+1 JSON)を読み込み

```bash
./commands/prj-load-analysis
```

- docs/analysis/README.mdを表示
- 23個のソースコード分析JSONの読み込み手順を提示

#### ./commands/prj-update-analysis
ソースコード分析ファイルの整合性チェック・更新案内

```bash
./commands/prj-update-analysis
```

- `src/*.py` と `docs/analysis/src/*.json` の対応を確認
- 更新必要/未分析ファイルを一覧表示
- 手動更新の手順を案内（分析JSONの再生成はAI依頼）

#### ./commands/prj-run-regression
レグレッションテストスイート実行

```bash
./commands/prj-run-regression
```

- 3段階テスト実行:
  1. run_quarterly_backtest.py
  2. regression_test_suite.py
  3. backtest_and_visualize.sh
- 結果サマリー表示
- グラフファイル検証

#### ./commands/prj-test-update
テストスイート自動更新・実行

```bash
./commands/prj-test-update
```

- `src/*.py` と `test/test_*_regression.py` の対応を確認
- “テスト未作成”モジュールを表示
- `test/regression_test_suite.py` を実行

## 使い方

### プロジェクトルートから実行

```bash
# プロジェクトルートから
./commands/prj-init
./commands/prj-help
./commands/prj-action-list
```

### PATH環境変数に追加（オプション）

```bash
# ~/.bashrc または ~/.zshrc に追加
export PATH="$PATH:$HOME/work/satosystem/commands"

# その後は直接実行可能
prj-init
prj-help
prj-action-list
```

### エイリアス設定（オプション）

```bash
# ~/.bashrc または ~/.zshrc に追加
alias prj-init="./commands/prj-init"
alias prj-help="./commands/prj-help"
alias prj-action-list="./commands/prj-action-list"
alias prj-load-analysis="./commands/prj-load-analysis"
alias prj-update-analysis="./commands/prj-update-analysis"
alias prj-run-regression="./commands/prj-run-regression"
alias prj-test-update="./commands/prj-test-update"
```

## 開発者向け情報

### 新しいコマンドの追加

1. commands/ディレクトリに新しいスクリプトを作成
2. 実行権限を付与: `chmod +x commands/prj-<name>`
3. このREADME.mdに追加
4. prj-helpを更新

### コマンド命名規則

- プレフィックス: `prj-`
- 小文字とハイフンのみ使用
- 動詞を含む説明的な名前

例:
- `prj-init` - 初期化
- `prj-help` - ヘルプ表示
- `prj-action-list` - アクション一覧
- `prj-run-regression` - レグレッション実行

## 関連ドキュメント

- [DEVELOPMENT_RULES.json](../DEVELOPMENT_RULES.json) - 開発ルール
- [PROGRESS.json](../PROGRESS.json) - 進捗状況
- [docs/ACTION_LIST.md](../docs/ACTION_LIST.md) - タスク管理

---

最終更新: 2026-01-31
