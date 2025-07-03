"""
Web服务安全模块

提供JWT token验证、密码哈希等安全功能。
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

from wxauto_mgt.utils.logging import logger
from wxauto_mgt.data.config_store import config_store

# JWT配置
JWT_SECRET_KEY = None  # 将在初始化时生成
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# HTTP Bearer token scheme
security = HTTPBearer()

async def initialize_security():
    """初始化安全模块"""
    global JWT_SECRET_KEY
    
    try:
        # 从配置中获取或生成JWT密钥
        JWT_SECRET_KEY = await config_store.get_config('system', 'jwt_secret_key', None)
        
        if not JWT_SECRET_KEY:
            # 生成新的JWT密钥
            JWT_SECRET_KEY = secrets.token_urlsafe(32)
            await config_store.set_config('system', 'jwt_secret_key', JWT_SECRET_KEY)
            logger.info("已生成新的JWT密钥")
        else:
            logger.info("已加载JWT密钥")
            
    except Exception as e:
        logger.error(f"初始化安全模块失败: {e}")
        # 使用临时密钥
        JWT_SECRET_KEY = secrets.token_urlsafe(32)

def hash_password(password: str) -> str:
    """
    对密码进行哈希处理
    
    Args:
        password: 原始密码
        
    Returns:
        str: 哈希后的密码
    """
    # 使用SHA256进行哈希
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def verify_password(password: str, hashed_password: str) -> bool:
    """
    验证密码
    
    Args:
        password: 原始密码
        hashed_password: 哈希后的密码
        
    Returns:
        bool: 密码是否正确
    """
    return hash_password(password) == hashed_password

async def get_web_service_password() -> Optional[str]:
    """
    获取web服务密码

    Returns:
        Optional[str]: 哈希后的密码，如果未设置则返回None
    """
    try:
        from .config import get_web_service_config
        web_config = get_web_service_config()
        return web_config.password
    except Exception as e:
        logger.error(f"获取web服务密码失败: {e}")
        return None

async def set_web_service_password(password: str) -> bool:
    """
    设置web服务密码

    Args:
        password: 原始密码

    Returns:
        bool: 是否设置成功
    """
    try:
        from .config import get_web_service_config
        web_config = get_web_service_config()
        success = await web_config.save_config(password=password)
        if success:
            logger.info("web服务密码已更新")
        return success
    except Exception as e:
        logger.error(f"设置web服务密码失败: {e}")
        return False

def create_access_token(data: Dict[str, Any]) -> str:
    """
    创建JWT访问令牌
    
    Args:
        data: 要编码的数据
        
    Returns:
        str: JWT令牌
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """
    验证JWT令牌

    Args:
        token: JWT令牌

    Returns:
        Optional[Dict[str, Any]]: 解码后的数据，如果验证失败则返回None
    """
    try:
        # logger.debug(f"JWT验证: token={token[:50] if token else 'None'}...")  # 避免循环日志
        # logger.debug(f"JWT验证: 使用密钥={JWT_SECRET_KEY[:20] if JWT_SECRET_KEY else 'None'}...")  # 避免循环日志
        # logger.debug(f"JWT验证: 算法={JWT_ALGORITHM}")  # 避免循环日志

        if not JWT_SECRET_KEY:
            logger.error("JWT验证失败: JWT密钥未设置")
            return None

        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        logger.debug(f"JWT验证成功: payload={payload}")
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("JWT令牌已过期")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"JWT令牌验证失败: {e}")
        return None
    except Exception as e:
        logger.error(f"JWT验证时发生未知错误: {e}")
        return None

async def authenticate_password(password: str) -> bool:
    """
    验证web服务密码
    
    Args:
        password: 原始密码
        
    Returns:
        bool: 密码是否正确
    """
    try:
        stored_password = await get_web_service_password()
        
        # 如果没有设置密码，则不需要验证
        if not stored_password:
            logger.info("web服务未设置密码，跳过验证")
            return True
            
        return verify_password(password, stored_password)
    except Exception as e:
        logger.error(f"验证密码失败: {e}")
        return False

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """
    获取当前用户（通过JWT令牌验证）
    
    Args:
        credentials: HTTP Bearer认证凭据
        
    Returns:
        Dict[str, Any]: 用户信息
        
    Raises:
        HTTPException: 认证失败时抛出
    """
    # 检查是否设置了密码
    stored_password = await get_web_service_password()
    if not stored_password:
        # 如果没有设置密码，则跳过验证
        return {"user": "anonymous", "authenticated": False}
    
    # 验证令牌
    payload = verify_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return {"user": payload.get("sub", "user"), "authenticated": True}

async def optional_auth(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Dict[str, Any]:
    """
    可选的身份验证（如果没有设置密码则跳过验证）
    
    Args:
        credentials: HTTP Bearer认证凭据（可选）
        
    Returns:
        Dict[str, Any]: 用户信息
    """
    try:
        # 检查是否设置了密码
        stored_password = await get_web_service_password()
        if not stored_password:
            # 如果没有设置密码，则跳过验证
            return {"user": "anonymous", "authenticated": False}
        
        # 如果设置了密码但没有提供令牌
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="需要认证令牌",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # 验证令牌
        payload = verify_token(credentials.credentials)
        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的认证令牌",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return {"user": payload.get("sub", "user"), "authenticated": True}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"身份验证失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="身份验证服务错误"
        )

async def check_password_required() -> bool:
    """
    检查是否需要密码验证

    Returns:
        bool: 是否需要密码验证
    """
    try:
        stored_password = await get_web_service_password()
        return bool(stored_password)
    except Exception as e:
        logger.error(f"检查密码要求失败: {e}")
        return False

async def verify_api_access(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    """
    验证API访问权限的依赖函数

    Args:
        credentials: HTTP Bearer认证凭据（可选）

    Returns:
        Dict[str, Any]: 用户信息

    Raises:
        HTTPException: 认证失败时抛出
    """
    try:
        # 检查是否设置了密码
        stored_password = await get_web_service_password()
        if not stored_password:
            # 如果没有设置密码，则跳过验证
            return {"user": "anonymous", "authenticated": False}

        # 如果设置了密码但没有提供令牌
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="需要认证令牌",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 验证令牌
        payload = verify_token(credentials.credentials)
        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的认证令牌",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return {"user": payload.get("sub", "user"), "authenticated": True}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API访问验证失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="身份验证服务错误"
        )
