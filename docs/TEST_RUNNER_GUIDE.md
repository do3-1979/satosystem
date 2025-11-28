# テストランナー統合ガイド

**最終更新**: 2025-11-28  
**バージョン**: 統合テストランナー v1.0

---

## 概要

`verify_all.py` は、複数のテスト・チェック機能を統合した単一コマンドテストランナーです。

**旧構成** (廃止):
- `run_all_checks.py` - pytest + security + サンプル
- `sample_test_runner.py` - モジュール + バックテスト

**新構成** (統合):
- `verify_all.py` - すべての機能を単一ツールで実行 ✅

---

## 実行方法

### シンプル実行
```bash
cd /home/satoshi/work/satosystem
python3 test/verify_all.py
```

### または test ディレクトリから
```bash
cd /home/satoshi/work/satosystem/test
./verify_all.py
```

---

## 実行内容

### 1️⃣ **ユニットテスト (pytest)**
```
test_config.py           - 設定ファイル検証
test_risk_management.py  - リスク管理モジュール
test_phase3.py          - Phase 3 自動化機能
```
**所要時間**: 5-10秒

### 2️⃣ **セキュリティチェック**
```
API キー流出確認
環境変数ファイル検査
.gitignore 推奨事項
```
**所要時間**: 1-2秒

### 3️⃣ **サンプルテスト**
```
📋 Config 読み込み       - 設定値検証（読み取り専用）
📦 モジュールインポート  - 7つのメインモジュール確認
🔬 バックテスト          - 実行可能性確認
🤖 Phase 3モジュール     - 自動化3モジュール確認
📊 可視化ファイル        - グラフ生成確認
📝 ログファイル         - ログ圧縮確認
✔️  データ整合性         - ディレクトリ構造確認
```
**所要時間**: 2-3秒

### 4️⃣ **ファイル整合性チェック**
```
config.ini の変更検知（MD5ハッシュ）
テスト実行前後で変更がないことを確認
```
**所要時間**: 1秒以下

---

## 実行結果

### ✅ 成功時
```
✅ すべてのテスト・チェックに合格しました！
✅ プロジェクトファイル（config.ini）の整合性も確認されました。
🚀 コミット・プッシュの準備ができています。

Exit Code: 0
```

### ❌ 失敗時
```
❌ N 個のテスト・チェックが失敗しました。
🔧 問題を修正してから再度実行してください。

Exit Code: 1
```

---

## 出力ファイル

各実行時にレポートを JSON 形式で保存：

```
work_reports/
  └── 2025-11-28/
      └── verify_all_report_20251128_091310.json
```

---

## 使用シーン

### 🔧 開発中の定期確認
```bash
# コード修正後に実行して不具合確認
python3 test/verify_all.py
```

### 💾 コミット前チェック
```bash
# すべての整合性を確認後にコミット
python3 test/verify_all.py && git add -A && git commit -m "..."
```

### 🔄 CI/CD パイプライン
```bash
# 自動テスト用スクリプト内で呼び出し
python3 test/verify_all.py
exit $?
```

### 📊 プロジェクト状態確認
```bash
# 現在のシステム状態を診断
python3 test/verify_all.py
```

---

## 仕様

### テスト項目数
- **合計**: 6つのテストスイート
- **詳細テスト**: 30+ 個のチェック項目

### 実行時間
- **通常実行**: 15-30秒
- **pytest タイムアウト**: 120秒
- **セキュリティチェック**: 30秒
- **サンプルテスト**: 60秒

### 安全性
- ✅ 読み取り専用テスト（ファイル変更なし）
- ✅ config.ini 変更検知（MD5ハッシュ）
- ✅ テスト終了時に整合性確認

---

## トラブルシューティング

### タイムアウトエラー
```
⏱️ test_XXX.py: TIMEOUT
```
**原因**: テスト実行に120秒以上かかった  
**対処**: タイムアウト値を増加 (verify_all.py の `timeout=120` を変更)

### モジュール import エラー
```
❌ module_name: ImportError
```
**原因**: sys.path に src が含まれていない  
**対処**: `cd test && ../test/verify_all.py` で実行

### config.ini 変更検知
```
❌ config.ini: テスト実行中に変更されました
```
**原因**: テスト実行中にテストスクリプトが config.ini を修正  
**対処**: 修正するテストを特定し、読み取り専用に変更

---

## 旧テストランナー

### 廃止スクリプト
- ❌ `run_all_checks.py`
- ❌ `sample_test_runner.py`

### 移行手順
既存スクリプトから移行する場合は、以下のように置き換え：

```bash
# 旧方式
python3 test/run_all_checks.py
python3 test/sample_test_runner.py

# 新方式（統合）
python3 test/verify_all.py
```

---

## 参考資料

- `ARCHITECTURE_OVERVIEW.md` - システムアーキテクチャ
- `TRADING_STRATEGY_PLAN.md` - 取引戦略詳細
- `src/config.ini` - システム設定
- `docs/` - 各種ドキュメント

---

**状態**: ✅ 本番運用可能  
**テスト成功率**: 100%
