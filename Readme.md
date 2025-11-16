# SatoSystem

暗号資産の自動トレードを「継続的改善ループ」で強化することを目的とした Python ベースのトレードボット/バックテストフレームワークです。単なる売買自動化ではなく、戦略→検証→評価→最適化→再投入の学習サイクルを高速に回すための土台を整備します。

## 目的
- バックテスト指標を定量化し、戦略改善を計画的に進める。
- リスク管理と実行制御 (注文 / ポートフォリオ / ロギング) を分離し保守性を高める。
- 抽象度の高い課題(M系列/C系列)と具体 Issue を接続し段階的に品質を向上。

## アーキテクチャ概要
主要コンポーネント:
- Exchange Adapter (`bybit_exchange.py` 他): 取引所APIラッパ。発注/残高/価格取得。
- Strategy (`trading_strategy.py`, `satostrategy.py`): シグナル生成とバックテストロジック。
- Risk Management (`risk_management.py`): ポジションサイズ/ストップ/資金保全。
- Portfolio (`portfolio.py`): 資産・建玉状態の集約。
- Price Data (`price_data_management.py`): OHLCVキャッシュと更新頻度制御。
- Bot Orchestrator (`bot.py`): ループ制御・戦略呼び出し・注文発行。
- Logging (`logger.py`): 構造化ログ出力 (将来: 分析パイプラインへ)。
- Event (予定, `event.py`): モジュール間の疎結合イベント通知。

データフロー (簡略):
```
PriceData -> Strategy -> Signal -> RiskManagement -> Order -> Exchange -> Portfolio -> Logger
```

## ディレクトリ構成 (抜粋)
```
src/
  bot.py                # メイン実行制御
  trading_strategy.py   # 戦略基底/実装
  satostrategy.py       # 具体戦略例
  risk_management.py    # リスク計算
  portfolio.py          # ポートフォリオ状態
  bybit_exchange.py     # 取引所アダプタ
  price_data_management.py # OHLCV管理
  analysis/             # 解析成果 (module_map, PROJECT_ANALYSIS, 役割文書)
  logs/                 # 実行ログ/データキャッシュ
```

## セットアップ
```bash
git clone https://github.com/do3-1979/satosystem.git
cd satosystem
pip install -r requirements.txt   # 依存ライブラリ
```
設定ファイル: `src/config.ini` を編集し API キーなどを投入。

## 実行方法
バックテスト例:
```bash
python src/backtest.py --config src/config.ini --strategy satostrategy --from 2024-01-01 --to 2024-06-30
```
ライブ運用 (試験運用推奨):
```bash
python src/bot.py --config src/config.ini --strategy satostrategy
```
ログは `src/logs/` 以下に保存。OHLCV キャッシュは再利用されリクエスト頻度を低減。

## 戦略改善ワークフロー (M4)
1. 指標設定: 勝率 / ProfitFactor / 最大ドローダウン / 日次シャープ。
2. データ固定: 期間・ペア・足種を明示し再現性確保。
3. バックテスト実行: 現行 vs 改善案を同条件比較。
4. 統計比較: 改善閾値 (例: シャープ +0.2 & 最大DD -10%) 達成確認。
5. 安全化: スリッページ耐性・異常注文防止・リスク上限再計算。
6. スモールライブ検証→本番昇格。

## バックテスト出力 & メトリクス
バックテスト終了時に `logs/backtest_summary_<timestamp>.json` を生成し以下を記録:
```json
{
  "total_pnl": 123.45,
  "profit_factor": 1.87,
  "max_drawdown": 56.7,
  "max_drawdown_rate": 12.3,
  "sharpe": 0.94,
  "win_rate": 46.2,
  "trades": 26
}
```
メトリクス算出ロジックは `src/metrics.py`。`pnl_history` シリーズから標準的手法で計算。

## 簡易アーキ図
```
      +----------------+
      |    Config      |
      +-------+--------+
        |
      +-------v--------+        +------------------+
   ticker -> | PriceDataMgmt  |<-----> | BybitExchange    |
     OHLCV   +-------+--------+        +------------------+
        | signals
      +-------v--------+    position/size   +------------------+
      | TradingStrategy+------------------->| RiskManagement   |
      +-------+--------+    stop updates    +------------------+
        | decisions                          |
      +-------v--------+                          |
      |      Bot       |<-------------------------+
      +-------+--------+
        | orders
      +-------v--------+
      |   Portfolio    |
      +-------+--------+
        |
    +---v---+
    |Logger |
    +-------+
```

## リスク管理と品質
- 例外方針: 発注 / ネットワーク / 戦略計算を分類し再試行 or 中断を選択。
- ログ: 構造化 (JSON) を分析パイプラインへ後段投入（C9）。
- テスト: `test/` 以下単体テスト（未整備領域は順次追加）。

## ロードマップ (要約)
- M1 差分整合: 分析成果物とコードの継続的同期。
- M2 README刷新: 本ファイルで実施中。
- C1〜C9: アーキ整合 / 命名標準化 / エラー耐性 / 設定キャッシュ / イベント統合 / 性能 / バックテスト強化 / リスク統合 / ログ分析。
- 戦略集合最適化: 複数戦略の相関低減と資本配分動的化 (長期)。

## Issue テンプレ (M3)
```
タイトル: [C<ID>] <要約>
背景: 現状問題/影響
ゴール: 成果指標 (性能/安定性/保守性 等)
範囲: 変更対象/非対象
検証: テスト/メトリクス/ログ確認
リスク: 破壊的変更/移行手順
```

## コントリビューションガイド (簡易)
1. 変更前に該当カテゴリ(Cx)と既存分析参照。
2. 小さな改善は直接PR。構造変更は Issue 事前起票。
3. バックテスト結果を PR に添付 (主要指標数値)。

## 免責
本ソフトは教育・研究目的。実運用は自己責任で行ってください。過去成績は将来を保証しません。

## ライセンス
MIT (必要に応じて `LICENSE` 参照)