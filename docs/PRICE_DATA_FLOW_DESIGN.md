# 価格データフロー設計書

## 概要

本ドキュメントは、satosystem における**バックテスト時**と**ホットテスト時**（ペーパートレード・本番取引）の価格データ取得・処理フローを説明します。ソースコード (src/*.py) に従って、現在の実装状態を記述しています。

---

## 1. ホットテストモード（back_test = 0）の流れ【実装現状】

### 1.1 概要

ホットテストモードは、**リアルタイムデータに基づいて**売買判定・実行を行うモードです。

| 項目 | 値 |
|-----|-----|
| **実行単位** | 60秒ごと（`bot_operation_cycle` = 60）|
| **データソース** | Bybit REST API（実データ）|
| **価格タイムフレーム** | 240分足（4時間足、config.ini の `time_frame=240` に従う）|
| **PSAR タイムフレーム** | 240分足（config.ini の `psar_time_frame=240` に従う）|
| **取引モード** | ペーパートレード（`hot_test_dummy_mode=1`） or 本番取引（`hot_test_dummy_mode=0`）|

### 1.2 データ取得フロー

#### メインループ（bot.run()）

```
while True:
    ├─ price_data_management.update_price_data()  # 60秒ごとに呼び出し
    ├─ time.sleep(60)  # 60秒待機
    └─ [ループ継続]
```

#### update_price_data() 内の処理（3つの API 呼び出し）

```python
def update_price_data(self):
    # (1) PSAR用 240分足 - fetch_latest_ohlcv(self.psar_time_frame)
    tmp_ohlcv_data_2 = self.exchange.fetch_latest_ohlcv(240)  # config.ini から 240 を取得
    self.set_ohlcv_data_by_time_frame(tmp_ohlcv_data_2, 240)
    
    # (2) メイン軸 240分足 - fetch_ohlcv(start_epoch, end_epoch, self.time_frame)
    tmp_ohlcv_data_1 = self.exchange.fetch_ohlcv(start_epoch, end_epoch, 240)
    last_ohlcv_data = tmp_ohlcv_data_1[-1]  # 最新行
    
    # (3) 現在値取得 - fetch_ticker()
    self.ticker = self.exchange.fetch_ticker()  # float値
    
    # 240分足の終値時刻が更新された場合のみシグナル再計算
    if self.prev_close_time < last_ohlcv_data['close_time']:
        # ボラティリティ更新
        self.volatility = self.calcurate_volatility(tmp_ohlcv_data_1)
        # OHLCV リスト管理
        self.append_ohlcv_data_by_time_frame(last_ohlcv_data, 240)
        self.del_ohlcv_data_by_time_frame(240)
```

### 1.3 API 呼び出し詳細

#### (1) fetch_ticker() - 現在値取得

| 項目 | 値 |
|------|-----|
| **API エンドポイント** | Bybit `/v5/market/ticker` |
| **呼び出し元** | `price_data_management.update_price_data()` |
| **目的** | 現在値（float）を取得 |
| **リトライ** | 3回（指数バックオフ：1秒→2秒→4秒、最大30秒）|
| **戻り値** | float（例：42750.5）|
| **実装ファイル** | [src/bybit_exchange.py](src/bybit_exchange.py#L852) |

```python
# ホットテスト時の実装
ticker = self.exchange.fetch_ticker(symbol, params={'timeout': 10000})
price = ticker["last"]  # float値
return price
```

#### (2) fetch_latest_ohlcv(240) - 最新確定足取得

| 項目 | 値 |
|------|-----|
| **API エンドポイント** | Bybit `/v5/market/kline` |
| **タイムフレーム** | 240分（4時間足、config.ini から取得）|
| **呼び出し元** | `price_data_management.update_price_data()` |
| **呼び出し頻度** | 60秒ごと |
| **目的** | 確定した最新足データ（OHLCV+Volume）を取得 |
| **データ完全性** | API から最大200本の履歴を取得し、最新の1本を抽出 |
| **リトライ** | 3回（指数バックオフ）|
| **戻り値** | List[Dict]（長さ1）：`[{'close_time': ..., 'close_price': ..., 'Volume': ...}]` |
| **実装ファイル** | [src/bybit_exchange.py](src/bybit_exchange.py#L785) |

```python
# 実装例（live_trading_mode）
ohlcv = self.exchange.fetch_ohlcv(
    symbol='BTC/USD:BTC',
    timeframe='4h',  # 240分足
    params={'timeout': 10000}
)
latest_ohlcv = ohlcv[-1]  # 最新の1本を抽出
# 返却: [{close_time, close_time_dt, open_price, high_price, low_price, close_price, Volume}]
```

#### (3) fetch_ohlcv(start_epoch, end_epoch, 240) - 履歴データ取得

| 項目 | 値 |
|------|-----|
| **API エンドポイント** | Bybit `/v5/market/kline` |
| **タイムフレーム** | 240分（config.ini から取得）|
| **呼び出し元** | `price_data_management.update_price_data()` |
| **呼び出し頻度** | 60秒ごと（常に最新の期間データを再取得）|
| **目的** | バックテスト時と同様に、指定期間内のすべての確定足を取得 |
| **データ完全性** | 期間内のすべてのローソク足を取得（最大200本ずつ、複数回のAPI呼び出し） |
| **リトライ** | 3回（指数バックオフ）|
| **戻り値** | List[Dict]：`[{close_time, open_price, high_price, low_price, close_price, Volume}, ...]` |
| **実装ファイル** | [src/bybit_exchange.py](src/bybit_exchange.py#L698) |

```python
# 実装例（ホットテスト）
ohlcv_data = self.exchange.fetch_ohlcv(
    symbol='BTC/USD:BTC',
    timeframe='4h',
    since=start_epoch * 1000,  # bybit はミリ秒
    params={'timeout': 10000}
)
# 返却: [240分足のすべての足（直近から開始日まで）]
```

### 1.4 データ整合性・タイムフレーム管理

#### ohlcv_data 構造

```python
# price_data_management.py の初期化時
self.ohlcv_data = [
    {"time_frame": 240, "data": [...]},      # メイン軸 240分足
    {"time_frame": 240, "data": [...]}       # PSAR 用 240分足
]
```

**重要**: config.ini に従って、両タイムフレームとも **240分足** が採用されます

```ini
[Market]
time_frame = 240          # メイン軸

[RiskManagement]
psar_time_frame = 240    # PSAR 用
```

#### 確定値 vs 未確定値の分離

```python
# 確定済みデータ（シグナル計算に使用）
self.ohlcv_data[0]['data']  # 最新足の1つ前までの確定足

# 未確定データ（リアルタイム価格表示用）
self.latest_ohlcv_data  # 現在形成中の最新足（毎60秒更新）
self.ticker  # 最新の現在値（float）
```

---

## 2. バックテストモード（back_test = 1）の流れ【実装現状】

### 2.1 概要

バックテストモードは、**過去データ**を用いて戦略を検証するモードです。

| 項目 | 値 |
|------|-----|
| **実行単位** | バッチ処理（全期間を一括処理）|
| **データソース** | SQLite キャッシュ（`ohlcv_cache.db`）|
| **価格タイムフレーム** | 240分足（config.ini の `time_frame=240` に従う）|
| **PSAR タイムフレーム** | 240分足（config.ini の `psar_time_frame=240` に従う）|
| **処理方式** | 仮想時刻進行（`progress_time` を 240分ずつ進める）|

### 2.2 データ取得フロー

#### 初期化フェーズ（bot.run()）

```python
if back_test_mode == 1:
    self.price_data_management.initialise_back_test_ohlcv_data()
    # SQLiteキャッシュから指定期間のすべてのデータを一括取得
```

[src/price_data_management.py](src/price_data_management.py#L554)

```python
def initialise_back_test_ohlcv_data(self):
    """バックテスト用データ初期化"""
    start_epoch = Config.get_start_epoch()
    end_epoch = Config.get_end_epoch()
    
    # SQLiteキャッシュから期間内のデータを取得
    ohlcv_data_cache = self.cache.get_ohlcv_data_partial(
        self.market,
        240,  # time_frame (config.ini から)
        start_epoch,
        end_epoch
    )
    # back_test_ohlcv_data に展開
    self.back_test_ohlcv_data[0]['data'] = ohlcv_data_cache
```

#### メインループ（bot.run()）

```python
while True:
    is_end = self.price_data_management.update_price_data_backtest()
    if is_end:
        break
    # シグナル計算・売買判定・ポジション更新
```

[src/price_data_management.py](src/price_data_management.py#L202)

```python
def update_price_data_backtest(self):
    """バックテスト用価格データ更新"""
    # back_test_ohlcv_data から 240分足単位でデータを進める
    # progress_time を 240分ずつ進める
    # 終端に到達したら is_end = True を返す
```

### 2.3 データソース

| 項目 | 詳細 |
|------|------|
| **ファイル** | `ohlcv_cache.db`（SQLite）|
| **テーブル** | `ohlcv_{symbol}` （例：`ohlcv_BTC_USDT`）|
| **カラム** | `timestamp, open, high, low, close, volume, timeframe` |
| **更新方式** | ホットテスト時に新規データが INSERT OR REPLACE される |
| **参照方式** | バックテスト時に期間指定で SELECT（`ohlcv_cache_inspector.py` で分析可能）|

---

## 3. ホットテスト vs バックテスト 比較表

| 項目 | ホットテスト | バックテスト |
|------|-----------|----------|
| **実行モード** | リアルタイム | バッチ |
| **データソース** | Bybit API | SQLite キャッシュ |
| **タイムフレーム** | 240分足（config.ini） | 240分足（config.ini） |
| **実行頻度** | 60秒ごと | 全期間一括（バッチ） |
| **価格タイプ** | 実データ | 過去データ |
| **ダミー価格** | 実運用時のみ実データ | ランダムダミー |
| **ダミー取引** | ペーパーモード時 | 常にダミー取引 |
| **出力** | リアルタイムログ | JSON サマリー + グラフ |
| **データ完全性** | 最大200本の履歴のみ | 完全（キャッシュに依存） |

---

## 4. 重要な設計要素

### 4.1 Config-Driven タイムフレーム管理

**すべてのタイムフレームは config.ini から取得されます**：

```python
# config.py
class Config:
    @classmethod
    def get_time_frame(cls):
        """時間軸を取得（Market セクション）"""
        return int(cls.config['Market']['time_frame'])  # 240
    
    @classmethod
    def get_psar_time_frame(cls):
        """PSAR用時間軸を取得（RiskManagement セクション）"""
        return int(cls.config['RiskManagement']['psar_time_frame'])  # 240
```

**ハードコード箇所**: テストコード内のみ（`bybit_exchange.py` 行932, `bitget_exchange.py` 行1110）

### 4.2 複数タイムフレームの同期

**現在の実装**: 240分足メイン軸 + 240分足PSAR用（同一）

```python
# price_data_management.py の ohlcv_data 構造
self.ohlcv_data = [
    {"time_frame": 240, "data": [...]},      # 240分足
    {"time_frame": 240, "data": [...]}       # PSAR用 240分足
]
```

**シグナル再計算トリガー**: メイン軸（240分足）が新規確定した時のみ

```python
if self.prev_close_time < last_ohlcv_data['close_time']:
    # ボラティリティ更新
    # OHLCV リスト更新
    # シグナル再計算（Donchian, PVO, ADX）
```

### 4.3 エラーハンドリング・リトライ戦略

**API リトライ**（すべての fetch_* メソッド）：

```python
max_retries = 3
wait_time = min(2 ** retry_count, 30)  # 指数バックオフ：1秒→2秒→4秒...最大30秒
```

**フォールバック（エントリー注文時）**：

```
成行注文 → 失敗
    ↓
指値注文（スリッページ漸増） × 4回
    ↓
最終成行注文 → 失敗時は例外
```

---

## 5. ホットテストの実行フロー（詳細）

### 5.1 ペーパートレード（hot_test_dummy_mode=1）

```
config.ini:
    back_test = 0
    hot_test_dummy_mode = 1

実行:
    python src/bot.py
    
結果:
    ✓ 実API価格で価格取得
    ✓ ダミー取引（ポジション情報のみ更新、実注文なし）
    ✓ ログに全取引記録
```

### 5.2 本番取引（hot_test_dummy_mode=0）

```
config.ini:
    back_test = 0
    hot_test_dummy_mode = 0

実行:
    python src/bot.py
    
確認プロンプト:
    "実際の取引を実行します。[Y/N]"
    
結果:
    ✓ 実API価格で価格取得
    ✓ 実取引実行（Bybit API へ注文発行）
    ✓ ログに全取引記録
```

---

## 6. 今後の拡張性

### 6.1 複数シンボル対応

現在は単一シンボル（BTC/USD, BTC/USDT など）に対応。複数シンボル対応には：

- PriceDataManagement の Singleton を解除
- シンボルごとの独立したインスタンス管理
- ohlcv_cache での シンボル・タイムフレーム複合キー管理

### 6.2 動的タイムフレーム切り替え

市場変動に応じたタイムフレーム動的変更は、以下の検討が必要：

- Config 値の動的更新（現在は起動時のみ読み込み）
- ohlcv_data の再初期化・バリデーション
- シグナル計算の継続性保証

### 6.3 リアルタイムデータ キャッシュ最適化

ホットテスト実行中の SQLite キャッシュ蓄積を活用：

- 運用中に取得した実データをキャッシュに保存
- 中断・再開時にキャッシュから復帰
- バックテスト時の参考データとして活用

---

## 参考資料

- [ARCHITECTURE_OVERVIEW.md](ARCHITECTURE_OVERVIEW.md) - システムアーキテクチャ・モジュール構成
- [DEVELOPMENT_RULES.md](DEVELOPMENT_RULES.md) - 開発ルール・実行モード設定
- [docs/analysis/src/price_data_management.json](docs/analysis/src/price_data_management.json) - PriceDataManagement クラス分析
- [docs/analysis/src/bybit_exchange.json](docs/analysis/src/bybit_exchange.json) - BybitExchange クラス分析

**ドキュメント更新日**: 2026-01-03  
**ソースコード基準**: gen2 ブランチ（2026-01-03時点）
