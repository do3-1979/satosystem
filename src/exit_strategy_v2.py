#!/usr/bin/env python3
"""
ExitStrategyV2: 複合シグナルベースの出口戦略
- Stage 1-4 をベースに実装
- バックテスト & ホットテスト対応

使用方法:
    exit_strategy = ExitStrategyV2()
    decision = exit_strategy.evaluate_exit_condition(
        current_ohlcv=ohlcv,
        position_info=position,
        entry_info=entry_record
    )
    
    if decision['should_exit']:
        portfolio.close_position(close_ratio=decision['close_ratio'])
"""

import json


class ExitStrategyV2:
    """複合シグナルベースの出口戦略"""
    
    def __init__(self):
        self.config = None  # Loggerは簡略化
        
        # Stage判定の閾値（調整可能）
        self.ADX_STRONG_THRESHOLD = 50      # Stage 1判定
        self.ADX_WEAK_THRESHOLD_LOW = 30    # Stage 2下限
        self.ADX_WEAK_THRESHOLD_HIGH = 50   # Stage 2上限
        self.PVO_EXHAUSTION_THRESHOLD = 0   # PVO反転判定
        
        # 部分利確の設定
        self.PARTIAL_EXIT_RATIO = 0.5       # Stage 2での利確比率
        self.MFE_TARGET_RATIO = 0.7         # MFEの目標到達率
        
        # Trailing Profit Target設定（Task 39a - 破棄済み）
        self.trailing_profit_enabled = False  # 破棄済み機能：ベースライン比-1,077 USD悪化
        self.profit_tier1_threshold = 0.02   # 2%
        self.profit_tier1_stop_multiplier = 1.5
        self.profit_tier2_threshold = 0.05   # 5%
        self.profit_tier2_stop_multiplier = 1.0
        self.profit_tier3_threshold = 0.10   # 10%
        self.profit_tier3_stop_multiplier = 0.8
        
        # Trailing Stop状態を保持
        self.trailing_stops = {}  # {trade_id: trailing_stop_price}
        
        # Time-Based Exit設定（Task 39d）
        self.time_based_exit_enabled = False  # デフォルト無効、load_config()で更新
        self.max_holding_hours = 72.0  # デフォルト72時間

        # Chandelier Exit設定（Task 44a）
        # N期間最高値（ロング）または最安値（ショート）から ATR×mult のトレイリングストップ
        # PSARよりボラティリティ適応性が高く、トレンド中の利益をより多く確定できる
        self.chandelier_exit_enabled = False    # デフォルト無効、load_config()で更新
        self.chandelier_period = 22              # 最高値/最安値の追跡期間（バー数）
        self.chandelier_mult   = 3.0             # ATR乗数（標準値: 3.0）
        self.chandelier_states = {}              # {trade_key: {'highest': float, 'lowest': float}}
        self.chandelier_replaces_psar = False    # TrueのときPSARトレイリングをスキップ

        # Profit Step Lock設定（Task 44b）
        # 含み益が段階目標に達した後、利益が大きく引き込んだらEXIT（利益の保護）
        # Tier1: MFE≥2% → 含み益1%以下に戻ったらEXIT
        # Tier2: MFE≥4% → 含み益2.5%以下に戻ったらEXIT
        # Tier3: MFE≥8% → 含み益6%以下に戻ったらEXIT
        self.profit_step_lock_enabled = False  # デフォルト無効
        self.psl_tiers = [
            {'mfe_threshold': 0.02, 'lock_level': 0.01,  'name': 'Tier1'},
            {'mfe_threshold': 0.04, 'lock_level': 0.025, 'name': 'Tier2'},
            {'mfe_threshold': 0.08, 'lock_level': 0.06,  'name': 'Tier3'},
        ]
        self.psl_states = {}  # {trade_key: {'max_pnl_pct': float}}

        # Volume Climax Exit設定（Task 44d）
        # 出来高が移動平均の threshold倍に急増したとき、含み益があればEXIT
        self.volume_climax_exit_enabled = False  # デフォルト無効
        self.volume_climax_threshold    = 3.0    # 出来高急増判定倍率
        self.volume_climax_lookback     = 20     # 出来高移動平均期間
        self.volume_climax_min_profit   = 0.005  # 最低含み益率（0.5%）
        self.volume_history             = []     # 直近出来高履歴

        # Composite Score Exit設定（Task 44e）
        # ADX低下・PVO低下・Volume低下の複合スコアでトレンド失速を検出してEXIT
        self.composite_score_exit_enabled = False  # デフォルト無効
        self.composite_exit_adx_drop      = 5.0   # ADX低下判定閾値
        self.composite_exit_pvo_threshold = 0.0   # PVO閾値
        self.composite_exit_volume_ratio  = 0.8   # Volume比率閾値
        self.composite_exit_min_score     = 2     # EXIT最低スコア
        self.composite_exit_min_profit    = 0.005 # 最低含み益率

    def load_config(self, config_module):
        """Configモジュールから設定を読み込む（bot.pyから呼び出し）"""
        try:
            self.time_based_exit_enabled = config_module.get_enable_time_based_exit()
            self.max_holding_hours = config_module.get_max_holding_hours()
        except Exception as e:
            print(f"⚠️  ExitStrategyV2: Config読み込みエラー（デフォルト値使用）: {e}")
        try:
            self.chandelier_exit_enabled  = config_module.get_enable_chandelier_exit()
            self.chandelier_period        = config_module.get_chandelier_period()
            self.chandelier_mult          = config_module.get_chandelier_mult()
            self.chandelier_replaces_psar = config_module.get_chandelier_replaces_psar()
        except Exception:
            pass  # デフォルト値を使用
        try:
            self.profit_step_lock_enabled = config_module.get_enable_profit_step_lock()
        except Exception:
            pass  # デフォルト値を使用
        try:
            self.volume_climax_exit_enabled = config_module.get_enable_volume_climax_exit()
            self.volume_climax_threshold    = config_module.get_volume_climax_threshold()
            self.volume_climax_lookback     = config_module.get_volume_climax_lookback()
            self.volume_climax_min_profit   = config_module.get_volume_climax_min_profit_pct()
        except Exception:
            pass  # デフォルト値を使用
        try:
            self.composite_score_exit_enabled = config_module.get_enable_composite_score_exit()
            self.composite_exit_adx_drop      = config_module.get_composite_exit_adx_drop()
            self.composite_exit_pvo_threshold = config_module.get_composite_exit_pvo_threshold()
            self.composite_exit_volume_ratio  = config_module.get_composite_exit_volume_ratio()
            self.composite_exit_min_score     = config_module.get_composite_exit_min_score()
            self.composite_exit_min_profit    = config_module.get_composite_exit_min_profit_pct()
        except Exception:
            pass  # デフォルト値を使用
    
    def evaluate_exit_condition(self, current_ohlcv, position_info, entry_info):
        """
        複合シグナルベースの出口判定
        
        Args:
            current_ohlcv: 現在のOHLCV + 指標 {
                'close_price', 'high_price', 'low_price',
                'psar', 'adx', 'pvo_val', 'volatility', ...
            }
            position_info: ポジション情報 {
                'entry_price', 'quantity', 'side', ...
            }
            entry_info: エントリー時の指標記録 {
                'entry_adx', 'entry_pvo', 'entry_price', ...
            }
        
        Returns:
            {
                'should_exit': bool,
                'exit_reason': str,
                'close_ratio': float (0.0-1.0),
                'stage': str,
                'confidence': float (0.0-1.0),
            }
        """
        
        # print(f"📍 evaluate_exit_condition() 呼び出し: time_based_exit_enabled={self.time_based_exit_enabled}")  # コメントアウト:出力過多
        
        try:
            # データタイプ検証用ヘルパー関数
            def safe_get(val, default=0):
                """辞書またはスカラー値をスカラー値に変換"""
                if isinstance(val, dict):
                    return val.get('value', default) or default
                try:
                    return float(val) if val else default
                except (ValueError, TypeError):
                    return default
            
            # 基本検証
            quantity = safe_get(position_info.get('quantity', 0))
            if not position_info or quantity <= 0:
                return {
                    'should_exit': False,
                    'exit_reason': 'NO_POSITION',
                    'close_ratio': 0.0,
                    'stage': 'N/A',
                    'confidence': 0.0,
                }
            
            # 指標の取得
            current_price = safe_get(current_ohlcv.get('close_price', 0))
            current_psar = safe_get(current_ohlcv.get('psar', 0))
            current_adx = safe_get(current_ohlcv.get('adx', 0))
            current_pvo = safe_get(current_ohlcv.get('pvo_val', 0))
            
            entry_price = safe_get(entry_info.get('entry_price', position_info.get('entry_price', 0)))
            entry_adx = safe_get(entry_info.get('entry_adx', 0))
            entry_pvo = safe_get(entry_info.get('entry_pvo', 0))
            
            # Trailing Profit Target チェック（最優先）
            if self.trailing_profit_enabled:
                trailing_check = self._check_trailing_profit_target(
                    current_price, entry_price, 
                    safe_get(current_ohlcv.get('volatility', 0)),
                    position_info
                )
                if trailing_check['should_exit']:
                    return trailing_check
            
            # print(f"[TBE] Trailing Profit通過, time_based_exit_enabled={self.time_based_exit_enabled}")
            
            # Time-Based Exit チェック（Task 39d: 長期ポジションの強制決済）
            if self.time_based_exit_enabled:
                # print(f"🔍 Time-Based Exit有効 → チェック実行")
                time_check = self._check_time_based_exit(
                    current_ohlcv.get('timestamp', 0),
                    entry_info.get('entry_time', 0),
                    current_price,
                    entry_price
                )
                if time_check['should_exit']:
                    # print(f"⏰ TIME_LIMIT発動: {time_check.get('exit_reason')}")
                    return time_check
            # else:
                # print(f"⚠️  Time-Based Exit無効（設定未読込またはdisable）")
            
            # Stage判定
            stage = self._identify_stage(entry_adx, entry_pvo, current_adx, current_pvo)

            # Chandelier Exit チェック（Task 44a: PSARより先に発動する可能性がある精密ストップ）
            if self.chandelier_exit_enabled:
                current_high = safe_get(current_ohlcv.get('high_price', 0))
                current_low  = safe_get(current_ohlcv.get('low_price', 0))
                current_atr  = safe_get(current_ohlcv.get('volatility', 0))
                chandelier_check = self._check_chandelier_exit(
                    current_price=current_price,
                    current_high=current_high,
                    current_low=current_low,
                    current_atr=current_atr,
                    entry_price=entry_price,
                    position_info=position_info,
                    entry_info=entry_info,
                )
                if chandelier_check['should_exit']:
                    return chandelier_check

            # Stage 4: PSAR Stop Loss (最優先)
            if self._check_stop_loss(current_price, current_psar, position_info):
                return {
                    'should_exit': True,
                    'exit_reason': 'PSAR_STOP_LOSS',
                    'close_ratio': 1.0,
                    'stage': 'STOP_LOSS',
                    'confidence': 1.0,
                }
            
            # 各Stageによる出口判定
            if stage == 'STRONG_TREND':
                return {
                    'should_exit': False,
                    'exit_reason': 'HOLD_STRONG_TREND',
                    'close_ratio': 0.0,
                    'stage': 'STRONG_TREND',
                    'confidence': 0.9,
                }
            
            elif stage == 'WEAK_TREND':
                # Stage 2: トレンド減衰 → ホールド継続（PSAR / MOMENTUM_EXHAUSTED でEXITを待つ）
                # NOTE: 部分利確（close_ratio=0.5）はportfolio.clear_position_quantity()が
                #       部分クローズ非対応のため未実装。should_exit=False の場合 close_ratio は 0.0 とする。
                #       部分EXIT実装は別途タスク（PARTIAL_EXIT Decision型の追加）が必要。
                return {
                    'should_exit': False,
                    'exit_reason': 'HOLD_WEAK_TREND',
                    'close_ratio': 0.0,
                    'stage': 'WEAK_TREND',
                    'confidence': 0.7,
                }
            
            elif stage == 'MOMENTUM_EXHAUSTED':
                # Stage 3: 全出口
                return {
                    'should_exit': True,
                    'exit_reason': 'MOMENTUM_EXHAUSTED',
                    'close_ratio': 1.0,
                    'stage': 'MOMENTUM_EXHAUSTED',
                    'confidence': 0.85,
                }
            
            # デフォルト: ホールド
            return {
                'should_exit': False,
                'exit_reason': 'DEFAULT_HOLD',
                'close_ratio': 0.0,
                'stage': stage,
                'confidence': 0.5,
            }
        
        except Exception as e:
            import traceback
            error_msg = f"{e}\n{traceback.format_exc()}"
            print(f"❌ ExitStrategyV2 エラー: {error_msg}")
            return {
                'should_exit': False,
                'exit_reason': 'ERROR',
                'close_ratio': 0.0,
                'stage': 'ERROR',
                'confidence': 0.0,
            }
    
    def _identify_stage(self, entry_adx, entry_pvo, curr_adx, curr_pvo):
        """
        トレンドステージを特定
        
        Stage 1: トレンド加速中
            - ADX > 50 かつ PVO > 0 かつ ADX上昇
            
        Stage 2: トレンド減衰
            - 30 < ADX < 50 かつ PVO > 0
            
        Stage 3: モメンタム消失
            - PVO < 0 または ADX < 30
            
        Stage 4: PSAR (別途判定)
        """
        
        # データタイプチェックと変換
        try:
            entry_adx = float(entry_adx) if entry_adx is not None else 0
            entry_pvo = float(entry_pvo) if entry_pvo is not None else 0
            curr_adx = float(curr_adx) if curr_adx is not None else 0
            curr_pvo = float(curr_pvo) if curr_pvo is not None else 0
        except (ValueError, TypeError):
            # 変換失敗時はデフォルト値で継続
            entry_adx, entry_pvo, curr_adx, curr_pvo = 0, 0, 0, 0
        
        adx_increasing = curr_adx > entry_adx
        pvo_positive = curr_pvo > self.PVO_EXHAUSTION_THRESHOLD
        adx_strong = curr_adx > self.ADX_STRONG_THRESHOLD
        adx_weak = self.ADX_WEAK_THRESHOLD_LOW < curr_adx <= self.ADX_WEAK_THRESHOLD_HIGH
        adx_exhausted = curr_adx <= self.ADX_WEAK_THRESHOLD_LOW
        pvo_negative = curr_pvo < self.PVO_EXHAUSTION_THRESHOLD
        
        # Stage 1: 強いトレンド継続
        if adx_strong and pvo_positive and adx_increasing:
            return 'STRONG_TREND'
        
        # Stage 2: トレンド減衰
        elif adx_weak and pvo_positive:
            return 'WEAK_TREND'
        
        # Stage 3: モメンタム消失
        elif pvo_negative or adx_exhausted:
            return 'MOMENTUM_EXHAUSTED'
        
        # デフォルト
        else:
            return 'UNSTABLE'

    def _check_chandelier_exit(self, current_price, current_high, current_low,
                                current_atr, entry_price, position_info, entry_info):
        """
        Chandelier Exit チェック（Task 44a）

        ロング: chandelier_stop = highest_high(過去N期間) - ATR × mult
        ショート: chandelier_stop = lowest_low(過去N期間) + ATR × mult

        ポジションオープン以降の最高値/最安値を内部状態として追跡し、
        価格がChandelier Stopを下回った（ロング）または上回った（ショート）
        タイミングでEXITを発動する。

        ATRとしては current_ohlcv['volatility'] を使用（平均true range相当）。
        """
        try:
            side = position_info.get('side', 'NONE')
            if side not in ('BUY', 'SELL'):
                return {'should_exit': False, 'exit_reason': 'NO_SIDE', 'close_ratio': 0.0,
                        'stage': 'CHANDELIER', 'confidence': 0.0}

            # trade_keyでポジション状態を識別（entry_priceをキーに使用）
            trade_key = f"{side}_{entry_price}"

            if side == 'BUY':
                # ロング: 最高値を追跡
                state = self.chandelier_states.get(trade_key, {'highest': entry_price})
                if current_high > state.get('highest', entry_price):
                    state['highest'] = current_high
                self.chandelier_states[trade_key] = state

                highest_high = state['highest']
                if current_atr > 0:
                    chandelier_stop = highest_high - current_atr * self.chandelier_mult
                else:
                    return {'should_exit': False, 'exit_reason': 'CHANDELIER_NO_ATR',
                            'close_ratio': 0.0, 'stage': 'CHANDELIER', 'confidence': 0.0}

                if current_price <= chandelier_stop:
                    return {
                        'should_exit': True,
                        'exit_reason': 'CHANDELIER_STOP',
                        'close_ratio': 1.0,
                        'stage': 'CHANDELIER',
                        'confidence': 0.95,
                        'chandelier_stop': chandelier_stop,
                        'highest_high': highest_high,
                    }

            elif side == 'SELL':
                # ショート: 最安値を追跡
                state = self.chandelier_states.get(trade_key, {'lowest': entry_price})
                if current_low < state.get('lowest', entry_price):
                    state['lowest'] = current_low
                self.chandelier_states[trade_key] = state

                lowest_low = state['lowest']
                if current_atr > 0:
                    chandelier_stop = lowest_low + current_atr * self.chandelier_mult
                else:
                    return {'should_exit': False, 'exit_reason': 'CHANDELIER_NO_ATR',
                            'close_ratio': 0.0, 'stage': 'CHANDELIER', 'confidence': 0.0}

                if current_price >= chandelier_stop:
                    return {
                        'should_exit': True,
                        'exit_reason': 'CHANDELIER_STOP',
                        'close_ratio': 1.0,
                        'stage': 'CHANDELIER',
                        'confidence': 0.95,
                        'chandelier_stop': chandelier_stop,
                        'lowest_low': lowest_low,
                    }

            return {'should_exit': False, 'exit_reason': 'CHANDELIER_HOLD',
                    'close_ratio': 0.0, 'stage': 'CHANDELIER', 'confidence': 0.0}

        except Exception as e:
            return {'should_exit': False, 'exit_reason': f'CHANDELIER_ERROR:{e}',
                    'close_ratio': 0.0, 'stage': 'CHANDELIER', 'confidence': 0.0}

    def _check_profit_step_lock(self, current_price, entry_price, position_info):
        """
        Profit Step Lock チェック（Task 44b）

        含み益（unrealized PnL%）が段階目標を達成した後、
        利益が大きく引き込んだらEXITして確定益を保護する。

        段階設定（デフォルト）:
            Tier1: MFE ≥ 2%  → 含み益 1%  以下に戻ったらEXIT
            Tier2: MFE ≥ 4%  → 含み益 2.5%以下に戻ったらEXIT
            Tier3: MFE ≥ 8%  → 含み益 6%  以下に戻ったらEXIT
        """
        try:
            if entry_price <= 0:
                return {'should_exit': False, 'exit_reason': 'PSL_NO_ENTRY',
                        'close_ratio': 0.0, 'stage': 'PROFIT_STEP_LOCK', 'confidence': 0.0}

            side = position_info.get('side', 'NONE')
            trade_key = f"{side}_{entry_price}"

            # 現在の含み益率を計算
            if side == 'BUY':
                pnl_pct = (current_price - entry_price) / entry_price
            elif side == 'SELL':
                pnl_pct = (entry_price - current_price) / entry_price
            else:
                return {'should_exit': False, 'exit_reason': 'PSL_NO_SIDE',
                        'close_ratio': 0.0, 'stage': 'PROFIT_STEP_LOCK', 'confidence': 0.0}

            # MFE追跡
            state = self.psl_states.get(trade_key, {'max_pnl_pct': 0.0})
            if pnl_pct > state['max_pnl_pct']:
                state['max_pnl_pct'] = pnl_pct
                self.psl_states[trade_key] = state

            max_pnl_pct = state['max_pnl_pct']

            # 段階判定（上位Tierから評価）
            active_tier = None
            for tier in reversed(self.psl_tiers):
                if max_pnl_pct >= tier['mfe_threshold']:
                    active_tier = tier
                    break

            if active_tier and pnl_pct <= active_tier['lock_level']:
                return {
                    'should_exit': True,
                    'exit_reason': f"PROFIT_LOCK_{active_tier['name']}",
                    'close_ratio': 1.0,
                    'stage': 'PROFIT_STEP_LOCK',
                    'confidence': 0.9,
                    'mfe_pct': max_pnl_pct,
                    'current_pnl_pct': pnl_pct,
                    'tier': active_tier['name'],
                }

            return {'should_exit': False, 'exit_reason': 'PSL_HOLD',
                    'close_ratio': 0.0, 'stage': 'PROFIT_STEP_LOCK', 'confidence': 0.0}

        except Exception as e:
            return {'should_exit': False, 'exit_reason': f'PSL_ERROR:{e}',
                    'close_ratio': 0.0, 'stage': 'PROFIT_STEP_LOCK', 'confidence': 0.0}

    def _check_volume_climax_exit(self, current_volume, current_price, entry_price, position_info):
        """
        Volume Climax Exit チェック（Task 44d）

        出来高が移動平均の threshold倍に急増したとき、
        最低含み益率以上の利益があれば EXIT（クライマックス利確）。

        Args:
            current_volume: 現在バーの出来高
            current_price:  現在の終値
            entry_price:    エントリー価格
            position_info:  {'side': 'BUY'|'SELL', ...}

        Returns:
            dict: should_exit, exit_reason, etc.
        """
        try:
            if entry_price <= 0:
                return {'should_exit': False, 'exit_reason': 'VCE_NO_ENTRY'}

            side = position_info.get('side', 'NONE')

            # 出来高履歴を更新（最大 lookback+1 件保持）
            self.volume_history.append(current_volume)
            max_hist = self.volume_climax_lookback + 1
            if len(self.volume_history) > max_hist:
                self.volume_history = self.volume_history[-max_hist:]

            # 移動平均を計算（lookback本分）
            if len(self.volume_history) < self.volume_climax_lookback:
                return {'should_exit': False, 'exit_reason': 'VCE_WARMUP'}

            avg_volume = sum(self.volume_history[-self.volume_climax_lookback:]) / self.volume_climax_lookback
            if avg_volume <= 0:
                return {'should_exit': False, 'exit_reason': 'VCE_NO_AVG'}

            volume_ratio = current_volume / avg_volume

            # 出来高急増チェック
            if volume_ratio < self.volume_climax_threshold:
                return {'should_exit': False, 'exit_reason': 'VCE_NORMAL_VOL'}

            # 含み益チェック
            if side == 'BUY':
                pnl_pct = (current_price - entry_price) / entry_price
            elif side == 'SELL':
                pnl_pct = (entry_price - current_price) / entry_price
            else:
                return {'should_exit': False, 'exit_reason': 'VCE_NO_SIDE'}

            if pnl_pct < self.volume_climax_min_profit:
                # 含み益不足（損失中または利益が閾値未満）→ EXIT しない
                return {'should_exit': False, 'exit_reason': 'VCE_LOW_PROFIT',
                        'volume_ratio': volume_ratio, 'pnl_pct': pnl_pct}

            return {
                'should_exit': True,
                'exit_reason': 'VOLUME_CLIMAX',
                'close_ratio': 1.0,
                'stage': 'VOLUME_CLIMAX_EXIT',
                'confidence': 0.85,
                'volume_ratio': volume_ratio,
                'avg_volume': avg_volume,
                'pnl_pct': pnl_pct,
            }

        except Exception as e:
            return {'should_exit': False, 'exit_reason': f'VCE_ERROR:{e}'}

    def _check_composite_score_exit(self, current_adx, current_pvo, current_volume,
                                    entry_adx, entry_price, current_price, position_info):
        """
        Composite Score Exit チェック（Task 44e）

        ADX低下・PVO低下・Volume低下の3指標をスコアリングし、
        スコアが閾値以上で、かつ最低含み益率を満たす場合にEXIT。

        Args:
            current_adx:    現在のADX値
            current_pvo:    現在のPVO値
            current_volume: 現在の出来高
            entry_adx:      エントリー時のADX値
            entry_price:    エントリー価格
            current_price:  現在の終値
            position_info:  {'side': 'BUY'|'SELL', ...}

        Returns:
            dict: should_exit, exit_reason, score, etc.
        """
        try:
            if entry_price <= 0:
                return {'should_exit': False, 'exit_reason': 'CSE_NO_ENTRY'}

            side = position_info.get('side', 'NONE')

            # 含み益チェック（最低利益要件）
            if side == 'BUY':
                pnl_pct = (current_price - entry_price) / entry_price
            elif side == 'SELL':
                pnl_pct = (entry_price - current_price) / entry_price
            else:
                return {'should_exit': False, 'exit_reason': 'CSE_NO_SIDE'}

            if pnl_pct < self.composite_exit_min_profit:
                return {'should_exit': False, 'exit_reason': 'CSE_LOW_PROFIT', 'pnl_pct': pnl_pct}

            # スコア計算
            score = 0
            reasons = []

            # 1. ADX低下チェック
            if entry_adx > 0 and (entry_adx - current_adx) >= self.composite_exit_adx_drop:
                score += 1
                reasons.append(f'ADX低下({entry_adx:.1f}→{current_adx:.1f})')

            # 2. PVO低下チェック（PVO値が閾値以下）
            if current_pvo <= self.composite_exit_pvo_threshold:
                score += 1
                reasons.append(f'PVO低下({current_pvo:.2f})')

            # 3. Volume低下チェック（出来高が移動平均の割合以下）
            # VCEが無効の場合、ここでvolumeHistoryを更新する
            if current_volume > 0 and not self.volume_climax_exit_enabled:
                self.volume_history.append(current_volume)
                max_hist = self.volume_climax_lookback + 1
                if len(self.volume_history) > max_hist:
                    self.volume_history = self.volume_history[-max_hist:]

            if len(self.volume_history) >= self.volume_climax_lookback and current_volume > 0:
                avg_vol = sum(self.volume_history[-self.volume_climax_lookback:]) / self.volume_climax_lookback
                if avg_vol > 0 and (current_volume / avg_vol) <= self.composite_exit_volume_ratio:
                    score += 1
                    reasons.append(f'Volume低下({current_volume/avg_vol:.2f}x)')

            if score >= self.composite_exit_min_score:
                return {
                    'should_exit': True,
                    'exit_reason': 'COMPOSITE_SCORE_EXIT',
                    'close_ratio': 1.0,
                    'stage': 'COMPOSITE_SCORE',
                    'confidence': 0.8,
                    'score': score,
                    'reasons': reasons,
                    'pnl_pct': pnl_pct,
                }

            return {'should_exit': False, 'exit_reason': 'CSE_LOW_SCORE', 'score': score}

        except Exception as e:
            return {'should_exit': False, 'exit_reason': f'CSE_ERROR:{e}'}

    def _check_stop_loss(self, current_price, psar_price, position_info):
        """
        PSAR Stop Loss チェック
        
        Args:
            current_price: 現在の価格
            psar_price: PSAR値
            position_info: ポジション情報 {'side': 'BUY' or 'SELL', ...}
        
        Returns:
            bool: Stop Loss に触れたか
        """
        
        # psar_priceが辞書の場合は値を抽出（データタイプチェック）
        if isinstance(psar_price, dict):
            psar_price = psar_price.get('value', 0) or 0
        
        # psar_priceが数値でない場合は0として扱う
        try:
            psar_price = float(psar_price) if psar_price else 0
        except (ValueError, TypeError):
            psar_price = 0
        
        # current_priceが数値でない場合も同様
        try:
            current_price = float(current_price) if current_price else 0
        except (ValueError, TypeError):
            current_price = 0
        
        side = position_info.get('side', 'NONE')
        
        # ロングポジション: 価格 <= PSAR でストップ
        if side == 'BUY' and psar_price > 0:
            return current_price <= psar_price
        
        # ショートポジション: 価格 >= PSAR でストップ
        elif side == 'SELL' and psar_price > 0:
            return current_price >= psar_price
        
        # ポジションなし
        else:
            return False
    
    def get_stage_description(self, stage):
        """Stage の説明を取得"""
        descriptions = {
            'STRONG_TREND': {
                'ja': 'トレンド加速中 - 保持',
                'action': 'ホールド（トレーリングストップ）',
                'risk_level': '低',
            },
            'WEAK_TREND': {
                'ja': 'トレンド減衰 - 部分利確',
                'action': f'{self.PARTIAL_EXIT_RATIO*100:.0f}% 利確',
                'risk_level': '中',
            },
            'MOMENTUM_EXHAUSTED': {
                'ja': 'モメンタム消失 - 全出口',
                'action': '全ポジション出口',
                'risk_level': '高',
            },
            'STOP_LOSS': {
                'ja': 'ストップロス発動',
                'action': '無条件出口',
                'risk_level': '極高',
            },
            'UNSTABLE': {
                'ja': '不安定 - 様子見',
                'action': 'ホールド',
                'risk_level': '中高',
            },
            'N/A': {
                'ja': 'ポジションなし',
                'action': '－',
                'risk_level': '－',
            },
        }
        
        return descriptions.get(stage, {
            'ja': '不明',
            'action': '不明',
            'risk_level': '不明',
        })
    
    def _check_trailing_profit_target(self, current_price, entry_price, volatility, position_info):
        """
        トレーリング利益確定ターゲットをチェック
        
        Args:
            current_price: 現在価格
            entry_price: エントリー価格
            volatility: ボラティリティ
            position_info: ポジション情報
            
        Returns:
            dict: 出口判定結果
        """
        position_id = position_info.get('id', 'default')
        side = position_info.get('side', 'BUY')
        
        # 含み益率を計算
        if side == 'BUY':
            profit_pct = (current_price - entry_price) / entry_price
        else:  # SELL
            profit_pct = (entry_price - current_price) / entry_price
        
        # どのティアに該当するか判定
        active_tier = None
        stop_multiplier = None
        
        if profit_pct >= self.profit_tier3_threshold:
            active_tier = 3
            stop_multiplier = self.profit_tier3_stop_multiplier
        elif profit_pct >= self.profit_tier2_threshold:
            active_tier = 2
            stop_multiplier = self.profit_tier2_stop_multiplier
        elif profit_pct >= self.profit_tier1_threshold:
            active_tier = 1
            stop_multiplier = self.profit_tier1_stop_multiplier
        
        # ティアに到達している場合のみトレーリングストップを更新
        if active_tier is not None:
            # トレーリングストップを計算
            trailing_distance = volatility * stop_multiplier
            
            if side == 'BUY':
                new_trailing_stop = current_price - trailing_distance
            else:  # SELL
                new_trailing_stop = current_price + trailing_distance
            
            # 既存のトレーリングストップを更新（常に有利な方向へのみ）
            if position_id not in self.trailing_stops:
                self.trailing_stops[position_id] = {
                    'stop_price': new_trailing_stop,
                    'tier': active_tier,
                    'max_profit_pct': profit_pct
                }
            else:
                # BUYの場合：ストップを上げる方向のみ、SELLの場合：ストップを下げる方向のみ
                old_stop = self.trailing_stops[position_id]['stop_price']
                if (side == 'BUY' and new_trailing_stop > old_stop) or \
                   (side == 'SELL' and new_trailing_stop < old_stop):
                    self.trailing_stops[position_id] = {
                        'stop_price': new_trailing_stop,
                        'tier': active_tier,
                        'max_profit_pct': profit_pct
                    }
        
        # トレーリングストップに到達したかチェック
        if position_id in self.trailing_stops:
            trailing_stop = self.trailing_stops[position_id]['stop_price']
            tier = self.trailing_stops[position_id]['tier']
            max_profit = self.trailing_stops[position_id]['max_profit_pct']
            
            should_exit = False
            if side == 'BUY' and current_price <= trailing_stop:
                should_exit = True
            elif side == 'SELL' and current_price >= trailing_stop:
                should_exit = True
            
            if should_exit:
                # トレーリングストップをクリア
                del self.trailing_stops[position_id]
                
                return {
                    'should_exit': True,
                    'stage': 'TRAILING_PROFIT_TARGET',
                    'exit_ratio': 1.0,
                    'reason': f'利益確定Tier{tier} (最大利益: {max_profit*100:.2f}%, トレーリングストップ到達)',
                    'description': f'含み益が{max_profit*100:.2f}%に達した後、トレーリングストップ({trailing_stop:.2f})まで押し戻されました',
                    'confidence': 0.9,
                }
        
        # トレーリングストップ未到達
        return {'should_exit': False}

    def _check_time_based_exit(self, current_timestamp, entry_timestamp, current_price, entry_price):
        """
        Time-Based Exit: 保有時間制限をチェック（Task 39d）
        
        Args:
            current_timestamp: 現在のタイムスタンプ（秒またはミリ秒）
            entry_timestamp: エントリー時のタイムスタンプ（秒またはミリ秒）
            current_price: 現在価格
            entry_price: エントリー価格
            
        Returns:
            dict: 出口判定結果
        """
        try:
            # タイムスタンプを秒単位に正規化（ミリ秒の場合は変換）
            if current_timestamp > 1e12:  # ミリ秒と判定
                current_ts = current_timestamp / 1000
            else:
                current_ts = current_timestamp
            
            if entry_timestamp > 1e12:  # ミリ秒と判定
                entry_ts = entry_timestamp / 1000
            else:
                entry_ts = entry_timestamp
            
            # 保有時間を計算（時間単位）
            holding_duration_hours = (current_ts - entry_ts) / 3600
            
            # # デバッグ出力
            # print(f"🕐 Time-Based Exit チェック中:")
            # print(f"   entry_ts: {entry_ts}, current_ts: {current_ts}")
            # print(f"   保有時間: {holding_duration_hours:.1f}h / 制限: {self.max_holding_hours}h")
            
            # 保有時間制限を超過しているかチェック
            if holding_duration_hours > self.max_holding_hours:
                # 含み損益を計算
                if entry_price != 0:
                    unrealized_pnl = current_price - entry_price
                    pnl_pct = (unrealized_pnl / entry_price) * 100
                else:
                    # entry_price不明の場合は P&L=0 として強制決済
                    unrealized_pnl = 0
                    pnl_pct = 0
                
                if unrealized_pnl > 0:
                    # 利益確定
                    return {
                        'should_exit': True,
                        'exit_reason': 'TIME_LIMIT_PROFIT',
                        'close_ratio': 1.0,
                        'stage': 'TIME_BASED_EXIT',
                        'confidence': 0.85,
                        'holding_hours': holding_duration_hours,
                        'pnl_pct': pnl_pct,
                        'description': f'{holding_duration_hours:.1f}時間保有（制限{self.max_holding_hours}h超過）。利益{pnl_pct:.2f}%で強制決済'
                    }
                else:
                    # 損切り（塩漬け防止）
                    return {
                        'should_exit': True,
                        'exit_reason': 'TIME_LIMIT_LOSS',
                        'close_ratio': 1.0,
                        'stage': 'TIME_BASED_EXIT',
                        'confidence': 0.85,
                        'holding_hours': holding_duration_hours,
                        'pnl_pct': pnl_pct,
                        'description': f'{holding_duration_hours:.1f}時間保有（制限{self.max_holding_hours}h超過）。損失{pnl_pct:.2f}%で強制決済（塩漬け防止）'
                    }
            
            # 制限未到達
            return {'should_exit': False}
        
        except Exception as e:
            print(f"⚠️  Time-Based Exit チェックエラー: {e}")
            return {'should_exit': False}


class PortfolioExitExecutor:
    """Portfolio との統合実行器"""
    
    def __init__(self, portfolio, exit_strategy=None):
        self.portfolio = portfolio
        self.exit_strategy = exit_strategy or ExitStrategyV2()
        self.logger_enabled = False  # ロギング簡略化
    
    def execute_exit_decision(self, current_ohlcv, position_info, entry_info):
        """
        出口判定と実行を統合
        
        Returns:
            {
                'executed': bool,
                'decision': exit_strategy_decision,
                'result': execution_result,
            }
        """
        
        # 出口判定
        decision = self.exit_strategy.evaluate_exit_condition(
            current_ohlcv, position_info, entry_info
        )
        
        result = {
            'executed': False,
            'decision': decision,
            'result': None,
        }
        
        try:
            if decision['should_exit']:
                # 全出口
                result['executed'] = True
                result['result'] = self._close_full_position(position_info)
            
            elif decision['close_ratio'] > 0:
                # 部分利確
                result['executed'] = True
                result['result'] = self._close_partial_position(
                    position_info, decision['close_ratio']
                )
        
        except Exception as e:
            print(f"❌ 出口実行エラー: {e}")
            result['executed'] = False
        
        return result
    
    def _close_full_position(self, position_info):
        """全ポジションを出口"""
        # 実装は portfolio.close_position() に委譲
        return {
            'type': 'FULL',
            'quantity': position_info.get('quantity', 0),
            'status': 'CLOSING',
        }
    
    def _close_partial_position(self, position_info, close_ratio):
        """部分ポジションを出口"""
        quantity = position_info.get('quantity', 0)
        close_quantity = quantity * close_ratio
        
        return {
            'type': 'PARTIAL',
            'quantity': close_quantity,
            'remaining': quantity - close_quantity,
            'status': 'CLOSING',
        }


# テスト用スクリプト
if __name__ == "__main__":
    # ExitStrategyV2 の動作確認
    exit_strategy = ExitStrategyV2()
    
    # テストケース 1: Strong Trend
    print("=" * 80)
    print("テストケース 1: Strong Trend (保持)")
    print("=" * 80)
    
    decision = exit_strategy.evaluate_exit_condition(
        current_ohlcv={
            'close_price': 101500,
            'psar': 100000,
            'adx': 55,
            'pvo_val': 100,
            'volatility': 1000,
        },
        position_info={
            'entry_price': 100000,
            'quantity': 1.0,
            'side': 'BUY',
        },
        entry_info={
            'entry_adx': 50,
            'entry_pvo': 50,
            'entry_price': 100000,
        }
    )
    
    print(f"判定: {decision}")
    desc = exit_strategy.get_stage_description(decision['stage'])
    print(f"説明: {desc}")
    print()
    
    # テストケース 2: Weak Trend
    print("=" * 80)
    print("テストケース 2: Weak Trend (部分利確)")
    print("=" * 80)
    
    decision = exit_strategy.evaluate_exit_condition(
        current_ohlcv={
            'close_price': 101000,
            'psar': 100500,
            'adx': 40,
            'pvo_val': 50,
            'volatility': 800,
        },
        position_info={
            'entry_price': 100000,
            'quantity': 1.0,
            'side': 'BUY',
        },
        entry_info={
            'entry_adx': 50,
            'entry_pvo': 50,
            'entry_price': 100000,
        }
    )
    
    print(f"判定: {decision}")
    desc = exit_strategy.get_stage_description(decision['stage'])
    print(f"説明: {desc}")
    print()
    
    # テストケース 3: Momentum Exhausted
    print("=" * 80)
    print("テストケース 3: Momentum Exhausted (全出口)")
    print("=" * 80)
    
    decision = exit_strategy.evaluate_exit_condition(
        current_ohlcv={
            'close_price': 100200,
            'psar': 100500,
            'adx': 25,
            'pvo_val': -50,
            'volatility': 500,
        },
        position_info={
            'entry_price': 100000,
            'quantity': 1.0,
            'side': 'BUY',
        },
        entry_info={
            'entry_adx': 50,
            'entry_pvo': 50,
            'entry_price': 100000,
        }
    )
    
    print(f"判定: {decision}")
    desc = exit_strategy.get_stage_description(decision['stage'])
    print(f"説明: {desc}")
    print()
    
    # テストケース 4: Stop Loss
    print("=" * 80)
    print("テストケース 4: Stop Loss (無条件出口)")
    print("=" * 80)
    
    decision = exit_strategy.evaluate_exit_condition(
        current_ohlcv={
            'close_price': 99000,
            'psar': 99500,
            'adx': 30,
            'pvo_val': 0,
            'volatility': 600,
        },
        position_info={
            'entry_price': 100000,
            'quantity': 1.0,
            'side': 'BUY',
        },
        entry_info={
            'entry_adx': 50,
            'entry_pvo': 50,
            'entry_price': 100000,
        }
    )
    
    print(f"判定: {decision}")
    desc = exit_strategy.get_stage_description(decision['stage'])
    print(f"説明: {desc}")
