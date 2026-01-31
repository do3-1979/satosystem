# AI Context - プロジェクト情報

このファイルはAIアシスタントがプロジェクトを理解するための情報です。

## プロジェクト概要

- **名称**: satosystem gen2
- **説明**: Bitcoin自動取引システム（Donchian Breakout + PVO + ADX filter）
- **ブランチ**: gen2
- **ベースライン性能**: +904.35 USD（2024-2025, 8四半期）
- **最終更新**: 2026-01-31

## 重大ルール（CRITICAL）

### コミット・プッシュの許可取得
**すべてのコミットとプッシュは、ユーザーの明示的な許可を得た後にのみ実行する**

理由：
- APIキーがconfig.iniに含まれている場合、意図しないプッシュで認証情報が公開される危険性
- 修正内容がユーザー指定の要件に合致しているか、事前にレビューを受ける必要
- テスト未実施のコードが公開されることを防止

ワークフロー：
1. 修正作業完了時 → `git status`で変更ファイルを確認し、ユーザーに報告
2. コミット前の確認 → 変更内容の要約、テスト結果などを提示し、ユーザーから「OK」を得る
3. プッシュ前の確認 → コミットメッセージがユーザーの意図に合致しているか確認を得る
4. 実行 → ユーザーの明示的な指示を受けて、初めてコミット・プッシュを実行

### 禁止事項
1. ❌ ユーザーの許可なくコミットすること
2. ❌ 複数の変更を一度にコミット・プッシュすること（ファイルごと、機能ごとに分割）
3. ❌ テスト未実施の状態でプッシュすること
4. ❌ APIキーがconfig.iniに含まれた状態でプッシュすること

## 必須ドキュメント

作業前に以下を確認：
- `docs/ACTION_LIST.md` - タスク管理（TODO/PROGRESS/DONE）
- `docs/DEVELOPMENT_RULES.md` - 開発ルール詳細
- `docs/ARCHITECTURE_OVERVIEW.md` - システムアーキテクチャ
- `PROGRESS.json` - 現在の進捗状況
- `DEVELOPMENT_RULES.json` - 開発ルール（JSON形式）

## 実行モード

| モード | back_test | dummy | 用途 | データ |
|--------|-----------|-------|------|--------|
| バックテスト | 1 | 1 | 過去データで戦略検証 | 過去データ |
| ペーパートレード | 0 | 1 | ライブ市場で検証 | ライブデータ |
| 本番取引 | 0 | 0 | 実際の取引実行 | ライブデータ |

## 現在の進捗状況

### 作業中タスク（PROGRESS）
- Task 22b: Strategy B（Bollinger+RSI+SMA）実装完了、有効化待機
- Task 22c: Strategy C（複合戦略A+B）実装完了、有効化待機
- Task 20b: マルチタイムフレーム ADX 確認、設計中

### 次の優先タスク（TODO）
- Task 39b: Two-Tier Entry System 実装（優先度: ★★★★★）
  - 期待利益: +$300-600/年
- Task 39c: Multi-Timeframe Integration 実装（優先度: ★★★★★）
  - 期待利益: +$400-700/年
- Task 39d: Time-Based Exit 実装（優先度: ★★★★☆）
  - 期待利益: +$100-200/年

### 最近完了（DONE）
- Task 33: ドキュメント整理（2026-01-31）
  - 一時レポート13ファイル削除、ACTION_LIST.md簡素化
- Task 39a: Trailing Profit Target検証完了・不採用（2026-01-11）
  - ベースライン比-1,077 USD悪化のため破棄
- Task 33: ADXフィルタ最適化（2026-01-02）
  - threshold=31で最適、累積+1936.98 USD（+31.9%改善）

## テスト品質基準

現在の状態（2025-12-29）：
- レグレッションテスト: 53/54 (97.8%) PASS
- 四半期テスト: 8/8 PASS
- 累積損益: +904.35 USD

必須基準：
- レグレッションテスト合格率 ≥ 95%
- 新機能実装時は必ずテスト追加
- コミット前にテスト実行

## コミットメッセージ規約

形式: `<type>: <description>`

Type:
- `feat`: 新機能追加
- `fix`: バグ修正
- `refactor`: リファクタリング
- `docs`: ドキュメント更新
- `test`: テスト追加・修正
- `chore`: ビルド・設定変更

例:
```
feat: Task 39b - Two-Tier Entry System実装完了
fix: exit_strategy.pyのPSAR判定バグ修正
docs: ACTION_LIST更新 - Task 39b完了記録
```

## ファイル構成

```
satosystem/
├── PROGRESS.json              # 進捗管理（JSON形式）
├── DEVELOPMENT_RULES.json     # 開発ルール（JSON形式）
├── docs/
│   ├── ACTION_LIST.md         # タスク管理
│   ├── DEVELOPMENT_RULES.md   # 開発ルール詳細
│   ├── ARCHITECTURE_OVERVIEW.md
│   └── analysis/src/          # ソースコード分析（23 JSON files）
├── src/                       # 本体ソースコード（23 Python modules）
├── test/                      # テストコード（26 test files）
└── tools/
    ├── load_development_rules.py  # ルール表示
    └── update_progress.py         # 進捗更新
```

## ツール

### 開発ルール表示
```bash
python3 tools/load_development_rules.py
```

### 進捗更新
```bash
# コミット情報更新
python3 tools/update_progress.py --commit

# タスク完了記録
python3 tools/update_progress.py --task-complete "39b" --description "実装完了"

# タスク開始記録
python3 tools/update_progress.py --task-start "39c" --description "実装開始"
```

## 作業フロー

1. **タスク開始時**
   - `docs/ACTION_LIST.md`のTODO確認
   - `python3 tools/update_progress.py --task-start <ID>`
   - ACTION_LIST.mdのPROGRESSセクション更新

2. **実装中**
   - DEVELOPMENT_RULES.md遵守
   - 変更はファイル・機能単位で分割
   - テストを並行して作成

3. **完了時**
   - レグレッションテスト実行
   - `git status`で変更確認
   - ユーザーに変更内容報告 → 許可取得
   - コミット実行
   - `python3 tools/update_progress.py --task-complete <ID> --commit`
   - ACTION_LIST.mdのDONEセクション更新

## 注意事項

- **すべてのコミット・プッシュは必ずユーザーの許可を得る**
- APIキーは`.api_key`（JSON形式）で管理、`config.ini`には含めない
- バックテスト結果は`baseline_backup/`に保存
- ログファイルは`logs/`に自動保存（定期クリーンアップ検討中）

---

詳細は以下を参照：
- 開発ルール詳細: `docs/DEVELOPMENT_RULES.md` または `DEVELOPMENT_RULES.json`
- 進捗詳細: `PROGRESS.json`
- タスク詳細: `docs/ACTION_LIST.md`
