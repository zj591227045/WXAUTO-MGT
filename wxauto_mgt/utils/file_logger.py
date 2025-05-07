"""
文件处理专用日志模块

提供专门用于文件处理（下载、上传、发送）的日志记录功能
现在将所有日志重定向到主日志文件，不再单独记录file_processing.log
"""

import os
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

# 创建专用日志记录器 - 使用与主日志相同的名称，确保日志被记录到主日志文件
file_logger = logging.getLogger('wxauto_mgt')
file_logger.setLevel(logging.DEBUG)  # 设置为DEBUG级别，记录所有日志

# 标记是否已初始化
_initialized = True  # 直接标记为已初始化，避免创建单独的日志文件

def setup_file_logger(log_dir=None):
    """
    设置文件处理专用日志记录器 - 现在只是一个空函数，所有日志都会被重定向到主日志

    Args:
        log_dir: 日志目录，不再使用
    """
    # 不执行任何操作，所有日志都会被重定向到主日志
    pass

# 不再需要初始化，直接使用主日志记录器
# setup_file_logger()

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
