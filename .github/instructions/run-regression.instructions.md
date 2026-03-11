---
description: レグレッションテストを実行し、結果を確認するスキル。「テスト実行」「回帰テスト」「コミット前確認」を依頼されたときに使用する。
applyTo: "**"
---

# レグレッションテスト実行スキル

## 目的

ソースコード変更後のコミット前に、レグレッションテストを実行して全テストPASSを確認する。

## 必須基準

| 指標 | 合格基準 |
|---|---|
| レグレッションテスト合格率 | ≥ 95%（現在の目標: 122/122 = 100%） |
| ベースライン累積損益 | +2402.94 USD 以上 |
| コミット可否 | 全テスト成功後のみ許可 |

## 手順

### 通常モード（コミット前確認・高速）

```bash
cd /home/satoshi/work/satosystem
./commands/prj-run-regression
```

内容：
- `test/regression_test_suite.py` を実行
- 約30〜60秒で完了

### フルモード（四半期バックテスト込み・機能変更後）

```bash
cd /home/satoshi/work/satosystem
./commands/prj-run-regression --full
```

内容：
- `run_quarterly_backtest.py`（8四半期バックテスト）
- `test/regression_test_suite.py`
- `backtest_and_visualize.sh`（グラフ生成）
- 10〜20分程度かかる

### 新機能追加後：テスト網羅確認

```bash
cd /home/satoshi/work/satosystem
./commands/prj-test-update
```

内容：
- `src/*.py` と `test/test_*_regression.py` の対応を確認
- テスト未作成のモジュールを表示
- `test/regression_test_suite.py` を実行

## 判定フロー

### ✅ テスト成功時

```
✅ regression_test_suite.py - 全テスト合格
🎉 コミット可能な状態です
```

→ ユーザーにコミット許可を求める（コミット・プッシュはユーザー承認後のみ実行）

### ❌ テスト失敗時

1. エラーメッセージの内容を確認
2. 失敗テスト名・原因を特定
3. ソースコードまたはテストコードを修正
4. 再度 `./commands/prj-run-regression` を実行
5. 全テストPASS後にユーザーへ報告

## テストファイル構成

```
test/
├── regression_test_suite.py   # メインスイート（全テストを束ねる）
├── test_*_regression.py       # 各モジュールのテスト
└── ...
```

テストの登録は `regression_test_suite.py` を参照する。新しいモジュールを追加した場合は `test/test_<module>_regression.py` を作成し、`regression_test_suite.py` に追加する。

## テスト追加・修正時の規則

- 新機能実装時は必ずテストを追加する
- テストファイルの命名: `test_<モジュール名>_regression.py`
- モックを使用して外部API依存を排除する
- バックテストのベースラインが大きく変わる修正は `baseline_backup/` に記録する
