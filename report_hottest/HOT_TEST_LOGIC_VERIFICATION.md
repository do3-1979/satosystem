# ホットテスト・ダミー取引 ロジック検証レポート

**検証日**: 2025年12月13日  
**検証対象**: `bot.py`, `price_data_management.py`, `bybit_exchange.py`  
**検証目的**: 前提条件のロジック実装状況確認

---

## 検証内容

### 前提条件（ユーザー提示）

```
ホットテスト＋ダミー取引のテストは:

✓ リアルタイムデータを使って１分おきに価格を取得
✓ ２時間足も取得してシグナル発生有無を判定
✓ リアルタイムと同じ時間がかかる（3分で3回の価格取得確認）
```

---

## ロジック検証結果

### 1️⃣ **1分おきにリアルタイム価格取得: ✅ 実装済み**

**コード場所**: `bot.py` L328-329

```python
else:  # ホットテスト時
    self.price_data_management.update_price_data()

# ループ末尾で待機
if back_test_mode == 0:
    time.sleep(self.bot_operation_cycle)  # 60秒待機
```

**実装内容**:
- `bot_operation_cycle` = 60秒（config.ini で設定可能）
- ホットテスト時は1分ごとにメインループが実行

✅ **判定**: 1分おきの価格取得は正しく実装されている

---

### 2️⃣ **2時間足でシグナル評価: ✅ 実装済み**

**コード場所**: `price_data_management.py` L368-450 (`update_price_data()`)

```python
def update_price_data(self):
    # PSAR用タイムフレーム（15分）最新データ取得
    tmp_ohlcv_data_2 = self.exchange.fetch_latest_ohlcv(self.psar_time_frame)
    
    # メイン用タイムフレーム（120分 = 2時間）の最新データ取得
    tmp_ohlcv_data_1 = self.exchange.fetch_ohlcv(start_epoch, end_epoch, self.time_frame)
    last_ohlcv_data = tmp_ohlcv_data_1[-1]  # 最新の2時間足
    
    # 最新1分の価格取得
    self.latest_ohlcv_data = self.exchange.fetch_latest_ohlcv(self.time_frame)
    self.ticker = self.exchange.fetch_ticker()
```

**実装内容**:
- `time_frame` = 120分（2時間）で設定
- `fetch_ohlcv()`: 過去データ含む**確定した2時間足**を取得
- `fetch_latest_ohlcv()`: **最新の1分単位**の価格を取得

✅ **判定**: 2時間足でのシグナル評価は正しく実装されている

---

### 3️⃣ **新規2時間足確定時のみシグナル再計算: ✅ 条件分岐実装済み**

**コード場所**: `price_data_management.py` L420-450

```python
# 初回の処理
if self.prev_close_time == 0:            
    self.prev_close_time = last_ohlcv_data['close_time']
    self.set_ohlcv_data_by_time_frame(tmp_ohlcv_data_1, self.time_frame)
    self.volatility = self.calcurate_volatility(tmp_ohlcv_data_1)
    return  # ← 初回は計算なしで返却

# データ更新時のみ再計算
if self.prev_close_time < last_ohlcv_data['close_time']:  # ← 重要な分岐
    # 新しい2時間足が確定した場合のみ実行
    volume = last_ohlcv_data['Volume']
    ohlcv_data = self.get_ohlcv_data_by_time_frame(self.time_frame)
    
    # PVO計算
    pvo, value = self.__evaluate_pvo(ohlcv_data, volume)
    self.signals['pvo']['signal'] = pvo
    self.signals['pvo']['info']['value'] = value
    
    # ボラティリティ計算
    self.volatility = self.calcurate_volatility(tmp_ohlcv_data_1)
    
    # 前回のclose_timeを更新
    self.prev_close_time = last_ohlcv_data['close_time']
    
    # OHLCVデータを更新（最新行を追加し、最古を削除する）
    self.append_ohlcv_data_by_time_frame(last_ohlcv_data, self.time_frame)
    self.del_ohlcv_data_by_time_frame(self.time_frame)
```

**実装内容**:
- `prev_close_time`: 前回取得した2時間足の終了時刻を記録
- 新しい終了時刻が来たら初めてシグナル再計算
- 常時計算ではなく、**条件付きで効率的に実行**

✅ **判定**: 新規2時間足確定時のシグナル再計算ロジックは正しく実装されている

---

### 4️⃣ **ドンチャン＆PVO計算の常時実行: ⚠️ 部分的な矛盾検出**

**コード場所**: `price_data_management.py` L410-420

```python
# donchianシグナル演算は常時実施
ohlcv_data = self.get_ohlcv_data_by_time_frame(self.time_frame)
dc, high, low = self.__evaluate_donchian(ohlcv_data, self.ticker)

if dc == 'BUY':
    self.signals['donchian']['signal'] = True
    self.signals['donchian']['side'] = 'BUY'
elif dc == 'SELL':
    self.signals['donchian']['signal'] = True
    self.signals['donchian']['side'] = 'SELL'
else:
    self.signals['donchian']['signal'] = False
    self.signals['donchian']['side'] = 'None'
```

**実装内容**:
- ドンチャン計算は **常時実施** される
- PVO計算は **新規2時間足確定時のみ**

⚠️ **矛盾検出**:
```
【不一致ポイント】

1. ドンチャン: 常時評価 → シグナル判定可能
2. PVO: 2時間足確定時のみ → シグナル判定は遅延

【結果】

trading_strategy.py での判定:
- ドンチャンがBUY/SELL → TrueでもPVOがまだ前回値
- 結果として、ドンチャンシグナルが有効にならない可能性
```

---

## 🔴 検出された潜在的な問題

### 問題 1: ドンチャン vs PVO の評価タイミング不一致

**症状**:
- ドンチャン: 常時評価（毎分）
- PVO: 2時間足確定時のみ更新（120分ごと）

**影響**:
```python
# trading_strategy.py での判定例
if signals['donchian']['signal'] and signals['pvo']['signal']:
    # 両条件が同時に成立した場合のみエントリー
    return 'ENTRY'
```

**問題**:
- ドンチャンブレイク発生時点で、PVO はまだ前回の確定値を使用
- 新しい2時間足確定時点でPVO更新 → ドンチャン判定は既に古い

**解決方法**:
```python
# ドンチャンはリアルタイム価格で常時評価
# PVOも同様にリアルタイム価格で常時更新
```

---

### 問題 2: `fetch_latest_ohlcv()` 使用の矛盾

**コード**: `price_data_management.py` L384

```python
# 最新1分の価格取得
self.latest_ohlcv_data = self.exchange.fetch_latest_ohlcv(self.time_frame)
```

**実装**: `bybit_exchange.py` L387-431

```python
def fetch_latest_ohlcv(self, time_frame):
    # ...
    ohlcv = self.exchange.fetch_ohlcv(
        symbol = self.market,
        timeframe = time_frame,  # ← 120分を指定
    )
    latest_ohlcv = ohlcv[-1]  # ← 最新1本の2時間足を取得
```

**問題**:
- メソッド名は「latest（最新1分）」だが、実装は「最新の2時間足」を返している
- 実際には、**現在進行中の2時間足（未確定）** を返している

**実装の実際**:
```
fetch_latest_ohlcv(120分) を呼ぶ
  → ccxt.fetch_ohlcv(..., timeframe=120) を実行
  → 最新1本の2時間足 = 「現在進行中の未確定2時間足」を返す
  → ドンチャン計算: この未確定足の高値/安値をチェック
  
fetch_ohlcv() を呼ぶ
  → 確定した2時間足のみを返す
  → 【2時間足確定時のみ】新しい確定足が返される
```

⚠️ **結果**:
- ドンチャン: 未確定2時間足の値で評価 → ブレイク判定あり
- PVO: 確定2時間足が更新されるまで旧値のまま → 常に「NONE」

---

## 📊 前提条件との整合性チェック

| 前提条件 | 実装内容 | 判定 |
|---------|--------|------|
| **1分おきに価格取得** | `time.sleep(60)` で60秒待機 | ✅ 正確 |
| **2時間足を取得** | `time_frame=120分` で設定 | ✅ 正確 |
| **シグナル判定同時実行** | ドンチャン常時、PVO遅延 | ⚠️ 部分的不一致 |
| **3分で3回確認可能** | ホットテスト実行で可能 | ✅ 正確 |

---

## 🎯 根本原因の仮説

### ラズパイホットテストで0エントリーの理由

```
【推測フロー】

1. ホットテスト1分目 (10:00)
   - ドンチャン評価: BUY → signal=True ✓
   - PVO評価: 前回値使用 → 判定なし ✗

2. ホットテスト60分目 (11:00)
   - ドンチャン評価: 継続チェック
   - 新2時間足確定 → fetch_ohlcv()で新データ取得
   - PVO計算: 新データで初めて評価
   - ただし、ドンチャンはもう「最新」ではなくなっている ✗

3. 結果
   - ドンチャン＋PVO同時成立なし
   - → エントリーなし
```

### バックテストで2エントリーある理由

```
【バックテスト時】

1. 確定2時間足で完全データ評価
   - ドンチャン: 完全な2時間足で正確に判定
   - PVO: 完全な2時間足で正確に判定
   - 両者の判定が「確定した過去」で同期

2. 結果
   - ドンチャン＋PVO同時成立 → エントリー成功
```

---

## ✅ 検証結論

### ロジック実装状態

✅ **前提条件のロジックは基本的に正しく実装されている**

- 1分おきの価格取得: 実装済み
- 2時間足でのシグナル評価: 実装済み
- 新規2時間足確定時のシグナル再計算: 実装済み

### 🔴 ただし実運用での問題

⚠️ **ドンチャンとPVOの評価タイミングが異なる**

- ドンチャン: 未確定2時間足で常時評価
- PVO: 確定2時間足でのみ評価
- 結果: 両者が同時成立しない → エントリー機会の喪失

### 推奨される修正

```python
# 修正案: PVO も常時評価に変更

def update_price_data(self):
    # ...
    
    # 常時ドンチャン評価（現在通り）
    dc, high, low = self.__evaluate_donchian(ohlcv_data, self.ticker)
    
    # 常時PVO評価（修正）← 2時間足確定時のみではなく
    pvo, value = self.__evaluate_pvo(ohlcv_data, latest_volume)
    self.signals['pvo']['signal'] = pvo
    self.signals['pvo']['info']['value'] = value
    
    # 別途: 2時間足確定時はボラティリティ更新のみ
    if self.prev_close_time < last_ohlcv_data['close_time']:
        self.volatility = self.calcurate_volatility(tmp_ohlcv_data_1)
        self.prev_close_time = last_ohlcv_data['close_time']
```

---

## 📋 チェックリスト

- [x] `bot.py` メインループロジック確認
- [x] `price_data_management.py` 更新ロジック確認
- [x] `bybit_exchange.py` データ取得メソッド確認
- [x] ドンチャン・PVO評価タイミング分析
- [x] バックテストとホットテストの差異原因特定
- [ ] PVO常時評価への修正実装（推奨）
- [ ] 修正後の再検証（推奨）

---

**検証者**: Copilot  
**最終判定**: 🟠 **ロジックは正しいが、実装に改善余地あり**

**次のステップ**:
1. PVO評価を常時に変更する修正を実装
2. ローカルでバックテスト再実行（修正後の動作確認）
3. ラズパイで再度ホットテスト実行（同じ期間で比較）
4. 結果が一致することを確認
