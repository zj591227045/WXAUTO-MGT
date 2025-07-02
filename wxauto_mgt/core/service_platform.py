"""
服务平台模块

该模块定义了服务平台的工厂函数和导入接口。
具体的平台实现已移动到platforms子目录中。
"""

import logging
from typing import Dict, Any, Optional

# 导入标准日志记录器
logger = logging.getLogger('wxauto_mgt')

# 导入基类和各平台实现
from .platforms.base_platform import ServicePlatform
from .platforms.dify_platform import DifyPlatform
from .platforms.openai_platform import OpenAIPlatform
from .platforms.keyword_platform import KeywordMatchPlatform
from .platforms.zhiweijz_platform import ZhiWeiJZPlatform
from .platforms.coze_platform import CozeServicePlatform


def create_platform(platform_type: str, platform_id: str, name: str, config: Dict[str, Any]) -> Optional[ServicePlatform]:
    """
    创建服务平台实例

    Args:
        platform_type: 平台类型
        platform_id: 平台ID
        name: 平台名称
        config: 平台配置

    Returns:
        Optional[ServicePlatform]: 服务平台实例
    """
    if platform_type == "dify":
        return DifyPlatform(platform_id, name, config)
    elif platform_type == "openai":
        return OpenAIPlatform(platform_id, name, config)
    elif platform_type == "keyword" or platform_type == "keyword_match":
        return KeywordMatchPlatform(platform_id, name, config)
    elif platform_type == "zhiweijz":
        return ZhiWeiJZPlatform(platform_id, name, config)
    elif platform_type == "coze":
        return CozeServicePlatform(platform_id, name, config)
    else:
        logger.error(f"不支持的平台类型: {platform_type}")
        return None


# 为了向后兼容，导出所有类
__all__ = [
    'ServicePlatform',
    'DifyPlatform',
    'OpenAIPlatform',
    'KeywordMatchPlatform',
    'ZhiWeiJZPlatform',
    'create_platform'
]