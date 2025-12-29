# PVOフィルタ設定が反映されない理由 - 最終調査報告

## 📋 問題の状況（ユーザー報告）

```
config.ini の enable_pvo_filter を 0 → 1 に変更して
run_quarterly_backtest.py を実行したが、結果が全く変わらない
```

## 🔍 根本原因の特定

### **実行ログの確認**

最新バックテストログ（logs/latest_backtest.log）を確認した結果：

```
grep "PVO フィルター" logs/latest_backtest.log
→ 結果：0件（フィルターログが出力されていない）
```

### **コード構造の分析**

[src/trading_strategy.py](src/trading_strategy.py#L186-L195) のフィルター実装：

```python
# Line 186-195
if allow_entry and enable_pvo_filter:
    pvo_value = signals["pvo"]["info"].get("value", 0)
    pvo_threshold = Config.get_pvo_threshold()  # ← pvo_threshold = 20
    if pvo_value <= pvo_threshold:  # ← この判定が問題
        allow_entry = False
    else:
        # フィルター成功ログ出力
```

## 💡 発見された問題

### **問題1: pvo_threshold の値の不適切性**

config.ini で設定されている値：
```ini
[Strategy]
pvo_threshold = 20
```

実際のバックテストで出現するPVO値：
```
例1: pvo_value = 116.258... 
例2: pvo_value = 173.460...
例3: pvo_value = -68.732...
```

**判定ロジック：**
```python
if pvo_value <= 20:  # ← 100以上の値は絶対に失敗しない
    allow_entry = False
```

**結果：**
- ほぼ全てのケースで `pvo_value > 20` なので、フィルターは**ほぼ常に合格**
- enable_pvo_filter=1/0を変更しても、結果に影響なし

### **問題2: フィルター実装の曖昧性**

コメント（Line 81）と実装に矛盾：

```python
# コメント: "enable_pvo_filter: PVO > 0 を必須条件として追加"
# 実装:     "pvo_value <= 20 で判定"
```

期待値 vs 実装値：
- **期待値**: PVO > 0 で判定（上昇トレンド判定）
- **実装値**: PVO > 20 で判定（？値が不明確）

### **問題3: 基本条件との重複**

```python
# Line 109: 基本条件
if signals["pvo"]["signal"] == True:  # ← 既にPVOシグナル確認済み
    # Line 186: フィルター
    if allow_entry and enable_pvo_filter:
        if pvo_value <= pvo_threshold:  # ← 重複判定？
```

両方でPVOをチェックしており、目的が不明確。

---

## 📊 実際のPVO値分析

バックテストログから抽出したPVO値：

```
時刻                  | PVO signal | PVO value    | 判定（threshold=20）
2025/09/30 21:00     | False      | 0            | 失敗
2025/10/01 09:00     | False      | -68.73       | 失敗
2025/10/01 19:00     | True       | 116.26       | 成功（enable_pvo_filter=1/0 関わらず）
2025/10/02 05:00     | True       | 173.46       | 成功（enable_pvo_filter=1/0 関わらず）
```

**結論：** threshold=20では、ほぼ全てのシナリオで判定結果は変わらない。

---

## 🎯 正しい実装の方向性

### **方案A: threshold値を現実的に変更**

```ini
# 現在
pvo_threshold = 20

# 改善案1: PVO > 50 で判定
pvo_threshold = 50

# 改善案2: PVO > 0 で判定（正のみを許可）
pvo_threshold = 0
```

### **方案B: フィルター実装を明確化**

```python
# 現在の曖昧な実装
if pvo_value <= pvo_threshold:
    allow_entry = False

# 改善案（意図を明確化）
# 想定: PVO > 0 なら上昇トレンド、< 0 なら下降トレンド
if pvo_value <= 0:  # 下降トレンドを除外
    allow_entry = False
```

### **方案C: コメントと実装を整合させる**

```python
# コメント削除or修正
# 現在: "enable_pvo_filter: PVO > 0 を必須条件として追加"
# 改正: "enable_pvo_filter: PVO > 20 のときのみエントリー"
```

---

## ✅ 推奨アクション

### **短期（即座）**

1. **config.ini の pvo_threshold 値を現実的に変更**

```ini
# 現在: pvo_threshold = 20
# 推奨: pvo_threshold = 0  # PVO > 0（正のみ）で判定
```

2. **再度バックテスト実行**

```bash
# enable_pvo_filter = 0
python3 run_quarterly_backtest.py | tee result_filter_disabled.log

# enable_pvo_filter = 1 に変更後
python3 run_quarterly_backtest.py | tee result_filter_enabled.log

# ログから「PVO フィルター」を確認
grep "PVO フィルター" result_*.log
```

3. **結果が変わることを確認**

現在のpvo_threshold=20では変化がないが、pvo_threshold=0に変更すると、負のPVO値でフィルターされるはず。

### **中期（ベストプラクティス）**

1. **フィルター実装を再検討**
   - コメントと実装の整合性確保
   - threshold値の定義を明確化

2. **ドキュメント追加**
   - pvo_threshold の役割説明
   - フィルター効果の検証方法

3. **ユニットテスト追加**
   - enable_pvo_filter=1/0で結果が異なることをテスト

---

## 📌 結論

**enable_pvo_filter を変更しても結果が変わらない理由：**

❌ **run_pvo_filter_test.py が硬くコードされたから** （初期仮説は誤り）

✅ **pvo_threshold=20という閾値が高過ぎて、実際のPVO値（100以上）が常に合格するから** （本当の原因）

つまり、フィルター実装自体は正しいが、**パラメータ設定が不適切** のため、効果が現れていません。

**即座の修正：** `pvo_threshold = 0` に変更し、PVO > 0 のみをエントリー許可とする。
