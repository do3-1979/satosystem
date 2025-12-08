# 実行モード管理ガイド

**バージョン**: v1.0.0-stable  
**作成日**: 2025-12-09  
**更新日**: 2025-12-09

---

## 📊 概要

satosystem は 3つの異なる実行モードをサポートしています。

| モード | back_test | hot_test_dummy_mode | 用途 | 取引 | データ |
|--------|-----------|-------------------|------|------|--------|
| **バックテスト** | 1 | 1 | 過去データで戦略検証 | ✅ ダミー | 過去 |
| **ペーパートレード** | 0 | 1 | ライブ市場で検証 | ✅ ダミー | ライブ |
| **本番取引** | 0 | 0 | 実際の取引実行 | 🚀 実取引 | ライブ |

---

## 🎯 実行モードの選択

### 1️⃣ バックテストモード（推奨：開発中）

**用途**: 戦略の初期検証、パラメータ調整

```bash
# config.ini を設定
vi src/config.ini
# [Backtest]
# back_test = 1
# hot_test_dummy_mode = 1

# 実行
bash src/bot_run.sh
# または
python src/bot.py
```

**特徴**:
- 過去のOHLCVデータを使用
- ダミー取引で実行（リスクなし）
- バックテスト結果をログに出力
- 高速実行（データを事前に取得）

**ログファイル**: `src/logs/latest_backtest.log`

---

### 2️⃣ ペーパートレード（推奨：本番前）

**用途**: ライブ市場での検証、実運用シミュレーション

```bash
# config.ini を設定
vi src/config.ini
# [Backtest]
# back_test = 0
# hot_test_dummy_mode = 1

# 実行
bash src/bot_run.sh
# または
python src/bot.py
```

**特徴**:
- ライブOHLCVデータを使用（リアルタイム）
- ダミー取引で実行（リスクなし）
- 実際の市場環境でテスト
- 安全な検証環境

**ログファイル**: `src/logs/latest_hot_test_dummy.log`

---

### 3️⃣ 本番取引（⚠️ 注意：リスク高）

**用途**: 実際の運用開始

```bash
# config.ini を設定
vi src/config.ini
# [Backtest]
# back_test = 0
# hot_test_dummy_mode = 0

# 実行
bash src/bot_run.sh
# bot_run.sh が確認プロンプトを表示
# 本当に実行しますか？ (yes/no): yes
```

**特徴**:
- ライブOHLCVデータを使用
- 🚀 実取引を実行（リスク発生）
- 実API呼び出し
- 確認プロンプト必須（誤実行防止）

**ログファイル**: `src/logs/latest_hot_test_live.log`

**警告**:
```
⚠️  WARNING: 本番取引モードで実行します。注意してください！
本当に実行しますか？ (yes/no): 
```

---

## 📝 config.ini の設定

### [Backtest] セクション

```ini
[Backtest]
# 実行モード: 1=バックテスト, 0=ホットテスト
back_test = 1

# ホットテスト時の取引モード: 1=ダミー取引（ペーパーテスト）, 0=本番取引
hot_test_dummy_mode = 1

# バックテスト後にインタラクティブグラフを自動生成
generate_interactive_graph = 1
```

### 設定値の組み合わせ

| back_test | hot_test_dummy_mode | 結果 |
|-----------|-------------------|------|
| 1 | 1 | バックテスト（ダミー） |
| 1 | 0 | バックテスト（ダミー） ※ hot_test_dummy_mode は無視 |
| 0 | 1 | ペーパートレード（ダミー） |
| 0 | 0 | 本番取引（実取引） |

---

## 🔧 bot_run.sh の動作

`bot_run.sh` は `config.ini` から設定を読み込んで自動的にモードを判定します。

```bash
# 設定読み込み
back_test=$(grep '^back_test *= *' config.ini | awk -F' *= *' '{print $2}')
hot_test_dummy_mode=$(grep '^hot_test_dummy_mode *= *' config.ini | awk -F' *= *' '{print $2}')

# モード判定ロジック
if [ "$back_test" = "1" ]; then
    # バックテスト
    echo "📊 バックテストモード"
    log_file="logs/latest_backtest.log"
elif [ "$hot_test_dummy_mode" = "1" ]; then
    # ペーパートレード
    echo "🎭 ホットテスト（ペーパートレード）モード"
    log_file="logs/latest_hot_test_dummy.log"
else
    # 本番取引
    echo "🚀 ホットテスト（本番取引）モード"
    log_file="logs/latest_hot_test_live.log"
    read -p "本当に実行しますか？ (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        exit 1
    fi
fi
```

---

## 💡 ダミー取引モードの仕組み

### bybit_exchange.py のダミーモード判定

```python
# is_dummy_mode は以下の条件で True になる
is_dummy_mode = (back_test == 1) or (back_test == 0 and hot_test_dummy_mode == 1)

# つまり:
# - バックテスト (back_test == 1) → 常にダミーモード
# - ペーパートレード (back_test == 0, hot_test_dummy_mode == 1) → ダミーモード
# - 本番取引 (back_test == 0, hot_test_dummy_mode == 0) → 実取引モード
```

### ダミー取引の実装

ダミーモード時、以下の処理が実行されます:

```python
# 口座残高
def get_account_balance():
    return {'USDT': {'total': 100000.0, 'used': 0, 'free': 100000.0}}

# 注文実行
def execute_order(side, quantity, price, order_type):
    # 実API呼び出しではなくダミー注文を記録
    self.dummy_orders[order_id] = {...}
    return True

# 価格取得
def fetch_latest_ohlcv(time_frame):
    # ランダムな価格データを返す
    return [{'close_price': random_price, ...}]
```

---

## 🧪 検証

### モード判定ロジックの検証

```bash
# test_mode_verification.py で検証
python test_mode_verification.py
```

**出力例**:
```
🧪 実行モード判定テスト
[1] ✅ バックテストモード
    back_test=1, hot_test_dummy_mode=1
    → バックテスト (is_dummy=True)

[2] ✅ ホットテスト（ダミー取引）
    back_test=0, hot_test_dummy_mode=1
    → ホットテスト（ペーパーテスト） (is_dummy=True)

[3] ✅ ホットテスト（本番取引）
    back_test=0, hot_test_dummy_mode=0
    → ホットテスト（本番取引） (is_dummy=False)
```

### ホットテスト検証

```bash
# ペーパートレードで 180秒実行、60秒周期の価格取得を検証
python test_hot_trading.py
```

**結果**:
```
✅ ホットテスト成功: 60秒周期の価格取得が正しく動作しています
```

---

## 📋 レグレッション テスト

すべてのモードで回帰テストが成功することを確認:

```bash
# back_test = 1 で実行
python test/regression_test_suite.py
```

**結果**: 54/54 テスト成功 ✅

---

## ⚠️ 安全上の推奨事項

### 開発フローの推奨順序

```
1. バックテストモード (back_test=1, hot_test_dummy_mode=1)
   ↓ 戦略が収益的になることを確認
   
2. ペーパートレード (back_test=0, hot_test_dummy_mode=1)
   ↓ ライブ市場で実動作を確認（リスクなし）
   
3. 本番取引 (back_test=0, hot_test_dummy_mode=0)
   ↓ 実際の取引開始（リスク発生）
```

### 本番取引への移行チェックリスト

- [ ] バックテストで十分な成績確認
- [ ] ペーパートレードで 1週間以上の検証完了
- [ ] APIキーの設定確認（`src/.api_key` が正しい）
- [ ] 取引レバレッジの確認（`config.ini` の `leverage` を確認）
- [ ] リスク管理設定の確認（`risk_percentage`, `account_balance`）
- [ ] 口座残高の確認（`Config.get_account_balance()` で設定した金額）
- [ ] ストップロス機能の動作確認

---

## 🔍 ログファイルの確認

### バックテスト

```bash
tail -f src/logs/latest_backtest.log
```

### ペーパートレード

```bash
tail -f src/logs/latest_hot_test_dummy.log
```

### 本番取引

```bash
tail -f src/logs/latest_hot_test_live.log
```

---

## 🚨 トラブルシューティング

### 「本当に実行しますか？」プロンプトが出ない

確認項目:
- `config.ini` で `hot_test_dummy_mode = 0` に設定済み？
- `bot_run.sh` が実行権限を持っている？

```bash
chmod +x src/bot_run.sh
```

### ダミーモードなのに実取引が発生している

確認項目:
- `config.ini` の設定値を確認
- `test_mode_verification.py` で判定ロジックを検証

```bash
python test_mode_verification.py
```

### APIキーエラーが出ている

確認項目:
- `.api_key` ファイルが存在するか？
- `replace_api_key.sh` が正常に実行されたか？

```bash
cd src
bash replace_api_key.sh
grep "api_key\|api_secret" config.ini
```

---

## 📌 まとめ

| 実行モード | 設定 | 用途 | リスク |
|-----------|------|------|--------|
| **バックテスト** | back_test=1 | 戦略開発 | ❌ なし |
| **ペーパートレード** | back_test=0, hot_test_dummy_mode=1 | 本番前検証 | ❌ なし |
| **本番取引** | back_test=0, hot_test_dummy_mode=0 | 運用開始 | ⚠️ あり |

**デフォルト設定**: `back_test=1, hot_test_dummy_mode=1`（最も安全）

**最初のステップ**: バックテストから始めて、ペーパートレード、本番取引の順に進める
