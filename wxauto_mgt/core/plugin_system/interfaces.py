"""
插件系统接口定义

该模块定义了WXAUTO-MGT插件系统的标准接口，包括：
- IPlugin: 插件基础接口
- IServicePlatform: 服务平台插件接口
- IMessageProcessor: 消息处理接口
- IConfigurable: 可配置接口
- IHealthCheck: 健康检查接口
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Union
from enum import Enum
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


class PluginState(Enum):
    """插件状态枚举"""
    UNLOADED = "unloaded"      # 未加载
    LOADED = "loaded"          # 已加载
    INITIALIZED = "initialized" # 已初始化
    ACTIVE = "active"          # 活跃状态
    INACTIVE = "inactive"      # 非活跃状态
    ERROR = "error"            # 错误状态
    DISABLED = "disabled"      # 已禁用


class MessageType(Enum):
    """消息类型枚举"""
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    VOICE = "voice"
    VIDEO = "video"
    LOCATION = "location"
    LINK = "link"
    SYSTEM = "system"


@dataclass
class PluginInfo:
    """插件信息"""
    plugin_id: str
    name: str
    version: str
    description: str
    author: str
    homepage: Optional[str] = None
    license: Optional[str] = None
    dependencies: Optional[List[str]] = None
    min_wxauto_version: Optional[str] = None
    max_wxauto_version: Optional[str] = None
    permissions: Optional[List[str]] = None
    tags: Optional[List[str]] = None


@dataclass
class MessageContext:
    """消息上下文"""
    message_id: str
    instance_id: str
    chat_name: str
    sender: str
    sender_remark: Optional[str] = None
    message_type: MessageType = MessageType.TEXT
    content: str = ""
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    timestamp: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ProcessResult:
    """处理结果"""
    success: bool
    response: Optional[str] = None
    error: Optional[str] = None
    should_reply: bool = True
    metadata: Optional[Dict[str, Any]] = None
    next_action: Optional[str] = None


class IPlugin(ABC):
    """插件基础接口"""
    
    @abstractmethod
    def get_info(self) -> PluginInfo:
        """
        获取插件信息
        
        Returns:
            PluginInfo: 插件信息
        """
        pass
    
    @abstractmethod
    async def initialize(self, config: Dict[str, Any]) -> bool:
        """
        初始化插件
        
        Args:
            config: 插件配置
            
        Returns:
            bool: 是否初始化成功
        """
        pass
    
    @abstractmethod
    async def activate(self) -> bool:
        """
        激活插件
        
        Returns:
            bool: 是否激活成功
        """
        pass
    
    @abstractmethod
    async def deactivate(self) -> bool:
        """
        停用插件
        
        Returns:
            bool: 是否停用成功
        """
        pass
    
    @abstractmethod
    async def cleanup(self) -> bool:
        """
        清理插件资源
        
        Returns:
            bool: 是否清理成功
        """
        pass
    
    @abstractmethod
    def get_state(self) -> PluginState:
        """
        获取插件状态
        
        Returns:
            PluginState: 插件状态
        """
        pass


class IServicePlatform(IPlugin):
    """服务平台插件接口"""
    
    @abstractmethod
    async def process_message(self, context: MessageContext) -> ProcessResult:
        """
        处理消息
        
        Args:
            context: 消息上下文
            
        Returns:
            ProcessResult: 处理结果
        """
        pass
    
    @abstractmethod
    async def test_connection(self) -> Dict[str, Any]:
        """
        测试连接
        
        Returns:
            Dict[str, Any]: 测试结果
        """
        pass
    
    @abstractmethod
    def get_supported_message_types(self) -> List[MessageType]:
        """
        获取支持的消息类型
        
        Returns:
            List[MessageType]: 支持的消息类型列表
        """
        pass
    
    @abstractmethod
    def get_platform_type(self) -> str:
        """
        获取平台类型标识
        
        Returns:
            str: 平台类型
        """
        pass


class IMessageProcessor(ABC):
    """消息处理接口"""
    
    @abstractmethod
    async def can_process(self, context: MessageContext) -> bool:
        """
        检查是否可以处理该消息
        
        Args:
            context: 消息上下文
            
        Returns:
            bool: 是否可以处理
        """
        pass
    
    @abstractmethod
    async def preprocess_message(self, context: MessageContext) -> MessageContext:
        """
        预处理消息
        
        Args:
            context: 消息上下文
            
        Returns:
            MessageContext: 处理后的消息上下文
        """
        pass
    
    @abstractmethod
    async def postprocess_result(self, result: ProcessResult, context: MessageContext) -> ProcessResult:
        """
        后处理结果
        
        Args:
            result: 处理结果
            context: 消息上下文
            
        Returns:
            ProcessResult: 处理后的结果
        """
        pass


class IConfigurable(ABC):
    """可配置接口"""
    
    @abstractmethod
    def get_config_schema(self) -> Dict[str, Any]:
        """
        获取配置模式定义
        
        Returns:
            Dict[str, Any]: JSON Schema格式的配置定义
        """
        pass
    
    @abstractmethod
    def validate_config(self, config: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        验证配置
        
        Args:
            config: 配置数据
            
        Returns:
            tuple[bool, Optional[str]]: (是否有效, 错误信息)
        """
        pass
    
    @abstractmethod
    async def update_config(self, config: Dict[str, Any]) -> bool:
        """
        更新配置
        
        Args:
            config: 新配置
            
        Returns:
            bool: 是否更新成功
        """
        pass
    
    @abstractmethod
    def get_config(self) -> Dict[str, Any]:
        """
        获取当前配置
        
        Returns:
            Dict[str, Any]: 当前配置
        """
        pass


class IHealthCheck(ABC):
    """健康检查接口"""
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """
        执行健康检查
        
        Returns:
            Dict[str, Any]: 健康检查结果
        """
        pass
    
    @abstractmethod
    def get_metrics(self) -> Dict[str, Any]:
        """
        获取性能指标
        
        Returns:
            Dict[str, Any]: 性能指标
        """
        pass
    
    @abstractmethod
    async def self_diagnose(self) -> Dict[str, Any]:
        """
        自我诊断
        
        Returns:
            Dict[str, Any]: 诊断结果
        """
        pass
