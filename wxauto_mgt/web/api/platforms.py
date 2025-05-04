"""
服务平台API

提供服务平台的管理接口，包括获取平台列表、添加平台、更新平台和删除平台等功能。
"""

import logging
from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/")
async def get_platforms():
    """
    获取所有服务平台
    
    Returns:
        list: 服务平台列表
    """
    return []
