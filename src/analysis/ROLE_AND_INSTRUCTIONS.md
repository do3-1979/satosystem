# 役割と運用指示 (GitHub Copilot エージェント)

最終更新: 2025-11-16

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

## 実装完了 (2025-11-16)

- **C1/C2/C5/C7/C8**: `nextarch` ブランチ実装済
- **C3**: 例外処理 (commit daa8fb3)
- **C7 拡張**: レポート出力先を `report/` ディレクトリへ統一 (commit 06391d8)
- **設定管理**: `config.ini` プレースホルダー化、`replace_api_key.sh` 復元機能追加 (commit ded06c1)

## C6 パフォーマンス最適化 Backlog

**現状:** PerformanceTracker 計測済 (price_update ~82%, logging ~15%)

**改善タスク (Phase A - 安全):**
1. Donchian差分キャッシュ
2. ログ削減・バッファリング
3. トラッキング無効化フラグ

**Phase B (中リスク):** ボラティリティ増分更新、リスク更新条件化、2h足gating

**Phase C (構造変更):** NumPy化、2h足再構築、ギャップ検出

## 次アクション

### 短期
- [x] ドローダウン計算統一 (metrics.py の計算をログ出力にも使用)
- [x] バックテスト終了時の強制決済処理 (EOB処理実装済)
- [ ] C6 Phase A 実装 (Donchian差分キャッシュ、ログ最適化)

### 中期 (IndicatorService分離 - 準備中)
- [x] ベースライン計測完了 (PnL: 108.99, Trades: 8, Time: 2m15s)
- [ ] IndicatorService クラス作成 (Donchian/PVO/PSAR/ADX/Volatility統合)
- [ ] 段階的リファクタ: PriceDataManagement → IndicatorService
- [ ] 段階的リファクタ: RiskManagement → IndicatorService  
- [ ] パリティテスト (同一結果確認)
- [ ] DataSource 抽象化 (Backtest vs Live)

### 長期
- [ ] 複数戦略ポートフォリオ
- [ ] 動的リスク配分
