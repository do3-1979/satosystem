## bot_run.sh と replace_api_key.sh の機能分析

### bot_run.sh が提供する機能

```
1. ログファイルの事前削除
   - logs/*.json を削除
   - logs/*.zip を削除
   - log.txt を削除
   - err.log を削除
   → 過去の実行結果との混在防止

2. APIキーの管理
   - 実行前: replace_api_key.sh で .api_key → config.ini へ置換
   - 実行後: replace_api_key.sh restore で プレースホルダーに復元
   → APIキーが config.ini に永続的に残らない

3. 実行モード
   - run: 通常実行（前処理 → bot.py → 後処理）
   - bg: バックグラウンド実行（err.log へリダイレクト）
   - clear: ログ削除のみ

4. 実行後のレポート表示
   - 最新の backtest_summary_*.json を表示
   - 最新の trend_trades_*.json を表示
   - 最新の pnl_timeseries_*.json を表示
   - trend_trades が生成されていないと警告

5. 実行時間の計測
   - 開始時刻と終了時刻から経過時間を計算
   - H:M:S フォーマットで表示
```

### replace_api_key.sh が提供する機能

```
1. APIキーの注入
   - .api_key ファイルから読み込み
   - config.ini の YOUR_API_KEY と YOUR_API_SECRET を置換

2. APIキーの復元
   - config.ini を YOUR_API_KEY / YOUR_API_SECRET に戻す
   - restore オプションで実行
```

---

## 新しい config_manager.py での実装状況

### ✅ カバーされている機能

```
1. APIキー管理
   ✅ ConfigManager.prepare_for_backtest()
      - .api_key から読み込み
      - config_temp.ini に注入
      → replace_api_key.sh と同等以上

   ✅ ConfigManager.cleanup_temp_configs()
      - config_temp.ini を削除
      - config.ini をテンプレートに戻す
      → replace_api_key.sh restore と同等

2. ログファイル削除
   ❌ 実装されていない
      → bot_run.sh の事前削除機能がない
      → 手動で追加が必要
```

### ❌ カバーされていない機能

```
1. ログファイルの事前削除
   - logs/*.json, logs/*.zip, log.txt, err.log の削除
   - これは backtest.py には実装されていない
   - 手動で bot.py 実行前に削除する必要あり

2. バックグラウンド実行（bg モード）
   - backtest.py に組み込むことは不可能（シェル層の機能）
   - ユーザーが必要なら手動で & を使用

3. 実行後のレポート表示
   - backtest.py で実行されるが詳細表示はない
   - report ファイルの自動表示機能がない

4. 実行時間の計測
   - backtest.py で各バックテストの時間は計測
   - 総実行時間は表示されているが簡潔
```

---

## 推奨方針: bot_run.sh, replace_api_key.sh を削除可能か？

### 結論: **条件付きで削除可能**

#### 削除できる理由

```
1. APIキー管理
   ✅ config_manager.py で完全に代替
   ✅ bot_run.sh → backtest.py で自動化
   ✅ replace_api_key.sh → ConfigManager.prepare_for_backtest() で自動化

2. 本番運用
   ✅ bot.py 本番実行の場合
      - APIキーは .api_key から直接読み込み（bybit_exchange.py）
      - config.ini に記録されない設計に変更済み
```

#### 削除する前に必要な対応

```
1. ❌ ログファイル事前削除機能が不足
   → backtest.py に追加する必要あり

2. ❌ 実行後のレポート表示が簡潔
   → backtest.py で詳細表示に改善

3. ⚠️  バックグラウンド実行（bg モード）の代替
   → シェルレベルで対応（& を使用）
   → または専用スクリプトを用意
```

---

## 実装計画

### Phase 1: backtest.py に機能を統合

```python
def main():
    # 0. ログファイルの事前削除 ← 新規追加
    cleanup_old_logs()
    
    # 1. ConfigManager初期化
    ConfigManager.init_config_files(".")
    
    # 2. APIキーをロード
    api_key, api_secret = load_api_keys()
    
    # ... バックテスト実行 ...
    
    # 3. 実行後のレポート表示 ← 改善
    display_latest_reports()
    
    # 4. クリーンアップ
    ConfigManager.cleanup_temp_configs(".")
```

### Phase 2: bot.py に機能を統合（本番用）

```python
def main():
    # ロギング前処理（古いログ削除）
    cleanup_old_logs()
    
    # 本番実行
    run_trading()
    
    # ログ後処理
    display_summary()
```

### Phase 3: 代替スクリプト（バックグラウンド実行用）

```bash
#!/bin/bash
# bot_bg.sh - バックグラウンド実行用シンプルスクリプト

cd "$(dirname "$0")"
python bot.py &> err.log &
PID=$!
echo "Background PID=$PID (err.log を監視)"
```

---

## bot_run.sh と replace_api_key.sh を削除するステップ

### Step 1: backtest.py に機能を組み込む

```
✓ ログファイル事前削除関数を追加
✓ 実行後のレポート表示を改善
✓ これで bot_run.sh の大部分を代替
```

### Step 2: bot.py に本番機能を整備

```
✓ logging 前処理（古いログ削除）
✓ .api_key から直接 APIキー読み込み
✓ config.ini に APIキーを記録しない設計確認
```

### Step 3: シェルスクリプト整理

```
✗ bot_run.sh を削除
✗ replace_api_key.sh を削除
✓ 必要に応じて bot_bg.sh (バックグラウンド用) を新規作成
```

---

## 確認項目

### backtest.py の改善内容

```python
def cleanup_old_logs(log_dirs=["logs"], files=["log.txt", "err.log"]):
    """古いログとレポートを削除"""
    # logs/*.json, logs/*.zip を削除
    # log.txt, err.log を削除
    # → 混在防止

def display_latest_reports():
    """実行後のレポートを詳細表示"""
    # backtest_summary_*.json
    # trend_trades_*.json
    # pnl_timeseries_*.json
    # 各々の最新ファイルを表示
```

### bot.py の改善内容

```python
def load_api_keys_from_file(file_path=".api_key"):
    """
    .api_key から直接読み込み
    config.ini に記録しない
    """
    pass

def cleanup_logs_before_run():
    """取引開始前のログ削除"""
    pass
```

---

## 削除対象の詳細

### bot_run.sh の役割

```
✅ ログファイル削除 → backtest.py に移す
✅ APIキー注入 → ConfigManager に移す
✅ bot.py 実行 → backtest.py 実行に置き換え
✅ APIキー復元 → ConfigManager に移す
✅ レポート表示 → backtest.py に移す
✅ 実行時間計測 → backtest.py に移す

❌ バックグラウンド実行（bg モード）
   → シェルの & で対応、または別スクリプト
```

### replace_api_key.sh の役割

```
✅ APIキー注入 → ConfigManager.prepare_for_backtest()
✅ APIキー復元 → ConfigManager.cleanup_temp_configs()

→ 完全に代替可能
```

---

## 推奨実行順序

1. **backtest.py の改善**
   - cleanup_old_logs() 関数を追加
   - display_latest_reports() 関数を追加
   - ConfigManager との統合確認

2. **bot.py の改善**
   - .api_key 直接読み込み確認
   - config.ini に APIキーを記録しない設計確認
   - ログ削除機能の追加

3. **動作テスト**
   - backtest.py だけで全機能が動作するか確認
   - bot.py だけで本番実行が可能か確認

4. **スクリプト削除**
   - bot_run.sh を削除
   - replace_api_key.sh を削除
   - 必要に応じて bot_bg.sh を新規作成

