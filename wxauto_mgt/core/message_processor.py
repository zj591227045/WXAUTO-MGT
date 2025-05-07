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

    def __init__(self, download_dir: str = None, use_temp_dir: bool = False):
        """
        初始化消息处理工具

        Args:
            download_dir: 文件下载保存目录，默认为项目根目录下的data/downloads文件夹
            use_temp_dir: 是否直接使用临时目录作为主要下载目录
        """
        import sys
        import platform
        import tempfile

        # 初始化标志，表示是否使用备用目录
        self.using_backup_dir = False

        # 设置临时目录作为备用
        self.temp_download_dir = os.path.join(tempfile.gettempdir(), "wxauto_downloads")
        os.makedirs(self.temp_download_dir, exist_ok=True)
        logger.debug(f"临时备用下载目录: {self.temp_download_dir}")

        # 如果指定使用临时目录，直接设置
        if use_temp_dir:
            self.download_dir = self.temp_download_dir
            self.using_backup_dir = True
            logger.info(f"根据配置使用临时目录作为主要下载目录: {self.download_dir}")
        # 否则使用指定目录或默认目录
        elif download_dir:
            self.download_dir = download_dir
        else:
            # 确定项目根目录
            if getattr(sys, 'frozen', False):
                # 打包环境 - 使用可执行文件所在目录
                project_root = os.path.dirname(sys.executable)
            else:
                # 开发环境 - 使用项目根目录
                project_root = Path(__file__).parent.parent.parent

            self.download_dir = os.path.join(project_root, "data", "downloads")
            logger.debug(f"项目根目录: {project_root}")
            logger.debug(f"当前操作系统: {platform.system()}")
            logger.debug(f"是否为打包环境: {getattr(sys, 'frozen', False)}")

        # 确保下载目录存在
        os.makedirs(self.download_dir, exist_ok=True)
        logger.info(f"文件下载目录: {self.download_dir}")

        # 检查下载目录权限
        if not self.using_backup_dir:  # 如果不是使用临时目录，才需要检查权限
            try:
                test_file_path = os.path.join(self.download_dir, ".test_write_permission")
                with open(test_file_path, 'w') as f:
                    f.write("test")
                os.remove(test_file_path)
                logger.debug(f"下载目录写入权限正常")

                # 在Windows打包环境下，尝试设置完全权限
                if platform.system() == "Windows" and getattr(sys, 'frozen', False):
                    try:
                        import subprocess
                        subprocess.run(['icacls', self.download_dir, '/grant', 'Everyone:(OI)(CI)F'],
                                      shell=True, check=False)
                        logger.debug(f"已尝试设置下载目录完全权限")
                    except Exception as e:
                        logger.warning(f"设置下载目录权限失败: {e}")
            except Exception as e:
                logger.error(f"下载目录写入权限检查失败: {e}")

                # 自动切换到临时目录
                logger.warning(f"由于权限问题，将使用临时目录作为下载目录: {self.temp_download_dir}")
                self.download_dir = self.temp_download_dir
                self.using_backup_dir = True

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
            import platform
            import sys

            file_logger.info(f"开始下载文件: {file_path}")
            logger.info(f"开始下载文件: {file_path}")

            # 记录当前环境信息，便于调试
            file_logger.debug(f"当前操作系统: {platform.system()}")
            file_logger.debug(f"Python版本: {sys.version}")
            file_logger.debug(f"是否为打包环境: {getattr(sys, 'frozen', False)}")
            file_logger.debug(f"下载目录: {self.download_dir}")

            # 确保下载目录存在
            os.makedirs(self.download_dir, exist_ok=True)

            # 检查下载目录权限
            try:
                test_file_path = os.path.join(self.download_dir, ".test_write_permission")
                with open(test_file_path, 'w') as f:
                    f.write("test")
                os.remove(test_file_path)
                file_logger.debug(f"下载目录写入权限正常")
            except Exception as e:
                file_logger.error(f"下载目录写入权限检查失败: {e}")
                logger.error(f"下载目录写入权限检查失败: {e}")

            # 调用API下载文件
            file_content = await api_client.download_file(file_path)
            if not file_content:
                file_logger.error(f"下载文件失败: {file_path}")
                logger.error(f"下载文件失败: {file_path}")
                return None

            # 提取文件名 - 只取最后的文件名部分，不包含路径
            # 兼容不同操作系统的路径分隔符
            normalized_path = file_path.replace('\\', '/')
            file_name = os.path.basename(normalized_path)
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
            save_success = False
            try:
                with open(local_path, 'wb') as f:
                    f.write(file_content)
                file_logger.debug(f"文件写入成功: {local_path}")
                save_success = True
            except Exception as e:
                file_logger.error(f"文件写入失败: {e}")
                logger.error(f"文件写入失败: {e}")

                # 尝试使用备用方法写入
                try:
                    import tempfile
                    temp_dir = tempfile.gettempdir()
                    temp_path = os.path.join(temp_dir, file_name)
                    file_logger.debug(f"尝试写入临时文件: {temp_path}")

                    with open(temp_path, 'wb') as f:
                        f.write(file_content)

                    # 如果临时文件写入成功，尝试复制到目标位置
                    import shutil
                    shutil.copy2(temp_path, local_path)
                    os.remove(temp_path)
                    file_logger.debug(f"通过临时文件成功写入: {local_path}")
                    save_success = True
                except Exception as e2:
                    file_logger.error(f"备用写入方法也失败: {e2}")
                    logger.error(f"备用写入方法也失败: {e2}")

                    # 如果备用方法也失败，尝试直接使用临时目录
                    if hasattr(self, 'temp_download_dir') and not self.using_backup_dir:
                        try:
                            # 切换到临时目录
                            temp_local_path = os.path.join(self.temp_download_dir, file_name)
                            file_logger.warning(f"尝试直接保存到临时目录: {temp_local_path}")

                            # 如果文件已存在，添加序号
                            counter = 1
                            base_name, ext = os.path.splitext(file_name)
                            while os.path.exists(temp_local_path):
                                new_name = f"{base_name}_{counter}{ext}"
                                temp_local_path = os.path.join(self.temp_download_dir, new_name)
                                file_logger.debug(f"临时目录中文件已存在，使用新路径: {temp_local_path}")
                                counter += 1

                            # 直接写入临时目录
                            with open(temp_local_path, 'wb') as f:
                                f.write(file_content)

                            file_logger.info(f"成功保存到临时目录: {temp_local_path}")
                            logger.info(f"成功保存到临时目录: {temp_local_path}")

                            # 更新本地路径
                            local_path = temp_local_path
                            save_success = True

                            # 标记使用了临时目录
                            self.using_backup_dir = True
                        except Exception as e3:
                            file_logger.error(f"保存到临时目录也失败: {e3}")
                            logger.error(f"保存到临时目录也失败: {e3}")
                            return None
                    else:
                        return None

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
                    # 尝试直接写入文件内容
                    with open(full_path, 'wb') as f:
                        f.write(file_content)
                    file_logger.debug(f"尝试重新写入文件内容")

                    # 再次检查
                    if os.path.exists(full_path) and os.path.getsize(full_path) > 0:
                        file_logger.debug(f"重新写入成功，文件大小: {os.path.getsize(full_path)} 字节")
                    else:
                        file_logger.error(f"重新写入后文件仍然为空或不存在")
                        return None
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
# 默认不使用临时目录，可以通过配置文件或环境变量来控制
import os
from ..core.config_manager import config_manager

# 优先使用环境变量
use_temp_dir = os.environ.get('WXAUTO_USE_TEMP_DIR', '').lower() in ('true', '1', 'yes')

# 如果环境变量未设置，则使用配置文件中的设置
if 'WXAUTO_USE_TEMP_DIR' not in os.environ:
    try:
        use_temp_dir = config_manager.get('app.use_temp_dir_for_downloads', False)
        logger.debug(f"从配置文件中读取临时目录设置: {use_temp_dir}")
    except Exception as e:
        logger.warning(f"读取配置文件中的临时目录设置失败: {e}，使用默认值: False")
        use_temp_dir = False

logger.info(f"是否使用临时目录作为下载目录: {use_temp_dir}")
message_processor = MessageProcessor(use_temp_dir=use_temp_dir)
