# 自律実行エージェント — BOT監視メール送信機能 実装プロンプト

> **用途**: このプロンプトを VS Code Copilot の Agent モードに貼り付けて実行する。  
> エージェントは自律的に実装・テスト・デプロイを進める。  
> コミット・プッシュ・デプロイはユーザーの明示的な許可を得てから実行する。

---

## あなたの役割

あなたは **シニアPythonエンジニア（自律実装エージェント）** です。

**ミッション**:  
BTC/XAUTのトレードBOTとは**完全に独立した別プロセス**として動作する監視プロセスを実装する。  
このプロセスは24時間に1回、BOTのログを自動分析し、Gmailでレポートを送信する。

**絶対制約**:
- 稼働中の本番BOTプロセス（`bot_BTC.pid` / `bot_XAUT.pid`）には一切触れない
- 既存のソースコード（`src/bot.py` 等）を変更しない
- 監視プロセスはログファイルとステータスJSONを**読み取るだけ**（書き込み禁止）

---

## Phase 0 — 作業前確認（必須）

以下をユーザーに確認してから Phase 1 に進む。

```
【確認事項 1 — Gmail設定の準備状況】
以下の情報を取得済みか確認:
  a) Gmailアカウントのメールアドレス（送信元）
  b) Googleアカウントのアプリパスワード（16文字）
     取得方法: Googleアカウント → セキュリティ → 2段階認証 → アプリパスワード
  c) 送信先メールアドレス（送信元と同じでも可）

【確認事項 2 — メール送信テストの実行タイミング】
  a) 実装完了後すぐにテストメールを送信する（推奨）
  b) ローカルで単体テストのみ確認し、RPiでテスト送信する

【確認事項 3 — 送信スケジュール】
  a) 毎日午前9時（JST）に送信 → デプロイ後は日本時間9時に固定
  b) 起動から24時間後に毎回送信（BOT起動時刻に依存）
  c) カスタム時刻を指定（例: 毎日18時JST）

【確認事項 4 — ローカルテストのログ状況】
  ローカルに src/logs/latest_status.json が存在するか確認
  → 存在しない場合はモックJSONを使ってテストする
```

---

## Phase 1 — 実装するファイル一覧

以下のファイルを新規作成する（既存ファイルの変更は禁止）。

| ファイル | 役割 |
|---|---|
| `src/bot_monitor.py` | メインの監視・分析・メール送信スクリプト |
| `src/start_monitor.sh` | モニタープロセス起動スクリプト |
| `src/stop_monitor.sh` | モニタープロセス停止スクリプト |
| `src/.monitor_config.json.example` | Gmail設定のサンプルファイル |
| `test/test_bot_monitor_regression.py` | レグレッションテスト |
| `commands/monitor_email` | ローカル実行用コマンドラッパー |

---

## Phase 2 — 実装仕様

### 2-1. `src/bot_monitor.py` の構成

```python
#!/usr/bin/env python3
"""
bot_monitor.py — BTC/XAUT BOT独立監視・Gmailレポート送信プロセス

別プロセスとして起動し、24時間に1回BOTのログを分析してGmailでレポートを送信する。
既存BOTプロセスには一切干渉しない（ログ読み取りのみ）。

使用方法:
  python3 bot_monitor.py                  # デーモン起動（24時間ループ）
  python3 bot_monitor.py --send-now       # 今すぐ1回分析・送信して終了
  python3 bot_monitor.py --dry-run        # 送信せずレポートを標準出力に表示
  python3 bot_monitor.py --test-email     # テストメールを送信して終了
"""
```

#### クラス構成

```
LogAnalyzer
  ├── find_latest_log(logs_dir) → str | None       # 最新ログファイルのパスを返す
  ├── parse_status_json(path) → dict               # latest_status.jsonを読む
  ├── check_bot_alive(logs_dir, symbol) → bool     # PIDファイルでプロセス確認
  ├── count_log_pattern(log_path, pattern) → int   # grep相当のカウント
  ├── analyze_btc() → BotAnalysisResult           # BTC BOT分析
  └── analyze_xaut() → BotAnalysisResult          # XAUT BOT分析

BotAnalysisResult (dataclass)
  ├── symbol: str
  ├── is_alive: bool                # プロセス生死
  ├── last_log_age_seconds: float   # 最新ログの古さ（秒）
  ├── status: dict                  # latest_status.json の内容
  ├── error_count: int
  ├── rate_limit_count: int
  ├── main_loop_error_count: int
  ├── strategy_a_buy: int
  ├── strategy_a_sell: int
  ├── strategy_a_none: int
  ├── breakout_buy: int
  ├── breakout_sell: int
  ├── volume_filter_ng: int
  ├── adx_filter_ng: int
  ├── entry_allowed: int
  ├── entry_skipped: int
  ├── entry_executed: int
  └── log_file: str                 # 分析したログファイル名

ReportBuilder
  ├── build_report(btc: BotAnalysisResult, xaut: BotAnalysisResult) → str
  ├── _section_bot_status(result) → str      # BOT稼働状況セクション
  ├── _section_trade_status(result) → str    # トレード状況セクション
  └── _section_signal_report(result) → str  # シグナル・フィルタ所見セクション

GmailSender
  ├── __init__(config_path)                  # .monitor_config.jsonを読む
  ├── send(subject, body) → bool            # SMTP SSL でメール送信
  └── send_test() → bool                    # テストメール送信

BotMonitor
  ├── __init__(config_path, send_hour_jst)
  ├── run_once() → None             # 1回分析・送信
  └── run_loop() → None             # 24時間ループ（SIGTERM/SIGINTでクリーン終了）
```

### 2-2. ログパス定義

```python
# BTC
BTC_LOGS_DIR   = "logs"                         # src/logs/
BTC_STATUS_JSON = "logs/latest_status.json"
BTC_PID_FILE   = "logs/bot_BTC.pid"

# XAUT
XAUT_LOGS_DIR   = "logs/xaut"                   # src/logs/xaut/
XAUT_STATUS_JSON = "logs/xaut/latest_status.json"
XAUT_PID_FILE   = "logs/xaut/bot_XAUT.pid"

# モニター自身のPID
MONITOR_PID_FILE = "logs/bot_monitor.pid"
MONITOR_LOG_FILE = "logs/bot_monitor.log"
```

### 2-3. `.monitor_config.json` の形式

```json
{
  "gmail_address": "your@gmail.com",
  "gmail_app_password": "xxxx xxxx xxxx xxxx",
  "notify_to": "your@gmail.com",
  "send_hour_jst": 9,
  "subject_prefix": "[satosystem]"
}
```

`.monitor_config.json.example` としてサンプルを作成し、  
`.gitignore` に `.monitor_config.json` が登録されているか確認する（なければ追加）。

### 2-4. メールレポートの形式

```
件名: [satosystem] BOT監視レポート 2026-04-25 09:00 JST

==================================================
satosystem BOT 監視レポート
生成日時: 2026-04-25 09:00:01 JST
==================================================

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【1. BOT稼働状況】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

■ BTC BOT: ✅ 正常稼働中
  プロセス     : 稼働中 (PID: 12345)
  最新ログ更新 : 45秒前 (正常)
  稼働開始     : 2026-04-20 09:15
  エラー件数   : 3件（全て自動回復）
  RATE LIMIT   : 2回（全て自動回復）

■ XAUT BOT: ✅ 正常稼働中
  プロセス     : 稼働中 (PID: 12346)
  最新ログ更新 : 52秒前 (正常)
  稼働開始     : 2026-04-20 09:15
  エラー件数   : 1件（全て自動回復）
  RATE LIMIT   : 1回（全て自動回復）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【2. トレード状況】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

■ BTC
  現在価格     : 93,245 USD
  ポジション   : なし（NONE）
  残高         : 125.40 USD
  累計損益     : +25.40 USD
  DC上限(dc_h) : 95,200 USD  (+2.1% 距離)
  DC下限(dc_l) : 88,600 USD  (-5.0% 距離)
  ADX          : 22.5（レンジ相場）
  PVO          : -3.2（出来高不足）
  decision     : NONE

■ XAUT
  現在価格     : 3,245 USD
  ポジション   : なし（NONE）
  残高         : 82.10 USD
  累計損益     : -17.90 USD
  DC上限(dc_h) : 3,310 USD  (+2.0% 距離)
  DC下限(dc_l) : 3,180 USD  (-2.0% 距離)
  ADX          : 44.2（トレンド強い）
  PVO          : -1.5（出来高不足）
  decision     : NONE

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【3. シグナル・フィルタ整合性レポート】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

■ BTC シグナル統計（直近ログ全件）
  strategy_A BUY  : 12件
  strategy_A SELL : 8件
  strategy_A NONE : 980件
  Breakout BUY    : 2件
  Breakout SELL   : 1件
  出来高不足(NG)  : 2件
  ADX不足(NG)     : 1件
  エントリー許可  : 0件
  エントリー実行  : 0件

  エントリーゼロ判定: ✅ 妥当
  理由: Breakout発生は少数(3件)でかつ出来高不足・ADX不足でフィルタ機能中
  最大ブロック要因: 出来高不足（レンジ相場）

■ XAUT シグナル統計（直近ログ全件）
  strategy_A BUY  : 20件
  strategy_A SELL : 15件
  strategy_A NONE : 965件
  Breakout BUY    : 3件
  Breakout SELL   : 2件
  出来高不足(NG)  : 5件
  ADX不足(NG)     : 0件
  エントリー許可  : 0件
  エントリー実行  : 0件

  エントリーゼロ判定: ✅ 妥当
  理由: ADXは26以上だがBreakout発生時に出来高条件未達
  最大ブロック要因: 出来高不足

■ 並行動作チェック
  RATE LIMIT同時発生: なし（同一APIキー共有は正常範囲内）
  ポジション重複    : なし
  証拠金干渉        : 問題なし

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【総合評価】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ 両BOTは期待通りに動作しています。
エントリーゼロについて: ✅ 妥当 — 出来高不足によるフィルタが正常機能中

--
satosystem bot_monitor v1.0
```

### 2-5. BOT異常検知の判定ロジック

```python
def judge_bot_health(result: BotAnalysisResult) -> tuple[str, str]:
    """
    (status_icon, status_text) を返す
    ✅ 正常 / ⚠️ 要注意 / ❌ 異常
    """
    # ❌ プロセスが死んでいる
    if not result.is_alive:
        return "❌", "プロセス停止"
    
    # ❌ ログが5分以上更新されていない
    if result.last_log_age_seconds > 300:
        return "❌", f"ログ停止 ({int(result.last_log_age_seconds/60)}分更新なし)"
    
    # ❌ メインループエラーが複数
    if result.main_loop_error_count >= 2:
        return "❌", f"メインループエラー {result.main_loop_error_count}件"
    
    # ⚠️ ログが2分以上更新されていない
    if result.last_log_age_seconds > 120:
        return "⚠️", f"ログ遅延 ({int(result.last_log_age_seconds)}秒前)"
    
    # ⚠️ ERRORが多数（XAUTの証拠金マイナスループを疑う）
    if result.error_count > 500:
        return "⚠️", f"ERROR多発 ({result.error_count}件) 証拠金ループ疑い"
    
    return "✅", "正常稼働中"
```

### 2-6. `start_monitor.sh` の仕様

```bash
# start_bot.sh を参考に実装
# PIDファイル: logs/bot_monitor.pid
# ログ: logs/bot_monitor.log にリダイレクト
# 多重起動防止チェック
# nohup で バックグラウンド起動
```

### 2-7. `commands/monitor_email` の仕様

```bash
#!/bin/bash
# monitor_email — BOT監視メール送信コマンド
# 使用方法:
#   ./commands/monitor_email           # デーモン起動
#   ./commands/monitor_email --send-now   # 今すぐ送信
#   ./commands/monitor_email --dry-run    # プレビュー（送信なし）
#   ./commands/monitor_email --stop       # 停止
```

---

## Phase 3 — テスト仕様

### 3-1. `test/test_bot_monitor_regression.py` のテストケース

```python
# テストケース一覧（全てモックを使用 - 実際のログファイルに依存しない）

class TestLogAnalyzer:
    def test_find_latest_log_normal()           # 正常: 最新ログファイルを返す
    def test_find_latest_log_empty_dir()        # 異常: ディレクトリが空
    def test_find_latest_log_no_dir()           # 異常: ディレクトリが存在しない
    def test_parse_status_json_normal()         # 正常: JSONを正しくパース
    def test_parse_status_json_not_found()      # 異常: ファイルが存在しない
    def test_parse_status_json_corrupted()      # 異常: JSONが壊れている
    def test_check_bot_alive_running()          # 正常: プロセス稼働中
    def test_check_bot_alive_no_pid_file()      # 異常: PIDファイルなし
    def test_check_bot_alive_dead_process()     # 異常: プロセス停止済み
    def test_count_log_pattern_normal()         # 正常: パターンをカウント
    def test_count_log_pattern_no_file()        # 異常: ログファイルなし
    def test_log_age_calculation()              # 正常: ログの古さを計算

class TestBotAnalysis:
    def test_analyze_btc_all_normal()           # 正常: BTC分析（全て正常）
    def test_analyze_xaut_all_normal()          # 正常: XAUT分析（全て正常）
    def test_analyze_btc_bot_stopped()          # 異常: BTCが停止中
    def test_analyze_xaut_many_errors()         # 異常: XAUTエラー多発

class TestReportBuilder:
    def test_build_report_both_normal()         # 正常: 両BOT正常時のレポート生成
    def test_build_report_btc_stopped()         # 異常: BTC停止時のレポート
    def test_build_report_entry_zero_valid()    # 正常: エントリーゼロ妥当判定
    def test_build_report_entry_zero_suspect()  # 要確認: エントリーゼロ要確認

class TestJudgeBotHealth:
    def test_judge_normal()                     # ✅ 正常
    def test_judge_process_dead()               # ❌ プロセス停止
    def test_judge_log_stale_300s()             # ❌ ログ5分以上停止
    def test_judge_log_stale_150s()             # ⚠️ ログ2分以上遅延
    def test_judge_many_errors()                # ⚠️ ERROR多発

class TestGmailSender:
    def test_send_mock_smtp()                   # SMTPをモックして送信成功
    def test_send_invalid_config()             # 設定ファイルなしでエラー
    def test_config_loading()                   # .monitor_config.jsonのパース
```

### 3-2. ローカル動作テスト手順

```bash
cd /home/satoshi/work/satosystem

# 1. レグレッションテスト実行
./commands/prj-run-regression

# 2. 新テスト単体実行
python3 -m pytest test/test_bot_monitor_regression.py -v

# 3. --dry-run でレポートをターミナルに表示
cd src
python3 bot_monitor.py --dry-run

# 4. テストメール送信（.monitor_config.json 作成後）
python3 bot_monitor.py --test-email

# 5. --send-now で1回送信テスト
python3 bot_monitor.py --send-now
```

---

## Phase 4 — デプロイ手順

### 前提条件（デプロイ前に確認）

- [ ] `python3 -m pytest test/test_bot_monitor_regression.py -v` が全PASS
- [ ] `./commands/prj-run-regression` が全PASS（既存テスト190件が壊れていない）
- [ ] ローカルで `--dry-run` でレポートが正常生成される
- [ ] ローカルで `--test-email` でGmailが届く
- [ ] `.gitignore` に `.monitor_config.json` が追加されている

### デプロイ手順

```bash
# 1. コミット（ユーザー許可後）
git add src/bot_monitor.py src/start_monitor.sh src/stop_monitor.sh \
        src/.monitor_config.json.example \
        test/test_bot_monitor_regression.py \
        commands/monitor_email
git commit -m "feat: BOT監視メール送信機能（bot_monitor.py）実装"

# 2. RPiへデプロイ（既存BOTは停止しない）
./commands/prj-deploy --no-restart

# 3. RPi側で .monitor_config.json を作成
ssh raspberry_pi "cat > ~/work/satosystem/src/.monitor_config.json << 'EOF'
{
  \"gmail_address\": \"（ユーザーが入力）\",
  \"gmail_app_password\": \"（ユーザーが入力）\",
  \"notify_to\": \"（ユーザーが入力）\",
  \"send_hour_jst\": 9,
  \"subject_prefix\": \"[satosystem]\"
}
EOF"

# 4. RPi側でテストメール送信確認
ssh raspberry_pi "cd ~/work/satosystem/src && python3 bot_monitor.py --test-email"

# 5. RPi側でモニタープロセスを起動
ssh raspberry_pi "cd ~/work/satosystem/src && ./start_monitor.sh"

# 6. RPiのプロセス状態確認
ssh raspberry_pi "ps aux | grep bot_monitor && cat ~/work/satosystem/src/logs/bot_monitor.pid"
```

---

## Phase 5 — 安全性チェックリスト

### ❌ 絶対にやってはいけないこと

| 禁止事項 | 理由 |
|---|---|
| `start_bot.sh` / `stop_bot.sh` の変更 | 稼働中BOTに影響する |
| `bot.py` / `config.ini` の変更 | 本番BOT設定の破損リスク |
| BOTのPIDファイルへの書き込み | プロセス管理が壊れる |
| BOTのログファイルへの書き込み | ログ整合性が壊れる |
| `logs/latest_status.json` への書き込み | BOT状態管理が壊れる |
| `.api_key` の変更 | 取引所API接続が切断される |

### ✅ 監視プロセスが書き込んでよいファイル

| ファイル | 用途 |
|---|---|
| `logs/bot_monitor.pid` | 監視プロセス自身のPID |
| `logs/bot_monitor.log` | 監視プロセス自身のログ |

---

## Phase 6 — 完了判定基準

以下が全て満たされた時点で実装完了とする。

| 条件 | 確認方法 |
|---|---|
| レグレッションテスト全PASS | `./commands/prj-run-regression` |
| 新テスト全PASS | `python3 -m pytest test/test_bot_monitor_regression.py -v` |
| `--dry-run` でレポートが生成される | ターミナルで確認 |
| `--test-email` でGmailが届く | メール受信確認 |
| RPiで監視プロセスが起動している | `ps aux | grep bot_monitor` |
| RPiで既存BOTが影響を受けていない | `./commands/prj-deploy --status-only` |
| 24時間後に定期レポートが届く | 翌日メール確認 |

---

## 注意事項

- **Gmail アプリパスワードは `.monitor_config.json` にのみ保存** — コードにハードコードしない
- **`.monitor_config.json` は `.gitignore` で除外** — GitHubにプッシュしない
- **BOTの停止もメールで通知** — `is_alive=False` の場合は件名を `[ALERT]` にする
- **ログが存在しない場合は "データなし" として処理** — 例外を飲み込まない

---

## 参考情報

### ログファイルのパス（RPi本番環境）

```
~/work/satosystem/src/logs/
  ├── bot_BTC_YYYYMMDD_HHMMSS.log   # BTC最新ログ
  ├── latest_status.json             # BTC現在状態
  ├── bot_BTC.pid                    # BTCプロセスID
  └── xaut/
      ├── bot_XAUT_YYYYMMDD_HHMMSS.log  # XAUT最新ログ
      ├── latest_status.json             # XAUT現在状態
      └── bot_XAUT.pid                   # XAUTプロセスID
```

### latest_status.json の主要フィールド

```json
{
  "updated_at": "2026-04-25T08:59:01",
  "decision": "NONE",
  "side": "BUY",
  "position_side": "NONE",
  "close": 93245.0,
  "dc_h": 95200.0,
  "dc_l": 88600.0,
  "adx": 22.5,
  "pvo_val": -3.2,
  "pnl": 0.0,
  "total_pnl": 25.40,
  "unionAvailable": 125.40
}
```

### check-rpi-logs.instructions.md のログ解析パターン（`grep` 相当）

```python
# エラー統計
error_count       = count_pattern(log, r'ERROR')
rate_limit_count  = count_pattern(log, r'RATE LIMIT')
main_loop_errors  = count_pattern(log, r'メインループエラー')

# シグナル統計
strategy_a_buy    = count_pattern(log, r'strategy_A: BUY')
strategy_a_sell   = count_pattern(log, r'strategy_A: SELL')
strategy_a_none   = count_pattern(log, r'全Strategy: NONE')
breakout_buy      = count_pattern(log, r'Breakout強度.*✓ BUY')
breakout_sell     = count_pattern(log, r'Breakout強度.*✓ SELL')
volume_ng         = count_pattern(log, r'相対出来高.*✗')
adx_ng            = count_pattern(log, r'ADX.*✗|ADX不足')
entry_allowed     = count_pattern(log, r'エントリー許可')
entry_skipped     = count_pattern(log, r'エントリー見送り')
entry_executed    = count_pattern(log, r'エントリー実行|注文送信|ポジション取得|Entry order')
```
