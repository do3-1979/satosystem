# satosystem gen2

Bitcoin / XAUT 自動取引ボット（Donchian Breakout + ADX + PVO フィルタ）

- **目標リターン**: 年利 50%
- **初期資本**: 100 USD、レバレッジ 10×
- **取引所**: Bybit（OHLCVデータ） + Bybit（注文執行）
- **稼働基盤**: Raspberry Pi 24/7
- **ブランチ**: `gen2`

---

## クイックスタート

```bash
# 1. 依存パッケージインストール
pip install -r requirements.txt   # 未作成の場合は pip install ccxt pytz psutil

# 2. APIキー設定
cp src/.api_key.example src/.api_key
# .api_key を編集して Bybit APIキーを記入

# 3. バックテスト実行
cd src && python3 bot.py

# 4. 本番起動（Raspberry Pi）
cd src && ./start_bot.sh        # BTC BOT
cd src && ./start_gold_bot.sh   # XAUT BOT

# 5. BOT停止
cd src && ./stop_bot.sh
```

---

## ドキュメント一覧

| ファイル | 内容 |
|---------|------|
| [docs/PROJECT_OVERVIEW.html](docs/PROJECT_OVERVIEW.html) | **プロジェクト全体統合ドキュメント（HTML）** |
| [docs/ARCHITECTURE_OVERVIEW.md](docs/ARCHITECTURE_OVERVIEW.md) | クラス構成・データフロー詳細 |
| [docs/AI_STRATEGY_GUIDE.md](docs/AI_STRATEGY_GUIDE.md) | AI向け戦略仕様・パラメータ一覧 |
| [docs/STATIC_ANALYSIS_REPORT.md](docs/STATIC_ANALYSIS_REPORT.md) | ソースコード静的解析レポート |
| [PROGRESS.json](PROGRESS.json) | 現在の進捗・タスク状態 |
| [ACTION_LIST.json](ACTION_LIST.json) | TODO / 作業中 / 完了タスク |
| [DEVELOPMENT_RULES.json](DEVELOPMENT_RULES.json) | 開発ルール・コーディング規約 |

---

## ディレクトリ構成

```
satosystem/
├── README.md                  # このファイル
├── ACTION_LIST.json           # タスク管理
├── PROGRESS.json              # 進捗管理
├── DEVELOPMENT_RULES.json     # 開発ルール
├── commands/                  # プロジェクトコマンド群
│   ├── prj-deploy             # RPiデプロイ一括実行
│   ├── prj-run-regression     # レグレッションテスト実行
│   ├── prj-update-ohlcv-db    # OHLCVキャッシュDB更新
│   ├── monitor_bot            # ターミナルBOTモニター
│   └── monitor_web            # Web版BOTモニター
├── src/                       # 本体ソースコード（Python）
│   ├── bot.py                 # メインループ・注文管理
│   ├── trading_strategy.py    # エントリー/エグジット判断
│   ├── risk_management.py     # ポジションサイズ・ストップ管理
│   ├── portfolio.py           # 損益・ドローダウン管理
│   ├── exit_strategy_v2.py    # 複合出口戦略（PSAR/Chandelier等）
│   ├── price_data_management.py # OHLCV取得・シグナル生成
│   ├── bybit_exchange.py      # Bybit取引所ラッパー
│   ├── config.py              # 設定値一元管理
│   ├── config.ini             # BTC BOT設定ファイル
│   ├── config_xaut.ini        # XAUT BOT設定ファイル
│   ├── risk_overlay.py        # DDキルスイッチ（Task40c）
│   ├── cost_model.py          # バックテスト手数料モデル（Task40b）
│   ├── new_indicators.py      # strategy_A (ADX-based)指標
│   ├── market_regime_detector.py # 市場体制判定
│   ├── vcp_strategy.py        # VCPパターン検出（補助）
│   ├── mean_reversion_strategy.py # 平均回帰戦略（Phase1評価中）
│   ├── ohlcv_cache.py         # SQLiteキャッシュ管理
│   └── logs/                  # ログ出力先
├── test/                      # テストコード（26ファイル）
│   └── regression_test_suite.py  # レグレッションテスト統合スイート
├── docs/                      # ドキュメント
├── baseline_backup/           # バックテストベースライン保存
├── ohlcv_data/                # OHLCVキャッシュDB
└── commands/                  # 運用コマンドスクリプト
```

---

## 戦略概要

### エントリー条件（全条件 AND）

| # | 条件 | パラメータ | BTC値 | XAUT値 |
|---|------|----------|------|------|
| 1 | Donchian Breakout | buy_term / sell_term | 30本 | 30本 |
| 2 | PVO > 閾値 | pvo_threshold | 10 | 0 |
| 3 | ADX ≥ 閾値 | adx_bull_threshold | 31 | 26 |
| 4 | strategy_A (TSMOM) 方向一致 | enable_strategy_a_adx | 有効 | 有効 |
| 5 | 相対出来高 ≥ 1.5× | volume filter | — | 有効 |

### エグジット条件（優先順）

1. **PSARトレイリングストップ**（メイン）: lookback=300, AF=0.02→0.20
2. **サージエグジット**: 急激な逆行
3. **スケールアウト（H-042）**: MFE 10% → 50%部分決済 → ブレイクイーブンストップ移動
4. **時間ベース（Stage3）**: 72時間保有上限（デフォルト無効）
5. **Chandelier Exit / PSL / VolumeClimax** 等（全てデフォルト無効）

---

## 実行モード

| モード | back_test | dummy | 用途 |
|--------|-----------|-------|------|
| バックテスト | 1 | 1 | 過去データで戦略検証 |
| キャッシュベースホットテスト | 0 | 1 | SQLiteキャッシュ使用・API不要 |
| ペーパートレード | 0 | 1 | ライブ市場・ダミー発注 |
| 本番取引 | 0 | 0 | 実際の取引実行 |

---

## パフォーマンス（最新ベースライン）

**ベースライン**: H-042 ScaleOut採用後（2026-05-11）

| 指標 | 値 |
|-----|---|
| 通年累積損益（2024/01〜2026/05） | +2,197.00 USD |
| 最大ドローダウン | ~36% (Q2-Q3 2024) |
| レグレッションテスト | 216/216 PASS |
| 四半期テスト（BTC） | 9/9 PASS |
| 四半期テスト（XAUT） | 4/4 PASS |

---

## 本番BOT監視

```bash
# RPi稼働状態確認
./commands/prj-deploy --status-only

# ターミナルモニター（Raspberry Pi）
./commands/monitor_bot --host raspberry_pi

# Webモニター（ブラウザ http://localhost:8080）
./commands/monitor_web --host raspberry_pi --port 8080
```

---

## 開発フロー

```bash
# 1. 変更後 → レグレッションテスト
./commands/prj-run-regression

# 2. PASS後 → ユーザー承認を得てコミット
git add -p && git commit -m "feat: ..."

# 3. RPiへデプロイ（両BOTがポジションなしを確認後）
./commands/prj-deploy
```

> **重要**: コミット・プッシュ・デプロイは必ずユーザーの明示的許可後に実行すること。

---

## 既知の制約

- BTC / XAUT が同一Bybit APIキーを共有するため、同時RATE LIMITが発生することがある（自動回復）
- Bybit合算証拠金モードでBTCポジション損益がXAUT証拠金計算に影響する場合がある
- 詳細は [docs/STATIC_ANALYSIS_REPORT.md](docs/STATIC_ANALYSIS_REPORT.md) 参照
