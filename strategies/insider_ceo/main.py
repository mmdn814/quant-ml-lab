# 最后更新时间6/30/25 17:06
# 运行入口：CEO insider buy 策略主函数

import os
import sys

# 添加项目根目录到模块路径
# 假设您的项目结构是：
# project_root/
# ├── shared/
# │   ├── logger.py
# │   ├── telegram_notifier.py
# │   ├── edgar_downloader.py
# │   ├── data_saver.py
# │   ├── data_loader.py
# │   └── fintel_scraper.py
# └── strategies/
#     └── insider_ceo/
#         ├── form4_ceo_selector.py
#         └── main.py  <-- 当前文件

# 确保 sys.path.append 的路径是项目根目录
current_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(current_dir, "../../"))
sys.path.append(project_root)

# 确保从正确的路径导入模块
from shared.logger import setup_logger
# 明确导入 form4_ceo_selector 模块中的 run_ceo_strategy 函数
from strategies.insider_ceo.form4_ceo_selector import run_ceo_strategy 

if __name__ == "__main__":
    logger = setup_logger("insider_ceo")
    logger.info("✅ 启动 CEO insider 策略主程序")
    # 调用策略主函数，可以根据需要调整 days_back 和 top_n 参数
    run_ceo_strategy(logger, days_back=7, top_n=20) 

