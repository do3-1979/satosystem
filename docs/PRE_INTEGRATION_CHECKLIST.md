# 織り込み前アクション（Pre-Integration Checklist）

**最終更新**: 2026-01-05  
**目的**: コードをmainブランチに織り込む前に、全ての機能が正常動作することを確認する

---

## 📋 実行手順

### 1. 全Qテスト（四半期別バックテスト）

```bash
cd /home/satoshi/work/satosystem
python3 run_quarterly_backtest.py
```

**期待される結果**:
- ✅ 8四半期（Q1 2024 ～ Q4 2025）すべてでバックテスト完了
- ✅ `docs/quarterly_backtest_results/quarterly_results_*.json` 生成
- ✅ 各四半期のtrade_log_*.json が `logs/` に保存
- ✅ エラーなく完了（exit code 0）

**確認コマンド**:
```bash
# 最新の結果ファイルを確認
ls -lt docs/quarterly_backtest_results/quarterly_results_*.json | head -1

# 結果サマリを表示
python3 << 'EOF'
import json
import glob
files = sorted(glob.glob('docs/quarterly_backtest_results/quarterly_results_*.json'))
if files:
    with open(files[-1]) as f:
        data = json.load(f)
    print(f"✓ 最新結果: {files[-1]}")
    print(f"  四半期数: {len(data)}")
    for q, stats in data.items():
        print(f"  {q}: PnL={stats['total_pnl']:.2f} USD, Trades={stats['total_trades']}, WR={stats['win_rate']:.1f}%")
EOF
```

**失敗時の対応**:
1. エラーログを確認: `logs/` 配下の最新ファイル
2. config.iniの設定を確認（期間、パラメータ）
3. OHLCVキャッシュの整合性確認: `src/ohlcv_data/ohlcv_cache.db`

---

### 2. レグレッションテスト

```bash
cd /home/satoshi/work/satosystem
python3 test/regression_test_suite.py
```

**期待される結果**:
- ✅ すべてのテストケースがPASS
- ✅ `docs/regression_test_results/` にレポート生成
- ✅ 以下の主要テストが成功:
  - `test_backtest`: バックテスト動作確認
  - `test_class_methods`: 主要クラス・メソッド単体テスト
  - `test_consistency`: 結果整合性チェック
  - `test_trade_logger_integration`: TradeLogger統合テスト（2026-01-05追加）
  - `test_market_regime_detector_ohlcv_keys`: MarketRegimeDetector OHLCV key確認（2026-01-05追加）

**確認コマンド**:
```bash
# レグレッションテスト結果を確認
ls -lt docs/regression_test_results/*.json | head -1
python3 << 'EOF'
import json
import glob
files = sorted(glob.glob('docs/regression_test_results/*.json'))
if files:
    with open(files[-1]) as f:
        results = json.load(f)
    passed = sum(1 for r in results if r['passed'])
    total = len(results)
    print(f"✓ テスト結果: {passed}/{total} passed")
    for r in results:
        status = "✓" if r['passed'] else "✗"
        print(f"  {status} {r['test']}")
EOF
```

**失敗時の対応**:
1. 失敗したテストケースのdetailsを確認
2. 該当ファイルのコード・設定を確認
3. 必要に応じてテストケースを修正またはスキップ

---

### 3. グラフ描画テスト

```bash
cd /home/satoshi/work/satosystem
bash backtest_and_visualize.sh
```

**期待される結果**:
- ✅ バックテスト実行完了
- ✅ `logs/backtest_summary_*.json` 生成
- ✅ `docs/results/backtest_psar_interactive.html` 生成（200KB以上）
- ✅ HTMLファイルがブラウザで正常表示可能

**確認コマンド**:
```bash
# 最新のHTMLファイルを確認
ls -lh docs/results/backtest_psar_interactive.html

# ファイルサイズ確認（200KB以上が正常）
FILE_SIZE=$(stat -c%s "docs/results/backtest_psar_interactive.html" 2>/dev/null || stat -f%z "docs/results/backtest_psar_interactive.html" 2>/dev/null)
if [ $FILE_SIZE -gt 200000 ]; then
    echo "✓ HTMLファイル正常生成（サイズ: $(($FILE_SIZE / 1024))KB）"
else
    echo "✗ HTMLファイルサイズ異常（サイズ: $(($FILE_SIZE / 1024))KB）"
fi
```

**ブラウザで確認**:
```bash
# ローカルで確認する場合
python3 -m http.server 8000 --directory docs/results
# ブラウザで http://localhost:8000/backtest_psar_interactive.html にアクセス
```

**失敗時の対応**:
1. bot.pyの実行ログを確認
2. visualizer.pyのエラーを確認
3. Plotlyライブラリのインストール確認: `pip3 list | grep plotly`

---

## 🔍 追加確認項目

### 4. 分析JSON整合性チェック

```bash
cd /home/satoshi/work/satosystem
python3 << 'EOF'
import os
import json

src_files = set()
for f in os.listdir('src'):
    if f.endswith('.py'):
        src_files.add(f[:-3])

analysis_files = set()
for f in os.listdir('docs/analysis/src'):
    if f.endswith('.json'):
        analysis_files.add(f[:-5])

missing_analysis = src_files - analysis_files
missing_src = analysis_files - src_files

if missing_analysis:
    print(f"⚠️  分析JSONが欠けているソースファイル: {missing_analysis}")
else:
    print("✓ 全てのソースファイルに分析JSONが存在")

if missing_src:
    print(f"⚠️  ソースファイルが欠けている分析JSON: {missing_src}")

# trade_logger.jsonの存在確認
if 'trade_logger' in analysis_files:
    print("✓ trade_logger.json 存在確認")
    with open('docs/analysis/src/trade_logger.json') as f:
        data = json.load(f)
        print(f"  - メソッド数: {len(data.get('methods', []))}")
else:
    print("✗ trade_logger.json が見つかりません")
EOF
```

### 5. 最近の変更の分析JSON反映確認

```bash
python3 << 'EOF'
import json

files_to_check = ['bot.json', 'market_regime_detector.json', 'trading_strategy.json', 'trade_logger.json']

for filename in files_to_check:
    filepath = f'docs/analysis/src/{filename}'
    try:
        with open(filepath) as f:
            data = json.load(f)
        if 'recent_changes' in data:
            print(f"✓ {filename}: recent_changes 存在（{len(data['recent_changes'])} 件）")
            if data['recent_changes']:
                latest = data['recent_changes'][-1]
                print(f"  最新: {latest.get('date', 'N/A')} - {latest.get('description', 'N/A')[:60]}...")
        else:
            print(f"⚠️  {filename}: recent_changes セクションなし")
    except FileNotFoundError:
        print(f"✗ {filename}: ファイルが見つかりません")
    except Exception as e:
        print(f"✗ {filename}: エラー - {e}")
EOF
```

---

## 📊 成功判定基準

すべての以下の条件を満たす場合、織り込みを承認:

### ✅ 必須条件
1. 全Qテスト: エラーなく8四半期すべて完了
2. レグレッションテスト: 全テストケースがPASS
3. グラフ描画テスト: HTMLファイル正常生成（200KB以上）

### ✅ 推奨条件
4. 分析JSON: 全ソースファイルに対応する分析JSONが存在
5. recent_changes: 最近変更された主要ファイルの分析JSONに更新情報が記載

---

## ⚠️ 失敗時のアクション

いずれかのテストが失敗した場合:

1. **即座に停止**: 織り込みを中止
2. **原因調査**: エラーログ・詳細情報を確認
3. **修正**: 問題箇所を修正し、再度全テストを実行
4. **記録**: 失敗の原因と修正内容をコミットメッセージに記載

---

## 🚀 織り込み前の最終確認

```bash
# 全テストを一括実行
cd /home/satoshi/work/satosystem

echo "=== 1. 全Qテスト ==="
python3 run_quarterly_backtest.py && echo "✓ 全Qテスト完了" || echo "✗ 全Qテスト失敗"

echo ""
echo "=== 2. レグレッションテスト ==="
python3 test/regression_test_suite.py && echo "✓ レグレッションテスト完了" || echo "✗ レグレッションテスト失敗"

echo ""
echo "=== 3. グラフ描画テスト ==="
bash backtest_and_visualize.sh && echo "✓ グラフ描画テスト完了" || echo "✗ グラフ描画テスト失敗"

echo ""
echo "=== 4. 分析JSON整合性チェック ==="
python3 << 'EOF'
import os
src_files = {f[:-3] for f in os.listdir('src') if f.endswith('.py')}
analysis_files = {f[:-5] for f in os.listdir('docs/analysis/src') if f.endswith('.json')}
missing = src_files - analysis_files
if missing:
    print(f"✗ 分析JSONが欠けているファイル: {missing}")
else:
    print("✓ 分析JSON整合性確認完了")
EOF

echo ""
echo "=== すべてのテストが✓の場合、織り込み準備完了 ==="
```

---

## 📝 使用例

このドキュメントを使用する場合：

```bash
# このドキュメントを表示
cat docs/PRE_INTEGRATION_CHECKLIST.md

# または、直接実行
bash -c "$(sed -n '/^# 全テストを一括実行/,/^echo.*織り込み準備完了/p' docs/PRE_INTEGRATION_CHECKLIST.md)"
```

---

**作成日**: 2026-01-05  
**関連ドキュメント**:
- [REGRESSION_TEST_POLICY.md](REGRESSION_TEST_POLICY.md)
- [ACTION_LIST.md](ACTION_LIST.md)
- [DEVELOPMENT_RULES.md](DEVELOPMENT_RULES.md)
