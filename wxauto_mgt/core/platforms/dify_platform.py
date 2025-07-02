"""
Dify平台实现

该模块实现了与Dify AI平台的集成，包括：
- 消息处理和对话管理
- 文件上传和处理
- 会话管理
- 连接测试
"""

import asyncio
import aiohttp
import json
import logging
import time
import os
import sys
from pathlib import Path
from typing import Dict, Any

from .base_platform import ServicePlatform

# 导入标准日志记录器
logger = logging.getLogger('wxauto_mgt')

# 导入文件日志记录器（如果存在）
try:
    from wxauto_mgt.core.message_delivery_service import file_logger
except ImportError:
    file_logger = logger

# 导入用户会话管理器
try:
    from wxauto_mgt.core.user_conversation_manager import user_conversation_manager
except ImportError:
    user_conversation_manager = None


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
        # 消息发送模式已在父类中初始化

    async def initialize(self) -> bool:
        """
        初始化平台

        Returns:
            bool: 是否初始化成功
        """
        try:
            # 验证基本配置（不进行网络请求）
            if not self.api_base or not self.api_key:
                logger.error("Dify平台配置不完整：缺少API基础URL或API密钥")
                self._initialized = False
                return False

            # 不在初始化阶段进行网络请求测试
            # 网络连接测试将在实际使用时或通过test_connection方法进行
            logger.info("Dify平台配置验证完成，跳过网络连接测试")
            self._initialized = True
            return True
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
            import aiofiles
            import mimetypes

            # 创建专用的Dify上传调试日志记录器
            dify_debug_logger = logging.getLogger('dify_upload_debug')
            if not dify_debug_logger.handlers:
                # 确定日志文件路径
                if getattr(sys, 'frozen', False):
                    # 打包环境 - 使用可执行文件所在目录
                    project_root = os.path.dirname(sys.executable)
                else:
                    # 开发环境 - 使用项目根目录
                    project_root = Path(__file__).parent.parent.parent

                log_dir = os.path.join(project_root, "data", "logs")
                os.makedirs(log_dir, exist_ok=True)

                log_file = os.path.join(log_dir, "dify_upload_debug.log")

                # 创建文件处理器
                file_handler = logging.FileHandler(log_file, encoding='utf-8')
                file_handler.setLevel(logging.DEBUG)
                formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
                file_handler.setFormatter(formatter)
                dify_debug_logger.addHandler(file_handler)
                dify_debug_logger.setLevel(logging.DEBUG)

                # 添加控制台处理器
                console_handler = logging.StreamHandler()
                console_handler.setLevel(logging.DEBUG)
                console_handler.setFormatter(formatter)
                dify_debug_logger.addHandler(console_handler)

                dify_debug_logger.info("Dify上传调试日志记录器已初始化")

            # 使用专用日志记录器记录详细信息
            file_logger.info(f"开始上传文件到Dify: {file_path}")
            dify_debug_logger.info(f"开始上传文件到Dify: {file_path}")

            # 记录当前环境信息
            dify_debug_logger.info(f"当前操作系统: {os.name}, 平台: {sys.platform}")
            dify_debug_logger.info(f"Python版本: {sys.version}")
            dify_debug_logger.info(f"是否为打包环境: {getattr(sys, 'frozen', False)}")

            # 如果只提供了文件名，构建完整路径
            if not os.path.dirname(file_path):
                # 确定项目根目录
                if getattr(sys, 'frozen', False):
                    # 打包环境 - 使用可执行文件所在目录
                    project_root = os.path.dirname(sys.executable)
                else:
                    # 开发环境 - 使用项目根目录
                    project_root = Path(__file__).parent.parent.parent

                download_dir = os.path.join(project_root, "data", "downloads")

                # 确保下载目录存在
                os.makedirs(download_dir, exist_ok=True)

                full_path = os.path.join(download_dir, file_path)
                file_logger.debug(f"只提供了文件名，构建完整路径: {full_path}")
                dify_debug_logger.info(f"只提供了文件名，构建完整路径: {full_path}")
                dify_debug_logger.info(f"项目根目录: {project_root}")
                dify_debug_logger.info(f"下载目录: {download_dir}")
            else:
                full_path = file_path

            # 记录文件路径详细信息
            file_logger.debug(f"文件路径详情: 原始={file_path}, 完整路径={full_path}")
            dify_debug_logger.info(f"文件路径详情: 原始={file_path}, 完整路径={full_path}")
            dify_debug_logger.info(f"文件是否存在: {os.path.exists(full_path)}")

            if os.path.exists(full_path):
                file_size = os.path.getsize(full_path)
                file_logger.debug(f"文件大小: {file_size} 字节")
                dify_debug_logger.info(f"文件大小: {file_size} 字节")
                dify_debug_logger.info(f"文件绝对路径: {os.path.abspath(full_path)}")

                # 检查文件权限
                try:
                    dify_debug_logger.info(f"检查文件权限...")
                    with open(full_path, 'rb') as f:
                        # 只读取一小部分来测试权限
                        _ = f.read(10)  # 使用下划线表示我们不关心这个值
                        dify_debug_logger.info(f"文件可读，读取测试成功")
                except Exception as e:
                    dify_debug_logger.error(f"文件权限检查失败: {e}")
            else:
                file_logger.error(f"文件不存在: {full_path}")
                dify_debug_logger.error(f"文件不存在: {full_path}")
                return {"error": f"文件不存在: {full_path}"}

            # 获取文件信息
            file_name = os.path.basename(full_path)
            file_size = os.path.getsize(full_path)
            content_type, _ = mimetypes.guess_type(full_path)
            if not content_type:
                # 默认为二进制流
                content_type = "application/octet-stream"

            file_logger.debug(f"文件信息: 名称={file_name}, 大小={file_size}字节, 类型={content_type}")
            dify_debug_logger.info(f"文件信息: 名称={file_name}, 大小={file_size}字节, 类型={content_type}")

            # 获取Dify文件类型
            dify_file_type = self._get_dify_file_type(file_name)
            file_logger.debug(f"文件 {file_name} 的Dify类型: {dify_file_type}")
            dify_debug_logger.info(f"文件 {file_name} 的Dify类型: {dify_file_type}")

            # 读取文件内容
            try:
                dify_debug_logger.info(f"开始读取文件内容...")
                async with aiofiles.open(full_path, 'rb') as f:
                    file_content = await f.read()
                    file_logger.debug(f"已读取文件内容，大小: {len(file_content)}字节")
                    dify_debug_logger.info(f"已读取文件内容，大小: {len(file_content)}字节")

                # 验证文件内容是否有效
                if len(file_content) == 0:
                    file_logger.error(f"文件内容为空: {full_path}")
                    dify_debug_logger.error(f"文件内容为空: {full_path}")
                    return {"error": f"文件内容为空: {full_path}"}

                file_logger.debug(f"文件内容有效，前20字节: {file_content[:20]}")
                dify_debug_logger.info(f"文件内容有效，前20字节: {file_content[:20]}")
            except Exception as e:
                file_logger.error(f"读取文件内容时出错: {e}")
                file_logger.exception(e)
                dify_debug_logger.error(f"读取文件内容时出错: {e}")
                dify_debug_logger.exception(e)
                return {"error": f"读取文件内容时出错: {str(e)}"}

            # 构建表单数据
            try:
                dify_debug_logger.info(f"开始构建表单数据...")
                form_data = aiohttp.FormData()
                form_data.add_field('file',
                                    file_content,
                                    filename=file_name,
                                    content_type=content_type)
                file_logger.debug(f"已创建表单数据，文件名: {file_name}, 内容类型: {content_type}")
                dify_debug_logger.info(f"已创建表单数据，文件名: {file_name}, 内容类型: {content_type}")
            except Exception as e:
                file_logger.error(f"创建表单数据时出错: {e}")
                file_logger.exception(e)
                dify_debug_logger.error(f"创建表单数据时出错: {e}")
                dify_debug_logger.exception(e)
                return {"error": f"创建表单数据时出错: {str(e)}"}

            # 构建请求URL和头信息
            upload_url = f"{self.api_base}/files/upload"
            headers = {"Authorization": f"Bearer {self.api_key}"}

            # 记录API信息
            file_logger.debug(f"Dify API基础URL: {self.api_base}")
            dify_debug_logger.info(f"Dify API基础URL: {self.api_base}")
            dify_debug_logger.info(f"上传URL: {upload_url}")

            # 记录API密钥的前5个字符，其余用*替代
            masked_key = self.api_key[:5] + "*" * (len(self.api_key) - 5) if self.api_key else "未设置"
            file_logger.debug(f"API密钥(部分隐藏): {masked_key}")
            dify_debug_logger.info(f"API密钥(部分隐藏): {masked_key}")

            file_logger.debug(f"准备发送上传请求: URL={upload_url}, 文件名={file_name}")
            dify_debug_logger.info(f"准备发送上传请求: URL={upload_url}, 文件名={file_name}")

            # 发送请求
            async with aiohttp.ClientSession() as session:
                try:
                    # 记录完整的请求信息
                    file_logger.debug(f"上传文件请求URL: {upload_url}")
                    dify_debug_logger.info(f"上传文件请求URL: {upload_url}")

                    # 记录请求头（隐藏API密钥）
                    safe_headers = headers.copy()
                    if 'Authorization' in safe_headers:
                        safe_headers['Authorization'] = 'Bearer ******'
                    dify_debug_logger.info(f"上传文件请求头: {safe_headers}")

                    # 记录表单数据摘要
                    dify_debug_logger.info(f"上传文件表单数据: 包含文件 {file_name}, 大小 {file_size} 字节")

                    # 记录请求开始时间
                    start_time = time.time()
                    file_logger.info(f"开始发送文件上传请求: {time.strftime('%H:%M:%S')}")
                    dify_debug_logger.info(f"开始发送文件上传请求: {time.strftime('%H:%M:%S')}")

                    dify_debug_logger.info(f"发送POST请求到 {upload_url}...")
                    async with session.post(
                        upload_url,
                        headers=headers,
                        data=form_data
                    ) as response:
                        # 记录响应时间
                        response_time = time.time() - start_time
                        response_status = response.status
                        file_logger.debug(f"上传文件响应状态码: {response_status}, 耗时: {response_time:.2f}秒")
                        dify_debug_logger.info(f"上传文件响应状态码: {response_status}, 耗时: {response_time:.2f}秒")

                        # 尝试获取响应内容
                        try:
                            response_text = await response.text()
                            file_logger.debug(f"上传文件响应内容: {response_text[:1000]}")
                            dify_debug_logger.info(f"上传文件响应内容: {response_text[:1000]}")
                        except Exception as e:
                            file_logger.warning(f"无法读取响应内容: {e}")
                            dify_debug_logger.error(f"无法读取响应内容: {e}")
                            response_text = "无法读取"

                        # Dify文件上传API返回201状态码表示成功
                        if response_status not in [200, 201]:
                            file_logger.error(f"上传文件到Dify失败: {response_status}, {response_text}")
                            logger.error(f"上传文件到Dify失败: {response_status}, 响应: {response_text[:200]}")
                            dify_debug_logger.error(f"上传文件到Dify失败: 状态码={response_status}, 响应={response_text}")
                            return {"error": f"上传文件失败: 状态码={response_status}, 响应={response_text[:200]}"}
                except Exception as e:
                    file_logger.error(f"发送文件上传请求时出错: {e}")
                    file_logger.exception(e)
                    logger.error(f"发送文件上传请求时出错: {e}")
                    dify_debug_logger.error(f"发送文件上传请求时出错: {e}")
                    dify_debug_logger.exception(e)
                    return {"error": f"发送文件上传请求时出错: {str(e)}"}

                # 处理成功响应
                try:
                    dify_debug_logger.info(f"解析上传响应...")
                    result = await response.json()
                    file_id = result.get('id')
                    if not file_id:
                        file_logger.error(f"上传文件成功但未返回文件ID: {result}")
                        logger.error(f"上传文件成功但未返回文件ID")
                        dify_debug_logger.error(f"上传文件成功但未返回文件ID: {result}")
                        return {"error": "上传文件成功但未返回文件ID"}

                    file_logger.info(f"成功上传文件到Dify: {file_name}, 文件ID: {file_id}")
                    file_logger.debug(f"上传文件完整响应: {result}")
                    logger.info(f"成功上传文件到Dify: {file_name}, 文件ID: {file_id}")
                    dify_debug_logger.info(f"成功上传文件到Dify: {file_name}, 文件ID: {file_id}")
                    dify_debug_logger.info(f"上传文件完整响应: {result}")

                    # 添加文件类型信息到结果中
                    result['dify_file_type'] = dify_file_type

                    # 记录更多详细信息
                    file_logger.debug(f"文件上传成功详情: ID={file_id}, 类型={dify_file_type}, 名称={file_name}")
                    dify_debug_logger.info(f"文件上传成功详情: ID={file_id}, 类型={dify_file_type}, 名称={file_name}")
                    return result
                except Exception as e:
                    file_logger.error(f"解析上传响应时出错: {e}")
                    file_logger.exception(e)
                    logger.error(f"解析上传响应时出错: {e}")
                    dify_debug_logger.error(f"解析上传响应时出错: {e}")
                    dify_debug_logger.exception(e)
                    return {"error": f"解析上传响应时出错: {str(e)}"}

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
        # 导入必要的模块，确保在所有代码路径中都可用
        import json
        import traceback

        file_logger.info(f"开始处理消息: ID={message.get('id', 'unknown')}, 类型={message.get('mtype', 'unknown')}")
        file_logger.debug(f"完整消息数据: {message}")

        # 确保dify_debug_logger已初始化
        dify_debug_logger = logging.getLogger('dify_upload_debug')
        if not dify_debug_logger.handlers:
            # 确定日志文件路径
            if getattr(sys, 'frozen', False):
                # 打包环境 - 使用可执行文件所在目录
                project_root = os.path.dirname(sys.executable)
            else:
                # 开发环境 - 使用项目根目录
                project_root = Path(__file__).parent.parent.parent

            log_dir = os.path.join(project_root, "data", "logs")
            os.makedirs(log_dir, exist_ok=True)

            log_file = os.path.join(log_dir, "dify_upload_debug.log")

            # 创建文件处理器
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
            file_handler.setFormatter(formatter)
            dify_debug_logger.addHandler(file_handler)
            dify_debug_logger.setLevel(logging.DEBUG)

        if not self._initialized:
            await self.initialize()
            if not self._initialized:
                file_logger.error("平台未初始化")
                return {"error": "平台未初始化"}

        try:
            # 检查是否是文件类型消息
            is_file_message = 'dify_file' in message or ('local_file_path' in message and message.get('file_type') in ['image', 'file'])

            # 构建请求数据
            # 获取发送者和聊天名称，优先使用sender_remark字段
            sender = message.get('sender_remark') or message.get('sender', '')
            chat_name = message.get('chat_name', '')

            # 根据消息对象名称与发送者名称是否相同来判断群聊
            # 当消息对象名称与发送者名称不同时，则判定为群聊
            if sender and chat_name and sender != chat_name:
                # 对于群聊消息，使用"群聊名称==发送者"格式的用户ID
                combined_user_id = f"{chat_name}=={sender}"
                file_logger.info(f"群聊消息，使用组合用户ID: {combined_user_id}")
                user_id = combined_user_id
            else:
                # 对于私聊消息，使用原始发送者ID
                user_id = sender or self.user_id
                file_logger.info(f"私聊消息，使用原始用户ID: {user_id}")

            request_data = {
                "inputs": {},
                # 如果是文件类型消息，使用空格作为query，否则使用原始内容
                "query": " " if is_file_message else message['content'],
                "response_mode": "blocking",
                "user": user_id
            }

            # 处理文件消息
            if is_file_message:
                file_logger.info(f"检测到文件类型消息，开始处理文件")
                dify_debug_logger.info(f"检测到文件类型消息，开始处理文件")

                # 检查是否已有Dify文件信息
                if 'dify_file' in message:
                    # 直接使用已有的Dify文件信息
                    dify_file_info = message['dify_file']
                    file_logger.info(f"使用已有的Dify文件信息: {dify_file_info}")
                    dify_debug_logger.info(f"使用已有的Dify文件信息: {dify_file_info}")

                    # 构建文件信息
                    file_info = {
                        "type": dify_file_info.get('dify_file_type', 'document'),
                        "transfer_method": "local_file",
                        "upload_file_id": dify_file_info.get('id')
                    }

                    request_data["files"] = [file_info]
                    file_logger.info(f"已添加Dify文件到请求: {file_info}")
                    dify_debug_logger.info(f"已添加Dify文件到请求: {file_info}")

                elif 'local_file_path' in message:
                    # 需要上传文件到Dify
                    local_file_path = message['local_file_path']
                    file_logger.info(f"需要上传本地文件到Dify: {local_file_path}")
                    dify_debug_logger.info(f"需要上传本地文件到Dify: {local_file_path}")

                    # 上传文件到Dify
                    upload_result = await self.upload_file_to_dify(local_file_path)
                    if 'error' in upload_result:
                        file_logger.error(f"上传文件到Dify失败: {upload_result['error']}")
                        dify_debug_logger.error(f"上传文件到Dify失败: {upload_result['error']}")
                        return {"error": f"上传文件失败: {upload_result['error']}"}

                    # 构建文件信息
                    file_info = {
                        "type": upload_result.get('dify_file_type', 'document'),
                        "transfer_method": "local_file",
                        "upload_file_id": upload_result.get('id')
                    }

                    request_data["files"] = [file_info]
                    file_logger.info(f"文件上传成功，已添加到请求: {file_info}")
                    dify_debug_logger.info(f"文件上传成功，已添加到请求: {file_info}")

            # 处理会话ID
            # 优先使用消息中的会话ID，然后是用户会话管理器中的会话ID，最后是平台配置的会话ID
            message_conversation_id = message.get('conversation_id', '')
            user_conversation_id = ""

            # 从用户会话管理器获取会话ID
            if user_conversation_manager:
                instance_id = message.get('instance_id', '')
                platform_id = self.platform_id
                if instance_id and chat_name and user_id and platform_id:
                    user_conversation_id = await user_conversation_manager.get_conversation_id(
                        instance_id, chat_name, user_id, platform_id
                    )
                    if user_conversation_id:
                        file_logger.info(f"从用户会话管理器获取到会话ID: {user_conversation_id}")

            # 选择会话ID的优先级：消息中的 > 用户会话管理器中的 > 平台配置的
            conversation_id_to_use = message_conversation_id or user_conversation_id or self.conversation_id

            if conversation_id_to_use:
                request_data["conversation_id"] = conversation_id_to_use
                file_logger.info(f"使用会话ID: {conversation_id_to_use}")
                dify_debug_logger.info(f"使用会话ID: {conversation_id_to_use}")
            else:
                dify_debug_logger.info("未使用会话ID，将创建新会话")

            if 'files' in request_data:
                file_ids = [f.get('upload_file_id') for f in request_data.get('files', [])]
                logger.info(f"请求包含文件: {file_ids}")
                dify_debug_logger.info(f"请求包含文件: {file_ids}")

                # 记录文件详细信息
                for i, file_info in enumerate(request_data.get('files', [])):
                    dify_debug_logger.info(f"文件 {i+1} 详情: {file_info}")
            else:
                dify_debug_logger.info("请求不包含文件")

            # 记录请求数据摘要
            dify_debug_logger.info(f"请求数据摘要: user={request_data.get('user')}, query长度={len(request_data.get('query', ''))}")
            dify_debug_logger.info(f"完整请求数据: {json.dumps(request_data, ensure_ascii=False)}")

            # 检查请求数据中的文件信息
            if 'files' in request_data and request_data['files']:
                for idx, file_info in enumerate(request_data['files']):
                    dify_debug_logger.info(f"请求中的文件 {idx+1}: {file_info}")
                    # 检查文件信息是否完整
                    if 'upload_file_id' not in file_info or not file_info['upload_file_id']:
                        dify_debug_logger.error(f"文件信息不完整，缺少upload_file_id: {file_info}")
                    if 'type' not in file_info or not file_info['type']:
                        dify_debug_logger.error(f"文件信息不完整，缺少type: {file_info}")
                    if 'transfer_method' not in file_info:
                        dify_debug_logger.warning(f"文件信息中缺少transfer_method字段: {file_info}")
            elif is_file_message:
                dify_debug_logger.warning("请求数据中没有文件信息，但消息类型为文件消息")

            chat_url = f"{self.api_base}/chat-messages"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            # 记录请求头（隐藏API密钥）
            safe_headers = headers.copy()
            if 'Authorization' in safe_headers:
                safe_headers['Authorization'] = 'Bearer ******'
            logger.debug(f"Dify API请求头: {safe_headers}")
            dify_debug_logger.info(f"Dify API请求头: {safe_headers}")

            # 记录请求开始时间
            start_time = time.time()
            logger.info(f"开始发送Dify API请求: {time.strftime('%H:%M:%S')}")
            dify_debug_logger.info(f"开始发送Dify API请求: {time.strftime('%H:%M:%S')}")

            dify_debug_logger.info(f"发送POST请求到 {chat_url}...")
            print(f"[DEBUG] 发送POST请求到 {chat_url}...")
            print(f"[DEBUG] 请求头: {safe_headers}")
            print(f"[DEBUG] 请求数据: {json.dumps(request_data, ensure_ascii=False)}")

            # 发送请求并处理响应
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    chat_url,
                    headers=headers,
                    json=request_data
                ) as response:
                    # 记录响应时间和状态
                    response_time = time.time() - start_time
                    response_status = response.status
                    logger.info(f"收到Dify API响应: 状态码={response_status}, 耗时={response_time:.2f}秒")
                    dify_debug_logger.info(f"收到Dify API响应: 状态码={response_status}, 耗时={response_time:.2f}秒")
                    print(f"[DEBUG] 收到Dify API响应: 状态码={response_status}, 耗时={response_time:.2f}秒")

                    # 尝试获取响应内容
                    try:
                        response_text = await response.text()
                        dify_debug_logger.info(f"响应内容: {response_text[:1000]}")
                        print(f"[DEBUG] 响应内容: {response_text[:1000]}")
                    except Exception as e:
                        dify_debug_logger.error(f"无法读取响应内容: {e}")
                        print(f"[ERROR] 无法读取响应内容: {e}")
                        response_text = "无法读取响应内容"

                    # 处理404错误（会话不存在）
                    if response_status == 404 and ('conversation_id' in request_data):
                        # 会话不存在，清除会话ID并重试
                        invalid_conversation_id = request_data.get('conversation_id', '')
                        file_logger.warning(f"会话ID {invalid_conversation_id} 不存在，将创建新会话")
                        logger.warning(f"会话ID {invalid_conversation_id} 不存在，将创建新会话")

                        # 如果是平台配置的会话ID，清除它
                        if self.conversation_id == invalid_conversation_id:
                            self.conversation_id = ""
                            self.config["conversation_id"] = ""
                            file_logger.info("已清除平台配置的会话ID")

                        # 从用户会话管理器中删除无效的会话ID
                        instance_id = message.get('instance_id', '')
                        platform_id = self.platform_id
                        if instance_id and chat_name and user_id and platform_id and user_conversation_manager:
                            await user_conversation_manager.delete_conversation_id(
                                instance_id, chat_name, user_id, platform_id
                            )
                            file_logger.info(f"已从用户会话管理器中删除无效会话ID: {instance_id} - {chat_name} - {user_id}")

                        # 如果是消息中的会话ID，需要从数据库中清除
                        if message.get('conversation_id') == invalid_conversation_id:
                            # 记录需要清除的会话ID信息，但不在这里执行清除操作
                            # 清除操作将在message_delivery_service.py中处理
                            file_logger.info(f"需要清除监听对象的无效会话ID: {message.get('instance_id')} - {message.get('chat_name')}")

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
                                dify_debug_logger.error(f"重试后Dify API仍然错误: 状态码={retry_status}, 响应={error_text}")

                                # 尝试解析错误响应
                                try:
                                    error_json = json.loads(error_text)
                                    dify_debug_logger.error(f"错误响应JSON: {error_json}")

                                    # 检查是否有文件相关的错误
                                    if 'message' in error_json:
                                        error_message = error_json.get('message', '')
                                        dify_debug_logger.error(f"错误消息: {error_message}")

                                        if 'file' in error_message.lower() or 'upload' in error_message.lower():
                                            dify_debug_logger.error(f"检测到可能与文件相关的错误: {error_message}")
                                except Exception as e:
                                    dify_debug_logger.error(f"解析错误响应时出错: {e}")

                                return {"error": f"API错误: {retry_status}"}

                            result = await retry_response.json()
                            file_logger.debug(f"重试请求响应数据: {result}")
                            dify_debug_logger.info(f"重试请求响应数据: {result}")
                    elif response_status != 200:
                        error_text = await response.text()
                        file_logger.error(f"Dify API错误: {response_status}, {error_text}")
                        logger.error(f"Dify API错误: {response_status}")
                        dify_debug_logger.error(f"Dify API错误: 状态码={response_status}, 响应={error_text}")

                        # 尝试解析错误响应
                        try:
                            error_json = json.loads(error_text)
                            dify_debug_logger.error(f"错误响应JSON: {error_json}")

                            # 检查是否有文件相关的错误
                            if 'message' in error_json:
                                error_message = error_json.get('message', '')
                                dify_debug_logger.error(f"错误消息: {error_message}")

                                if 'file' in error_message.lower() or 'upload' in error_message.lower():
                                    dify_debug_logger.error(f"检测到可能与文件相关的错误: {error_message}")
                        except Exception as e:
                            dify_debug_logger.error(f"解析错误响应时出错: {e}")

                        return {"error": f"API错误: {response_status}"}
                    else:
                        try:
                            result = await response.json()
                            dify_debug_logger.info(f"成功获取响应数据")
                            print(f"[DEBUG] 成功获取响应数据: {json.dumps(result, ensure_ascii=False)}")

                            # 记录响应摘要
                            answer = result.get("answer", "")
                            logger.info(f"收到Dify响应: 长度={len(answer)}")
                            logger.debug(f"Dify响应摘要: {answer[:100]}{'...' if len(answer) > 100 else ''}")
                            dify_debug_logger.info(f"收到Dify响应: 长度={len(answer)}")
                            dify_debug_logger.info(f"Dify响应摘要: {answer[:100]}{'...' if len(answer) > 100 else ''}")

                            # 记录完整响应（仅在DEBUG级别）
                            logger.debug(f"Dify完整响应: {json.dumps(result, ensure_ascii=False, indent=2)}")
                            dify_debug_logger.info(f"Dify完整响应: {json.dumps(result, ensure_ascii=False)}")

                            # 检查是否包含文件信息的请求
                            if "files" in request_data:
                                logger.info(f"包含文件的请求成功发送，响应状态码: {response_status}, 响应长度: {len(answer)}")
                                dify_debug_logger.info(f"包含文件的请求成功发送，响应状态码: {response_status}, 响应长度: {len(answer)}")

                                # 检查响应中是否有文件相关的信息
                                if 'message' in result:
                                    message_text = result.get('message', '')
                                    if message_text:
                                        dify_debug_logger.info(f"响应中的消息: {message_text}")
                                        if 'file' in message_text.lower() or 'upload' in message_text.lower():
                                            dify_debug_logger.warning(f"响应中包含可能与文件相关的消息: {message_text}")

                            # 获取会话ID
                            new_conversation_id = result.get("conversation_id", "")
                            dify_debug_logger.info(f"获取到会话ID: {new_conversation_id if new_conversation_id else '无'}")

                            # 如果获取到新的会话ID
                            if new_conversation_id:
                                # 获取实例ID和平台ID
                                instance_id = message.get('instance_id', '')
                                platform_id = self.platform_id

                                # 保存会话ID到用户会话管理器
                                if instance_id and chat_name and user_id and platform_id and user_conversation_manager:
                                    await user_conversation_manager.save_conversation_id(
                                        instance_id, chat_name, user_id, platform_id, new_conversation_id
                                    )
                                    file_logger.info(f"已更新用户会话ID: {instance_id} - {chat_name} - {user_id} - {new_conversation_id}")

                                # 如果消息中没有会话ID或平台没有会话ID，保存新的会话ID到平台配置
                                message_conversation_id = message.get('conversation_id', '')
                                if not message_conversation_id and not self.conversation_id:
                                    self.conversation_id = new_conversation_id
                                    # 更新配置
                                    self.config["conversation_id"] = self.conversation_id
                                    logger.info(f"已创建新的Dify会话，ID: {self.conversation_id}")

                                # 返回会话ID，以便更新监听对象
                                dify_debug_logger.info(f"返回结果包含会话ID: {new_conversation_id}")
                                return {
                                    "content": result.get("answer", ""),
                                    "raw_response": result,
                                    "conversation_id": new_conversation_id
                                }
                            else:
                                # 没有获取到新的会话ID，返回普通响应
                                dify_debug_logger.warning(f"返回结果不包含会话ID")
                                return {
                                    "content": result.get("answer", ""),
                                    "raw_response": result
                                }
                        except Exception as json_error:
                            dify_debug_logger.error(f"解析响应JSON时出错: {json_error}")
                            print(f"[ERROR] 解析响应JSON时出错: {json_error}")
                            # 尝试获取原始响应文本
                            try:
                                raw_text = await response.text()
                                dify_debug_logger.error(f"原始响应文本: {raw_text[:1000]}")
                                print(f"[ERROR] 原始响应文本: {raw_text[:1000]}")
                            except Exception as text_error:
                                dify_debug_logger.error(f"获取原始响应文本时出错: {text_error}")
                                print(f"[ERROR] 获取原始响应文本时出错: {text_error}")
                            return {"error": f"解析响应JSON时出错: {str(json_error)}"}
        except Exception as e:
            logger.error(f"处理消息时出错: {e}")
            logger.exception(e)

            # 确保dify_debug_logger已初始化
            try:
                dify_debug_logger.error(f"处理消息时出错: {e}")
                dify_debug_logger.exception(e)

                # 记录更详细的错误信息
                import traceback
                error_traceback = traceback.format_exc()
                dify_debug_logger.error(f"详细错误堆栈: {error_traceback}")

                # 检查是否与文件相关的错误
                error_str = str(e).lower()
                if 'file' in error_str or 'upload' in error_str or 'permission' in error_str:
                    dify_debug_logger.error(f"检测到可能与文件相关的错误: {e}")

                # 记录请求数据
                if 'request_data' in locals():
                    dify_debug_logger.error(f"错误发生时的请求数据: {json.dumps(request_data, ensure_ascii=False)}")

                # 记录消息数据
                if 'message' in locals():
                    dify_debug_logger.error(f"错误发生时的消息数据: {message}")
            except Exception as inner_e:
                logger.error(f"记录错误详情时出错: {inner_e}")

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
            logger.info(f"测试Dify API连接: URL={self.api_base}/app-info")

            # 记录请求头（隐藏API密钥）
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            safe_headers = headers.copy()
            if 'Authorization' in safe_headers:
                safe_headers['Authorization'] = 'Bearer ******'
            logger.debug(f"Dify API测试请求头: {safe_headers}")

            # 记录请求开始时间
            start_time = time.time()

            # 尝试获取应用信息而不是发送消息
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.api_base}/app-info",
                    headers=headers
                ) as response:
                    # 记录响应时间和状态
                    response_time = time.time() - start_time
                    logger.info(f"收到Dify API测试响应: 状态码={response.status}, 耗时={response_time:.2f}秒")

                    if response.status != 200:
                        logger.warning(f"Dify app-info端点不可用，尝试使用parameters端点")

                        # 记录备用请求开始时间
                        fallback_start_time = time.time()

                        # 如果app-info端点不可用，尝试使用其他端点
                        async with session.get(
                            f"{self.api_base}/parameters",
                            headers=headers
                        ) as fallback_response:
                            # 记录备用响应时间和状态
                            fallback_response_time = time.time() - fallback_start_time
                            logger.info(f"收到Dify parameters端点响应: 状态码={fallback_response.status}, 耗时={fallback_response_time:.2f}秒")

                            if fallback_response.status != 200:
                                error_text = await fallback_response.text()
                                logger.error(f"Dify API测试错误: 状态码={fallback_response.status}, 错误信息={error_text}")
                                return {"error": f"API错误: {fallback_response.status}, {error_text[:200]}"}

                            result = await fallback_response.json()
                            logger.info("Dify API测试成功(使用parameters端点)")
                            logger.debug(f"Dify parameters响应: {json.dumps(result, ensure_ascii=False, indent=2)}")
                    else:
                        result = await response.json()
                        logger.info("Dify API测试成功(使用app-info端点)")
                        logger.debug(f"Dify app-info响应: {json.dumps(result, ensure_ascii=False, indent=2)}")

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
