# 役割と運用指示 (GitHub Copilot エージェント)

最終更新: 2025-11-17

## 役割
Python 暗号資産トレードボットのアーキテクチャ改善・戦略検証・品質向上を支援。

## 成果物
- `ROLE_AND_INSTRUCTIONS.md` : 本ファイル
- `module_map.json` : クラス/関数/依存関係マップ
- `PROJECT_ANALYSIS_2025-11-16.md` : 初期包括分析

## 留意事項
- シングルトン (Logger, PriceDataManagement) の状態共有に注意
- 売買方向表記: 外部API 'buy'/'sell' vs 内部 'BUY'/'SELL'

## データキャッシュ
- DB: `src/ohlcv_data/ohlcv_cache.db` (SQLite, VCS除外)
- テーブル `candles`: `(symbol, timeframe, close_time)` 主キー
- 1分足・2時間足を timeframe 列で区別

## 課題トラッカ

### カテゴリ (C 系列)
- C1 アーキテクチャ整合: `Order` 契約統一 → **実装済** ✅
- C2 命名標準化: `side` 表記統一 → **実装済** ✅
- C3 例外処理: `Bot.run` エラーハンドリング → **実装済** ✅
- C4 設定キャッシュ: `Config` 頻度最適化 → 提案
- C5 イベント駆動: `EventBus` 統合 → **実装済** ✅
- C6 パフォーマンス: 価格/インジ計算最適化 → 実装中
- C7 レポート品質: 指標出力・PnL時系列・Markdown → **実装済** ✅
- C8 リスク統合: Stop/ポジションサイズ堅牢化 → **実装済** ✅
- C9 ログパイプライン: 集計自動化 → 提案

## 実装完了 (2025-11-16 ~ 2025-11-17)

- **C1/C2/C5/C7/C8**: `nextarch` ブランチ実装済
- **C3**: 例外処理 (commit daa8fb3)
- **C7 拡張**: レポート出力先を `report/` ディレクトリへ統一 (commit 06391d8)
- **設定管理**: `config.ini` プレースホルダー化、`replace_api_key.sh` 復元機能追加 (commit ded06c1)
- **C6 Phase 1**: IndicatorService 統合完了 (2025-11-17)
  - Donchian/PVO/PSAR/ADX/Volatility計算を集約
  - パリティ確認完了 (PnL/Trades/指標値が完全一致)
  - パフォーマンス: 実行時間 24.12s → 24.16s (0.2%増、誤差範囲内)

## C6 パフォーマンス最適化 Backlog

**現状:** PerformanceTracker 計測済 (price_update ~75%, logging ~20%)

**Phase 1 (完了):** IndicatorService 統合
- [x] インジケータ計算の集約・共有化
- [x] PriceDataManagement/RiskManagement リファクタ
- [x] パリティ確認 (PnL/Trades/指標値完全一致)
- [x] パフォーマンス測定 (実行時間: 0.2%増、誤差範囲内)

**Phase 2 (完了):**
1. Donchian差分キャッシュ → 実装済 (2025-11-17 commit 8091f97)
  - 手法: monotonic deque によるインクリメンタル更新 + 小期間(<50)高速パスフォールバック
  - 検証: 1週間ウィンドウ (9960 samples) で PnL / Trades / Samples 完全一致
  - 所見: 小さい期間ではオーバーヘッドにより速度改善なし (36.85s → ~41.86s)。長期・大期間で再評価予定。
2. ログ削減（インターバル）→ 実装済 (2025-11-17)
  - `config.ini` に `logging_interval=100` を追加し、Bot側で100回に1回のログ出力 + 重要イベント時は強制ログ
  - 1週間BT: logging 17.87% → 1.36%、総時間 ~41.9s → ~29.5s (約29%短縮)
  - 長期BT(10/01〜11/15, 64,801 samples): logging 0.41%, 総時間 ~13m56s
3. util.py 可視化拡張 → 実装済 (2025-11-17)
  - トレードイベント抽出CSV出力 (`export_trades_csv_from_logs`)
  - PnL時系列の自動Excel取り込み (report/pnl_timeseries_*.csv → 新規シート)
  - 間引きログ対応: 期間フィルタをConfig.get_start_time/end_timeから自動取得
  - 出力: `logs/combined_logs.xlsx` (Param/Data/Chart/PandL/PnL_Timeseries), `logs/trades_export.csv`

**Phase 3 (中リスク):** ボラティリティ増分更新、リスク更新条件化、2h足gating

**Phase 4 (構造変更):** NumPy化、2h足再構築、ギャップ検出

## 次アクション

### 短期
- [x] ドローダウン計算統一 (metrics.py の計算をログ出力にも使用)
- [x] バックテスト終了時の強制決済処理 (EOB処理実装済)
- [x] IndicatorService統合完了 (2025-11-17)
  - [x] ベースライン計測 (PnL: -13.67, Trades: 2, Time: 24.12s)
  - [x] IndicatorService クラス作成 (src/indicator_service.py, 380行)
  - [x] PriceDataManagement リファクタ (Donchian/PVO/Volatility委譲)
  - [x] RiskManagement リファクタ (PSAR/ADX委譲)
  - [x] bot.py/backtest.py での indicator_service 共有化
  - [x] パリティ確認 (PnL/Trades/指標値完全一致)
  - [x] bot_run.sh 動作確認完了
- [x] C6 Phase 2 Donchian差分キャッシュ (結果パリティ維持)
- [x] C6 Phase 2 ログ最適化 (interval; 重要イベントは強制ログ)
- [x] util.py 可視化拡張 (トレードCSV出力、PnL時系列Excel統合)
- [x] visualizer.py インタラクティブ可視化 (Plotly; 2h足ローソク+1分足+PnL; BUY/SELL色分け; report自動出力)

### 実行結果サマリ (最新)
- 1週間BT (2025/11/09〜11/16, 9960 samples): PnL 21.79, Trades 6, logging 1.36%, 総時間 29.51s
- 長期BT (2025/10/01〜11/15, 64801 samples): PnL 53.11, Trades 24, logging 0.41%, 総時間 785.79s (~13m56s)
- ボトルネック: `price_update` が支配的 (短期 ~76→93%, 長期 ~98%) → データアクセス/指標の増分化が引き続き有効
- util.py 出力: `logs/combined_logs.xlsx` (5シート: Param/Data/Chart/PandL/PnL_Timeseries 64,803行), `logs/trades_export.csv` (77トレード)
- visualizer.py 出力: `report/backtest_visualization_<ts>.html` (Plotly; 2h足ローソク+1分足線+PnLサブプロット; BUY=淡緑/SELL=淡赤ハイライト)

### 中期
- [ ] DataSource 抽象化 (Backtest vs Live)
- [ ] 戦略パラメータチューニング支援
- [ ] リスク管理ルール検証

### 長期
- [ ] 複数戦略ポートフォリオ
- [ ] 動的リスク配分
