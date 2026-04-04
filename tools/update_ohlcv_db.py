#!/usr/bin/env python3
"""
OHLCVキャッシュDB更新ツール

Bybit公開API経由でBTC/USDT:USDT 4H足データを取得し、
ohlcv_data/ohlcv_cache.db に保存します。
バックテスト時にAPIレートリミットにかかるのを防ぐため、
このコマンドで事前にデータを蓄積しておいてください。

使用例:
  python3 tools/update_ohlcv_db.py                  # DBの最新日以降を追記（推奨）
  python3 tools/update_ohlcv_db.py --stats           # DB統計を表示して終了
  python3 tools/update_ohlcv_db.py --year 2024       # 2024年データを取得・保存
  python3 tools/update_ohlcv_db.py --year 2025       # 2025年データを取得・保存
  python3 tools/update_ohlcv_db.py --year 2026       # 2026年（年初〜今日）を取得
  python3 tools/update_ohlcv_db.py --full            # 2023/11〜今日を全件re-fetch

Bybitの公開APIを使うためAPIキーは不要です。
3月23日以降もBybit公開APIが使えなくなった場合は取引所を変更してください。
"""

import sys
import os
import sqlite3
import time
import argparse
from datetime import datetime

# ccxt
try:
    import ccxt
except ImportError:
    print("ERROR: ccxt が見つかりません。pip install ccxt を実行してください。")
    sys.exit(1)

# -------------------------------------------------------
# 定数
# -------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, '..', 'ohlcv_data', 'ohlcv_cache.db')
DB_PATH = os.path.normpath(DB_PATH)

DEFAULT_SYMBOL = 'BTC/USDT:USDT'
TIMEFRAME = '4h'
TIMEFRAME_MIN = 240          # 4H = 240分
CHUNK_LIMIT = 200            # 1リクエストあたりの取得件数（Bybit上限1000、余裕を持って200）
RATE_LIMIT_SLEEP = 0.3       # リクエスト間のスリープ（秒）

# グローバル変数（--symbolで動的に設定される）
SYMBOL = DEFAULT_SYMBOL

# シンボル変換マップ: ショート名 → ccxt形式
SYMBOL_MAP = {
    'BTC/USDT':  'BTC/USDT:USDT',
    'ETH/USDT':  'ETH/USDT:USDT',
    'XAUT/USDT': 'XAUT/USDT:USDT',
    'PAXG/USDT': 'PAXG/USDT:USDT',
    'SOL/USDT':  'SOL/USDT:USDT',
}

# バックテストのlookback最大値（300足 x 240min = 72,000min ≈ 50日）
# 2024年バックテスト開始には2023/11中旬以降のデータが必要
FULL_FETCH_START = datetime(2023, 11, 1, 0, 0)  # 全件取得の開始日


# -------------------------------------------------------
# DB接続 & テーブル初期化
# -------------------------------------------------------
def get_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS candles (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol        TEXT    NOT NULL,
            start_epoch   INTEGER NOT NULL,
            end_epoch     INTEGER NOT NULL,
            time_frame    INTEGER NOT NULL,
            close_time    REAL    UNIQUE NOT NULL,
            close_time_dt TEXT    NOT NULL,
            open_price    REAL    NOT NULL,
            high_price    REAL    NOT NULL,
            low_price     REAL    NOT NULL,
            close_price   REAL    NOT NULL,
            volume        REAL    NOT NULL,
            created_at    TEXT    DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_params ON candles (symbol, start_epoch, end_epoch, time_frame)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_time   ON candles (close_time)")
    conn.commit()
    return conn


# -------------------------------------------------------
# DB統計表示
# -------------------------------------------------------
def show_stats(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute("""
        SELECT symbol, time_frame, COUNT(*),
               MIN(close_time_dt), MAX(close_time_dt),
               MIN(start_epoch),   MAX(end_epoch)
        FROM candles
        GROUP BY symbol, time_frame
        ORDER BY symbol, time_frame
    """)
    rows = cur.fetchall()
    if not rows:
        print("  (データなし)")
        return
    for r in rows:
        size_mb = os.path.getsize(DB_PATH) / 1024 / 1024
        print(f"  symbol     : {r[0]}")
        print(f"  timeframe  : {r[1]} min ({r[1]//60}H)")
        print(f"  candles    : {r[2]:,} 件")
        print(f"  data range : {r[3]}  〜  {r[4]}")
        print(f"  start_epoch: {datetime.fromtimestamp(r[5]).strftime('%Y/%m/%d %H:%M')} ({r[5]})")
        print(f"  end_epoch  : {datetime.fromtimestamp(r[6]).strftime('%Y/%m/%d %H:%M')} ({r[6]})")
        print(f"  DB file    : {DB_PATH}  ({size_mb:.1f} MB)")


# -------------------------------------------------------
# Bybitからローソク足を取得
# -------------------------------------------------------
def fetch_candles_from_bybit(
    start_ts_ms: int,
    end_ts_ms: int,
    show_progress: bool = True,
    symbol: str = None
) -> list:
    """
    Bybit公開APIから4H足OHLCVをページネーション取得

    Args:
        start_ts_ms: 開始時刻（ミリ秒）
        end_ts_ms:   終了時刻（ミリ秒）
    Returns:
        ローソク足リスト（各要素はdict）
    """
    fetch_symbol = symbol or SYMBOL
    exchange = ccxt.bybit({
        'enableRateLimit': True,
        'timeout': 30000,
        'options': {
            'fetchCurrencies': False,
        },
    })

    all_candles = []
    current_ms = start_ts_ms
    retries = 0

    while current_ms < end_ts_ms:
        try:
            ohlcv = exchange.fetch_ohlcv(
                fetch_symbol, TIMEFRAME,
                since=current_ms,
                limit=CHUNK_LIMIT
            )
            retries = 0
        except ccxt.RateLimitExceeded:
            retries += 1
            wait = min(60 * retries, 300)
            print(f"\n  ⚠ RateLimitExceeded: {wait}秒待機...")
            time.sleep(wait)
            continue
        except Exception as e:
            retries += 1
            wait = min(10 * retries, 60)
            print(f"\n  ⚠ API error ({retries}回目): {e}. {wait}秒待機...")
            if retries > 5:
                print("  エラーが続くため中断します")
                break
            time.sleep(wait)
            continue

        if not ohlcv:
            break

        for row in ohlcv:
            ts_s = row[0] / 1000
            if ts_s >= end_ts_ms / 1000:
                break
            # OHLC が全て0のローソク足は除外
            if row[1] and row[2] and row[3] and row[4]:
                all_candles.append({
                    'close_time':    ts_s,
                    'close_time_dt': datetime.fromtimestamp(ts_s).strftime('%Y/%m/%d %H:%M'),
                    'open_price':    float(row[1]),
                    'high_price':    float(row[2]),
                    'low_price':     float(row[3]),
                    'close_price':   float(row[4]),
                    'volume':        float(row[5]),
                })

        current_ms = ohlcv[-1][0] + 1

        if show_progress:
            dt_str = datetime.fromtimestamp(ohlcv[-1][0] / 1000).strftime('%Y/%m/%d %H:%M')
            print(f"  fetching... {dt_str}  ({len(all_candles):,} candles)", end='\r')

        time.sleep(RATE_LIMIT_SLEEP)

    if show_progress and all_candles:
        print()  # progress行を改行して確定

    return all_candles


# -------------------------------------------------------
# データ抜け確認
# -------------------------------------------------------
def check_gaps(conn: sqlite3.Connection) -> list:
    """
    DB内のclose_timeを順番にスキャンし、4H超の空白（抜け）を検出する。
    Returns:
        gaps: [{'gap_start_ts', 'gap_end_ts', 'gap_start_dt', 'gap_end_dt', 'missing_candles'}, ...]
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT close_time, close_time_dt
          FROM candles
         WHERE symbol=? AND time_frame=?
         ORDER BY close_time
    """, (SYMBOL, TIMEFRAME_MIN))
    rows = cur.fetchall()

    if len(rows) < 2:
        return []

    expected_interval = TIMEFRAME_MIN * 60  # 14400秒
    # 許容誤差: 1分（エポック変換の丸め誤差対策）
    tolerance = 60

    gaps = []
    for i in range(1, len(rows)):
        prev_ts = rows[i - 1][0]
        curr_ts = rows[i][0]
        diff = curr_ts - prev_ts

        if diff > expected_interval + tolerance:
            gap_start_ts = prev_ts + expected_interval
            gap_end_ts   = curr_ts - expected_interval
            missing = max(1, round((diff - expected_interval) / expected_interval))
            gaps.append({
                'gap_start_ts':  gap_start_ts,
                'gap_end_ts':    gap_end_ts,
                'gap_start_dt':  datetime.fromtimestamp(gap_start_ts).strftime('%Y/%m/%d %H:%M'),
                'gap_end_dt':    datetime.fromtimestamp(gap_end_ts).strftime('%Y/%m/%d %H:%M'),
                'missing_candles': missing,
            })
    return gaps


def show_gaps(gaps: list) -> None:
    if not gaps:
        print("  データ抜けなし ✓")
        return
    total = sum(g['missing_candles'] for g in gaps)
    print(f"  {len(gaps)} 件の抜けを検出（合計約 {total} candles）:")
    for g in gaps:
        print(f"    {g['gap_start_dt']} 〜 {g['gap_end_dt']}  (約 {g['missing_candles']} candles)")


# -------------------------------------------------------
# DB保存 / upsert
# -------------------------------------------------------
def upsert_candles(
    conn: sqlite3.Connection,
    candles: list,
    new_start_epoch: int,
    new_end_epoch: int
) -> int:
    """
    ローソク足をDBにupsertし、全既存行のstart/end_epochを統一する。

    close_time の UNIQUE 制約により、同じ足は INSERT OR REPLACE で上書き。
    既存行のstart/end_epochも new_start / new_end に揃えるため、
    backtestの partial match クエリが確実にヒットするようにする。

    Returns:
        保存した件数
    """
    if not candles:
        return 0

    cur = conn.cursor()

    # 新規ローソク足をupsert
    records = [
        (SYMBOL, new_start_epoch, new_end_epoch, TIMEFRAME_MIN,
         c['close_time'], c['close_time_dt'],
         c['open_price'], c['high_price'], c['low_price'],
         c['close_price'], c['volume'])
        for c in candles
    ]
    cur.executemany("""
        INSERT OR REPLACE INTO candles
           (symbol, start_epoch, end_epoch, time_frame,
            close_time, close_time_dt,
            open_price, high_price, low_price, close_price, volume)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, records)

    # 既存行のstart/end_epochを統一（partial matchクエリのため必須）
    cur.execute("""
        UPDATE candles
           SET start_epoch = ?, end_epoch = ?
         WHERE symbol = ? AND time_frame = ?
    """, (new_start_epoch, new_end_epoch, SYMBOL, TIMEFRAME_MIN))

    conn.commit()
    return len(candles)


# -------------------------------------------------------
# メイン
# -------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description='OHLCVキャッシュDB更新ツール（Bybit 4H足）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""使用例:
  python3 tools/update_ohlcv_db.py                  DBの最新日以降を追記（デフォルト: BTC/USDT）
  python3 tools/update_ohlcv_db.py --symbol XAUT/USDT          金データを追記
  python3 tools/update_ohlcv_db.py --symbol XAUT/USDT --full   金データを全件取得
  python3 tools/update_ohlcv_db.py --stats           DB統計表示
  python3 tools/update_ohlcv_db.py --check           データ抜け（4H超空白）を検出
  python3 tools/update_ohlcv_db.py --fill            データ抜けをBybitから補完
  python3 tools/update_ohlcv_db.py --year 2024       2024年分を取得・保存
  python3 tools/update_ohlcv_db.py --year 2025       2025年分を取得・保存
  python3 tools/update_ohlcv_db.py --year 2026       2026年分（年初〜今日）を取得
  python3 tools/update_ohlcv_db.py --full            2023/11以降を全件re-fetch"""
    )
    parser.add_argument('--symbol', type=str, default=None,
                        help='取引シンボル（例: XAUT/USDT, SOL/USDT）。省略時はBTC/USDT')
    parser.add_argument('--year',   type=int, choices=[2024, 2025, 2026],
                        help='特定年のデータを取得・保存')
    parser.add_argument('--full',   action='store_true',
                        help=f'2023/11/01以降を全件re-fetch（初回セットアップ用）')
    parser.add_argument('--append', action='store_true',
                        help='DBの最新日以降のみ追記（引数なし実行と同等）')
    parser.add_argument('--check',  action='store_true',
                        help='DBのデータ抜け（4H超空白）を検出して表示')
    parser.add_argument('--fill',   action='store_true',
                        help='DBのデータ抜けをBybitから取得して補完')
    parser.add_argument('--stats',  action='store_true',
                        help='DB統計を表示して終了')
    args = parser.parse_args()

    # --symbol指定時はグローバルSYMBOLを更新
    global SYMBOL
    if args.symbol:
        if args.symbol in SYMBOL_MAP:
            SYMBOL = SYMBOL_MAP[args.symbol]
        elif ':' in args.symbol:
            SYMBOL = args.symbol  # 既にccxt形式
        else:
            SYMBOL = f"{args.symbol}:USDT"  # 汎用変換

    conn = get_connection()
    now_ts = int(time.time())

    print("\n=== OHLCV DB Update Tool ===")
    print(f"DB path : {DB_PATH}")
    print(f"Symbol  : {SYMBOL}  Timeframe: {TIMEFRAME}")
    print(f"Time    : {datetime.fromtimestamp(now_ts).strftime('%Y/%m/%d %H:%M')}")
    print()
    print("[現在のDB状態]")
    show_stats(conn)

    if args.stats:
        conn.close()
        return

    # --check: データ抜け表示のみ
    if args.check:
        print("\n[データ抜けチェック]")
        gaps = check_gaps(conn)
        show_gaps(gaps)
        conn.close()
        return

    # --fill: データ抜けを補完
    if args.fill:
        print("\n[データ抜けチェック]")
        gaps = check_gaps(conn)
        show_gaps(gaps)
        if not gaps:
            conn.close()
            return

        cur2 = conn.cursor()
        cur2.execute(
            "SELECT MIN(start_epoch) FROM candles WHERE symbol=? AND time_frame=?",
            (SYMBOL, TIMEFRAME_MIN)
        )
        fill_start_epoch = cur2.fetchone()[0]

        print(f"\n[抜け補完] {len(gaps)} 件を取得します...")
        total_filled = 0
        for i, g in enumerate(gaps, 1):
            print(f"  [{i}/{len(gaps)}] {g['gap_start_dt']} 〜 {g['gap_end_dt']}")
            candles = fetch_candles_from_bybit(
                int(g['gap_start_ts']) * 1000,
                int(g['gap_end_ts'] + TIMEFRAME_MIN * 60) * 1000,
                show_progress=False
            )
            if candles:
                cur2.execute(
                    "SELECT MAX(close_time) FROM candles WHERE symbol=? AND time_frame=?",
                    (SYMBOL, TIMEFRAME_MIN)
                )
                latest = cur2.fetchone()[0] or candles[-1]['close_time']
                new_end = max(int(latest), int(candles[-1]['close_time']))
                n = upsert_candles(conn, candles, fill_start_epoch, new_end)
                total_filled += n
                print(f"    → {n} candles 補完")
            else:
                print(f"    → データなし（Bybit未確定期間の可能性）")

        print(f"\n  合計 {total_filled} candles を補完しました")
        print()
        print("[更新後のDB状態]")
        show_stats(conn)
        conn.close()
        print("\n完了")
        return

    # ------------------------------------------------------
    # 取得範囲を決定
    # ------------------------------------------------------
    cur = conn.cursor()
    cur.execute("""
        SELECT MIN(start_epoch), MAX(close_time), COUNT(*)
          FROM candles WHERE symbol=? AND time_frame=?
    """, (SYMBOL, TIMEFRAME_MIN))
    row = cur.fetchone()
    existing_start_epoch = row[0]
    existing_latest_ts   = row[1]
    existing_count       = row[2] or 0

    if args.full:
        # 全件re-fetch
        fetch_start = FULL_FETCH_START
        fetch_end_ts = now_ts
        print(f"\n[全件re-fetch] {fetch_start.strftime('%Y/%m/%d')} 〜 今日")
        fetch_start_ms = int(fetch_start.timestamp() * 1000)
        fetch_end_ms   = fetch_end_ts * 1000

        new_start_epoch = int(fetch_start.timestamp())
        new_end_epoch   = fetch_end_ts

    elif args.year:
        year = args.year
        year_start = datetime(year, 1, 1, 0, 0)
        year_end_ts = int(datetime(year + 1, 1, 1, 0, 0).timestamp()) if year < 2026 else now_ts

        print(f"\n[{year}年データ取得] {year_start.strftime('%Y/%m/%d')} 〜 {datetime.fromtimestamp(year_end_ts).strftime('%Y/%m/%d')}")
        fetch_start_ms = int(year_start.timestamp() * 1000)
        fetch_end_ms   = year_end_ts * 1000

        # 既存DBのstart_epochを引き継ぐ（新規なら年頭から）
        new_start_epoch = existing_start_epoch or int(year_start.timestamp())
        new_end_epoch   = max(existing_latest_ts or 0, year_end_ts)

    else:
        # デフォルト: 追記モード（最新日以降）
        if not existing_latest_ts:
            print("\n  DBが空です。まず --year 2024 〜 2026 で年次データを取得してください。")
            print("  または --full で全件取得してください。")
            conn.close()
            return

        fetch_start_ts = int(existing_latest_ts) + TIMEFRAME_MIN * 60
        fetch_end_ts   = now_ts

        if fetch_start_ts >= fetch_end_ts:
            print(f"\n  DBは最新です（{datetime.fromtimestamp(existing_latest_ts).strftime('%Y/%m/%d %H:%M')} まで蓄積済み）。追記不要。")
            conn.close()
            return

        print(f"\n[追記モード] {datetime.fromtimestamp(fetch_start_ts).strftime('%Y/%m/%d %H:%M')} 以降を取得...")
        fetch_start_ms = fetch_start_ts * 1000
        fetch_end_ms   = fetch_end_ts * 1000

        new_start_epoch = existing_start_epoch
        new_end_epoch   = fetch_end_ts

    # ------------------------------------------------------
    # 取得 & 保存
    # ------------------------------------------------------
    candles = fetch_candles_from_bybit(fetch_start_ms, fetch_end_ms)

    if candles:
        # new_end_epochを実際の最終ローソク足で確定
        new_end_epoch = max(new_end_epoch, int(candles[-1]['close_time']))
        print(f"  取得件数: {len(candles):,} candles")
        print(f"  範囲    : {candles[0]['close_time_dt']} 〜 {candles[-1]['close_time_dt']}")
        print()
        print("[DB保存中...]")
        n = upsert_candles(conn, candles, new_start_epoch, new_end_epoch)
        print(f"  {n:,} candles を保存しました")
    else:
        print("  新規データなし（最新データのみ）")

    print()
    print("[更新後のDB状態]")
    show_stats(conn)
    conn.close()
    print("\n完了")


if __name__ == '__main__':
    main()
