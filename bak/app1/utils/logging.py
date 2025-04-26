"""
WxAuto管理程序的日志模块

提供可配置的日志记录功能，包括控制台和文件输出，支持不同级别的日志记录。
"""

import os
import sys
import time
from pathlib import Path
from typing import Dict, Optional, Union

from loguru import logger

# 默认配置
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_FORMAT = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
DEFAULT_LOG_ROTATION = "500 MB"
DEFAULT_LOG_RETENTION = "10 days"


class LoggerManager:
    """
    日志管理器，用于配置和管理应用程序的日志记录
    """
    
    def __init__(self):
        """初始化日志管理器"""
        self._initialized = False
        self._log_path = None
        self._log_level = DEFAULT_LOG_LEVEL
        self._handlers_ids = {}
    
    def initialize(self, 
                  log_path: Optional[str] = None, 
                  log_level: str = DEFAULT_LOG_LEVEL,
                  console_enabled: bool = True,
                  file_enabled: bool = True,
                  log_format: str = DEFAULT_LOG_FORMAT) -> None:
        """
        初始化日志系统
        
        Args:
            log_path: 日志文件路径，默认为None（使用应用程序目录下的logs目录）
            log_level: 日志级别，默认为INFO
            console_enabled: 是否启用控制台日志，默认为True
            file_enabled: 是否启用文件日志，默认为True
            log_format: 日志格式，默认使用预定义的格式
        """
        if self._initialized:
            logger.warning("Logger already initialized")
            return
        
        # 移除默认的处理器
        logger.remove()
        
        self._log_level = log_level
        
        # 设置日志路径
        if log_path is None:
            app_dir = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            self._log_path = app_dir / "logs"
        else:
            self._log_path = Path(log_path)
        
        # 确保日志目录存在
        if file_enabled:
            os.makedirs(self._log_path, exist_ok=True)
        
        # 添加控制台处理器
        if console_enabled:
            console_handler_id = logger.add(
                sys.stderr,
                level=log_level,
                format=log_format,
                colorize=True
            )
            self._handlers_ids["console"] = console_handler_id
        
        # 添加文件处理器
        if file_enabled:
            log_file = self._log_path / "wxauto_mgt_{time}.log"
            file_handler_id = logger.add(
                str(log_file),
                level=log_level,
                format=log_format,
                rotation=DEFAULT_LOG_ROTATION,
                retention=DEFAULT_LOG_RETENTION,
                compression="zip",
                enqueue=True
            )
            self._handlers_ids["file"] = file_handler_id
        
        logger.info(f"日志系统初始化完成，日志级别：{log_level}")
        if file_enabled:
            logger.info(f"日志文件路径：{self._log_path}")
        
        self._initialized = True
    
    def set_level(self, level: str) -> None:
        """
        设置日志级别
        
        Args:
            level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        if not self._initialized:
            logger.warning("Logger not initialized, using default configuration")
            self.initialize()
        
        self._log_level = level
        for handler_id in self._handlers_ids.values():
            logger.level(handler_id, level)
        
        logger.info(f"日志级别已更改为：{level}")
    
    def get_logger(self):
        """获取日志记录器实例"""
        if not self._initialized:
            logger.warning("Logger not initialized, using default configuration")
            self.initialize()
        
        return logger
    
    @property
    def log_path(self) -> Optional[Path]:
        """获取日志文件路径"""
        return self._log_path
    
    @property
    def log_level(self) -> str:
        """获取当前日志级别"""
        return self._log_level
    
    def shutdown(self) -> None:
        """关闭日志系统"""
        if not self._initialized:
            return
        
        for handler_id in self._handlers_ids.values():
            logger.remove(handler_id)
        
        self._initialized = False
        self._handlers_ids = {}


# 创建全局日志管理器实例
log_manager = LoggerManager()

# 获取全局日志记录器
get_logger = log_manager.get_logger 