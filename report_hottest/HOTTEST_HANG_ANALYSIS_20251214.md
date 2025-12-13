# ホットテスト&ダミートレード ハング分析レポート
**実行日時:** 2025-12-14 01:32:17 - 01:43:00 (約11分間)
**停止理由:** プロセスがハング状態に陥ったため強制終了

---

## 1. ハング状況の詳細

### ログの時系列
```
01:32:17 - 🎭 ペーパートレードモード ON（起動成功）
01:32:22 - 最初のボットループ実行（正常）
01:33:22 - 2回目のループ実行（正常）
01:34:23 - 3回目のループ実行（正常）
01:35:23 - 4回目のループ実行（正常）
01:36:24 - 5回目のループ実行（正常）
01:37:25 - 6回目のループ実行（正常）
[ここから約6分間ログ出力なし - ハング状態]
01:43:00 - プロセス強制終了
```

### 各ループ間隔
- 最初5ループ: 約60秒周期（設定値: `bot_operation_cycle = 60`）
- 6ループ目: 約60秒後にハング

---

## 2. ハングの根本原因

### 🔴 **主原因: `bybit_exchange.py` の無限ループ**

**問題のコード場所:** [`src/bybit_exchange.py`](src/bybit_exchange.py#L327-L348)

```python
def fetch_ohlcv(self, start_epoch, end_epoch, time_frame):
    ...
    while True:  # ← 【致命的】無限ループ
        try:
            ohlcv = self.exchange.fetch_ohlcv(
                symbol = self.market,
                timeframe = time_frame,
                since = int(get_time * 1000),
            )
            break
        except ccxt.BaseError as e:
            if err_occuerd == False:
                self.logger.log_error(f"価格取得エラー:{str(e)}")
                err_occuerd = True
            time.sleep(server_retry_wait)  # ← リトライ待機
```

### 問題の詳細

| 項目 | 問題 | 影響 |
|------|------|------|
| **無限ループ** | `while True:` に最大試行回数制限なし | API呼び出しが失敗すると永遠に再試行 |
| **タイムアウト機構なし** | ccxt の `fetch_ohlcv()` に timeout パラメータなし | ネットワークハングで無期限待機 |
| **例外ハンドリング不足** | ccxt.BaseError のみキャッチ | Connection Timeout 等は catch されない |
| **リトライ戦略不完全** | 指数バックオフがない（単純な固定待機） | サーバ負荷軽減なし |
| **ログ出力停止** | エラーが繰り返された場合ログが止まる | デバッグ困難 |

---

## 3. ハング発生メカニズム

```
【正常な流れ（01:32-01:37）】
ボットループ開始
  ↓
update_price_data()
  ↓
_fetch_with_retry() で fetch_ohlcv() 実行
  ↓
（正常）データ取得成功 → ボットメインロジック進行
  ↓
60秒待機 → 次のループへ

【ハング時の流れ（01:37-01:43）】
ボットループ開始
  ↓
update_price_data()
  ↓
_fetch_with_retry() で fetch_ohlcv() 実行
  ↓
【ハング開始】
fetch_ohlcv() の while True ループで API呼び出し
  ↓
ネットワークエラー / API リスポンス遅延 / タイムアウト
  ↓
ccxt.BaseError 発生
  ↓
server_retry_wait（120秒） 待機 ※この待機中もログ出力なし
  ↓
再度 fetch_ohlcv() 試行
  ↓
再びハング（同じエラーで無限ループ）
  ↓
【解決手段なし】無限に繰り返す → プロセスがゾンビ化
```

---

## 4. ccxt ライブラリの仕様確認

ccxt の `fetch_ohlcv()` メソッドのデフォルト動作:

```python
# ccxt では以下のように timeout を指定可能:
exchange.fetch_ohlcv(
    symbol='BTC/USD',
    timeframe='1h',
    since=1234567890000,
    limit=None,
    params={'timeout': 5000}  # ← ミリ秒単位のタイムアウト
)
```

**現在のコード:** timeout を設定していない → ccxt のデフォルト（通常30秒）が使用

---

## 5. ハング発生の具体的な条件

### 予想される原因
1. **Bybit API レート制限**
   - 無限リトライで API 呼び出し頻度が上限超過
   - API が一時的に応答不可状態に

2. **ネットワーク遅延**
   - ラズパイの Wi-Fi 接続が不安定
   - TCP コネクションタイムアウト（デフォルト20-30秒）

3. **API レスポンス時間**
   - 大量の履歴データ取得時に API 処理時間が長化
   - socket タイムアウトに達する前に hang 状態に

4. **Bybit API の一時的な不具合**
   - API サーバ側のリソース枯渇
   - 500 エラーの返却とそれによるリトライ無限ループ

---

## 6. 修正方針

### 🔧 **優先度1: リトライ機構に最大試行回数制限を追加**

```python
def _fetch_with_retry(self, func, *args, retries=3, timeout=30):
    """API呼び出しをリトライ付きで実行するメソッド"""
    import time
    
    for attempt in range(retries):  # ← 最大3回で打ち切り
        try:
            # timeout パラメータを追加
            return func(*args, timeout=timeout)
        except Exception as e:
            if attempt == retries - 1:
                self.logger.log_error(f"API呼び出し失敗（最大リトライ到達）: {e}")
                raise
            wait_time = min(2 ** attempt, 30)  # 最大30秒の指数バックオフ
            self.logger.log(f"API呼び出し失敗（リトライ {attempt+1}/{retries}）: {e}")
            time.sleep(wait_time)
```

### 🔧 **優先度2: bybit_exchange.py の while True を修正**

```python
def fetch_ohlcv(self, start_epoch, end_epoch, time_frame):
    ...
    while get_time < end_epoch_fixed:
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:  # ← 無限ループを有限に
            try:
                ohlcv = self.exchange.fetch_ohlcv(
                    symbol = self.market,
                    timeframe = time_frame,
                    since = int(get_time * 1000),
                    params={'timeout': 10000}  # 10秒のタイムアウト
                )
                break
            except (ccxt.BaseError, TimeoutError) as e:
                retry_count += 1  # ← リトライ回数をインクリメント
                if retry_count >= max_retries:
                    self.logger.log_error(f"最大リトライ回数に達しました: {e}")
                    raise
                wait_time = 2 ** retry_count
                self.logger.log(f"リトライ {retry_count}/{max_retries}")
                time.sleep(wait_time)
```

### 🔧 **優先度3: ホットテスト用の時間範囲を制限**

```ini
# config.ini の Period セクション
[Period]
start_time = 2025/12/13 00:00  # 直近24時間に制限
end_time = 2025/12/14 01:00
```

### 🔧 **優先度4: タイムアウト検出ログの追加**

```python
# logger に timeout メッセージを追加
self.logger.log_error(f"【TIMEOUT】API呼び出し時間超過 (時刻: {datetime.now()})")
```

---

## 7. テスト方針

### 修正後の検証項目

| テスト項目 | 検証内容 | 期待結果 |
|-----------|--------|--------|
| **リトライ上限** | 3回失敗後、正常に例外を raise | ハング状態が解消 |
| **タイムアウト動作** | 10秒以内に API レスポンスなければ timeout 発生 | ログに timeout メッセージ出力 |
| **復帰可能性** | エラー発生後、次のループで正常に復帰 | 次の60秒周期で再度 API 呼び出し |
| **ホットテスト継続** | 24時間 連続実行 | ハングなく継続動作 |
| **メモリ監視** | 1時間ごとのメモリログ出力 | メモリリークなし（100-150 MB 範囲内） |

---

## 8. まとめ

### 原因
`bybit_exchange.py` の `fetch_ohlcv()` メソッド内の **無限ループ** + **タイムアウト機構なし** により、API エラーが発生すると永遠にリトライを続けてハング状態に陥る。

### 結果
- **起動後:** 5ループ（約5分）は正常動作
- **6ループ目:** API 呼び出し時にハング
- **状態:** 約6分間のログ出力なし → 強制終了

### 推奨対応
1. **緊急:** リトライ最大回数を3回に制限
2. **必須:** API timeout を 10 秒に設定
3. **推奨:** ホットテスト実行時間を24時間に制限
4. **推奨:** メモリ監視機能の有効化

---

**次ステップ:** これらの修正を実装してから、再度ホットテストを実行
