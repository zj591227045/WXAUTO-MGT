"""
WebSocket模块

提供实时数据更新的WebSocket接口，包括消息实时流、状态更新和日志流。
"""

from fastapi import APIRouter

router = APIRouter()

# 导入各WebSocket路由
try:
    from .messages import router as messages_ws_router
    from .status import router as status_ws_router

    # 注册WebSocket路由
    router.include_router(messages_ws_router)
    router.include_router(status_ws_router)
except Exception as e:
    import logging
    logging.getLogger(__name__).error(f"加载WebSocket路由失败: {e}")
    import traceback
    logging.getLogger(__name__).error(traceback.format_exc())

# 导出所有路由
__all__ = ["router"]
