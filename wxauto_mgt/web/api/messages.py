"""
消息API

提供消息的管理接口，包括获取消息列表、获取消息详情、更新消息状态和重试消息处理等功能。
"""

import logging
from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/")
async def get_messages():
    """
    获取所有消息
    
    Returns:
        list: 消息列表
    """
    return []
