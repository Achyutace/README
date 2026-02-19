"""
全局日志配置
"""
import logging
import sys

_initialized = False

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: int = logging.INFO) -> None:
    """
    配置 root logger
    """
    global _initialized
    if _initialized:
        return

    root = logging.getLogger()
    root.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
    root.addHandler(handler)

    _initialized = True


def get_logger(name: str) -> logging.Logger:
    """获取模块级 logger"""
    return logging.getLogger(name)
