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

logger = logging.getLogger(__name__)

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
            logger.info(f"处理{mtype}消息 ID: {message_id}, 原始内容: {content[:100]}...")
            file_path = self._extract_file_path(content)

            if file_path:
                logger.info(f"从{mtype}消息 ID: {message_id} 中提取到文件路径: {file_path}")
                # 下载文件
                file_info = await self._download_file(file_path, api_client)
                if file_info:
                    # 更新消息内容，添加本地文件路径信息
                    local_path, file_size = file_info
                    processed_msg['local_file_path'] = local_path
                    processed_msg['file_size'] = file_size
                    processed_msg['original_file_path'] = file_path
                    logger.info(f"已下载{mtype}文件 ID: {message_id}, 路径: {file_path} -> {local_path}, 大小: {file_size} 字节")
                else:
                    logger.warning(f"下载{mtype}文件失败 ID: {message_id}, 路径: {file_path}")
            else:
                logger.warning(f"无法从{mtype}消息 ID: {message_id} 中提取文件路径: {content[:100]}")

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
            logger.info(f"开始下载文件: {file_path}")

            # 调用API下载文件
            file_content = await api_client.download_file(file_path)
            if not file_content:
                logger.error(f"下载文件失败: {file_path}")
                return None

            # 提取文件名
            file_name = os.path.basename(file_path)
            logger.debug(f"提取的文件名: {file_name}")

            # 生成本地保存路径
            local_path = os.path.join(self.download_dir, file_name)
            logger.debug(f"初始本地保存路径: {local_path}")

            # 如果文件已存在，添加序号
            counter = 1
            base_name, ext = os.path.splitext(file_name)
            while os.path.exists(local_path):
                new_name = f"{base_name}_{counter}{ext}"
                local_path = os.path.join(self.download_dir, new_name)
                logger.debug(f"文件已存在，使用新路径: {local_path}")
                counter += 1

            # 保存文件
            with open(local_path, 'wb') as f:
                f.write(file_content)

            # 返回本地路径和文件大小
            file_size = len(file_content)
            logger.info(f"文件已保存: {local_path}, 大小: {file_size} 字节")

            # 返回相对路径，而不是绝对路径，便于数据库存储和跨平台兼容
            rel_path = os.path.relpath(local_path, Path(__file__).parent.parent.parent)
            logger.debug(f"返回相对路径: {rel_path}")

            return rel_path, file_size

        except Exception as e:
            logger.error(f"下载并保存文件时出错: {e}")
            logger.exception(e)
            return None

# 创建全局实例
message_processor = MessageProcessor()
