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
            
            # Stage判定
            stage = self._identify_stage(entry_adx, entry_pvo, current_adx, current_pvo)
            
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
                # Stage 2: 部分利確を検討
                return {
                    'should_exit': False,  # 全出口ではなく部分利確
                    'exit_reason': 'PARTIAL_EXIT_WEAK_TREND',
                    'close_ratio': self.PARTIAL_EXIT_RATIO,
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
