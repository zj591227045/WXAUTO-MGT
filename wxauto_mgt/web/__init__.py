"""
wxauto_Mgt Web管理界面模块

提供Web管理界面功能，允许通过浏览器管理wxauto实例、服务平台和消息转发规则。
使用FastAPI和Jinja2模板引擎实现，支持数据和日志实时刷新显示。
"""

import threading
import time
import os
import sys
from wxauto_mgt.utils.logging import logger

# 全局变量
_web_server_thread = None
_web_service_running = False
_web_service_config = {
    'port': 8080,
    'host': '0.0.0.0'
}

def get_web_service_config():
    """获取Web服务配置"""
    return _web_service_config.copy()

def set_web_service_config(config):
    """设置Web服务配置"""
    global _web_service_config
    _web_service_config.update(config)

def is_web_service_running():
    """检查Web服务是否运行"""
    return _web_service_running

async def start_web_service(config=None):
    """
    启动Web服务

    Args:
        config: 配置字典，包含host和port

    Returns:
        bool: 是否成功启动
    """
    global _web_server_thread, _web_service_running, _web_service_config

    if _web_service_running:
        return True

    if config:
        _web_service_config.update(config)

    # 确保数据库已初始化
    from wxauto_mgt.data.db_manager import db_manager
    if not db_manager._initialized:
        logger.info("初始化数据库...")
        await db_manager.initialize()
        logger.info("数据库初始化完成")

    try:
        # 检查依赖项
        try:
            import fastapi
            import uvicorn
            import jinja2
        except ImportError as e:
            error_msg = f"缺少必要的依赖项: {e}\n请安装: pip install fastapi uvicorn jinja2"
            logger.error(error_msg)
            return False

        # 延迟导入，避免循环导入
        from .server import create_app, run_server

        app = create_app()

        # 创建新线程运行FastAPI服务器
        _web_server_thread = threading.Thread(
            target=run_server,
            args=(app, _web_service_config['host'], _web_service_config['port']),
            daemon=True
        )
        _web_server_thread.start()

        # 等待服务器启动
        time.sleep(1)

        _web_service_running = True
        logger.info(f"Web服务已启动，地址: http://{_web_service_config['host']}:{_web_service_config['port']}")
        return True
    except Exception as e:
        import traceback
        logger.error(f"启动Web服务失败: {e}\n{traceback.format_exc()}")
        return False

async def stop_web_service():
    """
    停止Web服务

    Returns:
        bool: 是否成功停止
    """
    global _web_server_thread, _web_service_running

    if not _web_service_running:
        return True

    try:
        # 延迟导入，避免循环导入
        from .server import stop_server

        # 设置停止标志
        stop_server()

        # 等待线程结束
        if _web_server_thread and _web_server_thread.is_alive():
            logger.info("等待Web服务线程正常结束...")

            # 等待线程正常结束
            _web_server_thread.join(timeout=10)

            # 如果线程仍然存活，记录警告但不强制终止
            if _web_server_thread.is_alive():
                logger.warning("Web服务线程未能在10秒内正常结束，但将继续等待其自然结束")
                # 不使用强制终止，避免Segmentation fault

        _web_service_running = False
        _web_server_thread = None
        logger.info("Web服务已停止")
        return True
    except Exception as e:
        logger.error(f"停止Web服务失败: {e}")
        return False
