# プロジェクト引き継ぎドキュメント
作成日: 2026-06-28

---

## プロジェクト一覧

| プロジェクト名 | 概要 |
|---|---|
| **satosystem gen2** | BTC/USDT + XAUT/USDT デュアルアセット暗号資産自動売買ボット（ドンチャンブレイクアウト戦略） |

> 本リポジトリはモノリポ構成で、単一の主要プロジェクト `satosystem gen2` のみが存在する。

---

## 各プロジェクト詳細

### satosystem gen2

- **目的**: Bybit（データ取得）＋ Bitget（注文執行）を利用したBTC/USDT・XAUT/USDTの自動売買。ドンチャンブレイクアウト＋ADX/PVO/TSMOM多重フィルタ戦略で年率50%を目標とする。ラズベリーパイで24/7稼働中。

- **技術スタック**:
  - 言語: Python 3.x（約15,800 LOC）
  - 取引所API: CCXT（Bybit＝データ取得、Bitget＝注文実行）
  - DB: SQLite（OHLCVキャッシュ）
  - インフラ: Raspberry Pi（24/7本番）＋ WSL2 Ubuntu 22.04（開発環境）
  - 主要ライブラリ: ccxt, pytz, psutil

- **進捗**: **Phase 4 - デュアルアセット本番稼働中（完成度 約90%）**
  - フェーズ1（2024Q1〜Q3）: シングルアセット（BTC）基本戦略 ✅
  - フェーズ2（2024Q4〜2025Q2）: パラメータ最適化（仮説45+件） ✅
  - フェーズ3（2025Q3〜2026Q1）: 高度な出口戦略、XAUTインテグレーション ✅
  - フェーズ4（2026Q2〜）: デュアルアセットRPi稼働 🟢 現在進行中
  - テスト: 216/216 リグレッションテスト PASS（100%）
  - バックテスト成績: BTC累計 +3,062.87 USD（9Q）、XAUT累計 +89.36 USD（4Q）

- **直近の作業**:
  - `2026-06-16` `fix`: monitor_web zip読み込み上限を20→90に拡張（チャートの過去データ表示修正）
  - `2026-06-14` `feat`: H-XAUT-02 FundingRate閾値緩和 + XAUT 12Q対応 + quarterly regression test追加
  - `2026-06-12` `fix`: required_candles計算にdonchian_term・tsmom_lookbackを考慮（BTC:38→160本、XAUT:38→50本）
  - `2026-06-10` `docs`: README.md新規作成・PROJECT_OVERVIEW.html更新・古いMDファイル削除/アーカイブ・STATIC_ANALYSIS_REPORT.md追加
  - `2026-06-08` `fix`: 静的解析修正3件（bare raise→ValueError、stop_AF重複代入削除、未使用symbol変数削除）

- **残タスク**:
  - **【高優先度】Task 48**: Bybitサービス終了への対応 — PAXG/USDT（Bybit 2023-01〜）をXAUT代替ヒストリとして利用し、9Q以上のバックテスト対応を実現
    - コマンド: `prj-update-ohlcv-db --symbol PAXG/USDT --as-symbol XAUT/USDT --full`
  - **【高優先度】Task 47**: バランス取得モードの修正 — デフォルトをAPIからリアルタイム取得に変更（`use_custom_balance=1`の時のみ設定値を使用）
  - **【中優先度】Task 40f**: Price Data Health Check — OHLCVのギャップ・重複・スパイクの検出・修正
  - **【中優先度】pdca-H-037**: BTC+XAUT 合計エクスポージャー上限 — 証拠金の80%超で新規XAUT エントリを停止するロジックの検証
  - **【低優先度】pdca-H-023**: Fear & Greed Index 統合（感情フィルタ）
  - **設計メモ（Non-blocking）**:
    - DESIGN-003: Mean ReversionのSELLシグナル未実装（現在は無効、有効化前に要対応）
    - DESIGN-004: VCPが1hタイムフレームをハードコード（有効化前に動的読み取りに変更要）

- **次にやること**:
  1. **Task 47（バランス取得モード修正）の実装** — 直近タスクでスコープが小さく着手しやすい。`src/bot.py` のバランス読み取り部分を修正し、`use_custom_balance=1` のフラグが無ければAPIから取得するよう変更。
  2. **Task 48（PAXG代替OHLCV取得）の実施** — XAUTのバックテスト期間を2023Q1〜に延長することでXAUT戦略の信頼性が向上する。
  3. **リグレッションテストの確認** — 変更前後に必ず `./commands/prj-run-regression` を実行（216/216 PASS を確認）。
  4. **RPiへのデプロイ承認フロー** — `./commands/prj-deploy` を実行し、差分確認後に明示的承認を取ること。

---

## アーキテクチャ概要

```
Config (config.ini / config_xaut.ini)
  └─ PriceDataManagement (Bybit OHLCV取得)
       └─ TradingStrategy (ENTRY/ADD/EXIT判定)
            ├─ RiskManagement (ポジションサイジング、PSAR、ATR、ADX)
            ├─ ExitStrategyV2 (多段階出口ロジック)
            └─ RiskOverlay (DD 40%でキルスイッチ)
                 └─ Bot (Bitget経由で注文実行)
                      └─ Portfolio (P&L・ドローダウン追跡)
                           └─ Logger (JSON構造化ログ)
```

### デュアルノード構成

| 環境 | 役割 | 備考 |
|---|---|---|
| Raspberry Pi（192.168.1.19） | 24/7本番稼働（BTC + XAUT） | `ssh raspberry_pi` でアクセス |
| WSL2 Ubuntu 22.04（開発） | 開発・バックテスト・仮説検証 | 本リポジトリのパス |

### 重要なオペレーションルール

1. **RPiでのBot起動は必ず `./start_bot.sh` 経由で行う**（直接 `python3 bot.py` は禁止 — PID管理が機能しなくなる）
2. **commit/pushは必ず明示的なユーザー承認が必要**（APIキー漏洩のリスク確認を含む）
3. **デプロイ前に `./commands/prj-run-regression` を実行し、216/216 PASS を確認する**

---

## 重要ファイル一覧

| ファイル | 内容 |
|---|---|
| `README.md` | プロジェクト概要・クイックスタート |
| `PROGRESS.json` | フェーズ状態・完了タスク一覧 |
| `ACTION_LIST.json` | TODO・優先度・完了ログ |
| `DEVELOPMENT_RULES.json` | 運用ルール（必読） |
| `src/config.ini` | BTC戦略パラメータ |
| `src/config_xaut.ini` | XAUTパラメータ |
| `src/.api_key` | API認証情報（要秘匿・gitignored） |
| `docs/PROJECT_OVERVIEW.html` | 包括的HTMLドキュメント（マスター） |
| `docs/STATIC_ANALYSIS_REPORT.md` | 静的解析レポート |
| `ohlcv_data/satosystem.db` | SQLite OHLCVキャッシュ |

---

## 注意事項・メモ

- **`src/.api_key` は絶対にコミットしないこと。** `.gitignore` で管理しているが、`git status` で確認を怠らない。
- **RPiのBotを停止せずにコード変更をpushした場合、次回 `./start_bot.sh` の前に `./stop_bot.sh` で停止すること。**
- Bybitが日本向けサービスを段階終了中（2026年以降）。XAUTのデータソースとして PAXG/USDT への移行計画（Task 48）を優先的に進めること。
- sweep_scripts/ に仮説検証スクリプトが35本以上格納されている。新規仮説を検証する際はここに追加し、結果を `ACTION_LIST.json` に記録する。
- バックテスト実行には SQLite OHLCVキャッシュ（`ohlcv_data/satosystem.db`）が必要。キャッシュが古い場合は `./tools/update_ohlcv_db.py` で更新すること。
- `baseline_backup/` に各マイルストーン時点のパフォーマンス基準値が保存されている。新しい変更の効果測定に使用する。
