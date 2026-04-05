---
description: 全Qテスト（四半期別バックテスト）を実行し、ベースラインと比較して結果を検証するスキル。「全Qテスト」「四半期テスト」「ベースライン比較」「バックテスト検証」を依頼されたときに使用する。
applyTo: "**"
---

# 全Qテスト（四半期別バックテスト）実行・検証スキル

## 目的

BTC と XAUT の四半期別バックテストを実行し、既存ベースラインと比較して：
- 損益がベースライン以上か（大幅な利益減少がないか）
- 各四半期の結果が安定しているか
- レグレッションテストが全 PASS か

## 前提条件

- OHLCV キャッシュ DB が最新であること（`./commands/prj-update-ohlcv-db --stats` で確認）
- レグレッションテストが全 PASS であること

## 手順

### 1. レグレッションテスト実行（BTC + XAUT）

```bash
cd /home/satoshi/work/satosystem
./commands/prj-run-regression
```

合格基準：全テスト PASS（現在 190/190）

### 2. BTC 四半期バックテスト実行

```bash
cd /home/satoshi/work/satosystem
python3 run_quarterly_backtest.py
```

### 3. XAUT 四半期バックテスト実行

```bash
cd /home/satoshi/work/satosystem
python3 run_quarterly_backtest.py --config config_xaut.ini
```

### 4. ベースラインとの比較

ベースラインファイル：
- BTC: `baseline_backup/BASELINE_BTC_*.json`（最新のもの）
- XAUT: `baseline_backup/BASELINE_XAUT_*.json`（最新のもの）

比較スクリプト例：
```python
import json, glob

def compare_baseline(symbol, results_dir, baseline_pattern):
    # 最新の結果ファイル
    results = sorted(glob.glob(f'docs/quarterly_backtest_results/{symbol}/quarterly_results_*.json'))[-1]
    current = json.load(open(results))
    current_total = sum(q['metrics']['total_pnl'] for q in current['quarterly'])

    # 最新のベースライン
    baselines = sorted(glob.glob(f'baseline_backup/BASELINE_{symbol}_*.json'))[-1]
    baseline = json.load(open(baselines))
    baseline_total = baseline['baseline_info']['cumulative_pnl_usd']

    diff = current_total - baseline_total
    pct = (diff / abs(baseline_total)) * 100 if baseline_total != 0 else 0

    return {
        'symbol': symbol,
        'baseline': baseline_total,
        'current': current_total,
        'diff': diff,
        'diff_pct': pct,
        'pass': diff >= -abs(baseline_total) * 0.05  # 5%以内の劣化は許容
    }
```

### 5. 判定基準

| チェック項目 | 合格基準 |
|---|---|
| レグレッションテスト | 全 PASS（100%） |
| BTC 累積損益 | ベースラインと一致 or 改善 |
| XAUT 累積損益 | ベースラインと一致 or 改善 |
| 大幅劣化 | 累積損益が 5% 以上減少していないこと |
| 各四半期 | 大多数の四半期で損益が改善 or 維持 |

### 6. ベースライン更新（結果改善時）

改善が確認された場合：

```bash
# ベースライン JSON を作成
python3 -c "
import json
from datetime import datetime

results = json.load(open('docs/quarterly_backtest_results/SYMBOL/quarterly_results_YYYYMMDD_HHMMSS.json'))
total = sum(q['metrics']['total_pnl'] for q in results['quarterly'])
trades = sum(q['metrics']['trades'] for q in results['quarterly'])

baseline = {
    'baseline_info': {
        'name': 'SYMBOL_XXX.XXUSD_YYYYMMDD',
        'version': 'vYYYY.MM.DD-description',
        'created_at': datetime.now().isoformat(),
        'description': '説明',
        'symbol': 'SYMBOL/USDT',
        'config': 'config_xxx.ini',
        'cumulative_pnl_usd': round(total, 2),
        'total_trades': trades,
    },
    'quarterly_results': results['quarterly'],
}

with open('baseline_backup/BASELINE_SYMBOL_XXX.XXUSD_YYYYMMDD.json', 'w') as f:
    json.dump(baseline, f, indent=2, ensure_ascii=False)
"
```

## 出力フォーマット

```
## 全Qテスト結果

### レグレッションテスト
- BTC + XAUT: XXX/XXX PASS ✅/❌

### BTC 四半期バックテスト
| 四半期 | ベースライン | 今回 | 差分 | 判定 |
|--------|-------------|------|------|------|
| 2024Q1 | XXX.XX | XXX.XX | +X.XX | ✅/⚠️ |
| ... | | | | |
| **合計** | **XXXX.XX** | **XXXX.XX** | **+X.XX** | **✅/❌** |

### XAUT 四半期バックテスト
| 四半期 | ベースライン | 今回 | 差分 | 判定 |
|--------|-------------|------|------|------|
| 2025Q2 | XX.XX | XX.XX | +X.XX | ✅/⚠️ |
| ... | | | | |
| **合計** | **XX.XX** | **XX.XX** | **+X.XX** | **✅/❌** |

### 総合判定
- BTC: ベースライン一致/改善/劣化 ✅/❌
- XAUT: ベースライン一致/改善/劣化 ✅/❌
- コミット可否: ✅ 可能 / ❌ 要修正
```

## 注意事項

- BTC と XAUT は完全に独立して実行される（subprocess 隔離）
- Config, Log, OHLCV キャッシュは symbol で分離されている
- 四半期テストは 10-20 分かかる場合がある
- ベースライン更新後は必ずコミットに含める
