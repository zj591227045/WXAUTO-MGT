"""
服务模块

提供业务逻辑服务，处理API请求和数据库操作。
"""

# 导出所有服务
from .instance_service import InstanceService

__all__ = ["InstanceService"]
