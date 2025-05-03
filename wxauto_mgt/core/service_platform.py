"""
服务平台接口模块

该模块定义了服务平台的标准接口和基本实现，包括：
- ServicePlatform: 服务平台基类
- DifyPlatform: Dify平台实现
- OpenAIPlatform: OpenAI API平台实现
"""

import logging
import json
import time
import uuid
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List

import aiohttp

logger = logging.getLogger(__name__)

class ServicePlatform(ABC):
    """服务平台基类"""

    def __init__(self, platform_id: str, name: str, config: Dict[str, Any]):
        """
        初始化服务平台

        Args:
            platform_id: 平台ID
            name: 平台名称
            config: 平台配置
        """
        self.platform_id = platform_id
        self.name = name
        self.config = config
        self._initialized = False

    @abstractmethod
    async def initialize(self) -> bool:
        """
        初始化平台

        Returns:
            bool: 是否初始化成功
        """
        pass

    @abstractmethod
    async def process_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理消息

        Args:
            message: 消息数据

        Returns:
            Dict[str, Any]: 处理结果，包含回复内容
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

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典

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

    def get_safe_config(self) -> Dict[str, Any]:
        """
        获取安全的配置（隐藏敏感信息）

        Returns:
            Dict[str, Any]: 安全的配置
        """
        safe_config = self.config.copy()
        # 隐藏API密钥等敏感信息
        for key in ['api_key', 'token', 'secret']:
            if key in safe_config:
                safe_config[key] = '******'
        return safe_config

    @abstractmethod
    def get_type(self) -> str:
        """
        获取平台类型

        Returns:
            str: 平台类型
        """
        pass


class DifyPlatform(ServicePlatform):
    """Dify平台实现"""

    def __init__(self, platform_id: str, name: str, config: Dict[str, Any]):
        """
        初始化Dify平台

        Args:
            platform_id: 平台ID
            name: 平台名称
            config: 平台配置，必须包含api_base和api_key
        """
        super().__init__(platform_id, name, config)
        self.api_base = config.get('api_base', '').rstrip('/')
        self.api_key = config.get('api_key', '')
        self.conversation_id = config.get('conversation_id', '')
        self.user_id = config.get('user_id', 'default_user')

    async def initialize(self) -> bool:
        """
        初始化平台

        Returns:
            bool: 是否初始化成功
        """
        try:
            # 验证API密钥
            result = await self.test_connection()
            self._initialized = not result.get('error')
            return self._initialized
        except Exception as e:
            logger.error(f"初始化Dify平台失败: {e}")
            self._initialized = False
            return False

    async def upload_file_to_dify(self, file_path: str) -> Dict[str, Any]:
        """
        上传文件到Dify平台

        Args:
            file_path: 本地文件路径或文件名

        Returns:
            Dict[str, Any]: 上传结果，包含文件ID
        """
        try:
            import os
            import aiofiles
            import mimetypes
            from pathlib import Path

            # 如果只提供了文件名，构建完整路径
            if not os.path.dirname(file_path):
                # 默认使用项目根目录下的data/downloads文件夹
                project_root = Path(__file__).parent.parent.parent
                download_dir = os.path.join(project_root, "data", "downloads")
                full_path = os.path.join(download_dir, file_path)
                logger.debug(f"只提供了文件名，构建完整路径: {full_path}")
            else:
                full_path = file_path

            # 检查文件是否存在
            if not os.path.exists(full_path):
                logger.error(f"文件不存在: {full_path}")
                return {"error": f"文件不存在: {full_path}"}

            # 获取文件类型
            file_name = os.path.basename(full_path)
            content_type, _ = mimetypes.guess_type(full_path)
            if not content_type:
                # 默认为二进制流
                content_type = "application/octet-stream"

            # 读取文件内容
            async with aiofiles.open(full_path, 'rb') as f:
                file_content = await f.read()

            # 构建表单数据
            form_data = aiohttp.FormData()
            form_data.add_field('file',
                                file_content,
                                filename=file_name,
                                content_type=content_type)

            # 发送请求
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_base}/files/upload",
                    headers={
                        "Authorization": f"Bearer {self.api_key}"
                    },
                    data=form_data
                ) as response:
                    # Dify文件上传API返回201状态码表示成功
                    if response.status not in [200, 201]:
                        error_text = await response.text()
                        logger.error(f"上传文件到Dify失败: {response.status}, {error_text}")
                        return {"error": f"上传文件失败: {response.status}"}

                    result = await response.json()
                    logger.info(f"成功上传文件到Dify: {file_name}, 文件ID: {result.get('id')}")
                    return result

        except Exception as e:
            logger.error(f"上传文件到Dify时出错: {e}")
            logger.exception(e)
            return {"error": str(e)}

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
            # 构建请求数据
            request_data = {
                "inputs": {},
                "query": message['content'],
                "response_mode": "blocking",
                "user": message.get('sender', '') or self.user_id
            }

            # 如果有会话ID，添加到请求中
            if self.conversation_id:
                request_data["conversation_id"] = self.conversation_id

            # 处理文件类型消息
            if 'local_file_path' in message and message.get('file_type') in ['image', 'file']:
                # 上传文件到Dify
                file_path = message['local_file_path']
                upload_result = await self.upload_file_to_dify(file_path)

                if 'error' in upload_result:
                    logger.error(f"上传文件失败: {upload_result['error']}")
                else:
                    # 获取文件ID
                    file_id = upload_result.get('id')
                    if file_id:
                        # 添加文件到请求
                        file_type = "image" if message.get('file_type') == 'image' else "file"

                        # 如果files字段不存在，创建它
                        if "files" not in request_data:
                            request_data["files"] = []

                        # 添加文件信息
                        request_data["files"].append({
                            "type": file_type,
                            "transfer_method": "local_file",
                            "upload_file_id": file_id
                        })

                        logger.info(f"添加文件到请求: {file_id}, 类型: {file_type}")

            # 发送请求
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_base}/chat-messages",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json=request_data
                ) as response:
                    if response.status == 404 and self.conversation_id:
                        # 会话不存在，清除会话ID并重试
                        logger.warning(f"会话ID {self.conversation_id} 不存在，将创建新会话")
                        self.conversation_id = ""
                        self.config["conversation_id"] = ""

                        # 移除会话ID并重新构建请求
                        request_data.pop("conversation_id", None)

                        # 重新发送请求
                        async with session.post(
                            f"{self.api_base}/chat-messages",
                            headers={
                                "Authorization": f"Bearer {self.api_key}",
                                "Content-Type": "application/json"
                            },
                            json=request_data
                        ) as retry_response:
                            if retry_response.status != 200:
                                error_text = await retry_response.text()
                                logger.error(f"重试后Dify API仍然错误: {retry_response.status}, {error_text}")
                                return {"error": f"API错误: {retry_response.status}"}

                            result = await retry_response.json()
                    elif response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Dify API错误: {response.status}, {error_text}")
                        return {"error": f"API错误: {response.status}"}
                    else:
                        result = await response.json()

                    # 保存会话ID，用于后续请求
                    if not self.conversation_id and "conversation_id" in result:
                        self.conversation_id = result["conversation_id"]
                        # 更新配置
                        self.config["conversation_id"] = self.conversation_id
                        logger.info(f"已创建新的Dify会话，ID: {self.conversation_id}")

                    return {
                        "content": result.get("answer", ""),
                        "raw_response": result
                    }
        except Exception as e:
            logger.error(f"处理消息时出错: {e}")
            logger.exception(e)
            return {"error": str(e)}

    async def test_connection(self) -> Dict[str, Any]:
        """
        测试连接

        Returns:
            Dict[str, Any]: 测试结果
        """
        try:
            if not self.api_base or not self.api_key:
                return {"error": "API基础URL或API密钥未设置"}

            # 使用更简单的API端点测试连接，避免创建新的聊天消息
            # 尝试获取应用信息而不是发送消息
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.api_base}/app-info",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    }
                ) as response:
                    if response.status != 200:
                        # 如果app-info端点不可用，尝试使用其他端点
                        # 但不发送实际的聊天消息
                        async with session.get(
                            f"{self.api_base}/parameters",
                            headers={
                                "Authorization": f"Bearer {self.api_key}",
                                "Content-Type": "application/json"
                            }
                        ) as fallback_response:
                            if fallback_response.status != 200:
                                error_text = await fallback_response.text()
                                return {"error": f"API错误: {fallback_response.status}, {error_text}"}

                            result = await fallback_response.json()
                    else:
                        result = await response.json()

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
        return "dify"


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

    async def initialize(self) -> bool:
        """
        初始化平台

        Returns:
            bool: 是否初始化成功
        """
        try:
            # 验证API密钥
            result = await self.test_connection()
            self._initialized = not result.get('error')
            return self._initialized
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

            # 发送请求
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_base}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": self.temperature,
                        "max_tokens": self.max_tokens
                    }
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"OpenAI API错误: {response.status}, {error_text}")
                        return {"error": f"API错误: {response.status}"}

                    result = await response.json()
                    content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
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
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.api_base}/models",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    }
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        return {"error": f"API错误: {response.status}, {error_text}"}

                    result = await response.json()
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
    else:
        logger.error(f"不支持的平台类型: {platform_type}")
        return None
