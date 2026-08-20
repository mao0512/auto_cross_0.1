import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
import os

# 创建logs文件夹
LOG_DIR = Path(__file__).parent.parent.parent / "logs"
os.makedirs(LOG_DIR, exist_ok=True)

def setup_logger():
    logger = logging.getLogger("auto_cross")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    # 日志格式
    log_format = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 按天分割日志，保留30天
    file_handler = TimedRotatingFileHandler(
        filename=LOG_DIR / "auto_cross.log",
        when="D",
        interval=1,
        backupCount=30,
        encoding="utf-8"
    )
    file_handler.setFormatter(log_format)

    # 控制台输出
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_format)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger

# 全局日志实例
logger = setup_logger()