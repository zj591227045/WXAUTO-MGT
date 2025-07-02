"""
服务平台基类

定义了所有服务平台必须实现的标准接口。
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any

logger = logging.getLogger(__name__)


class ServicePlatform(ABC):
    """服务平台基类，定义所有平台必须实现的接口"""

    def __init__(self, platform_id: str, name: str, config: Dict[str, Any]):
        """
        初始化服务平台

        Args:
            platform_id: 平台唯一标识符
            name: 平台显示名称
            config: 平台配置字典
        """
        self.platform_id = platform_id
        self.name = name
        self.config = config
        self._initialized = False
        # 消息发送模式：normal(普通模式)或typing(打字机模式)，默认为normal
        self.message_send_mode = config.get('message_send_mode', 'normal')

    @abstractmethod
    async def initialize(self) -> bool:
        """
        初始化平台，验证配置和建立连接

        Returns:
            bool: 初始化是否成功
        """
        pass

    @abstractmethod
    async def process_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理消息的核心方法

        Args:
            message: 消息数据，包含以下字段：
                - content: 消息内容
                - sender: 发送者
                - sender_remark: 发送者备注
                - chat_name: 聊天对象名称
                - instance_id: 实例ID
                - message_id: 消息ID
                - mtype: 消息类型

        Returns:
            Dict[str, Any]: 处理结果，包含：
                - success: bool, 是否处理成功（可选）
                - content: str, 回复内容
                - error: str, 错误信息（可选）
                - raw_response: Any, 原始响应数据（可选）
                - should_reply: bool, 是否应该发送回复（可选）
                - conversation_id: str, 会话ID（可选）
        """
        pass

    @abstractmethod
    async def test_connection(self) -> Dict[str, Any]:
        """
        测试平台连接状态

        Returns:
            Dict[str, Any]: 测试结果，包含：
                - success: bool, 测试是否成功
                - message: str, 测试结果描述
                - error: str, 错误信息（可选）
                - data: Any, 额外数据（可选）
        """
        pass

    @abstractmethod
    def get_type(self) -> str:
        """
        获取平台类型标识符

        Returns:
            str: 平台类型（如 'dify', 'openai', 'zhiweijz', 'keyword'）
        """
        pass

    def get_safe_config(self) -> Dict[str, Any]:
        """
        获取安全的配置（隐藏敏感信息）

        Returns:
            Dict[str, Any]: 隐藏敏感信息后的配置
        """
        safe_config = self.config.copy()
        # 隐藏敏感信息
        sensitive_keys = ['api_key', 'token', 'secret', 'password']
        for key in sensitive_keys:
            if key in safe_config:
                safe_config[key] = '******'
        return safe_config

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式

        Returns:
            Dict[str, Any]: 平台信息字典
        """
        return {
            'platform_id': self.platform_id,
            'name': self.name,
            'type': self.get_type(),
            'config': self.get_safe_config(),
            'initialized': self._initialized
        }

    async def cleanup(self):
        """
        清理资源（可选实现）
        """
        pass

    def get_stats(self) -> Dict[str, Any]:
        """
        获取平台统计信息（可选实现）

        Returns:
            Dict[str, Any]: 统计信息
        """
        return {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0
        }
