"""
消息处理工具模块

该模块负责处理不同类型的消息，包括：
- 普通文本消息
- 卡片消息
- 语音消息
- 图片消息
- 文件消息
"""

import logging
import os
import re
import asyncio
from typing import Dict, Optional, Tuple, List, Any
from pathlib import Path

# 导入标准日志记录器
logger = logging.getLogger(__name__)

# 导入文件处理专用日志记录器
from wxauto_mgt.utils import file_logger

class MessageProcessor:
    """消息处理工具类"""

    def __init__(self, download_dir: str = None):
        """
        初始化消息处理工具

        Args:
            download_dir: 文件下载保存目录，默认为项目根目录下的data/downloads文件夹
        """
        # 设置下载目录
        if download_dir:
            self.download_dir = download_dir
        else:
            # 默认使用项目根目录下的data/downloads文件夹
            project_root = Path(__file__).parent.parent.parent
            self.download_dir = os.path.join(project_root, "data", "downloads")

        # 确保下载目录存在
        os.makedirs(self.download_dir, exist_ok=True)
        logger.info(f"文件下载目录: {self.download_dir}")

    async def process_message(self, message: Dict, api_client) -> Dict:
        """
        处理消息，根据消息类型进行不同处理

        Args:
            message: 消息数据
            api_client: API客户端实例，用于下载文件等操作

        Returns:
            Dict: 处理后的消息数据
        """
        # 复制原始消息，避免修改原始数据
        processed_msg = message.copy()

        # 获取消息类型
        mtype = message.get('mtype', '')
        content = message.get('content', '')
        message_id = message.get('id', 'unknown')

        logger.info(f"开始处理消息 ID: {message_id}, 类型: {mtype or '普通文本'}")

        # 根据不同类型处理
        if not mtype:
            # 普通文本消息，不需要特殊处理
            logger.debug(f"普通文本消息 ID: {message_id}, 内容: {content[:50]}...")
            return processed_msg

        elif mtype == 'card':
            # 卡片消息，移除[wxauto卡片链接解析]前缀
            logger.info(f"处理卡片消息 ID: {message_id}, 原始内容: {content[:100]}...")
            processed_content = self._process_card_message(content)
            processed_msg['content'] = processed_content
            logger.info(f"处理后的卡片消息 ID: {message_id}, 内容: {processed_content[:100]}...")
            return processed_msg

        elif mtype == 'voice':
            # 语音消息，移除[wxauto语音解析]前缀
            logger.info(f"处理语音消息 ID: {message_id}, 原始内容: {content[:100]}...")
            processed_content = self._process_voice_message(content)
            processed_msg['content'] = processed_content
            logger.info(f"处理后的语音消息 ID: {message_id}, 内容: {processed_content[:100]}...")
            return processed_msg

        elif mtype in ['image', 'file']:
            # 图片或文件消息，提取文件路径并下载
            file_logger.info(f"处理{mtype}消息 ID: {message_id}, 原始内容: {content[:100]}...")
            logger.info(f"处理{mtype}消息 ID: {message_id}")
            file_path = self._extract_file_path(content)

            if file_path:
                file_logger.info(f"从{mtype}消息 ID: {message_id} 中提取到文件路径: {file_path}")
                logger.info(f"从{mtype}消息 ID: {message_id} 中提取到文件路径")

                # 下载文件
                file_logger.debug(f"准备下载文件: {file_path}")
                file_info = await self._download_file(file_path, api_client)
                if file_info:
                    # 更新消息内容，添加本地文件路径信息
                    local_path, file_size = file_info
                    processed_msg['local_file_path'] = local_path
                    processed_msg['file_size'] = file_size
                    processed_msg['original_file_path'] = file_path
                    processed_msg['file_type'] = mtype  # 添加文件类型标记
                    file_logger.info(f"已下载{mtype}文件 ID: {message_id}, 路径: {file_path} -> {local_path}, 大小: {file_size} 字节")
                    logger.info(f"已下载{mtype}文件 ID: {message_id}, 大小: {file_size} 字节")

                    # 添加更详细的调试信息
                    file_logger.debug(f"文件处理完成，消息详情: {processed_msg}")

                    # 检查文件扩展名
                    _, ext = os.path.splitext(local_path)
                    if ext:
                        file_logger.info(f"文件扩展名: {ext.upper()}")
                else:
                    file_logger.warning(f"下载{mtype}文件失败 ID: {message_id}, 路径: {file_path}")
                    logger.warning(f"下载{mtype}文件失败 ID: {message_id}")
            else:
                file_logger.warning(f"无法从{mtype}消息 ID: {message_id} 中提取文件路径: {content[:100]}")
                logger.warning(f"无法从{mtype}消息 ID: {message_id} 中提取文件路径")

            return processed_msg

        else:
            # 未知类型，不做处理
            logger.warning(f"未知消息类型: {mtype}, ID: {message_id}, 内容: {content[:100]}...")
            return processed_msg

    def _process_card_message(self, content: str) -> str:
        """
        处理卡片消息，移除[wxauto卡片链接解析]前缀

        Args:
            content: 原始消息内容

        Returns:
            str: 处理后的消息内容
        """
        return content.replace('[wxauto卡片链接解析]', '').strip()

    def _process_voice_message(self, content: str) -> str:
        """
        处理语音消息，移除[wxauto语音解析]前缀

        Args:
            content: 原始消息内容

        Returns:
            str: 处理后的消息内容
        """
        return content.replace('[wxauto语音解析]', '').strip()

    def _extract_file_path(self, content: str) -> Optional[str]:
        """
        从消息内容中提取文件路径

        Args:
            content: 消息内容

        Returns:
            Optional[str]: 提取到的文件路径，如果没有则返回None
        """
        # 尝试直接提取路径格式 C:\\path\\to\\file.ext
        path_pattern = r'([A-Za-z]:\\(?:[^\\/:*?"<>|\r\n]+\\)*[^\\/:*?"<>|\r\n]*)'
        match = re.search(path_pattern, content)
        if match:
            return match.group(1)
        return None

    async def _download_file(self, file_path: str, api_client) -> Optional[Tuple[str, int]]:
        """
        下载文件并保存到本地

        Args:
            file_path: 远程文件路径
            api_client: API客户端实例

        Returns:
            Optional[Tuple[str, int]]: (本地文件路径, 文件大小)，如果下载失败则返回None
        """
        try:
            file_logger.info(f"开始下载文件: {file_path}")
            logger.info(f"开始下载文件: {file_path}")

            # 调用API下载文件
            file_content = await api_client.download_file(file_path)
            if not file_content:
                file_logger.error(f"下载文件失败: {file_path}")
                logger.error(f"下载文件失败: {file_path}")
                return None

            # 提取文件名 - 只取最后的文件名部分，不包含路径
            file_name = os.path.basename(file_path.replace('\\', '/'))
            file_logger.debug(f"提取的文件名: {file_name}")

            # 生成本地保存路径
            local_path = os.path.join(self.download_dir, file_name)
            file_logger.debug(f"初始本地保存路径: {local_path}")

            # 如果文件已存在，添加序号
            counter = 1
            base_name, ext = os.path.splitext(file_name)
            while os.path.exists(local_path):
                new_name = f"{base_name}_{counter}{ext}"
                local_path = os.path.join(self.download_dir, new_name)
                file_logger.debug(f"文件已存在，使用新路径: {local_path}")
                counter += 1

            # 保存文件
            with open(local_path, 'wb') as f:
                f.write(file_content)

            # 返回本地路径和文件大小
            file_size = len(file_content)
            file_logger.info(f"文件已保存: {local_path}, 大小: {file_size} 字节")
            logger.info(f"文件已保存: {local_path}, 大小: {file_size} 字节")

            # 只返回文件名，不包含路径信息
            saved_file_name = os.path.basename(local_path)
            file_logger.debug(f"返回文件名: {saved_file_name}")

            # 检查文件是否真的存在
            full_path = os.path.join(self.download_dir, saved_file_name)
            if os.path.exists(full_path):
                file_size_on_disk = os.path.getsize(full_path)
                file_logger.debug(f"验证文件已保存到磁盘: {full_path}, 磁盘上的大小: {file_size_on_disk} 字节")

                # 检查文件内容
                if file_size_on_disk > 0:
                    file_logger.debug(f"文件内容有效，大小: {file_size_on_disk} 字节")
                else:
                    file_logger.warning(f"文件内容为空: {full_path}")
            else:
                file_logger.error(f"文件保存失败，磁盘上找不到文件: {full_path}")
                logger.error(f"文件保存失败，磁盘上找不到文件: {full_path}")
                return None

            return saved_file_name, file_size

        except Exception as e:
            file_logger.error(f"下载并保存文件时出错: {e}")
            file_logger.exception(e)
            logger.error(f"下载并保存文件时出错: {e}")
            return None

# 创建全局实例
message_processor = MessageProcessor()
