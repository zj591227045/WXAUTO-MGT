"""
Web服务器实现

提供FastAPI应用创建和服务器运行功能。
"""

import os
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

    # 配置静态文件
    app.mount(
        "/static",
        StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")),
        name="static"
    )

    # 配置模板
    templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

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
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "error": "页面未找到"}
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
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "error": "服务器内部错误"}
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
    global _server_should_exit

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

    try:
        logger.info(f"Web服务器启动中，地址: http://{host}:{port}")
        # 运行服务器，直到收到退出信号
        server.run()
    except Exception as e:
        import traceback
        logger.error(f"Web服务器运行失败: {e}\n{traceback.format_exc()}")
    finally:
        logger.info("Web服务器已停止")

def stop_server():
    """停止服务器"""
    # 在这里我们不需要做任何事情，因为服务器将在线程终止时自动停止
    logger.info("正在停止Web服务器...")
