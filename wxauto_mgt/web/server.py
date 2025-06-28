"""
Web服务器实现

提供FastAPI应用创建和服务器运行功能。
"""

import os
import sys
import signal
import threading
import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from typing import Optional
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.cors import CORSMiddleware
from wxauto_mgt.utils.logging import logger

# 全局变量
_shutdown_requested = False
_server = None
_server_should_exit = threading.Event()


def get_resource_path(relative_path):
    """获取资源文件的绝对路径，兼容开发环境和打包后的exe"""
    try:
        # PyInstaller打包后的临时目录
        base_path = sys._MEIPASS
    except AttributeError:
        # 开发环境
        base_path = os.path.dirname(__file__)

    return os.path.join(base_path, relative_path)
_server_should_exit = threading.Event()

def create_app():
    """
    创建FastAPI应用

    Returns:
        FastAPI: FastAPI应用实例
    """
    # 创建FastAPI应用
    app = FastAPI(
        title="wxauto_Mgt Web管理界面",
        description="提供Web管理界面功能，允许通过浏览器管理wxauto实例、服务平台和消息转发规则。",
        version="0.1.0"
    )

    # 配置CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 配置静态文件路径（兼容打包后的exe）
    static_dir = get_resource_path("static")
    if not os.path.exists(static_dir):
        # 如果在打包环境中找不到，尝试从wxauto_mgt/web/static查找
        static_dir = get_resource_path(os.path.join("wxauto_mgt", "web", "static"))

    if os.path.exists(static_dir):
        app.mount(
            "/static",
            StaticFiles(directory=static_dir),
            name="static"
        )
        logger.info(f"静态文件目录: {static_dir}")
    else:
        logger.warning(f"静态文件目录不存在: {static_dir}")

    # 配置模板路径（兼容打包后的exe）
    templates_dir = get_resource_path("templates")
    if not os.path.exists(templates_dir):
        # 如果在打包环境中找不到，尝试从wxauto_mgt/web/templates查找
        templates_dir = get_resource_path(os.path.join("wxauto_mgt", "web", "templates"))

    if os.path.exists(templates_dir):
        templates = Jinja2Templates(directory=templates_dir)
        logger.info(f"模板文件目录: {templates_dir}")
    else:
        logger.error(f"模板文件目录不存在: {templates_dir}")
        # 创建一个空的模板对象以避免错误
        templates = None

    # 初始化安全模块
    @app.on_event("startup")
    async def startup_event():
        """应用启动时的初始化"""
        try:
            # 首先初始化Web服务配置
            from .config import get_web_service_config
            web_config = get_web_service_config()
            await web_config.initialize()
            logger.info("Web服务配置初始化完成")

            # 然后初始化安全模块
            from .security import initialize_security
            await initialize_security()
            logger.info("安全模块初始化完成")
        except Exception as e:
            logger.error(f"启动初始化失败: {e}")
            import traceback
            traceback.print_exc()

    # 注册API路由
    from .api import api_router
    app.include_router(api_router, prefix="/api")

    # 注册路由
    from .routes import register_routes
    register_routes(app, templates)

    # 错误处理
    @app.exception_handler(404)
    async def not_found_exception_handler(request: Request, exc: HTTPException):
        # 如果是API请求，检查是否是路由函数内部抛出的HTTPException
        if request.url.path.startswith("/api/"):
            # 如果异常有自定义的detail信息，保留原始信息
            if hasattr(exc, 'detail') and exc.detail and exc.detail != "Not Found":
                return JSONResponse(
                    status_code=404,
                    content={"detail": exc.detail}
                )
            else:
                # 只有在真正的路由未找到时才返回通用消息
                return JSONResponse(
                    status_code=404,
                    content={"detail": "API端点未找到"}
                )
        # 否则返回HTML错误页面
        if templates:
            return templates.TemplateResponse(
                "error.html",
                {"request": request, "error": "页面未找到"}
            )
        else:
            return JSONResponse(
                status_code=404,
                content={"detail": "页面未找到"}
            )

    @app.exception_handler(500)
    async def server_error_exception_handler(request: Request, exc: HTTPException):
        # 如果是API请求，返回JSON错误
        if request.url.path.startswith("/api/"):
            return JSONResponse(
                status_code=500,
                content={"detail": "服务器内部错误"}
            )
        # 否则返回HTML错误页面
        if templates:
            return templates.TemplateResponse(
                "error.html",
                {"request": request, "error": "服务器内部错误"}
            )
        else:
            return JSONResponse(
                status_code=500,
                content={"detail": "服务器内部错误"}
            )

    return app

def run_server(app, host, port):
    """
    在线程中运行FastAPI服务器

    Args:
        app: FastAPI应用实例
        host: 主机地址
        port: 端口号
    """
    global _server_should_exit, _server

    # 重置退出事件
    _server_should_exit.clear()

    # 配置Uvicorn服务器
    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        log_level="info",
        reload=False
    )

    # 创建服务器
    server = uvicorn.Server(config)
    _server = server  # 保存服务器实例以便停止

    try:
        logger.info(f"Web服务器启动中，地址: http://{host}:{port}")
        # 运行服务器，直到收到退出信号
        server.run()
    except Exception as e:
        import traceback
        logger.error(f"Web服务器运行失败: {e}\n{traceback.format_exc()}")
    finally:
        # 清理全局变量
        _server = None
        logger.info("Web服务器已停止")

def stop_server():
    """停止服务器"""
    global _server, _server_should_exit, _shutdown_requested

    logger.info("正在停止Web服务器...")

    try:
        # 设置停止标志
        _shutdown_requested = True
        _server_should_exit.set()

        # 如果服务器实例存在，尝试停止它
        if _server:
            # 停止服务器
            _server.should_exit = True
            if hasattr(_server, 'force_exit'):
                _server.force_exit = True
            logger.info("已发送停止信号给Web服务器")
        else:
            logger.warning("Web服务器实例不存在")

    except Exception as e:
        logger.error(f"停止Web服务器时出错: {e}")
        import traceback
        logger.error(traceback.format_exc())
