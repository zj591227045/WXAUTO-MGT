"""
简单回声插件实现

这是一个示例插件，展示了如何开发WXAUTO-MGT插件的基本流程。
该插件将收到的消息原样返回，并可以添加前缀和后缀。
"""

import logging
import asyncio
from typing import Dict, Any

from wxauto_mgt.core.plugin_system import (
    BaseServicePlatform, PluginInfo, MessageContext, ProcessResult, MessageType
)

logger = logging.getLogger(__name__)


class SimpleEchoPlugin(BaseServicePlatform):
    """简单回声插件"""
    
    def __init__(self, plugin_info: PluginInfo):
        """
        初始化插件
        
        Args:
            plugin_info: 插件信息
        """
        super().__init__(plugin_info)
        
        # 设置支持的消息类型
        self._supported_message_types = [MessageType.TEXT]
        self._platform_type = "echo"
        
        # 插件配置参数
        self.prefix = "回声: "
        self.suffix = ""
        self.enabled = True
        self.delay_seconds = 0.5
        self.max_length = 200
        
        # 统计信息
        self.message_count = 0
        self.total_characters = 0
    
    def get_config_schema(self) -> Dict[str, Any]:
        """
        获取配置模式定义
        
        Returns:
            Dict[str, Any]: JSON Schema格式的配置定义
        """
        return {
            "type": "object",
            "properties": {
                "prefix": {
                    "type": "string",
                    "title": "回复前缀",
                    "description": "在回复消息前添加的前缀文本",
                    "default": "回声: "
                },
                "suffix": {
                    "type": "string",
                    "title": "回复后缀",
                    "description": "在回复消息后添加的后缀文本",
                    "default": ""
                },
                "enabled": {
                    "type": "boolean",
                    "title": "启用插件",
                    "description": "是否启用此插件",
                    "default": True
                },
                "delay_seconds": {
                    "type": "number",
                    "title": "回复延迟",
                    "description": "回复前的延迟时间（秒）",
                    "default": 0.5,
                    "minimum": 0.0,
                    "maximum": 10.0
                },
                "max_length": {
                    "type": "integer",
                    "title": "最大长度",
                    "description": "回复消息的最大长度，超过将被截断",
                    "default": 200,
                    "minimum": 10,
                    "maximum": 1000
                }
            },
            "required": []
        }
    
    def validate_config(self, config: Dict[str, Any]) -> tuple[bool, str]:
        """
        验证配置
        
        Args:
            config: 配置数据
            
        Returns:
            tuple[bool, str]: (是否有效, 错误信息)
        """
        try:
            # 验证延迟时间
            delay = config.get('delay_seconds', 0.5)
            if not isinstance(delay, (int, float)) or delay < 0 or delay > 10:
                return False, "回复延迟必须在0到10秒之间"
            
            # 验证最大长度
            max_length = config.get('max_length', 200)
            if not isinstance(max_length, int) or max_length < 10 or max_length > 1000:
                return False, "最大长度必须在10到1000字符之间"
            
            # 验证前缀和后缀长度
            prefix = config.get('prefix', '')
            suffix = config.get('suffix', '')
            if len(prefix) + len(suffix) >= max_length:
                return False, "前缀和后缀的总长度不能超过最大长度"
            
            return True, ""
            
        except Exception as e:
            return False, f"配置验证失败: {str(e)}"
    
    async def _do_initialize(self):
        """执行自定义初始化逻辑"""
        # 从配置中提取参数
        self.prefix = self._config.get('prefix', '回声: ')
        self.suffix = self._config.get('suffix', '')
        self.enabled = self._config.get('enabled', True)
        self.delay_seconds = self._config.get('delay_seconds', 0.5)
        self.max_length = self._config.get('max_length', 200)
        
        # 重置统计信息
        self.message_count = 0
        self.total_characters = 0
        
        logger.info(f"简单回声插件初始化完成: 前缀='{self.prefix}', 后缀='{self.suffix}', 启用={self.enabled}")
    
    async def _do_process_message(self, context: MessageContext) -> ProcessResult:
        """
        处理消息
        
        Args:
            context: 消息上下文
            
        Returns:
            ProcessResult: 处理结果
        """
        try:
            # 检查插件是否启用
            if not self.enabled:
                logger.debug("插件已禁用，跳过消息处理")
                return ProcessResult(
                    success=True,
                    response="",
                    should_reply=False,
                    metadata={"reason": "plugin_disabled"}
                )
            
            # 获取消息内容
            content = context.content.strip()
            if not content:
                logger.debug("消息内容为空，跳过处理")
                return ProcessResult(
                    success=True,
                    response="",
                    should_reply=False,
                    metadata={"reason": "empty_content"}
                )
            
            logger.info(f"处理回声消息: {content[:50]}{'...' if len(content) > 50 else ''}")
            
            # 添加延迟（模拟处理时间）
            if self.delay_seconds > 0:
                await asyncio.sleep(self.delay_seconds)
            
            # 构建回复消息
            reply_content = f"{self.prefix}{content}{self.suffix}"
            
            # 检查长度限制
            if len(reply_content) > self.max_length:
                # 截断内容，保留前缀和后缀
                available_length = self.max_length - len(self.prefix) - len(self.suffix) - 3  # 3个字符用于"..."
                if available_length > 0:
                    truncated_content = content[:available_length] + "..."
                    reply_content = f"{self.prefix}{truncated_content}{self.suffix}"
                else:
                    # 如果前缀和后缀太长，只保留部分内容
                    reply_content = reply_content[:self.max_length]
            
            # 更新统计信息
            self.message_count += 1
            self.total_characters += len(content)
            
            logger.info(f"回声插件处理成功: {context.message_id}")
            
            return ProcessResult(
                success=True,
                response=reply_content,
                should_reply=True,
                metadata={
                    "original_length": len(content),
                    "reply_length": len(reply_content),
                    "truncated": len(reply_content) >= self.max_length,
                    "message_count": self.message_count,
                    "total_characters": self.total_characters
                }
            )
        
        except Exception as e:
            logger.error(f"回声插件处理失败: {context.message_id}, 错误: {e}")
            return ProcessResult(
                success=False,
                error=str(e),
                should_reply=False
            )
    
    async def _do_test_connection(self) -> Dict[str, Any]:
        """
        测试连接
        
        Returns:
            Dict[str, Any]: 测试结果
        """
        try:
            # 回声插件不需要外部连接，只需要检查配置
            if not self.enabled:
                return {
                    "success": False,
                    "error": "插件已禁用"
                }
            
            # 模拟测试处理
            test_message = "测试消息"
            test_reply = f"{self.prefix}{test_message}{self.suffix}"
            
            return {
                "success": True,
                "message": "回声插件测试成功",
                "test_input": test_message,
                "test_output": test_reply,
                "config": {
                    "prefix": self.prefix,
                    "suffix": self.suffix,
                    "max_length": self.max_length,
                    "delay_seconds": self.delay_seconds
                }
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _do_health_check(self) -> Dict[str, Any]:
        """
        执行健康检查
        
        Returns:
            Dict[str, Any]: 健康检查结果
        """
        health_data = {}
        
        # 检查配置状态
        health_data["config_valid"] = True
        health_data["enabled"] = self.enabled
        health_data["prefix"] = self.prefix
        health_data["suffix"] = self.suffix
        health_data["max_length"] = self.max_length
        health_data["delay_seconds"] = self.delay_seconds
        
        # 统计信息
        health_data["statistics"] = {
            "message_count": self.message_count,
            "total_characters": self.total_characters,
            "average_length": self.total_characters / max(self.message_count, 1)
        }
        
        # 性能指标
        metrics = self.get_metrics()
        health_data["performance"] = {
            "total_calls": metrics.get("total_calls", 0),
            "successful_calls": metrics.get("successful_calls", 0),
            "failed_calls": metrics.get("failed_calls", 0),
            "success_rate": metrics.get("successful_calls", 0) / max(metrics.get("total_calls", 1), 1) * 100,
            "average_response_time": metrics.get("average_response_time", 0)
        }
        
        return health_data
    
    async def _do_self_diagnose(self) -> Dict[str, Any]:
        """
        执行自我诊断
        
        Returns:
            Dict[str, Any]: 诊断结果
        """
        diagnosis = {}
        recommendations = []
        
        # 检查配置合理性
        if self.delay_seconds > 5:
            recommendations.append("回复延迟时间较长，可能影响用户体验")
        
        if len(self.prefix) + len(self.suffix) > self.max_length * 0.5:
            recommendations.append("前缀和后缀占用过多字符，建议缩短")
        
        if not self.enabled:
            recommendations.append("插件当前已禁用")
        
        # 检查性能
        metrics = self.get_metrics()
        error_rate = metrics.get("failed_calls", 0) / max(metrics.get("total_calls", 1), 1)
        if error_rate > 0.1:  # 错误率超过10%
            recommendations.append("错误率较高，建议检查配置或重启插件")
        
        if metrics.get("average_response_time", 0) > 2.0:
            recommendations.append("平均响应时间较长，建议优化配置")
        
        diagnosis["recommendations"] = recommendations
        diagnosis["health_score"] = max(0, 100 - len(recommendations) * 20)  # 每个问题扣20分
        
        return diagnosis
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取插件统计信息
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        return {
            "message_count": self.message_count,
            "total_characters": self.total_characters,
            "average_length": self.total_characters / max(self.message_count, 1),
            "config": {
                "prefix": self.prefix,
                "suffix": self.suffix,
                "max_length": self.max_length,
                "delay_seconds": self.delay_seconds,
                "enabled": self.enabled
            }
        }


# 插件工厂函数（可选）
def create_plugin(plugin_info: PluginInfo) -> SimpleEchoPlugin:
    """
    创建插件实例
    
    Args:
        plugin_info: 插件信息
        
    Returns:
        SimpleEchoPlugin: 插件实例
    """
    return SimpleEchoPlugin(plugin_info)


# 插件元数据（可选）
PLUGIN_METADATA = {
    "name": "简单回声插件",
    "description": "一个简单的示例插件，用于演示插件开发流程",
    "version": "1.0.0",
    "author": "WXAUTO-MGT Team",
    "category": "示例插件",
    "features": [
        "消息回声",
        "可配置前缀后缀",
        "长度限制",
        "延迟模拟",
        "统计功能"
    ]
}
