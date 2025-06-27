# 最后更新时间6/27/25 16:09
# 运行入口：CEO insider buy 策略主函数

import os
import sys

# 添加项目根目录到模块路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from shared.logger import setup_logger
from strategies.insider_ceo.form4_ceo_selector import run_ceo_strategy

if __name__ == "__main__":
    logger = setup_logger("insider_ceo")
    logger.info("✅ 启动 CEO insider 策略主程序")
    run_ceo_strategy(logger)
