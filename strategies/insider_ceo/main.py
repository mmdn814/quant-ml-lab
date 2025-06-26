# strategies/insider_ceo/main.py
# 功能：启动 insider_ceo 策略主入口

from shared.logger import setup_logger
from strategies.insider_ceo.form4_ceo_selector import run_ceo_strategy

if __name__ == "__main__":
    logger = setup_logger("insider_ceo")
    run_ceo_strategy(logger)
