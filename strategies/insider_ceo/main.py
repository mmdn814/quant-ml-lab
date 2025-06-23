#

from shared.logger import setup_logger
from strategies.insider_ceo.form4_ceo_selector import run_ceo_strategy

def run_strategy():
    """
    Colab & GitHub Actions 可共用的统一入口
    """
    logger = setup_logger("insider_ceo")
    logger.info("📈 Running insider CEO strategy ...")
    run_ceo_strategy(logger)

if __name__ == '__main__':
    run_strategy()
