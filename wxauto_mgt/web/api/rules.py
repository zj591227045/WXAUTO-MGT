"""
转发规则API

提供消息转发规则的管理接口，包括获取规则列表、添加规则、更新规则和删除规则等功能。
"""

import logging
from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/")
async def get_rules():
    """
    获取所有转发规则
    
    Returns:
        list: 转发规则列表
    """
    return []
