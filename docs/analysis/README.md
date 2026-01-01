# docs/analysis フォルダ構成

このフォルダは、プロジェクト全体の分析成果物とメタデータを整理管理します。
---

## 🎯 プロジェクト分析の推奨手順

### Step 1: 分析フォーマットの理解
最初に、プロジェクトで使用している分析フォーマット（**Level 1+ スキーマ**）を理解してください。
```bash
cat docs/analysis/ANALYSIS_SCHEMA_V2.json | jq '.'
```

**ANALYSIS_SCHEMA_V2.json が定義するもの**:
- `metadata`: 分析ファイルのメタデータ（作成日時、Python版、フォーマットバージョン）
- `file_overview`: ファイル全体の目的・行数・クラス数・責務定義
- `classes[]`: 各クラスの責務・メソッド・エラーハンドリング・テスト提案
- `functions[]`: スタンドアロン関数の詳細
- `summary`: アーキテクチャスコア（信頼性・テスト容易性・保守性）

### Step 2: ソースコード分析ファイルの参照
`docs/analysis/src/` 配下に、**全17個のPythonソースファイルの詳細分析**が格納されています。

```bash
# クリティカルモジュールから確認
cat docs/analysis/src/bot.json | jq '.file_overview'
cat docs/analysis/src/config.json | jq '.file_overview'
cat docs/analysis/src/trading_strategy.json | jq '.file_overview'

# 全ファイル一覧
ls docs/analysis/src/ | sort
```

**各JSONファイルの役割**:
| ファイル | 目的 | 優先度 |
|---------|------|--------|
| `bot.json` | トレード実行ループのオーケストレーション | ★★★★★ |
| `config.json` | 設定管理・パラメータ定義 | ★★★★★ |
| `trading_strategy.json` | Donchian + PVO シグナル生成 | ★★★★★ |
| `risk_management.json` | 資金管理・ポジションサイズ | ★★★★★ |
| `price_data_management.json` | OHLCV データキャッシュ・フェッチ | ★★★★☆ |
| `exit_strategy_v2.json` | 複合exit指標（PSAR+PVO+ADX） | ★★★★☆ |
| その他 | 補助機能（Order, Portfolio, Event等） | ★★★☆☆ |

### Step 3: プロジェクト全容の理解
以下の主要ドキュメントを順序付きで参照：

1. **[ARCHITECTURE_OVERVIEW.md](../ARCHITECTURE_OVERVIEW.md)** - システムアーキテクチャ・モジュール依存関係
2. **[PRICE_DATA_FLOW_DESIGN.md](../PRICE_DATA_FLOW_DESIGN.md)** - バックテスト / ペーパートレード / 本番トレードのデータフロー
3. **[DEVELOPMENT_RULES.md](../DEVELOPMENT_RULES.md)** - 開発ルール・テスト戦略・コミットメッセージ規約
4. **[ACTION_LIST.md](../ACTION_LIST.md)** - 進行中・完了済み・却下した施策一覧

### Step 4: 整合性確認
プロジェクト全容を把握した後、以下の観点で整合性を検証：

- ✅ **src/ JSONの統一性**: 全18ファイルが `format_version: "2.0"` を採用
- ✅ **責務の明確性**: 各クラスの `responsibility.primary` が唯一に定義されているか
- ✅ **依存関係の閉包性**: 循環依存がないか（DAG構造）
- ✅ **エラーハンドリング**: critical_methods が例外対応を記載しているか
- ✅ **テスト推奨事項**: テストケース提案が実装可能か

---
## ディレクトリ構成

### `/src/` - ソースコード分析結果
`src/` フォルダ以下のPythonファイルを自動解析したJSON形式の分析成果物。各ファイルは対応するソースファイルの構造（クラス、メソッド、関数など）を記録します。

**対象ファイル** (18個):
- `bot.json`, `bybit_exchange.json`, `config.json`
- `event.json`, `exchange.json`, `exit_strategy_v2.json`
- `logger.json`, `metrics.json`, `ohlcv_cache.json`, `ohlcv_cache_inspector.json`
- `order.json`, `portfolio.json`, `price_data_management.json`
- `risk_management.json`, `side.json`, `trading_strategy.json`
- `util.json`, `visualizer.json`

**フォーマット**: ANALYSIS_SCHEMA_V2.json に準拠（Level 1 フォーマット）
- `metadata`: 分析時刻・Python版・フォーマット版
- `file_overview`: 目的・行数・クラス数・責務定義
- `classes[]`: クラスごとの責務・メソッド・エラーハンドリング
- `summary`: スコア（アーキテクチャ、テスト容易性、保守性）

---

## ルートレベル - スキーマ・レポート

### スキーマ定義
- **ANALYSIS_SCHEMA_V2.json** - Level 1+ フォーマットのJSON Schema定義

### 戦略・分析レポート  
- **UPDATE_STRATEGY_SUMMARY.json** - 戦略更新・改善施策の総括
- **project_structure.json** - gen2 ブランチのプロジェクト構成メタデータ

---

## 効率的な参照方法

### 1. クリティカルモジュール構造の確認（最初の 5 分）
```bash
# Bot のメイン処理フロー
jq '.classes[0].responsibility' docs/analysis/src/bot.json

# Config パラメータ全体像
jq '.file_overview + .classes[0].methods | .[0:5]' docs/analysis/src/config.json

# Trading Strategy のシグナル生成
jq '.classes[0].methods[] | select(.name == "generate_signal")' docs/analysis/src/trading_strategy.json
```

### 2. システムアーキテクチャの把握（10 分）
```bash
# 依存関係を見る
jq '.file_overview' docs/analysis/src/bot.json
jq '.file_overview' docs/analysis/src/price_data_management.json

# 外部ドキュメント参照
cat docs/ARCHITECTURE_OVERVIEW.md
```

### 3. エラーハンドリング・テスト戦略の確認（必要時）
```bash
# 各クラスのエラーハンドリング
jq '.classes[0] | {name: .class_name, error_handling}' docs/analysis/src/*.json

# テスト推奨事項
jq '.classes[0].test_recommendations' docs/analysis/src/trading_strategy.json
```

---

## ドキュメント管理ルール

1. **ソース分析JSON** (`src/*.json`):
   - フォーマット: ANALYSIS_SCHEMA_V2.json に準拠
   - 更新: 手動（ソースコード変更後に手動で再分析）
   - コミット対象: Yes（参考資料・設計ドキュメント）

2. **スキーマ・メタデータ** (ルートレベル):
   - `ANALYSIS_SCHEMA_V2.json`: フォーマット定義（変更はめったにない）
   - `project_structure.json`: プロジェクト構成（ファイル追加・削除時に更新）
   - `UPDATE_STRATEGY_SUMMARY.json`: 戦略更新記録（施策実装時に更新）

3. **古いファイルの削除**:
   - フォーマット統一のため、旧フォーマット（v1.0以前）のJSONは削除
   - 不要な分析ファイル（テスト結果など）は `_archive/` に移動

4. **参照リンク**:
   - `docs/` ルートドキュメント（ARCHITECTURE, DEVELOPMENT_RULES など）への参照は絶対パスで記載
   - 例: `../ARCHITECTURE_OVERVIEW.md`, `../PRICE_DATA_FLOW_DESIGN.md`

---

## トラブルシューティング

### Q: JSON ファイルが古いフォーマットのように見える
**A:** `format_version` フィールドを確認してください。`2.0` 以上が新フォーマットです。
```bash
jq '.metadata.format_version' docs/analysis/src/bot.json
```

### Q: 新しいソースファイルを追加した
**A:** 対応する分析JSONを手動で作成してください（ANALYSIS_SCHEMA_V2.json に準拠）。
```bash
# テンプレートから生成
python << 'EOF'
import json
template = {
  "metadata": {"source_file": "src/new_module.py", "format_version": "2.0", ...},
  "file_overview": {...},
  "classes": [...],
  "summary": {...}
}
print(json.dumps(template, indent=2, ensure_ascii=False))
EOF
```

### Q: プロジェクト全容がわかりにくい
**A:** 推奨手順に従ってください：
1. ANALYSIS_SCHEMA_V2.json でフォーマット確認（2 分）
2. `docs/analysis/src/bot.json` でメイン処理確認（3 分）
3. `docs/ARCHITECTURE_OVERVIEW.md` でモジュール関係図確認（5 分）
4. 各 `src/*.json` で詳細確認（時間がある時）


3. **スキーマ・定義** (SOURCE_ANALYSIS_SCHEMA.json 他):
   - 仕様変更時のみ更新
   - 変更履歴を記録

4. **一時的なレポート**:
   - `report_tmp/` に移動（見直し予定のもの）
   - Git管理外（.gitignore）

---

## 関連ドキュメント

- `docs/DEVELOPMENT_RULES.md` - 開発ルール全般
- `docs/ACTION_LIST.md` - 課題・改善項目管理
- `docs/ARCHITECTURE_OVERVIEW.md` - アーキテクチャ概要
- `src/source_analyzer.py` - ソース分析ツール
