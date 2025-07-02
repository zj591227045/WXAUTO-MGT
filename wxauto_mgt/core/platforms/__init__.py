"""
服务平台模块

该模块包含所有服务平台的实现，每个平台都实现了统一的ServicePlatform接口。

支持的平台类型：
- dify: Dify AI平台
- openai: OpenAI兼容平台  
- zhiweijz: 只为记账平台
- keyword: 关键词匹配平台
"""

from .base_platform import ServicePlatform

__all__ = ['ServicePlatform']
