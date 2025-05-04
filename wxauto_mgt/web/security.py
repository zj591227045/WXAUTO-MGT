"""
安全模块

提供认证和授权功能，包括JWT令牌生成和验证、密码哈希和验证等。
"""

import logging
import time
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# 配置
SECRET_KEY = "wxauto_mgt_web_service_secret_key"  # 应该在生产环境中更改
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24小时

# 密码上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2密码Bearer
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")

class User(BaseModel):
    """用户模型"""
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = None
    role: str = "user"

class TokenData(BaseModel):
    """令牌数据模型"""
    username: Optional[str] = None

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码
    
    Args:
        plain_password: 明文密码
        hashed_password: 哈希密码
        
    Returns:
        bool: 密码是否匹配
    """
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """
    获取密码哈希
    
    Args:
        password: 明文密码
        
    Returns:
        str: 哈希密码
    """
    return pwd_context.hash(password)

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    创建访问令牌
    
    Args:
        data: 令牌数据
        expires_delta: 过期时间增量
        
    Returns:
        str: JWT令牌
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_user(username: str) -> Optional[User]:
    """
    获取用户
    
    Args:
        username: 用户名
        
    Returns:
        Optional[User]: 用户信息，如果不存在则返回None
    """
    # 这里应该从数据库获取用户信息
    # 临时使用硬编码的用户信息
    if username == "admin":
        return User(
            username="admin",
            email="admin@example.com",
            full_name="Admin User",
            disabled=False,
            role="admin"
        )
    return None

async def authenticate_user(username: str, password: str) -> Optional[User]:
    """
    认证用户
    
    Args:
        username: 用户名
        password: 密码
        
    Returns:
        Optional[User]: 认证成功的用户，如果认证失败则返回None
    """
    user = await get_user(username)
    if not user:
        return None
    # 这里应该从数据库获取密码哈希并验证
    # 临时使用硬编码的密码
    if username == "admin" and password == "admin":
        return user
    return None

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """
    获取当前用户
    
    Args:
        token: JWT令牌
        
    Returns:
        User: 当前用户
        
    Raises:
        HTTPException: 如果令牌无效或用户不存在
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的认证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = await get_user(username=token_data.username)
    if user is None:
        raise credentials_exception
    return user

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
