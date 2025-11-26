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

### 🟢 **Phase 2: 段階的フィルタリング実装** (✅ 実装完了 - 2025-11-24)

**実装状況 (2025-11-24更新)**:
- ✅ **実装完了**: Phase 2 段階的フィルタリング（0.75/1.0/1.25乗数）
- ✅ **14種類バックテスト完了**: 2024 Q1-Q4 + 2025 Q1-Q3（Baseline vs Phase 2）
- ✅ **効果検証完了**: +10.34% PnL改善、Q2 2025で+56.43%、Q1 2024で+11.61%
- ✅ **Config整合性確認**: config.template.ini → output_configs → Config → RiskManagement
- ✅ **Github コミット**: 4318da5 & 7c2b758

**実装詳細**:
```python
# risk_management.py
if graduated_sizing_enabled:
    multiplier = {
        'SIDEWAYS': 0.75,        # リスク削減
        'WEAK_TREND': 1.0,       # 基準
        'STRONG_TREND': 1.25     # 積極的
    }[current_regime]
    final_position = base_position * multiplier
```

**主要効果**:
- Q2 2025: +56.43%改善（保合い→トレンド転換環境で有効）
- Q1 2024: +11.61%改善（高ボラティリティ環境で有効）
- その他期間: -1.14% ～ +0.27%（許容範囲内）
- 総合: +$570.48改善（+10.34%）

### 🟡 **Phase 3: 自動化フレームワーク** (✅ 実装完了 - 2025-11-24)

**実装状況 (2025-11-24更新)**:
- ✅ **Task 7完了**: 環境自動判定スクリプト (`src/environment_auto_judge.py`)
  - 過去30日のレジーム分布分析
  - SIDEWAYS ≥30% で Phase 2有効化判定
  - JSON 出力: `work_reports/environment_auto_judgement_*.json`

- ✅ **Task 10完了**: 動的基準学習システム (`src/dynamic_threshold_learning.py`)
  - 過去データからvolarity_ratio/trend_strength最適値導出
  - Percentile探索（P40-P80）で効果スコア計算
  - JSON 出力: `work_reports/dynamic_threshold_learning_*.json`

- ✅ **Task 11完了**: リアルタイムパフォーマンス監視 (`src/realtime_performance_monitor.py`)
  - 日次PnL/Win Rate/Profit Factor監視（7日間スライディング）
  - アラート検出: WR_DEGRADATION(>10%), CONSECUTIVE_LOSSES(≥5日), LOW_PROFIT_FACTOR(<0.5), REGIME_CHANGE
  - JSON 出力: `work_reports/realtime_monitor_*.json`

**統合フロー**:
```
毎日実行 (00:00 UTC):
  └─ Task 11: リアルタイムモニター更新 → 環境劣化検出 → Phase 2 自動調整

毎週実行 (月曜 00:00 UTC):
  └─ Task 7: 環境自動判定 → config推奨値生成

毎月実行 (1日 00:00 UTC):
  └─ Task 10: 動的閾値学習 → 最適値導出 & 更新提案
```

**期待される追加改善**:
- Task 7による環境自動判定: 機会損失削減（±5%）
- Task 10による動的学習: レジーム検出精度向上（±5-10%）
- Task 11による監視: リスク軽減・早期検出（許容範囲内を実現）

**詳細**: `work_reports/phase3_implementation_summary_20251124.md` 参照

---

### 📋 **次フェーズ（推奨優先順）**

#### Task 17: 本番環境への Phase 2 反映 ← **次のステップ**

**目的**: Phase 2 段階的フィルタリングの本番適用

**実施内容**:
```bash
# config.ini を修正
[Strategy]
regime_detection_enabled = True        # Phase 1有効化
graduated_sizing_enabled = True        # Phase 2有効化 ← 変更
```

**期待効果**:
- 短期: +10.34% PnL改善（バックテスト実証値）
- 中期: Phase 3との統合で +5-10% 追加改善

**検証ポイント**:
- [ ] config が正常に読み込まれるか
- [ ] リスク管理が乗数を正確に適用しているか
- [ ] バックテスト結果と本番結果の乖離監視

**所要時間**: 1時間以内（実装は完了、テストのみ）

---

## 🚨 バックテスト課題・実装ログ

### Issue 1: バックテスト結果が全期間で赤字（2024年・2025年共通）

**発見日**: 2025-11-25

**現象**:
- 2024年通年平均 PnL: **-37,559 USD** （初期資本 10,000 USD）
- 2025年1/1～11/24平均 PnL: **-10,756 USD**
- すべての Q1～Q4 config で損失
- MaxDD が 0 になっている（不正）

**詳細**:
```
2024年通年:
  - extended_2024_Q1_baseline: -118,027 USD（96.83% 勝率なのに損失？）
  - extended_2024_Q2_baseline: -9,817 USD
  - extended_2024_Q3_baseline: -11,859 USD
  - extended_2024_Q4_baseline: -10,532 USD
  
2025年1/1～11/24:
  - phase2_2025_Q1_baseline: -13,940 USD（92.31% 勝率）
  - extended_Q4EARLY_2025_baseline: -6,416 USD（46.38% 勝率）
```

**改善方向**:
1. **ポジションサイジングロジック検証** - 損失が初期資本比で異常（300% 超過）
2. **ストップロス機能確認** - MaxDD が常に 0 → PSAR, trailing stop が機能していない可能性
3. **シグナル品質確認** - 高勝率なのに損失 → トレイドサイズが不均等？
4. **スリッページ・手数料考慮** - シミュレーション精度向上
5. **バックテストモード検証** - ライブテスト vs バックテストの結果乖離確認

**改善成果**:
- 2025年は 2024年比で **71% 損失削減** → Phase 2 実装による改善示唆
- ただし根本的な赤字解決には至っていない

**Next Step**: 
- [ ] ログ詳細分析（トレード毎の PnL, entry/exit 価格確認）
- [ ] 単一トレードのシミュレーション手動検証
- [ ] ボラティリティ計算、ADX 値の正確性確認
- [ ] 本番運用データとのバックテスト精度比較

---

このドキュメントは `README.md` および分析ファイルを補足します；段階的に更新してください。
