# main.py
# 功能：作为 CEO 买入策略的主入口
# 最后修改时间：2025-06-26

from shared.logger import setup_logger
from strategies.insider_ceo.form4_ceo_selector import CEOTradeStrategy

def main():
    # 初始化日志器（可改为文件输出等）
    logger = setup_logger("ceo_strategy_main")

    logger.info("📈 Running insider CEO strategy ...")
    
    # 创建并运行策略实例
    strategy = CEOTradeStrategy(logger=logger, days_back=3, top_n=20)
    strategy.run()

if __name__ == "__main__":
    main()
