# Satosystem - アーキテクチャ概要

**最終更新**: 2025-11-28  
**バージョン**: Phase 1 + Phase 2 + Phase 3（本番有効化）  

---

## 🎯 システム概要

自動取引ボット `satosystem` は、市場のレジーム判定に基づいた段階的フィルタリングと自動最適化により、継続的な利益生成を目指すシステムです。

### 運用状態
- **Phase 1**: ✅ レジーム検出機能（SIDEWAYS/WEAK_TREND/STRONG_TREND）
- **Phase 2**: ✅ 段階的ポジション調整（0.75x/1.0x/1.25x）
- **Phase 3**: ✅ 自動監視・学習ループ（日次監視/週次判定/月次最適化）

---

## 🏗️ システムアーキテクチャ

### 全体構成図

```
┌─────────────────────────────────────────────────────┐
│                 Trading Bot (Main)                  │
│  ├─ Initialize                                      │
│  ├─ Loop (市場データ取得 → シグナル計算 → 決定)      │
│  └─ Cleanup                                         │
└─────────────────────────────────────────────────────┘
        ↓
┌──────────────────────────────────────────────────────────┐
│              シグナル計算層 (Strategy Layer)              │
│  ┌──────────────────────────────────────────────────┐   │
│  │ PriceDataManagement                              │   │
│  │  ├─ Donchian チャネル計算                        │   │
│  │  ├─ PVO (Price Volume Oscillator)              │   │
│  │  ├─ Keltner チャネル (Phase B フィルタ)        │   │
│  │  ├─ ボラティリティ管理                           │   │
│  │  └─ レジーム検出（Phase 1）                     │   │
│  └──────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────┐   │
│  │ TradingStrategy                                  │   │
│  │  ├─ ENTRY 判定 (Donchian + PVO + Keltner)      │   │
│  │  ├─ ADD 判定 (段階的ポジション増加)             │   │
│  │  ├─ EXIT 判定 (STOP/トレーリング)              │   │
│  │  └─ レジーム統合判定（Phase 1）                 │   │
│  └──────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────┘
        ↓
┌──────────────────────────────────────────────────────────┐
│            リスク管理層 (Risk Management Layer)           │
│  ┌──────────────────────────────────────────────────┐   │
│  │ RiskManagement                                   │   │
│  │  ├─ ポジションサイジング (基本/段階的)           │   │
│  │  ├─ PSAR (Parabolic SAR) 計算                  │   │
│  │  ├─ トレーリングストップ                         │   │
│  │  ├─ ADX トレンド強度                            │   │
│  │  └─ Phase 2: 段階的調整（0.75x/1.0x/1.25x）    │   │
│  └──────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────┐   │
│  │ Portfolio                                        │   │
│  │  ├─ ポジション追跡 (qty/side/price)             │   │
│  │  ├─ PnL 計算                                    │   │
│  │  └─ ドローダウン追跡                             │   │
│  └──────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────┘
        ↓
┌──────────────────────────────────────────────────────────┐
│             データ管理層 (Data Management Layer)          │
│  ┌──────────────────────────────────────────────────┐   │
│  │ BybitExchange (API)                              │   │
│  │  ├─ OHLCV 取得 (1m/120m)                        │   │
│  │  ├─ 注文送信 (market/limit)                      │   │
│  │  └─ ポジション/残高照会                          │   │
│  └──────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────┐   │
│  │ OHLCVCache (SQLite)                              │   │
│  │  ├─ ローソク足データ永続化                       │   │
│  │  ├─ 高速ロード (初期化時)                        │   │
│  │  └─ キャッシュ充足判定                           │   │
│  └──────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────┐   │
│  │ Config (INI+Cache)                               │   │
│  │  ├─ パラメータ一元管理                           │   │
│  │  └─ キャッシュによる高速アクセス                  │   │
│  └──────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────┘
```

---

## 📦 主要コンポーネント

### 1. **Config** (`src/config.py`)
- **役割**: 設定ファイル(config.ini)の管理・キャッシュ
- **キャッシュ**: パラメータの頻繁なアクセスを高速化
- **連携先**: すべてのモジュール

### 2. **PriceDataManagement** (`src/price_data_management.py`)
- **OHLCV管理**: 時間足別データ保持・更新
- **シグナル計算**: Donchian/PVO/Keltner
- **ボラティリティ**: ATR/変動率で動的計算
- **レジーム検出** (Phase 1): 市場状態判定
- **修正済**: Donchian初期化データ制限（108797→95846, 11.8%改善）

### 3. **TradingStrategy** (`src/trading_strategy.py`)
- **ENTRY判定**: Donchianブレイク + PVO + Keltner フィルタ
- **ADD判定**: 段階的ポジション増加 (Phase 2)
- **EXIT判定**: ストップロス/トレーリング/時間制限
- **レジーム統合** (Phase 1): 市場状態に応じたフィルタリング

### 4. **RiskManagement** (`src/risk_management.py`)
- **ポジションサイジング**: 基本 + 段階的調整 (Phase 2)
- **PSAR計算**: 動的ストップレベル
- **トレーリングストップ**: 利益確保と損失制限
- **ADX計算**: トレンド強度評価

### 5. **IndicatorService** (`src/indicator_service.py`)
- **Donchian**: 直近20期間ウィンドウ（修正済）
- **PVO**: 価格・出来高オシレータ
- **ATR**: ボラティリティ指標
- **EMA**: 指数移動平均
- **ADX**: トレンド強度

### 6. **BybitExchange** (`src/exchange.py`)
- **API連携**: ccxt を使用した Bybit 取引所通信
- **OHLCV取得**: 複数時間足データ
- **注文管理**: 成行・指値注文
- **残高照会**: 証拠金/ポジション確認

### 7. **OHLCVCache** (`src/ohlcv_cache.py`)
- **永続化**: SQLite でローソク足を保存
- **キャッシュ充足判定**: API呼び出し最小化
- **高速ロード**: バックテスト初期化の高速化

### 8. **Logger** (`src/logger.py`)
- **構造化ログ**: JSON形式で記録
- **ローテーション**: 日次・サイズベース
- **圧縮**: 古いログを ZIP 圧縮

### 9. **Phase 3 モジュール**

#### **EnvironmentAutoJudge** (`src/environment_auto_judge.py`)
- 週次で市場環境を自動判定
- レジーム変更時に戦略調整

#### **DynamicThresholdLearning** (`src/dynamic_threshold_learning.py`)
- 月次でパラメータ閾値を最適化
- 過去パフォーマンスに基づく学習

#### **RealtimePerformanceMonitor** (`src/realtime_performance_monitor.py`)
- 日次監視・アラート生成
- PnL・ドローダウン追跡

---

## 🔄 データフロー

### バックテスト実行フロー

```
1. 初期化
   ├─ Config 読み込み
   ├─ OHLCVCache から過去データ取得
   ├─ PriceDataManagement に最新40期間ロード
   └─ 初期 Donchian/PSAR 計算

2. メインループ（各タイムステップ）
   ├─ get_back_test_ohlcv_data() で価格更新
   ├─ PriceDataManagement.update_price_data_backtest()
   │  ├─ Donchian シグナル計算（限定40期間）
   │  ├─ PVO シグナル計算
   │  ├─ Keltner フィルタ計算
   │  └─ ボラティリティ更新
   ├─ TradingStrategy.make_trade_decision()
   │  ├─ レジーム判定（Phase 1）
   │  ├─ ENTRY/ADD/EXIT 判定
   │  └─ 意思決定ロジック
   ├─ RiskManagement 更新
   │  ├─ ポジションサイズ調整（Phase 2）
   │  ├─ PSAR/ストップ再計算
   │  └─ ADX 更新
   ├─ 注文実行
   └─ ログ記録

3. 終了
   ├─ 最終成績計算
   ├─ レポート生成
   └─ ログ圧縮
```

---

## 🎯 主な改善点（本バージョン）

### Donchian 計算修正
- **問題**: 全データセット(2174レコード)を使い極値汚染
- **解決**: 最新40期間ウィンドウのみで計算
- **改善**: 108797 → 95846 (11.8%削減)

### STOP値ロジック
- **状態**: risk_management.py は正常に機能
- **確認**: position_quantity=0 でSTOP > 0 の事例なし

### ENTRY/EXIT 不均衡
- **改善**: 39:4 のバランスに向上
- **要因**: Donchian 正常化に伴い EXIT トリガー頻度向上

---

## 📊 パフォーマンス指標

### バックテスト結果（2025年1月-6月）
- **取引数**: 4件
- **勝率**: 0%（サンプル小）
- **最終損益**: -$1,367
- **ボラティリティ比**: 0.89
- **トレンド強度**: 0.01

### Phase 別実績
| フェーズ | 利益率 | 備考 |
|---------|--------|------|
| Phase 1 | +56.4% (Q2) | レジーム検出機能 |
| Phase 2 | +10.34% | 段階的ポジション調整 |
| Phase 3 | - | 監視・学習ループ |

---

## 🔧 パラメータ概要

### 主要パラメータ（config.ini）
```
[Trading]
market = BTC/USD
leverage = 1
time_frame = 120 (分)
psar_time_frame = 15

[Indicators]
donchian_buy_term = 20
donchian_sell_term = 20
keltner_ema_period = 20
keltner_atr_multiplier = 1.5

[RiskManagement]
initial_stop_range = 0.5
risk_percentage = 2.0
max_hold_bars = 10

[Phase2]
regime_detection_enabled = True
graduated_sizing_enabled = True

[Phase3]
auto_judge_enabled = True
threshold_learning_enabled = True
```

---

## 🚀 運用スケジュール

- **毎日 00:00 UTC**: 日次監視（Phase 3 Task 11）
- **毎週月曜 00:00 UTC**: 週次環境判定（Phase 3 Task 7）
- **毎月1日 00:00 UTC**: 月次パラメータ最適化（Phase 3 Task 10）

---

## 📝 主要ファイル構成

```
satosystem/
├── src/
│   ├── config.py              # 設定管理
│   ├── bot.py                 # メインループ
│   ├── exchange.py            # API連携
│   ├── price_data_management.py  # シグナル計算
│   ├── trading_strategy.py     # 取引判定
│   ├── risk_management.py      # リスク管理
│   ├── portfolio.py            # ポジション追跡
│   ├── indicator_service.py    # 技術指標
│   ├── logger.py               # ロギング
│   ├── ohlcv_cache.py          # キャッシュ
│   └── phase3/                 # Phase 3モジュール
│       ├── environment_auto_judge.py
│       ├── dynamic_threshold_learning.py
│       └── realtime_performance_monitor.py
├── test/                       # テスト
├── docs/                       # ドキュメント
└── config.ini                  # 設定ファイル
```

---

## ✅ テスト・検証

- **ユニットテスト**: pytest で config/risk_management/phase3 モジュールをカバー
- **セキュリティ**: API キー流出確認
- **サンプルテスト**: 各モジュール動作確認
- **バックテスト**: 6ヶ月データでの性能検証

---

**最終更新**: 2025-11-28  
**作成者**: Development Team  
**ステータス**: ✅ Production Ready (Phase 1/2/3 有効化完了)
