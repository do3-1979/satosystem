#!/usr/bin/env python3
"""
bot_monitor.py — BTC/XAUT BOT独立監視・Gmailレポート送信プロセス

別プロセスとして起動し、毎日JST 22:00 にBOTのログを分析してGmailでレポートを送信する。
既存BOTプロセスには一切干渉しない（ログ読み取りのみ）。

使用方法:
  python3 bot_monitor.py                  # デーモン起動（毎日22:00 JSTループ）
  python3 bot_monitor.py --send-now       # 今すぐ1回分析・送信して終了
  python3 bot_monitor.py --dry-run        # 送信せずレポートを標準出力に表示
  python3 bot_monitor.py --test-email     # テストメールを送信して終了
"""

import argparse
import glob
import json
import logging
import os
import re
import signal
import smtplib
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

# ==============================================================
# 定数定義
# ==============================================================

VERSION = "1.0"

# スクリプトのディレクトリ（src/）
SCRIPT_DIR = Path(__file__).parent.resolve()

# BTC BOT
BTC_LOGS_DIR    = SCRIPT_DIR / "logs"
BTC_STATUS_JSON = SCRIPT_DIR / "logs" / "latest_status.json"
BTC_PID_FILE    = SCRIPT_DIR / "logs" / "bot_BTC.pid"

# XAUT BOT
XAUT_LOGS_DIR    = SCRIPT_DIR / "logs" / "xaut"
XAUT_STATUS_JSON = SCRIPT_DIR / "logs" / "xaut" / "latest_status.json"
XAUT_PID_FILE    = SCRIPT_DIR / "logs" / "xaut" / "bot_XAUT.pid"

# モニター自身
MONITOR_PID_FILE = SCRIPT_DIR / "logs" / "bot_monitor.pid"
MONITOR_LOG_FILE = SCRIPT_DIR / "logs" / "bot_monitor.log"

# デフォルト設定ファイルパス（Gmail認証情報 — gitignore対象）
DEFAULT_CONFIG_PATH = SCRIPT_DIR / ".gmail"

# JST タイムゾーン
JST = timezone(timedelta(hours=9))

# デフォルト送信時刻（JST）
DEFAULT_SEND_HOUR_JST = 22

# ==============================================================
# ロガー設定
# ==============================================================

def setup_logger(log_file: Optional[Path] = None) -> logging.Logger:
    logger = logging.getLogger("bot_monitor")
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    if log_file:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    return logger

logger = setup_logger()

# ==============================================================
# データクラス
# ==============================================================

@dataclass
class BotAnalysisResult:
    symbol: str
    is_alive: bool = False
    pid: Optional[int] = None
    last_log_age_seconds: float = float("inf")
    log_file: str = ""
    status: dict = field(default_factory=dict)
    error_count: int = 0
    rate_limit_count: int = 0
    main_loop_error_count: int = 0
    main_loop_error_recent_count: int = 0  # 直近24時間
    strategy_a_buy: int = 0
    strategy_a_sell: int = 0
    strategy_a_none: int = 0
    breakout_buy: int = 0
    breakout_sell: int = 0
    volume_filter_ng: int = 0
    adx_filter_ng: int = 0
    entry_allowed: int = 0
    entry_skipped: int = 0
    entry_executed: int = 0
    no_log: bool = False
    status_age_seconds: float = float("inf")  # latest_status.json の updated_at からの経過秒

# ==============================================================
# LogAnalyzer
# ==============================================================

class LogAnalyzer:
    """BOTログの読み取り・分析（書き込みは行わない）"""

    def find_latest_log(self, logs_dir: Path, symbol: str) -> Optional[str]:
        """最新の BOT ログファイルパスを返す。存在しなければ None。"""
        if not logs_dir.exists():
            return None
        pattern = str(logs_dir / f"bot_{symbol}_*.log")
        files = glob.glob(pattern)
        if not files:
            return None
        return max(files, key=os.path.getmtime)

    def parse_status_json(self, path: Path) -> tuple[dict, float]:
        """
        latest_status.json を読み込む。
        戻り値: (status_dict, age_seconds)
        - status_dict: "latest" キー配下の取引データ（なければトップレベル）
        - age_seconds: updated_at からの経過秒（取得できなければ inf）
        """
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # ネスト構造対応: データは "latest" キー配下にある
            status = data.get("latest", data)
            # updated_at から経過秒を計算
            age = float("inf")
            updated_at = data.get("updated_at", "")
            if updated_at:
                try:
                    fmt = "%Y/%m/%d %H:%M:%S"
                    dt = datetime.strptime(updated_at, fmt).replace(tzinfo=JST)
                    age = (datetime.now(JST) - dt).total_seconds()
                except Exception:
                    pass
            return status, age
        except FileNotFoundError:
            return {}, float("inf")
        except json.JSONDecodeError:
            logger.warning(f"JSONパースエラー: {path}")
            return {}, float("inf")
        except Exception as e:
            logger.warning(f"status JSON 読み込みエラー: {path} - {e}")
            return {}, float("inf")

    def check_bot_alive(self, pid_file: Path) -> tuple[bool, Optional[int]]:
        """
        PID ファイルでプロセスの生死を確認する。
        戻り値: (is_alive, pid)
        """
        if not pid_file.exists():
            return False, None
        try:
            with open(pid_file, "r") as f:
                pid = int(f.read().strip())
            # シグナル 0 でプロセス存在確認
            os.kill(pid, 0)
            return True, pid
        except (ValueError, ProcessLookupError, PermissionError):
            return False, None
        except Exception:
            return False, None

    def count_log_pattern(self, log_path: str, pattern: str) -> int:
        """ログファイル内でパターンにマッチする行数を返す。"""
        if not log_path or not os.path.exists(log_path):
            return 0
        try:
            count = 0
            regex = re.compile(pattern)
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    if regex.search(line):
                        count += 1
            return count
        except Exception as e:
            logger.warning(f"ログパターンカウントエラー: {e}")
            return 0

    def count_log_pattern_recent(self, log_path: str, pattern: str, hours: int = 24) -> int:
        """直近 hours 時間以内でパターンにマッチする行数を返す。"""
        if not log_path or not os.path.exists(log_path):
            return 0
        cutoff = datetime.now() - timedelta(hours=hours)
        regex = re.compile(pattern)
        ts_regex = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")
        count = 0
        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    m = ts_regex.match(line)
                    if m:
                        try:
                            ts = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
                            if ts < cutoff:
                                continue
                        except ValueError:
                            pass
                    if regex.search(line):
                        count += 1
            return count
        except Exception as e:
            logger.warning(f"ログパターンカウントエラー(recent): {e}")
            return 0

    def get_log_age_seconds(self, log_path: str) -> float:
        """ログファイルの最終更新からの経過秒数を返す。"""
        if not log_path or not os.path.exists(log_path):
            return float("inf")
        mtime = os.path.getmtime(log_path)
        return time.time() - mtime

    def analyze(self, symbol: str, logs_dir: Path, status_json_path: Path,
                 pid_file: Path) -> BotAnalysisResult:
        """BOT を分析して BotAnalysisResult を返す。"""
        result = BotAnalysisResult(symbol=symbol)

        # プロセス確認
        result.is_alive, result.pid = self.check_bot_alive(pid_file)

        # ステータス JSON 読み込み
        result.status, result.status_age_seconds = self.parse_status_json(status_json_path)

        # 最新ログ
        log_path = self.find_latest_log(logs_dir, symbol)
        if log_path:
            result.log_file = os.path.basename(log_path)
            result.last_log_age_seconds = self.get_log_age_seconds(log_path)

            # パターンカウント
            result.error_count            = self.count_log_pattern(log_path, r"ERROR")
            result.rate_limit_count       = self.count_log_pattern(log_path, r"RATE LIMIT")
            result.main_loop_error_count        = self.count_log_pattern(log_path, r"メインループエラー")
            result.main_loop_error_recent_count = self.count_log_pattern_recent(log_path, r"メインループエラー", hours=24)
            result.strategy_a_buy         = self.count_log_pattern(log_path, r"strategy_A: BUY")
            result.strategy_a_sell        = self.count_log_pattern(log_path, r"strategy_A: SELL")
            result.strategy_a_none        = self.count_log_pattern(log_path, r"全Strategy: NONE")
            result.breakout_buy           = self.count_log_pattern(log_path, r"Breakout強度.*✓ BUY")
            result.breakout_sell          = self.count_log_pattern(log_path, r"Breakout強度.*✓ SELL")
            result.volume_filter_ng       = self.count_log_pattern(log_path, r"相対出来高.*✗")
            result.adx_filter_ng          = self.count_log_pattern(log_path, r"ADX.*✗|ADX不足")
            result.entry_allowed          = self.count_log_pattern(log_path, r"エントリー許可")
            result.entry_skipped          = self.count_log_pattern(log_path, r"エントリー見送り")
            result.entry_executed         = self.count_log_pattern(
                log_path, r"エントリー実行|注文送信|ポジション取得|Entry order"
            )
        else:
            result.no_log = True

        return result

    def analyze_btc(self) -> BotAnalysisResult:
        return self.analyze("BTC", BTC_LOGS_DIR, BTC_STATUS_JSON, BTC_PID_FILE)

    def analyze_xaut(self) -> BotAnalysisResult:
        return self.analyze("XAUT", XAUT_LOGS_DIR, XAUT_STATUS_JSON, XAUT_PID_FILE)


# ==============================================================
# BOT ヘルス判定
# ==============================================================

def judge_bot_health(result: BotAnalysisResult) -> tuple[str, str]:
    """
    (status_icon, status_text) を返す。
    ✅ 正常 / ⚠️ 要注意 / ❌ 異常
    """
    if not result.is_alive:
        return "❌", "プロセス停止"

    # latest_status.json の updated_at を主指標とする（BOTは毎分更新）
    # ログファイルの mtime は補助指標（hourly memory log のみの場合があるため）
    heartbeat_age = min(result.status_age_seconds, result.last_log_age_seconds)

    if heartbeat_age > 300:
        mins = int(heartbeat_age / 60)
        return "❌", f"ログ停止 ({mins}分更新なし)"

    if result.main_loop_error_recent_count >= 2:
        return "❌", f"メインループエラー {result.main_loop_error_recent_count}件(直近24h)"
    # 直近24h=0件なら累計エラーがあっても正常扱い

    if heartbeat_age > 120:
        secs = int(heartbeat_age)
        return "⚠️", f"ログ遅延 ({secs}秒前)"

    if result.error_count > 500:
        return "⚠️", f"ERROR多発 ({result.error_count}件) 証拠金ループ疑い"

    return "✅", "正常稼働中"


def judge_entry_zero(result: BotAnalysisResult) -> tuple[str, str]:
    """
    エントリーゼロの妥当性を判定する。
    (icon, reason) を返す。
    """
    if result.entry_executed > 0:
        return "✅", f"エントリー実行 {result.entry_executed}件"

    total_breakout = result.breakout_buy + result.breakout_sell

    if total_breakout == 0:
        return "✅", "Breakout未発生（レンジ相場）"

    # エントリー許可が出ているのに発注ゼロ
    if result.entry_allowed > 0 and result.entry_executed == 0:
        return "❌", f"エントリー許可{result.entry_allowed}件なのに発注ゼロ — ロジックバグ疑い"

    # 出来高不足が主因
    if result.volume_filter_ng >= total_breakout:
        return "✅", f"出来高不足({result.volume_filter_ng}件)がBreakout({total_breakout}件)を全ブロック"

    # ADX不足が主因
    if result.adx_filter_ng >= total_breakout:
        return "✅", f"ADX不足({result.adx_filter_ng}件)がBreakout({total_breakout}件)を全ブロック"

    # Breakout発生しているがフィルタ通過ゼロ
    if total_breakout > 5 and result.entry_allowed == 0:
        return "⚠️", f"Breakout{total_breakout}件発生だがエントリー許可ゼロ — フィルタ過剰の可能性"

    return "✅", "フィルタが正常機能中（出来高/ADX条件未達）"


# ==============================================================
# ReportBuilder
# ==============================================================

class ReportBuilder:
    """メールレポートの文字列を組み立てる"""

    def _fmt_seconds_ago(self, secs: float) -> str:
        if secs == float("inf"):
            return "不明"
        if secs < 60:
            return f"{int(secs)}秒前"
        return f"{int(secs / 60)}分{int(secs % 60)}秒前"

    def _fmt_price(self, val) -> str:
        try:
            return f"{float(val):,.2f}"
        except (TypeError, ValueError):
            return "N/A"

    def _fmt_pct_dist(self, price, target) -> str:
        try:
            pct = (float(target) - float(price)) / float(price) * 100
            sign = "+" if pct >= 0 else ""
            return f"{sign}{pct:.1f}%"
        except (TypeError, ValueError, ZeroDivisionError):
            return "N/A"

    def _adx_label(self, adx) -> str:
        try:
            v = float(adx)
            if v >= 31:
                return "トレンド強い"
            if v >= 20:
                return "弱トレンド"
            return "レンジ相場"
        except (TypeError, ValueError):
            return "N/A"

    def _pvo_label(self, pvo) -> str:
        try:
            v = float(pvo)
            if v >= 10:
                return "出来高十分"
            if v >= 0:
                return "出来高普通"
            return "出来高不足"
        except (TypeError, ValueError):
            return "N/A"

    def _section_bot_status(self, result: BotAnalysisResult) -> str:
        icon, status_text = judge_bot_health(result)
        proc_icon = "✅" if result.is_alive else "❌"
        pid_str = f"{proc_icon} 稼働中 (PID: {result.pid})" if result.is_alive else f"{proc_icon} 停止"
        heartbeat_age = min(result.last_log_age_seconds, result.status_age_seconds)
        age_str = self._fmt_seconds_ago(heartbeat_age)
        age_judge = "(正常)" if heartbeat_age <= 120 else "(⚠️遅延)" if heartbeat_age <= 300 else "(❌停止)"
        log_str = result.log_file if result.log_file else "ログなし"

        lines = [
            f"■ {result.symbol} BOT: {icon} {status_text}",
            f"  プロセス     : {pid_str}",
            f"  最終更新     : {age_str} {age_judge}",
            f"  ログファイル : {log_str}",
            f"  エラー件数   : {result.error_count}件",
            f"  RATE LIMIT   : {result.rate_limit_count}回",
            f"  メインループエラー: {result.main_loop_error_count}件 (直近24h: {result.main_loop_error_recent_count}件)",
        ]
        return "\n".join(lines)

    def _section_trade_status(self, result: BotAnalysisResult) -> str:
        st = result.status
        if not st:
            return f"■ {result.symbol}\n  データなし（latest_status.json 未取得）"

        close  = st.get("close", "N/A")
        dc_h   = st.get("dc_h", "N/A")
        dc_l   = st.get("dc_l", "N/A")
        adx    = st.get("adx", "N/A")
        pvo    = st.get("pvo_val", "N/A")
        pnl    = st.get("pnl", 0)
        total  = st.get("total_pnl", 0)
        _bal_raw = st.get("balance") or st.get("unionAvailable")
        bal    = _bal_raw if _bal_raw is not None else None
        pos    = st.get("position_side", "NONE")
        dec    = st.get("decision", "NONE")

        try:
            pnl_str   = f"{float(pnl):+.2f}"
            total_str = f"{float(total):+.2f}"
        except (TypeError, ValueError):
            pnl_str   = str(pnl)
            total_str = str(total)

        dc_h_dist = self._fmt_pct_dist(close, dc_h)
        dc_l_dist = self._fmt_pct_dist(close, dc_l)

        lines = [
            f"■ {result.symbol}",
            f"  現在価格     : {self._fmt_price(close)} USD",
            f"  ポジション   : {pos}",
            f"  残高         : {self._fmt_price(bal) if bal is not None else '更新待ち（次回BOT再起動後）'} USD",
            f"  累計損益     : {total_str} USD",
            f"  みなし損益   : {pnl_str} USD",
            f"  DC上限(dc_h) : {self._fmt_price(dc_h)} USD  ({dc_h_dist} 距離)",
            f"  DC下限(dc_l) : {self._fmt_price(dc_l)} USD  ({dc_l_dist} 距離)",
            f"  ADX          : {self._fmt_price(adx)}  ({self._adx_label(adx)})",
            f"  PVO          : {self._fmt_price(pvo)}  ({self._pvo_label(pvo)})",
            f"  decision     : {dec}",
        ]
        return "\n".join(lines)

    def _section_signal_report(self, result: BotAnalysisResult) -> str:
        if result.no_log:
            return f"■ {result.symbol} シグナル統計\n  ログファイルなし（分析不可）"

        total_breakout = result.breakout_buy + result.breakout_sell
        entry_icon, entry_reason = judge_entry_zero(result)

        lines = [
            f"■ {result.symbol} シグナル統計（直近ログ全件）",
            f"  strategy_A BUY  : {result.strategy_a_buy}件",
            f"  strategy_A SELL : {result.strategy_a_sell}件",
            f"  strategy_A NONE : {result.strategy_a_none}件",
            f"  Breakout BUY    : {result.breakout_buy}件",
            f"  Breakout SELL   : {result.breakout_sell}件",
            f"  出来高不足(NG)  : {result.volume_filter_ng}件",
            f"  ADX不足(NG)     : {result.adx_filter_ng}件",
            f"  エントリー許可  : {result.entry_allowed}件",
            f"  エントリー見送り: {result.entry_skipped}件",
            f"  エントリー実行  : {result.entry_executed}件",
            f"",
            f"  エントリー判定: {entry_icon} {entry_reason}",
        ]
        return "\n".join(lines)

    def build_report(self, btc: BotAnalysisResult, xaut: BotAnalysisResult) -> str:
        now_jst = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S JST")
        sep1 = "=" * 50
        sep2 = "━" * 40

        # 総合評価
        btc_icon, btc_text = judge_bot_health(btc)
        xaut_icon, xaut_text = judge_bot_health(xaut)

        btc_entry_icon, btc_entry_reason = judge_entry_zero(btc)
        xaut_entry_icon, xaut_entry_reason = judge_entry_zero(xaut)

        overall_ok = (btc_icon == "✅" and xaut_icon == "✅")
        overall_text = "両BOTは期待通りに動作しています。" if overall_ok else "⚠️ 要確認事項があります。"

        # RATE LIMIT 同時発生チェック（簡易：件数比較）
        rate_limit_note = "なし（自動回復範囲内）"
        if btc.rate_limit_count > 0 and xaut.rate_limit_count > 0:
            rate_limit_note = f"両BOTで発生 (BTC:{btc.rate_limit_count}回 / XAUT:{xaut.rate_limit_count}回) — 同一APIキー共有による競合（自動回復）"

        report = f"""{sep1}
satosystem BOT 監視レポート
生成日時: {now_jst}
{sep1}

{sep2}
【1. BOT稼働状況】
{sep2}

{self._section_bot_status(btc)}

{self._section_bot_status(xaut)}

{sep2}
【2. トレード状況】
{sep2}

{self._section_trade_status(btc)}

{self._section_trade_status(xaut)}

{sep2}
【3. シグナル・フィルタ整合性レポート】
{sep2}

{self._section_signal_report(btc)}

{self._section_signal_report(xaut)}

■ 並行動作チェック
  RATE LIMIT同時発生: {rate_limit_note}

{sep2}
【総合評価】
{sep2}

{btc_icon} BTC BOT : {btc_text}
{xaut_icon} XAUT BOT: {xaut_text}

{overall_text}

エントリー判定:
  BTC : {btc_entry_icon} {btc_entry_reason}
  XAUT: {xaut_entry_icon} {xaut_entry_reason}

--
satosystem bot_monitor v{VERSION}"""
        return report


# ==============================================================
# GmailSender
# ==============================================================

class GmailSender:
    """Gmail SMTP SSL でメールを送信する"""

    def __init__(self, config_path: Path = DEFAULT_CONFIG_PATH):
        self.config_path = config_path
        self._config = self._load_config()

    def _load_config(self) -> dict:
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Gmail設定ファイルが見つかりません: {self.config_path}\n"
                f"  → {self.config_path}.example を参考に作成してください。"
            )
        with open(self.config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        required = ["gmail_address", "gmail_app_password", "notify_to"]
        for key in required:
            if not cfg.get(key):
                raise ValueError(f"設定ファイルに '{key}' が未設定です: {self.config_path}")

        return cfg

    @property
    def sender(self) -> str:
        return self._config["gmail_address"]

    @property
    def recipient(self) -> str:
        return self._config["notify_to"]

    @property
    def subject_prefix(self) -> str:
        return self._config.get("subject_prefix", "[satosystem]")

    @property
    def send_hour_jst(self) -> int:
        return int(self._config.get("send_hour_jst", DEFAULT_SEND_HOUR_JST))

    def send(self, subject: str, body: str) -> bool:
        """メールを送信する。成功時 True、失敗時 False。"""
        full_subject = f"{self.subject_prefix} {subject}"
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = full_subject
        msg["From"]    = self.sender
        msg["To"]      = self.recipient

        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
                smtp.login(self.sender, self._config["gmail_app_password"])
                smtp.sendmail(self.sender, self.recipient, msg.as_bytes())
            logger.info(f"メール送信成功: {full_subject} -> {self.recipient}")
            return True
        except smtplib.SMTPAuthenticationError:
            logger.error("Gmail 認証エラー: アプリパスワードを確認してください")
            return False
        except Exception as e:
            logger.error(f"メール送信失敗: {e}")
            return False

    def send_test(self) -> bool:
        """テストメールを送信する。"""
        now_jst = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S JST")
        subject = "テストメール"
        body = (
            f"satosystem bot_monitor からのテストメールです。\n\n"
            f"送信日時: {now_jst}\n"
            f"このメールが届いていれば Gmail 設定は正常です。\n\n"
            f"-- satosystem bot_monitor v{VERSION}"
        )
        return self.send(subject, body)


# ==============================================================
# BotMonitor — メインコントローラ
# ==============================================================

class BotMonitor:
    def __init__(self, config_path: Path = DEFAULT_CONFIG_PATH):
        self.config_path = config_path
        self.analyzer = LogAnalyzer()
        self.builder  = ReportBuilder()
        self._running = True

        # SIGTERM / SIGINT ハンドラ
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT,  self._handle_signal)

    def _handle_signal(self, signum, frame):
        logger.info(f"シグナル受信 ({signum})。クリーン終了します...")
        self._running = False

    def _build_subject(self, btc: BotAnalysisResult, xaut: BotAnalysisResult) -> str:
        btc_icon, _  = judge_bot_health(btc)
        xaut_icon, _ = judge_bot_health(xaut)
        date_str = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")

        if btc_icon == "❌" or xaut_icon == "❌":
            return f"[ALERT] BOT監視レポート {date_str}"
        if btc_icon == "⚠️" or xaut_icon == "⚠️":
            return f"[WARNING] BOT監視レポート {date_str}"
        return f"BOT監視レポート {date_str}"

    def run_once(self, dry_run: bool = False) -> None:
        """1回分析・送信する。"""
        logger.info("BOT分析開始...")
        btc  = self.analyzer.analyze_btc()
        xaut = self.analyzer.analyze_xaut()

        report  = self.builder.build_report(btc, xaut)
        subject = self._build_subject(btc, xaut)

        if dry_run:
            print(f"\n件名: [satosystem] {subject}")
            print("-" * 60)
            print(report)
            return

        sender = GmailSender(self.config_path)
        sender.send(subject, report)

    def run_loop(self) -> None:
        """毎日 JST send_hour 時にレポートを送信するループ。"""
        # send_hour を設定ファイルから取得
        try:
            sender_cfg = GmailSender(self.config_path)
            send_hour = sender_cfg.send_hour_jst
        except Exception:
            send_hour = DEFAULT_SEND_HOUR_JST

        logger.info(f"BOTモニター起動 — 毎日 {send_hour:02d}:00 JST にレポートを送信します")

        while self._running:
            now_jst  = datetime.now(JST)
            # 次回の送信時刻を計算
            next_send = now_jst.replace(hour=send_hour, minute=0, second=0, microsecond=0)
            if now_jst >= next_send:
                next_send += timedelta(days=1)

            wait_secs = (next_send - now_jst).total_seconds()
            logger.info(f"次回送信: {next_send.strftime('%Y-%m-%d %H:%M JST')} ({int(wait_secs)}秒後)")

            # 60秒ごとにウェイク（SIGINTに素早く反応するため）
            while self._running and wait_secs > 0:
                sleep_time = min(60, wait_secs)
                time.sleep(sleep_time)
                wait_secs -= sleep_time

            if not self._running:
                break

            try:
                self.run_once()
            except Exception as e:
                logger.error(f"run_once エラー: {e}")

        logger.info("BOTモニター終了")
        self._remove_pid()

    def _remove_pid(self):
        try:
            MONITOR_PID_FILE.unlink(missing_ok=True)
        except Exception:
            pass


# ==============================================================
# エントリーポイント
# ==============================================================

def main():
    parser = argparse.ArgumentParser(description="satosystem BOT 監視・メール送信プロセス")
    parser.add_argument("--send-now",    action="store_true", help="今すぐ1回分析・送信して終了")
    parser.add_argument("--dry-run",     action="store_true", help="送信せずレポートを標準出力に表示")
    parser.add_argument("--test-email",  action="store_true", help="テストメールを送信して終了")
    parser.add_argument("--config",      default=str(DEFAULT_CONFIG_PATH), help="設定ファイルパス")
    args = parser.parse_args()

    config_path = Path(args.config)

    # ログファイル設定（デーモンモード時）
    if not args.dry_run and not args.send_now and not args.test_email:
        MONITOR_PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        global logger
        logger = setup_logger(MONITOR_LOG_FILE)
        # PID ファイル書き込み
        with open(MONITOR_PID_FILE, "w") as f:
            f.write(str(os.getpid()))

    monitor = BotMonitor(config_path=config_path)

    if args.test_email:
        try:
            sender = GmailSender(config_path)
            ok = sender.send_test()
            sys.exit(0 if ok else 1)
        except FileNotFoundError as e:
            print(f"エラー: {e}")
            sys.exit(1)

    elif args.dry_run or args.send_now:
        try:
            monitor.run_once(dry_run=args.dry_run)
        except FileNotFoundError as e:
            if args.dry_run:
                # dry-run は設定ファイル不要
                monitor.run_once(dry_run=True)
            else:
                print(f"エラー: {e}")
                sys.exit(1)

    else:
        # デーモンモード
        try:
            monitor.run_loop()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
