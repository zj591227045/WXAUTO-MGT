"""
OpenAI平台实现

该模块实现了与OpenAI兼容API的集成，包括：
- 消息处理和对话管理
- 模型配置和参数设置
- 连接测试
"""

import aiohttp
import json
import logging
import time
from typing import Dict, Any

from .base_platform import ServicePlatform

# 导入标准日志记录器
logger = logging.getLogger('wxauto_mgt')


class OpenAIPlatform(ServicePlatform):
    """OpenAI API平台实现"""

    def __init__(self, platform_id: str, name: str, config: Dict[str, Any]):
        """
        初始化OpenAI平台

        Args:
            platform_id: 平台ID
            name: 平台名称
            config: 平台配置，必须包含api_base和api_key
        """
        super().__init__(platform_id, name, config)
        self.api_base = config.get('api_base', 'https://api.openai.com/v1').rstrip('/')
        self.api_key = config.get('api_key', '')
        self.model = config.get('model', 'gpt-3.5-turbo')
        self.temperature = config.get('temperature', 0.7)
        self.system_prompt = config.get('system_prompt', '你是一个有用的助手。')
        self.max_tokens = config.get('max_tokens', 1000)
        # 消息发送模式已在父类中初始化

    async def initialize(self) -> bool:
        """
        初始化平台

        Returns:
            bool: 是否初始化成功
        """
        try:
            # 验证基本配置（不进行网络请求）
            if not self.api_key:
                logger.error("OpenAI平台配置不完整：缺少API密钥")
                self._initialized = False
                return False

            # 不在初始化阶段进行网络请求测试
            # 网络连接测试将在实际使用时或通过test_connection方法进行
            logger.info("OpenAI平台配置验证完成，跳过网络连接测试")
            self._initialized = True
            return True
        except Exception as e:
            logger.error(f"初始化OpenAI平台失败: {e}")
            self._initialized = False
            return False

    async def process_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理消息

        Args:
            message: 消息数据

        Returns:
            Dict[str, Any]: 处理结果，包含回复内容
        """
        if not self._initialized:
            await self.initialize()
            if not self._initialized:
                return {"error": "平台未初始化"}

        try:
            # 构建消息历史
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": message['content']}
            ]

            # 记录API调用详情
            logger.info(f"准备调用OpenAI API: URL={self.api_base}/chat/completions, 模型={self.model}")
            logger.debug(f"OpenAI请求消息: {json.dumps(messages, ensure_ascii=False, indent=2)}")

            # 构建请求体
            request_body = {
                "model": self.model,
                "messages": messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens
            }

            # 记录请求体
            logger.debug(f"OpenAI API完整请求体: {json.dumps(request_body, ensure_ascii=False, indent=2)}")

            # 记录请求头（隐藏API密钥）
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            safe_headers = headers.copy()
            if 'Authorization' in safe_headers:
                safe_headers['Authorization'] = 'Bearer ******'
            logger.debug(f"OpenAI API请求头: {safe_headers}")

            # 记录请求开始时间
            start_time = time.time()
            logger.info(f"开始发送OpenAI API请求: {time.strftime('%H:%M:%S')}")

            # 发送请求
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_base}/chat/completions",
                    headers=headers,
                    json=request_body
                ) as response:
                    # 记录响应时间和状态
                    response_time = time.time() - start_time
                    logger.info(f"收到OpenAI API响应: 状态码={response.status}, 耗时={response_time:.2f}秒")

                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"OpenAI API错误: 状态码={response.status}, 错误信息={error_text}")
                        return {"error": f"API错误: {response.status}, {error_text[:200]}"}

                    result = await response.json()

                    # 记录响应摘要
                    content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                    logger.info(f"收到OpenAI响应: 长度={len(content)}")
                    logger.debug(f"OpenAI响应摘要: {content[:100]}{'...' if len(content) > 100 else ''}")

                    # 记录完整响应（仅在DEBUG级别）
                    logger.debug(f"OpenAI完整响应: {json.dumps(result, ensure_ascii=False, indent=2)}")

                    logger.info(f"OpenAI API调用完成: 响应长度={len(content)}")
                    return {
                        "content": content,
                        "raw_response": result
                    }
        except Exception as e:
            logger.error(f"处理消息时出错: {e}")
            return {"error": str(e)}

    async def test_connection(self) -> Dict[str, Any]:
        """
        测试连接

        Returns:
            Dict[str, Any]: 测试结果
        """
        try:
            if not self.api_key:
                return {"error": "API密钥未设置"}

            # 使用模型列表API测试连接，避免创建聊天完成
            logger.info(f"测试OpenAI API连接: URL={self.api_base}/models")

            # 记录请求头（隐藏API密钥）
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            safe_headers = headers.copy()
            if 'Authorization' in safe_headers:
                safe_headers['Authorization'] = 'Bearer ******'
            logger.debug(f"OpenAI API测试请求头: {safe_headers}")

            # 记录请求开始时间
            start_time = time.time()

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.api_base}/models",
                    headers=headers
                ) as response:
                    # 记录响应时间和状态
                    response_time = time.time() - start_time
                    logger.info(f"收到OpenAI API测试响应: 状态码={response.status}, 耗时={response_time:.2f}秒")

                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"OpenAI API测试错误: 状态码={response.status}, 错误信息={error_text}")
                        return {"error": f"API错误: {response.status}, {error_text[:200]}"}

                    result = await response.json()

                    # 记录响应摘要
                    model_count = len(result.get("data", []))
                    logger.info(f"OpenAI API测试成功: 获取到 {model_count} 个模型")

                    # 记录可用模型列表（仅在DEBUG级别）
                    if model_count > 0:
                        model_ids = [model.get("id") for model in result.get("data", [])]
                        logger.debug(f"可用模型列表: {model_ids}")

                    return {
                        "success": True,
                        "message": "连接成功",
                        "data": result
                    }
        except Exception as e:
            logger.error(f"测试连接时出错: {e}")
            return {"error": str(e)}

    def get_type(self) -> str:
        """
        获取平台类型

        Returns:
            str: 平台类型
        """
        return "openai"
