"""
文件处理专用日志模块

提供专门用于文件处理（下载、上传、发送）的日志记录功能
"""

import os
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

# 创建专用日志记录器
file_logger = logging.getLogger('file_processing')
file_logger.setLevel(logging.DEBUG)  # 设置为DEBUG级别，记录所有日志

# 标记是否已初始化
_initialized = False

def setup_file_logger(log_dir=None):
    """
    设置文件处理专用日志记录器
    
    Args:
        log_dir: 日志目录，如果为None，则使用默认的data/logs目录
    """
    global _initialized
    
    if _initialized:
        return
    
    # 设置日志目录
    if log_dir is None:
        # 使用项目根目录下的data/logs目录
        project_root = Path(__file__).parent.parent.parent
        log_dir = os.path.join(project_root, 'data', 'logs')
    
    # 确保日志目录存在
    os.makedirs(log_dir, exist_ok=True)
    
    # 设置日志文件路径
    log_file = os.path.join(log_dir, 'file_processing.log')
    
    # 创建文件处理器
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    
    # 设置日志格式
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(name)s - %(funcName)s:%(lineno)d - %(message)s'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # 添加处理器
    file_logger.addHandler(file_handler)
    file_logger.addHandler(console_handler)
    
    # 标记为已初始化
    _initialized = True
    
    file_logger.info(f"文件处理专用日志记录器已初始化，日志文件: {log_file}")

# 初始化日志记录器
setup_file_logger()

# 导出日志记录函数
def debug(msg, *args, **kwargs):
    """记录DEBUG级别日志"""
    file_logger.debug(msg, *args, **kwargs)

def info(msg, *args, **kwargs):
    """记录INFO级别日志"""
    file_logger.info(msg, *args, **kwargs)

def warning(msg, *args, **kwargs):
    """记录WARNING级别日志"""
    file_logger.warning(msg, *args, **kwargs)

def error(msg, *args, **kwargs):
    """记录ERROR级别日志"""
    file_logger.error(msg, *args, **kwargs)

def critical(msg, *args, **kwargs):
    """记录CRITICAL级别日志"""
    file_logger.critical(msg, *args, **kwargs)

def exception(msg, *args, **kwargs):
    """记录异常日志"""
    file_logger.exception(msg, *args, **kwargs)
