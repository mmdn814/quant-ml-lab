#控制台输出格式化日志；
#每个模块可独立创建自己的 logger；
#GitHub Actions 也会完整记录日志，非常方便排错。

import logging
import os

def setup_logger(name):
    """
    通用日志封装，方便在每个策略模块复用
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # 避免重复添加 Handler
    if not logger.handlers:
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] - %(message)s')
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        logger.addHandler(console)

    return logger

