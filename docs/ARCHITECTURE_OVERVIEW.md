# アーキテクチャ概要

## コンポーネント責任分担

| コンポーネント | 責務 | 主な連携先 |
|-----------|------|----------|
| Config | config.ini からのパラメータ一元管理・キャッシュ | すべてのモジュール |
| BybitExchange | ccxt ラッパー（マーケット/残高/注文/OHLCV） | PriceDataManagement, Bot |
| PriceDataManagement | OHLCV取得・バッファリング、シグナル導出（Donchian, PVO）、ボラティリティ計算、バックテスト時間進行 | TradingStrategy, RiskManagement |
| OHLCVCache | SQLite永続化（1m/120m マルチタイムフレーム）、upsert・充分性確認 | PriceDataManagement（初期ロード） |
| TradingStrategy | ENTRY/ADD/EXIT判定（シグナル＆ポートフォリオ状態ベース） | Bot, Portfolio |
| RiskManagement | ポジションサイジング、トレーリングストップ（PSAR, 急伸）、ADX状態 | Bot, Portfolio, PriceDataManagement |
| Portfolio | ポジション/平均価格/累積PnL・ドローダウン追跡 | Bot, RiskManagement |
| Order | オーダー意図のDTO（MFE/MAEメトリクス含む） | Bot, Exchange |
| Logger | 構造化ログ、ローテーション、圧縮 | Bot, Util, Metrics |
| Util | ログ抽出・可視化（Excel、チャート） | Logger出力 |
| Metrics | バックテスト後パフォーマンスメトリクス（Sharpe, MaxDD, PF, WinRate） | Bot（サマリー） |

## 実行ルール

### Bot 実行標準
**直接的な `python src/bot.py` 実行で実行可能**

注意点:
- APIキーは `.api_key` ファイルまたは環境変数 `BYBIT_API_KEY`, `BYBIT_API_SECRET` から読み込まれる
- config.ini は テンプレート（config.template.ini）から自動生成される
- APIキーは config.ini に含めないこと（バージョン管理の安全性）

バックテスト時は config ファイルの `back_test = 1` で実行モード切り替え。

## データフロー（バックテスト＆本番）

```
          +-------------+
          |   Config    |
          +------+------+         +------------------+
                 |                |  BybitExchange    |
                 | OHLCV/ticker   +---------+---------+
          +------+------++-------------------+
          | PriceData   | signals/volatility |
          | Management  |<-------------------+
          +------+------+                    |
                 |                           |
          +------+------+
          |  Strategy   | ENTRY/ADD/EXIT
          +------+------+
                 | decision
          +------+------+
          |    Bot      | ループ調整
          +--+-------+--+
             |       |
     sizing/STOP   order DTO
             |       v
          +--v--+  +--v-------------+
          |Risk |  |    Order       |
          |Mgmt |  +-------+--------+
          +--+--+          |
             |             |
             |   exec      v
          +--v-------------+--+
          |    Exchange       |
          +--+----------------+
             |
             | fills/update
          +--v--+
          |Portfolio (PnL history) |
          +--+--+
             |
             v
          +--+--+
          |Logger|--> JSON log files --> Util / Metrics
          +--+--+
             |
             v (backtest end)
          +--+--+
          |Metrics| summary JSON
          +------+
``` 

## タイムフレーム・キャッシュアーキテクチャ

システムは2つの粒度を消費します:
- **2時間足（120m）**: 戦略・リスク判定用
- **1分足**: 細粒度の進行と最新ティッカー/出来高用

両者は単一の SQLite テーブル `candles` に格納され、`(symbol, timeframe, close_time)` でキー付けされます:

```
CREATE TABLE candles (
   symbol TEXT,
   timeframe INTEGER,      -- minutes (1, 15, 120 ...)
   close_time INTEGER,     -- epoch seconds (end of candle)
   open_price REAL,
   high_price REAL,
   low_price REAL,
   close_price REAL,
   volume REAL,
   PRIMARY KEY(symbol, timeframe, close_time)
)
```

### 初期バックテストロード

`PriceDataManagement.initialise_back_test_ohlcv_data()` の流れ:
1. 拡張開始日を計算（開始日 - initial_term * timeframe）
2. 各タイムフレーム（1, 15?, 120）に対して旧JSON形式ロード試行 → DB に upsert
3. `has_sufficient_cache(symbol, timeframe, start, end)` を呼び出し；False の場合は API から全範囲をフェッチして upsert
4. `get_range(...)` で統一範囲をメモリ配列にプル
5. ファイルベース OHLCV を期待する従来ツール用に互換性 JSON を出力

### リフェッチ抑制

`has_sufficient_cache` は実行行数と期待値を比較（許容差2キャンドル）。充分なら API呼び出しなし。これはレート制限を保護し、同一履歴窓の重複ダウンロードを回避します。

### 現在の制限

- 充分性はカウントベース；内部ギャップ（連続キャンドルの欠落）は検出されない
- 2h キャンドルは 1m データからのロールアップではなく直接フェッチ（重複排除の機会）
- 不充分な場合は全範囲フェッチ（欠落セグメントのみに狭められる可能性）

### 将来の拡張

- **ギャップ検出**: 不連続を特定（`delta(close_time) > timeframe*60`）、欠落スパンのみをフェッチ
- **ロールアップエンジン**: 1m ベースシリーズから高いタイムフレームを導出、一貫性と外部依存の低減
- **整合性監査**: 定期レポート（境界カバレッジ、ギャップ数、最新更新タイムスタンプ）
- **適応的許容度**: タイムフレーム長と戦略ウォームアップ需要に基づく動的許容欠落数

### VCS・再現性

キャッシュ DB（`src/ohlcv_data/ohlcv_cache.db` + WAL/SHM）は無視される—バックテストは必要な範囲を再生成します。旧 JSON ファイルは互換性のために保持され、すべてのコンシューマが DB クエリに移行したら削除される可能性があります。

```

## バックテスト進行

- `PriceDataManagement.update_price_data_backtest()` は仮想時計を1分単位で進行させます
- シグナルは フレーム完了時のみ再計算（例: 2h / 15m）
- Bot は各イテレーションごとに `total_profit_and_loss` を `pnl_history` に収集
- 終了条件がメトリクスサマリー JSON をトリガー

## 拡張可能性ポイント

| ポイント | 現状戦略 | 代替案 | 備考 |
|---------|---------|--------|------|
| 指標計算 | Price/Risk内 | 専用 IndicatorService | クラス肥大化を軽減 |
| データソース | 単一クラス | インタフェース（Live vs Backtest） | テスト可能性向上 |
| STOP ロジック | 混合（PSAR + 急伸） | ポリシーオブジェクト | 複合化可能 |
| ログスキーマ | 暗黙的 dict | バージョン化スキーマファイル | フィールド進化の安全化 |

## 戦略最適化履歴

### Keltner チャネルフィルタ（却下）

**決定日**: 2025-11-21  
**テスト期間**: 2025/10/01 - 2025/11/01  
**結果**: 採用せず

12パラメータ組み合わせをテスト（EMA周期: 10/20/30 × ATR倍率: 1.5/2.0/2.5/3.0）:
- すべての設定で同等の悪いパフォーマンス: PnL -35.21（ベースライン 9.94 対比）
- Profit Factor: 0.70、Max DD Rate: 58.18%、Win Rate: 46.67%、取引数: 15
- 0/12設定がベースラインを超える → 決定的に却下

**現在状態**: `keltner_enabled=False` in config.ini；将来参照用にコード保持

### ピラミッディング最適化（採用: entry_times=4）

**決定日**: 2025-11-21  
**テスト期間**: 2025/10/01 - 2025/11/01  
**結果**: entry_times=4 を最適バランスとして選択

テスト設定（entry_times: 2, 3, 4, 5, 10）:

| entry_times | PnL | DD Rate | リスク調整スコア | PF | Sharpe | Win Rate |
|-------------|-----|---------|------------------|-----|--------|----------|
| **4 (採用)** | **107.10** | **49.75%** | **215.27** | **1.25** | **0.343** | **93.33%** |
| 2 | 281.68 | 70.07% | 402.02 | 1.20 | 0.287 | 100% |
| 5 | 69.78 | 44.94% | 155.28 | 1.23 | 0.32 | 93.33% |
| 3 | 45.33 | 64.47% | 70.31 | 1.08 | 0.12 | 93.33% |
| 10 (ベース) | 9.94 | 113.17% | 8.78 | 1.53 | 0.63 | 94.12% |

**選択根拠**:
- DD率が50%未満（本番トレード実用的リスク閾値）
- 最高Sharpe比（0.343）で最良リスク調整リターン
- PnL改善: ベースライン対比 +977%
- 均衡アプローチ: 最大利益より安定性優先
- 長期運用に適合

**現在状態**: `entry_times=4` in config.ini

## 計画中の改善（M ロードマップ）

- M2: ドキュメント統合（README + このファイル）
- M3: リファクタリング課題テンプレート・バックログカテゴリ化
- M4: メトリクスパイプライン（実装完了）& 反復的戦略強化ループ
- M5: トレード分類最適化（k1,k2,k3,L閾値の TREND vs FALSE_BREAK）
- M6: マルチポジション保持用部分利確機能
- M7: EXIT条件の洗練化（トレーリングストップ、利益目標）
- M8: 最新データでの PVO 閾値再最適化

## 計算メトリクス

| メトリクス | ソース | 計算式（簡略） |
|-----------|--------|---------------|
| total_pnl | 累積 PnL | last(pnl_history) |
| profit_factor | 増分リターン | sum(pos)/abs(sum(neg)) |
| max_drawdown | pnl_history | max(peak - trough) |
| max_drawdown_rate | pnl_history | max_drawdown / peak * 100 |
| sharpe | 増分リターン | mean(ret)/std(ret)*sqrt(n) |
| win_rate | trade_results | wins / trades * 100 |

## テスト検討事項

- 合成 pnl パス（単調、変動、平坦）を使用したユニットテストメトリクス関数
- エッジケース: 空履歴、すべて損失、単一サンプル

## Enum 標準化（計画中 C2）

内部 `Side` enum（BUY, SELL, NONE）をすべてのデシジョン＆ポートフォリオ連携に採用；変換は Exchange 境界でのみ実施。

## セキュリティ・障害処理

- ネットワーク/API リトライ: スリープ付きの基本ループ；max-attempt & 指数バックオフが必要
- API キーは config から取得；シークレット のログ出力を回避

## 将来の分離

1. `IndicatorService` （PSAR, ADX, Donchian, PVO）
2. `DataSource` 抽象化（LiveDataSource / BacktestDataSource）
3. `RiskEngine` をサイジングヒューリスティクスから分離

## 優先アクション項目（2025 Q4）

### 🔴 **最優先: Phase 1マーケットレジーム検出の適用化** (100% 検証完了→次フェーズ)

**実装状況 (2025-11-24更新)**:
- ✅ **14種類フルバックテスト完了** （2024年Q1-Q4 + 2025年Q1, Q2, Q4初期）
- ✅ **効果分析完了**: Q2で+56.4%改善、Q4初期で-34.9%悪化
- ✅ **改善案2個検証完了**: 動的STRONG_TREND調整、環境別PVO閾値調整とも効果なし（却下）
- ✅ **本番導入準備完了**: deployment_readiness.md作成、チェックリスト整備

**重要な知見**: 
- Phase 1は**環境依存が極めて大きい**（SIDEWAYS環境では+56.4%有効、トレンド環境では-34.9%有害）
- Binary（ON/OFF）フィルタリングは不十分 → **段階的フィルタリングが必須**
- 現在のボラティリティ閾値（1.2）が実市場で達成されにくい → **閾値自体の再検討必要**

**次のステップ（優先順）**: 
1. **Task 9: 段階的フィルタリング実装** ← **最急務**
   - SIDEWAYS時: ポジションサイズ 0% (現在のまま)
   - WEAK_TREND時: ポジションサイズ 75%に削減
   - STRONG_TREND時: ポジションサイズ 125%に増加
   - 期待効果: -34.9% → -10%程度に改善

2. **Task 7: 環境自動判定スクリプト** （Task 9完了後）
   - リアルタイムでSIDEWAYS出現率計算
   - Phase 1 ON/OFF判定の自動化
   - 市場環境の自動分類

3. **Task 11: リアルタイム監視体制** （Task 9, 7完了後）
   - Win Rate 低下アラート
   - 環境劣化検出
   - 自動パラメータロールバック

**実装優先度**: 🔴 **最優先**（本番導入の前提条件）  
**詳細**: `docs/TRADING_STRATEGY_PLAN.md`, `docs/ACTION_LIST.md` 参照

---

このドキュメントは `README.md` および分析ファイルを補足します；段階的に更新してください。
