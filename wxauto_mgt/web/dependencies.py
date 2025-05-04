"""
依赖注入模块

定义FastAPI依赖项，用于请求处理中的依赖注入。
"""

import logging
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from .security import get_current_user, User

logger = logging.getLogger(__name__)

# OAuth2密码Bearer
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")

async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """
    获取当前活动用户
    
    Args:
        current_user: 当前用户
        
    Returns:
        User: 当前活动用户
        
    Raises:
        HTTPException: 如果用户已禁用
    """
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="用户已禁用")
    return current_user

async def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """
    获取管理员用户
    
    Args:
        current_user: 当前用户
        
    Returns:
        User: 当前管理员用户
        
    Raises:
        HTTPException: 如果用户不是管理员
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足，需要管理员权限"
        )
    return current_user
