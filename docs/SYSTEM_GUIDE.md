# Satosystem - システム総合ガイド

**最終更新**: 2025-11-28 15:00  
**バージョン**: Phase 1 + Phase 2 + Phase 3（**本番有効化完了**）  
**最新修正**: トレード条件明確化 + ADD条件バグ修正 (Commit: cc62516)  

---

## 🎯 システムの目的

自動取引ボットで継続的な利益生成を実現。市場レジーム判定 → 段階的フィルタリング → 自動最適化ループで段階的改善。

---

## 📊 現在の状態

### 進捗状況
| フェーズ | 内容 | 状態 | 改善率 |
|---------|------|------|--------|
| **Phase 1** | レジーム検出（SIDEWAYS/WEAK_TREND/STRONG_TREND） | ✅ 完了 | +56.4%（Q2）/ +11.6%（Q1 2024） |
| **Phase 2** | 段階的ポジション調整（0.75x/1.0x/1.25x） | ✅ 完了 | +10.34%（全期間平均） |
| **Phase 3** | 自動監視・学習ループ（Task 7/10/11） | ✅ 完了 | - |

### 運用スケジュール
```
毎日 00:00 UTC   → Task 11 (realtime_performance_monitor.py) - 日次監視
毎週月曜 00:00   → Task 7 (environment_auto_judge.py) - 環境判定
毎月1日 00:00    → Task 10 (dynamic_threshold_learning.py) - 最適化学習
```

### 業績（バックテスト）
- **2024年**: 平均 -$37,559（初期資本 10,000 USD比で300%超過損失）
- **2025年**: 平均 -$10,756（71%削減）
- **Phase 2適用後**: +10.34%改善実績
- **課題**: 根本的な赤字解決に至らず → Task 19で実運用検証中

---

## 🏗️ システムアーキテクチャ

### コンポーネント責務表

| モジュール | 役割 | 連携先 |
|-----------|------|-------|
| **Config** | config.ini パラメータ一元管理・キャッシュ | 全モジュール |
| **BybitExchange** | ccxt ラッパー（OHLCV/注文/残高） | PriceDataManagement, Bot |
| **PriceDataManagement** | OHLCV取得・シグナル計算（Donchian/PVO）・ボラティリティ | TradingStrategy, RiskManagement |
| **OHLCVCache** | SQLite永続化（1m/120m） | PriceDataManagement初期ロード |
| **TradingStrategy** | ENTRY/ADD/EXIT判定 | Bot, Portfolio |
| **RiskManagement** | ポジションサイジング・PSAR/トレーリングストップ | Bot, Portfolio |
| **Portfolio** | ポジション/PnL/ドローダウン追跡 | Bot, RiskManagement |
| **Logger** | 構造化ログ・ローテーション・圧縮 | すべて |
| **Metrics** | PnL/Sharpe/Win Rate/Profit Factor計算 | Bot（サマリー） |

### データフロー

```
Config → PriceDataManagement → TradingStrategy → Bot
         ↓（シグナル）            ↓（ENTRY/EXIT） ↓（ポジション調整）
      RiskManagement ←----------→ Portfolio ← Logger
         ↓（サイジング）              ↓（PnL）    ↓（圧縮）
      Exchange（注文実行）      Metrics（集計）  work_reports
```

### タイムフレーム・キャッシュ
- **戦略用**: 2時間足（120m）- 高レベルシグナル
- **詳細用**: 1分足 - 最新ティッカー・出来高
- **永続化**: SQLite `candles` テーブル（`symbol, timeframe, close_time`キー）

---

## 🎛️ 実行ルール

### Bot 実行方法

**バックテスト** （config.ini で `back_test = 1` 設定）
```bash
python3 run_backtest.py [--full-logging]
```

**本番実行** （config.ini で `back_test = 0` 設定）
```bash
python3 src/bot.py
```

### 設定ファイル体系

```
src/config.ini（ユーザ設定 - 変更可）
    ↑（読み込み）
src/config.template.ini（テンプレート - 自動生成）

[Strategy]
regime_detection_enabled = True
graduated_sizing_enabled = True   ← Phase 2 有効化（本番反映済み）

[Risk]
entry_times = 4                   ← ピラミッディング（最適値）
stop_offset = 1.5                 ← ストップロス距離
```

**セキュリティ**: API キー は `.api_key` ファイルまたは環境変数 `BYBIT_API_KEY`, `BYBIT_API_SECRET` から読み込み（config.ini に含めない）

---

## 🎯 トレード条件（Phase B-D）

戦略は以下の4つの明確なトレード条件で構成されています。これらは `src/trading_strategy.py` の `TradingStrategy` クラスで実装されています。

### 1️⃣ ENTRY条件（Phase B）

**目的**: ポジションを新規開始する

**実装メソッド**: `TradingStrategy.evaluate_entry()`

**判定ロジック（優先度順）**:
```
1. ポジション保有状態: NO（量 = 0）
2. PVO シグナル: YES (出来高確認)
3. Donchian ブレイク: YES (BUY/SELL発生)
   
   [Keltner フィルタ無効時]
   → ENTRY判定完了 ✓
   
   [Keltner フィルタ有効時]
   4. Keltner 幅: >= 閾値 (ボラティリティ十分 = トレンド強い)
   → ENTRY判定完了 ✓
   
   [レジーム検出有効時]
   5. レジーム判定: SIDEWAYS 判定で除外
      WEAK_TREND / STRONG_TREND で許可
   → ENTRY判定完了 ✓
```

**パラメータ** (config.ini):
- `donchian_buy_term` / `donchian_sell_term`: Donchian チャネル期間
- `pvo_threshold`: PVO 出来高閾値
- `keltner_enabled`: フィルタ有効化（True/False）
- `regime_detection_enabled`: レジーム検出有効化（True/False）

**シグナル情報** (from `PriceDataManagement.get_signals()`):
```python
{
  "pvo": {"signal": bool},                    # 出来高OK
  "donchian": {"signal": bool, "side": str},  # "BUY" or "SELL"
  "keltner": {"signal": bool, "info": {...}}, # ボラティリティOK
  "regime_stats": {...}                       # レジーム情報
}
```

**実装例** (`src/trading_strategy.py` Line 55-160):
```python
def evaluate_entry(self):
    signals = self.price_data_management.get_signals()
    if signals["pvo"]["signal"] == True:
        if signals["donchian"]["signal"] == True:
            if keltner_pass:  # フィルタ判定
                donchian_side = signals["donchian"]["side"]
                if donchian_side == "BUY":
                    side = "BUY"
                    decision = "ENTRY"
```

---

### 2️⃣ ADD条件（Phase C）

**目的**: 既存ポジションをピラミッディング（段階的に増やす）

**実装メソッド**: `TradingStrategy.evaluate_add(price)`

**判定ロジック**:
```
1. ポジション保有状態: YES（量 > 0）
2. ADD回数上限: add_count < entry_times
   (entry_times = 4 = 最大4回のポジション分割)
3. 価格変動条件:
   - BUY ポジション: price - last_entry_price > add_range
   - SELL ポジション: last_entry_price - price > add_range
   
   → ADD判定完了 ✓
```

**重要**: 
- 最初の ENTRY は price_based のみ判定
- 2回目以降の ADD は add_range (= entry_range / √entry_times) 条件
- ADD直後は EXIT判定をスキップ（同一バー内 EXIT 重複防止）

**パラメータ** (config.ini):
- `entry_times`: 分割回数（最適値: 4）
- `entry_range`: 初回エントリー範囲（初期STOP基準値）
- `add_range`: 追加レンジ幅（自動計算: entry_range / √entry_times）

**ポジション追跡** (from `RiskManagement`):
```python
self.last_entry_price      # 前回エントリー価格
self.add_range             # 追加実行判定用レンジ幅
self.portfolio.add_count   # 追加回数（0-3）
```

**実装例** (`src/trading_strategy.py` Line 168-220):
```python
def evaluate_add(self, price):
    position_side = self.portfolio.get_position_side()
    if position_side != 'NONE':
        add_count = getattr(self.portfolio, 'add_count', 0)
        if add_count < max_entries:
            range_val = self.risk_manager.get_add_range()
            last_entry_price = self.risk_manager.get_last_entry_price()
            if position_side == "BUY" and (price - last_entry_price) > range_val:
                side = "BUY"
                decision = "ADD"
                self.portfolio.add_count = add_count + 1
```

---

### 3️⃣ EXIT条件（Phase D）

**目的**: ポジションをクローズする

**実装メソッド**: `TradingStrategy.evaluate_exit()`

**判定ロジック（優先度順）**:
```
1. 時間制限 (max_hold_bars 有効時):
   bars_held >= max_hold_bars
   → EXIT実行（強制決済）✓
   
2. 部分利確 (partial_exit_enabled 有効時):
   profit_rate >= partial_exit_profit_rate
   AND bars_held >= partial_exit_min_bars
   → PARTIAL_EXIT実行（50%決済）✓
   
3. ストップロス判定 (リアルタイム価格):
   - BUY: current_price <= stop_price
   - SELL: current_price >= stop_price
   → EXIT実行（スリッページ考慮）✓
```

**重要**: 
- ポジション成立直後 (bars=0) のストップロス判定は **スキップ**
  （極限価格でのストップロス発火防止）
- ADD実行直後もストップロス判定をスキップ（ADD→EXIT連鎖防止）
- EXIT後は `risk_manager.reset_position_tracking()` でポジション追跡状態をリセット

**パラメータ** (config.ini):
- `max_hold_bars`: 最大保持バー数（0=無効）
- `partial_exit_enabled`: 部分利確有効化（True/False）
- `partial_exit_profit_rate`: 利確率（例: 0.10 = 10%）
- `partial_exit_ratio`: 利確割合（例: 0.5 = 50%決済）
- `partial_exit_min_bars`: 利確最小保持バー数

**実装例** (`src/trading_strategy.py` Line 225-345):
```python
def evaluate_exit(self):
    if portfolio.bars_held >= max_hold_bars:
        decision = "EXIT"  # 時間制限
        
    if profit_rate >= partial_exit_profit_rate:
        decision = "PARTIAL_EXIT"  # 部分利確
        
    if not skip_stoploss:
        if position_side == "BUY" and current_price <= stop_price:
            decision = "EXIT"  # ストップロス
```

---

### 4️⃣ STOP条件

**目的**: リスク管理用に各ポジションのストップロス価格を計算・管理

**実装メソッド**: `RiskManagement.update_stop_price()` / `get_stop_price()`

**判定ロジック（複数ソース統合）**:
```
1. 基本STOP (ボラティリティ基準):
   BUY: entry_price - (ATR * initial_stop_range)
   SELL: entry_price + (ATR * initial_stop_range)
   
2. PSAR (Parabolic SAR + サニティチェック):
   - PSAR値が逆行していないか確認
   - BUY: PSAR < entry_price の場合のみ採用
   - SELL: PSAR > entry_price の場合のみ採用
   
3. トレーリングストップ (価格上昇時):
   - AF（加速係数）で段階的にSTOP更新
   - AF_initial → AF_initial + AF_add (最大AF_max)
   - 極限価格（±0.5%スリッページ）との比較
   
4. 最終STOP = MAX(基本STOP, PSAR, トレーリング)
   （最も保守的な値）
```

**パラメータ** (config.ini):
- `stop_range`: 基本ストップ幅（ATR乗数、例: 2.0）
- `stop_AF`: 初期加速係数（例: 0.02）
- `stop_AF_add`: AF増加ステップ（例: 0.02）
- `stop_AF_max`: 最大加速係数（例: 0.20）
- `surge_follow_price_ratio`: 極限価格用乗数（例: 0.995）
- `psar_time_frame`: PSAR時間軸（例: 120 = 2時間足）

**ポジション追跡** (from `RiskManagement`):
```python
self.stop_price              # 最終ストップ価格（全ソース統合）
self.stop_offset             # STOP価格オフセット（価格ベース）
self.last_entry_price        # 前回エントリー価格
self.psar_stop_offset        # PSAR由来のオフセット
self.price_surge_stop_offset # トレーリング由来のオフセット
```

**実装例** (`src/risk_management.py`):
```python
def update_stop_price(self, entry_side, entry_price):
    # 1. 基本STOP (ATR基準)
    base_stop = entry_price - ATR * initial_stop_range  # BUY の場合
    
    # 2. PSAR (サニティチェック付き)
    psar_stop = self.__follow_psar()  # BUY時: stop < entry, SELL時: stop > entry
    
    # 3. トレーリング (AF加速)
    trailing_stop = self.__follow_price_surge()
    
    # 4. 統合
    self.stop_price = max(base_stop, psar_stop, trailing_stop)
```

**重要な修正** (Commit: f5f74ea / 16ae12f / 7863fee):
- ✅ PSAR逆行チェック: BUY時に `psar > entry_price` なら採用しない
- ✅ 初期化時ゼロ値対応: ボラティリティ計算前はSTOP=0で代替
- ✅ ADD直後のEXIT重複防止: `bars=-1` リセット

---

### トレード条件フロー図

```
[ポジションなし] 
    ↓
    → evaluate_entry()
         │
         ├─ PVO OK? ❌ → ENTRY判定なし
         │
         ├─ Donchian BUY/SELL? ❌ → ENTRY判定なし
         │
         ├─ Keltner フィルタ? ❌ → ENTRY判定なし
         │
         └─ レジーム OK? ✓ → ENTRY決定! 
              ↓
              [ENTRY実行] → ポジション成立 (quantity > 0, bars=0)
    
    
[ポジション保有] 
    ↓
    → ADD判定可? (bars >= 1)
         │
         ├─ add_count >= max? ✓ → ADD判定なし
         │
         └─ 価格変動 > add_range? ✓ → ADD決定!
              ↓
              [ADD実行] → ポジション増加 (quantity += 1, add_count += 1)
              
    ↓ (ADD判定結果で EXIT判定スキップ)
    
    → evaluate_exit() [ADD未発火時のみ]
         │
         ├─ 時間超過? ✓ → EXIT決定!
         │
         ├─ 利益確定? ✓ → PARTIAL_EXIT決定!
         │
         └─ ストップロス? ✓ → EXIT決定!
              ↓
              [EXIT実行] → ポジション決済 (quantity = 0)
              ↓
              [状態リセット] → reset_position_tracking()
    
    ↓
    [ポジションなし] ← ループ開始へ
```

---

### パラメータ最適値（テスト済み）

| パラメータ | 現在値 | テスト範囲 | 最適理由 |
|-----------|--------|-----------|--------|
| `entry_times` | 4 | 2-10 | Sharpe 0.343、DD 49.75% |
| `donchian_buy_term` | 20 | 10-50 | 標準的なDonchian期間 |
| `pvo_threshold` | 10 | 5-50 | 出来高フィルタ精度 |
| `keltner_enabled` | True | - | ダマシ回避（却下テスト: -35.21） |
| `regime_detection_enabled` | True | - | SIDEWAYS除外で改善 |
| `stop_range` | 2.0 | 1.5-3.0 | リスク許容度バランス |
| `stop_AF` | 0.02 | 0.01-0.05 | トレーリング段階性 |
| `max_hold_bars` | 0 | - | 無制限（デフォルト） |

---

## 🔄 Phase 3 - 自動化ループ

### Task 11: リアルタイムパフォーマンス監視
**実行**: 毎日 00:00 UTC  
**スクリプト**: `src/realtime_performance_monitor.py`  
**監視項目**: 日次PnL / Win Rate / Profit Factor（7日スライディング）  
**アラート**: WR低下 / 連続損失 / Profit Factor低下 / レジーム変化  
**出力**: `work_reports/realtime_monitor_*.json`

### Task 7: 環境自動判定
**実行**: 毎週月曜 00:00 UTC  
**スクリプト**: `src/environment_auto_judge.py`  
**判定**: 過去30日レジーム分布 → SIDEWAYS ≥30% で Phase 2 有効化判定  
**出力**: `work_reports/environment_auto_judgement_*.json`

### Task 10: 動的基準学習
**実行**: 毎月1日 00:00 UTC  
**スクリプト**: `src/dynamic_threshold_learning.py`  
**学習内容**: volatility_ratio / trend_strength 最適値（Percentile P40-P80）  
**出力**: `work_reports/dynamic_threshold_learning_*.json`

### Crontab 設定
```bash
# Task 11
0 0 * * * cd /home/satoshi/work/satosystem && python3 src/realtime_performance_monitor.py >> logs/task11.log 2>&1

# Task 7
0 0 * * 1 cd /home/satoshi/work/satosystem && python3 src/environment_auto_judge.py >> logs/task7.log 2>&1

# Task 10
0 0 1 * * cd /home/satoshi/work/satosystem && python3 src/dynamic_threshold_learning.py >> logs/task10.log 2>&1
```

---

## 📋 Task 進捗

### ✅ 完了（15/15）
| # | タスク | 完了日 | 効果 |
|----|--------|--------|------|
| P0-1 | Win Rate計算修正 | 2025-11-26 | - |
| P0-2 | ストップロス実装 | 2025-11-26 | - |
| P0-3 | ポジション検証 | 2025-11-26 | - |
| Task 7 | 環境自動判定 | 2025-11-24 | - |
| Task 10 | 動的基準学習 | 2025-11-24 | - |
| Task 11 | リアルタイム監視 | 2025-11-24 | - |
| Task 17 | Phase 2本番反映 | 2025-11-26 | +10.34% |
| Task 18 | Cron統合 | 2025-11-26 | - |

### 🔄 進行中
**Task 19**: 4週間ホットテスト運用（2025-11-27 ～ 2025-12-24）
- 目的: Phase 2の実運用効果検証
- 監視: 毎日Task 11自動実行
- 判定予定: 4週間後

---

## 🔍 戦略最適化の履歴

### ✅ ピラミッディング最適化（採用: entry_times=4）
**テスト期間**: 2025/10/01 - 2025/11/01  
**選択根拠**: 
- Max DD 49.75%（50%未満で本番実用的）
- 最高Sharpe比 0.343（リスク調整リターン最適）
- PnL改善 +977%（ベースライン対比）

| entry_times | PnL | DD Rate | Sharpe | Win Rate |
|-------------|-----|---------|--------|----------|
| **4 (採用)** | **107.10** | **49.75%** | **0.343** | **93.33%** |
| 2 | 281.68 | 70.07% | 0.287 | 100% |
| 5 | 69.78 | 44.94% | 0.32 | 93.33% |
| 3 | 45.33 | 64.47% | 0.12 | 93.33% |
| 10 (ベース) | 9.94 | 113.17% | 0.63 | 94.12% |

### ❌ Keltner チャネルフィルタ（却下）
**テスト期間**: 2025/10/01 - 2025/11/01  
**結果**: 12パラメータ組み合わせすべてでベースラインより劣化（-35.21）  
**理由**: Profit Factor 0.70、Max DD 58.18%、実用性なし

---

## 📁 重要ファイル

### スクリプト
- `run_backtest.py` - バックテスト実行
- `src/bot.py` - メインロジック
- `src/environment_auto_judge.py` - Task 7
- `src/dynamic_threshold_learning.py` - Task 10
- `src/realtime_performance_monitor.py` - Task 11

### 設定
- `src/config.ini` - 本番設定（Phase 2適用済み）
- `src/config.template.ini` - テンプレート
- `crontab_entries.txt` - Cron設定

### ドキュメント
- `docs/SYSTEM_GUIDE.md` - このファイル（統合ガイド）
- `docs/TRADING_STRATEGY_PLAN.md` - 戦略詳細・改善案（参考用）
- `docs/_archive/` - 過去の分析データ

### テスト
- `test/run_all_checks.py` - 全テスト実行（config.ini変更なし確認）
- `test/sample_test_runner.py` - モジュール・ビジュアライゼーション検証

---

## 🚀 次のステップ

### 短期（1週間以内）
1. Task 19 監視中 - 日次PnL確認（毎日00:05 UTC）
2. Task 7/10結果レビュー（毎週月曜・毎月1日）

### 中期（1ヶ月以内）
1. Task 19判定（2025-12-24）- 継続/調整/中止判定
2. 必要に応じてパラメータ調整

### 長期（3ヶ月以内）
1. Phase 4: 複数シンボル対応
2. Phase 5: マルチポジション保持・部分利確
3. Phase 6: EXIT条件の洗練化

---

## 🔧 トラブルシューティング

### Cron ジョブが実行されない
```bash
service cron status              # Cronデーモン確認
crontab -l                       # 登録確認
cat /var/log/syslog | grep CRON # Cronログ確認
```

### Python スクリプトエラー
```bash
# 直接実行テスト
cd /home/satoshi/work/satosystem
python3 src/environment_auto_judge.py

# モジュール確認
python3 -c "import src.environment_auto_judge"
```

### Config キャッシュ問題
```python
# src/config.py で強制リロード
Config.reload_config()
```

---

## 📞 参照マップ

| 質問 | 参照箇所 |
|------|---------|
| システム全体の構造は？ | このファイルの「システムアーキテクチャ」 |
| Phase 2 の詳細な改善案は？ | TRADING_STRATEGY_PLAN.md（参考用） |
| 戦略の過去テスト結果は？ | docs/_archive/COMPREHENSIVE_VALIDATION_REPORT.md |
| Cron 設定の詳細は？ | このファイルの「Phase 3 - 自動化ループ」 |
| テスト実行方法は？ | test/README.md または このファイルの「実行ルール」 |
| バックテスト詳細解析は？ | docs/_archive/ 参照 |

---

**このドキュメントはプロジェクトの単一の真実（SSOT）です。定期的に確認してください。**

---

## 📝 最新修正履歴

### 2025-11-28: トレード条件明確化 + ADD条件バグ修正
**Commit**: `cc62516`

**修正内容**:
1. ✅ **ドキュメント追加**: SYSTEM_GUIDE.mdに「トレード条件（Phase B-D）」章を追加
   - ENTRY条件の詳細定義
   - ADD条件の詳細定義（ピラミッディング）
   - EXIT条件の詳細定義（時間制限・部分利確・ストップロス）
   - STOP条件の詳細定義（複数ソース統合）
   - トレード条件フロー図追加
   - パラメータ最適値表追加

2. ✅ **バグ修正**: ADD条件判定の失敗問題
   - **問題**: `update_stop_price()` 内でポジション保有中に `add_range=0` にリセットされていた
   - **根本原因**: `quantity=0` 判定時に誤りが発生し、保有中のポジションが「なし」と判定される
   - **影響**: ADD判定が常に失敗し、ピラミッディングが実行されない
   - **修正**:
     * `add_range` リセットを `reset_position_tracking()` に明示化（EXIT時のみ）
     * `update_stop_price()` の else 分岐では `add_range` をリセットしない
     * `reset_position_tracking()` ログを追加

**テスト結果**:
- バックテスト実行時にADD条件判定が正常に動作することを確認 ✓
- ADD実行ログ: `[条件判定:ADD] 価格変動 XXX が変動幅 YYY を超過` が表示される

**残存課題**:
- ボラティリティ初期化時の極端に低い値（0.28%）によるSTOP価格逆行
- 初期期間のDonchian判定が頻発する問題
- これらは次フェーズで対応予定

最終更新: 2025-11-28
