# ADX による適応型レジーム判定の実装ガイド

## 1. ADX でトレンド/ボックスを判定する精度

### ADX の役割と限界

**ADX の本質**:
- ADX は**トレンドの強さ**を測定するもので、トレンド方向は測定しない
- 高ADX (> 25-30) = 強いトレンド
- 低ADX (< 20) = 弱いトレンド/ボックス

**精度の問題**:
```
ADX の判定が後行指標である理由:
- ADX は DI (方向性指標) を基に計算
- DI は過去 14 本の価格データから計算
- つまり「過去 14 本のトレンドの強さ」を示す
- 相場環境が激変している時点では反応が遅れる
```

**実際の精度**:
| 時間軸 | 精度 | 遅延 | 備考 |
|--------|------|------|------|
| 15分足 | 50-60% | 210分 (14本) | ノイズが多い、判定が不安定 |
| 1時間足 | 60-70% | 14時間 | 実用的だが遅延がある |
| **2時間足** | **65-75%** | **28時間** | 当システムの対象（評価期間 1+ 日） |
| 4時間足 | 70-80% | 56時間 | より安定的だが評価期間が長い |
| 日足 | 75-85% | 14日 | 最も安定的だが判定が遅い |

---

## 2. トレンド vs ボックス での戦略の変え方

### 現在のシステム vs 適応型への進化

**現在の実装**:
```python
# trading_strategy.py (ExitStrategyV2)
# 常に PSAR ベースの Stop Loss + 複合シグナル判定
# = 「トレンド戦略に最適化」した固定ロジック
```

**適応型への変更案**:

#### 🔵 **トレンド相場** (ADX > 25)
```
特性: 一方向の値動きが続く
戦略: トレンドフォロー最適化

実装例:
- エントリー: より早期（PSAR 反転直後）
- ポジション: 複数ADD で増玉（順張り）
- ストップ: PSAR ベース（現在通り）
- 利確: トレーリングストップ（利益を伸ばす）
- 指標: PSAR が機能しやすい → 信頼度高

実装コード:
if adx > 25:  # トレンド相場
    position_strategy = "trend_following"
    max_add_times = 3  # 複数ADD許可
    stop_loss_type = "psar_trailing"
    take_profit_ratio = 0.05  # 5% で利確ターゲット設定
```

#### 🟢 **弱トレンド相場** (20 < ADX ≤ 25)
```
特性: 値動きの方向は定まっているが弱い
戦略: 慎重なトレンドフォロー

実装例:
- エントリー: トレンド確認後（より遅延させる）
- ポジション: ADD は控えめ（1-2回まで）
- ストップ: 固定 % ベース + PSAR 確認
- 利確: 固定利幅（3% など）
- 指標: PSAR 信頼度中程度

if 20 < adx <= 25:  # 弱トレンド
    position_strategy = "conservative_trend"
    max_add_times = 1
    stop_loss_ratio = 0.02  # 2% 固定
    take_profit_ratio = 0.03  # 3% 固定
```

#### 🟡 **ボックス相場** (ADX ≤ 20)
```
特性: 上下の値動きが繰り返される
戦略: レンジトレード/逆張り

実装例:
- エントリー: レンジ上限/下限での逆張り
- ポジション: ポジションサイズ縮小
- ストップ: 短く設定（ブレイク対策）
- 利確: 早期利確（1% でも良い）
- 指標: Donchian チャネルが機能、PSAR は無視

if adx <= 20:  # ボックス相場
    position_strategy = "range_trading"
    max_add_times = 0  # ADD なし
    stop_loss_ratio = 0.01  # 1% 短い
    take_profit_ratio = 0.01  # 1% 早期利確
    # Donchian の上下限でエントリー検討
```

---

## 3. パラメータ見直しの戦略（期間別）

### 3-1. 判定期間の選択肢と特性

| 期間 | 使用シーン | 評価データ | 対応時間 | 実装難度 |
|------|-----------|----------|---------|---------|
| **1週間** | 日内・スウィング | 336本 (2h) | 3-7日 | 低 |
| **1ヶ月** | スウィング・中期 | 360本 (2h) | 15-30日 | 中 |
| **3ヶ月** | 中期・四半期 | 1080本 (2h) | 45-90日 | 高 |

### 3-2. パラメータ見直し手順（推奨フロー）

#### **フェーズ 1: 複数期間の並行評価** (1週間)
```python
# trading_strategy.py 拡張案
class AdaptiveRegimeDetector:
    def __init__(self):
        self.adx_short = ADX(period=14, lookback_bars=168)   # 1週間（2h足×84本）
        self.adx_mid = ADX(period=14, lookback_bars=360)     # 1ヶ月
        self.adx_long = ADX(period=14, lookback_bars=1080)   # 3ヶ月
    
    def get_regime(self, current_adx):
        """複数期間のコンセンサスを取る"""
        regimes = {
            'short': self._classify(self.adx_short),
            'mid': self._classify(self.adx_mid),
            'long': self._classify(self.adx_long),
        }
        
        # 2/3 以上が同じレジームなら採用
        trend_votes = sum(1 for r in regimes.values() if r == 'trend')
        if trend_votes >= 2:
            return 'trend'
        elif trend_votes == 0:
            return 'box'
        else:
            return 'mixed'  # 判定が不安定

# 戦略制御の例
regime = detector.get_regime(current_adx)
if regime == 'trend':
    apply_trend_strategy()
elif regime == 'box':
    apply_range_strategy()
else:  # mixed
    apply_conservative_strategy()  # 保守的に振る舞う
```

#### **フェーズ 2: 期間別パラメータセット** (2-4週間)
```python
# config.ini 拡張案
[Strategy_Regimes]
# トレンド相場用パラメータ
trend_stop_loss_percent = 0.025
trend_max_add_times = 3
trend_psar_af_start = 0.02
trend_psar_af_max = 0.20

# ボックス相場用パラメータ
box_stop_loss_percent = 0.01
box_max_add_times = 0
box_donchian_period = 20
box_take_profit_percent = 0.01

# 混合相場用パラメータ
mixed_stop_loss_percent = 0.015
mixed_max_add_times = 1
mixed_use_volatility_scaling = true
```

#### **フェーズ 3: 期間別パフォーマンス測定** (1-2ヶ月)
```python
# backtest_results_by_regime.json 例
{
  "test_period": "2025-09-01 to 2025-12-10",
  "regimes": {
    "trend": {
      "adx_range": [25, 100],
      "occurrences": 45,
      "win_rate": 0.75,
      "profit_factor": 2.3,
      "avg_bars_held": 12,
      "notes": "効率的な戦略"
    },
    "box": {
      "adx_range": [0, 20],
      "occurrences": 28,
      "win_rate": 0.52,
      "profit_factor": 0.95,
      "avg_bars_held": 5,
      "notes": "収益性が低い → 戦略改善必要"
    },
    "mixed": {
      "adx_range": [20, 25],
      "occurrences": 15,
      "win_rate": 0.60,
      "profit_factor": 1.1,
      "avg_bars_held": 8,
      "notes": "保守的に対応 → 良好"
    }
  }
}
```

---

## 4. 実装の推奨アプローチ

### 段階 1: 検証フェーズ（1-2週間）
```
目標: ADX の有効性を確認
- 現在のバックテストに ADX 値を記録
- 各トレードの開始時 ADX を分類
- レジーム別の勝率/利益因子を集計
- 差があるかを統計検定
```

**実装スクリプト**:
```python
# tools/regime_analysis.py (新規)
def analyze_regime_effectiveness():
    """過去ログから ADX とパフォーマンスの関係を分析"""
    df = load_backtest_results()
    df['adx_regime'] = df['entry_adx'].apply(classify_regime)
    
    results = df.groupby('adx_regime').agg({
        'pnl': ['sum', 'mean', 'std'],
        'win_rate': 'mean',
        'trade_id': 'count'
    })
    
    print(results)  # トレンド > ボックス であるか確認
```

### 段階 2: パラメータ最適化フェーズ（2-4週間）
```
目標: レジーム別の最適パラメータを見つける
- Grid Search で各レジームのパラメータを探索
- レジーム別に異なるパラメータセットを作成
- 混合相場での扱いを決定
```

**実装スクリプト**:
```python
# tools/regime_param_optimization.py (新規)
def optimize_by_regime():
    """各レジーム別にパラメータを最適化"""
    regimes = ['trend', 'box', 'mixed']
    
    for regime in regimes:
        # 該当期間のみを抽出
        regime_data = filter_by_adx_regime(regime)
        
        # Grid Search
        best_params = grid_search_parameters(
            data=regime_data,
            param_grid={
                'stop_loss_percent': [0.01, 0.015, 0.02, 0.025],
                'max_add_times': [0, 1, 2, 3],
                'take_profit_ratio': [0.01, 0.02, 0.03, 0.05]
            }
        )
        
        save_regime_params(regime, best_params)
```

### 段階 3: 本運用フェーズ（以降）
```
目標: リアルタイムで判定・切り替え
- ホットテスト中に ADX を常時計算
- 現在のレジームを判定
- 対応するパラメータセットを適用
- 月 1 回、レジーム別パフォーマンスを確認
- 必要に応じてパラメータを微調整
```

---

## 5. 現在のシステムへの統合計画

### 短期（1-2週間）
```
[ ] tools/regime_analysis.py 新規作成
[ ] 過去ログから ADX × パフォーマンス分析
[ ] NO.20 タスク: 「ADX で環境判定」の検証完了
```

### 中期（3-8週間）
```
[ ] trading_strategy.py に AdaptiveRegimeDetector 実装
[ ] config.ini にレジーム別パラメータを追加
[ ] tools/regime_param_optimization.py で最適化
[ ] 3ヶ月分のバックテスト結果を分析
```

### 長期（9週間以降）
```
[ ] ホットテストで実装検証
[ ] パラメータを月 1 回見直し
[ ] 四半期別の成績改善を確認
```

---

## 6. 注意点・リスク

### 6-1. オーバーフィッティングの危険性
```
問題: 過去データに最適化したパラメータが未来に通用しない
対策:
- Walk-Forward Analysis を実装
- 1ヶ月単位で訓練→検証を繰り返す
- アウトオブサンプルテストを必須とする
```

### 6-2. 判定遅延による損失
```
問題: ADX が反応してからエントリーしていたら、トレンド終盤の可能性
対策:
- ADX のしきい値を厳密にしない（連続的に判定）
- 複数期間のコンセンサスを取る
- トレンド判定時も保守的なストップを設定
```

### 6-3. ボックス相場での収益性低下
```
問題: ボックス相場の戦略がまだ確立していない
対策:
- ボックス相場では取引を避ける（勝率 < 50% なら取引禁止）
- または取引ロットを縮小する
```

---

## 7. まとめ表

| 項目 | 評価 |
|------|------|
| **ADX で「その瞬間」判定の精度** | 65-75% (2時間足) |
| **判定遅延** | 28時間（14本の過去データ）|
| **トレンド/ボックス戦略の差** | ★★★★★ (完全に異なる) |
| **推奨判定期間** | 1ヶ月～ (1週間は短すぎ) |
| **パラメータ見直し頻度** | 月 1 回 (四半期ごとに大修正) |
| **実装難度** | 中程度 (2-4週間で実装可能) |

---

## 8. 次のアクション

1. **NO.20 の第 1 ステップ**:
   ```bash
   python3 tools/regime_analysis.py
   ```
   → 過去ログから「トレンド相場と、ボックス相場で成績が異なるか」を確認

2. **差がある場合** (期待度 70%):
   → 本格的なパラメータ最適化に進む

3. **差がない場合** (期待度 30%):
   → ADX 判定精度が低い可能性 → 判定期間を長くする / 他の指標と併用
