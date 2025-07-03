# ✅ 文件：strategies/insider_ceo/main.py
# 功能：运行 CEO insider 策略（支持 CLI 手动调用 & GitHub Actions 自动运行）

import os
import sys
import argparse

# 添加项目根目录到模块路径
current_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(current_dir, "../../"))
sys.path.append(project_root)

# 模块导入
from shared.logger import setup_logger
from strategies.insider_ceo.form4_ceo_selector import run_ceo_strategy

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Insider CEO Strategy")
    parser.add_argument("--days_back", type=int, default=3, help="回溯天数（默认3）")
    parser.add_argument("--top_n", type=int, default=20, help="推送前N名（默认20）")
    parser.add_argument("--mode", type=str, default="index", choices=["index", "atom"], help="抓取模式（index或atom）")
    args = parser.parse_args()

    logger = setup_logger("insider_ceo")
    logger.info("✅ 启动 CEO insider 策略主程序")

    run_ceo_strategy(
        logger,
        days_back=args.days_back,
        top_n=args.top_n,
        mode=args.mode
    )
