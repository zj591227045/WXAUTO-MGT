"""
OpenAI平台插件实现

该插件实现了与OpenAI API的集成，支持：
- GPT模型对话
- 多种模型选择
- 系统提示配置
- 参数调节
"""

import logging
import json
import time
import asyncio
import aiohttp
from typing import Dict, Any

from wxauto_mgt.core.plugin_system import (
    BaseServicePlatform, PluginInfo, MessageContext, ProcessResult, MessageType
)

logger = logging.getLogger(__name__)


class OpenAIPlatformPlugin(BaseServicePlatform):
    """OpenAI平台插件"""
    
    def __init__(self, plugin_info: PluginInfo):
        """初始化OpenAI平台插件"""
        super().__init__(plugin_info)
        
        # 设置支持的消息类型
        self._supported_message_types = [MessageType.TEXT]
        self._platform_type = "openai"
        
        # OpenAI特定配置
        self.api_base = "https://api.openai.com/v1"
        self.api_key = ""
        self.model = "gpt-3.5-turbo"
        self.temperature = 0.7
        self.max_tokens = 1000
        self.system_prompt = "你是一个有用的助手。"
        self.timeout = 30
    
    def get_config_schema(self) -> Dict[str, Any]:
        """获取配置模式定义"""
        return {
            "type": "object",
            "properties": {
                "api_base": {
                    "type": "string",
                    "title": "API基础URL",
                    "description": "OpenAI API的基础URL",
                    "default": "https://api.openai.com/v1"
                },
                "api_key": {
                    "type": "string",
                    "title": "API密钥",
                    "description": "OpenAI API密钥",
                    "format": "password"
                },
                "model": {
                    "type": "string",
                    "title": "模型名称",
                    "description": "使用的GPT模型",
                    "default": "gpt-3.5-turbo"
                },
                "temperature": {
                    "type": "number",
                    "title": "温度参数",
                    "description": "控制回复的随机性",
                    "default": 0.7,
                    "minimum": 0.0,
                    "maximum": 2.0
                },
                "max_tokens": {
                    "type": "integer",
                    "title": "最大令牌数",
                    "description": "回复的最大令牌数",
                    "default": 1000,
                    "minimum": 1,
                    "maximum": 4000
                },
                "system_prompt": {
                    "type": "string",
                    "title": "系统提示",
                    "description": "系统角色提示词",
                    "default": "你是一个有用的助手。"
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
            "required": ["api_key"]
        }
    
    def validate_config(self, config: Dict[str, Any]) -> tuple[bool, str]:
        """验证配置"""
        if not config.get('api_key'):
            return False, "API密钥不能为空"
        
        # 验证温度参数
        temperature = config.get('temperature', 0.7)
        if not (0.0 <= temperature <= 2.0):
            return False, "温度参数必须在0.0到2.0之间"
        
        # 验证最大令牌数
        max_tokens = config.get('max_tokens', 1000)
        if not (1 <= max_tokens <= 4000):
            return False, "最大令牌数必须在1到4000之间"
        
        return True, None
    
    async def _do_initialize(self):
        """执行自定义初始化逻辑"""
        # 从配置中提取参数
        self.api_base = self._config.get('api_base', 'https://api.openai.com/v1').rstrip('/')
        self.api_key = self._config.get('api_key', '')
        self.model = self._config.get('model', 'gpt-3.5-turbo')
        self.temperature = self._config.get('temperature', 0.7)
        self.max_tokens = self._config.get('max_tokens', 1000)
        self.system_prompt = self._config.get('system_prompt', '你是一个有用的助手。')
        self.timeout = self._config.get('timeout', 30)
        
        logger.info(f"OpenAI插件初始化完成: {self.model}")
    
    async def _do_process_message(self, context: MessageContext) -> ProcessResult:
        """处理消息"""
        try:
            # 构建消息列表
            messages = []
            
            # 添加系统提示
            if self.system_prompt:
                messages.append({
                    "role": "system",
                    "content": self.system_prompt
                })
            
            # 添加用户消息
            messages.append({
                "role": "user",
                "content": context.content
            })
            
            # 构建请求数据
            request_data = {
                "model": self.model,
                "messages": messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens
            }
            
            # 发送请求
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            logger.info(f"发送OpenAI API请求: {context.message_id}")
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.post(
                    f"{self.api_base}/chat/completions",
                    headers=headers,
                    json=request_data
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"OpenAI API错误: {response.status}, {error_text}")
                        return ProcessResult(
                            success=False,
                            error=f"API错误: {response.status}",
                            should_reply=False
                        )
                    
                    result = await response.json()
                    
                    # 提取回复内容
                    choices = result.get("choices", [])
                    if not choices:
                        logger.warning("OpenAI API返回空回复")
                        return ProcessResult(
                            success=True,
                            response="",
                            should_reply=False
                        )
                    
                    reply_content = choices[0].get("message", {}).get("content", "")
                    if not reply_content:
                        logger.warning("OpenAI API返回空内容")
                        return ProcessResult(
                            success=True,
                            response="",
                            should_reply=False
                        )
                    
                    logger.info(f"OpenAI API处理成功: {context.message_id}")
                    return ProcessResult(
                        success=True,
                        response=reply_content.strip(),
                        should_reply=True,
                        metadata={
                            "model": self.model,
                            "usage": result.get("usage", {}),
                            "finish_reason": choices[0].get("finish_reason")
                        }
                    )
        
        except asyncio.TimeoutError:
            logger.error(f"OpenAI API请求超时: {context.message_id}")
            return ProcessResult(
                success=False,
                error="请求超时",
                should_reply=False
            )
        except Exception as e:
            logger.error(f"OpenAI API处理失败: {context.message_id}, 错误: {e}")
            return ProcessResult(
                success=False,
                error=str(e),
                should_reply=False
            )
    
    async def _do_test_connection(self) -> Dict[str, Any]:
        """测试连接"""
        try:
            # 发送测试请求 - 获取模型列表
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get(
                    f"{self.api_base}/models",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        model_count = len(result.get("data", []))
                        return {
                            "success": True,
                            "message": f"连接测试成功，获取到 {model_count} 个模型",
                            "model_count": model_count
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
        health_data["config_valid"] = bool(self.api_key)
        health_data["model"] = self.model
        
        # 检查网络连接
        try:
            test_result = await self._do_test_connection()
            health_data["connection_ok"] = test_result.get("success", False)
            if not test_result.get("success"):
                health_data["connection_error"] = test_result.get("error")
            else:
                health_data["model_count"] = test_result.get("model_count", 0)
        except Exception as e:
            health_data["connection_ok"] = False
            health_data["connection_error"] = str(e)
        
        return health_data
