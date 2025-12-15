# 指値注文機能追加のためのシステム統合分析

**作成日**: 2025-12-14  
**対象**: bybit_exchange.py への指値注文機能追加  
**分析範囲**: bybit_exchange、trading_strategy、price_data_management、bot、risk_management、portfolio

---

## 1. 各モジュール分析概要

### 1.1 bybit_exchange.py（交換層）
**責務**: Bybit取引所との通信、注文実行  
**主要メソッド**:
- `__init__`: CCXT ライブラリを使用した取引所初期化
- `execute_order()`: 市場注文・指値注文の発行（現在：市場注文のみ）
- `fetch_ohlcv()`: 過去の価格データ取得
- `fetch_latest_ohlcv()`: 最新の未確定 OHLCV データ取得
- `fetch_ticker()`: 最新ティック価格取得
- `get_account_balance()`: 口座残高取得

**現在の注文実装**:
```python
# execute_order() の内部ロジック
if order_type == 'market':
    self.exchange.create_market_order(...)
elif order_type == 'limit':
    self.exchange.create_limit_order(...)
```

**問題点**:
- 指値注文の戻り値処理が不完全
- 注文の約定確認メカニズムがない
- 約定されない指値注文のキャンセル処理がない

---

### 1.2 trading_strategy.py（戦略層）
**責務**: トレード決定ロジック（エントリー、ピラミッディング、イグジット）  
**主要メソッド**:
- `evaluate_entry()`: エントリー条件評価（Donchian Channel、PVO）
- `evaluate_add()`: ピラミッディング条件評価
- `evaluate_exit()`: イグジット条件評価（ストップロス優先）
- `make_trade_decision()`: 総合判定

**戦略体系**:
- Strategy A: ADXベース市場レジーム検出
- Strategy B: Bollinger Bands + RSI + SMA複合指標
- Strategy C: 全指標統合

**トレード決定の流れ**:
```
evaluate_entry() → 条件チェック
                 → signal/strategy/confidenceを返す
                 → TradingStrategy.trade_decision に格納
```

**問題点**:
- トレード決定は「市場注文」前提で設計
- 指値注文の成行落ちやキャンセル判定がない
- 約定待ちの状態管理がない

---

### 1.3 price_data_management.py（価格データ層）
**責務**: OHLCV データの取得・管理・キャッシング  
**主要メソッド**:
- `initialize()`: BybitExchange、OHLCVCache の初期化
- `update_price_data()`: リアルタイム価格更新
- `update_price_data_backtest()`: バックテスト用価格更新
- `get_latest_ohlcv()`: 最新 OHLCV データ取得
- `get_signals()`: トレードシグナル（Donchian、PVO）取得

**データフロー**:
```
BybitExchange.fetch_latest_ohlcv()
    ↓
PriceDataManagement.update_price_data()
    ↓
RiskManagement (指標計算) / TradingStrategy (シグナル評価)
```

**問題点**:
- リアルタイムデータ更新の周期管理が必要
- 指値注文成行落ちへの対応がない
- 約定確認までの時間経過追跡がない

---

### 1.4 bot.py（ボット層）
**責務**: メインループ、注文実行制御、PnL 管理  
**主要メソッド**:
- `run()`: ボットメインループ
- `execute_order()`: Order オブジェクトを exchange に渡す

**実行フロー**:
```
while:
  update_price_data()
  make_trade_decision()
  if trade_signal:
    execute_order(Order)
  update_risk_status()
  log_trade_data()
```

**問題点**:
- `execute_order()` は市場注文即時実行のみ
- 指値注文の成行落ち時の処理がない
- 注文状態追跡機能がない
- 約定から決済までの管理が不十分

---

### 1.5 risk_management.py（リスク管理層）
**責務**: ポジションサイズ、ストップロス、テクニカル指標計算  
**主要メソッド**:
- `calculate_position_size()`: リスク比率から数量計算
- `update_risk_status()`: ストップ価格更新（Parabolic SAR）
- `evaluate_all_strategies()`: A/B/C 全ストラテジー評価
- `get_donchian_high()`, `get_donchian_low()`: ドンチャン計算
- `get_bb_upper()`, `get_bb_lower()`: ボリンジャーバンド計算

**テクニカル指標**:
- Parabolic SAR（ストップ価格）
- ADX（トレンド強度）
- Bollinger Bands（ボラティリティ）
- RSI（買われ過ぎ/売られ過ぎ）

**問題点**:
- ポジションサイズ計算は「最初のエントリー」のみ
- 指値注文の部分約定への対応がない
- 約定後のリスク再計算が必要

---

### 1.6 portfolio.py（ポジション管理層）
**責務**: ポジション保有情報、利益損失追跡  
**主要メソッド**:
- `get_position_quantity()`: 保有ポジション数量
- `get_position_side()`: 保有ポジション方向（LONG/SHORT）
- `get_position_price()`: 平均建値
- `add_position_quantity()`: ポジション追加（ピラミッディング）
- `clear_position_quantity()`: ポジション決済
- `get_profit_and_loss()`: P&L 計算

**管理情報**:
```python
self.positions = {
    'BTC/USD': {
        'quantity': 1.0,
        'side': 'LONG',
        'entry_price': 45000.0,
        'entry_count': 1
    }
}
```

**問題点**:
- 指値注文の「部分約定」追跡がない
- 複数枚建てのロット管理がない
- 約定時刻の記録がない

---

## 2. 依存関係マップ

```
Bot.run()
  ├→ PriceDataManagement.update_price_data()
  │   ├→ BybitExchange.fetch_latest_ohlcv()
  │   ├→ BybitExchange.fetch_ohlcv()
  │   └→ BybitExchange.fetch_ticker()
  │
  ├→ RiskManagement.update_risk_status()
  │   ├→ PriceDataManagement (OHLCV データ)
  │   ├→ Portfolio (ポジション情報)
  │   └→ NewIndicators (テクニカル指標)
  │
  ├→ TradingStrategy.make_trade_decision()
  │   ├→ RiskManagement (指標)
  │   ├→ PriceDataManagement (シグナル)
  │   ├→ Portfolio (ポジション)
  │   └→ ExitStrategyV2 (イグジット判定)
  │
  └→ Bot.execute_order(order)
      ├→ BybitExchange.execute_order()
      │   └→ ccxt.bybit.create_limit_order()
      │       or ccxt.bybit.create_market_order()
      │
      └→ Portfolio (ポジション更新)
```

---

## 3. 指値注文機能追加の課題

### 3.1 現在の実装上の問題点

#### ① 注文状態管理の欠落
**現状**:
- `execute_order()` は注文発行後、即座に約定と仮定
- 指値注文の約定確認メカニズムがない
- 注文 ID の追跡がない

**影響**:
- 成行落ちした指値注文の検出ができない
- 部分約定の扱いが不明確
- 注文キャンセル機能がない

#### ② ポジション管理の単純さ
**現状**:
- Portfolio は単一ロットのポジション管理のみ
- 約定時刻、約定数量の記録がない
- ピラミッディングは追加購入のみで、複数ロット管理がない

**影響**:
- 指値注文の部分約定時の平均建値計算が困難
- 複数枚注文の約定確認が複雑化
- 税務報告（トレード履歴）に不十分

#### ③ トレード決定ロジックの融硬さ
**現状**:
- `make_trade_decision()` は「即座に実行」を想定
- 指値注文の成行落ちへの対応判定がない
- 注文有効期限（Time in Force）の概念がない

**影響**:
- 成行落ちした指値注文の再検討ロジックが必要
- エグジット条件の再評価が複雑化
- トレード開始・中断の状態遷移が不明確

#### ④ リスク管理の限定的対応
**現状**:
- ストップロス価格は「現在のポジション」基準
- 未約定の指値注文に対する事前ストップ設定がない
- 部分約定時の段階的ストップ更新がない

**影響**:
- 指値注文発行時のリスク計算が不正確
- エグジット時の計算ロジックが複雑化

---

### 3.2 技術的実装上の課題

#### ① CCXT の limit_order API との整合性
**現在の実装**:
```python
def execute_order(self, side, quantity, price, order_type):
    if order_type == 'limit':
        result = self.exchange.create_limit_order(
            symbol, order_type, side, quantity, price
        )
    return result
```

**問題**:
- `result` は CCXT の戻り値（order オブジェクト）
- order ID を保持しているが、使用されていない
- Time in Force（IOC、GTC）の指定がない

#### ② 約定確認メカニズムの欠落
**必要な機能**:
- `fetch_order(order_id)`: 単一注文状態確認
- `fetch_orders(symbol)`: 複数注文状態確認
- タイムアウト判定（例：10分指値）
- 部分約定の追跡

#### ③ 再エントリー処理の複雑化
**指値注文成行落ち時の処理**:
```
成行落ち判定
  → 前回注文のキャンセル
  → 市場注文への切り替え判定
    または
  → 価格調整して再発行
```

---

## 4. 改善設計方針

### 4.1 推奨アーキテクチャ

#### Phase 1: 注文状態管理層の追加

**新ファイル**: `order_manager.py`

```python
class OrderManager:
    """注文の状態追跡とライフサイクル管理"""
    
    def __init__(self, exchange, logger):
        self.pending_orders = {}  # order_id -> order_info
        self.order_history = []
        
    def create_limit_order(self, symbol, side, quantity, price):
        """指値注文発行"""
        order = self.exchange.create_limit_order(...)
        self.pending_orders[order['id']] = {
            'order': order,
            'created_at': time.time(),
            'status': 'open',
            'filled': 0.0,
            'remaining': quantity
        }
        return order['id']
    
    def check_order_status(self, order_id):
        """注文状態確認（CCXT fetch_order）"""
        order = self.exchange.fetch_order(order_id)
        self.pending_orders[order_id]['status'] = order['status']
        self.pending_orders[order_id]['filled'] = order['filled']
        return order
    
    def cancel_order(self, order_id):
        """注文キャンセル"""
        result = self.exchange.cancel_order(order_id)
        self.pending_orders[order_id]['status'] = 'canceled'
        return result
    
    def is_timed_out(self, order_id, timeout_sec=600):
        """タイムアウト判定"""
        created = self.pending_orders[order_id]['created_at']
        return (time.time() - created) > timeout_sec
```

#### Phase 2: ポジション管理の強化

**拡張**: `portfolio.py`

```python
class Portfolio:
    def __init__(self):
        # 既存
        self.positions = {}  
        
        # 追加: 注文ロットの追跡
        self.pending_orders = {
            'order_id': {
                'symbol': 'BTC/USD',
                'side': 'BUY',
                'quantity': 1.0,
                'price': 45000,
                'filled': 0.5,
                'status': 'open'
            }
        }
        
        # 追加: トレード履歴（約定ロット）
        self.trade_history = [
            {
                'order_id': 'xxx',
                'symbol': 'BTC/USD',
                'side': 'BUY',
                'quantity': 0.5,
                'price': 45000,
                'filled_price': 45010,
                'filled_at': 1702500000,
                'commission': 10
            }
        ]
    
    def add_pending_order(self, order_id, symbol, side, quantity, price):
        """未約定注文を記録"""
        self.pending_orders[order_id] = {...}
    
    def update_pending_order(self, order_id, filled, status):
        """部分約定を反映"""
        ...
    
    def execute_pending_order(self, order_id, filled_quantity, filled_price):
        """注文の約定をポジションに反映"""
        ...
    
    def get_position_with_pending(self, symbol):
        """ポジション + 未約定数の合計"""
        ...
```

#### Phase 3: トレード決定の状態遷移化

**拡張**: `trading_strategy.py`

```python
class TradingStrategy:
    
    def __init__(self, ...):
        # 状態管理
        self.order_state = 'idle'  # idle -> order_pending -> filled -> closed
        self.pending_order_id = None
        
    def evaluate_entry_with_order_state(self):
        """状態に応じたエントリー判定"""
        if self.order_state == 'idle':
            # 通常のエントリー判定
            return self.evaluate_entry()
        
        elif self.order_state == 'order_pending':
            # 注文待機中: キャンセル判定
            # - 市場が逆向き
            # - 指値が成行落ち（タイムアウト）
            # → キャンセル & 市場注文切り替え判定
            return self.evaluate_pending_order_status()
        
        elif self.order_state == 'filled':
            # 部分約定: ピラミッディング判定
            return self.evaluate_add()
    
    def evaluate_pending_order_status(self):
        """指値注文の成行落ち判定"""
        current_price = self.price_data_management.get_ticker()
        
        # Strategy: 価格が逆向きに○○ pips 以上動いたら成行落ちと判定
        if current_price > entry_price + reversal_threshold:
            # キャンセル & 市場注文実行判定
            return {
                'signal': 'CANCEL_AND_SWITCH',
                'order_type': 'market',
                'reason': 'price_reversal'
            }
```

#### Phase 4: Bot の注文実行ロジック更新

**拡張**: `bot.py`

```python
def run(self):
    while True:
        # ...
        trade_decision = self.strategy.make_trade_decision()
        
        if trade_decision['signal'] == 'BUY' or 'SELL':
            order_type = trade_decision.get('order_type', 'limit')
            
            if order_type == 'limit':
                # 指値注文
                order_id = self.order_manager.create_limit_order(...)
                self.strategy.order_state = 'order_pending'
                self.strategy.pending_order_id = order_id
                
            elif order_type == 'market':
                # 市場注文（即座に実行）
                self.execute_order(order)
                self.strategy.order_state = 'filled'
        
        elif trade_decision['signal'] == 'CANCEL_AND_SWITCH':
            # 指値成行落ち → 市場注文切り替え
            self.order_manager.cancel_order(self.strategy.pending_order_id)
            self.execute_order(...)  # 市場注文
            self.strategy.order_state = 'filled'
        
        # 注文状態確認（毎ループ）
        if self.strategy.order_state == 'order_pending':
            order_status = self.order_manager.check_order_status(
                self.strategy.pending_order_id
            )
            if order_status['status'] == 'closed':
                self.portfolio.execute_pending_order(...)
                self.strategy.order_state = 'filled'
            elif self.order_manager.is_timed_out(...):
                # タイムアウト処理
                ...
```

---

### 4.2 実装優先順位

| フェーズ | 対象 | 難度 | 効果 | 所要時間 |
|---------|------|------|------|---------|
| **1** | OrderManager（注文状態管理） | 中 | 高 | 2-3h |
| **2** | Portfolio 拡張（ロット管理） | 中 | 高 | 3-4h |
| **3** | TradingStrategy 拡張（状態遷移） | 高 | 中 | 4-5h |
| **4** | Bot 更新（注文実行制御） | 中 | 高 | 3-4h |
| **5** | テスト & デバッグ | 高 | 高 | 5-8h |

**合計見積**: 17-24 時間

---

## 5. 実装上の注意点

### 5.1 CCXT の制限事項
- Bybit の API タイムアウト: 30秒
- `fetch_order()` の呼び出し頻度制限（60回/分）
- 約定確認のレイテンシ（1-5秒）

### 5.2 エラーハンドリング
```python
try:
    order = self.exchange.create_limit_order(...)
except ccxt.InsufficientBalance:
    # 余剰資金不足
    logging.error("Insufficient balance")
except ccxt.InvalidOrder:
    # 無効な注文（価格範囲外など）
    logging.error("Invalid order parameters")
except ccxt.NetworkError:
    # ネットワーク遅延
    retry_count += 1
```

### 5.3 テスト戦略
- **ユニットテスト**: OrderManager、Portfolio 拡張
- **統合テスト**: Bot.run() での指値注文フロー
- **バックテスト**: 過去データでの指値注文シミュレーション
- **ペーパートレード**: バックテスト後、実環境前のシミュレーション

---

## 6. 結論

### 現状の課題まとめ

| 課題 | 影響度 | 解決策 |
|------|--------|--------|
| 注文状態管理の欠落 | **高** | OrderManager クラス導入 |
| ポジション管理の単純さ | **中** | Portfolio にロット履歴機能追加 |
| トレード決定の融硬さ | **中** | 状態遷移パターン導入 |
| リスク管理の限定性 | **中** | 部分約定時のリスク再計算 |

### 推奨実装パス

1. **短期（1週間）**: OrderManager + Portfolio 拡張 → 基本的な指値注文機能
2. **中期（2週間）**: TradingStrategy + Bot 統合 → 状態遷移的な実行制御
3. **長期（3週間）**: テスト、バックテスト、本番化

### 期待効果

- ✅ より低い約定価格でのエントリー
- ✅ スリッページの削減
- ✅ 注文成行落ち時の自動復帰
- ✅ トレード履歴の詳細記録
- ✅ 複雑なポジション管理への対応

---

**このドキュメントは分析ベースです。実装時は要件定義とテスト計画を並行して進めてください。**
