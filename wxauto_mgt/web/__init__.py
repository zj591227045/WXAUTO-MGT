"""
Web服务模块

提供基于FastAPI的Web管理界面，允许通过浏览器远程管理wxauto_Mgt系统。
"""

import logging
import asyncio
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Web服务状态
web_service_running = False
web_server_app = None
web_server_instance = None

# 默认配置
DEFAULT_CONFIG = {
    "port": 8443,
    "host": "0.0.0.0",
    "debug": False,
    "reload": False,
    "workers": 1,
    "ssl_certfile": None,
    "ssl_keyfile": None,
    "auth_enabled": True,
    "token_expire_minutes": 1440,  # 24小时
    "secret_key": "wxauto_mgt_web_service_secret_key",  # 应该在生产环境中更改
}

# 当前配置
current_config = DEFAULT_CONFIG.copy()

async def start_web_service(config: Optional[Dict[str, Any]] = None) -> bool:
    """
    启动Web服务

    Args:
        config: Web服务配置，如果为None则使用默认配置

    Returns:
        bool: 是否成功启动
    """
    global web_service_running, web_server_app, web_server_instance, current_config

    if web_service_running:
        logger.warning("Web服务已经在运行")
        return True

    try:
        # 更新配置
        if config:
            current_config.update(config)

        # 导入FastAPI相关模块
        try:
            from fastapi import FastAPI
            from uvicorn import Config, Server
        except ImportError as e:
            logger.error(f"未安装FastAPI或Uvicorn: {e}")
            logger.error("请先安装: pip install fastapi uvicorn python-jose[cryptography] passlib[bcrypt]")
            return False

        # 创建FastAPI应用
        try:
            from .server import create_app
            app = create_app(current_config)
            web_server_app = app
        except Exception as e:
            logger.error(f"创建FastAPI应用失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

        # 配置Uvicorn服务器
        try:
            # 确保端口是整数
            if isinstance(current_config["port"], str):
                current_config["port"] = int(current_config["port"])

            server_config = Config(
                app=app,
                host=current_config["host"],
                port=current_config["port"],
                reload=current_config["reload"],
                workers=current_config["workers"],
                ssl_certfile=current_config["ssl_certfile"],
                ssl_keyfile=current_config["ssl_keyfile"],
                log_level="info"
            )

            # 创建服务器实例
            server = Server(server_config)
            web_server_instance = server

            # 在新线程中启动服务器
            # 使用独立的事件循环来避免Windows下的问题
            import threading

            def run_server():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(server.serve())
                except Exception as e:
                    logger.error(f"服务器运行时出错: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                finally:
                    loop.close()

            # 启动线程
            thread = threading.Thread(target=run_server, daemon=True)
            thread.start()

            # 等待服务器启动
            import time
            time.sleep(1)

            web_service_running = True
            logger.info(f"Web服务已启动: http{'s' if current_config['ssl_certfile'] else ''}://{current_config['host']}:{current_config['port']}")
            return True

        except Exception as e:
            logger.error(f"配置Uvicorn服务器失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    except Exception as e:
        logger.error(f"启动Web服务失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

async def stop_web_service() -> bool:
    """
    停止Web服务

    Returns:
        bool: 是否成功停止
    """
    global web_service_running, web_server_instance

    if not web_service_running:
        logger.warning("Web服务未运行")
        return True

    try:
        if web_server_instance:
            try:
                # 尝试正常关闭
                await web_server_instance.shutdown()
            except Exception as e:
                logger.warning(f"正常关闭Web服务失败，将强制关闭: {e}")
                # 如果正常关闭失败，强制设置状态
                pass
            finally:
                web_server_instance = None

        web_service_running = False
        logger.info("Web服务已停止")
        return True

    except Exception as e:
        logger.error(f"停止Web服务失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        # 即使出错，也强制设置为未运行状态
        web_service_running = False
        return False

def is_web_service_running() -> bool:
    """
    检查Web服务是否正在运行

    Returns:
        bool: 是否正在运行
    """
    global web_service_running
    return web_service_running

def get_web_service_config() -> Dict[str, Any]:
    """
    获取当前Web服务配置

    Returns:
        Dict[str, Any]: 当前配置
    """
    global current_config
    return current_config.copy()

def set_web_service_config(config: Dict[str, Any]) -> None:
    """
    设置Web服务配置

    Args:
        config: 新配置
    """
    global current_config
    current_config.update(config)
