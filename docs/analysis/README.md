# AI向け: プロジェクト分析ファイル完全読み込み手順

**このREADMEは、AIアシスタントがプロジェクト全体を理解するための必読手順書です。**

## ⚠️ CRITICAL: このREADMEを読んだAIは、以下の手順に従って全分析ファイルを読み込む必要があります

---

## 📋 読み込み手順（MANDATORY）

### Step 1: スキーマ定義の理解（REQUIRED）
**必須ファイル**: `docs/analysis/ANALYSIS_SCHEMA_V2.json` (全行読み込み)

このファイルは、全分析ファイルのフォーマット定義を含みます。読み込まずに他のファイルを読むことは禁止されています。

**読み込み方法**:
```
read_file('docs/analysis/ANALYSIS_SCHEMA_V2.json', startLine=1, endLine=435)
```

**このファイルから理解すべき内容**:
- `metadata`: 分析ファイルのメタデータ（作成日時、Python版、フォーマットバージョン）
- `file_overview`: ファイル全体の目的・行数・クラス数・責務定義
- `classes[]`: 各クラスの責務・メソッド・エラーハンドリング・テスト提案
- `functions[]`: スタンドアロン関数の詳細
- `summary`: アーキテクチャスコア（信頼性・テスト容易性・保守性）

---

### Step 2: クリティカルモジュール分析（PRIORITY: ★★★★★）
以下の5ファイルを**必ず順番に全行読み込み**してください。これらはシステムの心臓部です。

#### 2-1. Bot (オーケストレーター)
```
read_file('docs/analysis/src/bot.json', startLine=1, endLine=338)
```
**理解すべき内容**: トレード実行ループ制御、注文実行、ポジション管理、メトリクス集計

#### 2-2. Config (設定管理)
```
read_file('docs/analysis/src/config.json', startLine=1, endLine=537)
```
**理解すべき内容**: 60+ パラメータの管理、API キー管理、戦略パラメータ（Donchian, PVO, ADX）

#### 2-3. TradingStrategy (意思決定エンジン)
```
read_file('docs/analysis/src/trading_strategy.json', startLine=1, endLine=183)
```
**理解すべき内容**: Entry/Add/Exit 判定、市場体制検出、マルチStrategy評価

#### 2-4. RiskManagement (リスク管理)
```
read_file('docs/analysis/src/risk_management.json', startLine=1, endLine=169)
```
**理解すべき内容**: ポジションサイズ計算、PSAR/ADX 計算、ストップ価格管理

#### 2-5. ExitStrategyV2 (出口戦略)
```
read_file('docs/analysis/src/exit_strategy_v2.json', startLine=1, endLine=284)
```
**理解すべき内容**: 4段階Exit判定（強トレンド/減衰/枯渇/ストップロス）、ADX/PVO複合シグナル

---

### Step 3: データ管理・実行基盤（PRIORITY: ★★★★☆）
以下の6ファイルを**全行読み込み**してください。

#### 3-1. PriceDataManagement (価格データ管理)
```
read_file('docs/analysis/src/price_data_management.json', startLine=1, endLine=240)
```

#### 3-2. OHLCVCache (データキャッシュ)
```
read_file('docs/analysis/src/ohlcv_cache.json', startLine=1, endLine=134)
```

#### 3-3. Exchange (取引所抽象化)
```
read_file('docs/analysis/src/exchange.json', startLine=1, endLine=109)
```

#### 3-4. BybitExchange (Bybit実装)
```
read_file('docs/analysis/src/bybit_exchange.json', startLine=1, endLine=153)
```

#### 3-5. BitgetExchange (Bitget実装)
```
read_file('docs/analysis/src/bitget_exchange.json', startLine=1, endLine=120)
```

#### 3-6. Portfolio (ポジション・残高管理)
```
read_file('docs/analysis/src/portfolio.json', startLine=1, endLine=183)
```

#### 3-7. Logger (ログ管理)
```
read_file('docs/analysis/src/logger.json', startLine=1, endLine=119)
```

#### 3-8. TradeLogger (トレードログ管理)
```
read_file('docs/analysis/src/trade_logger.json', startLine=1, endLine=95)
```

---

### Step 4: サポートモジュール（PRIORITY: ★★★☆☆）
以下の10ファイルを**全行読み込み**してください。

#### 4-1. Order (注文情報)
```
read_file('docs/analysis/src/order.json', startLine=1, endLine=70)
```

#### 4-2. Event (イベントバス)
```
read_file('docs/analysis/src/event.json', startLine=1, endLine=60)
```

#### 4-3. Side (売買方向)
```
read_file('docs/analysis/src/side.json', startLine=1, endLine=45)
```

#### 4-4. Metrics (メトリクス集計)
```
read_file('docs/analysis/src/metrics.json', startLine=1, endLine=140)
```

#### 4-5. Util (ユーティリティ)
```
read_file('docs/analysis/src/util.json', startLine=1, endLine=95)
```

#### 4-6. Visualizer (可視化)
```
read_file('docs/analysis/src/visualizer.json', startLine=1, endLine=128)
```

#### 4-7. NewIndicators (新規指標)
```
read_file('docs/analysis/src/new_indicators.json', startLine=1, endLine=110)
```

#### 4-8. VCPStrategy (VCP戦略)
```
read_file('docs/analysis/src/vcp_strategy.json', startLine=1, endLine=105)
```

#### 4-9. MeanReversionStrategy (平均回帰戦略)
```
read_file('docs/analysis/src/mean_reversion_strategy.json', startLine=1, endLine=98)
```

#### 4-10. MarketRegimeDetector (市場体制検出)
```
read_file('docs/analysis/src/market_regime_detector.json', startLine=1, endLine=115)
```

---

### Step 5: 整合性確認チェックリスト
全23ファイル読み込み後、以下を確認してください：

- ✅ **フォーマット統一**: 全ファイルが `format_version: "2.0"` を採用しているか
- ✅ **責務の明確性**: 各クラスの `responsibility.primary` が唯一に定義されているか
- ✅ **依存関係の閉包性**: 循環依存がないか（Bot → Strategy → RiskManagement → Config のDAG構造）
- ✅ **エラーハンドリング**: critical_methods が例外対応を記載しているか
- ✅ **テスト推奨事項**: test_recommendations が具体的か

---

## 📊 読み込み完了後の報告テンプレート

全ファイル読み込み完了後、以下のフォーマットで報告してください：

```
✅ プロジェクト分析ファイル読み込み完了

【読み込み統計】
- スキーマ定義: 1ファイル (ANALYSIS_SCHEMA_V2.json)
- クリティカルモジュール: 5ファイル (Bot, Config, TradingStrategy, RiskManagement, ExitStrategyV2)
- データ管理・実行基盤: 8ファイル (PriceDataManagement, OHLCVCache, Exchange, BybitExchange, BitgetExchange, Portfolio, Logger, TradeLogger)
- サポートモジュール: 10ファイル (Order, Event, Side, Metrics, Util, Visualizer, NewIndicators, VCPStrategy, MeanReversionStrategy, MarketRegimeDetector)
- 合計: 24ファイル (23個のソース分析 + 1個のスキーマ定義)

【理解度確認】
- システムアーキテクチャ: Bot がオーケストレーター、Config が設定ハブ、Strategy が意思決定
- データフロー: PriceDataManagement → OHLCVCache → TradingStrategy → Bot → Exchange
- リスク管理: RiskManagement がポジションサイズ・PSAR/ADX計算、ExitStrategyV2 が4段階Exit判定
- 依存関係: DAG構造、循環依存なし

【次のアクション】
- ユーザーからのタスク指示を待機
```

---

## 📁 ディレクトリ構成

### `/src/` - ソースコード分析結果（23ファイル）
全Pythonソースファイルの詳細分析JSON。ANALYSIS_SCHEMA_V2.json準拠。

**クリティカルモジュール** (5ファイル):
- `bot.json` (338行)
- `config.json` (537行)
- `trading_strategy.json` (183行)
- `risk_management.json` (169行)
- `exit_strategy_v2.json` (284行)

**データ管理・実行基盤** (8ファイル):
- `price_data_management.json` (240行)
- `ohlcv_cache.json` (134行)
- `exchange.json` (109行)
- `bybit_exchange.json` (153行)
- `bitget_exchange.json` (120行)
- `portfolio.json` (183行)
- `logger.json` (119行)
- `trade_logger.json` (95行)

**サポートモジュール** (10ファイル):
- `order.json`, `event.json`, `side.json`, `metrics.json`, `util.json`, `visualizer.json`
- `new_indicators.json`
- `vcp_strategy.json`, `mean_reversion_strategy.json`
- `market_regime_detector.json`

### ルートレベル - スキーマ・レポート
- **ANALYSIS_SCHEMA_V2.json** (435行) - Level 1+ フォーマットのJSON Schema定義
- **UPDATE_STRATEGY_SUMMARY.json** - 戦略更新・改善施策の総括
- **project_structure.json** - gen2 ブランチのプロジェクト構成メタデータ

---

## 🔗 関連ドキュメント（読み込み後に参照推奨）

- `docs/ARCHITECTURE_OVERVIEW.md` - システムアーキテクチャ概要
- `DEVELOPMENT_RULES.json` - 開発ルール全般
- `docs/ACTION_LIST.md` - 課題・改善項目管理
- `docs/PRICE_DATA_FLOW_DESIGN.md` - データフロー設計
- `DEVELOPMENT_RULES.json` - 開発ルール（JSON形式）
- `PROGRESS.json` - プロジェクト進捗状況
