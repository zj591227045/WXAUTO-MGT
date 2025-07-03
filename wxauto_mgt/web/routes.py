"""
路由定义

定义Web管理界面的所有路由。
"""

from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from wxauto_mgt.utils.logging import logger

async def check_auth(request: Request):
    """检查用户认证状态，如果需要认证但未通过则返回重定向响应"""
    try:
        from .security import check_password_required
        password_required = await check_password_required()
        logger.debug(f"认证检查: password_required={password_required}")

        if password_required:
            # 检查Cookie中的token
            token = request.cookies.get("auth_token")
            logger.debug(f"认证检查: token存在={bool(token)}")

            if not token:
                # 没有token，重定向到登录页面
                logger.debug("认证检查: 没有token，重定向到登录页面")
                return RedirectResponse(url="/login", status_code=302)

            # 验证token
            from .security import verify_token
            payload = verify_token(token)
            logger.debug(f"认证检查: token验证结果={payload}")

            if payload is None:
                # token无效，重定向到登录页面
                logger.debug("认证检查: token无效，重定向到登录页面")
                response = RedirectResponse(url="/login", status_code=302)
                response.delete_cookie("auth_token")
                return response
            else:
                logger.debug("认证检查: token验证成功")
    except Exception as e:
        logger.error(f"认证检查失败: {e}")
        # 出错时不阻止访问
        pass
    return None

def register_routes(app: FastAPI, templates: Jinja2Templates):
    """
    注册所有路由

    Args:
        app: FastAPI应用实例
        templates: Jinja2模板引擎
    """
    # API路由现在在server.py中注册
    logger.info("注册Web路由")

    # 登录页面
    @app.get("/login", response_class=HTMLResponse)
    async def login_page(request: Request):
        """登录页面"""
        if templates:
            return templates.TemplateResponse(
                "login.html",
                {
                    "request": request,
                    "title": "登录 - wxauto_Mgt"
                }
            )
        else:
            return JSONResponse(
                status_code=200,
                content={"message": "登录页面", "page": "login"}
            )

    # 首页（仪表盘）
    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        """首页（仪表盘）"""
        # 检查认证
        auth_response = await check_auth(request)
        if auth_response:
            return auth_response

        if templates:
            return templates.TemplateResponse(
                "index.html",
                {
                    "request": request,
                    "title": "仪表盘 - wxauto_Mgt"
                }
            )
        else:
            return JSONResponse(
                status_code=200,
                content={"message": "WxAuto管理工具 - 仪表盘", "status": "running"}
            )

    # 实例管理页面
    @app.get("/instances", response_class=HTMLResponse)
    async def instances(request: Request):
        """实例管理页面"""
        # 检查认证
        auth_response = await check_auth(request)
        if auth_response:
            return auth_response

        if templates:
            return templates.TemplateResponse(
                "instances.html",
                {
                    "request": request,
                    "title": "实例管理 - wxauto_Mgt"
                }
            )
        else:
            return JSONResponse(
                status_code=200,
                content={"message": "实例管理页面", "page": "instances"}
            )

    # 服务平台和消息转发规则管理页面
    @app.get("/platforms", response_class=HTMLResponse)
    async def platforms(request: Request):
        """服务平台和消息转发规则管理页面"""
        # 检查认证
        auth_response = await check_auth(request)
        if auth_response:
            return auth_response

        if templates:
            return templates.TemplateResponse(
                "platforms.html",
                {
                    "request": request,
                    "title": "服务平台和规则管理 - wxauto_Mgt"
                }
            )
        else:
            return JSONResponse(
                status_code=200,
                content={"message": "服务平台和规则管理页面", "page": "platforms"}
            )

    # 消息监控页面
    @app.get("/messages", response_class=HTMLResponse)
    async def messages(request: Request):
        """消息监控页面"""
        # 检查认证
        auth_response = await check_auth(request)
        if auth_response:
            return auth_response

        if templates:
            import time
            return templates.TemplateResponse(
                "messages.html",
                {
                    "request": request,
                    "title": "消息监控 - wxauto_Mgt",
                    "timestamp": int(time.time())
                }
            )
        else:
            return JSONResponse(
                status_code=200,
                content={"message": "消息监控页面", "page": "messages"}
            )
