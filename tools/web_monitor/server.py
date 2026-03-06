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
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

# ──────────────────────────────────────────
#  設定
# ──────────────────────────────────────────
DEFAULT_SSH_HOST    = "raspberry_pi"
DEFAULT_PORT        = 8080
REMOTE_LOG_DIR      = "~/work/satosystem/src/logs"
LOCAL_LOG_DIR       = os.path.join(
    os.path.dirname(__file__), "..", "..", "src", "logs"
)
LATEST_STATUS_FILE  = "latest_status.json"
CACHE_TTL           = 30    # 秒: ステータスキャッシュ有効期限
MAX_CHART_CANDLES   = 180   # 240分足で約1ヶ月分
CANDLES_CACHE_TTL   = 300   # 秒: キャンドルキャッシュ有効期限 (5分)

# ──────────────────────────────────────────
#  グローバルキャッシュ
# ──────────────────────────────────────────
_cache_lock = threading.Lock()
_cache = {"data": None, "timestamp": 0}
_ssh_host   = DEFAULT_SSH_HOST
_local_mode = False   # True = ローカルファイル直読み

_candles_lock  = threading.Lock()
_candles_cache = {"data": None, "timestamp": 0}


# ──────────────────────────────────────────
#  データ取得
# ──────────────────────────────────────────

def fetch_local() -> dict:
    """ローカルの latest_status.json を直接読む"""
    path = os.path.normpath(os.path.join(LOCAL_LOG_DIR, LATEST_STATUS_FILE))
    if not os.path.exists(path):
        raise FileNotFoundError(f"latest_status.json が見つかりません: {path}")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    data["source"] = "local"
    return data


def fetch_remote(host: str) -> dict:
    """SSH 経由でラズパイの latest_status.json を取得"""
    remote_path = f"{REMOTE_LOG_DIR}/{LATEST_STATUS_FILE}"
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


def fetch_process_status(host: str) -> dict:
    """BOTプロセスの状態を SSH で取得（リモートモード用）"""
    cmd = (
        "PID=$(pgrep -f 'python3 -u bot.py' | head -1); "
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


def fetch_local_process_status() -> dict:
    """ローカルの BOTプロセス状態を取得"""
    import re
    try:
        result = subprocess.run(
            ["pgrep", "-f", "python3 -u bot.py"],
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


def _entries_to_candles(entries: list) -> list:
    """trade_data エントリリストをチャート用キャンドル形式に変換"""
    candles = []
    for td in entries:
        if not isinstance(td, dict):
            continue
        positions = td.get("positions") or {}
        if not isinstance(positions, dict):
            positions = {}
        candles.append({
            "ts":           td.get("close_time_dt", td.get("real_time", "")),
            "time":         int(td.get("close_time") or td.get("timestamp") or 0),
            "open":         float(td.get("open_price") or 0),
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
        })
    return candles


def fetch_candles_local(max_candles: int = MAX_CHART_CANDLES) -> list:
    """ローカルの logs/*.json からキャンドルデータを組み立てる"""
    log_dir = os.path.normpath(LOCAL_LOG_DIR)
    # YYYYMMDDHHMMSS.json 形式のファイルのみ（latest_status.json は除外）
    files = sorted(
        [f for f in glob.glob(os.path.join(log_dir, "????????*.json"))
         if "latest_status" not in os.path.basename(f)],
        reverse=True,
    )
    candles: list = []
    for fpath in files:
        entries = _read_log_file_safe(fpath)
        candles.extend(_entries_to_candles(entries))
        if len(candles) >= max_candles * 2:
            break
    candles.sort(key=lambda c: c["time"])
    seen: set = set()
    unique: list = []
    for c in candles:
        if c["time"] not in seen:
            seen.add(c["time"])
            unique.append(c)
    return unique[-max_candles:]


# RPi 側で実行する Python スクリプト（SSH モード用）
_REMOTE_CANDLE_SCRIPT = """
import json, glob, os, sys
log_dir = os.path.expanduser('~/work/satosystem/src/logs')
files = sorted(
    [f for f in glob.glob(os.path.join(log_dir, '????????*.json'))
     if 'latest_status' not in os.path.basename(f)],
    reverse=True
)
candles = []
for fpath in files:
    try:
        with open(fpath, 'rb') as fp:
            raw = fp.read().decode('utf-8', errors='replace').rstrip()
        if not raw:
            continue
        if not raw.endswith(']'):
            idx = raw.rfind('}')
            if idx < 0:
                continue
            raw = raw[:idx+1] + ']'
            if not raw.startswith('['):
                raw = '[' + raw
        entries = json.loads(raw)
        for td in entries:
            if not isinstance(td, dict):
                continue
            pos = td.get('positions') or {}
            if not isinstance(pos, dict):
                pos = {}
            candles.append({
                'ts':           td.get('close_time_dt', td.get('real_time', '')),
                'time':         int(td.get('close_time') or td.get('timestamp') or 0),
                'open':         float(td.get('open_price') or 0),
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
            })
    except Exception:
        pass
    if len(candles) >= 360:
        break
candles.sort(key=lambda c: c['time'])
seen = set()
unique = []
for c in candles:
    if c['time'] not in seen:
        seen.add(c['time'])
        unique.append(c)
print(json.dumps(unique[-180:]))
"""


def fetch_candles_remote(host: str, max_candles: int = MAX_CHART_CANDLES) -> list:
    """SSH 経由でラズパイの logs/*.json からキャンドルデータを取得"""
    result = subprocess.run(
        ["ssh", host, "python3"],
        input=_REMOTE_CANDLE_SCRIPT,
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return []
    return json.loads(result.stdout.strip())


def get_candles() -> list:
    """キャッシュ付き: キャンドルデータを取得して返す"""
    now = time.time()
    with _candles_lock:
        if _candles_cache["data"] is not None and (now - _candles_cache["timestamp"]) < CANDLES_CACHE_TTL:
            return _candles_cache["data"]

    try:
        data = fetch_candles_local() if _local_mode else fetch_candles_remote(_ssh_host)
    except Exception:
        with _candles_lock:
            if _candles_cache["data"] is not None:
                return _candles_cache["data"]
        return []

    with _candles_lock:
        _candles_cache["data"] = data
        _candles_cache["timestamp"] = now
    return data


# ──────────────────────────────────────────
#  ステータスデータ取得
# ──────────────────────────────────────────

def get_status() -> dict:
    now = time.time()
    with _cache_lock:
        if _cache["data"] and (now - _cache["timestamp"]) < CACHE_TTL:
            cached = dict(_cache["data"])
            cached["from_cache"] = True
            return cached

    try:
        if _local_mode:
            data = fetch_local()
            proc = fetch_local_process_status()
        else:
            data = fetch_remote(_ssh_host)
            proc = fetch_process_status(_ssh_host)
        data["process"]    = proc
        data["from_cache"] = False
        data["error"]      = None
        data["fetched_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        with _cache_lock:
            if _cache["data"]:
                stale = dict(_cache["data"])
                stale["from_cache"]   = True
                stale["fetch_error"]  = str(e)
                return stale
        return {
            "error":      str(e),
            "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "from_cache": False,
        }

    with _cache_lock:
        _cache["data"]      = data
        _cache["timestamp"] = now
    return data



# ──────────────────────────────────────────
#  HTML テンプレート
# ──────────────────────────────────────────
HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>satosystem BOT Monitor</title>
<script src="https://unpkg.com/lightweight-charts@4.1.0/dist/lightweight-charts.standalone.production.js"></script>
<style>
:root{--bg:#0d1117;--card:#161b22;--card2:#1c2128;--border:#30363d;--text:#e6edf3;--muted:#8b949e;--green:#3fb950;--red:#f85149;--yellow:#d29922;--blue:#58a6ff;--purple:#bc8cff;}
*{box-sizing:border-box;margin:0;padding:0;}
html,body{height:100%;overflow:hidden;}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:var(--bg);color:var(--text);display:flex;flex-direction:column;height:100vh;padding:8px 12px;gap:6px;}
/* Header */
.hdr{display:flex;align-items:center;gap:10px;flex-shrink:0;}
.hdr-logo{font-size:18px;font-weight:700;background:linear-gradient(135deg,var(--blue),var(--purple));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}
.hdr-r{margin-left:auto;font-size:11px;color:var(--muted);text-align:right;line-height:1.5;}
/* Badges */
.badge{display:inline-flex;align-items:center;gap:4px;padding:2px 8px;border-radius:20px;font-size:11px;font-weight:600;}
.badge-g{background:rgba(63,185,80,.15);color:var(--green);border:1px solid rgba(63,185,80,.3);}
.badge-r{background:rgba(248,81,73,.15);color:var(--red);border:1px solid rgba(248,81,73,.3);}
.dot{display:inline-block;width:7px;height:7px;border-radius:50%;}
.dot-g{background:var(--green);animation:pulse 2s infinite;}
.dot-r{background:var(--red);}
@keyframes pulse{0%,100%{opacity:1;}50%{opacity:.4;}}
/* Layout rows */
.row1{display:grid;grid-template-columns:repeat(8,1fr);gap:6px;flex-shrink:0;}
.row2{display:grid;grid-template-columns:1fr 1fr;gap:6px;flex:1;min-height:0;}
.row3{display:grid;grid-template-columns:1fr;gap:6px;flex-shrink:0;}
/* Cards */
.card{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:8px 10px;overflow:hidden;}
.card.chart-card{display:flex;flex-direction:column;min-height:0;}
.ct{font-size:9px;font-weight:600;letter-spacing:.07em;text-transform:uppercase;color:var(--muted);margin-bottom:4px;}
.cv{font-size:20px;font-weight:700;line-height:1;}
.cs{font-size:10px;color:var(--muted);margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
/* Colors */
.g{color:var(--green);}.r{color:var(--red);}.y{color:var(--yellow);}.b{color:var(--blue);}.m{color:var(--muted);}
/* Indicator row inside chart card */
.ind-bar{display:flex;gap:10px;flex-wrap:nowrap;flex-shrink:0;padding:4px 0 2px;border-top:1px solid var(--border);margin-top:4px;}
.ind{display:flex;flex-direction:column;gap:1px;}
.ind-lbl{font-size:9px;color:var(--muted);font-weight:600;text-transform:uppercase;letter-spacing:.04em;}
.ind-val{font-size:13px;font-weight:700;}
/* Meter */
.mtrk{height:5px;background:var(--border);border-radius:3px;overflow:hidden;margin-top:4px;}
.mfill{height:100%;border-radius:3px;transition:width .4s;}
/* Table */
.tbl{width:100%;border-collapse:collapse;font-size:10px;}
.tbl th{text-align:left;padding:3px 6px;color:var(--muted);font-size:9px;font-weight:600;border-bottom:1px solid var(--border);text-transform:uppercase;letter-spacing:.04em;}
.tbl td{padding:3px 6px;border-bottom:1px solid rgba(48,54,61,.3);font-variant-numeric:tabular-nums;white-space:nowrap;}
.tbl tr:last-child td{border-bottom:none;}
/* Error / BT inline */
.inline-section{display:flex;gap:6px;align-items:flex-start;font-size:10px;}
.err-item{color:var(--red);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.bt-items{display:flex;gap:8px;flex-wrap:wrap;}
.bt-item{display:flex;flex-direction:column;}
.bt-lbl{font-size:9px;color:var(--muted);text-transform:uppercase;}
.bt-val{font-size:13px;font-weight:700;}
/* Chart wrapper */
.chart-wrap{flex:1;min-height:0;position:relative;}
.spin{display:inline-block;width:11px;height:11px;border:2px solid var(--border);border-top-color:var(--blue);border-radius:50%;animation:sp .7s linear infinite;vertical-align:middle;margin-right:3px;}
@keyframes sp{to{transform:rotate(360deg);}}
canvas{position:absolute;top:0;left:0;width:100%!important;height:100%!important;}
</style>
</head>
<body>

<!-- HEADER -->
<div class="hdr">
  <span class="hdr-logo">⚡ satosystem</span>
  <span id="procBadge" style="flex-shrink:0;">—</span>
  <span id="procMeta" style="font-size:10px;color:var(--muted);"></span>
  <div class="hdr-r">
    <div id="refreshStatus"><span class="spin"></span>読み込み中...</div>
    <div id="nextRefresh"></div>
  </div>
</div>

<!-- ROW1: 8カラム KPI -->
<div class="row1">
  <div class="card">
    <div class="ct">累計損益</div>
    <div class="cv" id="valTotalPnl">—</div>
    <div class="cs" id="valPnl"></div>
  </div>
  <div class="card">
    <div class="ct">ポジション</div>
    <div class="cv" id="valPos">—</div>
    <div class="cs" id="valPosDetail"></div>
  </div>
  <div class="card">
    <div class="ct">BTC 終値</div>
    <div class="cv b" id="valClose">—</div>
    <div class="cs"><span class="y" id="valHigh">—</span> / <span id="valLow">—</span></div>
  </div>
  <div class="card">
    <div class="ct">シグナル</div>
    <div class="cv" id="valSignal" style="font-size:15px;">—</div>
    <div class="cs" id="valTs"></div>
  </div>
  <div class="card">
    <div class="ct">ADX</div>
    <div class="cv" id="indADX">—</div>
    <div class="cs">≥25 トレンド</div>
  </div>
  <div class="card">
    <div class="ct">PVO / PSAR</div>
    <div class="cv" id="indPVO" style="font-size:16px;">—</div>
    <div class="cs" id="indPSAR">—</div>
  </div>
  <div class="card">
    <div class="ct">DCH / DCL</div>
    <div class="cv" id="indDCH" style="font-size:15px;color:var(--yellow);">—</div>
    <div class="cs b" id="indDCL">—</div>
  </div>
  <div class="card">
    <div class="ct">ボラ / エラー</div>
    <div class="cv" id="valVola">—</div>
    <div class="mtrk"><div class="mfill" id="volaMeter" style="width:0%;background:var(--green);"></div></div>
    <div class="cs"><span id="errCount" class="g">0</span> errs &nbsp;<span id="indPosSize" class="m"></span></div>
  </div>
</div>

<!-- ROW2: チャート(左) + 履歴テーブル(右) -->
<div class="row2">
  <div class="card chart-card">
    <div class="ct">BTC ローソク足（最大1ヶ月）<span id="candleCount" style="margin-left:6px;font-size:9px;color:var(--muted)"></span></div>
    <div class="chart-wrap"><div id="chartCandle" style="position:absolute;top:0;left:0;width:100%;height:100%;"></div></div>
    <div class="ind-bar">
      <div class="ind"><span class="ind-lbl">累計損益</span><span class="ind-val" id="indTotalPnl2">—</span></div>
      <div class="ind"><span class="ind-lbl">出来高</span><span class="ind-val m" id="indVol">—</span></div>
      <div class="ind"><span class="ind-lbl">ポジSZ</span><span class="ind-val m" id="indPS2">—</span></div>
    </div>
  </div>
  <div class="card chart-card">
    <div class="ct">直近シグナル履歴（最新 5件）</div>
    <div style="overflow:auto;flex:1;min-height:0;">
      <table class="tbl">
        <thead><tr>
          <th>時刻</th><th>シグナル</th><th>終値</th><th>ポジ</th>
          <th>ADX</th><th>PVO</th><th>みなし</th><th>累計</th>
        </tr></thead>
        <tbody id="historyBody"></tbody>
      </table>
    </div>
    <!-- BT結果 / エラー -->
    <div id="btSection" style="display:none;border-top:1px solid var(--border);padding-top:5px;margin-top:5px;">
      <div style="font-size:9px;color:var(--purple);font-weight:600;margin-bottom:4px;">📊 バックテスト結果</div>
      <div class="bt-items" id="btResult"></div>
    </div>
    <div id="errorSection" style="display:none;border-top:1px solid var(--border);padding-top:4px;margin-top:4px;">
      <div style="font-size:9px;color:var(--red);font-weight:600;margin-bottom:2px;">⚠ 直近エラー</div>
      <div id="errorBody"></div>
    </div>
  </div>
</div>

<script>
const REFRESH_INTERVAL = 30;
let countdown = REFRESH_INTERVAL;
let lwChart, lwCandle, lwDCH, lwDCL, lwPSAR;

function initCandleChart(){
  const wrap = document.getElementById('chartCandle');
  lwChart = LightweightCharts.createChart(wrap, {
    autoSize: true,
    layout:{ background:{type:'solid',color:'#161b22'}, textColor:'#8b949e', fontSize:10 },
    grid:{ vertLines:{color:'#30363d'}, horzLines:{color:'#30363d'} },
    timeScale:{ timeVisible:true, secondsVisible:false, borderColor:'#30363d' },
    rightPriceScale:{ borderColor:'#30363d' },
    crosshair:{ mode:1 },
  });
  lwCandle = lwChart.addCandlestickSeries({
    upColor:'#3fb950', downColor:'#f85149',
    borderUpColor:'#3fb950', borderDownColor:'#f85149',
    wickUpColor:'#3fb950', wickDownColor:'#f85149',
  });
  lwDCH = lwChart.addLineSeries({ color:'#d29922', lineWidth:1, lineStyle:2,
    priceLineVisible:false, lastValueVisible:false, title:'DCH' });
  lwDCL = lwChart.addLineSeries({ color:'#58a6ff', lineWidth:1, lineStyle:2,
    priceLineVisible:false, lastValueVisible:false, title:'DCL' });
  lwPSAR = lwChart.addLineSeries({ color:'#8b949e', lineWidth:1, lineStyle:3,
    priceLineVisible:false, lastValueVisible:false, title:'PSAR' });
}

function _mkLine(candles, key){
  const d=[]; const s=new Set();
  candles.filter(c=>c.time>0 && c[key]>0).sort((a,b)=>a.time-b.time).forEach(c=>{
    if(!s.has(c.time)){ s.add(c.time); d.push({time:c.time, value:c[key]}); }
  });
  return d;
}

function updateCandleChart(candles){
  if(!candles||!candles.length||!lwCandle) return;
  const seen=new Set(); const ohlc=[];
  candles.filter(c=>c.time>0).sort((a,b)=>a.time-b.time).forEach(c=>{
    if(!seen.has(c.time)){
      seen.add(c.time);
      ohlc.push({time:c.time, open:c.open||c.close, high:c.high, low:c.low, close:c.close});
    }
  });
  if(!ohlc.length) return;
  lwCandle.setData(ohlc);
  lwDCH.setData(_mkLine(candles,'dc_h'));
  lwDCL.setData(_mkLine(candles,'dc_l'));
  lwPSAR.setData(_mkLine(candles,'psar'));
  // エントリーシグナルマーカー
  const markers=[];
  candles.filter(c=>c.time>0&&c.decision&&c.decision.includes('ENTRY'))
    .sort((a,b)=>a.time-b.time).forEach(c=>{
      const isSell=(c.side==='SELL'||c.position_side==='SELL');
      markers.push({time:c.time,
        position:isSell?'aboveBar':'belowBar',
        color:isSell?'#f85149':'#3fb950',
        shape:isSell?'arrowDown':'arrowUp',
        text:(c.decision||'').replace('ENTRY_','').replace('ENTRY','E'), size:1});
    });
  lwCandle.setMarkers(markers);
}

async function fetchCandles(){
  try{
    const res=await fetch('/api/candles');
    if(!res.ok) return;
    const candles=await res.json();
    updateCandleChart(candles);
    const el=document.getElementById('candleCount');
    if(el) el.textContent=candles.length+'件';
  }catch(e){ console.warn('candles fetch error:',e); }
}

function fmt(n,d=2){
  if(n===null||n===undefined||n==='') return '—';
  const v=parseFloat(n); return isNaN(v)?String(n):v.toLocaleString(undefined,{minimumFractionDigits:d,maximumFractionDigits:d});
}
function fmtPnl(val){
  const n=parseInt(val); if(isNaN(n)) return '—';
  return (n>=0?'+':'')+n.toLocaleString()+' USD';
}
function pnlClass(val){const n=parseInt(val);return n>0?'g':n<0?'r':'m';}

function render(d){
  if(d.error){
    document.getElementById('refreshStatus').innerHTML=`<span style="color:var(--red)">⚠ ${d.error}</span>`;
    return;
  }
  const cache=d.from_cache?' <span style="color:var(--muted)">(cache)</span>':'';
  document.getElementById('refreshStatus').innerHTML=`取得: ${(d.fetched_at||d.updated_at||'').slice(5)}${cache}`;

  const proc=d.process||{};
  const running=proc.pid&&proc.pid!=='';
  document.getElementById('procBadge').innerHTML=running
    ?`<span class="badge badge-g"><span class="dot dot-g"></span>稼働中</span>`
    :`<span class="badge badge-r"><span class="dot dot-r"></span>停止中</span>`;
  document.getElementById('procMeta').textContent=running?`PID ${proc.pid} CPU ${proc.cpu} MEM ${proc.mem}`:'';

  const l=d.latest||{};

  // 損益
  const tp=parseInt(l.total_pnl);
  const tpEl=document.getElementById('valTotalPnl');
  tpEl.textContent=isNaN(tp)?'—':fmtPnl(tp);
  tpEl.className='cv '+(isNaN(tp)?'m':pnlClass(tp));
  document.getElementById('valPnl').textContent=isNaN(parseInt(l.pnl))?'':`みなし: ${fmtPnl(l.pnl)}`;
  document.getElementById('indTotalPnl2').textContent=isNaN(tp)?'—':fmtPnl(tp);
  document.getElementById('indTotalPnl2').className='ind-val '+(isNaN(tp)?'m':pnlClass(tp));

  // ポジション
  const pos=l.position_side||l.pos||'NONE';
  const posEl=document.getElementById('valPos');
  posEl.textContent=pos; posEl.className='cv '+(pos==='BUY'?'g':pos==='SELL'?'r':'m');
  const buyP=parseInt(l.buy_price),stopP=parseInt(l.stop);
  document.getElementById('valPosDetail').textContent=(!isNaN(buyP)&&buyP>0)?`${buyP.toLocaleString()} / SL:${stopP.toLocaleString()}`:'';

  // BTC
  const close=parseFloat(l.close||0);
  document.getElementById('valClose').textContent=close?close.toLocaleString():'—';
  document.getElementById('valHigh').textContent=l.high?parseInt(l.high).toLocaleString():'—';
  document.getElementById('valLow').textContent=l.low?parseInt(l.low).toLocaleString():'—';

  // シグナル
  const dec=l.decision||'',side=l.side||'';
  const sigText=dec&&dec!=='None'?`${dec}→${side}`:(side&&side!=='None'?side:'NONE');
  const sigEl=document.getElementById('valSignal');
  sigEl.textContent=sigText; sigEl.className='cv '+((dec.includes('ENTRY')||side==='BUY'||side==='SELL')?'g':'m');
  document.getElementById('valTs').textContent=l.ts?l.ts.slice(5):'';

  // 指標
  const adx=parseFloat(l.adx||0);
  const adxEl=document.getElementById('indADX');
  adxEl.textContent=adx?adx.toFixed(1):'—'; adxEl.className='cv '+(adx>=25?'g':adx>0?'y':'m');
  document.getElementById('indPVO').textContent=l.pvo_val!=null?parseFloat(l.pvo_val).toFixed(2):'—';
  document.getElementById('indPSAR').textContent=l.psar?'PSAR '+parseInt(l.psar).toLocaleString():'—';
  document.getElementById('indDCH').textContent=l.dc_h?parseInt(l.dc_h).toLocaleString():'—';
  document.getElementById('indDCL').textContent=l.dc_l?parseInt(l.dc_l).toLocaleString():'—';
  const psz=l.position_size!=null?parseFloat(l.position_size).toFixed(4):'—';
  document.getElementById('indPosSize').textContent='sz:'+psz;
  document.getElementById('indPS2').textContent=psz;

  // ボラ
  const vola=parseFloat(l.volatility||0);
  document.getElementById('valVola').textContent=vola.toFixed(0);
  const vRatio=Math.min(vola/2500,1);
  const mEl=document.getElementById('volaMeter');
  mEl.style.width=(vRatio*100)+'%';
  let vc='var(--green)';
  if(vola>=2500)vc='var(--red)'; else if(vola>=2000)vc='var(--yellow)';
  mEl.style.background=vc;

  // 出来高
  document.getElementById('indVol').textContent=fmt(l.volume,0);

  // エラー数
  const ec=d.error_count||0;
  const ecEl=document.getElementById('errCount');
  ecEl.textContent=ec; ecEl.className=ec>0?'r':'g';

  // ローソク足チャート（latest_status.json の candles でリアルタイム更新）
  if(d.candles&&d.candles.length>0) updateCandleChart(d.candles);

  // 履歴 (最新5件)
  const tbody=document.getElementById('historyBody');
  tbody.innerHTML='';
  (d.candles||[]).slice(-5).reverse().forEach(r=>{
    const pn=parseInt(r.pnl),tp2=parseInt(r.total_pnl);
    const adx2=parseFloat(r.adx||0),pvo2=parseFloat(r.pvo_val||0);
    const dec2=r.decision||'',sid2=r.position_side||r.side||'';
    const sig2=dec2&&dec2!=='None'?`${dec2}→${sid2}`:sid2||'—';
    const sCol=(dec2.includes('ENTRY')||sid2==='BUY'||sid2==='SELL')?'var(--green)':'var(--muted)';
    const pCol=r.position_side==='BUY'?'var(--green)':r.position_side==='SELL'?'var(--red)':'var(--muted)';
    tbody.innerHTML+=`<tr>
      <td style="color:var(--muted)">${r.ts?r.ts.slice(5):''}</td>
      <td style="color:${sCol};font-weight:600">${sig2}</td>
      <td>${r.close?parseInt(r.close).toLocaleString():'—'}</td>
      <td style="color:${pCol};font-weight:600">${r.position_side||r.side||'—'}</td>
      <td style="color:${adx2>=25?'var(--green)':'var(--yellow)'}">${adx2.toFixed(1)}</td>
      <td>${pvo2.toFixed(2)}</td>
      <td style="color:${pn>=0?'var(--green)':'var(--red)'}">${fmtPnl(pn)}</td>
      <td style="color:${tp2>=0?'var(--green)':'var(--red)'}">${fmtPnl(tp2)}</td>
    </tr>`;
  });

  // バックテスト
  const bt=d.backtest_result;
  const btSec=document.getElementById('btSection');
  if(bt){
    btSec.style.display='';
    const items=[['損益','total_pnl','USD'],['勝率','win_rate','%'],['取引数','trades',''],['Sharpe','sharpe',''],['MaxDD','max_drawdown_pct','%'],['PF','profit_factor','']];
    document.getElementById('btResult').innerHTML=items.map(([lb,k,u])=>{
      const v=bt[k]!=null?bt[k]:'—';
      const vf=typeof v==='number'?(Number.isInteger(v)?v.toLocaleString():v.toFixed(2))+(u?' '+u:''):'—';
      const c=k.includes('pnl')||k==='win_rate'?(parseFloat(v)||0)>=0?'g':'r':'b';
      return `<div class="bt-item"><div class="bt-lbl">${lb}</div><div class="bt-val ${c}">${vf}</div></div>`;
    }).join('');
  } else btSec.style.display='none';

  // エラー詳細
  const errSec=document.getElementById('errorSection');
  const errs=d.recent_errors||[];
  if(errs.length>0){
    errSec.style.display='';
    document.getElementById('errorBody').innerHTML=errs.slice(-3).reverse()
      .map(e=>`<div class="err-item"><span style="color:var(--muted);margin-right:6px">${e.ts?e.ts.slice(5):''}</span>${e.msg||String(e)}</div>`).join('');
  } else errSec.style.display='none';
}

async function refresh(){
  document.getElementById('refreshStatus').innerHTML='<span class="spin"></span>更新中...';
  try{
    const res=await fetch('/api/status');
    render(await res.json());
  }catch(e){
    document.getElementById('refreshStatus').innerHTML=`<span style="color:var(--red)">⚠ ${e.message}</span>`;
  }
  countdown=REFRESH_INTERVAL;
}

setInterval(()=>{
  countdown--;
  document.getElementById('nextRefresh').textContent=`次回: ${countdown}s`;
  if(countdown<=0){countdown=REFRESH_INTERVAL;refresh();}
},1000);

initCandleChart();
fetchCandles();                        // 初回: ログファイルから最大1ヶ月分取得
setInterval(fetchCandles, 300000);     // 5分毎にキャンドル更新
refresh();                             // 30秒毎のステータス更新も開始
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
        elif path == "/api/status":
            try:
                data = get_status()
                body = json.dumps(data, ensure_ascii=False).encode("utf-8")
                self._send(200, "application/json; charset=utf-8", body)
            except Exception as e:
                body = json.dumps({"error": str(e)}).encode("utf-8")
                self._send(500, "application/json; charset=utf-8", body)
        elif path == "/api/candles":
            try:
                candles = get_candles()
                body = json.dumps(candles, ensure_ascii=False).encode("utf-8")
                self._send(200, "application/json; charset=utf-8", body)
            except Exception as e:
                body = json.dumps({"error": str(e)}).encode("utf-8")
                self._send(500, "application/json; charset=utf-8", body)
        else:
            self._send(404, "text/plain", b"Not Found")

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
