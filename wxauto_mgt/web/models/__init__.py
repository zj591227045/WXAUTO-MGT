"""
数据模型模块

定义API请求和响应的数据模型。
"""

# 导出所有模型
from .instance import InstanceCreate, InstanceUpdate, InstanceResponse, InstanceStatus

__all__ = [
    "InstanceCreate", 
    "InstanceUpdate", 
    "InstanceResponse", 
    "InstanceStatus"
]
