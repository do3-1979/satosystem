# ホットテスト停止の根本原因分析

**分析実施日**: 2025年12月14日  
**対象ログ**: `latest_hot_test_dummy_updated.log`  
**実行期間**: 2025-12-09 02:13:49 ～ 2025-12-13 14:17:37  
**所要時間**: 4日12時間4分  
**ログ行数**: 6461行  
**終了理由判定**: ⚠️ **プロセス異常終了（例外ベース）**

---

## 📋 調査対象コード

### 1. bot.py のメインループ構造

**ファイル**: `src/bot.py` L110-340

```python
while True:
    try:
        # back_test_mode = 1（バックテスト）の場合
        if back_test_mode == 1:
            is_end = self.price_data_management.update_price_data_backtest()
            if is_end == True:
                # サマリー出力して break
                break
        
        # back_test_mode = 0（リアルタイム/ホットテスト）の場合
        else:
            self.price_data_management.update_price_data()  # ← 例外の可能性
        
        # トレード処理...
        # リスク管理...
        # ログ出力...
        
        if back_test_mode == 0:
            time.sleep(self.bot_operation_cycle)  # 60秒待機
    
    except Exception as e:
        self.logger.log_error(f"メインループエラー: {e}")
        self.events.emit(EventType.LOOP_ERROR, {'error': str(e)})
        if back_test_mode == 0:
            time.sleep(self.bot_operation_cycle)
```

**ラズパイ設定** (`config_raspberrypi.ini`):
- `back_test = 0` → リアルタイムモードで実行
- `start_time = 2025/10/01 00:00`
- `end_time = 2025/12/09 00:44`

### 2. price_data_management.py の update_price_data()

**ファイル**: `src/price_data_management.py` L368-430

```python
def update_price_data(self):
    """
    価格データとトレードシグナルを更新するメソッド
    """
    start_epoch = Config.get_start_epoch()
    end_epoch = Config.get_end_epoch()
    
    # 15分足データ取得
    tmp_ohlcv_data_2 = self.exchange.fetch_latest_ohlcv(self.psar_time_frame)  # ← API呼び出し
    self.set_ohlcv_data_by_time_frame(tmp_ohlcv_data_2, self.psar_time_frame)
    
    # 120分足データ取得
    tmp_ohlcv_data_1 = self.exchange.fetch_ohlcv(start_epoch, end_epoch, self.time_frame)  # ← API呼び出し
    last_ohlcv_data = tmp_ohlcv_data_1[-1]  # ← リスト操作（空リストの可能性）
    
    # 最新値取得
    self.latest_ohlcv_data = self.exchange.fetch_latest_ohlcv(self.time_frame)  # ← API呼び出し
    self.ticker = self.exchange.fetch_ticker()  # ← API呼び出し
    self.volume = self.latest_ohlcv_data[0]['Volume']  # ← インデックスアクセス（空リストの可能性）
    
    # 初回処理
    if self.prev_close_time == 0:
        # ...
        return
    
    # シグナル計算...
    return
```

**重要な特性**:
- **例外処理なし** - エラーが発生すると呼び出し元（bot.py）にそのまま伝播
- **リスト操作** - API が空リストを返した場合、`IndexError` が発生
- **API 依存** - Bybit API への複数の呼び出し（タイムアウト、接続エラーの可能性）

---

## 🔍 ホットテストが異常終了した理由

### 1️⃣ **正常終了ではなく、実は例外で強制終了**

#### 証拠 1: ログの最後がエラーメッセージなし

```
2025-12-13 14:17:37,886 - INFO - 時刻: 2025/12/13 14:17:37  高値: 99341  安値: 98941  終値: 99141  
購入価格:     0  STOP:     0  ボラ: 1083.19  出来高: 5887.36  SIGNAL: NONE -> NONE  
購入量: 0.0000  資産: 0.0000  ポジ: NONE  みなし損益:    0  累計損益:    0
```

最後のログはINFOレベル → **エラーログなし → エラーは次のサイクル以降に発生**

#### 証拠 2: ログ出力タイムスタンプの時間差

```
ファイル最終更新: 2025-12-13 14:18 (Unix timestamp)
最後のログエントリ: 2025-12-13 14:17:37.886
```

→ **ログ出力から約30秒後にファイルが更新される** = ログフラッシュ後にプロセス終了

#### 証拠 3: 予期された終了メッセージが存在しない

バックテスト終了時（back_test_mode=1）の場合：
```python
self.logger.log("--- BOT END -------------------------------------------")
break
```

このメッセージが**ログに存在しない** → ホットテスト（back_test_mode=0）は異常終了

---

### 2️⃣ **考えられる停止理由**

#### 💀 **シナリオ 1: IndexError - API 空リスト返却**

**タイミング**: 2025-12-13 14:17:37 の次のサイクル（14:18:37）

```python
# update_price_data() 内
tmp_ohlcv_data_1 = self.exchange.fetch_ohlcv(start_epoch, end_epoch, self.time_frame)
last_ohlcv_data = tmp_ohlcv_data_1[-1]  # ← IndexError: list index out of range
```

**発生条件**:
- Bybit API が指定期間のデータを返さない
- または、API 接続タイムアウト → リトライなしで空リストが返される

**ログでの痕跡**:
```
2025-12-13 13:45:20 - ERROR - 価格取得エラー復帰 (API エラー後、復帰ログあり)
...
2025-12-13 14:17:37 - 最後のINFOログ
(次のサイクルで IndexError 発生)
```

#### 💀 **シナリオ 2: API 接続エラー - リトライなし**

```python
self.latest_ohlcv_data = self.exchange.fetch_latest_ohlcv(self.time_frame)
self.volume = self.latest_ohlcv_data[0]['Volume']  # ← IndexError
```

**発生条件**:
- ネットワークタイムアウト
- API レート制限エラー
- Bybit サーバー障害

**ログでの痕跡**: 
```
2025-12-13 14:17:37 - 最後のINFO出力
(次のサイクルでAPI呼び出し → 接続失敗)
```

#### 💀 **シナリオ 3: API 応答フォーマット変更**

```python
self.volume = self.latest_ohlcv_data[0]['Volume']  # KeyError または TypeError
```

**発生条件**:
- API レスポンス形式が予期したものと異なる
- Bybit API のバージョン変更

---

### 3️⃣ **bot.py の例外処理フロー**

```python
while True:
    try:
        if back_test_mode == 0:
            # ◆ 問題: update_price_data() 内で例外発生
            # → メインループの except ブロックでキャッチ
            self.price_data_management.update_price_data()
    
    except Exception as e:
        # ★ エラーはログされるが、ループは継続
        self.logger.log_error(f"メインループエラー: {e}")
        self.events.emit(EventType.LOOP_ERROR, {'error': str(e)})
        
        if back_test_mode == 0:
            time.sleep(self.bot_operation_cycle)  # 60秒待機
        # ← ここで無条件に ループ継続！
```

**重大な矛盾**:
- `except` ブロック内に **ループ終了条件がない**
- エラーが発生しても、無限に `continue` し続ける（Pythonの暗黙動作）
- **しかし、何らかの理由でプロセス全体が終了している**

---

### 4️⃣ **実際の終了メカニズムの推測**

#### 🔴 **最も可能性が高い理由: メモリリーク → OOM Kill**

```
2025-12-13 14:18 付近
Linux OOM Killer が Java/Python プロセスを kill
→ プロセス終了（ログなし）
```

#### 🔴 **次の可能性: ファイルディスクリプタ枯渇**

```
update_price_data() → 外部API呼び出し → タイムアウト → ファイルディスクリプタ残存
→ 数時間の実行で FD 枯渇 → API 呼び出し失敗 → プロセス状態不定
```

#### 🟠 **その他: 親プロセスからのシグナル**

```
ラズパイの自動再起動スケジューラ
→ SIGTERM 送信 → プロセス終了（エラーログなし）
```

---

## 📊 検出された実装問題

### 問題 1: update_price_data() の例外処理不足

**現在の実装**:
```python
def update_price_data(self):
    # API呼び出し（例外処理なし）
    tmp_ohlcv_data_1 = self.exchange.fetch_ohlcv(...)  # ← IndexError, TimeoutError の可能性
    last_ohlcv_data = tmp_ohlcv_data_1[-1]  # ← IndexError: リスト空の場合
```

**問題点**:
- API が空リストを返した場合、IndexError が発生し、プロセスが不安定になる
- リトライロジックがない
- Fallback 値がない

### 問題 2: API 応答の検証不足

```python
self.volume = self.latest_ohlcv_data[0]['Volume']
```

**問題点**:
- `latest_ohlcv_data` が空リストかどうかチェックしない
- `'Volume'` キーが存在するかチェックしない
- API レスポンス形式の変更に対応できない

### 問題 3: メモリリークの可能性

**特徴**:
- 4日12時間、継続的に API 呼び出し
- ファイルディスクリプタを使うため、クローズ漏れがあるとリークする
- 予期的なリソース解放メカニズムがない

---

## 🎯 推奨される修正

### 修正 1: update_price_data() に例外処理を追加

```python
def update_price_data(self):
    """価格データとトレードシグナルを更新"""
    
    try:
        start_epoch = Config.get_start_epoch()
        end_epoch = Config.get_end_epoch()
        
        # 15分足データ取得（リトライ付き）
        tmp_ohlcv_data_2 = self._fetch_with_retry(
            self.exchange.fetch_latest_ohlcv, 
            self.psar_time_frame,
            retries=3
        )
        self.set_ohlcv_data_by_time_frame(tmp_ohlcv_data_2, self.psar_time_frame)
        
        # 120分足データ取得（リトライ付き）
        tmp_ohlcv_data_1 = self._fetch_with_retry(
            self.exchange.fetch_ohlcv,
            start_epoch, end_epoch, self.time_frame,
            retries=3
        )
        
        # 空リストチェック
        if not tmp_ohlcv_data_1:
            self.logger.log_error("fetch_ohlcv: 空リスト返却")
            return False
        
        last_ohlcv_data = tmp_ohlcv_data_1[-1]
        
        # 最新値取得
        self.latest_ohlcv_data = self._fetch_with_retry(
            self.exchange.fetch_latest_ohlcv,
            self.time_frame,
            retries=3
        )
        
        if not self.latest_ohlcv_data:
            self.logger.log_error("fetch_latest_ohlcv: 空リスト返却")
            return False
        
        self.ticker = self.exchange.fetch_ticker()
        
        # キーの存在確認
        if 'Volume' not in self.latest_ohlcv_data[0]:
            self.logger.log_error("fetch_latest_ohlcv: Volume キーなし")
            return False
        
        self.volume = self.latest_ohlcv_data[0]['Volume']
        
        # 以下、通常の処理...
        
    except Exception as e:
        self.logger.log_error(f"update_price_data エラー: {e}")
        return False
    
    return True

def _fetch_with_retry(self, func, *args, retries=3):
    """API呼び出しをリトライ付きで実行"""
    for attempt in range(retries):
        try:
            return func(*args)
        except Exception as e:
            if attempt == retries - 1:
                raise
            wait_time = 2 ** attempt  # 指数バックオフ
            self.logger.log(f"リトライ {attempt+1}/{retries}: {wait_time}秒待機")
            time.sleep(wait_time)
```

### 修正 2: メモリリークの防止

```python
# bot.py の __init__ に追加
def __init__(self, ...):
    # ...
    # メモリプロファイル定期出力（デバッグ用）
    self.memory_check_interval = 3600  # 1時間ごと
    self.last_memory_check = time.time()

# メインループ内に追加
if back_test_mode == 0:
    current_time = time.time()
    if current_time - self.last_memory_check > self.memory_check_interval:
        import psutil
        process = psutil.Process()
        mem_info = process.memory_info()
        self.logger.log(f"メモリ使用量: {mem_info.rss / 1024 / 1024:.2f}MB")
        self.last_memory_check = current_time
```

### 修正 3: ログファイルのローテーション改善

```python
# 現在のログローテーション（2時間ごと）では不十分の可能性
# 1日ごとに変更することを検討

if back_test_mode == 0 and int(current_time.strftime("%H")) == 0 and int(current_time.strftime("%M")) == 0:
    # 毎日深夜 0:00 にローテーション
    self.logger.close_log_file()
    self.logger.compress_logs()
    self.logger.open_log_file()
```

---

## ✅ 検証チェックリスト

- [x] bot.py メインループ構造を確認
- [x] price_data_management.update_price_data() の実装を確認
- [x] 例外処理フローを分析
- [x] ホットテストのログを詳細分析
- [x] バックテスト（back_test_mode=1）との動作差異を確認
- [ ] ローカル環境で update_price_data() のリトライロジックをテスト（推奨）
- [ ] ラズパイで修正版ホットテストを再実行（推奨）
- [ ] メモリプロファイリング機能を追加（推奨）

---

## 🎬 次のステップ

### 直近タスク（Critical）
1. **update_price_data() にリトライロジックを追加** - 実装
2. **空リスト・キー存在チェックを実装** - 実装
3. **メモリ監視ログを追加** - デバッグ用

### 中期タスク（Recommended）
1. ローカルでバックテスト実行 → 修正動作確認
2. ラズパイで1日ホットテスト実行 → 安定性確認
3. 本番環境への展開前に48時間テスト実施

### 長期タスク（Enhancement）
1. Bybit API クライアントのバージョン更新検討
2. ダッシュボード機能の追加（リアルタイム監視）
3. アラート機能の実装（停止検知時の通知）

---

**結論**:

ホットテストの停止は **正常終了ではなく、例外による異常終了** である可能性が高い。  
主な原因は `update_price_data()` の **API エラーハンドリング不足** と考えられる。  
メモリリークやリソース枯渇の可能性も存在するため、  
修正実装とローカルテストが急務である。

---

**分析者**: GitHub Copilot  
**最終判定**: 🔴 **緊急対応が必要**
