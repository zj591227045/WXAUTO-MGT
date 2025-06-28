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

def get_web_service_config():
    """获取Web服务配置"""
    from .config import get_web_service_config_dict
    return get_web_service_config_dict()

def set_web_service_config(config):
    """设置Web服务配置"""
    from .config import set_web_service_config_dict
    set_web_service_config_dict(config)

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
    global _web_server_thread, _web_service_running

    if _web_service_running:
        return True

    # 获取配置并初始化
    from .config import get_web_service_config
    web_config = get_web_service_config()
    await web_config.initialize()

    # 如果传入了配置，更新配置（但不覆盖密码）
    if config:
        await web_config.save_config(
            host=config.get('host'),
            port=config.get('port'),
            auto_start=config.get('auto_start')
            # 注意：不传递password参数，避免覆盖现有密码
        )

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
            args=(app, web_config.host, web_config.port),
            daemon=True
        )
        _web_server_thread.start()

        # 等待服务器启动
        time.sleep(1)

        _web_service_running = True
        logger.info(f"Web服务已启动，地址: http://{web_config.host}:{web_config.port}")
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
        logger.info("发送停止信号给Web服务器...")
        stop_server()

        # 等待线程结束
        if _web_server_thread and _web_server_thread.is_alive():
            logger.info("等待Web服务线程正常结束...")

            # 分阶段等待线程结束
            # 第一阶段：等待5秒
            _web_server_thread.join(timeout=5)

            if _web_server_thread.is_alive():
                logger.info("Web服务线程仍在运行，继续等待...")
                # 第二阶段：再等待5秒
                _web_server_thread.join(timeout=5)

                if _web_server_thread.is_alive():
                    logger.warning("Web服务线程未能在10秒内正常结束")
                    # 不强制终止线程，让它自然结束
                    # 这样可以避免段错误和其他严重问题
                else:
                    logger.info("Web服务线程已正常结束")
            else:
                logger.info("Web服务线程已正常结束")

        _web_service_running = False
        _web_server_thread = None
        logger.info("Web服务已停止")
        return True
    except Exception as e:
        logger.error(f"停止Web服务失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
