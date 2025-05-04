"""
Web服务器模块

实现FastAPI应用创建和配置，包括路由注册、中间件设置和异常处理。
"""

import logging
import os
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

def create_app(config: Optional[Dict[str, Any]] = None) -> "FastAPI":
    """
    创建FastAPI应用

    Args:
        config: 应用配置

    Returns:
        FastAPI: FastAPI应用实例
    """
    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.staticfiles import StaticFiles
        from fastapi.responses import JSONResponse

        # 创建FastAPI应用
        app = FastAPI(
            title="wxauto_Mgt Web管理界面",
            description="wxauto_Mgt系统的Web管理界面",
            version="1.0.0",
            docs_url="/api/docs",
            redoc_url="/api/redoc",
            openapi_url="/api/openapi.json"
        )

        # 配置CORS
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # 在生产环境中应该限制为特定域名
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # 注册API路由
        try:
            from .api import router as api_router
            app.include_router(api_router, prefix="/api")

            # 注册WebSocket路由
            try:
                from .websockets import router as ws_router
                app.include_router(ws_router)
            except Exception as e:
                logger.error(f"注册WebSocket路由失败: {e}")
                import traceback
                logger.error(traceback.format_exc())
        except Exception as e:
            logger.error(f"注册路由失败: {e}")
            import traceback
            logger.error(traceback.format_exc())

            # 创建一个简单的路由，确保应用可以启动
            @app.get("/api/status")
            async def get_status():
                return {"status": "ok", "message": "Web服务已启动，但API路由加载失败"}

        # 异常处理
        @app.exception_handler(HTTPException)
        async def http_exception_handler(request, exc):
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
            )

        @app.exception_handler(Exception)
        async def general_exception_handler(request, exc):
            logger.error(f"未处理的异常: {exc}")
            import traceback
            logger.error(traceback.format_exc())
            return JSONResponse(
                status_code=500,
                content={"detail": "服务器内部错误"},
            )

        # 挂载前端静态文件
        frontend_path = os.path.join(os.path.dirname(__file__), "frontend", "dist")
        if os.path.exists(frontend_path):
            app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")

        # 启动和关闭事件
        @app.on_event("startup")
        async def startup_event():
            logger.info("Web服务启动中...")
            # 初始化数据库连接池等资源

        @app.on_event("shutdown")
        async def shutdown_event():
            logger.info("Web服务关闭中...")
            # 释放资源

        return app

    except Exception as e:
        logger.error(f"创建FastAPI应用失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise
