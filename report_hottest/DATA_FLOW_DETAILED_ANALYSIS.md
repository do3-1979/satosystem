# ホットテスト データフロー詳細解析

**検証日**: 2025年12月13日  
**検証対象**: `bot.py`, `price_data_management.py`, `trading_strategy.py`, `bybit_exchange.py`

---

## 📊 ホットテスト実行時のデータフロー

### メインループ（bot.py L328-329）

```python
else:  # ホットテストモード (back_test=0)
    self.price_data_management.update_price_data()
    
# メインループ末尾（bot.py L326）
if back_test_mode == 0:
    time.sleep(self.bot_operation_cycle)  # 60秒待機 → 1分ごとに実行
```

---

## 🔍 price_data_management.update_price_data() のデータ取得

### フェーズ1: 2つのデータソースから取得（L376-393）

```
【確定データ取得】
tmp_ohlcv_data_1 = self.exchange.fetch_ohlcv(start_epoch, end_epoch, self.time_frame)
                  └─ bybit_exchange.fetch_ohlcv(start_epoch, end_epoch, 120)
                     └─ ccxt.fetch_ohlcv(timeframe=120分)
                        └─ 「確定した過去の2時間足」のみ返す ✓

last_ohlcv_data = tmp_ohlcv_data_1[-1]  # 最新の確定2時間足
```

```
【リアルタイムデータ取得】
self.latest_ohlcv_data = self.exchange.fetch_latest_ohlcv(self.time_frame)
                        └─ bybit_exchange.fetch_latest_ohlcv(120)
                           └─ ccxt.fetch_ohlcv()[-1]
                              └─ 「現在進行中の未確定2時間足」を返す

self.ticker = self.exchange.fetch_ticker()
            └─ bybit_exchange.fetch_ticker()
               └─ ccxt.fetch_ticker(symbol)
                  └─ ticker["last"]  ← 「リアルタイム価格」✓

self.volume = self.latest_ohlcv_data[0]['Volume']
```

---

## 🎯 ドンチャン判定（L410-420）

### 常時実施（毎回のループで実行）

```python
# 常時実施のドンチャン判定
ohlcv_data = self.get_ohlcv_data_by_time_frame(self.time_frame)
             # ↓ self.ohlcv_data 内部に保存された「確定済み2時間足データ」を取得

dc, high, low = self.__evaluate_donchian(ohlcv_data, self.ticker)
                # ┌─ 確定した過去足の高値/安値を取得
                # └─ リアルタイム価格と比較 ← fetch_ticker()
```

### ドンチャン計算ロジック（L582-610）

```python
def __evaluate_donchian(self, ohlcv_data, price):
    highest = max(i['high_price'] for i in ohlcv_data[(-1 * buy_term):])
              # ↑ 過去20本の確定足から最高値

    if price > highest:  # ← リアルタイム価格がブレイク
        side = 'BUY'     # ← シグナル発生！

    return side, highest, lowest
```

**データソース内訳**:
- `ohlcv_data`: 確定した過去2時間足（20本分） ✓
- `price (self.ticker)`: リアルタイム価格（fetch_ticker()） ✓

---

## 🎯 PVO判定（L423-432）

### 条件付きで実施（新規2時間足確定時のみ）

```python
# 新しい2時間足が確定したかチェック
if self.prev_close_time < last_ohlcv_data['close_time']:
   # ↑ 前回のclose_time < 新しいclose_time
   # ↓ 新規2時間足が確定した時のみ以下を実行

    volume = last_ohlcv_data['Volume']
            # ↓ 最新の確定2時間足のVolume

    ohlcv_data = self.get_ohlcv_data_by_time_frame(self.time_frame)
                # ↓ 同じ「確定済み2時間足データ」

    pvo, value = self.__evaluate_pvo(ohlcv_data, volume)
                # └─ 確定足データのみで計算

    self.signals['pvo']['signal'] = pvo
                # ↓ シグナル値を更新
```

**データソース内訳**:
- `ohlcv_data`: 確定した過去2時間足 ✓
- `volume`: 確定2時間足のVolume ✓

---

## ⚠️ 検出された非同期性

### タイミングの不一致

```
【時刻: 10:00 の状況】

前の確定2時間足: 08:00-10:00（既確定）
現在進行中の足: 10:00-12:00（未確定）

1分ごとの実行 (10:00):
   ┌─ ドンチャン判定
   │  ├─ ohlcv_data: 過去足（08:00-10:00）← 確定 ✓
   │  └─ price: fetch_ticker() ← リアルタイム ✓
   │     → BUY シグナル発生 ✓
   │
   └─ PVO判定
      ├─ 新規足確定チェック:
      │  prev_close_time (10:00) < last_close_time (10:00)?
      │  → NO、一致している
      │  → PVO計算はスキップ
      │  → 前回値のまま（08:00-10:00足の値）
      │
      └─ 結果: PVO シグナルなし ✗

【最終判定】
if donchian['signal'] and pvo['signal']:  # ✓ and ✗ = ✗
    return 'ENTRY'
    
→ エントリーなし
```

---

## 🔄 データ更新の流れ

### スタート（初回実行）

```
時刻: 08:00
- prev_close_time = 0
- fetch_ohlcv() → 08:00-10:00 の確定足を取得
- prev_close_time = 10:00（最新確定足の終了時刻）
- PVO計算実行（初回）
```

### ホットテスト実行 1分目～60分目（08:01～09:00）

```
時刻: 08:01～09:00
- prev_close_time = 10:00（変わらず）
- fetch_ohlcv() → まだ 08:00-10:00 の確定足のみ（新しい足はない）
- last_ohlcv_data['close_time'] = 10:00
- if 10:00 < 10:00: false  → PVO計算スキップ

毎分:
- ドンチャン判定: リアルタイム価格で常時更新 ✓
- PVO判定: 前回値のまま ✗
```

### 120分経過（09:00時点で新規足確定）

```
時刻: 10:00 (120分経過)
- fetch_ohlcv() → 新しい確定足（10:00-12:00）が返される
- last_ohlcv_data['close_time'] = 12:00（新しい確定足の終了時刻）
- if 10:00 < 12:00: true  → PVO計算実行！
- prev_close_time = 12:00（更新）

BUT:
- ドンチャンが BUY シグナルを出したのは、09:xx 分の時点
- PVO計算が実行されるのは、12:00の確定まで待つ必要
- 結果: 両者が同時成立しない
```

---

## 📋 get_ticker() の実装

### 定義（price_data_management.py L87-94）

```python
def get_ticker(self):
    return self.ticker  # L393 で fetch_ticker() の値が代入されている
```

### 値の設定箇所（price_data_management.py L393）

```python
self.ticker = self.exchange.fetch_ticker()
```

### fetch_ticker() の実装（bybit_exchange.py L443-467）

```python
def fetch_ticker(self):
    # ダミーモード対応
    if self.is_dummy_mode:
        return 100000 + random.uniform(-1000, 1000)
    
    # ライブモード
    ticker = self.exchange.fetch_ticker(symbol)
    price = ticker["last"]
    return price  # ← リアルタイムの最新価格
```

**結論**: `get_ticker()` は **fetch_ticker()** から取得 ✓
- **ドンチャン判定に使用**: YES ✓
- fetch_latest_ohlcv() ではなく fetch_ticker() を使用

---

## 🎯 ドンチャン vs PVO の比較

| 項目 | ドンチャン | PVO |
|------|---------|-----|
| **判定頻度** | 毎分（常時） | 120分ごと（新規足確定時） |
| **高値・安値の出典** | 確定足 | 確定足 |
| **現在価格の出典** | リアルタイム（fetch_ticker） | 確定足のVolume |
| **更新タイミング** | 毎分 | 新規足確定時 |
| **ホットテストでの挙動** | ✓ 常時判定 | ✗ 遅延更新 |

---

## 🔴 ホットテストで0エントリーの真の原因

### 根本的な設計の問題

```
ドンチャン判定:
  └─ 過去足の高値 vs リアルタイム価格で判定
     └─ リアルタイムに反応 ✓

PVO判定:
  └─ 確定足のボリュームのみで判定
     └─ 確定までの120分、更新されない ✗

結果:
  └─ ドンチャンが反応しても、PVOは前回値
  └─ 両条件が同時成立しない
  └─ → 108時間でエントリー 0回
```

### バックテストで2エントリーある理由

```
バックテスト時:
  └─ 過去データで確定済み
  └─ ドンチャン判定: 確定足の高値 vs 確定足の終値
  └─ PVO判定: 確定足のVolume
  └─ 両者が同期している ✓
  └─ → 2エントリー検出
```

---

## ✅ 最終判定

### 質問1: 最新値取得は bot.py で get_ticker() を使っているか？

✅ **YES**
```python
price = self.price_data_management.get_ticker()  # bot.py L169
```

### 質問2: get_ticker() の中身は fetch_latest_ohlcv() か？

❌ **NO**
```python
get_ticker() → self.ticker（L87）
self.ticker は L393 で fetch_ticker() から設定される

fetch_ticker() = ccxt.fetch_ticker(symbol)["last"]
                ≠ fetch_latest_ohlcv()
```

### 質問3: ドンチャンは fetch_latest_ohlcv() で判定している？

❌ **NO**
```python
ドンチャン判定:
  - 確定足の高値/安値取得: self.get_ohlcv_data_by_time_frame()
  - リアルタイム価格: self.ticker (= fetch_ticker()) ✓
  
ドンチャンは「確定足」と「リアルタイム価格」で判定
```

### 質問4: PVO は fetch_ohlcv() で判定している？

✅ **YES**
```python
PVO判定 (L423-432):
  - 新規足確定時のみ実行
  - volume = last_ohlcv_data['Volume']  ← fetch_ohlcv()の値
  - ohlcv_data = self.get_ohlcv_data_by_time_frame()  ← 確定足
  
PVOは「確定足のみ」で判定
```

---

## 📌 ホットテストの実装の核心

### 階層的な役割分担

```
【API呼び出しの層】
1. fetch_ohlcv(start, end, timeframe)
   └─ 過去のデータ範囲から確定足のみ取得
   └─ 毎回呼び出し（キャッシュ機構あり）

2. fetch_latest_ohlcv(timeframe)
   └─ 最新1本の足を取得（未確定を含む）
   └─ 補助的に使用（Volumeなど）

3. fetch_ticker()
   └─ 単純な最新価格
   └─ ドンチャン判定に使用 ✓

【判定ロジックの層】
1. ドンチャン判定
   └─ 確定足 + リアルタイム価格
   └─ 毎分実行

2. PVO判定
   └─ 確定足のみ
   └─ 新規足確定時に実行

【問題点】
   └─ 判定の「時間的同期」が取れていない
```

---

## 🛠️ 推奨される修正

### 修正案 A: PVO を毎分評価に変更

```python
def update_price_data(self):
    # ...
    
    # ドンチャン判定（現在通り）
    ohlcv_data = self.get_ohlcv_data_by_time_frame(self.time_frame)
    dc, high, low = self.__evaluate_donchian(ohlcv_data, self.ticker)
    
    # 【修正】PVO も毎分評価
    volume = self.volume  # 最新のVolume
    pvo, value = self.__evaluate_pvo(ohlcv_data, volume)  # 毎分実行
    self.signals['pvo']['signal'] = pvo
    
    # ボラティリティは新規足確定時のみ
    if self.prev_close_time < last_ohlcv_data['close_time']:
        self.volatility = self.calcurate_volatility(tmp_ohlcv_data_1)
        self.prev_close_time = last_ohlcv_data['close_time']
        # OHLCVデータ更新
        self.append_ohlcv_data_by_time_frame(last_ohlcv_data, self.time_frame)
        self.del_ohlcv_data_by_time_frame(self.time_frame)
```

### 修正案 B: ドンチャン・PVO 共に確定足のみで評価

```python
def update_price_data(self):
    # ...
    
    # 新規足確定時のみ判定を実行
    if self.prev_close_time < last_ohlcv_data['close_time']:
        ohlcv_data = self.get_ohlcv_data_by_time_frame(self.time_frame)
        
        # ドンチャン判定（足の終値で判定）
        close_price = ohlcv_data[-1]['close_price']
        dc, high, low = self.__evaluate_donchian(ohlcv_data, close_price)
        self.signals['donchian']['signal'] = (dc != 'None')
        
        # PVO判定
        volume = last_ohlcv_data['Volume']
        pvo, value = self.__evaluate_pvo(ohlcv_data, volume)
        self.signals['pvo']['signal'] = pvo
        
        # データ更新
        self.prev_close_time = last_ohlcv_data['close_time']
        self.append_ohlcv_data_by_time_frame(last_ohlcv_data, self.time_frame)
        self.del_ohlcv_data_by_time_frame(self.time_frame)
```

---

**検証者**: Copilot  
**最終結論**: 🔴 **ドンチャン・PVO の時間的非同期が根本原因**

ホットテストで 0 エントリーの直接的理由は、2つの判定ロジックが異なる「タイミング」で実行されているため、両シグナルが同時成立しないこと。
