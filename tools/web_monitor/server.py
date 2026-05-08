#!/usr/bin/env python3
"""
satosystem Web Monitor
======================
BOTの latest_status.json を読んでブラウザに表示するダッシュボード。

動作モード:
  --local   ホストPCのローカルJSONを直接読む（SSH不要）
  --host    ラズパイにSSH接続して取得する（デフォルト: raspberry_pi）

使い方:
  python3 tools/web_monitor/server.py --local
  python3 tools/web_monitor/server.py --host raspberry_pi --port 8080
"""

import argparse
import glob
import json
import os
import re
import subprocess
import sys
import threading
import time
import zipfile
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

# ──────────────────────────────────────────
#  設定
# ──────────────────────────────────────────
DEFAULT_SSH_HOST    = "raspberry_pi"
DEFAULT_PORT        = 8080
REMOTE_LOG_DIR      = "~/work/satosystem/src/logs"
REMOTE_LOG_DIR_XAUT = "~/work/satosystem/src/logs/xaut"
LOCAL_LOG_DIR       = os.path.join(
    os.path.dirname(__file__), "..", "..", "src", "logs"
)
LOCAL_LOG_DIR_XAUT  = os.path.join(
    os.path.dirname(__file__), "..", "..", "src", "logs", "xaut"
)
LATEST_STATUS_FILE  = "latest_status.json"
CACHE_TTL           = 30    # 秒: ステータスキャッシュ有効期限
MAX_CHART_CANDLES   = 180   # 240分足で約1ヶ月分
CANDLES_CACHE_TTL   = 300   # 秒: キャンドルキャッシュ有効期限 (5分)

# アセット別設定
ASSET_CONFIG = {
    "btc": {
        "label": "BTC/USDT",
        "local_log_dir": LOCAL_LOG_DIR,
        "remote_log_dir": REMOTE_LOG_DIR,
        "process_pattern": "python3 -u bot.py",
    },
    "xaut": {
        "label": "XAUT/USDT",
        "local_log_dir": LOCAL_LOG_DIR_XAUT,
        "remote_log_dir": REMOTE_LOG_DIR_XAUT,
        "process_pattern": "python3 -u bot.py --config config_xaut.ini",
    },
}

# ──────────────────────────────────────────
#  グローバルキャッシュ（アセット別）
# ──────────────────────────────────────────
_cache_lock = threading.Lock()
_caches = {
    "btc":  {"data": None, "timestamp": 0},
    "xaut": {"data": None, "timestamp": 0},
}
_ssh_host   = DEFAULT_SSH_HOST
_local_mode = False   # True = ローカルファイル直読み

_candles_lock  = threading.Lock()
_candles_caches = {
    "btc":  {"data": None, "timestamp": 0},
    "xaut": {"data": None, "timestamp": 0},
}


# ──────────────────────────────────────────
#  データ取得
# ──────────────────────────────────────────

def fetch_local(log_dir: str = None) -> dict:
    """ローカルの latest_status.json を直接読む"""
    log_dir = log_dir or LOCAL_LOG_DIR
    path = os.path.normpath(os.path.join(log_dir, LATEST_STATUS_FILE))
    if not os.path.exists(path):
        raise FileNotFoundError(f"latest_status.json が見つかりません: {path}")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    data["source"] = "local"
    return data


def fetch_remote(host: str, remote_dir: str = None) -> dict:
    """SSH 経由でラズパイの latest_status.json を取得"""
    remote_dir = remote_dir or REMOTE_LOG_DIR
    remote_path = f"{remote_dir}/{LATEST_STATUS_FILE}"
    cmd = f"cat {remote_path}"
    result = subprocess.run(
        ["ssh", host, cmd],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError(f"SSH failed: {result.stderr.strip()}")
    data = json.loads(result.stdout)
    data["source"] = "ssh"
    data["ssh_host"] = host
    return data


def fetch_process_status(host: str, process_pattern: str = "python3 -u bot.py") -> dict:
    """BOTプロセスの状態を SSH で取得（リモートモード用）"""
    # シングルクォート内でパターンを安全にエスケープ
    escaped = process_pattern.replace("'", "'\\''")
    cmd = (
        f"PID=$(pgrep -f '{escaped}' | head -1); "
        "if [ -n \"$PID\" ]; then "
        "  CPU=$(ps -p $PID -o %cpu --no-headers 2>/dev/null | tr -d ' '); "
        "  MEM=$(ps -p $PID -o %mem --no-headers 2>/dev/null | tr -d ' '); "
        "  STARTED=$(ps -p $PID -o lstart --no-headers 2>/dev/null | xargs); "
        "  echo \"pid=$PID cpu=$CPU mem=$MEM started=$STARTED\"; "
        "else echo 'pid='; fi"
    )
    try:
        result = subprocess.run(
            ["ssh", host, cmd], capture_output=True, text=True, timeout=8
        )
        import re
        m = re.match(
            r"pid=(\S*)\s*(?:cpu=(\S*)\s*mem=(\S*)\s*started=(.+))?",
            result.stdout.strip()
        )
        if m:
            return {
                "pid": m.group(1) or "",
                "cpu": m.group(2) or "",
                "mem": m.group(3) or "",
                "started": m.group(4) or "",
            }
    except Exception:
        pass
    return {"pid": "", "cpu": "", "mem": "", "started": ""}


def fetch_local_process_status(process_pattern: str = "python3 -u bot.py") -> dict:
    """ローカルの BOTプロセス状態を取得"""
    import re
    try:
        result = subprocess.run(
            ["pgrep", "-f", process_pattern],
            capture_output=True, text=True
        )
        pid = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
        if pid:
            cpu_r = subprocess.run(
                ["ps", "-p", pid, "-o", "%cpu,rss", "--no-headers"],
                capture_output=True, text=True
            )
            parts = cpu_r.stdout.strip().split()
            cpu = parts[0] if parts else ""
            mem_mb = f"{int(parts[1]) // 1024}MB" if len(parts) > 1 else ""
            return {"pid": pid, "cpu": cpu, "mem": mem_mb, "started": ""}
    except Exception:
        pass
    return {"pid": "", "cpu": "", "mem": "", "started": ""}


# ──────────────────────────────────────────
#  キャンドルデータ取得
# ──────────────────────────────────────────

def _read_log_file_safe(filepath: str) -> list:
    """不完全な JSON ログファイル（ボット稼働中でも）を安全に読む"""
    try:
        with open(filepath, "rb") as f:
            raw = f.read().decode("utf-8", errors="replace").rstrip()
        if not raw:
            return []
        if not raw.endswith("]"):
            # ボット稼働中は末尾の ] がない。最後の完全な } を探して補完する
            idx = raw.rfind("}")
            if idx < 0:
                return []
            raw = raw[: idx + 1] + "]"
            if not raw.startswith("["):
                raw = "[" + raw
        return json.loads(raw)
    except Exception:
        return []


# YYYYMMDDHHMMSS.json 形式（14桁数字）のみマッチ
_OHLCV_LOG_RE = re.compile(r"^\d{14}\.json$")
# YYYYMMDDHHMMSS_N.zip 形式（圧縮アーカイブ）のみマッチ
_ZIP_LOG_RE   = re.compile(r"^\d{14}_\d+\.zip$")


def _real_time_to_ts(rt: str) -> int:
    """real_time 文字列（例 '2026/03/06 10:00:00'）を Unix 秒に変換"""
    for fmt in ("%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M"):
        try:
            return int(datetime.strptime(rt, fmt).timestamp())
        except Exception:
            pass
    return 0


def _entries_to_candles(entries: list) -> list:
    """trade_data エントリリストをチャート用キャンドル形式に変換"""
    candles = []
    for td in entries:
        if not isinstance(td, dict):
            continue
        positions = td.get("positions") or {}
        if not isinstance(positions, dict):
            positions = {}
        # close_time / timestamp がなければ real_time から変換
        _ts = td.get("close_time") or td.get("timestamp")
        if _ts:
            _time = int(float(_ts))
        else:
            _time = _real_time_to_ts(td.get("real_time", ""))
        candles.append({
            "ts":           td.get("close_time_dt", td.get("real_time", "")),
            "time":         _time,
            "open":         float(td.get("open_price") or td.get("close_price") or 0),
            "high":         float(td.get("high_price") or 0),
            "high":         float(td.get("high_price") or 0),
            "low":          float(td.get("low_price") or 0),
            "close":        float(td.get("close_price") or 0),
            "decision":     str(td.get("decision") or ""),
            "side":         str(td.get("side") or ""),
            "position_side": positions.get("side", ""),
            "psar":         float(td.get("psar") or 0),
            "dc_h":         float(td.get("dc_h") or 0),
            "dc_l":         float(td.get("dc_l") or 0),
            "adx":          float(td.get("adx") or 0),
            "pvo_val":      float(td.get("pvo_val") or 0),
            "total_pnl":    float(td.get("total_profit_and_loss") or 0),
            "volume":       float(td.get("Volume") or td.get("volume") or 0),
            "stop_price":   float(td.get("stop_price") or 0),
            "pnl":          float(td.get("profit_and_loss") or 0),
            "position_qty": float(td.get("position_quantity") or 0),
            "volatility":   float(td.get("volatility") or 0),
        })
    return candles


def fetch_candles_local(max_candles: int = MAX_CHART_CANDLES, log_dir: str = None) -> list:
    """ローカルの logs/*.json / *_N.zip と latest_status.json からキャンドルデータを組み立てる"""
    log_dir = os.path.normpath(log_dir or LOCAL_LOG_DIR)
    # YYYYMMDDHHMMSS.json 形式（14桁数字）のファイルのみ
    files = sorted(
        [f for f in glob.glob(os.path.join(log_dir, "*.json"))
         if _OHLCV_LOG_RE.match(os.path.basename(f))],
        reverse=True,
    )
    candles: list = []
    for fpath in files:
        entries = _read_log_file_safe(fpath)
        candles.extend(_entries_to_candles(entries))
    # zip アーカイブからも読み込む（YYYYMMDDHHMMSS_N.zip 形式）– 最新 20 ファイルまで
    zip_files = sorted(
        [f for f in glob.glob(os.path.join(log_dir, "*.zip"))
         if _ZIP_LOG_RE.match(os.path.basename(f))],
        reverse=True,
    )
    for zpath in zip_files[:20]:
        try:
            with zipfile.ZipFile(zpath) as zf:
                for info in sorted(zf.infolist(), key=lambda i: i.filename, reverse=True):
                    if not _OHLCV_LOG_RE.match(info.filename):
                        continue
                    if info.file_size == 0:
                        continue
                    with zf.open(info.filename) as fp:
                        raw = fp.read().decode("utf-8", errors="replace").rstrip()
                    if not raw:
                        continue
                    if not raw.endswith("]"):
                        idx = raw.rfind("}")
                        if idx < 0:
                            continue
                        raw = raw[: idx + 1] + "]"
                        if not raw.startswith("["):
                            raw = "[" + raw
                    try:
                        entries = json.loads(raw)
                        candles.extend(_entries_to_candles(entries))
                    except Exception:
                        pass
        except Exception:
            pass
    # latest_status.json の candles も統合（BOT稼働中のリアルタイムデータ）
    ls_path = os.path.normpath(os.path.join(log_dir, LATEST_STATUS_FILE))
    if os.path.exists(ls_path):
        try:
            with open(ls_path, encoding="utf-8") as _f:
                ls_data = json.load(_f)
            ls_candles = ls_data.get("candles", [])
            if ls_candles:
                # 旧バージョンの logger.py は time/open がない場合がある
                for lc in ls_candles:
                    if not lc.get("time"):
                        ts_str = lc.get("ts", "")
                        lc["time"] = _real_time_to_ts(ts_str) if ts_str else 0
                    if "open" not in lc:
                        lc["open"] = lc.get("close", 0)
                candles.extend(ls_candles)
        except Exception:
            pass
    candles.sort(key=lambda c: c.get("time", 0))
    # same close_time の中で最後のエントリを使う（累積済みの真の4H OHLCVを取得するため）
    candle_map: dict = {}
    for c in candles:
        t = c.get("time", 0)
        if t > 0:
            candle_map[t] = c   # last wins
    unique: list = sorted(candle_map.values(), key=lambda c: c["time"])
    return unique[-max_candles:]


# RPi 側で実行する Python スクリプト（SSH モード用）
_REMOTE_CANDLE_SCRIPT = """
import json, glob, os, re, sys, zipfile
from datetime import datetime as _dt

log_dir = os.path.expanduser('~/work/satosystem/src/logs')
OHLCV_LOG_RE = re.compile(r'^\\d{14}\\.json$')
ZIP_LOG_RE   = re.compile(r'^\\d{14}_\\d+\\.zip$')

def _rt_to_ts(rt):
    for fmt in ('%Y/%m/%d %H:%M:%S', '%Y/%m/%d %H:%M'):
        try:
            return int(_dt.strptime(rt, fmt).timestamp())
        except Exception:
            pass
    return 0

def _td_to_candle(td):
    pos = td.get('positions') or {}
    if not isinstance(pos, dict):
        pos = {}
    _ts = td.get('close_time') or td.get('timestamp')
    _time = int(float(_ts)) if _ts else _rt_to_ts(td.get('real_time', ''))
    return {
        'ts':           td.get('close_time_dt', td.get('real_time', '')),
        'time':         _time,
        'open':         float(td.get('open_price') or td.get('close_price') or 0),
        'high':         float(td.get('high_price') or 0),
        'low':          float(td.get('low_price') or 0),
        'close':        float(td.get('close_price') or 0),
        'decision':     str(td.get('decision') or ''),
        'side':         str(td.get('side') or ''),
        'position_side': pos.get('side', ''),
        'psar':         float(td.get('psar') or 0),
        'dc_h':         float(td.get('dc_h') or 0),
        'dc_l':         float(td.get('dc_l') or 0),
        'adx':          float(td.get('adx') or 0),
        'pvo_val':      float(td.get('pvo_val') or 0),
        'total_pnl':    float(td.get('total_profit_and_loss') or 0),
        'volume':       float(td.get('Volume') or td.get('volume') or 0),
        'stop_price':   float(td.get('stop_price') or 0),
        'pnl':          float(td.get('profit_and_loss') or 0),
        'position_qty': float(td.get('position_quantity') or 0),
        'volatility':   float(td.get('volatility') or 0),
    }

def _parse_raw(raw):
    raw = raw.rstrip()
    if not raw:
        return []
    if not raw.endswith(']'):
        idx = raw.rfind('}')
        if idx < 0:
            return []
        raw = raw[:idx+1] + ']'
        if not raw.startswith('['):
            raw = '[' + raw
    try:
        return json.loads(raw)
    except Exception:
        return []

candles = []

# 直接 JSON ファイルを読む
files = sorted(
    [f for f in glob.glob(os.path.join(log_dir, '*.json'))
     if OHLCV_LOG_RE.match(os.path.basename(f))],
    reverse=True
)
for fpath in files:
    try:
        with open(fpath, 'rb') as fp:
            entries = _parse_raw(fp.read().decode('utf-8', errors='replace'))
        candles.extend(_td_to_candle(td) for td in entries if isinstance(td, dict))
    except Exception:
        pass

# zip アーカイブからも読み込む（YYYYMMDDHHMMSS_N.zip 形式）– 最新 20 ファイルまで
zip_files = sorted(
    [f for f in glob.glob(os.path.join(log_dir, '*.zip'))
     if ZIP_LOG_RE.match(os.path.basename(f))],
    reverse=True
)
for zpath in zip_files[:20]:
    try:
        with zipfile.ZipFile(zpath) as zf:
            for info in sorted(zf.infolist(), key=lambda i: i.filename, reverse=True):
                if not OHLCV_LOG_RE.match(info.filename):
                    continue
                if info.file_size == 0:
                    continue
                with zf.open(info.filename) as fp:
                    entries = _parse_raw(fp.read().decode('utf-8', errors='replace'))
                candles.extend(_td_to_candle(td) for td in entries if isinstance(td, dict))
    except Exception:
        pass

# latest_status.json の candles(リアルタイムデータ)も統合
ls_path = os.path.join(log_dir, 'latest_status.json')
if os.path.exists(ls_path):
    try:
        ls_data = json.load(open(ls_path, encoding='utf-8'))
        ls_candles = ls_data.get('candles', [])
        if ls_candles:
            for lc in ls_candles:
                if not lc.get('time'):
                    ts_str = lc.get('ts', '')
                    lc['time'] = _rt_to_ts(ts_str) if ts_str else 0
                if 'open' not in lc:
                    lc['open'] = lc.get('close', 0)
            candles.extend(ls_candles)
    except Exception:
        pass
candles.sort(key=lambda c: c.get('time', 0))
# same close_time の中で最後のエントリを使う（累積済みの真の4H OHLCVを取得するため）
candle_map = {}
for c in candles:
    t = c.get('time', 0)
    if t > 0:
        candle_map[t] = c   # last wins
unique = sorted(candle_map.values(), key=lambda c: c['time'])
print(json.dumps(unique[-180:]))
"""


def fetch_candles_remote(host: str, max_candles: int = MAX_CHART_CANDLES, remote_log_dir: str = None) -> list:
    """SSH 経由でラズパイの logs/*.json からキャンドルデータを取得"""
    log_dir_val = remote_log_dir or REMOTE_LOG_DIR
    script = _REMOTE_CANDLE_SCRIPT.replace(
        "log_dir = os.path.expanduser('~/work/satosystem/src/logs')",
        f"log_dir = os.path.expanduser('{log_dir_val}')"
    )
    result = subprocess.run(
        ["ssh", host, "python3"],
        input=script,
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return []
    return json.loads(result.stdout.strip())


def get_candles(asset: str = "btc") -> list:
    """キャッシュ付き: キャンドルデータを取得して返す"""
    cfg = ASSET_CONFIG.get(asset, ASSET_CONFIG["btc"])
    now = time.time()
    with _candles_lock:
        cache = _candles_caches[asset]
        if cache["data"] is not None and (now - cache["timestamp"]) < CANDLES_CACHE_TTL:
            return cache["data"]

    try:
        if _local_mode:
            data = fetch_candles_local(log_dir=cfg["local_log_dir"])
        else:
            data = fetch_candles_remote(_ssh_host, remote_log_dir=cfg["remote_log_dir"])
    except Exception:
        with _candles_lock:
            if _candles_caches[asset]["data"] is not None:
                return _candles_caches[asset]["data"]
        return []

    with _candles_lock:
        _candles_caches[asset]["data"] = data
        _candles_caches[asset]["timestamp"] = now
    return data


# ──────────────────────────────────────────
#  ステータスデータ取得
# ──────────────────────────────────────────

def get_status(asset: str = "btc") -> dict:
    cfg = ASSET_CONFIG.get(asset, ASSET_CONFIG["btc"])
    now = time.time()
    with _cache_lock:
        cache = _caches[asset]
        if cache["data"] and (now - cache["timestamp"]) < CACHE_TTL:
            cached = dict(cache["data"])
            cached["from_cache"] = True
            return cached

    try:
        if _local_mode:
            data = fetch_local(log_dir=cfg["local_log_dir"])
            proc = fetch_local_process_status(process_pattern=cfg["process_pattern"])
        else:
            data = fetch_remote(_ssh_host, remote_dir=cfg["remote_log_dir"])
            proc = fetch_process_status(_ssh_host, process_pattern=cfg["process_pattern"])
        data["process"]    = proc
        data["from_cache"] = False
        data["error"]      = None
        data["fetched_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        data["asset"]      = asset
    except Exception as e:
        with _cache_lock:
            if _caches[asset]["data"]:
                stale = dict(_caches[asset]["data"])
                stale["from_cache"]   = True
                stale["fetch_error"]  = str(e)
                return stale
        return {
            "error":      str(e),
            "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "from_cache": False,
            "asset":      asset,
        }

    with _cache_lock:
        _caches[asset]["data"]      = data
        _caches[asset]["timestamp"] = now
    return data



# ──────────────────────────────────────────
#  HTML テンプレート
# ──────────────────────────────────────────
HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>satosystem Dual Monitor</title>
<script src="https://unpkg.com/lightweight-charts@4.1.0/dist/lightweight-charts.standalone.production.js"></script>
<style>
:root{--bg:#0d1117;--card:#161b22;--card2:#1c2128;--border:#30363d;--text:#e6edf3;--muted:#8b949e;
--green:#3fb950;--red:#f85149;--yellow:#d29922;--blue:#58a6ff;--purple:#bc8cff;--gold:#f0b90b;--gold-dim:rgba(240,185,11,.15);}
*{box-sizing:border-box;margin:0;padding:0;}
html,body{height:100%;overflow:hidden;}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:var(--bg);color:var(--text);
display:flex;flex-direction:column;height:100vh;padding:6px 10px;gap:5px;}

/* Header */
.hdr{display:flex;align-items:center;gap:10px;flex-shrink:0;}
.hdr-logo{font-size:16px;font-weight:700;background:linear-gradient(135deg,var(--blue),var(--purple));
-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}
.hdr-r{margin-left:auto;font-size:10px;color:var(--muted);text-align:right;line-height:1.4;}
.badge{display:inline-flex;align-items:center;gap:3px;padding:1px 7px;border-radius:20px;font-size:10px;font-weight:600;}
.badge-g{background:rgba(63,185,80,.15);color:var(--green);border:1px solid rgba(63,185,80,.3);}
.badge-r{background:rgba(248,81,73,.15);color:var(--red);border:1px solid rgba(248,81,73,.3);}
.badge-gold{background:var(--gold-dim);color:var(--gold);border:1px solid rgba(240,185,11,.3);}
.dot{display:inline-block;width:6px;height:6px;border-radius:50%;}
.dot-g{background:var(--green);animation:pulse 2s infinite;}
.dot-r{background:var(--red);}
@keyframes pulse{0%,100%{opacity:1;}50%{opacity:.4;}}

/* Combined Summary Row */
.summary-row{display:grid;grid-template-columns:1fr auto 1fr;gap:6px;flex-shrink:0;}
.summary-divider{width:1px;background:var(--border);margin:4px 0;}

/* Dual Panel Layout */
.dual{display:grid;grid-template-columns:1fr 1fr;gap:6px;flex:1;min-height:0;}

/* Cards */
.card{background:var(--card);border:1px solid var(--border);border-radius:6px;padding:6px 8px;overflow:hidden;}
.card.chart-card{display:flex;flex-direction:column;min-height:0;}
.card-btc{border-left:2px solid var(--blue);}
.card-xaut{border-left:2px solid var(--gold);}
.ct{font-size:8px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin-bottom:3px;}
.cv{font-size:17px;font-weight:700;line-height:1;}
.cs{font-size:9px;color:var(--muted);margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}

/* KPI Grid inside each panel */
.kpi-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:4px;flex-shrink:0;}
.kpi-grid .card{padding:5px 7px;}

/* Colors */
.g{color:var(--green);}.r{color:var(--red);}.y{color:var(--yellow);}.b{color:var(--blue);}.m{color:var(--muted);}.gold{color:var(--gold);}

/* Indicator row */
.ind-bar{display:flex;gap:8px;flex-wrap:nowrap;flex-shrink:0;padding:3px 0 1px;border-top:1px solid var(--border);margin-top:3px;}
.ind{display:flex;flex-direction:column;gap:1px;}
.ind-lbl{font-size:8px;color:var(--muted);font-weight:600;text-transform:uppercase;letter-spacing:.03em;}
.ind-val{font-size:11px;font-weight:700;}

/* Meter */
.mtrk{height:4px;background:var(--border);border-radius:3px;overflow:hidden;margin-top:3px;}
.mfill{height:100%;border-radius:3px;transition:width .4s;}

/* Table */
.tbl{width:100%;border-collapse:collapse;font-size:9px;}
.tbl th{text-align:left;padding:2px 4px;color:var(--muted);font-size:8px;font-weight:600;border-bottom:1px solid var(--border);text-transform:uppercase;letter-spacing:.03em;}
.tbl td{padding:2px 4px;border-bottom:1px solid rgba(48,54,61,.3);font-variant-numeric:tabular-nums;white-space:nowrap;}
.tbl tr:last-child td{border-bottom:none;}

/* Error */
.err-item{color:var(--red);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:9px;}

/* Chart wrapper */
.chart-wrap{flex:1;min-height:0;position:relative;}
.spin{display:inline-block;width:10px;height:10px;border:2px solid var(--border);border-top-color:var(--blue);border-radius:50%;animation:sp .7s linear infinite;vertical-align:middle;margin-right:3px;}
@keyframes sp{to{transform:rotate(360deg);}}

/* Footer */
.footer{display:flex;align-items:center;gap:12px;flex-shrink:0;font-size:10px;color:var(--muted);padding:2px 0;}
.footer-pnl{font-size:14px;font-weight:700;}
</style>
</head>
<body>

<!-- HEADER -->
<div class="hdr">
  <span class="hdr-logo">⚡ satosystem Dual Monitor</span>
  <span id="btcBadge" style="flex-shrink:0;">—</span>
  <span id="xautBadge" style="flex-shrink:0;">—</span>
  <div class="hdr-r">
    <div id="refreshStatus"><span class="spin"></span>読み込み中...</div>
    <div id="nextRefresh"></div>
  </div>
</div>

<!-- DUAL PANEL -->
<div class="dual">
  <!-- ===== BTC Panel ===== -->
  <div style="display:flex;flex-direction:column;gap:5px;min-height:0;">
    <div class="ct" style="margin:0;font-size:10px;font-weight:700;color:var(--blue);">₿ BTC/USDT <span id="btcProcMeta" style="font-size:9px;color:var(--muted);font-weight:400;"></span></div>
    <div class="kpi-grid">
      <div class="card card-btc">
        <div class="ct">累計損益</div>
        <div class="cv" id="btc_valTotalPnl">—</div>
        <div class="cs" id="btc_valPnl"></div>
      </div>
      <div class="card card-btc">
        <div class="ct">ポジション</div>
        <div class="cv" id="btc_valPos">—</div>
        <div class="cs" id="btc_valPosDetail"></div>
      </div>
      <div class="card card-btc">
        <div class="ct">終値</div>
        <div class="cv b" id="btc_valClose">—</div>
        <div class="cs"><span class="y" id="btc_valHigh">—</span> / <span id="btc_valLow">—</span></div>
      </div>
      <div class="card card-btc">
        <div class="ct">シグナル</div>
        <div class="cv" id="btc_valSignal" style="font-size:13px;">—</div>
        <div class="cs" id="btc_valTs"></div>
      </div>
    </div>
    <div class="card chart-card card-btc" style="flex:1;min-height:0;">
      <div class="ct">ローソク足 <span id="btc_candleCount" style="font-size:8px;color:var(--muted);"></span></div>
      <div class="chart-wrap"><div id="btc_chartCandle" style="position:absolute;top:0;left:0;width:100%;height:100%;"></div></div>
      <div class="ind-bar">
        <div class="ind"><span class="ind-lbl">ADX</span><span class="ind-val" id="btc_indADX">—</span></div>
        <div class="ind"><span class="ind-lbl">PVO</span><span class="ind-val" id="btc_indPVO">—</span></div>
        <div class="ind"><span class="ind-lbl">DCH</span><span class="ind-val y" id="btc_indDCH">—</span></div>
        <div class="ind"><span class="ind-lbl">DCL</span><span class="ind-val b" id="btc_indDCL">—</span></div>
        <div class="ind"><span class="ind-lbl">PSAR</span><span class="ind-val m" id="btc_indPSAR">—</span></div>
        <div class="ind"><span class="ind-lbl">ボラ</span><span class="ind-val m" id="btc_valVola">—</span></div>
        <div class="ind"><span class="ind-lbl">出来高</span><span class="ind-val m" id="btc_indVol">—</span></div>
        <div class="ind"><span class="ind-lbl">SL</span><span class="ind-val m" id="btc_indStop">—</span></div>
      </div>
    </div>
    <div class="card card-btc" style="max-height:120px;overflow:auto;">
      <div class="ct">直近シグナル</div>
      <table class="tbl"><thead><tr><th>時刻</th><th>シグナル</th><th>終値</th><th>ADX</th><th>PVO</th><th>累計</th></tr></thead>
      <tbody id="btc_historyBody"></tbody></table>
      <div id="btc_errorSection" style="display:none;border-top:1px solid var(--border);padding-top:3px;margin-top:3px;">
        <div style="font-size:8px;color:var(--red);font-weight:600;">⚠ エラー</div>
        <div id="btc_errorBody"></div>
      </div>
    </div>
  </div>

  <!-- ===== XAUT Panel ===== -->
  <div style="display:flex;flex-direction:column;gap:5px;min-height:0;">
    <div class="ct" style="margin:0;font-size:10px;font-weight:700;color:var(--gold);">🏆 XAUT/USDT <span id="xautProcMeta" style="font-size:9px;color:var(--muted);font-weight:400;"></span></div>
    <div class="kpi-grid">
      <div class="card card-xaut">
        <div class="ct">累計損益</div>
        <div class="cv" id="xaut_valTotalPnl">—</div>
        <div class="cs" id="xaut_valPnl"></div>
      </div>
      <div class="card card-xaut">
        <div class="ct">ポジション</div>
        <div class="cv" id="xaut_valPos">—</div>
        <div class="cs" id="xaut_valPosDetail"></div>
      </div>
      <div class="card card-xaut">
        <div class="ct">終値</div>
        <div class="cv gold" id="xaut_valClose">—</div>
        <div class="cs"><span class="y" id="xaut_valHigh">—</span> / <span id="xaut_valLow">—</span></div>
      </div>
      <div class="card card-xaut">
        <div class="ct">シグナル</div>
        <div class="cv" id="xaut_valSignal" style="font-size:13px;">—</div>
        <div class="cs" id="xaut_valTs"></div>
      </div>
    </div>
    <div class="card chart-card card-xaut" style="flex:1;min-height:0;">
      <div class="ct">ローソク足 <span id="xaut_candleCount" style="font-size:8px;color:var(--muted);"></span></div>
      <div class="chart-wrap"><div id="xaut_chartCandle" style="position:absolute;top:0;left:0;width:100%;height:100%;"></div></div>
      <div class="ind-bar">
        <div class="ind"><span class="ind-lbl">ADX</span><span class="ind-val" id="xaut_indADX">—</span></div>
        <div class="ind"><span class="ind-lbl">PVO</span><span class="ind-val" id="xaut_indPVO">—</span></div>
        <div class="ind"><span class="ind-lbl">DCH</span><span class="ind-val y" id="xaut_indDCH">—</span></div>
        <div class="ind"><span class="ind-lbl">DCL</span><span class="ind-val b" id="xaut_indDCL">—</span></div>
        <div class="ind"><span class="ind-lbl">ChExit</span><span class="ind-val m" id="xaut_indPSAR">—</span></div>
        <div class="ind"><span class="ind-lbl">ボラ</span><span class="ind-val m" id="xaut_valVola">—</span></div>
        <div class="ind"><span class="ind-lbl">出来高</span><span class="ind-val m" id="xaut_indVol">—</span></div>
        <div class="ind"><span class="ind-lbl">SL</span><span class="ind-val m" id="xaut_indStop">—</span></div>
      </div>
    </div>
    <div class="card card-xaut" style="max-height:120px;overflow:auto;">
      <div class="ct">直近シグナル</div>
      <table class="tbl"><thead><tr><th>時刻</th><th>シグナル</th><th>終値</th><th>ADX</th><th>PVO</th><th>累計</th></tr></thead>
      <tbody id="xaut_historyBody"></tbody></table>
      <div id="xaut_errorSection" style="display:none;border-top:1px solid var(--border);padding-top:3px;margin-top:3px;">
        <div style="font-size:8px;color:var(--red);font-weight:600;">⚠ エラー</div>
        <div id="xaut_errorBody"></div>
      </div>
    </div>
  </div>
</div>

<!-- FOOTER -->
<div class="footer">
  <span>合計損益:</span>
  <span class="footer-pnl" id="combinedPnl">—</span>
  <span style="margin-left:auto;">BTC err: <span id="btc_errCount" class="g">0</span> &nbsp; XAUT err: <span id="xaut_errCount" class="g">0</span></span>
</div>

<script>
const REFRESH_INTERVAL = 30;
let countdown = REFRESH_INTERVAL;

// 各アセット用チャートオブジェクト
const charts = {};
['btc','xaut'].forEach(a => { charts[a] = {}; });

const _toJST = ts => new Date((ts + 9*3600) * 1000);
const _jstTickFmt = (ts, type) => {
  const d = _toJST(ts);
  const TM = LightweightCharts.TickMarkType;
  if(type===TM.Year) return d.getUTCFullYear()+'年';
  if(type===TM.Month) return (d.getUTCMonth()+1)+'月';
  if(type===TM.DayOfMonth) return d.getUTCDate()+'日';
  return String(d.getUTCHours()).padStart(2,'0')+':'+String(d.getUTCMinutes()).padStart(2,'0');
};
const _jstTimeFmt = ts => {
  const d = _toJST(ts);
  return d.getUTCFullYear()+'/'+String(d.getUTCMonth()+1).padStart(2,'0')+'/'+
         String(d.getUTCDate()).padStart(2,'0')+' '+
         String(d.getUTCHours()).padStart(2,'0')+':'+String(d.getUTCMinutes()).padStart(2,'0')+' JST';
};

function initChart(asset, colors){
  const wrap = document.getElementById(asset+'_chartCandle');
  const ch = LightweightCharts.createChart(wrap, {
    autoSize:true,
    layout:{background:{type:'solid',color:'#161b22'},textColor:'#8b949e',fontSize:9},
    grid:{vertLines:{color:'#30363d'},horzLines:{color:'#30363d'}},
    localization:{timeFormatter:_jstTimeFmt},
    timeScale:{timeVisible:true,secondsVisible:false,borderColor:'#30363d',tickMarkFormatter:_jstTickFmt},
    rightPriceScale:{borderColor:'#30363d'},
    crosshair:{mode:1},
  });
  charts[asset].chart = ch;
  charts[asset].candle = ch.addCandlestickSeries({
    upColor:colors.up, downColor:colors.down,
    borderUpColor:colors.up, borderDownColor:colors.down,
    wickUpColor:colors.up, wickDownColor:colors.down,
  });
  charts[asset].dch = ch.addLineSeries({color:'#d29922',lineWidth:1,lineStyle:2,priceLineVisible:false,lastValueVisible:false,title:'DCH'});
  charts[asset].dcl = ch.addLineSeries({color:'#58a6ff',lineWidth:1,lineStyle:2,priceLineVisible:false,lastValueVisible:false,title:'DCL'});
  charts[asset].psar = ch.addLineSeries({color:'#8b949e',lineWidth:1,lineStyle:3,priceLineVisible:false,lastValueVisible:false,title:'PSAR'});
  charts[asset].volume = ch.addHistogramSeries({
    color:'rgba(88,166,255,0.4)',priceFormat:{type:'volume'},
    priceScaleId:'vol',lastValueVisible:false,priceLineVisible:false,
  });
  ch.priceScale('vol').applyOptions({scaleMargins:{top:0.8,bottom:0}});
  charts[asset].stop = ch.addLineSeries({color:'#ff6b6b',lineWidth:1,lineStyle:2,priceLineVisible:false,lastValueVisible:false,title:'SL'});
}

function _mkLine(candles,key){
  const d=[];const s=new Set();
  candles.filter(c=>c.time>0&&c[key]>0).sort((a,b)=>a.time-b.time).forEach(c=>{
    if(!s.has(c.time)){s.add(c.time);d.push({time:c.time,value:c[key]});}
  }); return d;
}

function updateChart(asset, candles){
  const ch = charts[asset];
  if(!candles||!candles.length||!ch.candle) return;
  const seen=new Set();const ohlc=[];
  candles.filter(c=>c.time>0).sort((a,b)=>a.time-b.time).forEach(c=>{
    if(!seen.has(c.time)){seen.add(c.time);ohlc.push({time:c.time,open:c.open||c.close,high:c.high,low:c.low,close:c.close});}
  });
  if(!ohlc.length) return;
  ch.candle.setData(ohlc);
  ch.dch.setData(_mkLine(candles,'dc_h'));
  ch.dcl.setData(_mkLine(candles,'dc_l'));
  ch.psar.setData(_mkLine(candles,'psar'));
  if(ch.volume){
    const vSeen=new Set();const vols=[];
    candles.filter(c=>c.time>0&&c.volume>0).sort((a,b)=>a.time-b.time).forEach(c=>{
      if(!vSeen.has(c.time)){vSeen.add(c.time);
        vols.push({time:c.time,value:c.volume,color:c.close>=c.open?'rgba(63,185,80,0.45)':'rgba(248,81,73,0.45)'});}
    });
    ch.volume.setData(vols);
  }
  if(ch.stop) ch.stop.setData(_mkLine(candles,'stop_price'));
  const markers=[];
  candles.filter(c=>c.time>0&&c.decision&&c.decision.includes('ENTRY'))
    .sort((a,b)=>a.time-b.time).forEach(c=>{
      const isSell=(c.side==='SELL'||c.position_side==='SELL');
      markers.push({time:c.time,position:isSell?'aboveBar':'belowBar',
        color:isSell?'#f85149':'#3fb950',shape:isSell?'arrowDown':'arrowUp',
        text:(c.decision||'').replace('ENTRY_','').replace('ENTRY','E'),size:1});
    });
  ch.candle.setMarkers(markers);
}

function fmt(n,d=2){
  if(n===null||n===undefined||n==='') return '—';
  const v=parseFloat(n); return isNaN(v)?String(n):v.toLocaleString(undefined,{minimumFractionDigits:d,maximumFractionDigits:d});
}
function fmtPnl(val){
  const n=parseFloat(val);if(isNaN(n)) return '—';
  return (n>=0?'+':'')+n.toFixed(2)+' USD';
}
function pnlClass(val){const n=parseFloat(val);return n>0?'g':n<0?'r':'m';}

let _lastBtcPnl=0, _lastXautPnl=0;

function renderAsset(asset, d){
  const p = asset+'_';
  if(d.error){return;}
  const proc=d.process||{};
  const running=proc.pid&&proc.pid!=='';
  const badgeId=asset==='btc'?'btcBadge':'xautBadge';
  const badgeCls=asset==='xaut'?'badge-gold':'badge-g';
  document.getElementById(badgeId).innerHTML=running
    ?`<span class="badge ${badgeCls}"><span class="dot dot-g"></span>${asset.toUpperCase()} 稼働</span>`
    :`<span class="badge badge-r"><span class="dot dot-r"></span>${asset.toUpperCase()} 停止</span>`;
  const metaId=asset==='btc'?'btcProcMeta':'xautProcMeta';
  document.getElementById(metaId).textContent=running?`PID:${proc.pid} CPU:${proc.cpu}`:'';

  const l=d.latest||{};
  const tp=parseFloat(l.total_pnl);
  const tpEl=document.getElementById(p+'valTotalPnl');
  tpEl.textContent=isNaN(tp)?'—':fmtPnl(tp);
  tpEl.className='cv '+(isNaN(tp)?'m':pnlClass(tp));
  document.getElementById(p+'valPnl').textContent=isNaN(parseFloat(l.pnl))?'':`みなし: ${fmtPnl(l.pnl)}`;

  if(asset==='btc') _lastBtcPnl=tp||0; else _lastXautPnl=tp||0;

  const pos=l.position_side||l.pos||'NONE';
  const posEl=document.getElementById(p+'valPos');
  posEl.textContent=pos;posEl.className='cv '+(pos==='BUY'?'g':pos==='SELL'?'r':'m');
  const buyP=parseFloat(l.buy_price),stopP=parseFloat(l.stop);
  document.getElementById(p+'valPosDetail').textContent=(!isNaN(buyP)&&buyP>0)?`${buyP.toLocaleString(undefined,{maximumFractionDigits:2})} / SL:${stopP.toLocaleString(undefined,{maximumFractionDigits:2})}`:'';

  const close=parseFloat(l.close||0);
  document.getElementById(p+'valClose').textContent=close?close.toLocaleString(undefined,{maximumFractionDigits:2}):'—';
  document.getElementById(p+'valHigh').textContent=l.high?parseFloat(l.high).toLocaleString(undefined,{maximumFractionDigits:2}):'—';
  document.getElementById(p+'valLow').textContent=l.low?parseFloat(l.low).toLocaleString(undefined,{maximumFractionDigits:2}):'—';

  const dec=l.decision||'',side=l.side||'';
  const sigText=dec&&dec!=='None'?`${dec}→${side}`:(side&&side!=='None'?side:'NONE');
  const sigEl=document.getElementById(p+'valSignal');
  sigEl.textContent=sigText;sigEl.className='cv '+((dec.includes('ENTRY')||side==='BUY'||side==='SELL')?'g':'m');
  document.getElementById(p+'valTs').textContent=l.ts?l.ts.slice(5):'';

  const adx=parseFloat(l.adx||0);
  const adxEl=document.getElementById(p+'indADX');
  adxEl.textContent=adx?adx.toFixed(1):'—';adxEl.className='ind-val '+(adx>=25?'g':adx>0?'y':'m');
  document.getElementById(p+'indPVO').textContent=l.pvo_val!=null?parseFloat(l.pvo_val).toFixed(2):'—';
  document.getElementById(p+'indPSAR').textContent=l.psar?parseFloat(l.psar).toLocaleString(undefined,{maximumFractionDigits:2}):'—';
  document.getElementById(p+'indDCH').textContent=l.dc_h?parseFloat(l.dc_h).toLocaleString(undefined,{maximumFractionDigits:2}):'—';
  document.getElementById(p+'indDCL').textContent=l.dc_l?parseFloat(l.dc_l).toLocaleString(undefined,{maximumFractionDigits:2}):'—';
  document.getElementById(p+'valVola').textContent=l.volatility?parseFloat(l.volatility).toFixed(0):'—';
  document.getElementById(p+'indVol').textContent=l.volume&&parseFloat(l.volume)>0?Math.round(parseFloat(l.volume)).toLocaleString():'—';
  const stopVal=parseFloat(l.stop||l.stop_price||0);
  document.getElementById(p+'indStop').textContent=stopVal>0?stopVal.toLocaleString(undefined,{maximumFractionDigits:2}):'—';

  // history
  const tbody=document.getElementById(p+'historyBody');
  tbody.innerHTML='';
  (d.candles||[]).slice(-5).reverse().forEach(r=>{
    const tp2=parseFloat(r.total_pnl),adx2=parseFloat(r.adx||0),pvo2=parseFloat(r.pvo_val||0);
    const dec2=r.decision||'',sid2=r.position_side||r.side||'';
    const sig2=dec2&&dec2!=='None'?`${dec2}→${sid2}`:sid2||'—';
    const sCol=(dec2.includes('ENTRY')||sid2==='BUY'||sid2==='SELL')?'var(--green)':'var(--muted)';
    tbody.innerHTML+=`<tr>
      <td style="color:var(--muted)">${r.ts?r.ts.slice(5):''}</td>
      <td style="color:${sCol};font-weight:600">${sig2}</td>
      <td>${r.close?parseFloat(r.close).toLocaleString(undefined,{maximumFractionDigits:2}):'—'}</td>
      <td style="color:${adx2>=25?'var(--green)':'var(--yellow)'}">${adx2.toFixed(1)}</td>
      <td>${pvo2.toFixed(2)}</td>
      <td style="color:${tp2>=0?'var(--green)':'var(--red)'}">${fmtPnl(tp2)}</td>
    </tr>`;
  });

  // errors
  const ec=d.error_count||0;
  document.getElementById(p+'errCount').textContent=ec;
  document.getElementById(p+'errCount').className=ec>0?'r':'g';
  const errSec=document.getElementById(p+'errorSection');
  const errs=d.recent_errors||[];
  if(errs.length>0){
    errSec.style.display='';
    document.getElementById(p+'errorBody').innerHTML=errs.slice(-3).reverse()
      .map(e=>`<div class="err-item"><span style="color:var(--muted);margin-right:4px">${e.ts?e.ts.slice(5):''}</span>${e.msg||String(e)}</div>`).join('');
  } else errSec.style.display='none';
}

function updateCombinedPnl(){
  const total=_lastBtcPnl+_lastXautPnl;
  const el=document.getElementById('combinedPnl');
  el.textContent=fmtPnl(total);
  el.className='footer-pnl '+(total>=0?'g':'r');
}

async function fetchStatus(asset){
  try{
    const res=await fetch('/api/status/'+asset);
    const d=await res.json();
    renderAsset(asset,d);
    updateCombinedPnl();
  }catch(e){ console.warn(asset+' status error:',e); }
}

async function fetchCandles(asset){
  try{
    const res=await fetch('/api/candles/'+asset);
    if(!res.ok) return;
    const candles=await res.json();
    updateChart(asset,candles);
    const el=document.getElementById(asset+'_candleCount');
    if(el) el.textContent=candles.length+'件';
  }catch(e){ console.warn(asset+' candles error:',e); }
}

async function refreshAll(){
  document.getElementById('refreshStatus').innerHTML='<span class="spin"></span>更新中...';
  await Promise.all([fetchStatus('btc'),fetchStatus('xaut')]);
  const ts=new Date().toLocaleTimeString('ja-JP',{hour:'2-digit',minute:'2-digit',second:'2-digit'});
  document.getElementById('refreshStatus').textContent='取得: '+ts;
  countdown=REFRESH_INTERVAL;
}

// Init
initChart('btc',{up:'#3fb950',down:'#f85149'});
initChart('xaut',{up:'#f0b90b',down:'#e67e22'});
fetchCandles('btc');fetchCandles('xaut');
setInterval(()=>{fetchCandles('btc');fetchCandles('xaut');},300000);
refreshAll();
setInterval(()=>{
  countdown--;
  document.getElementById('nextRefresh').textContent='次回: '+countdown+'s';
  if(countdown<=0){countdown=REFRESH_INTERVAL;refreshAll();}
},1000);
</script>
</body>
</html>
"""




# ──────────────────────────────────────────
#  HTTP ハンドラ
# ──────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        # アクセスログを静かにする
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/":
            self._send(200, "text/html; charset=utf-8", HTML_TEMPLATE.encode("utf-8"))
        elif path in ("/api/status", "/api/status/btc"):
            self._send_json(get_status("btc"))
        elif path == "/api/status/xaut":
            self._send_json(get_status("xaut"))
        elif path in ("/api/candles", "/api/candles/btc"):
            self._send_json(get_candles("btc"))
        elif path == "/api/candles/xaut":
            self._send_json(get_candles("xaut"))
        else:
            self._send(404, "text/plain", b"Not Found")

    def _send_json(self, data):
        try:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self._send(200, "application/json; charset=utf-8", body)
        except BrokenPipeError:
            pass
        except Exception as e:
            try:
                body = json.dumps({"error": str(e)}).encode("utf-8")
                self._send(500, "application/json; charset=utf-8", body)
            except BrokenPipeError:
                pass

    def _send(self, code: int, ctype: str, body: bytes):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)


# ──────────────────────────────────────────
#  エントリポイント
# ──────────────────────────────────────────
def main():
    global _ssh_host, _local_mode

    parser = argparse.ArgumentParser(description="satosystem Web Monitor")
    parser.add_argument("--host", default=DEFAULT_SSH_HOST, help="SSH ホスト名 (default: raspberry_pi)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="リッスンポート (default: 8080)")
    parser.add_argument("--local", action="store_true", help="ローカルJSONを直接読む（SSH不要、ホストPC確認用）")
    args = parser.parse_args()

    _ssh_host   = args.host
    _local_mode = args.local

    if _local_mode:
        local_path = os.path.normpath(os.path.join(LOCAL_LOG_DIR, LATEST_STATUS_FILE))
        print(f"📂 ローカルモード: {local_path}")
        if not os.path.exists(local_path):
            print(f"⚠  latest_status.json が見つかりません。BOTを起動して生成してください。")
            print(f"   ダミーファイルを作成して起動継続します。")
    else:
        # 起動時に一度 SSH 疎通確認
        print(f"🔌 SSH接続確認中: {_ssh_host} ...")
        try:
            result = subprocess.run(
                ["ssh", "-o", "ConnectTimeout=5", _ssh_host, "echo ok"],
                capture_output=True, text=True, timeout=8
            )
            if result.stdout.strip() == "ok":
                print(f"✅ SSH OK")
            else:
                print(f"⚠  SSH レスポンス: {result.stdout.strip() or result.stderr.strip()}")
        except Exception as e:
            print(f"⚠  SSH 確認失敗: {e}  (起動は継続します)")

    server = HTTPServer(("0.0.0.0", args.port), Handler)
    mode_str = "ローカル" if _local_mode else f"SSH → {_ssh_host}"
    print(f"\n🚀 satosystem Web Monitor 起動")
    print(f"   ブラウザで開く: http://localhost:{args.port}")
    print(f"   データ取得先 : {mode_str}")
    print(f"   キャッシュTTL : {CACHE_TTL}秒")
    print(f"   停止: Ctrl+C\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n⏹  Monitor停止")
        server.shutdown()


if __name__ == "__main__":
    main()
