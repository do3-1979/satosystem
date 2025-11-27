# docs フォルダ ガイド

**最終更新**: 2025-11-28  
**このフォルダについて**: satosystemの公式ドキュメント一元管理

---

## 📖 まず読むべきドキュメント

### **🌟 SYSTEM_GUIDE.md（統合ガイド - これを読んでください）**

システム全体を理解するための単一統合ドキュメント。以下をカバー:
- システムの目的と現在の状態（進捗/スケジュール/業績）
- アーキテクチャ全体（責務表・データフロー）
- 実行方法（バックテスト・本番）
- Phase 3自動化ループの詳細（Task 7/10/11）
- 完了タスク一覧と進行中タスク

**必要時間**: 15-20分  
**対象**: すべてのステークホルダー

---

## 📚 参考ドキュメント（詳細情報）

### TRADING_STRATEGY_PLAN.md
**参照用**: Phase 1マーケットレジーム検出の詳細分析、改善案の検証結果  
**対象**: 戦略改善に関心がある場合

### ACTION_LIST.md
**参照用**: 完了タスクと現在進行中のTask 19詳細  
**対象**: プロジェクト進捗をより詳しく知りたい場合

---

## 📊 分析データ（随時更新）

### `analysis/` フォルダ

本番導入後、以下ファイルを常に最新化してください。

#### `market_analysis.md`
- 直近30日のレジーム分布（SIDEWAYS%, WEAK_TREND%, STRONG_TREND%）
- ボラティリティ統計（平均、標準偏差）
- トレンド強度統計
- Phase 1適用可否判定

**更新頻度**: 週1回（毎日曜朝）

---

#### `strategy_performance.md`
- 直近30日の日次PnL推移
- Win Rate 推移
- Profit Factor推移
- 環境別効果測定（Phase 1 ON/OFF比較）

**更新頻度**: 毎日（朝8:00）

---

#### `deployment_readiness.md`
- Phase 1導入準備状況
- チェックリスト進捗
- リスク評価
- 推奨次のステップ

**更新頻度**: 必要に応じて（通常は月1回）

---

## 🗂️ アーカイブ（参考用）

### `_archive/` フォルダ

過去の分析ドキュメント（参考資料として保持）

**含まれるファイル**:
- COMPREHENSIVE_VALIDATION_REPORT.md
- PHASE1_EXTENDED_PERIOD_ANALYSIS.md
- PVO_OPT_PLAN.md
- その他12ファイル

**用途**: 過去のバックテスト結果、実装履歴の参照

---

## 💡 ドキュメント読み方ガイド

### シナリオ1: 新しく参加したメンバーの場合
1. **ARCHITECTURE_OVERVIEW.md** で全体像を理解
2. **TRADING_STRATEGY_PLAN.md** で現在の戦略を理解
3. **ACTION_LIST.md** で今後の方針を理解

**必要時間**: 1-2時間

---

### シナリオ2: 本番運用が始まった場合
1. **strategy_performance.md** で日次パフォーマンス確認
2. **market_analysis.md** で環境判定確認
3. 問題検出時 → **ACTION_LIST.md** のトラブルシューティング確認

**実施頻度**: 毎日

---

### シナリオ3: 改善提案が出た場合
1. **TRADING_STRATEGY_PLAN.md** で過去の改善案を確認
2. `_archive/PHASE1_IMPROVEMENT_ANALYSIS.md` で詳細技術情報
3. **ACTION_LIST.md** でタスク追加

**必要時間**: 30分-1時間

---

### シナリオ4: パフォーマンス低下時
1. **strategy_performance.md** で異常値確認
2. **market_analysis.md** で環境判定確認
3. **TRADING_STRATEGY_PLAN.md** で対応方針確認
4. **ACTION_LIST.md** で緊急対応をチェック

**必要時間**: 15分

---

## 📋 チェックリスト

### ドキュメント整合性チェック（月1回）

- [ ] 3つのコアドキュメントは日本語統一か？
- [ ] analysis/ファイルは最新か？（更新日確認）
- [ ] ACTION_LIST.mdの完了タスクは既に終わっているか？
- [ ] 古いドキュメント参照はないか？（→ _archive/へ移動）
- [ ] リンク切れがないか？

---

## 🔄 ドキュメント更新ルール

### 日次（毎朝8:00）
```bash
# 自動スクリプト実行
python tools/daily_monitor.py > analysis/strategy_performance.md
```

### 週次（毎日曜朝）
```bash
# 自動スクリプト実行
python tools/weekly_report.py > analysis/market_analysis.md
```

### 月次（毎月1日）
- `TRADING_STRATEGY_PLAN.md` で重要な変更があれば更新
- `ACTION_LIST.md` で実行中→完了のタスク移動

### 年次（毎年1月1日）
- バックテスト実行
- パラメータ見直し
- ドキュメント大規模更新の検討

---

## 📞 質問が出た時

| 質問 | 参照するドキュメント |
|------|------------------|
| システムはどう動いているの？ | ARCHITECTURE_OVERVIEW.md |
| なぜPhase 1は効く時と効かない時がある？ | TRADING_STRATEGY_PLAN.md の「重要な発見」セクション |
| 次に何をすべき？ | ACTION_LIST.md の「未実施」セクション |
| 昨日のPnLは？ | analysis/strategy_performance.md |
| 今の市場環境は？ | analysis/market_analysis.md |
| 過去のバックテスト詳細は？ | _archive/PHASE1_IMPROVEMENT_ANALYSIS.md |

---

## 版管理

| 版 | 更新日 | 変更内容 |
|----|--------|---------|
| v1.0 | 2025-11-24 | 初版作成（3ドキュメント構成開始） |

**最終更新**: 2025-11-24

---

**このドキュメントを印刷またはブックマークに追加することをお勧めします。**
