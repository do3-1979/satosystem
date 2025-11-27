# Satosystem - システム総合ガイド

**最終更新**: 2025-11-28 14:30  
**バージョン**: Phase 1 + Phase 2 + Phase 3（**本番有効化完了**）  

---

## 🎯 システムの目的

自動取引ボットで継続的な利益生成を実現。市場レジーム判定 → 段階的フィルタリング → 自動最適化ループで段階的改善。

---

## 📊 現在の状態

### 進捗状況
| フェーズ | 内容 | 状態 | 改善率 |
|---------|------|------|--------|
| **Phase 1** | レジーム検出（SIDEWAYS/WEAK_TREND/STRONG_TREND） | ✅ 完了 | +56.4%（Q2）/ +11.6%（Q1 2024） |
| **Phase 2** | 段階的ポジション調整（0.75x/1.0x/1.25x） | ✅ 完了 | +10.34%（全期間平均） |
| **Phase 3** | 自動監視・学習ループ（Task 7/10/11） | ✅ 完了 | - |

### 運用スケジュール
```
毎日 00:00 UTC   → Task 11 (realtime_performance_monitor.py) - 日次監視
毎週月曜 00:00   → Task 7 (environment_auto_judge.py) - 環境判定
毎月1日 00:00    → Task 10 (dynamic_threshold_learning.py) - 最適化学習
```

### 業績（バックテスト）
- **2024年**: 平均 -$37,559（初期資本 10,000 USD比で300%超過損失）
- **2025年**: 平均 -$10,756（71%削減）
- **Phase 2適用後**: +10.34%改善実績
- **課題**: 根本的な赤字解決に至らず → Task 19で実運用検証中

---

## 🏗️ システムアーキテクチャ

### コンポーネント責務表

| モジュール | 役割 | 連携先 |
|-----------|------|-------|
| **Config** | config.ini パラメータ一元管理・キャッシュ | 全モジュール |
| **BybitExchange** | ccxt ラッパー（OHLCV/注文/残高） | PriceDataManagement, Bot |
| **PriceDataManagement** | OHLCV取得・シグナル計算（Donchian/PVO）・ボラティリティ | TradingStrategy, RiskManagement |
| **OHLCVCache** | SQLite永続化（1m/120m） | PriceDataManagement初期ロード |
| **TradingStrategy** | ENTRY/ADD/EXIT判定 | Bot, Portfolio |
| **RiskManagement** | ポジションサイジング・PSAR/トレーリングストップ | Bot, Portfolio |
| **Portfolio** | ポジション/PnL/ドローダウン追跡 | Bot, RiskManagement |
| **Logger** | 構造化ログ・ローテーション・圧縮 | すべて |
| **Metrics** | PnL/Sharpe/Win Rate/Profit Factor計算 | Bot（サマリー） |

### データフロー

```
Config → PriceDataManagement → TradingStrategy → Bot
         ↓（シグナル）            ↓（ENTRY/EXIT） ↓（ポジション調整）
      RiskManagement ←----------→ Portfolio ← Logger
         ↓（サイジング）              ↓（PnL）    ↓（圧縮）
      Exchange（注文実行）      Metrics（集計）  work_reports
```

### タイムフレーム・キャッシュ
- **戦略用**: 2時間足（120m）- 高レベルシグナル
- **詳細用**: 1分足 - 最新ティッカー・出来高
- **永続化**: SQLite `candles` テーブル（`symbol, timeframe, close_time`キー）

---

## 🎛️ 実行ルール

### Bot 実行方法

**バックテスト** （config.ini で `back_test = 1` 設定）
```bash
python3 run_backtest.py [--full-logging]
```

**本番実行** （config.ini で `back_test = 0` 設定）
```bash
python3 src/bot.py
```

### 設定ファイル体系

```
src/config.ini（ユーザ設定 - 変更可）
    ↑（読み込み）
src/config.template.ini（テンプレート - 自動生成）

[Strategy]
regime_detection_enabled = True
graduated_sizing_enabled = True   ← Phase 2 有効化（本番反映済み）

[Risk]
entry_times = 4                   ← ピラミッディング（最適値）
stop_offset = 1.5                 ← ストップロス距離
```

**セキュリティ**: API キー は `.api_key` ファイルまたは環境変数 `BYBIT_API_KEY`, `BYBIT_API_SECRET` から読み込み（config.ini に含めない）

---

## 🔄 Phase 3 - 自動化ループ

### Task 11: リアルタイムパフォーマンス監視
**実行**: 毎日 00:00 UTC  
**スクリプト**: `src/realtime_performance_monitor.py`  
**監視項目**: 日次PnL / Win Rate / Profit Factor（7日スライディング）  
**アラート**: WR低下 / 連続損失 / Profit Factor低下 / レジーム変化  
**出力**: `work_reports/realtime_monitor_*.json`

### Task 7: 環境自動判定
**実行**: 毎週月曜 00:00 UTC  
**スクリプト**: `src/environment_auto_judge.py`  
**判定**: 過去30日レジーム分布 → SIDEWAYS ≥30% で Phase 2 有効化判定  
**出力**: `work_reports/environment_auto_judgement_*.json`

### Task 10: 動的基準学習
**実行**: 毎月1日 00:00 UTC  
**スクリプト**: `src/dynamic_threshold_learning.py`  
**学習内容**: volatility_ratio / trend_strength 最適値（Percentile P40-P80）  
**出力**: `work_reports/dynamic_threshold_learning_*.json`

### Crontab 設定
```bash
# Task 11
0 0 * * * cd /home/satoshi/work/satosystem && python3 src/realtime_performance_monitor.py >> logs/task11.log 2>&1

# Task 7
0 0 * * 1 cd /home/satoshi/work/satosystem && python3 src/environment_auto_judge.py >> logs/task7.log 2>&1

# Task 10
0 0 1 * * cd /home/satoshi/work/satosystem && python3 src/dynamic_threshold_learning.py >> logs/task10.log 2>&1
```

---

## 📋 Task 進捗

### ✅ 完了（15/15）
| # | タスク | 完了日 | 効果 |
|----|--------|--------|------|
| P0-1 | Win Rate計算修正 | 2025-11-26 | - |
| P0-2 | ストップロス実装 | 2025-11-26 | - |
| P0-3 | ポジション検証 | 2025-11-26 | - |
| Task 7 | 環境自動判定 | 2025-11-24 | - |
| Task 10 | 動的基準学習 | 2025-11-24 | - |
| Task 11 | リアルタイム監視 | 2025-11-24 | - |
| Task 17 | Phase 2本番反映 | 2025-11-26 | +10.34% |
| Task 18 | Cron統合 | 2025-11-26 | - |

### 🔄 進行中
**Task 19**: 4週間ホットテスト運用（2025-11-27 ～ 2025-12-24）
- 目的: Phase 2の実運用効果検証
- 監視: 毎日Task 11自動実行
- 判定予定: 4週間後

---

## 🔍 戦略最適化の履歴

### ✅ ピラミッディング最適化（採用: entry_times=4）
**テスト期間**: 2025/10/01 - 2025/11/01  
**選択根拠**: 
- Max DD 49.75%（50%未満で本番実用的）
- 最高Sharpe比 0.343（リスク調整リターン最適）
- PnL改善 +977%（ベースライン対比）

| entry_times | PnL | DD Rate | Sharpe | Win Rate |
|-------------|-----|---------|--------|----------|
| **4 (採用)** | **107.10** | **49.75%** | **0.343** | **93.33%** |
| 2 | 281.68 | 70.07% | 0.287 | 100% |
| 5 | 69.78 | 44.94% | 0.32 | 93.33% |
| 3 | 45.33 | 64.47% | 0.12 | 93.33% |
| 10 (ベース) | 9.94 | 113.17% | 0.63 | 94.12% |

### ❌ Keltner チャネルフィルタ（却下）
**テスト期間**: 2025/10/01 - 2025/11/01  
**結果**: 12パラメータ組み合わせすべてでベースラインより劣化（-35.21）  
**理由**: Profit Factor 0.70、Max DD 58.18%、実用性なし

---

## 📁 重要ファイル

### スクリプト
- `run_backtest.py` - バックテスト実行
- `src/bot.py` - メインロジック
- `src/environment_auto_judge.py` - Task 7
- `src/dynamic_threshold_learning.py` - Task 10
- `src/realtime_performance_monitor.py` - Task 11

### 設定
- `src/config.ini` - 本番設定（Phase 2適用済み）
- `src/config.template.ini` - テンプレート
- `crontab_entries.txt` - Cron設定

### ドキュメント
- `docs/SYSTEM_GUIDE.md` - このファイル（統合ガイド）
- `docs/TRADING_STRATEGY_PLAN.md` - 戦略詳細・改善案（参考用）
- `docs/_archive/` - 過去の分析データ

### テスト
- `test/run_all_checks.py` - 全テスト実行（config.ini変更なし確認）
- `test/sample_test_runner.py` - モジュール・ビジュアライゼーション検証

---

## 🚀 次のステップ

### 短期（1週間以内）
1. Task 19 監視中 - 日次PnL確認（毎日00:05 UTC）
2. Task 7/10結果レビュー（毎週月曜・毎月1日）

### 中期（1ヶ月以内）
1. Task 19判定（2025-12-24）- 継続/調整/中止判定
2. 必要に応じてパラメータ調整

### 長期（3ヶ月以内）
1. Phase 4: 複数シンボル対応
2. Phase 5: マルチポジション保持・部分利確
3. Phase 6: EXIT条件の洗練化

---

## 🔧 トラブルシューティング

### Cron ジョブが実行されない
```bash
service cron status              # Cronデーモン確認
crontab -l                       # 登録確認
cat /var/log/syslog | grep CRON # Cronログ確認
```

### Python スクリプトエラー
```bash
# 直接実行テスト
cd /home/satoshi/work/satosystem
python3 src/environment_auto_judge.py

# モジュール確認
python3 -c "import src.environment_auto_judge"
```

### Config キャッシュ問題
```python
# src/config.py で強制リロード
Config.reload_config()
```

---

## 📞 参照マップ

| 質問 | 参照箇所 |
|------|---------|
| システム全体の構造は？ | このファイルの「システムアーキテクチャ」 |
| Phase 2 の詳細な改善案は？ | TRADING_STRATEGY_PLAN.md（参考用） |
| 戦略の過去テスト結果は？ | docs/_archive/COMPREHENSIVE_VALIDATION_REPORT.md |
| Cron 設定の詳細は？ | このファイルの「Phase 3 - 自動化ループ」 |
| テスト実行方法は？ | test/README.md または このファイルの「実行ルール」 |
| バックテスト詳細解析は？ | docs/_archive/ 参照 |

---

**このドキュメントはプロジェクトの単一の真実（SSOT）です。定期的に確認してください。**

最終更新: 2025-11-28
