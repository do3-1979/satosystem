# ACTION LIST

このファイルでは `DEVELOPMENT_RULES.md` に基づいて、現在の gen2 ブランチの課題をTODO/PROGRESS/DONE で管理します。

## TODO

| ジャンル                | No. | タスク内容                                                                                       | 関連コミット/備考             | 優先度 |
|------------------------|-----|--------------------------------------------------------------------------------------------------|----------------------------------|--------|
| **パラメータ最適化**    | 24  | entry_times 10→5 + risk 30%→0.5% + leverage 10→5 に変更（+155%期待）                        | parameter_optimization_analysis | ★★★★★ |
| **パラメータ最適化**    | 25  | 新設定で 2024-2025全期間 re-backtest + results 比較（COMPREHENSIVE_TRADE_ANALYSIS参照）      | implementation_guide            | ★★★★★ |
| **Phase 0改善戦略**     | 22a | Strategy A: 市場レジーム検出（ADX）- 負けQ損失を70-80%削減（+15-25%期待、3-5日）              | COMPREHENSIVE_TRADE_ANALYSIS    | ★★★★★ |
| **Phase 0改善戦略**     | 22b | Strategy B: 指標確認（Bollinger+RSI+SMA）- エントリー精度向上（+8-12%期待、2-3日）            | COMPREHENSIVE_TRADE_ANALYSIS    | ★★★★☆ |
| **Phase 0改善戦略**     | 22c | Strategy C: 複合戦略（A+B）- 最大改善期待（+20-30%期待）                                       | COMPREHENSIVE_TRADE_ANALYSIS    | ★★★★☆ |
| **段階1（即座）**       | 23a | Fear & Greed Index 統合 - 過度な楽観/恐怖でのエントリー抑制（+5-8%期待、2-3h）               | IMPLEMENTATION_ROADMAP          | ★★★★★ |
| **段階1（即座）**       | 23b | RSI 二重確認実装 - 過買い状態でのロング回避（+2-3%期待、1-2h）                                 | IMPLEMENTATION_ROADMAP          | ★★★★★ |
| **戦略最適化**          | 20  | マーケット環境変化対応 - ADX で トレンド強度を検出し、パラメータを動的調整                       | docs/QUARTERLY_BACKTEST_ANALYSIS | ★★★★★ |
| **エントリー戦略**      | 21  | ローソク足形状シグナル分析 - 高値・安値・終値の関係からエントリー効果を検証                      | 効果測定検討中                   | ★★★★☆ |
| ログ制御・出力          | 3   | drawdown計算の統一・修正                                                                         | 71efcfe, 7e9c659, 68a51dc        | ★★★★☆ |
| ログ制御・出力          | 4   | PnL時系列エクスポート機能の実装                                                                  | 6efcedc                          | ★★★★☆ |
| ログ制御・出力          | 6   | ログファイル自動整理・定期クリーンアップ機能の実装                                              | QUARTERLY_BACKTEST分析参照       | ★★★☆☆ |
| ログ制御・出力          | 5   | full-loggingオプションのBot反映                                                                  | bff567b                          | ★★★☆☆ |
| doc/test整備           | 10  | ドキュメント統合・体系化                                                                         | 814ec47, 2e5e837, 1dd7658        | ★★★☆☆ |
| doc/test整備           | 11  | テストランナー統合・verify_all.py追加                                                            | 35508c6, 5ce4761                 | ★★★☆☆ |
| doc/test整備           | 12  | ドキュメント構造テスト追加                                                                       | 5ce4761                          | ★★★☆☆ |
| doc/test整備           | 13  | analysis/project_structure.json・ARCHITECTURE_OVERVIEW.mdにクラス・メソッド一覧を反映             | 本分析                           | ★★★☆☆ |
| config/キャッシュ管理   | 13  | config.iniのプレースホルダ化・コメント整形                                                       | 38b761d, d6c7da3, 26c9f48        | ★★★☆☆ |
| config/キャッシュ管理   | 15  | path_utils.pyによるパス管理の一元化                                                              | bbd8514                          | ★★★☆☆ |
| スクリプト統合・運用    | 16  | backtest.pyへの機能統合                                                                          | 7bbbcf9, 604848c                 | ★★★☆☆ |
| スクリプト統合・運用    | 17  | bot_run.sh, replace_api_key.shの整理                                                             | d683227                          | ★★★☆☆ |

## PROGRESS

| ジャンル                | No. | タスク内容                                                                                       | 進捗                             | 優先度 |
|------------------------|-----|--------------------------------------------------------------------------------------------------|----------------------------------|--------|
| **パラメータ最適化分析** | 23c | Leverage×Risk×EntryTimes スイープテスト 実施完了 - 57テスト、最適パラメータ特定                 | ✅ 分析完了（parameter_optimization_analysis.json）| ★★★★★ |
| **ドキュメント統合**    | 23d | docs/ の DEVELOPMENT_RULES/ARCHITECTURE/PRICE_DATA_FLOW を analysis/ に反映                     | ✅ 完了（docs_to_analysis_integration.py）       | ★★★★★ |
| **Phase 1.5実装**       | 20a | 3段階ADXフィルタ戦略実装 - BOX/WEAK/STRONG環境対応                                             | ✅ 完了、+$641改善達成          | ★★★★★ |
| **Phase 3計画**         | 20b | マルチタイムフレーム ADX 確認 - 1h+4h複合判定でノイズ削減                                      | 🔄 設計中 (2025年度対応)        | ★★★★☆ |

## DONE

| ジャンル                | No. | タスク内容                                                                                       | 完了時期             | 優先度 |
|------------------------|-----|--------------------------------------------------------------------------------------------------|----------------------|--------|
| **Phase 0: 基準測定**   | -   | 基準状態タグ付け、四半期別レグレッション分析、問題Q特定 (2024 Q2, 2025 Q1/Q2/Q3)              | 2025-12-11          | ★★★★★ |
| **Phase 1実装**         | -   | ADX<25フィルタ、Weak Trend時平均化禁止 → 44% 問題Q改善 (-$479→-$269)                         | 2025-12-11          | ★★★★★ |
| **Phase 1.5実装**       | 20a | 3段階ADXフィルタ実装 - +$641改善達成 (基準-$375→+$266)、Phase1.5_final_20251211タグ付け     | 2025-12-11          | ★★★★★ |
| **Phase 2実装**         | -   | Box市場Donchian逆張り戦略 - バックテスト実施、失敗 (-$109悪化) → 廃棄判定                      | 2025-12-11          | ★★★★☆ |
| **戦略最適化**          | 18  | 2025年成績悪化の根本原因分析・四半期別分析 → Stage 1-4 改善戦略策定                            | 2025-12-09          | ★★★★★ |
| **個別トレード改善**    | 19  | 出口戦略の複合指標化（PSAR + PVO + ADX） → MFE失われた利益を75%削減                           | 2025-12-10          | ★★★★★ |
| **個別トレード改善**    | 19a | ExitStrategyV2 統合 - Q4 2025 で -2.63 → +368.20 USD に改善、勝率 100%達成                   | 2025-12-10          | ★★★★★ |
| Document governance    | -   | `docs/DEVELOPMENT_RULES.md`、`docs/ACTION_LIST.md`、`docs/analysis/project_structure.json` 整備 | 2025-11-26          | ★★★★☆ |
| Update architecture    | -   | `docs/ARCHITECTURE_OVERVIEW.md` を gen2 現況に合わせて更新                                      | 2025-11-26          | ★★★★☆ |
| Backtest optimization  | 2   | `price_data_management.py` 1分刻み → 2時間足刻み進行、`trading_strategy.py` ストップ判定改善  | 2025-11-27 (9f6f0da) | ★★★★☆ |
| Cleanup local assets   | -   | 非追跡キャッシュ削除、`.gitignore` 更新、ローカル運用方針明記                                  | 2025-11-27          | ★★★★☆ |
| 実行パス抜本解決       | -   | ディレクトリ統一（src/ 固定）、ENTRY=0 エラー解消、全レグレッション [OK]                      | 2025-11-28          | ★★★★☆ |
| PSAR初期化期間拡張     | -   | `psar_lookback_term = 100` 追加、Close > STOP 比率 65% → 51%正常化                            | 2025-11-28 (b9f5cc1) | ★★★★☆ |
| インタラクティブグラフ | -   | `visualizer.py` Plotlyベース、Row1-4 構成、ズーム/凡例切り替え、PNG出力                       | 2025-11-29          | ★★★★☆ |
| EXIT/ADD マーカー表示  | -   | visualizer.py に ENTRY/ADD/EXIT マーカー、ポジション背景色ハイライト実装                     | 2025-11-29          | ★★★★☆ |
| ドキュメント統合       | -   | VISUALIZATION_GUIDE.md 統合、REGRESSION_TEST_POLICY.md 削除、docs 整理完了                   | 2025-11-30          | ★★★☆☆ |
| OHLCV SQLiteキャッシュ | -   | `ohlcv_cache.py` 新規、JSON → SQLite 移行、全テスト [OK]                                       | 2025-12-01          | ★★★★☆ |
| OHLCV キャッシュ検査   | -   | `ohlcv_cache_inspector.py` 新規、サマリー/範囲/断絶/詳細分析、`ohlcv_cache_info.sh` ラッパー | 2025-12-02          | ★★★★☆ |
| OHLCV 部分一致機能     | -   | `get_ohlcv_data_partial()` 追加、サーバアクセス削減、柔軟な期間マッチング対応                 | 2025-12-03          | ★★★☆☆ |
| 四半期別バックテスト   | -   | 8四半期分析完了（2024/1Q～2025/4Q）、累積 +576.11 USD、詳細分析 markdown 作成               | 2025-12-04          | ★★★★☆ |
| ホットテスト実装       | -   | ペーパートレード機能実装、本番API + ダミー売買、無限ループ対応                                | 2025-12-05          | ★★★★☆ |
| レグレッションテスト   | -   | 固まり問題解決（config.ini 矛盾修正）、exchange 初期化矛盾解決                                | 2025-12-06          | ★★★★☆ |
| メインループ修復       | -   | exchange 初期化矛盾解決、バックテストモードでも exchange 生成、NoneType エラー解消           | 2025-12-07          | ★★★★☆ |
| テスト体制整備         | 1   | コミット前のレグレッションテスト作成 - 全54テスト PASS、pytest + regression_test_suite.py | 2025-12-10          | ★★★★★ |
| ADX 可視化             | -   | visualizer.py Row3 に ADX 追加、Z-score 正規化トグル、標準化指標表示対応                     | 2025-12-09          | ★★★★☆ |
| Dual PnL 表示          | -   | visualizer.py Row4 に 実績PnL (青実線) + トータルPnL (オレンジ破線) 双方表示                 | 2025-12-10          | ★★★★☆ |
| テスト体制整備         | -   | レグレッションテスト全54テスト PASS、visualizer テストバグ修正、ベースライン更新               | 2025-12-10          | ★★★★☆ |


