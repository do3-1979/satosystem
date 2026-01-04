# 損失トレード分析ツール - 使用ガイド

## 概要

このツールセットは、ビットコインの取引ログから損失トレードを系統的に分析し、
改善戦略を提案するための完全なパイプラインです。

```
ログファイル
   ↓
[trade_extractor.py] - トレード単位で抽出
   ↓
[trades_with_metadata.csv] - トレード詳細データ
   ↓
[trade_analyzer.py] - パターン検出＆改善案生成
   ↓
[分析レポート＋マトリックス]
```

---

## インストール

### 必要なパッケージ

```bash
pip install pandas numpy scipy scikit-learn
```

---

## 使用方法

### 1. パイプライン全実行（推奨）

```bash
cd /home/satoshi/work/satosystem/tools
./loss_trade_analysis_pipeline.sh
```

このコマンドで、以下が自動的に実行されます：
1. ログからトレードを抽出
2. トレード分析を実行
3. レポート生成

### 2. 個別ステップの実行

#### Step 1: トレード抽出

```bash
python3 /home/satoshi/work/satosystem/tools/trade_extractor.py
```

**出力ファイル:**
- `analysis/trades_with_metadata.csv` - CSV 形式のトレード詳細
- `analysis/trades_with_metadata.json` - JSON 形式のトレード詳細

**CSV の構成例:**

```
trade_id,entry_timestamp,entry_side,entry_price,...,pnl_usd,pnl_pct,market_regime,adx_value,pvo_value
20260104_142850_BUY,2026-01-04 14:28:50,BUY,42850.5,...,-750.25,-1.75,TRENDING_UP,38.2,395.3
...
```

#### Step 2: トレード分析

```bash
python3 /home/satoshi/work/satosystem/tools/trade_analyzer.py
```

**出力ファイル:**
- `analysis/causality_matrix.csv` - 条件別の勝率＆利益マトリックス
- `analysis/loss_trade_analysis_report.html` - インタラクティブレポート

---

## 出力ファイルの解釈

### 1. causality_matrix.csv

条件別の勝率と平均 PnL を表示します。

**例:**

```csv
condition,total_trades,wins,losses,win_rate_pct,avg_pnl_usd,total_pnl_usd
pvo_value: 0 - 50,28,8,20,28.6,-340.25,-9527.0
pvo_value: 50 - 100,45,28,17,62.2,185.50,8347.5
pvo_value: 100 - 500,95,65,30,68.4,520.10,49409.5
adx_value: 0 - 20,35,9,26,25.7,-420.30,-14710.5
adx_value: 20 - 30,53,35,18,66.0,280.15,14847.95
adx_value: 30 - 50,105,58,47,55.2,680.50,71452.5
market_regime: RANGING,53,25,28,47.2,-180.40,-9551.2
market_regime: TRENDING_UP,128,98,30,76.6,520.10,66572.8
market_regime: TRENDING_DOWN,76,45,31,59.2,320.50,24358.0
```

**解釈方法:**

- **PVO: 0-50** → 勝率 28.6%, 平均損失 340 USD
  - 「PVO が低いとき、エントリーすべきではない」という仮説が支持される
  
- **ADX: 0-20** → 勝率 25.7%, 平均損失 420 USD
  - 「ADX が低いトレンドでのエントリーは避けるべき」

- **RANGING** → 勝率 47.2%
  - 「ボックス相場での取引戦略は弱い」

### 2. loss_trade_analysis_report.html

ブラウザで開いて確認します。

```bash
open analysis/loss_trade_analysis_report.html  # macOS
# または
xdg-open analysis/loss_trade_analysis_report.html  # Linux
start analysis/loss_trade_analysis_report.html  # Windows
```

レポートに含まれる情報：
- **検出された損失パターン** - パターン ID、説明、影響度スコア
- **改善仮説** - 推奨されるロジック変更
- **統計情報** - 総トレード数、勝率、利益

---

## 分析例

### ケース 1: PVO フィルタが効いていない

**症状:**
```
condition: pvo_value: 0 - 50
win_rate_pct: 28.6%
total_pnl_usd: -9527.0
```

**結論:** PVO が 50 未満のとき、負けトレードが多い

**改善案:**
```python
# src/config.py で PVO 閾値を変更
Config.pvo_threshold = 100  # 10 → 100
```

**検証:**
- バックテスト期間: 2024 年全体
- 期待される損失削減: 約 2,500 USD
- リスク: 取引機会 30% 削減

### ケース 2: RANGING での勝率が低い

**症状:**
```
condition: market_regime: RANGING
win_rate_pct: 47.2%
```

**結論:** ボックス相場でのエントリーロジックが弱い

**改善案:**

```python
# src/trading_strategy.py で条件追加
if market_regime == 'RANGING':
    return None  # エントリー禁止
```

**検証:**
- RANGING 時の取引を除いた場合の勝率向上
- ホットテストで実際に改善されるか確認

---

## ワークフロー

### 1 週間のサイクル

```
【月曜日】
  └─ ./loss_trade_analysis_pipeline.sh
  └─ HTML レポート確認
  └─ 改善案のリストアップ

【火～水曜日】
  └─ バックテストで改善案を検証
  └─ A/B テストで統計的有意性確認
  └─ リスク評価

【木～金曜日】
  └─ 承認された改善案をコード実装
  └─ ホットテスト実施（1-2 日間）
  └─ 結果確認

【土～日曜日】
  └─ 新しい損失パターンがないか監視
  └─ 微調整が必要か判断
```

---

## トラブルシューティング

### Q: "AttributeError: 'NoneType' object has no attribute 'get'"

**原因:** ログ形式が変わったか、トレードメタデータが不完全

**対策:**
1. ログファイルのフォーマット確認
2. `trade_extractor.py` の `parse_log_line()` を更新
3. テストログで動作確認

### Q: "no data" (トレードが 0 件抽出される)

**原因:** ログにエントリー/イグジット情報がない

**対策:**
1. ログファイルのパスを確認
2. `[条件一覧]`, `[フィルタ一覧]`, `[最終判定]` が含まれているか確認
3. ログ出力ロジックを確認

### Q: レポートが開けない

**原因:** HTML ファイルのパス問題

**対策:**
```bash
# ファイルの確認
ls -la /home/satoshi/work/satosystem/analysis/loss_trade_analysis_report.html

# ブラウザで直接開く
python3 -m http.server 8000
# http://localhost:8000/analysis/loss_trade_analysis_report.html にアクセス
```

---

## 次のステップ

1. **最初の実行**
   - パイプラインを実行してレポート確認
   - 損失パターンが何か特定

2. **改善案の実装**
   - Top 3 の改善案を選定
   - バックテストで検証
   - コード実装

3. **ホットテスト**
   - 実装した改善案を 1-2 週間走らせる
   - 実績がバックテスト予測に近いか確認

4. **継続改善**
   - 月次でパイプラインを再実行
   - 新しい損失パターンを検出
   - 改善の効果を測定

---

## 参考資料

- [docs/LOSS_TRADE_ANALYSIS_PLAN.md](./LOSS_TRADE_ANALYSIS_PLAN.md) - 詳細な分析方法論
- [docs/LOG_IMPROVEMENT_20260104.md](./LOG_IMPROVEMENT_20260104.md) - ログ出力改善について

---

## サポート

質問や問題がある場合は、以下をご確認ください：

1. ログファイルが正しい形式か
2. Python 環境が正しく構成されているか
3. 必要なパッケージがインストールされているか

---

**最終更新:** 2026-01-04
