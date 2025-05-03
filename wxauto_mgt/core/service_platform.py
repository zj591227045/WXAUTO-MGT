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

# 导入标准日志记录器
logger = logging.getLogger(__name__)

# 导入文件处理专用日志记录器
from wxauto_mgt.utils import file_logger

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

    def _get_dify_file_type(self, file_path: str) -> str:
        """
        根据文件扩展名判断Dify文件类型

        Args:
            file_path: 文件路径

        Returns:
            str: 文件类型，'document'或'image'
        """
        import os

        # 获取文件扩展名并转为大写
        _, ext = os.path.splitext(file_path)
        ext = ext[1:].upper() if ext else ""

        # 文档类型
        document_extensions = ['TXT', 'MD', 'MARKDOWN', 'PDF', 'HTML', 'XLSX',
                              'XLS', 'DOCX', 'CSV', 'EML', 'MSG', 'PPTX',
                              'PPT', 'XML', 'EPUB']

        # 图片类型
        image_extensions = ['JPG', 'JPEG', 'PNG', 'GIF', 'WEBP', 'SVG']

        if ext in document_extensions:
            return "document"
        elif ext in image_extensions:
            return "image"
        else:
            # 默认作为文档处理
            logger.warning(f"未知文件类型: {ext}，默认作为document处理")
            return "document"

    async def upload_file_to_dify(self, file_path: str) -> Dict[str, Any]:
        """
        上传文件到Dify平台

        Args:
            file_path: 本地文件路径或文件名

        Returns:
            Dict[str, Any]: 上传结果，包含文件ID和文件类型
        """
        try:
            import os
            import aiofiles
            import mimetypes
            from pathlib import Path

            # 使用专用日志记录器记录详细信息
            file_logger.info(f"开始上传文件到Dify: {file_path}")

            # 如果只提供了文件名，构建完整路径
            if not os.path.dirname(file_path):
                # 默认使用项目根目录下的data/downloads文件夹
                project_root = Path(__file__).parent.parent.parent
                download_dir = os.path.join(project_root, "data", "downloads")
                full_path = os.path.join(download_dir, file_path)
                file_logger.debug(f"只提供了文件名，构建完整路径: {full_path}")
            else:
                full_path = file_path

            # 检查文件是否存在
            if not os.path.exists(full_path):
                file_logger.error(f"文件不存在: {full_path}")
                return {"error": f"文件不存在: {full_path}"}

            # 获取文件信息
            file_name = os.path.basename(full_path)
            file_size = os.path.getsize(full_path)
            content_type, _ = mimetypes.guess_type(full_path)
            if not content_type:
                # 默认为二进制流
                content_type = "application/octet-stream"

            file_logger.debug(f"文件信息: 名称={file_name}, 大小={file_size}字节, 类型={content_type}")

            # 获取Dify文件类型
            dify_file_type = self._get_dify_file_type(file_name)
            file_logger.debug(f"文件 {file_name} 的Dify类型: {dify_file_type}")

            # 读取文件内容
            async with aiofiles.open(full_path, 'rb') as f:
                file_content = await f.read()
                file_logger.debug(f"已读取文件内容，大小: {len(file_content)}字节")

            # 构建表单数据
            form_data = aiohttp.FormData()
            form_data.add_field('file',
                                file_content,
                                filename=file_name,
                                content_type=content_type)

            # 构建请求URL和头信息
            upload_url = f"{self.api_base}/files/upload"
            headers = {"Authorization": f"Bearer {self.api_key}"}

            file_logger.debug(f"准备发送上传请求: URL={upload_url}, 文件名={file_name}")

            # 发送请求
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    upload_url,
                    headers=headers,
                    data=form_data
                ) as response:
                    response_status = response.status
                    file_logger.debug(f"上传文件响应状态码: {response_status}")

                    # Dify文件上传API返回201状态码表示成功
                    if response_status not in [200, 201]:
                        error_text = await response.text()
                        file_logger.error(f"上传文件到Dify失败: {response_status}, {error_text}")
                        logger.error(f"上传文件到Dify失败: {response_status}")
                        return {"error": f"上传文件失败: {response_status}"}

                    result = await response.json()
                    file_logger.info(f"成功上传文件到Dify: {file_name}, 文件ID: {result.get('id')}")
                    file_logger.debug(f"上传文件完整响应: {result}")
                    logger.info(f"成功上传文件到Dify: {file_name}, 文件ID: {result.get('id')}")

                    # 添加文件类型信息到结果中
                    result['dify_file_type'] = dify_file_type
                    return result

        except Exception as e:
            file_logger.error(f"上传文件到Dify时出错: {e}")
            file_logger.exception(e)
            logger.error(f"上传文件到Dify时出错: {e}")
            return {"error": str(e)}

    async def process_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理消息

        Args:
            message: 消息数据

        Returns:
            Dict[str, Any]: 处理结果，包含回复内容
        """
        file_logger.info(f"开始处理消息: ID={message.get('id', 'unknown')}, 类型={message.get('mtype', 'unknown')}")
        file_logger.debug(f"完整消息数据: {message}")

        if not self._initialized:
            await self.initialize()
            if not self._initialized:
                file_logger.error("平台未初始化")
                return {"error": "平台未初始化"}

        try:
            # 检查是否是文件类型消息
            is_file_message = 'dify_file' in message or ('local_file_path' in message and message.get('file_type') in ['image', 'file'])

            # 构建请求数据
            request_data = {
                "inputs": {},
                # 如果是文件类型消息，使用空格作为query，否则使用原始内容
                "query": " " if is_file_message else message['content'],
                "response_mode": "blocking",
                "user": message.get('sender', '') or self.user_id
            }

            file_logger.debug(f"初始请求数据: {request_data}")

            # 检查消息中是否包含会话ID（从监听对象获取）
            message_conversation_id = message.get('conversation_id', '')

            # 优先使用消息中的会话ID，其次使用平台配置的会话ID
            if message_conversation_id:
                request_data["conversation_id"] = message_conversation_id
                file_logger.debug(f"使用消息中的会话ID: {message_conversation_id}")
            elif self.conversation_id:
                request_data["conversation_id"] = self.conversation_id
                file_logger.debug(f"使用平台配置的会话ID: {self.conversation_id}")

            # 处理文件类型消息
            # 检查是否已经在deliver_message中处理过文件上传
            if 'dify_file' in message:
                try:
                    # 文件已经在deliver_message中上传过，直接使用上传结果
                    file_info = message['dify_file']
                    file_id = file_info.get('id')
                    dify_file_type = file_info.get('type', 'document')

                    file_logger.info(f"使用已上传的文件: {file_id}, 类型: {dify_file_type}")

                    # 如果files字段不存在，创建它
                    if "files" not in request_data:
                        request_data["files"] = []

                    # 添加文件信息
                    file_data = {
                        "type": dify_file_type,
                        "transfer_method": "local_file",
                        "upload_file_id": file_id
                    }
                    request_data["files"].append(file_data)

                    file_logger.info(f"添加文件到请求: {file_id}, 类型: {dify_file_type}")
                    logger.info(f"添加文件到请求: {file_id}")
                    file_logger.debug(f"当前请求数据: {request_data}")
                except Exception as e:
                    file_logger.error(f"处理已上传文件信息时出错: {e}")
                    file_logger.exception(e)
            # 兼容旧代码，如果没有在deliver_message中处理过文件上传，则在这里处理
            elif 'local_file_path' in message and message.get('file_type') in ['image', 'file']:
                file_logger.info(f"检测到文件类型消息: local_file_path={message.get('local_file_path')}, file_type={message.get('file_type')}")
                logger.info(f"检测到文件类型消息: {message.get('file_type')}")

                # 记录完整的消息信息，用于调试
                file_logger.debug(f"文件类型消息完整信息: {message}")

                # 上传文件到Dify
                file_path = message['local_file_path']
                file_logger.info(f"准备上传文件到Dify: {file_path}")
                upload_result = await self.upload_file_to_dify(file_path)

                if 'error' in upload_result:
                    file_logger.error(f"上传文件失败: {upload_result['error']}")
                    logger.error(f"上传文件失败: {upload_result['error']}")
                else:
                    # 获取文件ID
                    file_id = upload_result.get('id')
                    file_logger.info(f"文件上传成功，获取到文件ID: {file_id}")

                    if file_id:
                        # 从上传结果中获取Dify文件类型
                        dify_file_type = upload_result.get('dify_file_type', 'document')
                        file_logger.debug(f"文件类型: {dify_file_type}")

                        # 如果files字段不存在，创建它
                        if "files" not in request_data:
                            request_data["files"] = []

                        # 添加文件信息
                        file_info = {
                            "type": dify_file_type,  # 使用根据文件扩展名判断的类型
                            "transfer_method": "local_file",
                            "upload_file_id": file_id
                        }
                        request_data["files"].append(file_info)

                        file_logger.info(f"添加文件到请求: {file_id}, 类型: {dify_file_type}")
                        file_logger.debug(f"完整的文件信息: {file_info}")
                        file_logger.debug(f"当前请求数据: {request_data}")
                        logger.info(f"添加文件到请求: {file_id}, 类型: {dify_file_type}")

            # 发送请求
            file_logger.debug(f"准备发送消息到Dify API，请求数据: {request_data}")
            logger.debug(f"准备发送消息到Dify API")

            chat_url = f"{self.api_base}/chat-messages"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            file_logger.debug(f"发送请求: URL={chat_url}, 头信息={headers}")

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    chat_url,
                    headers=headers,
                    json=request_data
                ) as response:
                    response_status = response.status
                    file_logger.debug(f"Dify API响应状态码: {response_status}")

                    if response_status == 404 and self.conversation_id:
                        # 会话不存在，清除会话ID并重试
                        file_logger.warning(f"会话ID {self.conversation_id} 不存在，将创建新会话")
                        logger.warning(f"会话ID {self.conversation_id} 不存在，将创建新会话")
                        self.conversation_id = ""
                        self.config["conversation_id"] = ""

                        # 移除会话ID并重新构建请求
                        request_data.pop("conversation_id", None)
                        file_logger.debug(f"重试请求，移除会话ID后的请求数据: {request_data}")

                        # 重新发送请求
                        async with session.post(
                            chat_url,
                            headers=headers,
                            json=request_data
                        ) as retry_response:
                            retry_status = retry_response.status
                            file_logger.debug(f"重试请求响应状态码: {retry_status}")

                            if retry_status != 200:
                                error_text = await retry_response.text()
                                file_logger.error(f"重试后Dify API仍然错误: {retry_status}, {error_text}")
                                logger.error(f"重试后Dify API仍然错误: {retry_status}")
                                return {"error": f"API错误: {retry_status}"}

                            result = await retry_response.json()
                            file_logger.debug(f"重试请求响应数据: {result}")
                    elif response_status != 200:
                        error_text = await response.text()
                        file_logger.error(f"Dify API错误: {response_status}, {error_text}")
                        logger.error(f"Dify API错误: {response_status}")
                        return {"error": f"API错误: {response_status}"}
                    else:
                        result = await response.json()
                        file_logger.debug(f"Dify API响应数据: {result}")

                        # 检查是否包含文件信息的请求
                        if "files" in request_data:
                            file_logger.info(f"包含文件的请求成功发送，响应状态码: {response_status}")
                            logger.info(f"包含文件的请求成功发送")

                    # 获取会话ID
                    new_conversation_id = result.get("conversation_id", "")

                    # 如果获取到新的会话ID
                    if new_conversation_id:
                        # 如果消息中没有会话ID或平台没有会话ID，保存新的会话ID
                        message_conversation_id = message.get('conversation_id', '')
                        if not message_conversation_id and not self.conversation_id:
                            self.conversation_id = new_conversation_id
                            # 更新配置
                            self.config["conversation_id"] = self.conversation_id
                            logger.info(f"已创建新的Dify会话，ID: {self.conversation_id}")

                        # 返回会话ID，以便更新监听对象
                        return {
                            "content": result.get("answer", ""),
                            "raw_response": result,
                            "conversation_id": new_conversation_id
                        }
                    else:
                        # 没有获取到新的会话ID，返回普通响应
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
