"""
日志工具模块

提供日志设置和获取功能
"""

import os
import sys
import time
import logging
from datetime import datetime
from typing import Optional

# 导出原始logging.py中的logger变量
try:
    from loguru import logger
except ImportError:
    # 如果loguru不可用，使用标准logging
    logger = logging.getLogger("wxauto_mgt")

def setup_logging(
    log_dir: str,
    console_level: str = "INFO",
    file_level: str = "DEBUG",
    retention: str = "7 days",
    rotation: str = "500 MB",
    instance_id: Optional[str] = None
) -> None:
    """
    配置日志系统
    
    Args:
        log_dir: 日志文件目录
        console_level: 控制台日志级别
        file_level: 文件日志级别
        retention: 日志保留时间
        rotation: 日志文件轮转大小
        instance_id: 实例ID，用于区分不同实例的日志
    """
    try:
        # 确保日志目录存在
        os.makedirs(log_dir, exist_ok=True)
        
        # 如果是使用loguru
        if "remove" in dir(logger):
            # 移除默认处理器
            logger.remove()
            
            # 添加控制台处理器
            logger.add(
                sys.stdout,
                level=console_level,
                format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                "<level>{message}</level>",
                backtrace=True,
                diagnose=True
            )
            
            # 构建日志文件名
            instance_suffix = f"_{instance_id}" if instance_id else ""
            log_file = os.path.join(
                log_dir,
                f"wxauto_mgt{instance_suffix}_{time.strftime('%Y%m%d')}.log"
            )
            
            # 添加文件处理器
            logger.add(
                log_file,
                level=file_level,
                format="{time:YYYY-MM-DD HH:mm:ss.SSS} | "
                "{level: <8} | "
                "{name}:{function}:{line} | "
                "{message}",
                rotation=rotation,
                retention=retention,
                encoding="utf-8",
                backtrace=True,
                diagnose=True
            )
            
            logger.info(f"日志系统初始化完成，日志文件：{log_file}")
        else:
            # 使用标准logging
            # 设置根日志器级别
            logger.setLevel(getattr(logging, console_level))
            
            # 添加控制台处理器
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(getattr(logging, console_level))
            console_formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(name)s:%(funcName)s:%(lineno)d - %(message)s'
            )
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)
            
            # 添加文件处理器
            instance_suffix = f"_{instance_id}" if instance_id else ""
            log_file = os.path.join(
                log_dir,
                f"wxauto_mgt{instance_suffix}_{time.strftime('%Y%m%d')}.log"
            )
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(getattr(logging, file_level))
            file_formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(name)s:%(funcName)s:%(lineno)d - %(message)s'
            )
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
            
            logger.info(f"日志系统初始化完成，日志文件：{log_file}")
    except Exception as e:
        print(f"日志系统初始化失败: {str(e)}")
        # 确保提供基本日志功能
        logging.basicConfig(level=logging.INFO)

def get_logger(name: str = None):
    """
    获取logger实例
    
    Args:
        name: 日志器名称
        
    Returns:
        Logger: logger实例
    """
    # 兼容loguru和标准logging
    if hasattr(logger, "bind"):
        return logger.bind(name=name) if name else logger
    else:
        return logging.getLogger(name) if name else logger

def setup_logger(name=None):
    """
    设置并返回一个logger实例
    
    Args:
        name: logger名称
        
    Returns:
        logging.Logger: 日志记录器实例
    """
    return get_logger(name) 