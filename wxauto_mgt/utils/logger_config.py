"""
日志配置模块

提供详细的日志配置，支持控制台和文件输出
"""

import os
import logging
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
import json
import traceback
import sys

# 日志级别
DEBUG = logging.DEBUG
INFO = logging.INFO
WARNING = logging.WARNING
ERROR = logging.ERROR
CRITICAL = logging.CRITICAL

# 日志格式
DEFAULT_FORMAT = '%(asctime)s - %(levelname)s - %(name)s - %(message)s'
DETAILED_FORMAT = '%(asctime)s - %(levelname)s - %(name)s:%(funcName)s:%(lineno)d - %(message)s'

# 全局日志配置
_loggers = {}
_log_dir = None
_default_level = DEBUG
_default_format = DETAILED_FORMAT
_max_bytes = 10 * 1024 * 1024  # 10MB
_backup_count = 5

def setup_log_dir(base_dir=None):
    """
    设置日志目录
    
    Args:
        base_dir: 基础目录，如果为None，则使用当前工作目录
    """
    global _log_dir
    
    if base_dir is None:
        # 使用项目根目录
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    # 创建日志目录
    log_dir = os.path.join(base_dir, 'data', 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    _log_dir = log_dir
    return log_dir

def get_logger(name, level=None, log_file=None, log_format=None, console=True):
    """
    获取日志记录器
    
    Args:
        name: 日志记录器名称
        level: 日志级别
        log_file: 日志文件名，如果为None，则使用name.log
        log_format: 日志格式
        console: 是否输出到控制台
        
    Returns:
        logging.Logger: 日志记录器
    """
    global _loggers, _log_dir, _default_level, _default_format
    
    # 如果已经创建过，直接返回
    if name in _loggers:
        return _loggers[name]
    
    # 确保日志目录已设置
    if _log_dir is None:
        _log_dir = setup_log_dir()
    
    # 设置默认值
    if level is None:
        level = _default_level
    
    if log_format is None:
        log_format = _default_format
    
    if log_file is None:
        log_file = f"{name.replace('.', '_')}.log"
    
    # 创建日志记录器
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 清除已有的处理器
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # 创建格式化器
    formatter = logging.Formatter(log_format)
    
    # 创建文件处理器
    log_path = os.path.join(_log_dir, log_file)
    file_handler = RotatingFileHandler(
        log_path, 
        maxBytes=_max_bytes, 
        backupCount=_backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # 如果需要，添加控制台处理器
    if console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # 保存日志记录器
    _loggers[name] = logger
    
    return logger

def get_debug_logger(name, console=False):
    """
    获取调试日志记录器，使用更详细的日志格式
    
    Args:
        name: 日志记录器名称
        console: 是否输出到控制台
        
    Returns:
        logging.Logger: 日志记录器
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = f"debug_{name.replace('.', '_')}_{timestamp}.log"
    return get_logger(name, DEBUG, log_file, DETAILED_FORMAT, console)

def get_module_logger(module_name, level=None, console=True):
    """
    获取模块日志记录器
    
    Args:
        module_name: 模块名称
        level: 日志级别
        console: 是否输出到控制台
        
    Returns:
        logging.Logger: 日志记录器
    """
    if level is None:
        level = INFO
    
    log_file = f"{module_name.replace('.', '_')}.log"
    return get_logger(module_name, level, log_file, DEFAULT_FORMAT, console)

def log_exception(logger, exc_info=None, level=ERROR):
    """
    记录异常信息
    
    Args:
        logger: 日志记录器
        exc_info: 异常信息，如果为None，则使用sys.exc_info()
        level: 日志级别
    """
    if exc_info is None:
        exc_info = sys.exc_info()
    
    if exc_info[0] is not None:
        tb_lines = traceback.format_exception(*exc_info)
        logger.log(level, "异常详情:\n%s", ''.join(tb_lines))

def log_dict(logger, data, message="字典数据:", level=DEBUG):
    """
    记录字典数据
    
    Args:
        logger: 日志记录器
        data: 字典数据
        message: 日志消息
        level: 日志级别
    """
    try:
        json_str = json.dumps(data, ensure_ascii=False, indent=2)
        logger.log(level, "%s\n%s", message, json_str)
    except Exception as e:
        logger.error("无法序列化字典数据: %s", str(e))
        logger.log(level, "%s %s", message, str(data))

def configure_root_logger(level=INFO, log_file="app.log", console=True):
    """
    配置根日志记录器
    
    Args:
        level: 日志级别
        log_file: 日志文件名
        console: 是否输出到控制台
    """
    # 确保日志目录已设置
    if _log_dir is None:
        setup_log_dir()
    
    # 配置根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # 清除已有的处理器
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 创建格式化器
    formatter = logging.Formatter(DEFAULT_FORMAT)
    
    # 创建文件处理器
    log_path = os.path.join(_log_dir, log_file)
    file_handler = RotatingFileHandler(
        log_path, 
        maxBytes=_max_bytes, 
        backupCount=_backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # 如果需要，添加控制台处理器
    if console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    
    return root_logger

# 初始化日志目录
setup_log_dir()
