# ロギング制御ガイド

## 概要

バックテスト実行時、デフォルトではログが「間引き」されています。これはパフォーマンス最適化のための仕組みですが、指標の検証や市場データの詳細分析には **全データのログ出力** が必要です。

本ガイドでは、ログ間引きの仕組みと、実データグラフ出力用に全ログを取得する方法を説明します。

---

## 1. ログ間引きの仕組み

### 実装箇所
- **ファイル**: `src/bot.py` (Lines 720-730)
- **制御変数**: `logging_interval` (config.ini)

### デフォルト動作

```python
# src/bot.py の実装
self._log_counter += 1
force_log = trade_executed or (self._log_counter % self._logging_interval == 0)

if force_log:
    # ログ出力
```

**ロジック**:
- 通常は `logging_interval` の倍数回毎にのみログを出力（高速化）
- ただし、トレード実行時（ENTRY/ADD/EXIT）は **常に** ログを出力（重要イベント）
- これにより、ログサイズ・処理時間を削減しながら取引情報は完全に記録

### デフォルト値

| 設定項目 | デフォルト値 | 説明 |
|---------|----------|------|
| `logging_interval` | 10000 | 10,000イテレーション毎にログ出力 |

---

## 2. パフォーマンス影響

### ログ出力有無による差分

| 期間 | ロギング削減率 | 処理時間短縮 |
|------|--------------|----------|
| 1週間 BT | 17.87% → 1.36% | 41.9s → 29.5s (29%削減) |
| 10週間 BT | 0.41% | ~13m56s (安定) |

※ `logging_interval=100` の場合の測定値

---

## 3. 全ログ出力（実データグラフ用）

### 3.1 Config設定で制御

#### 方法: config.ini で `logging_interval` を変更

**ファイル**: `src/config.ini` または config ファイル

```ini
[Log]
logging_interval = 1  # 毎回ログ出力（間引きなし）
```

**効果**:
- 1分足の全データがログに出力される
- グラフ可視化で全指標が正確に表示
- 処理時間は約30%増加

#### 設定手順

1. **テンポラリ config ファイルを作成**

```bash
cp src/config.ini temp_config_full_log.ini
```

2. **logging_interval を変更**

```ini
[Log]
logging_interval = 1  # 毎回ログ出力
```

3. **バックテスト実行時に指定**

```bash
# Python スクリプト内
from src.config import Config
Config.set_config_file('temp_config_full_log.ini')
```

### 3.2 コマンドラインで制御（将来実装予定）

```bash
# 予定: 全ログ出力モード
python3 backtest.py --log-all
python3 backtest.py --full-logging

# 予定: ログ間隔指定
python3 backtest.py --logging-interval 1
```

---

## 4. ビジュアル分析用ワークフロー

### 4.1 実データグラフの生成手順

#### ステップ1: 全ログ出力でバックテスト実行

```python
import sys
sys.path.insert(0, 'src')

from config import Config
from bot import Bot
# ... 初期化コード ...

# 全ログ出力に設定
Config.set_config_file('temp_config_full_log.ini')

# バックテスト実行
bot = Bot(...)
bot.run()
```

#### ステップ2: 可視化エンジンでグラフ生成

```python
from visualizer import Visualizer

vis = Visualizer()
vis.visualize_backtest(
    log_directory="logs",
    output_html="report/analysis_full_logs.html",
    start_time="2025/11/01 00:00",
    end_time="2025/11/25 23:59"
)
```

#### ステップ3: ブラウザで確認

```bash
# ブラウザで開く
open report/analysis_full_logs.html
```

---

## 5. ロギング制御の詳細仕様

### 5.1 出力対象

**常に出力される（logging_interval に関わらず）**:
- ENTRY: ポジション新規オープン
- ADD: ポジション追加
- EXIT: ポジション決済
- 予約済みポジション情報

**間引き対象（logging_interval の倍数回毎）**:
- OHLCV (Open, High, Low, Close, Volume)
- 技術指標 (Donchian, PVO, ATR, etc.)
- 口座状態 (残高, ポジション情報)

### 5.2 データグラフ表示に必要なログ

| 指標 | ログ必須 | 間引き耐性 |
|------|---------|----------|
| ローソク足 (OHLCV) | ✓ 必須 | ✗ 低い |
| Donchian Channel | ✓ 必須 | ✗ 低い |
| PVO | ✓ 必須 | ✗ 低い |
| ATR | ✓ 必須 | ✗ 低い |
| Volatility | ✓ 必須 | ✗ 低い |
| エントリ/イグジット点 | ✓ 必須 | ✓ 高い |

**結論**: **指標検証には全ログ出力 (`logging_interval=1`) が必須**

---

## 6. 推奨設定

### 6.1 本番運用（高速）

```ini
[Log]
logging_interval = 10000  # デフォルト: 高速
```

**特徴**:
- ✓ 最高パフォーマンス
- ✓ ログサイズ最小
- ✗ 指標検証に不向き

### 6.2 指標検証（詳細）

```ini
[Log]
logging_interval = 1  # 毎回出力
```

**特徴**:
- ✓ 全指標が正確に表示
- ✓ データグラフで検証可能
- ✗ 処理時間 +30%
- ✗ ログサイズ大

### 6.3 バランス型（将来実装予定）

```ini
[Log]
logging_interval = 100  # 100回毎
```

**特徴**:
- 処理時間: 約 10% 増加
- ログサイズ: 約 90% 削減
- グラフ表示: ほぼ問題なし

---

## 7. 実装チェックリスト

- [x] ログ間引き機構の確認 (`logging_interval`)
- [x] 重要イベント強制ログの確認
- [x] ドキュメント作成
- [ ] CLI オプション実装 (`--full-logging`, `--logging-interval`)
- [ ] 推奨設定テンプレート作成
- [ ] ビジュアル分析ワークフロー自動化

---

## 8. トラブルシューティング

### Q: グラフにローソク足が表示されない

**A**: `logging_interval` が高すぎる可能性があります。

```python
# 確認
from src.config import Config
logging_interval = Config.get_logging_interval()
print(f"logging_interval: {logging_interval}")

# 解決
# → logging_interval = 1 に変更してバックテストを再実行
```

### Q: ログファイルサイズが大きすぎる

**A**: `logging_interval` を調整してください。

| logging_interval | ログサイズ削減 | 指標精度 |
|-----------------|--------------|--------|
| 1 | 基準 (100%) | ✓ 完全 |
| 10 | 90% | △ 最小限ズレ |
| 100 | 99% | △ ズレあり |
| 10000 | 99.99% | ✗ 実用的でない |

### Q: バックテスト時間が長すぎる

**A**: `logging_interval` を増やすか、テスト期間を短縮してください。

```python
# 方法1: ログ出力を減らす
Config.set_config_file('temp_config_fast.ini')
# → logging_interval = 10000

# 方法2: テスト期間を短縮
start_time = "2025/11/20 00:00"  # より直近
end_time = "2025/11/25 23:59"
```

---

## 9. 次のステップ

1. **CLI オプション実装**
   - `--full-logging` フラグで全ログ出力
   - `--logging-interval N` で間隔を指定

2. **設定テンプレート**
   - `config_fast.ini` - 高速モード
   - `config_detailed.ini` - 詳細分析用

3. **自動化スクリプト**
   - バックテスト → グラフ生成を一括実行
   - 複数期間の並列実行

---

## 参考資料

- `src/bot.py` L720-730: ログ出力制御実装
- `src/config.py` L664-672: ロギング間隔設定
- `src/visualizer.py`: グラフ生成エンジン
- `docs/analysis/PROJECT_ANALYSIS_2025-11-16.md`: パフォーマンス分析

---

**最終更新**: 2025-11-26  
**作成者**: GitHub Copilot
