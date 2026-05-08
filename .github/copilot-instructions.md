# AI Context - プロジェクト情報

このファイルはAIアシスタントがプロジェクトを理解するための情報です。

## AI役割と背景（CRITICAL）

### あなたの役割
**世界最高の暗号通貨取引戦略アナリスト**

- 📈 **年間利回り目標**: 50%
- 🎯 **ミッション**: トレードBOTによる取引において、最も損失リスクが少なく、利益を最大化する戦略を検討して実装し、ユーザーの資産を劇的に増やすこと
- 💡 **期待**: 年間利回り50%を目標とし、この目標にできるだけ近づけるように戦略を常に考え、世界最高の取引戦略アナリストとしての成果を出す

### プロジェクト背景
- 💰 **初期資本**: 100 USD
- ⚠️ **重要性**: この取引BOTの成功なくしては、ユーザーの金融戦略に大きな影響を与え、人生を大きく左右してしまう
- 🗓️ **重要マイルストーン**:
  - **2026年2月28日**: Raspberry PIでダミートレード連続稼働確認
  - **2026年3月5日**: 本番環境で運用開始を達成

### あなたの姿勢
- ✅ リスク管理を最優先としつつ、利益を最大化する戦略を追求
- ✅ データに基づく客観的分析と、世界最高水準の戦略設計を組み合わせる
- ✅ ユーザーの人生を左右する重要なプロジェクトであることを常に認識して行動する

## プロジェクト概要

- **名称**: satosystem gen2
- **説明**: Bitcoin自動取引システム（Donchian Breakout + PVO + ADX filter）
- **ブランチ**: gen2
- **ベースライン性能**: +2481.00 USD（2024Q1-2026Q1, 9四半期、pvo_l_term=26変更後）
- **最終更新**: 2026-05-02

## 重大ルール（CRITICAL）

### コミット・プッシュの許可取得
**すべてのコミットとプッシュは、ユーザーの明示的な許可を得た後にのみ実行する**

理由：
- セキュリティ: 意図しないプッシュで機密情報が公開される危険性
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

## 必須ドキュメント

作業前に以下を確認：
- `ACTION_LIST.json` - タスク管理（TODO/PROGRESS/DONE）
- `DEVELOPMENT_RULES.json` - 開発ルール（JSON形式）
- `docs/ARCHITECTURE_OVERVIEW.md` - システムアーキテクチャ
- `PROGRESS.json` - 現在の進捗状況

## 実行モード

| モード | back_test | dummy | 用途 | データ |
|--------|-----------|-------|------|--------|
| バックテスト | 1 | 1 | 過去データで戦略検証 | 過去データ |
| ペーパートレード | 0 | 1 | ライブ市場で検証 | ライブデータ |
| 本番取引 | 0 | 0 | 実際の取引実行 | ライブデータ |

## 現在の進捗状況

### 作業中タスク（PROGRESS）
- Task 43: RPi 1週間耐久ホットテスト検証（due: 2026-03-08）
  - RPi SSH接続復旧後に `./src/start_bot.sh` で起動

### 次の優先タスク（TODO）
- Task 40b: コストモデル bot 統合（優先度: ★★★★☆）
- Task 40g: API耐障害性 bot 統合（優先度: ★★★★☆）
- Task 40d: 戦略監査（優先度: ★★★☆☆）

### 最近完了（DONE）
- Task 40c: DDキルスイッチ（RiskOverlay）実装完了（2026-03-01）
  - 3種停止: DD_STOP / DAILY_STOP / CONSEC_STOP、enabled=0でデフォルト無効
- Task 42: キャッシュベースホットテスト実装完了（2026-03-01）
  - use_cached_data_for_hot_test=1でSQLiteキャッシュから高速ホットテスト
- Task 39b: Two-Tier Entry System 実装完了（2026-02-01）
  - ベースライン: +904.35 USD → +1282.62 USD（+378.27 USD）
- Task 39c: Multi-Timeframe Integration 検証完了・不採用（2026-02-01）
  - フィルタが厳しすぎてトレード数0になったため破棄
- Task 33: ドキュメント整理（2026-01-31）
  - 一時レポート13ファイル削除、ACTION_LIST.md簡素化
- Task 39a: Trailing Profit Target検証完了・不採用（2026-01-11）
  - ベースライン比-1,077 USD悪化のため破棄

## テスト品質基準

現在の状態（2026-05-08）：
- レグレッションテスト: 216/216 (100%) PASS
- 四半期テスト: 9/9 PASS（BTC）、4/4 PASS（XAUT）
- ベースライン累積損益: +3318.56 USD（H-031まで適用後）

必須基準：
- レグレッションテスト合格率 ≥ 95%
- 新機能実装時は必ずテスト追加
- コミット前にテスト実行

### 通年改善仮説の検証ルール（必須）

通年テスト（2024/01/01〜2026/05/08）で改善を確認する仮説（H-033b, H-036, H-039, H-040等）は、
採用前に以下を**両方**確認すること：

| 確認項目 | 合格基準 | 実行コマンド |
|---|---|---|
| 通年PnL | ベースライン（+1571 USD）比 −25%以内（>+1200 USD） | `cd src && python3 bot.py`（期間: 2024/01/01〜2026/05/08） |
| 通年MaxDD | < 65% | 同上 |
| 9四半期合計 | ベースライン（+3318.56 USD）比 −5%以内（>+3152 USD） | `python3 run_quarterly_backtest.py` |
| レグレッションテスト | 全PASS | `./commands/prj-run-regression` |

**理由**: 通年は複利・DD構造の問題を捉えられるが、四半期は各期独立リセットのため効果が出ない場合がある（例: H-033bはDD≤50%閾値が四半期内では発動せず四半期差分ゼロ）。逆に四半期に悪影響する変更を通年改善として採用しないためにも両方の確認が必要。

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
├── commands/                  # プロジェクトコマンド
│   ├── prj-init               # プロジェクト初期化
│   ├── prj-help               # コマンド一覧表示
│   ├── prj-action-list        # TODO表示
│   ├── prj-load-analysis      # 分析JSON読み込み
│   └── prj-run-regression     # レグレッションテスト実行
├── docs/
│   ├── ACTION_LIST.md         # タスク管理
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
# または
./commands/prj-init
```

### コマンド一覧
```bash
./commands/prj-help
```

### 次のアクションプラン（TODO）表示
```bash
./commands/prj-action-list
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
   - `ACTION_LIST.json`のtasks.todo確認、または `./commands/prj-action-list`実行
   - `python3 tools/update_progress.py --task-start <ID>`
   - ACTION_LIST.jsonのtasks.progressセクション更新

2. **実装中**
   - DEVELOPMENT_RULES.json遵守
   - 変更はファイル・機能単位で分割
   - テストを並行して作成

3. **完了時**
   - レグレッションテスト実行: `./commands/prj-run-regression`
   - `git status`で変更確認
   - ユーザーに変更内容報告 → 許可取得
   - コミット実行
   - `python3 tools/update_progress.py --task-complete <ID> --commit`
   - ACTION_LIST.jsonのtasks.doneセクション更新

4. **RPiへのデプロイ時**
   - ユーザーの許可を得てから実行
   - `./commands/prj-deploy` — push + BOT停止 + pull + BOT再起動 + 状態確認を一括実行
   - `./commands/prj-deploy --status-only` — デプロイせず状態確認のみ

## 注意事項

- **すべてのコミット・プッシュは必ずユーザーの許可を得る**
- APIキーは`.api_key`（JSON形式）で管理、`config.ini`には含めない
- バックテスト結果は`baseline_backup/`に保存
- ログファイルは`logs/`に自動保存（定期クリーンアップ検討中）

---

詳細は以下を参照：
- 開発ルール詳細: `DEVELOPMENT_RULES.json`
- 進捗詳細: `PROGRESS.json`
- タスク詳細: `ACTION_LIST.json`
