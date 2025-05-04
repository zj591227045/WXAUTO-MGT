"""
API路由模块

集中管理所有API路由，包括实例管理、服务平台管理、消息转发规则管理等。
"""

from fastapi import APIRouter

router = APIRouter()

# 导入各模块路由
try:
    from .auth import router as auth_router
    from .instances import router as instances_router
    from .platforms import router as platforms_router
    from .rules import router as rules_router
    from .messages import router as messages_router
    from .system import router as system_router

    # 注册路由
    router.include_router(auth_router, prefix="/auth", tags=["认证"])
    router.include_router(instances_router, prefix="/instances", tags=["实例管理"])
    router.include_router(platforms_router, prefix="/platforms", tags=["服务平台"])
    router.include_router(rules_router, prefix="/rules", tags=["转发规则"])
    router.include_router(messages_router, prefix="/messages", tags=["消息管理"])
    router.include_router(system_router, prefix="/system", tags=["系统管理"])
except Exception as e:
    import logging
    logging.getLogger(__name__).error(f"加载API路由失败: {e}")
    import traceback
    logging.getLogger(__name__).error(traceback.format_exc())

    # 创建一个简单的路由，确保应用可以启动
    from fastapi import APIRouter as SimpleRouter
    simple_router = SimpleRouter()

    @simple_router.get("/status")
    async def get_status():
        return {"status": "ok", "message": "API路由加载失败，仅提供基本功能"}

    # 注册简单路由
    router.include_router(simple_router, prefix="/system", tags=["系统管理"])

# 导出所有路由
__all__ = ["router"]
