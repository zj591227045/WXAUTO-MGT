"""
插件基类实现

该模块提供了插件系统的基础实现类，包括：
- BasePlugin: 插件基类
- BaseServicePlatform: 服务平台插件基类
- PluginException: 插件异常类
"""

import logging
import time
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime

from .interfaces import (
    IPlugin, IServicePlatform, IMessageProcessor, IConfigurable, IHealthCheck,
    PluginInfo, PluginState, MessageContext, ProcessResult, MessageType
)

logger = logging.getLogger(__name__)


class PluginException(Exception):
    """插件异常"""
    
    def __init__(self, message: str, plugin_id: str = None, error_code: str = None):
        super().__init__(message)
        self.plugin_id = plugin_id
        self.error_code = error_code
        self.timestamp = datetime.now()


class BasePlugin(IPlugin, IConfigurable, IHealthCheck):
    """插件基类"""
    
    def __init__(self, plugin_info: PluginInfo):
        """
        初始化插件
        
        Args:
            plugin_info: 插件信息
        """
        self._info = plugin_info
        self._state = PluginState.UNLOADED
        self._config = {}
        self._initialized = False
        self._active = False
        self._error_count = 0
        self._last_error = None
        self._start_time = None
        self._metrics = {
            'total_calls': 0,
            'successful_calls': 0,
            'failed_calls': 0,
            'average_response_time': 0.0,
            'last_call_time': None
        }
    
    def get_info(self) -> PluginInfo:
        """获取插件信息"""
        return self._info
    
    def get_state(self) -> PluginState:
        """获取插件状态"""
        return self._state
    
    async def initialize(self, config: Dict[str, Any]) -> bool:
        """
        初始化插件
        
        Args:
            config: 插件配置
            
        Returns:
            bool: 是否初始化成功
        """
        try:
            logger.info(f"初始化插件: {self._info.name}")
            
            # 验证配置
            is_valid, error_msg = self.validate_config(config)
            if not is_valid:
                raise PluginException(f"配置验证失败: {error_msg}", self._info.plugin_id)
            
            self._config = config.copy()
            self._state = PluginState.LOADED
            
            # 执行自定义初始化
            await self._do_initialize()
            
            self._initialized = True
            self._state = PluginState.INITIALIZED
            self._start_time = datetime.now()
            
            logger.info(f"插件初始化成功: {self._info.name}")
            return True
            
        except Exception as e:
            self._state = PluginState.ERROR
            self._last_error = str(e)
            self._error_count += 1
            logger.error(f"插件初始化失败: {self._info.name}, 错误: {e}")
            return False
    
    async def activate(self) -> bool:
        """激活插件"""
        try:
            if not self._initialized:
                raise PluginException("插件未初始化", self._info.plugin_id)
            
            logger.info(f"激活插件: {self._info.name}")
            
            # 执行自定义激活逻辑
            await self._do_activate()
            
            self._active = True
            self._state = PluginState.ACTIVE
            
            logger.info(f"插件激活成功: {self._info.name}")
            return True
            
        except Exception as e:
            self._state = PluginState.ERROR
            self._last_error = str(e)
            self._error_count += 1
            logger.error(f"插件激活失败: {self._info.name}, 错误: {e}")
            return False
    
    async def deactivate(self) -> bool:
        """停用插件"""
        try:
            logger.info(f"停用插件: {self._info.name}")
            
            # 执行自定义停用逻辑
            await self._do_deactivate()
            
            self._active = False
            self._state = PluginState.INACTIVE
            
            logger.info(f"插件停用成功: {self._info.name}")
            return True
            
        except Exception as e:
            self._state = PluginState.ERROR
            self._last_error = str(e)
            self._error_count += 1
            logger.error(f"插件停用失败: {self._info.name}, 错误: {e}")
            return False
    
    async def cleanup(self) -> bool:
        """清理插件资源"""
        try:
            logger.info(f"清理插件: {self._info.name}")
            
            # 执行自定义清理逻辑
            await self._do_cleanup()
            
            self._initialized = False
            self._active = False
            self._state = PluginState.UNLOADED
            
            logger.info(f"插件清理成功: {self._info.name}")
            return True
            
        except Exception as e:
            self._state = PluginState.ERROR
            self._last_error = str(e)
            self._error_count += 1
            logger.error(f"插件清理失败: {self._info.name}, 错误: {e}")
            return False
    
    # 配置接口实现
    def get_config_schema(self) -> Dict[str, Any]:
        """获取配置模式定义 - 子类应重写此方法"""
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    def validate_config(self, config: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """验证配置 - 子类可重写此方法"""
        return True, None
    
    async def update_config(self, config: Dict[str, Any]) -> bool:
        """更新配置"""
        try:
            is_valid, error_msg = self.validate_config(config)
            if not is_valid:
                return False
            
            old_config = self._config.copy()
            self._config = config.copy()
            
            # 执行配置更新逻辑
            success = await self._do_config_update(old_config, config)
            if not success:
                self._config = old_config  # 回滚配置
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"更新插件配置失败: {self._info.name}, 错误: {e}")
            return False
    
    def get_config(self) -> Dict[str, Any]:
        """获取当前配置"""
        return self._config.copy()
    
    # 健康检查接口实现
    async def health_check(self) -> Dict[str, Any]:
        """执行健康检查"""
        try:
            # 基础健康检查
            health_data = {
                'plugin_id': self._info.plugin_id,
                'name': self._info.name,
                'state': self._state.value,
                'initialized': self._initialized,
                'active': self._active,
                'error_count': self._error_count,
                'last_error': self._last_error,
                'uptime': self._get_uptime(),
                'healthy': self._state == PluginState.ACTIVE and self._error_count < 10
            }
            
            # 执行自定义健康检查
            custom_health = await self._do_health_check()
            health_data.update(custom_health)
            
            return health_data
            
        except Exception as e:
            return {
                'plugin_id': self._info.plugin_id,
                'healthy': False,
                'error': str(e)
            }
    
    def get_metrics(self) -> Dict[str, Any]:
        """获取性能指标"""
        return self._metrics.copy()
    
    async def self_diagnose(self) -> Dict[str, Any]:
        """自我诊断"""
        try:
            diagnosis = {
                'plugin_id': self._info.plugin_id,
                'state_check': self._state in [PluginState.ACTIVE, PluginState.INACTIVE],
                'config_check': bool(self._config),
                'error_rate': self._error_count / max(self._metrics['total_calls'], 1),
                'recommendations': []
            }
            
            # 添加建议
            if self._error_count > 5:
                diagnosis['recommendations'].append("错误次数过多，建议检查配置或重启插件")
            
            if self._metrics['average_response_time'] > 10.0:
                diagnosis['recommendations'].append("响应时间过长，建议优化处理逻辑")
            
            # 执行自定义诊断
            custom_diagnosis = await self._do_self_diagnose()
            diagnosis.update(custom_diagnosis)
            
            return diagnosis
            
        except Exception as e:
            return {
                'plugin_id': self._info.plugin_id,
                'error': str(e)
            }
    
    # 内部方法
    def _get_uptime(self) -> Optional[float]:
        """获取运行时间（秒）"""
        if self._start_time:
            return (datetime.now() - self._start_time).total_seconds()
        return None
    
    def _record_call(self, success: bool, response_time: float = 0.0):
        """记录调用统计"""
        self._metrics['total_calls'] += 1
        self._metrics['last_call_time'] = datetime.now()
        
        if success:
            self._metrics['successful_calls'] += 1
        else:
            self._metrics['failed_calls'] += 1
            self._error_count += 1
        
        # 更新平均响应时间
        total_time = self._metrics['average_response_time'] * (self._metrics['total_calls'] - 1)
        self._metrics['average_response_time'] = (total_time + response_time) / self._metrics['total_calls']
    
    # 子类需要实现的方法
    async def _do_initialize(self):
        """执行自定义初始化逻辑"""
        pass
    
    async def _do_activate(self):
        """执行自定义激活逻辑"""
        pass
    
    async def _do_deactivate(self):
        """执行自定义停用逻辑"""
        pass
    
    async def _do_cleanup(self):
        """执行自定义清理逻辑"""
        pass
    
    async def _do_config_update(self, old_config: Dict[str, Any], new_config: Dict[str, Any]) -> bool:
        """执行配置更新逻辑"""
        return True
    
    async def _do_health_check(self) -> Dict[str, Any]:
        """执行自定义健康检查"""
        return {}
    
    async def _do_self_diagnose(self) -> Dict[str, Any]:
        """执行自定义诊断"""
        return {}


class BaseServicePlatform(BasePlugin, IServicePlatform, IMessageProcessor):
    """服务平台插件基类"""

    def __init__(self, plugin_info: PluginInfo):
        """
        初始化服务平台插件

        Args:
            plugin_info: 插件信息
        """
        super().__init__(plugin_info)
        self._supported_message_types = [MessageType.TEXT]
        self._platform_type = "unknown"

    async def process_message(self, context: MessageContext) -> ProcessResult:
        """
        处理消息

        Args:
            context: 消息上下文

        Returns:
            ProcessResult: 处理结果
        """
        start_time = time.time()

        try:
            if not self._active:
                return ProcessResult(
                    success=False,
                    error="插件未激活",
                    should_reply=False
                )

            # 检查是否可以处理该消息
            if not await self.can_process(context):
                return ProcessResult(
                    success=False,
                    error="不支持的消息类型",
                    should_reply=False
                )

            # 预处理消息
            processed_context = await self.preprocess_message(context)

            # 执行实际处理
            result = await self._do_process_message(processed_context)

            # 后处理结果
            final_result = await self.postprocess_result(result, processed_context)

            # 记录成功调用
            response_time = time.time() - start_time
            self._record_call(True, response_time)

            return final_result

        except Exception as e:
            # 记录失败调用
            response_time = time.time() - start_time
            self._record_call(False, response_time)

            logger.error(f"处理消息失败: {self._info.name}, 错误: {e}")
            return ProcessResult(
                success=False,
                error=str(e),
                should_reply=False
            )

    async def test_connection(self) -> Dict[str, Any]:
        """
        测试连接

        Returns:
            Dict[str, Any]: 测试结果
        """
        try:
            if not self._initialized:
                return {
                    'success': False,
                    'error': '插件未初始化'
                }

            # 执行自定义连接测试
            result = await self._do_test_connection()
            return result

        except Exception as e:
            logger.error(f"测试连接失败: {self._info.name}, 错误: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def get_supported_message_types(self) -> List[MessageType]:
        """获取支持的消息类型"""
        return self._supported_message_types.copy()

    def get_platform_type(self) -> str:
        """获取平台类型标识"""
        return self._platform_type

    # 消息处理接口实现
    async def can_process(self, context: MessageContext) -> bool:
        """
        检查是否可以处理该消息

        Args:
            context: 消息上下文

        Returns:
            bool: 是否可以处理
        """
        return context.message_type in self._supported_message_types

    async def preprocess_message(self, context: MessageContext) -> MessageContext:
        """
        预处理消息

        Args:
            context: 消息上下文

        Returns:
            MessageContext: 处理后的消息上下文
        """
        # 默认不做任何处理，子类可以重写
        return context

    async def postprocess_result(self, result: ProcessResult, context: MessageContext) -> ProcessResult:
        """
        后处理结果

        Args:
            result: 处理结果
            context: 消息上下文

        Returns:
            ProcessResult: 处理后的结果
        """
        # 默认不做任何处理，子类可以重写
        return result

    # 子类需要实现的方法
    async def _do_process_message(self, context: MessageContext) -> ProcessResult:
        """
        执行实际的消息处理逻辑

        Args:
            context: 消息上下文

        Returns:
            ProcessResult: 处理结果
        """
        raise NotImplementedError("子类必须实现 _do_process_message 方法")

    async def _do_test_connection(self) -> Dict[str, Any]:
        """
        执行实际的连接测试逻辑

        Returns:
            Dict[str, Any]: 测试结果
        """
        raise NotImplementedError("子类必须实现 _do_test_connection 方法")
