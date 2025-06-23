from shared.logger import setup_logger
from strategies.insider_ceo.form4_ceo_selector import run_ceo_strategy
from strategies.insider_ceo.telegram_push import send_trade_summary
from shared.data_saver import save_dataframe_to_csv
from datetime import datetime
import pandas as pd

def run_strategy():
    logger = setup_logger("insider_ceo")
    logger.info("📈 Running insider CEO strategy ...")

    trade_results = run_ceo_strategy(logger)

    if trade_results:
        df = pd.DataFrame(trade_results)
        today_str = datetime.today().strftime('%Y%m%d')
        path = f"data/insider_ceo/ceo_results_{today_str}.csv"
        save_dataframe_to_csv(df, path)
        logger.info(f"✅ 保存成功：{path}")
    else:
        logger.info("😶 今日无符合条件记录，不保存")

    send_trade_summary(trade_results)

if __name__ == '__main__':
    run_strategy()
