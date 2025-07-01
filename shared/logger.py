import logging
import os
from datetime import datetime

def setup_logger(name, log_dir="logs", level=logging.DEBUG): # 将默认级别改为 DEBUG
    """
    设置并返回一个配置好的日志记录器。

    Args:
        name (str): 日志记录器的名称。
        log_dir (str): 日志文件保存的目录。
        level (int): 日志级别 (例如 logging.INFO, logging.DEBUG)。
    
    Returns:
        logging.Logger: 配置好的日志记录器实例。
    """
    # 确保日志目录存在
    os.makedirs(log_dir, exist_ok=True)

    # 获取当前日期作为文件名的一部分
    current_date = datetime.now().strftime("%Y%m%d")
    log_file_path = os.path.join(log_dir, f"{name}_{current_date}.log")

    # 配置日志
    # 移除可能存在的旧handler，避免重复日志
    for handler in logging.root.handlers[:]:
        if isinstance(handler, logging.FileHandler) and handler.baseFilename == log_file_path:
            logging.root.removeHandler(handler)
        if isinstance(handler, logging.StreamHandler):
            logging.root.removeHandler(handler)

    # 创建一个日志记录器
    logger = logging.getLogger(name)
    logger.setLevel(level) # 设置日志记录器的最低级别

    # 创建一个文件处理器，用于写入日志文件
    file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
    file_handler.setLevel(level) # 文件处理器也设置为 DEBUG 级别

    # 创建一个控制台处理器，用于输出到控制台
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level) # 控制台处理器也设置为 DEBUG 级别

    # 定义日志格式
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # 将处理器添加到日志记录器
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

# 如果需要，可以在这里添加一个简单的测试
if __name__ == "__main__":
    test_logger = setup_logger("test_log", level=logging.DEBUG)
    test_logger.debug("这是一条DEBUG级别的测试消息。")
    test_logger.info("这是一条INFO级别的测试消息。")
    test_logger.warning("这是一条WARNING级别的测试消息。")
    test_logger.error("这是一条ERROR级别的测试消息。")
