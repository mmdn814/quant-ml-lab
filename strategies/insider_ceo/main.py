import os
from dotenv import load_dotenv
load_dotenv()  # ✅ 从 .env 文件加载环境变量

from shared.logger import setup_logger
from strategies.insider_ceo.form4_ceo_selector import run_ceo_strategy
from strategies.insider_ceo.telegram_push import send_trade_summary
from shared.data_saver import save_dataframe_to_csv
from datetime import datetime
import pandas as pd

def run_strategy():
    logger = setup_logger("insider_ceo")
    logger.info("📈 Running insider CEO strategy ...")

    # 1. 执行策略并返回结构化结果
    trade_results = run_ceo_strategy(logger)

    # 2. 保存结果为 CSV（如有数据）
    if trade_results:
        df = pd.DataFrame(trade_results)
        today_str = datetime.today().strftime('%Y%m%d')
        path = f"data/insider_ceo/ceo_results_{today_str}.csv"
        save_dataframe_to_csv(df, path, logger=logger)
    else:
        logger.info("😶 今日无符合条件记录，不保存")

    # 3. 推送 Telegram（不论有无数据）
    send_trade_summary(trade_results)

if __name__ == '__main__':
    run_strategy()
