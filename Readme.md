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

### 重要ルール: bot_run.sh の使用必須
**すべてのバックテスト/ライブ実行は `src/bot_run.sh` を経由すること。**

理由:
- APIキーの自動注入/復元 (`replace_api_key.sh` による安全管理)
- ログファイルの自動クリーンアップ
- config.iniへのAPIキー残留防止 (コミット事故防止)

**直接 `python bot.py` を実行することは禁止** (デバッグ時を除く)。

### 実行例
バックテスト (推奨):
```bash
cd src
./bot_run.sh
```

バックグラウンド実行 (ライブ運用):
```bash
cd src
./bot_run.sh bg
```

ログクリーンアップのみ:
```bash
cd src
./bot_run.sh clear
```

### 自動化スクリプトの注意事項
A/B実験や月次バックテストなどの自動化ツールは、必ず `bot_run.sh` を `subprocess` で呼び出すこと:
```python
# Good: bot_run.sh を使用
subprocess.run(['bash', 'bot_run.sh'], cwd=src_dir, ...)

# Bad: bot.py を直接実行 (APIキー管理が不統一になる)
subprocess.run(['python', 'bot.py'], ...)  # NG
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
バックテスト終了時に以下の出力を自動生成します:

### レポートファイル (report/)
- `backtest_report_<timestamp>.md`: 実行サマリー (テキスト形式)
- `backtest_summary_<timestamp>.json`: メトリクス詳細 (JSON)
- `pnl_timeseries_<timestamp>.csv/json`: 全取引の PnL 時系列データ
- `backtest_visualization_<timestamp>.html`: インタラクティブなチャート可視化

### ログファイル (logs/)
- `<timestamp>.zip`: バックテスト実行ログ (JSON形式、自動圧縮)
- `combined_logs_<timestamp>.xlsx`: 集計Excel (5シート: Param/Data/Chart/PandL/PnL_Timeseries)
- `trades_export_<timestamp>.csv`: 全取引履歴 (ENTRY/ADD/EXIT 分類付き)

### 主要メトリクス
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

### 自動化機能 (Phase 1 & 3)
- **ZIP自動圧縮**: バックテスト終了時にログファイルを自動圧縮 (logger.py)
- **Excel自動集計**: 複数ログを1つのExcelファイルに統合 (util.py)
- **CSV自動エクスポート**: 取引履歴を分析用CSVフォーマットで出力

メトリクス算出ロジックは `src/metrics.py`。`pnl_history` シリーズから標準的手法で計算。

## データキャッシュとタイムフレーム運用
本システムは戦略判定に 2時間足 (120分) を用い、補助/内部更新に 1分足を利用します。両者は同一 SQLite キャッシュテーブル `candles` 内で `timeframe` (分) により区別され、主キー `(symbol, timeframe, close_time)` により衝突しません。

### キャッシュ仕様
- DBパス: `src/ohlcv_data/ohlcv_cache.db` (WAL 有効)
- 保存列: `open_price, high_price, low_price, close_price, volume`
- 取得処理: バックテスト初期化時 `initialise_back_test_ohlcv_data` が必要期間を算出し
  1. 旧 JSON キャッシュ(互換)があれば取り込み → DBへ upsert
  2. `has_sufficient_cache()` で本数判定し不足時のみ API `fetch_ohlcv` で取得
  3. DBから要求期間を復元しメモリロード

### 再取得抑止ロジック
`has_sufficient_cache(symbol, timeframe, start, end)` は期待本数 `((end-start)//(timeframe*60))` から許容差 2 本を引いた閾値以上であれば再取得をスキップ。これにより既存期間全体が揃っている場合 Bybit API コールは発生しません。

### データ保持ポリシー
- **2025年以降のデータのみ保持**: 古いデータ (2024年以前) は定期的に削除し、最新データのみをキャッシュに保持
- バックテスト用 OHLCV データは `src/ohlcv_data/` 以下に JSON 形式で保存 (2025年1月以降)
- キャッシュ容量削減により高速アクセスと管理性を向上

### 留意点
- 本数のみで充足判定しており途中ギャップは未検出 (必要ならギャップ検出ロジック導入可能)。
- 2時間足は現状 1分足から再集計せず直接 API 取得（将来: 1分足ロールアップ最適化）。
- キャッシュ DB と WAL/SHM は `.gitignore` で除外し再現性は API + 初期化ロジックで担保。

### 将来改善候補
- ギャップ検出+差分取得による API 呼び出し最小化。
- 1分足のみ永続化し 2時間足はオンデマンド集計 (I/O 削減・一貫性向上)。
- キャッシュ整合性検査 (min/max 境界 & 連続性) レポート出力。


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

## 最新アップデート (2025-11-21)

### 🔴 適応型分類閾値システム実装完了 (優先度A)
- **適応型モニター**: `tools/adaptive_threshold_monitor.py` 実装完了
  - 最新trend_trades自動検出
  - 四半期ごとの自動チェック (`--check`)
  - config.ini自動更新 (`--apply-recommendations`)
  - ドリフト検出 (閾値15%で警告)
  
- **初回チェック結果** (2025-11-21):
  - トレード数: 168
  - 現設定: k2=2.2, k3=1.6
  - 推奨値: k2=1.9, k3=1.8
  - ドリフト: k2 13.6%, k3 12.5% (閾値15%未満)
  - 判定: ✅ 現設定は適切範囲内

- **実装ロードマップ作成**: `docs/IMPLEMENTATION_ROADMAP.md`
  - 優先度A〜D の段階的実装計画
  - 週次マイルストーンと成功指標
  - 進捗トラッキング (現在32.5%完了)

### 🟡 EXIT戦略拡張 (優先度B - 30%完了)
- **時間ベースEXIT**: `max_hold_bars` 実装済 (最適値探索待ち)
- **部分利確機能**: 実装済 (パラメータ最適化待ち)
- 次のステップ: ADX連動EXIT、レンジ相場EXIT

### 🟢 バックテスト高速化計画 (優先度C)
- 並列実行、キャッシュ最適化、段階的グリッド探索
- 目標: 32組合せを4時間以内 (現状112時間から1/28短縮)

### 過去のアップデート
- **Keltnerチャネル実装完了**: `price_data_management.py`にKeltnerシグナル評価追加、`trading_strategy.py`でフィルタ統合（トグル可能）
- **設定更新**: entry_times=4最適化、PVO業界標準(12/26/0)適用

詳細は `docs/IMPLEMENTATION_ROADMAP.md` および `docs/ARCHITECTURE_OVERVIEW.md` を参照。

## 免責
本ソフトは教育・研究目的。実運用は自己責任で行ってください。過去成績は将来を保証しません。

## ライセンス
MIT (必要に応じて `LICENSE` 参照)