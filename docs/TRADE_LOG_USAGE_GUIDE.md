# Trade Log JSON システム - 使用ガイド

## 概要

Trade Log JSON システムは、Bitcoin 自動取引ボットのすべてのトレード情報を構造化されたJSON形式で自動的に記録します。これにより、統計分析、パターン検出、改善案の検証が効率的に実施できます。

---

## クイックスタート

### 1. バックテスト実行（自動で Trade Log JSON を生成）

```bash
cd /home/satoshi/work/satosystem
python3 src/bot.py
```

**出力**:
- `logs/trade_log_{timestamp}.json` - 55トレード全メタデータ（約78KB）

### 2. 基本統計分析

```bash
python3 tools/analyze_trade_log.py logs/trade_log_20260105082010.json
```

**出力**:
- `logs/trade_log_analysis_{timestamp}.json` - フィルター別・市場レジーム別分析

### 3. 統計検定（Bootstrap CI）

```bash
python3 tools/analyze_trade_log_statistics.py logs/trade_log_20260105082010.json
```

**出力**:
- `logs/statistical_analysis_{timestamp}.json` - Bootstrap 95% CI、統計検定結果

### 4. 結果の確認

```bash
# 要約統計を表示
cat logs/statistical_analysis_*.json | jq '.summary'

# フィルター効果を表示
cat logs/statistical_analysis_*.json | jq '.filter_analysis'
```

---

## Trade Log JSON 構造

### ファイル形式

```json
{
  "metadata": {
    "generated_at": "2025-01-05T08:20:10",
    "total_trades": 55,
    "completed_trades": 55
  },
  "trades": [
    {
      "trade_id": "2024/01/30 01:00_BUY_42982",
      "entry": {
        "timestamp": "2024-01-30T01:00:00",
        "side": "BUY",
        "price": 42982.50,
        "signals": {
          "pvo_signal": true,
          "donchian_signal": "BUY",
          "strategy_signal": "NONE"
        },
        "filters": {
          "pvo": {"pass": true, "value": 395.30, "threshold": 10.0},
          "adx": {"pass": true, "value": 38.20, "threshold": 25.0},
          "volume": {"pass": true, "value": 2100000, "threshold": 1500000},
          "volatility": {"pass": true, "value": 1.25, "threshold": 2.50}
        },
        "market": {
          "regime": "TRANSITION",
          "confidence": 0.65
        }
      },
      "exit": {
        "timestamp": "2024-01-30T03:00:00",
        "price": 43150.75,
        "reason": "TAKE_PROFIT"
      },
      "result": {
        "pnl_usd": 168.25,
        "pnl_pct": 0.39,
        "max_drawdown_usd": -45.00,
        "max_drawdown_pct": -0.10,
        "bars_held": 120,
        "duration_minutes": 120,
        "cumulative_pnl": 1731.29,
        "win": true
      }
    }
  ]
}
```

### 各フィールドの説明

#### Entry（進入時）

| フィールド | 説明 | 例 |
|-----------|------|-----|
| `timestamp` | 進入時刻 | 2024-01-30T01:00:00 |
| `side` | 取引方向 | BUY / SELL |
| `price` | 進入価格 | 42982.50 |
| `signals.pvo_signal` | PVO シグナル | true / false |
| `signals.donchian_signal` | Donchian シグナル | BUY / SELL / NONE |
| `signals.strategy_signal` | Strategy シグナル | 通常は NONE |
| `filters.*.pass` | フィルター合格判定 | true / false |
| `filters.*.value` | フィルター現在値 | 395.30 等 |
| `filters.*.threshold` | フィルター閾値 | 10.0 等 |
| `market.regime` | 市場レジーム | TRANSITION / TRENDING_UP / TRENDING_DOWN |
| `market.confidence` | レジーム確信度 | 0.65 等 |

#### Exit（撤出時）

| フィールド | 説明 | 例 |
|-----------|------|-----|
| `timestamp` | 撤出時刻 | 2024-01-30T03:00:00 |
| `price` | 撤出価格 | 43150.75 |
| `reason` | 撤出理由 | TAKE_PROFIT / STOP_LOSS / TRAILING_STOP |

#### Result（取引結果）

| フィールド | 説明 | 例 |
|-----------|------|-----|
| `pnl_usd` | 利益（ドル） | 168.25 |
| `pnl_pct` | 利益（パーセント） | 0.39 |
| `max_drawdown_usd` | 最大ドローダウン（ドル） | -45.00 |
| `max_drawdown_pct` | 最大ドローダウン（パーセント） | -0.10 |
| `bars_held` | 保有バー数 | 120 |
| `duration_minutes` | 保有時間（分） | 120 |
| `cumulative_pnl` | 累積 PnL（ドル） | 1731.29 |
| `win` | 勝敗フラグ | true / false |

---

## カスタム分析スクリプト

### テンプレート1: フィルター別分析

```python
import json

# Trade Log を読み込む
with open('logs/trade_log_20260105082010.json', 'r') as f:
    data = json.load(f)

# Volatility フィルターで分析
volatility_pass_trades = []
volatility_fail_trades = []

for trade in data['trades']:
    volatility_status = trade['entry']['filters']['volatility']['pass']
    pnl = trade['result']['pnl_usd']
    
    if volatility_status:
        volatility_pass_trades.append(pnl)
    else:
        volatility_fail_trades.append(pnl)

# 統計を計算
import statistics

print(f"Volatility PASS: {len(volatility_pass_trades)} 件")
print(f"  勝率: {sum(1 for x in volatility_pass_trades if x > 0) / len(volatility_pass_trades) * 100:.1f}%")
print(f"  平均 PnL: ${statistics.mean(volatility_pass_trades):.2f}")

print(f"\nVolatility FAIL: {len(volatility_fail_trades)} 件")
print(f"  勝率: {sum(1 for x in volatility_fail_trades if x > 0) / len(volatility_fail_trades) * 100:.1f}%")
print(f"  平均 PnL: ${statistics.mean(volatility_fail_trades):.2f}")
```

### テンプレート2: 市場レジーム別分析

```python
import json
from collections import defaultdict

# Trade Log を読み込む
with open('logs/trade_log_20260105082010.json', 'r') as f:
    data = json.load(f)

# 市場レジーム別に集計
regime_stats = defaultdict(lambda: {'pnls': [], 'count': 0})

for trade in data['trades']:
    regime = trade['entry']['market']['regime']
    pnl = trade['result']['pnl_usd']
    
    regime_stats[regime]['pnls'].append(pnl)
    regime_stats[regime]['count'] += 1

# 結果を表示
for regime, stats in regime_stats.items():
    pnls = stats['pnls']
    print(f"\n市場レジーム: {regime} ({len(pnls)} 件)")
    print(f"  勝率: {sum(1 for x in pnls if x > 0) / len(pnls) * 100:.1f}%")
    print(f"  平均 PnL: ${sum(pnls) / len(pnls):.2f}")
    print(f"  総 PnL: ${sum(pnls):.2f}")
```

### テンプレート3: 撤出理由別分析

```python
import json
from collections import defaultdict

# Trade Log を読み込む
with open('logs/trade_log_20260105082010.json', 'r') as f:
    data = json.load(f)

# 撤出理由別に集計
exit_reason_stats = defaultdict(lambda: {'pnls': [], 'count': 0})

for trade in data['trades']:
    reason = trade['exit']['reason']
    pnl = trade['result']['pnl_usd']
    
    exit_reason_stats[reason]['pnls'].append(pnl)
    exit_reason_stats[reason]['count'] += 1

# 結果を表示
for reason, stats in exit_reason_stats.items():
    pnls = stats['pnls']
    print(f"\n撤出理由: {reason} ({len(pnls)} 件)")
    print(f"  勝率: {sum(1 for x in pnls if x > 0) / len(pnls) * 100:.1f}%")
    print(f"  平均 PnL: ${sum(pnls) / len(pnls):.2f}")
    print(f"  総 PnL: ${sum(pnls):.2f}")
```

---

## 分析スクリプト仕様

### analyze_trade_log.py

**用途**: 基本的な統計情報を計算

**入力**:
```bash
python3 tools/analyze_trade_log.py <path_to_trade_log.json>
```

**出力**: `logs/trade_log_analysis_{timestamp}.json`

**含まれる情報**:
- 基本統計（勝敗数、勝率、総 PnL、平均 PnL）
- フィルター別統計（PVO, ADX, Volume, Volatility）
- 市場レジーム別統計
- フィルター効果分析（各フィルターの pass/fail で成績がどう変わるか）

### analyze_trade_log_statistics.py

**用途**: 統計的検定を実施

**入力**:
```bash
python3 tools/analyze_trade_log_statistics.py <path_to_trade_log.json>
```

**出力**: `logs/statistical_analysis_{timestamp}.json`

**含まれる情報**:
- Bootstrap 信頼区間（95% CI）
- フィルター効果の有意性検定
- 市場レジーム別の有意性検定

**統計的有意性の解釈**:
- **CI が 0 を含まない** → 統計的に有意（改善は偶然ではない）
- **CI が 0 を含む** → 統計的に有意でない（偶然の可能性）

---

## 実装の詳細

### TradeLogger クラス（src/trade_logger.py）

#### 主要メソッド

```python
class TradeLogger:
    def __init__(self, log_dir: str):
        """初期化"""
        
    def log_entry(self, entry_data: dict):
        """ENTRY デシジョン時に呼び出し"""
        
    def log_exit(self, exit_data: dict):
        """EXIT デシジョン時に呼び出し"""
        
    def save_trades_json(self, filename: str) -> str:
        """JSON ファイルに保存"""
        return filepath
        
    def get_statistics(self) -> dict:
        """統計サマリーを取得"""
        return {
            'total_trades': 55,
            'completed_trades': 55,
            'wins': 53,
            'losses': 2,
            'win_rate': 0.964
        }
```

#### bot.py での統合箇所

**1. インポート** (src/bot.py の先頭)
```python
from trade_logger import TradeLogger
```

**2. 初期化** (Bot.__init__)
```python
self.trade_logger = TradeLogger(Config.get_log_dir_name())
```

**3. ENTRY 時** (ENTRY デシジョン時)
```python
if trade_decision["decision"] == "ENTRY":
    entry_data = {
        'timestamp': entry_time,
        'side': trade_decision["side"],
        'price': price,
        # ... すべてのシグナル、フィルター値、市場レジームを記録
    }
    self.trade_logger.log_entry(entry_data)
```

**4. EXIT 時** (EXIT デシジョン時)
```python
if trade_decision["decision"] == "EXIT":
    exit_data = {
        'timestamp': exit_time,
        'price': exit_price,
        'pnl_usd': pnl,
        'reason': exit_reason,
        # ... その他の撤出情報
    }
    self.trade_logger.log_exit(exit_data)
```

**5. バックテスト終了時** (backtest 終了)
```python
trade_log_path = self.trade_logger.save_trades_json(f"trade_log_{ts}.json")
stats = self.trade_logger.get_statistics()
self.logger.log(f"トレード統計: {stats}")
```

---

## パフォーマンス結果

### 最新バックテスト（2024/01/01～2025/09/30）

```
【基本統計】
  総トレード数: 55
  勝利: 53 (96.4%)
  損失: 2 (3.6%)
  総 PnL: 95,220.68 USD
  平均 PnL: 1,731.29 USD

【Bootstrap 95% 信頼区間】
  点推定: 1,731.29 USD
  95% CI: [1,294.92, 2,206.54] USD
  統計的有意性: ✓ YES（0 を含まない）

【フィルター別分析】
  Volatility PASS: 37 件、94.6% 勝率、1,222.62 USD 平均
  Volatility FAIL: 18 件、100.0% 勝率、2,776.86 USD 平均

【市場レジーム】
  TRANSITION: 55 件 (100%)
```

### 重要な発見

⚠️ **Volatility フィルターの逆説的な効果**:
- Volatility が FAIL（高ボラティリティ）の環境では、むしろパフォーマンスが良い（100% 勝率）
- これは直感と反対だが、統計データが示す現実

→ **Phase 4**: Volatility フィルターの実装ロジックを詳細に検証予定

---

## トラブルシューティング

### Q: Trade Log JSON が生成されない

**確認項目**:
1. `src/bot.py` に TradeLogger が統合されているか確認
   ```bash
   grep "trade_logger" src/bot.py
   ```

2. バックテスト実行ログで エラーがないか確認
   ```bash
   python3 src/bot.py 2>&1 | tail -20
   ```

3. `logs/` ディレクトリが存在するか確認
   ```bash
   ls -la logs/
   ```

### Q: 分析スクリプトがエラーになる

**確認項目**:
1. Trade Log ファイル名を正しく指定しているか
   ```bash
   ls -la logs/trade_log_*.json
   ```

2. Python モジュールが揃っているか（numpy, scipy 等）
   ```bash
   python3 -c "import numpy, scipy; print('OK')"
   ```

3. JSON ファイルの形式が正しいか
   ```bash
   python3 -c "import json; json.load(open('logs/trade_log_*.json'))"
   ```

### Q: Bootstrap CI の計算が遅い

**原因**: デフォルトで 10,000 回のリサンプリングを実行

**解決**:
```python
# analyze_trade_log_statistics.py の以下の行を修正
n_iterations = 10000  # → 1000 に減らす
```

---

## 次ステップ

### Phase 4: Core Logic Validation

Trade Log JSON データを使用して以下を検証:

1. **Volatility フィルター実装の検証**
   - 現在: Volatility FAIL で高パフォーマンス（逆説的）
   - 検証: なぜこのような結果になるのか詳細分析

2. **Market Regime Detection**
   - 現在: すべてのトレードが TRANSITION（異常）
   - 検証: ロジックが正しく機能しているか確認

3. **Strategy Signal**
   - 現在: すべてのトレードで NONE（記録されていない）
   - 検証: ロジックが有効か確認

### Phase 5: パターン検出と改善

1. 損失トレードの共通パターン検出
2. 各パターンに対する改善案自動生成
3. A/B テストで改善案の効果検証

---

## 参考資料

- [LOSS_TRADE_ANALYSIS_PLAN.md](../docs/LOSS_TRADE_ANALYSIS_PLAN.md) - 完全な分析フレームワーク
- [TRADE_LOG_IMPLEMENTATION_SUMMARY.md](../docs/TRADE_LOG_IMPLEMENTATION_SUMMARY.md) - 実装の詳細サマリー
- [src/trade_logger.py](../src/trade_logger.py) - TradeLogger クラスソースコード
- [tools/analyze_trade_log.py](../tools/analyze_trade_log.py) - 基本統計分析スクリプト
- [tools/analyze_trade_log_statistics.py](../tools/analyze_trade_log_statistics.py) - 統計検定スクリプト

---

**最終更新**: 2025/01/05  
**ステータス**: 実装完了・運用中
