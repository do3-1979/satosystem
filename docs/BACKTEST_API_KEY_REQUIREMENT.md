# バックテスト実行に必要な API キー設定

## 問題の背景

Phase 1 バックテスト実行時に、すべてのパターンで同じ結果（PnL=$-269）が返されていた。

### 根本原因の階層化診断

#### Level 1: コンフィグ形式
- **Status**: ✅ 修正完了
- **Issue**: コンフィグのタイムフォーマット不一致（YYYY-MM-DD vs YYYY/MM/DD）
- **Fix**: quarterly_backtest_2024_2025.py による再生成（28ファイル正常生成確認）

#### Level 2: コンフィグ反映
- **Status**: ✅ 正常確認
- **Verification**:
  ```
  baseline_old stop_range: 2.0  ✅
  baseline_new stop_range: 4.0  ✅
  ```
- **Mechanism**: Config.get_stop_range() → _initialize_cache() → config.ini 読み込み

#### Level 3: **バックテスト実行 (CRITICAL)**
- **Status**: ❌ 実行不成功
- **Root Cause**: `.api_key` ファイルが存在しない
- **Impact**: Bybit API からの過去データ取得失敗 → バックテスト実行なし → キャッシュレポート返却

## 必須セットアップ

### 1. API キー設定ファイルの作成

`.api_key` ファイルを以下の形式で作成（プロジェクトルート）:

```
your_actual_api_key_here
your_actual_api_secret_here
```

**例**:
```
y29tAbaV...abcdefg...
xYz123...secret...
```

### 2. API キーの入手方法

1. Bybit アカウントにログイン
2. 設定 → API 管理
3. 新しい API キーを生成
4. API キーと API シークレットをコピー

### 3. セキュリティ上の注意

- `.api_key` ファイルを Git にコミットしないこと（`.gitignore` に追加済み）
- API キーは環境変数 or 安全なストレージに保管すること
- 本番環境では定期的にキーをローテーションすること

## バックテストの実行フロー

```
1. .api_key ファイルから API キーを読み込み
   ↓
2. Config.set_config_file() で期間・パターン別コンフィグをロード
   ↓
3. BybitExchange.get_historical_data() で指定期間の過去データを取得
   ↓
4. Price キャッシュに保存
   ↓
5. Bot.run() でシミュレーション実行
   ↓
6. report/backtest_summary_*.json に結果を保存
```

## 診断コマンド

### API キーの存在確認
```bash
ls -la /home/satoshi/work/satosystem/.api_key
```

### API キー読み込みの検証
```python
from src.backtest import load_api_keys
api_key, api_secret = load_api_keys()
print(f"API Key: {api_key}")  # None の場合は .api_key ファイルがない
```

### コンフィグの動作確認
```python
from src.config import Config

Config.set_config_file('output_configs/quarterly_2024_Q1_baseline_old.ini')
Config.reload_config()
print(f"Stop Range: {Config.get_stop_range()}")  # Should be 2.0
```

## 代替案: モック/ダミーデータでのバックテスト

API キーなしでバックテストを実行する場合（開発環境など）:

1. **モックデータ生成**:
```python
# 仮の価格データを生成
import json
from datetime import datetime, timedelta

mock_data = {
    "timestamp": int(datetime.now().timestamp()),
    "open": 40000,
    "high": 41000,
    "low": 39500,
    "close": 40500,
    "volume": 100
}
```

2. **PriceDataManagement をモック化**:
```python
class MockPriceDataManagement:
    def get_price(self):
        return 40500  # 固定価格
    def get_volatility(self):
        return 500  # 固定ボラティリティ
```

## 期待される改善効果

### stop_range = 2.0 vs 4.0

| Scenario | Effect |
|----------|--------|
| 高ボラティリティ環境 | stop_range 増加 → ストップロス幅拡大 |
| 低ボラティリティ環境 | stop_range 増加 → ポジションサイズ縮小（リスク固定） |
| 総リスク管理 | max_loss_per_trade = balance × risk% を維持 |

### Phase 1 (マーケットレジーム検出)

| Regime | Action |
|--------|--------|
| Strong Trend | ポジション追加/継続 |
| Sideways/Weak | ポジション縮小/回避 |
| Regime Change | トレンド転換に対応 |

## トラブルシューティング

### Q: バックテストが実行されない
**A**: `.api_key` ファイルを確認してください
```bash
test -f .api_key && echo "OK" || echo "Missing .api_key"
```

### Q: 古い結果が返される
**A**: report/*.json をクリアして再実行
```bash
rm -f report/backtest_summary_*.json
python3 quarterly_backtest_scheduler.py --priority high
```

### Q: API エラーが発生する
**A**: API キーの有効期限と権限を確認してください

## 参考資料

- Bybit API ドキュメント: https://bybit-exchange.github.io/docs
- Config 形式: `src/config.ini` (テンプレート)
- バックテスト実装: `src/backtest.py`
- スケジューラ: `quarterly_backtest_scheduler.py`
