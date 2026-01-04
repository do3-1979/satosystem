# ログ出力改善 (2026-01-04)

## 改善内容

### 1. 新指標の重複ログを削除（状態変化検出）

**Before:**
```
2026-01-04 21:35:15,927 - [新指標] strategy_a: SELL
2026-01-04 21:35:16,027 - [新指標] strategy_a: SELL  # 重複
2026-01-04 21:35:16,127 - [新指標] strategy_a: SELL  # 重複
```

**After:**
```
2026-01-04 21:35:15,927 - [新指標] strategy_A: SELL (ADX=18.07, RSI=45.2, ...)
# シグナルが BUY に変わったときだけ出力
2026-01-04 21:35:20,027 - [新指標] strategy_A: BUY (ADX=22.5, RSI=55.1, ...)
# 全Strategy が NONE になったときに表示
2026-01-04 21:35:25,027 - [新指標] 全Strategy: NONE（シグナル消滅）
```

**実装方法:**
- `self.last_strategy_signal` で前回のシグナルを保持
- `signal_key = f"{strategy_name}:{normalized}"` で前回と比較
- 状態変化時のみログ出力（重複排除）

### 2. 具体的な条件値をログに表示

**Before:**
```
[新指標] strategy_a: SELL
```

**After:**
```
[新指標] strategy_A: SELL (ADX=18.07, RSI=45.2, MA_Gap=0.95)
```

**実装方法:**
- Strategy評価結果から `conditions` dict を抽出
- `", ".join([f"{k}={v}" for k, v in conditions.items()])` で整形

### 3. エントリー判定の構造化：条件一覧 → フィルタ一覧 → 最終判定

**Before:**
```
2026-01-04 21:35:15,927 - [条件判定:ENTRY] PVO信号 OK → ベースライン許可 (Donchian: SELL)
2026-01-04 21:35:15,927 - [フィルター:ENTRY] PVO フィルター成功 (PVO=359.1067 > 10)
2026-01-04 21:35:15,927 - [フィルター:ENTRY] ADX フィルター失敗 (ADX=18.07 < 31)
→ エントリー判定が不明確
```

**After:**
```
[条件一覧] PVO信号: ✓ | Donchian: SELL | Strategy: NONE
[フィルタ一覧] PVO: ✓ (359.1 > 10) | ADX: ✗ (18.07 < 31) | Volume: ✓ | Volatility: ✓
[最終判定] ✗ エントリー見送り（フィルター不合格）
```

**メリット：**
- 一目で全フィルターの合否が判明
- 見送り理由が明確に表示される
- 条件→フィルター→判定の論理的流れが視覚的に理解しやすい

**実装方法:**
- `filter_results = []` で全フィルター結果を集約
- `filter_results.append(f"PVO: ✓ ({value:.4f} > {threshold})")` で詳細情報付き
- `"[フィルタ一覧] " + " | ".join(filter_results)` で一行に整形
- 最終判定は ✅/✗ 絵文字で見送り理由を表示

### 4. エモジの活用で見やすさ向上

| 記号 | 意味 |
|------|------|
| ✓ | フィルター成功 |
| ✗ | フィルター失敗 |
| ✅ | エントリー許可 |
| ✗ | エントリー見送り |

## コード変更箇所

### src/trading_strategy.py

#### 1. クラス初期化（line ~54）
```python
self.last_strategy_signal = None  # 新指標の状態追跡用
```

#### 2. _evaluate_new_indicator_strategy()（lines 289-310）
- 状態キーの生成：`signal_key = f"{strategy_name}:{normalized}"`
- 状態変化検出：`if signal_key != self.last_strategy_signal:`
- 条件抽出：`conditions = result.get('conditions', {})`
- 条件表示：`condition_str = ", ".join([f"{k}={v}" for k, v in conditions.items()])`

#### 3. evaluate_entry() フィルター部分（lines 195-246）
- `filter_results = []` で結果を集約
- 個別ログの削除（PVO/ADX/Volume/Volatility）
- フィルター一覧の出力：`[フィルタ一覧] PVO: ✓ | ADX: ✗ | ...`

#### 4. 最終判定出力（lines 248-264）
```python
if allow_entry:
    self.logger.log(f"[最終判定] ✅ エントリー許可 ({desired_side})")
    side = desired_side
    decision = "ENTRY"
else:
    reason = "フィルター不合格" if failed_filters else "条件不満"
    self.logger.log(f"[最終判定] ✗ エントリー見送り（{reason}）")
```

## ログの流れ例

```
[条件一覧] PVO信号: ✓ | Donchian: BUY | Strategy: strategy_A (SELL)
           → 条件で 4 つの要素をチェック

[フィルタ一覧] PVO: ✓ (395.3 > 10) | ADX: ✓ (38.2 >= 25) | Volume: ✓ | Volatility: ✓
           → フィルター 4 つとも成功

[最終判定] ✅ エントリー許可 (BUY)
           → 最終的にエントリー判定
```

## 利点

1. **重複ログの削減** - 新指標のシグナルが変わらない限り出力されない
2. **情報の完全性** - 条件値を含むため、なぜそのシグナルなのかが分かる
3. **判定の明確化** - 一行で全フィルター結果が見える
4. **見送り理由の追跡** - 「フィルター不合格」なのか「戦略無し」なのかが分かる
5. **視覚的な判読性** - 絵文字と構造化で人間が見やすい

## テスト

バックテスト実行時に以下の点を確認：
- [ ] 新指標がシグナル変化時のみ出力される
- [ ] 各フィルター値が表示される
- [ ] 最終判定が ✅/✗ で表示される
- [ ] ログファイルサイズが大幅に削減される

## 関連コミット

- commit: 1498b82 "improve: ログ出力の改善 - 状態変化検出・条件表示・フィルタ一覧・最終判定構造化"
