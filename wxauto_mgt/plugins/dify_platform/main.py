"""
Dify平台插件实现

该插件实现了与Dify平台的集成，支持：
- 消息发送和接收
- 会话管理
- 连接测试
- 配置验证
"""

import logging
import json
import time
import asyncio
import aiohttp
from typing import Dict, Any, List

from wxauto_mgt.core.plugin_system import (
    BaseServicePlatform, PluginInfo, MessageContext, ProcessResult, MessageType
)

logger = logging.getLogger(__name__)


class DifyPlatformPlugin(BaseServicePlatform):
    """Dify平台插件"""
    
    def __init__(self, plugin_info: PluginInfo):
        """初始化Dify平台插件"""
        super().__init__(plugin_info)
        
        # 设置支持的消息类型
        self._supported_message_types = [MessageType.TEXT, MessageType.IMAGE, MessageType.FILE]
        self._platform_type = "dify"
        
        # Dify特定配置
        self.api_base = ""
        self.api_key = ""
        self.conversation_id = ""
        self.user_id = "default_user"
        self.timeout = 30
    
    def get_config_schema(self) -> Dict[str, Any]:
        """获取配置模式定义"""
        return {
            "type": "object",
            "properties": {
                "api_base": {
                    "type": "string",
                    "title": "API基础URL",
                    "description": "Dify API的基础URL"
                },
                "api_key": {
                    "type": "string",
                    "title": "API密钥",
                    "description": "Dify API密钥",
                    "format": "password"
                },
                "conversation_id": {
                    "type": "string",
                    "title": "会话ID",
                    "description": "Dify会话ID（可选）",
                    "default": ""
                },
                "user_id": {
                    "type": "string",
                    "title": "用户ID",
                    "description": "Dify用户ID",
                    "default": "default_user"
                },
                "timeout": {
                    "type": "integer",
                    "title": "请求超时时间",
                    "description": "API请求超时时间（秒）",
                    "default": 30,
                    "minimum": 5,
                    "maximum": 300
                }
            },
            "required": ["api_base", "api_key"]
        }
    
    def validate_config(self, config: Dict[str, Any]) -> tuple[bool, str]:
        """验证配置"""
        if not config.get('api_base'):
            return False, "API基础URL不能为空"
        
        if not config.get('api_key'):
            return False, "API密钥不能为空"
        
        # 验证URL格式
        api_base = config['api_base'].strip()
        if not (api_base.startswith('http://') or api_base.startswith('https://')):
            return False, "API基础URL必须以http://或https://开头"
        
        return True, None
    
    async def _do_initialize(self):
        """执行自定义初始化逻辑"""
        # 从配置中提取参数
        self.api_base = self._config.get('api_base', '').rstrip('/')
        self.api_key = self._config.get('api_key', '')
        self.conversation_id = self._config.get('conversation_id', '')
        self.user_id = self._config.get('user_id', 'default_user')
        self.timeout = self._config.get('timeout', 30)
        
        logger.info(f"Dify插件初始化完成: {self.api_base}")
    
    async def _do_process_message(self, context: MessageContext) -> ProcessResult:
        """处理消息"""
        try:
            # 构建请求数据
            request_data = {
                "inputs": {},
                "query": context.content,
                "response_mode": "blocking",
                "user": context.sender_remark or context.sender or self.user_id
            }
            
            # 如果有会话ID，添加到请求中
            if self.conversation_id:
                request_data["conversation_id"] = self.conversation_id
            
            # 处理文件类型消息
            if context.message_type in [MessageType.IMAGE, MessageType.FILE]:
                if context.file_path:
                    request_data["files"] = [context.file_path]
                    # 对于文件消息，添加文件描述
                    if context.content:
                        request_data["query"] = f"文件: {context.content}"
                    else:
                        request_data["query"] = "请分析这个文件"
            
            # 发送请求
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            logger.info(f"发送Dify API请求: {context.message_id}")
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.post(
                    f"{self.api_base}/chat-messages",
                    headers=headers,
                    json=request_data
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Dify API错误: {response.status}, {error_text}")
                        return ProcessResult(
                            success=False,
                            error=f"API错误: {response.status}",
                            should_reply=False
                        )
                    
                    result = await response.json()
                    
                    # 提取回复内容
                    reply_content = result.get("answer", "")
                    if not reply_content:
                        logger.warning("Dify API返回空回复")
                        return ProcessResult(
                            success=True,
                            response="",
                            should_reply=False
                        )
                    
                    # 更新会话ID
                    if "conversation_id" in result:
                        self.conversation_id = result["conversation_id"]
                    
                    logger.info(f"Dify API处理成功: {context.message_id}")
                    return ProcessResult(
                        success=True,
                        response=reply_content,
                        should_reply=True,
                        metadata={
                            "conversation_id": result.get("conversation_id"),
                            "message_id": result.get("id"),
                            "usage": result.get("metadata", {}).get("usage", {})
                        }
                    )
        
        except asyncio.TimeoutError:
            logger.error(f"Dify API请求超时: {context.message_id}")
            return ProcessResult(
                success=False,
                error="请求超时",
                should_reply=False
            )
        except Exception as e:
            logger.error(f"Dify API处理失败: {context.message_id}, 错误: {e}")
            return ProcessResult(
                success=False,
                error=str(e),
                should_reply=False
            )
    
    async def _do_test_connection(self) -> Dict[str, Any]:
        """测试连接"""
        try:
            # 发送测试请求
            test_data = {
                "inputs": {},
                "query": "Hello",
                "response_mode": "blocking",
                "user": "test_user"
            }
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.post(
                    f"{self.api_base}/chat-messages",
                    headers=headers,
                    json=test_data
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return {
                            "success": True,
                            "message": "连接测试成功",
                            "response_preview": result.get("answer", "")[:100]
                        }
                    else:
                        error_text = await response.text()
                        return {
                            "success": False,
                            "error": f"HTTP {response.status}: {error_text}"
                        }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _do_health_check(self) -> Dict[str, Any]:
        """执行健康检查"""
        health_data = {}
        
        # 检查配置
        health_data["config_valid"] = bool(self.api_base and self.api_key)
        
        # 检查网络连接
        try:
            test_result = await self._do_test_connection()
            health_data["connection_ok"] = test_result.get("success", False)
            if not test_result.get("success"):
                health_data["connection_error"] = test_result.get("error")
        except Exception as e:
            health_data["connection_ok"] = False
            health_data["connection_error"] = str(e)
        
        return health_data
