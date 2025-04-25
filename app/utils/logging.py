"""
日志工具模块

提供配置日志的工具函数
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

def setup_logger(name="wxauto_mgt", level=logging.INFO, log_dir="logs"):
    """
    设置并返回日志记录器
    
    Args:
        name: 日志记录器名称
        level: 日志级别
        log_dir: 日志文件目录
        
    Returns:
        logging.Logger: 配置好的日志记录器
    """
    # 创建日志目录
    log_dir_path = Path(log_dir)
    log_dir_path.mkdir(exist_ok=True, parents=True)
    
    # 创建日志记录器
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 如果日志记录器已经有处理器，则返回
    if logger.handlers:
        return logger
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    
    # 创建文件处理器
    file_handler = RotatingFileHandler(
        log_dir_path / f"{name}.log",
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setLevel(level)
    
    # 创建格式化器
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)
    
    # 添加处理器
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger 