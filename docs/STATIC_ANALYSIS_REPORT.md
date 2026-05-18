# ソースコード静的解析レポート

**対象バージョン**: satosystem gen2 (2026-05-16)  
**解析対象**: `src/` 以下の全 Python モジュール（約15,800行）  
**解析方法**: 手動コードレビュー（構造・ロジック・パターン分析）

---

## 概要

| 種別 | 件数 | 状態 |
|---|---|---|
| バグ（潜在的なランタイムエラー） | 1 | 修正済み |
| 冗長コード（機能影響なし） | 3 | 修正済み |
| 設計不整合（意図との乖離） | 4 | 要注意 |

---

## 1. バグ

### [BUG-001] bot.py — `else: raise` による潜在的 RuntimeError

- **ファイル**: `src/bot.py` 付近の注文サイジングブロック
- **問題**: `trade_decision["decision"]` が想定外の値を持つ場合、`else: raise` がアクティブ例外なしで実行され `RuntimeError: No active exception to re-raise` が発生する
- **影響範囲**: ENTRY / ADD / EXIT / SCALE_OUT / SCALE_IN 以外のdecisionが渡された場合に限り発生（通常パスでは問題なし）
- **修正方法**:

```python
# 修正前
else:
    raise

# 修正後
else:
    raise ValueError(f"Unknown trade decision: {trade_decision['decision']}")
```

- **状態**: ✅ 修正済み

---

## 2. 冗長コード

### [REDUN-001] risk_management.py — `stop_AF_add` / `stop_AF_max` 二重代入

- **ファイル**: `src/risk_management.py` 付近の `__init__` または設定読み込みブロック
- **問題**: `stop_AF_add` と `stop_AF_max` が同一値で2回連続代入されている。機能的な影響は一切ないが、コードが冗長で誤解を招く。
- **修正方法**: 後方の重複代入行を削除

```python
# 修正前（重複あり）
self.stop_AF_add = float(config.get("RiskManagement", "stop_af_add", fallback=0.02))
self.stop_AF_max = float(config.get("RiskManagement", "stop_af_max", fallback=0.20))
self.stop_AF_add = float(config.get("RiskManagement", "stop_af_add", fallback=0.02))  # ← 削除
self.stop_AF_max = float(config.get("RiskManagement", "stop_af_max", fallback=0.20))  # ← 削除

# 修正後
self.stop_AF_add = float(config.get("RiskManagement", "stop_af_add", fallback=0.02))
self.stop_AF_max = float(config.get("RiskManagement", "stop_af_max", fallback=0.20))
```

- **状態**: ✅ 修正済み

### [REDUN-002] bot.py:execute_order() — 未使用変数 `symbol`

- **ファイル**: `src/bot.py` の `execute_order()` メソッド内
- **問題**: `symbol = order['symbol']` と代入しているが、以降で `symbol` を使用していない。コメントでも `# execute orderには使わない` と明記されている。
- **影響**: なし（実行時に変数が評価されるだけ）
- **修正方法**: 該当行を削除

```python
# 削除対象
symbol = order['symbol']  # execute orderには使わない
```

- **状態**: ✅ 修正済み

### [REDUN-003] exit_strategy_v2.py — 放棄機能の Dead Code

- **ファイル**: `src/exit_strategy_v2.py`
- **問題**: Task 39a（Trailing Profit Target）が検証で不採用（−$1,077 USD 劣化）となった後も、関連するコード (`trailing_profit_enabled = False`、`tier1_trigger`〜`tier3_size` パラメータ群) が残存している。
- **影響**: `trailing_profit_enabled = False` の固定値により、関連ロジックは永遠に実行されない
- **修正方法（任意）**: Dead code ブロックを削除してコードを整理（機能影響なし）
- **状態**: ⚠️ 低優先度・未修正（将来の整理タスクで対処）

---

## 3. 設計不整合

### [DESIGN-001] mean_reversion_strategy.py — 非標準 RSI 計算

- **ファイル**: `src/mean_reversion_strategy.py`
- **問題**: RSI 計算に Wilder の指数平滑移動平均（EMA方式）ではなく、単純移動平均（SMA方式）を使用している。これにより、同じ期間パラメータでも一般的な RSI ライブラリと異なる値が出力される。
- **影響**: **本番での影響なし**（`enable_mean_reversion_strategy = 0` でデフォルト無効）。有効化した場合、バックテストで調整したパラメータが本来の RSI 値とズレる。
- **推奨対応**: MR戦略を有効化する場合は Wilder EMA 方式に修正する

```python
# 現状（SMA方式）
avg_gain = sum(gains[-period:]) / period
avg_loss = sum(losses[-period:]) / period

# 推奨（Wilder EMA方式）
alpha = 1 / period
avg_gain = gains[-1]  # seed
for g in gains[-period+1:]:
    avg_gain = alpha * g + (1 - alpha) * avg_gain
# avg_loss も同様
```

- **状態**: ⚠️ MR戦略を有効化するまでは影響なし

### [DESIGN-002] vcp_strategy.py — VCP 評価結果がエントリー判定に反映されない

- **ファイル**: `src/vcp_strategy.py` / `src/trading_strategy.py`
- **問題**: `VCPStrategy.evaluate()` の結果は `TradingStrategy` 内で `self.vcp_signal_latest` に保存されるが、`allow_entry` フラグを変更しないため、VCP パターンを検出してもエントリー判断には一切影響しない。
- **影響**: VCP 計算コストが毎ループ発生するが効果がない
- **設計意図と現実のズレ**: VCP を「フィルター」として使うつもりであれば、`allow_entry` に連携させる必要がある。現状は「ログ記録専用」の補助情報として機能している。
- **推奨対応**:
  - VCP を実際のフィルターとして使う → `allow_entry = allow_entry and vcp_signal` に変更してバックテスト検証
  - VCP を廃止する → 関連コード削除でパフォーマンス改善
  - 現状維持（ログ専用）→ コメントを明確にして意図を文書化
- **状態**: ⚠️ 設計方針の決定が必要

### [DESIGN-003] trading_strategy.py — MeanReversion 有効時に BUY 方向固定

- **ファイル**: `src/trading_strategy.py`
- **問題**: `enable_mean_reversion_strategy = True` 時、Donchian Breakout 評価ロジックが完全スキップされ、MeanReversion の BUY シグナルのみが生成される。SELL エントリーが発生しない片方向戦略になる。
- **影響**: **本番での影響なし**（デフォルト `enable_mean_reversion_strategy = 0`）。MR 戦略を有効化した場合は下げ相場でのショート機会を逃す。
- **推奨対応**: MR 戦略を評価・有効化する前に、SELL シグナルの統合方法を設計する
- **状態**: ⚠️ MR戦略有効化時に要対応

### [DESIGN-004] risk_management.py — `get_donchian_high/low()` のタイムフレームハードコード

- **ファイル**: `src/risk_management.py` の `get_donchian_high()` / `get_donchian_low()`
- **問題**: これらのメソッド内で `main_time_frame = '1h'` がハードコードされている。ボット本体は 4H 足（240分）を使用しており、設定値と異なる。
- **影響**: これらのメソッドは **VCPStrategy 専用**（`vcp_strategy.py` から呼び出される）であり、メインの Donchian シグナル（`price_data_management.py` 内で生成）とは別系統。デフォルトで VCP が無効なため本番影響なし。
- **推奨対応**: VCP を有効化する場合は `main_time_frame` を `config.time_frame` 等から動的に読み込む
- **状態**: ⚠️ VCP有効化時に要対応

---

## 修正済み変更一覧

| ID | ファイル | 変更内容 |
|---|---|---|
| BUG-001 | `src/bot.py` | `else: raise` → `else: raise ValueError(f"Unknown trade decision: ...")` |
| REDUN-001 | `src/risk_management.py` | `stop_AF_add` / `stop_AF_max` 重複代入行を削除 |
| REDUN-002 | `src/bot.py` | `execute_order()` 内の未使用 `symbol` 変数削除 |

---

## 非修正事項（設計方針として保留）

| ID | 理由 |
|---|---|
| REDUN-003 | Dead code の除去は機能影響なし・低優先度。将来の整理タスクで対処。 |
| DESIGN-001 | MR戦略無効（本番設定）のため影響なし。有効化時に再対応。 |
| DESIGN-002 | VCPのエントリー統合は独立した検証タスクとして扱うべき。 |
| DESIGN-003 | MR有効化のタイミングで SELL 統合を設計する。 |
| DESIGN-004 | VCP無効（本番設定）のため影響なし。有効化時に再対応。 |

---

*生成日: 2026-05-16 | 解析者: GitHub Copilot (Claude Sonnet 4.6)*
