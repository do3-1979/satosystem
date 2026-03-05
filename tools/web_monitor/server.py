#!/usr/bin/env python3
"""
satosystem Web Monitor
======================
ホストPC上で動かすWeb監視ダッシュボード。
SSH経由でラズパイのBOTログを取得してブラウザに表示する。

ラズパイへの負荷配慮:
  - tail -n 300 で最新行のみ取得
  - 30秒キャッシュ (同期間の重複SSH接続を防止)
  - SSH timeout 8秒

使い方:
  python3 tools/web_monitor/server.py
  python3 tools/web_monitor/server.py --host raspberry_pi --port 8080
"""

import argparse
import json
import os
import re
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

# ──────────────────────────────────────────
#  設定
# ──────────────────────────────────────────
DEFAULT_SSH_HOST = "raspberry_pi"
DEFAULT_PORT = 8080
LOG_DIR = "~/work/satosystem/src/logs"
CACHE_TTL = 30          # 秒: キャッシュ有効期限
LOG_TAIL_LINES = 500    # ラズパイから取得する最新行数


# ──────────────────────────────────────────
#  グローバルキャッシュ
# ──────────────────────────────────────────
_cache_lock = threading.Lock()
_cache = {
    "data": None,
    "timestamp": 0,
}
_ssh_host = DEFAULT_SSH_HOST


# ──────────────────────────────────────────
#  SSH経由ログ取得
# ──────────────────────────────────────────
def fetch_log_via_ssh(host: str):
    """
    ラズパイのログファイルを SSH 経由で取得する。
    負荷軽減のため tail -n TAIL_LINES のみ取得。
    """
    cmd = (
        f"LOGFILE=$(ls -t {LOG_DIR}/*.log 2>/dev/null | head -1); "
        f"if [ -n \"$LOGFILE\" ]; then "
        f"  echo \"__LOGFILE__:$LOGFILE\"; "
        f"  tail -n {LOG_TAIL_LINES} \"$LOGFILE\"; "
        f"fi"
    )
    result = subprocess.run(
        ["ssh", host, cmd],
        capture_output=True,
        text=True,
        timeout=8,
    )
    if result.returncode != 0:
        raise RuntimeError(f"SSH failed: {result.stderr.strip()}")
    return result.stdout


def fetch_process_status(host: str) -> dict:
    """BOTプロセスの状態を取得する（CPU / MEM / PID / 起動時刻）"""
    cmd = (
        "PID=$(pgrep -f 'python3.*bot.py' | head -1); "
        "if [ -n \"$PID\" ]; then "
        "  CPU=$(ps -p $PID -o %cpu --no-headers 2>/dev/null | tr -d ' '); "
        "  MEM=$(ps -p $PID -o %mem --no-headers 2>/dev/null | tr -d ' '); "
        "  STARTED=$(ps -p $PID -o lstart --no-headers 2>/dev/null | xargs); "
        "  echo \"pid=$PID cpu=$CPU mem=$MEM started=$STARTED\"; "
        "else "
        "  echo 'pid='; "
        "fi"
    )
    try:
        result = subprocess.run(
            ["ssh", host, cmd],
            capture_output=True,
            text=True,
            timeout=8,
        )
        line = result.stdout.strip()
        info: dict = {}
        # pid=1234 cpu=0.5 mem=1.2 started=Thu Mar  6 00:00:00 2026
        m = re.match(r"pid=(\S*)\s*(?:cpu=(\S*)\s*mem=(\S*)\s*started=(.+))?", line)
        if m:
            info["pid"] = m.group(1) or ""
            info["cpu"] = m.group(2) or ""
            info["mem"] = m.group(3) or ""
            info["started"] = m.group(4) or ""
        return info
    except Exception:
        return {"pid": "", "cpu": "", "mem": "", "started": ""}


# ──────────────────────────────────────────
#  ログ解析
# ──────────────────────────────────────────
LOG_RE = re.compile(
    r"時刻: (?P<ts>\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})"
    r".*?高値:\s*(?P<high>[\d.]+)"
    r".*?安値:\s*(?P<low>[\d.]+)"
    r".*?終値:\s*(?P<close>[\d.]+)"
    r".*?購入価格:\s*(?P<buy>[\d.]+)"
    r".*?STOP:\s*(?P<stop>[\d.]+)"
    r".*?ボラ:\s*(?P<vola>[\d.]+)"
    r".*?出来高:\s*(?P<volume>[\d.]+)"
    r".*?SIGNAL:\s*(?P<signal>\S+ -> \S+)"
    r".*?購入量:\s*(?P<qty>[\d.]+)"
    r".*?資産:\s*(?P<asset>[\d.]+)"
    r".*?ポジ:\s*(?P<pos>\S+)"
    r".*?みなし損益:\s*(?P<pnl>[-\d]+)"
    r".*?累計損益:\s*(?P<total_pnl>[-\d]+)"
)
BALANCE_RE = re.compile(r"unionAvailable=([\d.]+)")
ERROR_RE = re.compile(r"\b(ERROR|RATE LIMIT|Exception)\b", re.IGNORECASE)


def parse_log(raw: str) -> dict:
    """ログテキストを解析してダッシュボード用データを返す"""
    lines = raw.splitlines()
    logfile = ""
    data_lines = []
    for line in lines:
        if line.startswith("__LOGFILE__:"):
            logfile = line.split(":", 1)[1].strip()
        else:
            data_lines.append(line)

    signal_rows = []
    for line in data_lines:
        m = LOG_RE.search(line)
        if m:
            signal_rows.append(m.groupdict())

    # 残高取得
    balance = ""
    for line in reversed(data_lines):
        mb = BALANCE_RE.search(line)
        if mb:
            balance = mb.group(1)
            break

    # エラー数 (直近 200 行)
    recent_lines = data_lines[-200:]
    error_lines = [l for l in recent_lines if ERROR_RE.search(l)]

    latest = signal_rows[-1] if signal_rows else {}

    # チャート用: 最新 60 件
    chart_rows = signal_rows[-60:]
    chart_labels = [r["ts"][5:] for r in chart_rows]   # MM/DD HH:MM:SS
    chart_close  = [float(r["close"])     for r in chart_rows]
    chart_high   = [float(r["high"])      for r in chart_rows]
    chart_low    = [float(r["low"])       for r in chart_rows]
    chart_pnl    = [int(r["total_pnl"])   for r in chart_rows]
    chart_volume = [float(r["volume"])    for r in chart_rows]
    chart_vola   = [float(r["vola"])      for r in chart_rows]

    # シグナル履歴 (最新 10 件)
    history = []
    for r in signal_rows[-10:]:
        history.append({
            "ts": r["ts"],
            "signal": r["signal"],
            "close": r["close"],
            "pos": r["pos"],
            "pnl": r["pnl"],
            "total_pnl": r["total_pnl"],
        })
    history.reverse()

    return {
        "logfile": os.path.basename(logfile),
        "balance": balance,
        "latest": latest,
        "error_lines": error_lines[-5:],
        "error_count": len(error_lines),
        "chart": {
            "labels":  chart_labels,
            "close":   chart_close,
            "high":    chart_high,
            "low":     chart_low,
            "pnl":     chart_pnl,
            "volume":  chart_volume,
            "vola":    chart_vola,
        },
        "history": history,
        "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def get_status() -> dict:
    """キャッシュ付き: ラズパイからデータ取得して返す"""
    global _cache
    now = time.time()
    with _cache_lock:
        if _cache["data"] and (now - _cache["timestamp"]) < CACHE_TTL:
            cached = dict(_cache["data"])
            cached["from_cache"] = True
            return cached

    try:
        raw = fetch_log_via_ssh(_ssh_host)
        proc = fetch_process_status(_ssh_host)
        data = parse_log(raw)
        data["process"] = proc
        data["ssh_host"] = _ssh_host
        data["from_cache"] = False
        data["error"] = None
    except Exception as e:
        with _cache_lock:
            if _cache["data"]:
                stale = dict(_cache["data"])
                stale["from_cache"] = True
                stale["fetch_error"] = str(e)
                return stale
        return {
            "error": str(e),
            "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "from_cache": False,
        }

    with _cache_lock:
        _cache["data"] = data
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
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
<style>
  :root {
    --bg:      #0d1117;
    --card:    #161b22;
    --border:  #30363d;
    --text:    #e6edf3;
    --muted:   #8b949e;
    --green:   #3fb950;
    --red:     #f85149;
    --yellow:  #d29922;
    --blue:    #58a6ff;
    --purple:  #bc8cff;
    --orange:  #ffa657;
    --accent:  #1f6feb;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    padding: 20px;
  }

  /* ── Header ── */
  .header {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-bottom: 24px;
    padding-bottom: 16px;
    border-bottom: 1px solid var(--border);
  }
  .header-logo {
    font-size: 28px;
    font-weight: 700;
    background: linear-gradient(135deg, var(--blue), var(--purple));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }
  .header-sub {
    color: var(--muted);
    font-size: 13px;
    margin-top: 2px;
  }
  .header-right {
    margin-left: auto;
    text-align: right;
    font-size: 12px;
    color: var(--muted);
    line-height: 1.8;
  }
  .status-dot {
    display: inline-block;
    width: 10px; height: 10px;
    border-radius: 50%;
    margin-right: 6px;
    animation: pulse 2s infinite;
  }
  .dot-green { background: var(--green); }
  .dot-red   { background: var(--red); animation: none; }
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50%       { opacity: 0.4; }
  }

  /* ── Card grid ── */
  .grid { display: grid; gap: 16px; }
  .grid-4 { grid-template-columns: repeat(4, 1fr); }
  .grid-3 { grid-template-columns: repeat(3, 1fr); }
  .grid-2 { grid-template-columns: repeat(2, 1fr); }
  .grid-1 { grid-template-columns: 1fr; }

  .card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
  }
  .card-title {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 12px;
  }
  .card-value {
    font-size: 26px;
    font-weight: 700;
    line-height: 1;
  }
  .card-sub {
    font-size: 12px;
    color: var(--muted);
    margin-top: 6px;
  }
  .text-green  { color: var(--green); }
  .text-red    { color: var(--red); }
  .text-yellow { color: var(--yellow); }
  .text-blue   { color: var(--blue); }
  .text-muted  { color: var(--muted); }
  .text-orange { color: var(--orange); }

  /* ── Process badge ── */
  .badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
  }
  .badge-green { background: rgba(63,185,80,.15); color: var(--green); border: 1px solid rgba(63,185,80,.3); }
  .badge-red   { background: rgba(248,81,73,.15);  color: var(--red);   border: 1px solid rgba(248,81,73,.3); }

  /* ── Meter bar ── */
  .meter-track {
    height: 8px;
    background: var(--border);
    border-radius: 4px;
    overflow: hidden;
    margin-top: 8px;
  }
  .meter-fill {
    height: 100%;
    border-radius: 4px;
    transition: width 0.4s ease;
  }

  /* ── Signal table ── */
  .sig-table { width: 100%; border-collapse: collapse; font-size: 13px; }
  .sig-table th {
    text-align: left;
    padding: 8px 12px;
    color: var(--muted);
    font-size: 11px;
    font-weight: 600;
    border-bottom: 1px solid var(--border);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .sig-table td {
    padding: 8px 12px;
    border-bottom: 1px solid rgba(48,54,61,.5);
    color: var(--text);
    font-variant-numeric: tabular-nums;
  }
  .sig-table tr:last-child td { border-bottom: none; }
  .sig-table tr:hover td { background: rgba(255,255,255,.03); }

  /* ── Error list ── */
  .error-item {
    font-size: 12px;
    color: var(--red);
    padding: 4px 0;
    border-bottom: 1px solid rgba(248,81,73,.15);
    word-break: break-all;
  }
  .error-item:last-child { border-bottom: none; }

  /* ── Misc ── */
  .section-gap { margin-top: 20px; }
  .row { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
  .label {
    font-size: 11px;
    color: var(--muted);
    margin-right: 4px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  canvas { max-height: 220px; }
  .spinner {
    display: inline-block;
    width: 14px; height: 14px;
    border: 2px solid var(--border);
    border-top-color: var(--blue);
    border-radius: 50%;
    animation: spin .7s linear infinite;
    vertical-align: middle;
    margin-right: 4px;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  @media (max-width: 900px) {
    .grid-4, .grid-3 { grid-template-columns: repeat(2, 1fr); }
    .grid-2            { grid-template-columns: 1fr; }
  }
  @media (max-width: 540px) {
    .grid-4, .grid-3, .grid-2 { grid-template-columns: 1fr; }
  }
</style>
</head>
<body>

<!-- ══ HEADER ══════════════════════════════════════════════════════ -->
<div class="header">
  <div>
    <div class="header-logo">⚡ satosystem</div>
    <div class="header-sub">Bitcoin Auto-Trading Monitor</div>
  </div>
  <div class="header-right">
    <div id="refreshStatus">
      <span class="spinner"></span>読み込み中...
    </div>
    <div id="nextRefresh" style="margin-top:4px;"></div>
  </div>
</div>

<!-- ══ プロセス状態 ═══════════════════════════════════════════════ -->
<div class="grid grid-4">
  <div class="card" id="cardProcess">
    <div class="card-title">プロセス状態</div>
    <div id="procBadge">—</div>
    <div class="card-sub" id="procMeta"></div>
  </div>
  <div class="card">
    <div class="card-title">残高 (USDT)</div>
    <div class="card-value text-blue" id="valBalance">—</div>
    <div class="card-sub" id="valLogfile"></div>
  </div>
  <div class="card">
    <div class="card-title">累計損益</div>
    <div class="card-value" id="valTotalPnl">—</div>
    <div class="card-sub" id="valPnl"></div>
  </div>
  <div class="card">
    <div class="card-title">エラー (直近)</div>
    <div class="card-value" id="valErrCount">—</div>
    <div class="card-sub">直近 200 行</div>
  </div>
</div>

<!-- ══ 現在データ ═══════════════════════════════════════════════ -->
<div class="grid grid-4 section-gap">
  <div class="card">
    <div class="card-title">BTC 終値</div>
    <div class="card-value" id="valClose">—</div>
    <div class="card-sub row" style="margin-top:8px;">
      <span><span class="label">高</span><span class="text-yellow" id="valHigh">—</span></span>
      <span><span class="label">安</span><span class="text-blue"   id="valLow">—</span></span>
    </div>
  </div>
  <div class="card">
    <div class="card-title">ポジション</div>
    <div class="card-value" id="valPos">—</div>
    <div class="card-sub" id="valPosDetail"></div>
  </div>
  <div class="card">
    <div class="card-title">シグナル</div>
    <div class="card-value" style="font-size:18px;" id="valSignal">—</div>
    <div class="card-sub" id="valTs"></div>
  </div>
  <div class="card">
    <div class="card-title">出来高</div>
    <div class="card-value" id="valVolume">—</div>
    <div class="card-sub"></div>
  </div>
</div>

<!-- ══ ボラティリティメーター ════════════════════════════════════ -->
<div class="card section-gap">
  <div class="card-title">ボラティリティ</div>
  <div class="row" style="margin-bottom:6px;">
    <span class="card-value" id="valVola">—</span>
    <span class="text-muted" style="font-size:13px;">/ 2500 (閾値)</span>
    <span id="volaLabel" style="font-size:12px; font-weight:600; margin-left:8px;"></span>
  </div>
  <div class="meter-track">
    <div class="meter-fill" id="volaMeter" style="width:0%; background: var(--green);"></div>
  </div>
</div>

<!-- ══ チャート ══════════════════════════════════════════════════ -->
<div class="grid grid-2 section-gap">
  <div class="card">
    <div class="card-title">BTC 価格推移（直近 60 件）</div>
    <canvas id="chartPrice"></canvas>
  </div>
  <div class="card">
    <div class="card-title">累計損益推移 USD（直近 60 件）</div>
    <canvas id="chartPnl"></canvas>
  </div>
</div>
<div class="grid grid-2 section-gap">
  <div class="card">
    <div class="card-title">出来高推移（直近 60 件）</div>
    <canvas id="chartVolume"></canvas>
  </div>
  <div class="card">
    <div class="card-title">ボラティリティ推移（直近 60 件）</div>
    <canvas id="chartVola"></canvas>
  </div>
</div>

<!-- ══ シグナル履歴 ═════════════════════════════════════════════ -->
<div class="card section-gap">
  <div class="card-title">直近シグナル履歴</div>
  <table class="sig-table">
    <thead>
      <tr>
        <th>時刻</th>
        <th>シグナル</th>
        <th>終値</th>
        <th>ポジション</th>
        <th>みなし損益</th>
        <th>累計損益</th>
      </tr>
    </thead>
    <tbody id="historyBody"></tbody>
  </table>
</div>

<!-- ══ エラー詳細 ═══════════════════════════════════════════════ -->
<div class="card section-gap" id="errorSection" style="display:none;">
  <div class="card-title" style="color: var(--red);">⚠ エラー詳細（直近）</div>
  <div id="errorBody"></div>
</div>

<div style="height:40px;"></div>

<!-- ══ Script ══════════════════════════════════════════════════ -->
<script>
const REFRESH_INTERVAL = 30; // 秒
let countdown = REFRESH_INTERVAL;
let chartPrice, chartPnl, chartVolume, chartVola;

const chartDefaults = {
  responsive: true,
  maintainAspectRatio: true,
  animation: { duration: 300 },
  plugins: {
    legend: { display: false },
    tooltip: {
      backgroundColor: '#1c2128',
      borderColor: '#30363d',
      borderWidth: 1,
      titleColor: '#8b949e',
      bodyColor: '#e6edf3',
    }
  },
  scales: {
    x: {
      ticks: { color: '#8b949e', maxTicksLimit: 6, font: { size: 10 } },
      grid: { color: 'rgba(48,54,61,0.5)' },
    },
    y: {
      ticks: { color: '#8b949e', font: { size: 10 } },
      grid: { color: 'rgba(48,54,61,0.5)' },
    }
  }
};

function initCharts() {
  chartPrice = new Chart(document.getElementById('chartPrice').getContext('2d'), {
    type: 'line',
    data: { labels: [], datasets: [
      { label: '終値', data: [], borderColor: '#58a6ff', backgroundColor: 'rgba(88,166,255,.07)', fill: true, tension: 0.3, pointRadius: 1 },
      { label: '高値', data: [], borderColor: '#d29922', backgroundColor: 'transparent', borderDash: [4,4], tension: 0.3, pointRadius: 0 },
      { label: '安値', data: [], borderColor: '#3fb950', backgroundColor: 'transparent', borderDash: [4,4], tension: 0.3, pointRadius: 0 },
    ]},
    options: { ...chartDefaults, plugins: { ...chartDefaults.plugins, legend: { display: true, labels: { color: '#8b949e', font: { size: 11 } } } } }
  });
  chartPnl = new Chart(document.getElementById('chartPnl').getContext('2d'), {
    type: 'line',
    data: { labels: [], datasets: [
      { label: '累計損益', data: [], borderColor: '#3fb950', backgroundColor: 'rgba(63,185,80,.08)', fill: true, tension: 0.3, pointRadius: 1 }
    ]},
    options: { ...chartDefaults }
  });
  chartVolume = new Chart(document.getElementById('chartVolume').getContext('2d'), {
    type: 'bar',
    data: { labels: [], datasets: [
      { label: '出来高', data: [], backgroundColor: 'rgba(88,166,255,.5)', borderColor: '#58a6ff', borderWidth: 0 }
    ]},
    options: { ...chartDefaults }
  });
  chartVola = new Chart(document.getElementById('chartVola').getContext('2d'), {
    type: 'line',
    data: { labels: [], datasets: [
      { label: 'ボラ', data: [], borderColor: '#ffa657', backgroundColor: 'rgba(255,166,87,.08)', fill: true, tension: 0.3, pointRadius: 1 }
    ]},
    options: { ...chartDefaults }
  });
}

function updateCharts(chart) {
  const c = chart;
  chartPrice.data.labels              = c.labels;
  chartPrice.data.datasets[0].data   = c.close;
  chartPrice.data.datasets[1].data   = c.high;
  chartPrice.data.datasets[2].data   = c.low;
  chartPrice.update();

  const minPnl = Math.min(...c.pnl);
  chartPnl.data.labels                = c.labels;
  chartPnl.data.datasets[0].data     = c.pnl;
  chartPnl.data.datasets[0].borderColor    = minPnl < 0 ? '#f85149' : '#3fb950';
  chartPnl.data.datasets[0].backgroundColor = minPnl < 0 ? 'rgba(248,81,73,.08)' : 'rgba(63,185,80,.08)';
  chartPnl.update();

  chartVolume.data.labels             = c.labels;
  chartVolume.data.datasets[0].data  = c.volume;
  chartVolume.update();

  chartVola.data.labels               = c.labels;
  chartVola.data.datasets[0].data    = c.vola;
  chartVola.update();
}

function fmt(num, digits=2) {
  if (num === null || num === undefined || num === '') return '—';
  const n = parseFloat(num);
  return isNaN(n) ? String(num) : n.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function fmtPnl(val) {
  const n = parseInt(val);
  if (isNaN(n)) return '—';
  const sign = n >= 0 ? '+' : '';
  return `${sign}${n.toLocaleString()} USD`;
}

function render(d) {
  if (d.error) {
    document.getElementById('refreshStatus').innerHTML = `<span style="color:var(--red)">⚠ ${d.error}</span>`;
    return;
  }

  const cache = d.from_cache ? ' (キャッシュ)' : '';
  document.getElementById('refreshStatus').innerHTML = `最終取得: ${d.fetched_at}${cache}`;

  // ── プロセス ──
  const proc = d.process || {};
  const running = proc.pid && proc.pid !== '';
  document.getElementById('procBadge').innerHTML = running
    ? `<span class="badge badge-green"><span class="status-dot dot-green"></span>稼働中</span>`
    : `<span class="badge badge-red"><span class="status-dot dot-red"></span>停止中</span>`;
  if (running) {
    document.getElementById('procMeta').textContent = `PID ${proc.pid}  CPU ${proc.cpu}%  MEM ${proc.mem}%`;
  } else {
    document.getElementById('procMeta').textContent = proc.started ? `停止確認: ${proc.started}` : '';
  }

  // ── 残高 ──
  document.getElementById('valBalance').textContent = d.balance ? fmt(d.balance, 2) : '—';
  document.getElementById('valLogfile').textContent = d.logfile || '';

  // ── 最新データ ──
  const l = d.latest || {};
  const close = parseFloat(l.close) || 0;
  document.getElementById('valClose').textContent = close ? close.toLocaleString() : '—';
  document.getElementById('valHigh').textContent  = l.high  ? parseInt(l.high).toLocaleString()  : '—';
  document.getElementById('valLow').textContent   = l.low   ? parseInt(l.low).toLocaleString()   : '—';

  // ポジション
  const pos = l.pos || 'NONE';
  const posEl = document.getElementById('valPos');
  posEl.textContent = pos;
  posEl.className = 'card-value ' + (pos === 'BUY' ? 'text-green' : pos === 'SELL' ? 'text-red' : 'text-muted');
  document.getElementById('valPosDetail').textContent =
    l.buy && l.buy !== '0' ? `購入価格: ${parseInt(l.buy).toLocaleString()}  STOP: ${parseInt(l.stop).toLocaleString()}` : '';

  // シグナル
  const sig = l.signal || '';
  const sigEl = document.getElementById('valSignal');
  sigEl.textContent = sig || '—';
  sigEl.className = 'card-value ' + (sig.includes('ENTRY') || sig.includes('BUY') || sig.includes('SELL') ? 'text-green' : 'text-muted');
  document.getElementById('valTs').textContent = l.ts || '';

  // 出来高
  document.getElementById('valVolume').textContent = l.volume ? fmt(l.volume, 2) : '—';

  // 損益
  const totalPnl = parseInt(l.total_pnl);
  const tpEl = document.getElementById('valTotalPnl');
  tpEl.textContent = isNaN(totalPnl) ? '—' : fmtPnl(totalPnl);
  tpEl.className = 'card-value ' + (totalPnl > 0 ? 'text-green' : totalPnl < 0 ? 'text-red' : 'text-muted');
  const pnl = parseInt(l.pnl);
  document.getElementById('valPnl').textContent = isNaN(pnl) ? '' : `みなし: ${fmtPnl(pnl)}`;

  // エラー
  const errEl = document.getElementById('valErrCount');
  errEl.textContent = d.error_count;
  errEl.className = 'card-value ' + (d.error_count > 0 ? 'text-red' : 'text-green');

  // ボラティリティ
  const vola = parseFloat(l.vola) || 0;
  document.getElementById('valVola').textContent = vola.toFixed(2);
  const volaRatio = Math.min(vola / 2500, 1);
  const meterEl = document.getElementById('volaMeter');
  meterEl.style.width = (volaRatio * 100) + '%';
  let volaColor = 'var(--green)', volaText = '通常';
  if (vola >= 2500) { volaColor = 'var(--red)'; volaText = '⚠ 高'; }
  else if (vola >= 2000) { volaColor = 'var(--yellow)'; volaText = '注意'; }
  meterEl.style.background = volaColor;
  const volaLbl = document.getElementById('volaLabel');
  volaLbl.textContent = volaText;
  volaLbl.style.color = volaColor;

  // チャート
  if (d.chart && d.chart.labels.length > 0) updateCharts(d.chart);

  // シグナル履歴
  const tbody = document.getElementById('historyBody');
  tbody.innerHTML = '';
  (d.history || []).forEach(r => {
    const pnl = parseInt(r.pnl);
    const tpnl = parseInt(r.total_pnl);
    const sig = r.signal || '';
    const sigColor = (sig.includes('ENTRY') || sig.includes('BUY') || sig.includes('SELL')) ? 'var(--green)' : 'var(--muted)';
    const posColor = r.pos === 'BUY' ? 'var(--green)' : r.pos === 'SELL' ? 'var(--red)' : 'var(--muted)';
    tbody.innerHTML += `
      <tr>
        <td style="color:var(--muted); font-size:12px;">${r.ts}</td>
        <td style="color:${sigColor}; font-weight:600;">${sig}</td>
        <td>${parseInt(r.close).toLocaleString()}</td>
        <td style="color:${posColor}; font-weight:600;">${r.pos}</td>
        <td style="color:${pnl>=0?'var(--green)':'var(--red)'};">${fmtPnl(pnl)}</td>
        <td style="color:${tpnl>=0?'var(--green)':'var(--red)'};">${fmtPnl(tpnl)}</td>
      </tr>`;
  });

  // エラー詳細
  const errSection = document.getElementById('errorSection');
  if (d.error_count > 0 && d.error_lines && d.error_lines.length > 0) {
    errSection.style.display = '';
    document.getElementById('errorBody').innerHTML =
      d.error_lines.map(e => `<div class="error-item">${e}</div>`).join('');
  } else {
    errSection.style.display = 'none';
  }
}

async function refresh() {
  document.getElementById('refreshStatus').innerHTML = '<span class="spinner"></span>更新中...';
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    render(data);
  } catch (e) {
    document.getElementById('refreshStatus').innerHTML = `<span style="color:var(--red)">⚠ 通信エラー: ${e.message}</span>`;
  }
  countdown = REFRESH_INTERVAL;
}

function startCountdown() {
  setInterval(() => {
    countdown--;
    document.getElementById('nextRefresh').textContent = `次回更新まで ${countdown}秒`;
    if (countdown <= 0) {
      countdown = REFRESH_INTERVAL;
      refresh();
    }
  }, 1000);
}

initCharts();
refresh();
startCountdown();
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
    global _ssh_host

    parser = argparse.ArgumentParser(description="satosystem Web Monitor")
    parser.add_argument("--host", default=DEFAULT_SSH_HOST, help="SSH ホスト名 (default: raspberry_pi)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="リッスンポート (default: 8080)")
    args = parser.parse_args()

    _ssh_host = args.host

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
    print(f"\n🚀 satosystem Web Monitor 起動")
    print(f"   ブラウザで開く: http://localhost:{args.port}")
    print(f"   ラズパイ接続先: {_ssh_host}")
    print(f"   キャッシュTTL : {CACHE_TTL}秒")
    print(f"   停止: Ctrl+C\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n⏹  Monitor停止")
        server.shutdown()


if __name__ == "__main__":
    main()
