# テスト体制ドキュメント

Phase 3 前に構築された包括的なテスト・チェック体制

## 概要

このテストスイートは、コミット・プッシュ前にすべてのロジックが正常に動作していることを確認するための包括的な体制です。

### 4つの主要コンポーネント

1. **ユニットテスト** (`pytest`)
   - 各モジュールの関数の動作確認
   - test_config.py, test_risk_management.py, test_phase3.py

2. **セキュリティチェック**
   - API キー流出の確認
   - .env ファイルの誤ったコミット確認
   - security_check.py

3. **サンプルテスト実行**
   - Config の読み込みテスト
   - モジュールのインポート確認
   - バックテストの実行可能性確認
   - Phase 3 モジュール（環境自動判定、動的学習、リアルタイム監視）の確認
   - sample_test_runner.py

4. **一括実行スクリプト**
   - 上記 1-3 をすべて実行
   - テスト結果をレポート出力
   - run_all_checks.py

---

## 使用方法

### 全テスト・チェックを実行（推奨）

```bash
# リポジトリルートから
python3 test/run_all_checks.py

# または test ディレクトリから
cd test && python3 run_all_checks.py
```

実行結果:
- ✅ すべてのテストに合格 → コミット・プッシュ可能
- ❌ 失敗がある → 問題を修正してから再実行

### 個別実行

#### 1. ユニットテスト実行

```bash
# すべてのテストを実行
pytest test/

# 特定のテストファイルのみ
pytest test/test_config.py -v
pytest test/test_risk_management.py -v
pytest test/test_phase3.py -v

# 特定のテストクラスのみ
pytest test/test_config.py::TestConfigBasics -v

# 特定のテスト関数のみ
pytest test/test_config.py::TestConfigBasics::test_config_initialization -v
```

#### 2. セキュリティチェック実行

```bash
python3 test/security_check.py
```

チェック内容:
- ソースコード内の API キー流出スキャン
- Git ステージングエリアの機密情報確認
- .env ファイルの git コミット確認
- .gitignore の設定確認

#### 3. サンプルテスト実行

```bash
python3 test/sample_test_runner.py
```

テスト内容:
- Config の読み込みテスト
- 主要モジュールのインポート確認
- バックテスト実行可能性確認
- Phase 3 モジュール確認

---

## テストファイル構成

```
test/
├── __pycache__/                    # Python キャッシュ
├── test_data/                      # テスト用データ
├── test_TradingStrategy.py         # 既存テスト
├── test_pos_mng.py                 # 既存テスト
├── test_config.py                  # Config モジュールテスト ✨ NEW
├── test_risk_management.py         # RiskManagement テスト ✨ NEW
├── test_phase3.py                  # Phase 3 モジュールテスト ✨ NEW
├── security_check.py               # セキュリティチェック ✨ NEW
├── sample_test_runner.py           # サンプルテスト実行 ✨ NEW
├── run_all_checks.py               # 一括実行スクリプト ✨ NEW
└── README.md                        # このファイル
```

---

## テスト内容詳細

### test_config.py

#### TestConfigBasics
- Config インスタンス化
- regime_detection_enabled の取得
- graduated_sizing_enabled の取得
- Strategy セクション全体の取得
- RiskManagement セクションの確認
- Config キャッシュ機能

#### TestConfigValidation
- ボラティリティ閾値の妥当性
- トレンド強度閾値の妥当性

#### TestConfigSecurityCheck
- config.ini に API キーが含まれていないか
- config.template.ini に実際の API キーが含まれていないか

### test_risk_management.py

#### TestRiskManagementBasics
- RiskManagement インスタンス化
- 段階的フィルタリング計算テスト
- 各レジームでのポジションサイジング

#### TestRiskManagementValidation
- 段階的フィルタリング乗数の妥当性 (0.75/1.0/1.25)
- ポジションサイズが常に非負

#### TestRiskManagementEdgeCases
- ゼロのベースポジション
- 負のベースポジション

### test_phase3.py

#### TestEnvironmentAutoJudge
- environment_auto_judge.py のインポート確認
- 環境自動判定の出力フォーマット確認

#### TestDynamicThresholdLearning
- dynamic_threshold_learning.py のインポート確認
- 動的学習の出力フォーマット確認

#### TestRealtimePerformanceMonitor
- realtime_performance_monitor.py のインポート確認
- リアルタイム監視の出力フォーマット確認

#### TestPhase3Integration
- work_reports ディレクトリの存在確認
- 生成された JSON ファイルの読可能性確認

### security_check.py

- ソースコード内の API キー流出スキャン
- Git ステージングエリアの機密情報確認
- .env ファイルの誤ったコミット確認
- .gitignore の設定確認

### sample_test_runner.py

- Config の読み込みテスト
- 主要モジュール（config, risk_management, trading_strategy など）のインポート確認
- バックテストスクリプトの実行可能性確認
- Phase 3 モジュール（environment_auto_judge, dynamic_threshold_learning, realtime_performance_monitor）のインポート確認

### run_all_checks.py

上記 1-3 をすべて実行し、総合的なテスト結果をレポート出力

---

## テスト結果レポート

### レポート出力先

```
work_reports/
├── all_checks_report_YYYYMMDD_HHMMSS.json       # 一括実行結果
├── sample_test_report_YYYYMMDD_HHMMSS.json      # サンプルテスト結果
└── ...
```

### レポートフォーマット

```json
{
  "timestamp": "2025-11-25T12:34:56.789012",
  "checks": {
    "test_config.py": "PASS",
    "test_risk_management.py": "PASS",
    "test_phase3.py": "PASS",
    "security_check": "PASS",
    "sample_tests": "PASS"
  },
  "summary": {
    "total": 5,
    "passed": 5,
    "failed": 0
  }
}
```

---

## コミット前チェックリスト

コミット・プッシュ前に必ず実行してください：

- [ ] `python3 test/run_all_checks.py` を実行
- [ ] すべてのテストが ✅ PASS を確認
- [ ] 失敗がある場合は問題を修正して再実行
- [ ] レポートを確認して問題がないことを確認

---

## ロジック変更時の対応

**重要**: 以降、ロジック変更をする場合は、テストも同時に更新してください。

### テスト追加・更新の手順

1. ロジック変更を実装
2. test/*.py で対応するテストを追加・更新
3. `python3 test/run_all_checks.py` で全テスト実行
4. すべてのテストが PASS したことを確認
5. コミット・プッシュ

### テスト更新例

```python
# src/risk_management.py にメソッドを追加した場合
# → test/test_risk_management.py にテストケースを追加

def test_new_method(self):
    """新しいメソッドのテスト"""
    result = risk_manager.new_method(input_value)
    assert result is not None
    # 期待値をアサーション
```

---

## よくある質問

### Q1: pytest がインストールされていない

```bash
pip install pytest
```

### Q2: テストが失敗した場合

1. エラーメッセージを確認
2. テストに関連するロジックを修正
3. `python3 test/run_all_checks.py` で再実行

### Q3: 特定のテストだけをスキップしたい

```bash
pytest test/test_config.py -v -k "not security_check"
```

### Q4: テスト追加方法

1. test/test_モジュール名.py に新しいテストクラス・メソッドを追加
2. `def test_xxx(self):` メソッドを実装
3. `assert` で期待値をチェック
4. `python3 test/run_all_checks.py` で実行確認

---

## 最後に

このテスト体制により、安心してロジック変更ができます。

**コミット前は必ず `python3 test/run_all_checks.py` を実行してください！**

---

**作成**: 2025-11-25  
**バージョン**: 1.0  
**関連ドキュメント**: ../docs/ACTION_LIST.md
