# アクションリスト

**最終更新**: 2025-11-25  
**担当**: 開発チーム  
**優先度**: 高(H) / 中(M) / 低(L)  
**ステータス**: Phase 2 & Phase 3 実装完了、本番導入可能

---

## 現在のステータス

### ✅ 完了済み

| # | タイトル | 完了日 | 検証状況 |
|----|---------|--------|---------|
| 1 | Phase 1マーケットレジーム検出基本実装 | 2025-11-21 | ✅ バックテスト検証済み |
| 2 | 2024-2025年全期間バックテスト実施 | 2025-11-24 | ✅ 7期間 × 2パターン = 14テスト完了 |
| 3 | 改善案1/2の検証 | 2025-11-24 | ✅ 両案とも却下（不効果） |
| 4 | 詳細分析レポート作成 | 2025-11-24 | ✅ PHASE1_IMPROVEMENT_ANALYSIS.md |
| 5 | ドキュメント整理・統一 | 2025-11-24 | ✅ 3ドキュメント構成に統一 |
| 9 | **Phase 2: 段階的フィルタリング実装** | 2025-11-24 | ✅ 実装・バックテスト・コミット完了 |
| 7 | **Task 7: 環境自動判定スクリプト** | 2025-11-24 | ✅ 実装・テスト完了 |
| 10 | **Task 10: 動的基準学習システム** | 2025-11-24 | ✅ 実装・テスト完了 |
| 11 | **Task 11: リアルタイムパフォーマンス監視** | 2025-11-24 | ✅ 実装・テスト完了 |
| 6 | Config 整合性確認・修正 | 2025-11-25 | ✅ config.py に Phase 2パラメータ追加、整合性検証済み |
| 16 | ドキュメント更新（Phase 2/3記載） | 2025-11-25 | ✅ ARCHITECTURE_OVERVIEW.md, TRADING_STRATEGY_PLAN.md, ACTION_LIST.md 更新 |

### 🚀 実施中

| # | タイトル | 優先度 | 期限 | 進捗 |
|----|---------|--------|------|------|
| - | **すべての主要タスク完了** | - | - | **✅ 本番導入可能** |

| # | タイトル | 優先度 | 期限 | 進捗 |
|----|---------|--------|------|------|
| 6 | プロジェクト分析シート（analysis/）更新 | H | 本日 | **進行中** |
| 7 | 環境自動判定ロジック設計 | H | 1週間以内 | 待機中 |

### 📋 未実施（推奨優先順）

---

### 📋 次フェーズ（推奨優先順）

#### Phase 3 統合・運用関連

| # | タイトル | 優先度 | 推奨実施期間 | 難易度 | 概要 |
|----|---------|--------|-------------|--------|------|
| 17 | 本番環境への Phase 2 反映 | H | 即時 | L | config.ini で graduated_sizing_enabled = True に変更 |
| 18 | Phase 3 スケジューラ統合 | H | 1週間以内 | M | cron または GitHub Actions で Task 7/10/11 定期実行設定 |
| 19 | 4週間ホットテスト運用 | H | 2025/11/25 - 12/25 | L | 実際のパフォーマンス検証、日次 PnL/WR 追跡 |
| 12 | 環境劣化自動検出アラート（Task 11拡張） | M | 1ヶ月以内 | M | Win Rate低下時の Slack/Email アラート統合 |

---

## 詳細タスク

### ✅ 完了済みタスク

#### Task 9: 段階的フィルタリング実装 ✅

**目的**: Q4初期 -34.9%の悪化を緩和

**実装内容** (2025-11-24完了):
```python
# risk_management.py
if graduated_sizing_enabled:
    multiplier = {
        'SIDEWAYS': 0.75,        # リスク削減
        'WEAK_TREND': 1.0,       # 基準
        'STRONG_TREND': 1.25     # 積極的
    }[current_regime]
    final_position = base_position * multiplier
```

**バックテスト成績**: 
- 総PnL: +$570.48 (+10.34%) 改善
- Q2 2025: +56.43% 改善

**実装期間**: 2025-11-24完了 ✅

---

#### Task 7: 環境自動判定スクリプト ✅

**目的**: Phase 2 の有効/無効を自動判定

**実装内容** (2025-11-24完了):
```python
# src/environment_auto_judge.py
if SIDEWAYS_ratio >= 30%:
    recommend = 'enable_phase2'
else:
    recommend = 'disable_phase2'
```

**出力**: `work_reports/environment_auto_judgement_*.json`

**実装期間**: 2025-11-24完了 ✅

---

#### Task 10: 動的基準学習システム ✅

**目的**: 最適な volatility_ratio と trend_strength 閾値を導出

**実装内容** (2025-11-24完了):
- 過去30日データから percentile 探索（P40-P80）
- Win Rate ベースの効果スコア計算
- 現在値との改善予測

**出力**: `work_reports/dynamic_threshold_learning_*.json`

**実装期間**: 2025-11-24完了 ✅

---

#### Task 11: リアルタイムパフォーマンス監視 ✅

**目的**: パフォーマンス劣化を自動検出、即座に対応

**実装内容** (2025-11-24完了):
- 日次PnL/Win Rate/Profit Factor監視（7日間スライディング）
- アラート検出: WR_DEGRADATION(>10%), CONSECUTIVE_LOSSES(≥5日), LOW_PROFIT_FACTOR(<0.5), REGIME_CHANGE
- JSON 出力: `work_reports/realtime_monitor_*.json`

**実装期間**: 2025-11-24完了 ✅

---

### 🚀 実施予定タスク

#### Task 17: 本番環境への Phase 2 反映 ← **次のステップ**

**目的**: Phase 2 段階的フィルタリングの本番適用

**実施内容**:
```bash
# config.ini を修正
[Strategy]
regime_detection_enabled = True        # Phase 1有効化
graduated_sizing_enabled = True        # Phase 2有効化 ← 変更
```

**期待効果**:
- 短期: +10.34% PnL改善（バックテスト実証値）
- 中期: Phase 3との統合で +5-10% 追加改善

**検証ポイント**:
- [ ] config が正常に読み込まれるか
- [ ] リスク管理が乗数を正確に適用しているか
- [ ] バックテスト結果と本番結果の乖離監視

**所要時間**: 1時間以内（実装は完了、テストのみ）

**優先度**: H | **実施期限**: 即時 | **難易度**: L

---

#### Task 18: Phase 3 スケジューラ統合

**目的**: Task 7/10/11 の定期自動実行設定

**実施内容**:
```bash
# crontab の設定例（または GitHub Actions）

# 毎日 00:00 UTC: リアルタイムモニター
0 0 * * * cd /home/satoshi/work/satosystem && python3 src/realtime_performance_monitor.py >> logs/task11.log 2>&1

# 毎週月曜 00:00 UTC: 環境自動判定
0 0 * * 1 cd /home/satoshi/work/satosystem && python3 src/environment_auto_judge.py >> logs/task7.log 2>&1

# 毎月1日 00:00 UTC: 動的基準学習
0 0 1 * * cd /home/satoshi/work/satosystem && python3 src/dynamic_threshold_learning.py >> logs/task10.log 2>&1
```

**出力ファイル**:
- `work_reports/environment_auto_judgement_*.json` (Task 7)
- `work_reports/dynamic_threshold_learning_*.json` (Task 10)
- `work_reports/realtime_monitor_*.json` (Task 11)

**ダッシュボード**: JSON 出力を Slack/Discord に通知（オプション）

**所要時間**: 2-3時間（cron設定 + テスト）

**優先度**: H | **実施期限**: 1週間以内 | **難易度**: M

---

#### Task 19: 4週間ホットテスト運用

**目的**: Phase 2 の実際のパフォーマンス検証

**期間**: 2025/11/25 - 12/25（4週間）

**監視項目**:
- [ ] 日次 PnL (期待値: 安定性向上)
- [ ] Win Rate (期待値: 26.7% 以上維持)
- [ ] Profit Factor (期待値: 1.5 以上)
- [ ] 取引数（データ収集）
- [ ] 環境変化への適応性

**判定基準**:
- ✅ **継続**: 期待値範囲内でテスト完了
- 🔄 **調整**: パラメータ微調整が必要
- ❌ **中止**: 予期しない悪化があれば即座に無効化

**報告**: 毎週金曜に週次レポート

**所要時間**: 定期監視のみ

**優先度**: H | **実施期限**: 2025/11/25 - 12/25 | **難易度**: L

---

#### Task 12: 環境劣化自動検出アラート（Task 11拡張）

**目的**: Win Rate低下等の環境劣化を Slack/Email で通知

**実施内容** (Task 11基盤上で拡張):
```python
# Slack webhook 統合例
if WR_DEGRADATION > 10%:
    send_slack_alert(f"⚠️ Win Rate低下: {WR_CURRENT}% (前週 {WR_PREV}%)")
    disable_phase2()
```

**所要時間**: 1-2日

**優先度**: M | **実施期限**: 1ヶ月以内 | **難易度**: M

---



#### Task 7: 環境自動判定スクリプト実装

**目的**: Phase 1の有効/無効を自動判定するロジック（Task 9後の依存）

**実施内容**:
```python
# 疑似コード
def should_enable_phase1():
    historical_data = get_last_30_days()
    regime_dist = count_regimes(historical_data)
    sideways_ratio = regime_dist['SIDEWAYS'] / len(regime_dist)
    
    # SIDEWAYS出現度が30%以上なら有効化推奨
    if sideways_ratio > 0.30:
        return True, "Sideways dominant"
    
    # トレンド転換を検出（ボラティリティ上昇傾向）
    vol_trend = linear_trend(historical_data.volatility)
    if vol_trend > 0.05:  # 上昇トレンド
        return True, "Volatility rising"
    
    return False, "Trending stable"
```

**成果物**: `src/regime_analyzer.py` (新規作成)  
**テスト**: 過去3ヶ月でバックテスト検証  
**実装期間**: 1-2週間（Task 9完了後）

---

#### Task 11: リアルタイムパフォーマンス監視

**目的**: 本番運用時の日次PnL監視

**実装内容**:
- [ ] `tools/daily_monitor.py` - 日次集計スクリプト
  - 昨日のPnL, Win Rate, PF
  - 直近7日の移動平均
  - アラート判定（WR<30%など）

- [ ] `tools/weekly_report.py` - 週次レポート
  - 週単位のパフォーマンス
  - 環境判定と推奨パラメータ

**実行**: 毎日朝8:00に自動実行（cronジョブ）

---

### 🎯 優先度M：1ヶ月以内

#### Task 10: 動的基準学習システム

**目的**: 固定基準（Vol>=1.2など）を廃止し、市場適応的に

**技術ロードマップ**:
1. 過去データの統計計算
2. パーセンタイル法による最適値導出
3. 週次更新メカニズム
4. パフォーマンスフィードバック

**実装難易度**: 高（2-3週間）

---

## 本番導入チェックリスト

### 導入前

- [ ] Task 6 完了：分析シート更新
- [ ] Task 9 完了：段階的フィルタリング実装 ← **必須**
- [ ] Task 7 完了：環境自動判定ロジック
- [ ] Task 11 完了：リアルタイム監視体制
- [ ] 過去30日のレジーム分析完了
- [ ] アラート機能テスト完了
- [ ] 本番運用マニュアル作成
- [ ] 本番パラメータ確定

### 導入初期（1週間）

- [ ] 日次PnL監視実施
- [ ] Win Rate確認（30%以上か）
- [ ] アラート動作確認
- [ ] ログ記録確認

### 継続運用（毎週）

- [ ] 週次レポート確認
- [ ] 環境判定の妥当性確認
- [ ] パラメータ調整必要性検討

---

## リスク管理

### ⚠️ 予想される問題と対策

| 問題 | 原因 | 対策 |
|------|------|------|
| Phase 1でWR急低下 | 環境判定ミス | 即座にオフ、アラート |
| ボラティリティ計算エラー | キャッシュ不一致 | 日次キャッシュリセット |
| パラメータ過最適化 | 過去データへの過学習 | 月次更新に限定 |
| レジーム遅延検出 | ボラティリティ平均が遅滞 | 20日平均に短縮検討 |

---

## 参考資料

| ドキュメント | 用途 |
|-------------|------|
| `ARCHITECTURE_OVERVIEW.md` | システムアーキテクチャ全体 |
| `TRADING_STRATEGY_PLAN.md` | 戦略方針・改善案検証 |
| `PHASE1_IMPROVEMENT_ANALYSIS.md` | 詳細技術分析 |
| `analysis/market_analysis.md` | 現在の市場分析（常に最新） |
| `analysis/strategy_performance.md` | パフォーマンス追跡（常に最新） |

---

**最終更新**: 2025-11-25  
**次回レビュー**: 2025-12-08（Task 17/18実施後、ホットテスト中）
