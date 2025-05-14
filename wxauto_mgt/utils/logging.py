"""
日志配置模块

配置系统日志记录，支持控制台输出和文件记录。
支持多实例日志管理。
"""

import os
import sys
import time
from datetime import datetime
from typing import Optional

from loguru import logger

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
    # 确保日志目录存在
    os.makedirs(log_dir, exist_ok=True)

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

    # 设置文件处理专用日志记录器的路径
    file_log_dir = os.path.dirname(log_dir)  # 使用data目录
    file_processing_log = os.path.join(file_log_dir, "logs", "file_processing.log")
    print(f"文件处理专用日志记录器已初始化，日志文件: {file_processing_log}")

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

def get_logger(name: str = None):
    """
    获取logger实例

    Args:
        name: 日志器名称

    Returns:
        Logger: logger实例
    """
    return logger.bind(name=name) if name else logger

def get_instance_logger(instance_id: str):
    """
    获取实例专用的logger

    Args:
        instance_id: 实例ID

    Returns:
        Logger: 实例专用的logger
    """
    return logger.bind(instance_id=instance_id)

def log_exception(e: Exception, context: str = "") -> None:
    """
    记录异常信息

    Args:
        e: 异常对象
        context: 上下文信息
    """
    error_msg = f"{context} - {str(e)}" if context else str(e)
    logger.exception(error_msg)

def log_api_request(method: str, url: str, params: dict = None, data: dict = None) -> None:
    """
    记录API请求信息

    Args:
        method: 请求方法
        url: 请求URL
        params: URL参数
        data: 请求数据
    """
    logger.debug(f"API请求: {method} {url}")
    if params:
        logger.debug(f"请求参数: {params}")
    if data:
        logger.debug(f"请求数据: {data}")

def log_api_response(status_code: int, response_data: dict, elapsed: float) -> None:
    """
    记录API响应信息

    Args:
        status_code: 响应状态码
        response_data: 响应数据
        elapsed: 请求耗时（秒）
    """
    logger.debug(f"API响应: 状态码={status_code}, 耗时={elapsed:.3f}秒")
    logger.debug(f"响应数据: {response_data}")

def log_performance(operation: str, elapsed: float, context: dict = None) -> None:
    """
    记录性能指标

    Args:
        operation: 操作名称
        elapsed: 操作耗时（秒）
        context: 上下文信息
    """
    msg = f"性能指标 - {operation}: {elapsed:.3f}秒"
    if context:
        msg += f" | 上下文: {context}"
    logger.debug(msg)

def get_log_file_path(instance_id: Optional[str] = None) -> str:
    """
    获取当前日志文件路径

    Args:
        instance_id: 实例ID，用于区分不同实例的日志

    Returns:
        str: 日志文件路径
    """
    # 获取应用程序的基础路径
    if getattr(sys, 'frozen', False):
        # 打包环境 - 使用可执行文件所在目录
        base_dir = os.path.dirname(sys.executable)
    else:
        # 开发环境 - 使用项目根目录
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

    # 构建日志目录路径
    log_dir = os.path.join(base_dir, 'data', 'logs')

    # 构建日志文件名
    instance_suffix = f"_{instance_id}" if instance_id else ""
    log_file = os.path.join(
        log_dir,
        f"wxauto_mgt{instance_suffix}_{time.strftime('%Y%m%d')}.log"
    )

    return log_file