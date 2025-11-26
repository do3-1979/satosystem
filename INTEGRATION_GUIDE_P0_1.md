"""
P0-1統合: bot.py へのトレード詳細ログ機能の統合指示書

目的: 個別トレードの詳細情報をキャプチャして分析可能にする

統合ポイント:
1. Bot.__init__() に TradeDetailLogger を初期化
2. Bot でのトレード実行後、execute_trade() 直後に詳細ログを記録
3. バックテスト終了時に TradeAnalyzer で分析を実行

実装手順:
"""

# bot.py への統合コード例

# ====== bot.py の import に追加 ======
# from src.trade_detail_analyzer import TradeDetailLogger

# ====== Bot.__init__() 内に追加 ======
# self.trade_logger = TradeDetailLogger()

# ====== Bot.run() の各トレード実行後に追加 ======
# 詳細ログを記録
# self.trade_logger.log_trade({
#     'trade_id': len(self.trade_logger.trades) + 1,
#     'timestamp': datetime.now().isoformat(),
#     'entry_price': entry_price,
#     'exit_price': exit_price,
#     'position_size': position_size,
#     'pnl': pnl_value,
#     'side': trade_data.get('side'),
#     'volatility': trade_data.get('volatility'),
#     'stop_price': trade_data.get('stop_price'),
#     'reason': trade_data.get('decision'),
# })

# ====== Bot.run() の終了時に追加 ======
# バックテスト完了時に分析を実行
# if Config.get_back_test():
#     self.trade_logger.save_to_file()
#     from src.trade_detail_analyzer import TradeAnalyzer
#     analyzer = TradeAnalyzer(self.trade_logger.trades)
#     report = analyzer.generate_report()
#     print(report)
