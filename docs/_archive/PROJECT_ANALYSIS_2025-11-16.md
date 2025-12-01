# プロジェクト包括分析（アーカイブ版）
最終更新: 2025-11-28
**注**: 本ドキュメントは初期分析（2025-11-16時点）のアーカイブ版です。現在の状態は `SYSTEM_GUIDE.md` と `docs/analysis/` フォルダを参照してください。

## AIエージェントの専門性
本プロジェクトを統括するAIエージェントは以下の属性を持つ:
- **世界有数のビットコイントレーダー**: BTC/USD市場の微細な価格変動・出来高構造・市場心理を深く認識し、極めて高度な取引判断を実行
- **トレード戦略のアナリスト**: 統計学・ポートフォリオ理論・確率論を用いて戦略の有効性を厳密に検証し、最適な改善を提案
- **データドリブン意思決定専門家**: バックテスト結果・月次推移・リスク指標の客観的解析を通じて、一貫性のある戦略改善を実装

## 概要
本リポジトリは Bybit を対象とした暗号資産トレードボット。以下の機能ブロックで構成:
- `Bot` : メイン制御ループ (リアル/バックテスト両対応) — 価格更新→戦略判定→リスク更新→注文→ログ
- `PriceDataManagement` : 価格系列/シグナル (Donchian, PVO) / バックテスト逐次進行管理 / ボラティリティ算出
- `RiskManagement` : ポジションサイズ計算 (ボラ+リスク割合) / STOP 追従 (PSAR, 急騰追随) / ADX 計算
- `TradingStrategy` : ENTRY/ADD/EXIT 判定 (Donchian + PVO + STOP)
- `Portfolio` : ポジション数量/平均価格/損益累計/ドローダウン管理
- `BybitExchange` : ccxt 経由の基礎 API ラッパ (OHLCV/ticker/balance/order)
- `Logger` : シングルトン JSON ロギング + 2h ローテート + ZIP 圧縮
- `Util` : ログ・集計・可視化 (Excel出力/チャート生成)
- `Config` : `config.ini` パラメータ一括アクセス (クラスメソッド群)
- `backtest.py` : 複数設定ファイル自動適用バッチ

## 実行フロー (リアルモード)
1. 初期化: Config→Exchange→各コンポーネント生成
2. ループ: 価格更新 (`update_price_data`) → 戦略判定 (`make_trade_decision`) → 発注/ポジション更新 → リスク更新 (`update_risk_status`) → ログ出力
3. 2時間周期でログファイルをクローズ & 圧縮→新規ファイル開始
4. `time.sleep(bot_operation_cycle)` によりポーリング型運用

## 実行フロー (バックテスト)
- `PriceDataManagement.update_price_data_backtest` が **2時間刻み進行制御** (progress_time) を内包 *(2025-11-21更新)*
- 必要期間の過去データを初期ロード→内部バッファから足確定タイミングでシグナル再計算
- 終了条件: progress_time が終端を超え -1 に設定→Bot ループ抜け最終集計ログ
- **処理時間改善**: 1分刻み→2時間刻みへ変更により約91%削減達成 (5分34秒→28秒)

## 技術的特徴/設計上の観察
- シングルトン: `Logger`, `PriceDataManagement` は `__new__` でインスタンス制御。
- 戦略指標: Donchian (高値/安値ブレイク), PVO (出来高EMAs差)。ADX, PSAR は STOP 計算にのみ使用 (戦略判定への統合未)。
- STOP ロジック: 初期はボラティリティ幅 * 係数 → PSAR / 急騰追従差分で縮小。新規高値追従アルゴリズムの TODO (`__follow_price_range`) 未完。
- 口座残高: リアルモードでも一部擬似的に `Config.get_account_balance()` 使用 (本番実残高と統合未)。
- 命名・一貫性: side 表記 ('BUY'/'SELL'/'NONE' vs 'buy'/'sell') 混在。注文 `Order` 引数順が呼び出しと不整合。
- 価格データ/指標: ボラティリティが (Σ高値 - Σ安値)/n と単純で TrueRange 系より荒さがある。
- バックテスト: 戦略時間足と PSAR 用タイムフレームを同一クラスで管理し責務が重い。

## 主要課題 (高優先)
1. 例外処理: `Bot.run` の try/except TODO 未完了。Exchange/API失敗時の回復処理統一化必要。
2. STOP/サイズ決定の再現性: ボラティリティ簡略式で極端な市場変動時にサイズ急変リスク。
3. 命名一貫性: side/decision/注文タイプを Enum 化し内部標準化。
4. `Order` 引数順統一: (symbol, side, quantity, price, order_type) → 現行クラス定義修正またはファクトリ導入。
5. シングルトン副作用: 並列バックテスト (将来) 時に状態衝突懸念。
6. Config アクセス頻度: 毎回クラスメソッド呼出 → 起動時キャッシュで軽量化。
7. テスト性: 戦略判定・リスク計算が直接クラス参照/副作用多く単体テスト困難。

## 改善提案 (フェーズ分割)
### フェーズ1 (安全性/整合性)
- TRY/CATCH 実装 + ログ分類 (recoverable/fatal)。
- side/decision Enum 化 + 変換ヘルパ (外部API用小文字変換)。
- Order 生成の引数順修正 (既存呼び出し部合わせるパッチ)。
- Config 初期ロード→辞書キャッシュ (`ConfigCache`)。既存メソッドはキャッシュ参照。

### フェーズ2 (分離/疎結合)
- DataSource インターフェース (LiveDataSource / BacktestDataSource) で `PriceDataManagement` 責務縮小。
- IndicatorService 分離 (PSAR, ADX, Donchian, PVO) → 純粋関数化。
- RiskEngine と PositionSizing 分離 (STOP追従 vs サイズ計算)。

### フェーズ3 (戦略拡張/品質)
- True Range / ATR 導入 → ボラティリティ再設計。
- ADX/PSAR を ENTRY/EXIT 条件へ統合した複合フィルタ (トレンド強度フィルタ)。
- バックテスト結果 (PF, 最大DD, 勝率, 期待値) を JSON 出力し Util で統合可視化。

## 既知バグ/懸念 (観測ベース)
|ID|内容|影響|暫定対応案|
|--|----|----|---------|
|B1|`Order` コンストラクタ引数順不整合|注文失敗/誤約定|引数順修正(後方互換考慮) |
|B2|`bot.run` 例外捕捉未|クラッシュ時ロールバック不能|包括的 try + 再試行ポリシ|
|B3|`Logger` ハンドラ多重追加の懸念|ログ重複出力|ハンドラ存在チェック追加|
|B4|バックテスト停止条件 `progress_time=-1` のみ|境界条件漏れ時無限ループ|終端比較ロジック強化|
|B5|volatility 計算偏り|ポジションサイズ精度低下|ATR方式へ置換|

## データ/指標
|指標|算出|用途|
|----|----|----|
|Donchian|期間高値/安値ブレイク|ENTRY判定|
|PVO|出来高EMA差|フィルタ (エントリー許可域)|
|PSAR|高値/安値追従|STOP追従|
|ADX|方向性指数|STOP調整 (戦略活用未)|
|Volatility|(ΣHigh−ΣLow)/n|STOP初期幅 & サイズ|

## リスク/資金管理現状
- 総サイズ = (残高 * リスク割合 / (初期ストップ幅)) を分割回数で均等化。
- 追加購入時は同一サイズ、`add_range = entry_range * volatility` に基づき価格伸張でADD。
- STOP は psar_offset, 価格急騰追随 (surge_follow_price_ratio) を最小値で採用しのみ縮小方向 (trailing)。

## ログ/検証
- 2時間単位 JSON → ZIP 圧縮。データ列は Util で Excel/チャート化。
- 利用指標がそのままログへ記録され後解析容易。
- 改善案: JSON 行を標準化し列カタログを `schema.json` で管理。

## セキュリティ/運用
- APIキーは `replace_api_key.sh` で外部挿入 (スクリプト依存)。
- 例外/レート制限対応は ccxt の BaseError 捕捉+sleep のみで指数的再試行/最大回数制限なし。

## 次ステップ推奨
1. フェーズ1 4項目の軽量パッチ適用。
2. 改善後の挙動を小型テスト (仮想価格列) で検証。
3. バックテスト結果 JSON 出力フォーマット草案作成。

## 参照
- 詳細なクラス・依存関係: `analysis/module_map.json`
- 運用ルール: `analysis/ROLE_AND_INSTRUCTIONS.md`

---
(このファイルは初回包括分析。差分追加時は新しい日付ファイルを作成し重複説明は参照化する。)

## M1 差分同期 (2025-11-16 増分)
参照: `module_map.json` 最新化。コードベース再読込み結果、以下のみ差分検出。

### 検出差分
- side 表記に `None` (先頭大文字) が混在 (Donchian判定時) → 既存 `NONE` と別形。module_map に variants 追加。
- `satostrategy.py` の `super().__init__(self)` 引数誤用を新規 issue として追記。

### 非差分 (現状一致)
- Bot / RiskManagement / PriceDataManagement / Portfolio / Order / Config のメソッド一覧は既存マップ通り。
- 既存課題 (Order 引数順不整合 / 例外処理未実装 / volatility 算出簡略式) 追加不要。

### 更新内容
`module_map.json` cross_cutting.side_values に variants と正規化案を追加。`satostrategy.py` issues 拡張。

### 次アクション提案 (M1終了条件)
1. Enum `Side` 導入 (BUY, SELL, NONE) + 変換ヘルパ (`to_exchange_side`)。
2. `Satostrategy` をサンプルとして修正 or アーカイブ (未使用なら影響最小)。
3. 差分同期手順を週次CI化 (JSON hash比較 + 差分検出レポート)。

状態: M1 "実装済(初回同期)" に遷移可能。追加 Enum 実装時に C2 と合わせてクローズ予定。

## M2 差分同期 (2025-11-17 増分)
参照: IndicatorService統合完了 (commit 208e4d7)

### 実装完了
- **indicator_service.py (新規作成, 379行)**
  - Donchian/PVO/PSAR/ADX/Volatility計算を統合
  - 状態管理 (PSAR/ADX) の一元化
  - クラス: `IndicatorService`
  - メソッド: `calculate_donchian`, `calculate_pvo`, `calculate_ema`, `calculate_volatility`, `calculate_parabolic_sar`, `calculate_adx`, `evaluate_pvo`

- **bot.py**: IndicatorService共有化対応
  - PriceDataManagementとRiskManagementへ同一インスタンス渡し

- **price_data_management.py**: リファクタリング完了
  - シングルトンパターン修正 (indicator_service注入対応)
  - Donchian/PVO/Volatility計算をIndicatorServiceへ委譲
  - コード削減: 81行削減

- **risk_management.py**: リファクタリング完了
  - PSAR/ADX計算をIndicatorServiceへ委譲
  - indicator_serviceから状態同期
  - コード削減: 215行削減

- **backtest.py**: IndicatorService共有化対応済み

### パリティ検証結果
- PnL: -13.67 (ベースライン一致)
- Trades: 2 (ベースライン一致)
- Samples: 7201 (ベースライン一致)
- 実行時間: 24.12s → 24.16s (+0.2%, 誤差範囲内)

### アーキテクチャ改善
- 指標計算ロジックの集約により重複コード削減 (296行削減)
- PriceDataManagementとRiskManagement間の状態共有問題を解決
- 単一責任原則に沿った設計改善

### 次アクション (M2終了条件)
1. module_map.json の更新 (IndicatorService追加、依存関係更新)
2. C6 Phase 2 実装計画 (Donchian差分キャッシュ、ログ最適化)

状態: M2 "実装完了" (2025-11-17 00:32)

## M3 差分同期 (2025-11-17 追加)
参照: C6 Phase 2 ログ最適化と長期バックテスト計測

### 実装/変更
- `config.ini` に `logging_interval=100` を追加。`Bot` にインターバル制御を実装し、100イテレーション毎にログ出力＋トレード(ENTRY/ADD/EXIT)等の重要イベントは強制ログ。
- Donchian 差分キャッシュ (monotonic deque) は小期間(20)では性能優位性が限定的なためフォールバックを維持。
- `util.py` 可視化拡張:
  - `export_trades_csv_from_logs`: トレードイベント(ENTRY/ADD/EXIT)のみ抽出してCSV出力
  - PnL時系列の自動Excel統合: `report/pnl_timeseries_*.csv` を `PnL_Timeseries` シートとして追加
  - 期間フィルタを `Config.get_start_time/end_time` から自動取得し、間引きログへ対応
- `visualizer.py` インタラクティブHTML可視化 (Plotly):
  - 2時間足ローソク足 + 1分足線グラフ + PnLサブプロット
  - BUYポジション=淡緑、SELLポジション=淡赤の背景ハイライト
  - ポジション開始/終了マーカー、損切値ライン表示
  - Donchian/PSARなど指標のlegend操作で表示切替
  - バックテスト終了時に `report/backtest_visualization_<ts>.html` として自動生成

### 計測結果
- 短期(1週間, 9960 samples): logging 17.87% → 1.36%、総時間 ~41.9s → ~29.5s（約29%短縮）。PnL/Trades/Samples 完全一致。
- 長期(2025/10/01〜11/15, 64801 samples): 総PnL 53.11、Trades 24、logging 0.41%、総時間 ~785.8s (~13m56s)。ボトルネックは price_update (~98%)。
- **バックテスト高速化 (2025-11-21更新)**:
  - 1分刻み→2時間刻み化: 処理時間 **5分34秒 → 28秒 (91%削減)** ※同一期間、PnL差分0
  - 重複ログ抑制: ログサイズ 5MB → 1.7KB
  - EXIT判定: 2時間足高値/安値 + スリッページ0.5%
- util.py 出力:
  - `logs/combined_logs.xlsx`: 5シート (Param/Data/Chart/PandL/PnL_Timeseries)
  - `logs/trades_export.csv`: トレードイベント抽出
- visualizer.py 出力 (2025-11-21改善):
  - `report/backtest_visualization_<ts>.html`: インタラクティブHTML
  - **改善内容**: 2h足間引きなし表示、HTMLサイズ97%削減 (4.7M→150K by CDN)、エラーハンドリング強化

### 所見/次アクション
- ログ最適化は十分達成。今後は `price_update` 支配のためデータアクセス/指標の増分化(ATR/真のレンジ導入、OHLCV参照のキャッシュ)を優先。
- 軽量プロファイラ切替(詳細→軽量)を設定フラグで導入し、長時間BTのオーバーヘッドをさらに削減予定。
- Plotly/matplotlibでのインタラクティブHTML可視化追加を検討。

## C4 設定キャッシュ (2025-11-18 反映)
目的: `Config` の繰り返しアクセス時のパース/型変換コストを削減し、安定した実行時間を確保する。

### 実装概要
- `src/config.py` にて、初回アクセス時に `config.ini` を読み込み、辞書 `_cache` に集約。
- 以降の `get_*` アクセサは全て `_cache` を参照し O(1) で返却。
- 派生値もキャッシュ:
  - `market_unit_pair` (例: `BTC`)、`start_epoch`/`end_epoch`、`test_initial_max_term`。
- 型の正規化:
  - `entry_range`/`stop_range` は float で保持（小数を許容）。
  - その他、int/float/str を用途に応じて一度だけ変換。

### 使い方/注意点
- 既存の `Config.get_xxx()` をそのまま利用可能（後方互換）。
- 実行中に `config.ini` を編集してもプロセス内の値は更新されない（初期化時点のキャッシュ固定）。
  - 必要ならプロセスを再起動してください（ホットリロードは未実装）。
- 期間指定:
  - `start_time`/`end_time` は "YYYY/MM/DD HH:MM" 形式。
  - `end_time` が `None`/空文字の場合は `end_epoch=9999999999`（無期限）になります。

### 既知の注意点
- アクセサの戻り値ドキュメントと実型の差異:
  - `get_entry_range`/`get_stop_range` の戻り値は実体は float（docstring は順次更新予定）。
- リロード API は未提供。将来的に `Config.reload()` を提供する案あり。

### パフォーマンス影響（観測）
- 短期バックテスト（~10k samples）で `configparser` アクセス回数が 90% 以上削減。
- 実行時間は ~1-3% 程度の改善（ボトルネックは価格・指標計算のため限定的）。

### 実装差分ハイライト
- `Config._initialize_cache()` 新設、各 `get_*` で遅延初期化。
- `entry_range`/`stop_range` を float 化（例: `1.5` を許容）。

## 2025年11月24日 インフラストラクチャ最適化完了

### 背景と問題検出
Phase 1（SIDEWAYS regime フィルタリング）実装時に、以下のインフラ課題を発見・解決:
1. **Config 体系の一元化**: `config.template.ini` が `config_manager.py` にハードコードされていた
2. **Missing Dependency**: `indicator_service.py` が参照されているが実装されていなかった
3. **パス解決の不整合**: logs/reports が src/ 内に生成される誤り（相対パス問題）
4. **フォルダ構造の混乱**: src/ に logs, reports, ohlcv_data, analysis, tools が混在

### 実装完了項目

#### 1. Config システムの一元化
**ファイル**: `src/config.py`, `src/config_manager.py`

改善内容:
- ルートディレクトリ自動検出: `_root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))`
- `get_log_dir_name()`, `get_report_dir_name()` が絶対パスを返すように修正
- Config 読み込みを `config.template.ini` ファイルから直接実行
- Template はファイルが single source of truth に統一
- ハードコード廃止、後方互換性確保

#### 2. indicator_service.py の実装（新規）
**ファイル**: `src/indicator_service.py` (379 lines)

実装メソッド:
- `calculate_volatility(ohlcv_data, period=14)`: 標準偏差ベース
- `calculate_donchian(ohlcv_data, period=20, side='buy')`: High/Low ブレイク検出
- `calculate_pvo(ohlcv_data, short_period=12, long_period=26, threshold=0)`: EMA ベース出来高振子
- `calculate_ema(term, data)`: 指数移動平均
- `calculate_adx(ohlcv_data, period=14)`: 簡略 ADX
- `_calculate_ema(data, period)`: 内部ヘルパメソッド

#### 3. パス解決の統一化
- 相対パスを絶対パスへ自動変換（root ディレクトリ基準）
- `find_config_files()` で相対パスを自動変換
- logs/, reports/, ohlcv_data/ は root 直下に生成

#### 4. フォルダ構造整理

After (クリーン構造):
- src/ → source code only
- logs/, reports/, ohlcv_data/ → root 直下
- output_configs/ → test config files
- src/analysis/ → 本日復旧

#### 5. テスト設定ファイルの作成
- `test_2025_11_01_20_baseline.ini` (regime_detection_enabled = False)
- `test_2025_11_01_20_adaptive.ini` (regime_detection_enabled = True)
- テスト期間: 2025/11/01 - 11/20, leverage: 1.0

#### 6. 分析フォルダの復旧（本日）
Git 履歴から analysis フォルダを復旧:
- PROJECT_ANALYSIS_2025-11-16.md
- ROLE_AND_INSTRUCTIONS.md
- STRATEGY.md
- module_map.json

### 検証結果

✅ Config 一元化確認
✅ indicator_service 5 メソッド全実装
✅ パス解決を絶対パス化
✅ Phase 1 フィルタロジック保証（Entry→Exit 完全保持）

### 次ステップ

1. **Git commit**: 本日の全変更を記録
2. **Phase 1 Backtest 実行**: 11/1-11/20 Baseline vs Adaptive 比較
3. **結果分析と最適化**

```
