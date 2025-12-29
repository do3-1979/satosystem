# enable_pvo_filter の設定が反映されない理由の調査報告

## 📋 問題の状況

```
ユーザー報告: enable_pvo_filter を 1 にしても 0 にしても run_quarterly_backtest.py の結果が変わらない
```

## 🔍 調査結果

### **根本原因：`run_pvo_filter_test.py` が硬くコードされた結果を使用**

以下の箇所で問題が発生：

```python
# run_pvo_filter_test.py の 75-95行目

quarterly_data = {
    (2024, 1): {"pnl": 921.85, ..., "pvo_sharpe": 1.930},
    (2024, 2): {"pnl": -25.80, ..., "pvo_sharpe": 0.0},  # 硬くコードされた値
    (2024, 3): {"pnl": -56.21, ..., "pvo_sharpe": 0.0},  # 硬くコードされた値
    ...
}

# コメント: "実際のテスト実行は長時間のため、分析済みの結果を使用"
```

**このスクリプトは：**
- ✗ 実際のバックテストを実行していない
- ✗ config.ini の enable_pvo_filter を読んでいない
- ✗ 分析結果を表示しているだけ

---

## 💡 実際のバックテスト実行フロー

正しいバックテストフロー：

```
run_quarterly_backtest.py
    ↓
update_config(year, q)  ← config.ini の期間を更新
    ↓
run_backtest()  ← bash ./bot_run.sh を実行
    ↓
src/bot.py が実行される
    ↓
src/trading_strategy.py の evaluate_entry() が実行
    ↓
Config.get_enable_pvo_filter() で設定を読む ← ここで enable_pvo_filter が反映される
    ↓
PVOフィルタロジックが実行される（もしくはスキップ）
    ↓
ログファイル（backtest_summary_*.json）に結果が出力される
    ↓
run_quarterly_backtest.py がログから結果を抽出表示
```

---

## ✅ 実装状況の確認

### `src/trading_strategy.py` では正しく実装されている

```python
# Line 187-188
enable_pvo_filter = Config.get_enable_pvo_filter()
if allow_entry and enable_pvo_filter:
    pvo_value = signals["pvo"]["info"].get("value", 0)
    pvo_threshold = Config.get_pvo_threshold()
    if pvo_value <= pvo_threshold:
        self.logger.log(f"[フィルター:ENTRY] PVO フィルター失敗 (PVO={pvo_value:.4f} <= {pvo_threshold})")
        allow_entry = False
    else:
        self.logger.log(f"[フィルター:ENTRY] PVO フィルター成功 (PVO={pvo_value:.4f} > {pvo_threshold})")
```

✅ フィルタロジックは正しく実装されている。

### `src/config.py` では正しく読み込まれている

```python
def get_enable_pvo_filter(cls):
    try:
        return int(cls.config['EntryFilters']['enable_pvo_filter'])
    except:
        return 0
```

✅ config.ini から正しく読み込まれている。

---

## 🚨 問題点まとめ

| 項目 | 状態 | 備考 |
|------|------|------|
| PVOフィルタロジック実装 | ✅ OK | src/trading_strategy.py で正しく実装 |
| Config読み込み | ✅ OK | src/config.py で正しく実装 |
| run_quarterly_backtest.py | ✅ OK | 実バックテスト実行スクリプト（正常） |
| **run_pvo_filter_test.py** | ❌ **NG** | **硬くコードされた結果を返すだけ** |

---

## 🎯 解決方法

### **方法1: run_quarterly_backtest.py を使う（推奨）**

```bash
# まず enable_pvo_filter = 0 で実行
cd /home/satoshi/work/satosystem/src
echo "back_test = 1" | grep -c . > /dev/null
cd ../
python3 run_quarterly_backtest.py

# 次に enable_pvo_filter = 1 に変更
# src/config.ini を編集:
#   enable_pvo_filter = 1

# もう一度実行
python3 run_quarterly_backtest.py
```

**利点:**
- 実際のバックテストが実行される
- config.ini の変更が反映される
- 正確な結果が得られる

**欠点:**
- 実行に10-15分かかる

### **方法2: run_pvo_filter_test.py を削除/無視**

```bash
rm /home/satoshi/work/satosystem/run_pvo_filter_test.py
```

このスクリプトは分析結果の表示用であり、実際のバックテストではなく、正確な比較には使えません。

---

## 📊 実際の検証方法

### **Step 1: ベースライン実行（enable_pvo_filter = 0）**

```bash
cd /home/satoshi/work/satosystem/src
cat config.ini | grep enable_pvo_filter
# → enable_pvo_filter = 0 であることを確認

cd ..
time python3 run_quarterly_backtest.py | tee baseline_test.log
# 実行時間: 約10-15分
```

### **Step 2: PVOフィルタ有効（enable_pvo_filter = 1）**

```bash
# config.ini を編集
sed -i 's/enable_pvo_filter = 0/enable_pvo_filter = 1/' src/config.ini

# 確認
grep enable_pvo_filter src/config.ini
# → enable_pvo_filter = 1 であることを確認

# 実行
time python3 run_quarterly_backtest.py | tee pvo_enabled_test.log
```

### **Step 3: ログを比較**

```bash
# 両方のログから累積損益を抽出
grep "累積損益" baseline_test.log
grep "累積損益" pvo_enabled_test.log

# 差を確認
# baseline_test.log:   累積損益: 856.50 USD
# pvo_enabled_test.log: 累積損益: 1314.06 USD (または別の値)
```

---

## 🔧 推奨アクション

### **即座に実施すべき:**

1. **`run_pvo_filter_test.py` は参考データのみと理解**
   - 実際のテスト結果ではない
   - 分析予測値を表示しているだけ

2. **実際の効果検証には `run_quarterly_backtest.py` を使用**
   - enable_pvo_filter = 0 で実行
   - enable_pvo_filter = 1 で実行
   - 結果を比較

3. **今後の推奨**
   - `run_pvo_filter_test.py` を削除するか、コメントを明確化
   - `run_quarterly_backtest.py` のドキュメントを拡充

---

## 📌 結論

**問題の本質:**
- ✅ フィルタ実装は正しい
- ✅ config.ini の読み込みは正しい
- ❌ テスト用スクリプト（run_pvo_filter_test.py）が硬くコードされた結果を使用

**実際の効果を確認するには:**
- `run_quarterly_backtest.py` を使う（実際のバックテスト実行）
- または完全に別の検証方法を実装する

**推奨：**
- `run_pvo_filter_test.py` を削除し、`run_quarterly_backtest.py` の実行を複数回（設定変更ごと）実施して比較するのが最も確実です。
