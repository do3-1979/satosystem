# ロギング制御 - クイックスタートガイド

## シナリオ別使用方法

### シナリオ1: グラフ分析（指標の詳細検証）

**目的**: ローソク足、Donchian、PVO などの指標を全て表示してグラフで分析

```bash
# 方法A: コマンドラインで全ログ出力
python3 run_backtest.py --full-logging

# 方法B: config ファイルで指定
cp output_configs/config_detailed_logging.ini temp_analysis.ini
# temp_analysis.ini の logging_interval を 1 に設定
python3 -c "
import sys; sys.path.insert(0, 'src')
from config import Config
Config.set_config_file('temp_analysis.ini')
# ... バックテスト実行コード ...
"
```

**結果**:
- ✓ 全1分足データがログに記録
- ✓ `report/backtest_visualization_*.html` に全指標がプロット
- ✓ グラフズーム・レジェンド切り替えで詳細分析可能

---

### シナリオ2: 本番パラメータテスト（高速）

**目的**: 複数パラメータを素早くテスト、定量指標（PnL、WinRate）を比較

```bash
# 方法A: 高速モード（デフォルト）
python3 run_backtest.py

# 方法B: 明示的に高速設定
python3 run_backtest.py --logging-interval 10000 --fast-summary

# 方法C: config で設定
cp output_configs/config_fast_mode.ini temp_test.ini
python3 -c "
import sys; sys.path.insert(0, 'src')
from config import Config
Config.set_config_file('temp_test.ini')
# ... バックテスト実行 ...
"
```

**結果**:
- ✓ 処理時間: 約30%削減
- ✓ JSON メトリクスのみ出力（Excel・レポート・可視化スキップ）
- ✓ `report/backtest_summary_*.json` で定量結果を確認

---

### シナリオ3: バランス型（推奨）

**目的**: 標準的な分析（処理時間とグラフ精度のバランス）

```bash
python3 run_backtest.py --logging-interval 100
```

**結果**:
- ✓ ログサイズ: 約99%削減
- ✓ 処理時間: 約10%増加のみ
- ✓ グラフ表示: ほぼ問題なし

---

## ロギング間隔の選択ガイド

| logging_interval | 用途 | ログサイズ | 処理時間 | グラフ精度 |
|-----------------|------|----------|--------|----------|
| **1** | 指標検証 | 大 | +30% | ✓ 完全 |
| **100** | バランス型（推奨） | 1/100 | +10% | △ 最適 |
| **10000** | 本番テスト（デフォルト） | 1/10000 | -30% | ✗ 実用的でない |

---

## コマンドラインオプション

```
python3 run_backtest.py [OPTIONS]

OPTIONS:
  --full-logging              全ログ出力（logging_interval=1）
  --logging-interval N        ロギング間隔をNに指定（1,100,10000など）
  --period START END          テスト期間を指定（例: "2025/11/01 00:00" "2025/11/25 23:59"）
  --fast-summary             高速サマリモード（Excel/レポート/可視化をスキップ）
  
EXAMPLES:
  python3 run_backtest.py --full-logging
  python3 run_backtest.py --logging-interval 100 --fast-summary
  python3 run_backtest.py --period "2025/11/01 00:00" "2025/11/25 23:59"
```

---

## ファイル構成

```
output_configs/
├── config_detailed_logging.ini  ← グラフ分析用（logging_interval=1）
├── config_fast_mode.ini         ← 本番テスト用（logging_interval=10000）
└── ...

run_backtest.py                  ← ロギング制御用ヘルパースクリプト

docs/
├── LOGGING_CONTROL_GUIDE.md     ← 詳細ドキュメント
└── ...
```

---

## トラブルシューティング

### Q: グラフが正確でない（ギャップがある）
**A**: `logging_interval` が高すぎます。
```bash
python3 run_backtest.py --full-logging  # logging_interval=1 に設定
```

### Q: バックテストが遅い
**A**: 高速モードを使用してください。
```bash
python3 run_backtest.py --fast-summary
```

### Q: ログファイルサイズが大きい
**A**: `logging_interval` を増やしてください。
```bash
python3 run_backtest.py --logging-interval 1000
```

---

## 参考ドキュメント

- 詳細説明: [`docs/LOGGING_CONTROL_GUIDE.md`](../LOGGING_CONTROL_GUIDE.md)
- 実装詳細: `src/bot.py` (Lines 720-730)
- 設定管理: `src/config.py` (Lines 664-672)

---

**作成日**: 2025-11-26
