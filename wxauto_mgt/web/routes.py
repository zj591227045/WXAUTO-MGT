"""
路由定义

定义Web管理界面的所有路由。
"""

from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from wxauto_mgt.utils.logging import logger

def register_routes(app: FastAPI, templates: Jinja2Templates):
    """
    注册所有路由

    Args:
        app: FastAPI应用实例
        templates: Jinja2模板引擎
    """
    # API路由现在在server.py中注册
    logger.info("注册Web路由")

    # 首页（仪表盘）
    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        """首页（仪表盘）"""
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "title": "仪表盘 - wxauto_Mgt"
            }
        )

    # 实例管理页面
    @app.get("/instances", response_class=HTMLResponse)
    async def instances(request: Request):
        """实例管理页面"""
        return templates.TemplateResponse(
            "instances.html",
            {
                "request": request,
                "title": "实例管理 - wxauto_Mgt"
            }
        )

    # 服务平台和消息转发规则管理页面
    @app.get("/platforms", response_class=HTMLResponse)
    async def platforms(request: Request):
        """服务平台和消息转发规则管理页面"""
        return templates.TemplateResponse(
            "platforms.html",
            {
                "request": request,
                "title": "服务平台和规则管理 - wxauto_Mgt"
            }
        )

    # 消息监控页面
    @app.get("/messages", response_class=HTMLResponse)
    async def messages(request: Request):
        """消息监控页面"""
        return templates.TemplateResponse(
            "messages.html",
            {
                "request": request,
                "title": "消息监控 - wxauto_Mgt"
            }
        )
