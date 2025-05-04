"""
实例数据模型

定义与wxauto实例相关的数据模型，用于API请求和响应。
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum
import time

class InstanceStatus(str, Enum):
    """实例状态枚举"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    UNKNOWN = "unknown"

class InstanceBase(BaseModel):
    """实例基础模型"""
    name: str = Field(..., description="实例名称")
    base_url: str = Field(..., description="API基础URL")
    config: Optional[Dict[str, Any]] = Field(None, description="实例配置")

class InstanceCreate(InstanceBase):
    """实例创建模型"""
    api_key: str = Field(..., description="API密钥")

class InstanceUpdate(BaseModel):
    """实例更新模型"""
    name: Optional[str] = Field(None, description="实例名称")
    base_url: Optional[str] = Field(None, description="API基础URL")
    api_key: Optional[str] = Field(None, description="API密钥")
    enabled: Optional[bool] = Field(None, description="是否启用")
    config: Optional[Dict[str, Any]] = Field(None, description="实例配置")

class InstanceResponse(InstanceBase):
    """实例响应模型"""
    instance_id: str = Field(..., description="实例ID")
    status: InstanceStatus = Field(..., description="实例状态")
    enabled: bool = Field(..., description="是否启用")
    last_active: Optional[int] = Field(None, description="最后活动时间")
    created_at: int = Field(..., description="创建时间")
    updated_at: int = Field(..., description="更新时间")

    class Config:
        orm_mode = True
