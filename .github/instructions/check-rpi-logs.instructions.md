---
description: ラズパイ本番BOTのログを取得・分析し、期待通りの動作かを確認するスキル。BOT稼働確認・ログ取得・エラー確認を依頼されたときに使用する。BTCとXAUTの両方のBOTを確認する。
applyTo: "**"
---

# RPi本番BOTログ確認スキル（BTC + XAUT 対応版）

## 目的

Raspberry Piで稼働中の**BTC BOT・XAUT BOT（両方）**のログを取得し、以下を検証する：
- 両BOTが継続稼働しているか
- エラー・異常が発生していないか
- シグナルとエントリー条件が戦略通りか
- 現在のポジション・残高状態
- **並行動作による干渉（API競合・証拠金干渉・ポジション重複）がないか**

## BOTとログのパス一覧

| BOT | ログディレクトリ | PIDファイル | latest_status |
|---|---|---|---|
| BTC | `~/work/satosystem/src/logs/` | `bot_BTC.pid` | `src/logs/latest_status.json` |
| XAUT | `~/work/satosystem/src/logs/xaut/` | `bot_XAUT.pid` | `src/logs/xaut/latest_status.json` |

## 手順

### 1. 両ログディレクトリを確認

```bash
ssh raspberry_pi "echo '=== BTC logs ===' && ls -la ~/work/satosystem/src/logs/ | tail -10 && echo '=== XAUT logs ===' && ls -la ~/work/satosystem/src/logs/xaut/"
```

確認するファイル（各BOT）：
- `bot_BTC_YYYYMMDD_HHMMSS.log` / `bot_XAUT_YYYYMMDD_HHMMSS.log` — 最新ログ
- `latest_status.json` — 現在のBOT状態
- `bot_BTC.pid` / `bot_XAUT.pid` — プロセスID

### 2. 両BOTの設定と起動確認（ログ先頭）

```bash
ssh raspberry_pi "echo '=== BTC BOT HEAD ===' && head -35 ~/work/satosystem/src/logs/<BTCの最新ログ> && echo '=== XAUT BOT HEAD ===' && head -35 ~/work/satosystem/src/logs/xaut/<XAUTの最新ログ>"
```

確認項目（両BOT共通）：
- `Back Test Mode: 0` — 本番モードか
- `Risk Percentage` / `Leverage` / `Market` — 設定値
- `BOT START` の日時 — いつから稼働しているか

### 3. 両BOTの最新動作確認（ログ末尾）

```bash
ssh raspberry_pi "echo '=== BTC TAIL ===' && tail -80 ~/work/satosystem/src/logs/<BTCの最新ログ> && echo '=== XAUT TAIL ===' && tail -80 ~/work/satosystem/src/logs/xaut/<XAUTの最新ログ>"
```

確認項目：
- 直近のタイムスタンプが現在時刻に近いか（1分以内が正常）
- `unionAvailable` の残高推移（大きな減少がないか）
- **証拠金マイナスエラーが出ていないか** → エントリーループの危険

### 4. 両BOTのエラー統計

```bash
ssh raspberry_pi "
echo '=== BTC ERROR統計 ===' && grep -c 'ERROR' ~/work/satosystem/src/logs/<BTCの最新ログ> && \
echo '=== BTC RATE LIMIT回数 ===' && grep -c 'RATE LIMIT' ~/work/satosystem/src/logs/<BTCの最新ログ> && \
echo '=== BTC メインループエラー ===' && (grep 'メインループエラー' ~/work/satosystem/src/logs/<BTCの最新ログ> || echo 'なし') && \
echo '' && \
echo '=== XAUT ERROR統計 ===' && grep -c 'ERROR' ~/work/satosystem/src/logs/xaut/<XAUTの最新ログ> && \
echo '=== XAUT RATE LIMIT回数 ===' && grep -c 'RATE LIMIT' ~/work/satosystem/src/logs/xaut/<XAUTの最新ログ> && \
echo '=== XAUT メインループエラー ===' && (grep 'メインループエラー' ~/work/satosystem/src/logs/xaut/<XAUTの最新ログ> || echo 'なし')
"
```

⚠️ **XAUTのERROR件数が数百件を超える場合は、証拠金マイナスによる無限ループの可能性**：
```bash
ssh raspberry_pi "grep 'ERROR' ~/work/satosystem/src/logs/xaut/<XAUTの最新ログ> | grep -v 'RATE LIMIT\|最新価格取得エラー復帰' | head -10"
```

### 5. 両BOTのシグナル・フィルタ・エントリー詳細確認

#### 5a. シグナル統計（稼働開始から通算）

```bash
ssh raspberry_pi "
echo '=== BTC シグナル統計 ===' && \
echo 'strategy_A BUY件数:' && grep -c 'strategy_A: BUY' ~/work/satosystem/src/logs/<BTCの最新ログ> && \
echo 'strategy_A SELL件数:' && grep -c 'strategy_A: SELL' ~/work/satosystem/src/logs/<BTCの最新ログ> && \
echo '全Strategy NONE件数:' && grep -c '全Strategy: NONE' ~/work/satosystem/src/logs/<BTCの最新ログ> && \
echo 'Breakout BUY発生:' && (grep -c 'Breakout強度.*✓ BUY' ~/work/satosystem/src/logs/<BTCの最新ログ> || echo 0) && \
echo 'Breakout SELL発生:' && (grep -c 'Breakout強度.*✓ SELL' ~/work/satosystem/src/logs/<BTCの最新ログ> || echo 0) && \
echo '出来高不足(NG):' && (grep -c '相対出来高.*✗' ~/work/satosystem/src/logs/<BTCの最新ログ> || echo 0) && \
echo 'ADX不足(NG):' && (grep -c 'ADX.*✗\|ADX不足' ~/work/satosystem/src/logs/<BTCの最新ログ> || echo 0) && \
echo 'エントリー許可:' && (grep -c 'エントリー許可' ~/work/satosystem/src/logs/<BTCの最新ログ> || echo 0) && \
echo 'エントリー見送り:' && (grep -c 'エントリー見送り' ~/work/satosystem/src/logs/<BTCの最新ログ> || echo 0) && \
echo 'エントリー実行（実際の発注）:' && (grep -c 'エントリー実行\|注文送信\|ポジション取得\|Entry order' ~/work/satosystem/src/logs/<BTCの最新ログ> || echo 0) && \
echo '--- strategy_A 直近履歴 ---' && grep 'strategy_A' ~/work/satosystem/src/logs/<BTCの最新ログ> | tail -10 && \
echo '' && \
echo '=== XAUT シグナル統計 ===' && \
echo 'strategy_A BUY件数:' && grep -c 'strategy_A: BUY' ~/work/satosystem/src/logs/xaut/<XAUTの最新ログ> && \
echo 'strategy_A SELL件数:' && grep -c 'strategy_A: SELL' ~/work/satosystem/src/logs/xaut/<XAUTの最新ログ> && \
echo '全Strategy NONE件数:' && grep -c '全Strategy: NONE' ~/work/satosystem/src/logs/xaut/<XAUTの最新ログ> && \
echo 'Breakout BUY発生:' && (grep -c 'Breakout強度.*✓ BUY' ~/work/satosystem/src/logs/xaut/<XAUTの最新ログ> || echo 0) && \
echo 'Breakout SELL発生:' && (grep -c 'Breakout強度.*✓ SELL' ~/work/satosystem/src/logs/xaut/<XAUTの最新ログ> || echo 0) && \
echo '出来高不足(NG):' && (grep -c '相対出来高.*✗' ~/work/satosystem/src/logs/xaut/<XAUTの最新ログ> || echo 0) && \
echo 'ADX不足(NG):' && (grep -c 'ADX.*✗\|ADX不足' ~/work/satosystem/src/logs/xaut/<XAUTの最新ログ> || echo 0) && \
echo 'エントリー許可:' && (grep -c 'エントリー許可' ~/work/satosystem/src/logs/xaut/<XAUTの最新ログ> || echo 0) && \
echo 'エントリー見送り:' && (grep -c 'エントリー見送り' ~/work/satosystem/src/logs/xaut/<XAUTの最新ログ> || echo 0) && \
echo 'エントリー実行（実際の発注）:' && (grep -c 'エントリー実行\|注文送信\|ポジション取得\|Entry order' ~/work/satosystem/src/logs/xaut/<XAUTの最新ログ> || echo 0) && \
echo '--- strategy_A 直近履歴 ---' && grep 'strategy_A' ~/work/satosystem/src/logs/xaut/<XAUTの最新ログ> | tail -10
"
```

#### 5b. エントリー阻害フィルタの直近詳細

```bash
ssh raspberry_pi "
echo '=== BTC 直近フィルタ詳細（最新20件） ===' && \
grep -E 'Breakout強度|相対出来高|Range Breakout Enhanced|ADX|PVO|エントリー許可|エントリー見送り' ~/work/satosystem/src/logs/<BTCの最新ログ> | tail -20 && \
echo '' && \
echo '=== XAUT 直近フィルタ詳細（最新20件） ===' && \
grep -E 'Breakout強度|相対出来高|Range Breakout Enhanced|ADX|PVO|エントリー許可|エントリー見送り' ~/work/satosystem/src/logs/xaut/<XAUTの最新ログ> | tail -20
"
```

確認項目：
- `エントリー実行` が 0件 → 実際のポジション発注は一度もなし
- `エントリー見送り` の理由（出来高不足 / ADX不足 / strategy_A不一致）を特定
- Breakout発生回数に対してエントリー許可が何件あったか

### 6. 両BOTの最新ステータス確認

```bash
ssh raspberry_pi "
echo '=== BTC latest_status ===' && python3 -m json.tool ~/work/satosystem/src/logs/latest_status.json | head -40 && \
echo '' && \
echo '=== XAUT latest_status ===' && python3 -m json.tool ~/work/satosystem/src/logs/xaut/latest_status.json | head -40
"
```

確認項目（両BOT）：
- `updated_at` — 最後の更新時刻（BOT稼働確認）
- `decision` / `side` / `position_side` — 現在のシグナル・ポジション
- `pnl` / `total_pnl` — 損益
- `pvo_val` — PVO値
- `adx` — ADX値
- `dc_h` / `dc_l` — ドンチャン上限/下限

### 7. 並行動作の干渉確認

```bash
# RATE LIMITの同時発生確認（両BOTで14秒以内の同時発生 = API競合を示す）
ssh raspberry_pi "
echo '=== BTC RATE LIMIT タイムスタンプ ===' && grep 'RATE LIMIT' ~/work/satosystem/src/logs/<BTCの最新ログ> | grep -v '復帰' && \
echo '' && \
echo '=== XAUT RATE LIMIT タイムスタンプ ===' && grep 'RATE LIMIT' ~/work/satosystem/src/logs/xaut/<XAUTの最新ログ> | grep -v '復帰'
"
```

確認項目：
- 同じ時刻帯（数十秒以内）に両BOTが RATE LIMIT → **同一APIキー共有による競合**
- BTC ポジション保有中 + XAUT エントリー試行 → **証拠金干渉の可能性**

## 判定基準

### ✅ 正常の条件

| チェック項目 | 正常の目安 |
|---|---|
| ログのタイムスタンプ（両BOT） | 直近1〜2分以内のログがある |
| ERROR件数（各BOT） | 少数（3日間で30件未満）かつ全て自動回復 |
| RATE LIMIT | 自動回復している（`ERROR - 最新価格取得エラー復帰`が続く） |
| メインループエラー | 0件 または 1件（連続ではない） |
| ポジション未保有 | ドンチャンにブレイクアウトなし＋PVO≦0 なら静観が正常 |
| 残高 | 開始残高から大きく減少していない |
| RATE LIMIT同時発生 | 数十秒以内の同時RATE LIMITは許容（自動回復すれば正常） |

### ⚠️ 要注意の条件

| 状況 | 対応 |
|---|---|
| ログが5分以上止まっている | BOTクラッシュの可能性 → `bot.pid`でプロセス確認 |
| RATE LIMIT が回復しない（連続ERROR） | APIキーの制限超過 → 取引所ダッシュボード確認 |
| `メインループエラー` が複数 | 例外の原因を確認・Task 40g（API耐障害性）参照 |
| pnl がマイナスで急拡大 | ポジション状態と価格を確認 |
| **XAUTのERROR件数が数百件超** | 証拠金マイナスによる無限ループを疑う |
| **エントリー価格がXAUT値域外（例: 70000台）** | 価格データ混線バグ。実オーダーは0量なら実害なし |

### ❌ 緊急対応が必要な条件

| 状況 | 対応 |
|---|---|
| `証拠金-XX.XXが最低額0.0を下回ったので発注できません` が連続 | 証拠金マイナスループ発生中。BOTを手動停止・口座残高確認 |
| 両BOTが同時ポジション保有 + 合算証拠金モード | 強制清算リスク。片方のポジションを確認・クローズ検討 |
| メインループエラーが連続発生 | BOT再起動を検討 |

### エントリーが発生しない理由（正常な場合）

**BTC（Donchian Breakout + ADX31フィルタ）全条件が同時に必要**:
1. ドンチャン上/下限突破（`close > dc_h` または `close < dc_l`）
2. PVO > 10（出来高十分）
3. ADX ≥ 31（トレンド相場）
4. 新指標（strategy_A）の方向一致

**XAUT（Donchian Breakout + 出来高フィルタ）全条件が同時に必要**:
1. ドンチャン上/下限突破（`close > dc_h` または `close < dc_l`）
2. 相対出来高 ≥ 1.5x（出来高十分）
3. PVO > 0
4. ADX ≥ 26（トレンド相場）

### エントリーゼロが妥当かの判断基準

以下の観点でエントリーゼロが正常かを評価する：

| 判断軸 | 正常（エントリーなしが妥当） | 異常（要調査） |
|---|---|---||
| Breakout発生回数 | 0〜数件（レンジ相場） | 多数Breakoutなのにエントリーなし |
| 最大ブロックフィルタ | 出来高不足が大半 → 低ボラ相場の証拠 | ADX不足のみ → ドンチャン設定見直し検討 |
| strategy_A方向 | BUY/SELLがBreakout方向と不一致 | NONE連続 → シグナル計算バグの可能性 |
| ADX値（BTC） | 12〜25（レンジ相場、31未満なら正常） | 35以上なのにエントリーなし → 要確認 |
| ADX値（XAUT） | 44以上（トレンド強い）なのに出来高不足 → 正常 | ADX ≥ 26 かつ Breakout済みなのに見送り → バグ疑い |
| 稼働期間 | 数日〜数週間エントリーなしは許容範囲 | 1ヶ月以上Breakout自体が0件 → 設定確認 |

**エントリーゼロの結論を以下の形式で必ず述べること**：
- `✅ 妥当`：フィルタが正しく機能しており、市場条件がエントリー基準に達していない
- `⚠️ 要確認`：Breakoutは発生しているがフィルタで全件見送り → フィルタが厳しすぎる可能性
- `❌ バグ疑い`：エントリー許可が出ているのに発注0件 → ロジックバグ

### 並行動作の既知の問題（2026-04-08確認）

1. **Bybit API RATE LIMIT競合**: BTCとXAUTが同一BybitAPIキーを使用。同時呼び出しでRATE LIMIT頻発（自動回復するため実害は軽微）

2. **XAUT証拠金計算のバグ**: Bybit合算証拠金モードでBTCポジション損益がXAUT証拠金計算に影響し、証拠金がマイナスになる場合がある。発注量=0で実際の注文は通らないが、**エントリーシグナルが立っている間ループが止まらない**（数時間・数万件のERROR）

3. **XAUTのBTC価格・BTC単位表示バグ**: XAUTのエントリーログにBTCの価格（70000台）・単位（BTC）が表示される。実害なし（発注量=0）

## 出力フォーマット

分析後、以下の形式で報告する：

```
## ログ分析結果

### BTC BOT稼働状況 ✅/⚠️/❌
| 稼働開始 | YYYY-MM-DD HH:MM |
| 最新ログ | YYYY-MM-DD HH:MM |
| 動作サイクル | 毎分1回 正常/異常 |

### XAUT BOT稼働状況 ✅/⚠️/❌
| 稼働開始 | YYYY-MM-DD HH:MM |
| 最新ログ | YYYY-MM-DD HH:MM |
| 動作サイクル | 毎分1回 正常/異常 |

### シグナル・フィルタサマリ

**BTC**:
| 指標 | 値 | 判定 |
|---|---|---|
| strategy_A | BUY/SELL/NONE | ✅/⚠️ |
| 直近Breakout | BUY X件 / SELL X件 | ✅/⚠️ |
| 出来高フィルタ通過 | X/X件（全Breakout中） | ✅/❌ |
| ADXフィルタ通過 | X/X件（全Breakout中） | ✅/❌ |
| エントリー許可 | X件 | ✅/❌ |
| エントリー実行（実発注） | **X件** | ✅/❌ |

**XAUT**:
| 指標 | 値 | 判定 |
|---|---|---|
| strategy_A | BUY/SELL/NONE | ✅/⚠️ |
| 直近Breakout | BUY X件 / SELL X件 | ✅/⚠️ |
| 出来高フィルタ通過 | X/X件（全Breakout中） | ✅/❌ |
| ADXフィルタ通過 | X/X件（全Breakout中） | ✅/❌ |
| エントリー許可 | X件 | ✅/❌ |
| エントリー実行（実発注） | **X件** | ✅/❌ |

### エントリーゼロの妥当性評価
- 最大ブロック要因: 出来高不足 / ADX不足 / strategy_A不一致 / Breakout未達
- 判定: **✅ 妥当 / ⚠️ 要確認 / ❌ バグ疑い**
- 理由: （フィルタ別ブロック件数と現在の指標値を根拠に記述）

### エラーサマリ
| BOT | ERROR件数 | RATE LIMIT | メインループエラー |
|-----|-----------|------------|------------------|
| BTC  | X件 | X回（全て自動回復） | X件 |
| XAUT | X件 | X回（全て自動回復） | X件 |

### 並行動作チェック
- RATE LIMIT同時発生: あり/なし（○回・全て自動回復/未回復あり）
- ポジション重複: あり/なし（BTC: X側 / XAUT: X側）
- 証拠金干渉: 問題なし/要注意（内容）

### 現在の市場状況

**BTC**:
- 現在価格: XX,XXX USD
- ドンチャン上限（dc_h）: XX,XXX USD  （上限まで +X,XXX USD, X.X%）
- PVO: XX.XX / ADX: XX.XX / decision: NONE/ENTRY等

**XAUT**:
- 現在価格: X,XXX USD
- ドンチャン上限（dc_h）: X,XXX USD
- PVO: XX.XX / ADX: XX.XX / decision: NONE/ENTRY等

### 総合評価
両BOTは期待通りに動作しています / 要確認事項あり...

（エントリーゼロについて: ✅ 妥当 / ⚠️ 要確認 / ❌ バグ疑い、理由を一言で）
```
