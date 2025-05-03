"""
消息投递服务模块

该模块负责从消息监听服务获取未处理的消息，并将其投递到指定的服务平台，
然后将服务平台的回复发送回微信联系人。
"""

import logging
import asyncio
import time
import json
from typing import Dict, List, Optional, Any, Set

from wxauto_mgt.data.db_manager import db_manager
from wxauto_mgt.core.api_client import instance_manager
from wxauto_mgt.core.service_platform_manager import platform_manager, rule_manager
from wxauto_mgt.core.message_sender import message_sender

# 导入标准日志记录器
logger = logging.getLogger(__name__)

# 导入文件处理专用日志记录器
from wxauto_mgt.utils import file_logger

class MessageDeliveryService:
    """消息投递服务"""

    def __init__(self, poll_interval: int = 5, batch_size: int = 10,
                merge_messages: bool = True, merge_window: int = 60):
        """
        初始化消息投递服务

        Args:
            poll_interval: 轮询间隔（秒）
            batch_size: 每次处理的消息数量
            merge_messages: 是否合并消息
            merge_window: 消息合并时间窗口（秒）
        """
        self.poll_interval = poll_interval
        self.batch_size = batch_size
        self.merge_messages = merge_messages
        self.merge_window = merge_window

        self._running = False
        self._tasks = set()
        self._lock = asyncio.Lock()
        self._initialized = False
        self._processing_messages: Set[str] = set()  # 正在处理的消息ID集合

    async def initialize(self) -> bool:
        """
        初始化服务

        Returns:
            bool: 是否初始化成功
        """
        if self._initialized:
            return True

        try:
            # 确保数据库表已创建
            await self._ensure_table()

            # 初始化服务平台管理器
            await platform_manager.initialize()

            # 初始化投递规则管理器
            await rule_manager.initialize()

            # 初始化消息发送器
            await message_sender.initialize()

            self._initialized = True
            logger.info("消息投递服务初始化完成")
            return True
        except Exception as e:
            logger.error(f"初始化消息投递服务失败: {e}")
            return False

    async def _ensure_table(self) -> None:
        """确保数据库表已创建"""
        try:
            # 检查messages表是否有投递相关字段
            result = await db_manager.fetchone(
                """
                SELECT sql FROM sqlite_master
                WHERE type='table' AND name='messages'
                """
            )

            if not result:
                logger.error("messages表不存在")
                raise RuntimeError("messages表不存在")

            # 检查是否有delivery_status字段
            table_sql = result['sql']
            if 'delivery_status' not in table_sql:
                # 添加投递相关字段
                await db_manager.execute(
                    "ALTER TABLE messages ADD COLUMN delivery_status INTEGER DEFAULT 0"
                )
                await db_manager.execute(
                    "ALTER TABLE messages ADD COLUMN delivery_time INTEGER"
                )
                await db_manager.execute(
                    "ALTER TABLE messages ADD COLUMN platform_id TEXT"
                )
                await db_manager.execute(
                    "ALTER TABLE messages ADD COLUMN reply_content TEXT"
                )
                await db_manager.execute(
                    "ALTER TABLE messages ADD COLUMN reply_status INTEGER DEFAULT 0"
                )
                await db_manager.execute(
                    "ALTER TABLE messages ADD COLUMN reply_time INTEGER"
                )
                await db_manager.execute(
                    "ALTER TABLE messages ADD COLUMN merged INTEGER DEFAULT 0"
                )
                await db_manager.execute(
                    "ALTER TABLE messages ADD COLUMN merged_count INTEGER DEFAULT 0"
                )
                await db_manager.execute(
                    "ALTER TABLE messages ADD COLUMN merged_ids TEXT"
                )

                # 创建索引
                await db_manager.execute(
                    "CREATE INDEX IF NOT EXISTS idx_messages_delivery_status ON messages(delivery_status)"
                )
                await db_manager.execute(
                    "CREATE INDEX IF NOT EXISTS idx_messages_platform_id ON messages(platform_id)"
                )
                await db_manager.execute(
                    "CREATE INDEX IF NOT EXISTS idx_messages_reply_status ON messages(reply_status)"
                )

                logger.info("添加消息投递相关字段到messages表")
        except Exception as e:
            logger.error(f"确保数据库表结构正确时出错: {e}")
            raise

    async def start(self) -> None:
        """启动服务"""
        if self._running:
            logger.warning("消息投递服务已经在运行")
            return

        if not self._initialized:
            success = await self.initialize()
            if not success:
                logger.error("初始化消息投递服务失败，无法启动")
                return

        self._running = True
        logger.info("启动消息投递服务")

        # 创建消息轮询任务
        poll_task = asyncio.create_task(self._message_poll_loop())
        self._tasks.add(poll_task)
        poll_task.add_done_callback(self._tasks.discard)

    async def stop(self) -> None:
        """停止服务"""
        if not self._running:
            return

        self._running = False
        logger.info("停止消息投递服务")

        # 取消所有任务
        for task in self._tasks:
            task.cancel()

        # 等待所有任务完成
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        self._tasks.clear()

    async def _message_poll_loop(self) -> None:
        """消息轮询循环"""
        while self._running:
            try:
                # 获取所有实例
                instances = instance_manager.get_all_instances()
                file_logger.debug(f"获取到 {len(instances)} 个实例")

                for instance_id in instances:
                    file_logger.debug(f"开始处理实例: {instance_id}")

                    # 获取未处理的消息
                    messages = await self._get_unprocessed_messages(instance_id)

                    if not messages:
                        file_logger.debug(f"实例 {instance_id} 没有未处理的消息")
                        continue

                    file_logger.info(f"获取到 {len(messages)} 条未处理消息，实例: {instance_id}")
                    logger.info(f"获取到 {len(messages)} 条未处理消息，实例: {instance_id}")

                    # 处理消息
                    if self.merge_messages:
                        # 合并消息
                        file_logger.debug(f"开始合并消息")
                        merged_messages = await self._merge_messages(messages)
                        file_logger.info(f"合并后有 {len(merged_messages)} 条消息")
                        logger.info(f"合并后有 {len(merged_messages)} 条消息")

                        for message in merged_messages:
                            file_logger.debug(f"创建处理任务: {message.get('message_id')}")
                            # 创建处理任务
                            task = asyncio.create_task(self.process_message(message))
                            self._tasks.add(task)
                            task.add_done_callback(self._tasks.discard)
                    else:
                        # 逐条处理
                        for message in messages:
                            file_logger.debug(f"创建处理任务: {message.get('message_id')}")
                            # 创建处理任务
                            task = asyncio.create_task(self.process_message(message))
                            self._tasks.add(task)
                            task.add_done_callback(self._tasks.discard)

                # 等待下一次轮询
                file_logger.debug(f"等待下一次轮询，间隔: {self.poll_interval}秒")
                await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                file_logger.info("消息轮询被取消")
                break
            except Exception as e:
                file_logger.error(f"消息轮询出错: {e}")
                file_logger.exception(e)
                logger.error(f"消息轮询出错: {e}")
                await asyncio.sleep(self.poll_interval)

    async def _get_unprocessed_messages(self, instance_id: str) -> List[Dict[str, Any]]:
        """
        获取未处理的消息

        Args:
            instance_id: 实例ID

        Returns:
            List[Dict[str, Any]]: 未处理消息列表
        """
        try:
            # 查询未处理且未投递的消息
            sql = """
            SELECT * FROM messages
            WHERE instance_id = ? AND processed = 0 AND delivery_status = 0
            ORDER BY create_time ASC
            LIMIT ?
            """

            file_logger.debug(f"查询实例 {instance_id} 的未处理消息")
            messages = await db_manager.fetchall(sql, (instance_id, self.batch_size))
            file_logger.debug(f"查询到 {len(messages)} 条未处理消息")

            if messages:
                file_logger.debug(f"消息示例: {messages[0]}")

            # 过滤掉正在处理的消息
            filtered_messages = []
            for msg in messages:
                if msg['message_id'] not in self._processing_messages:
                    filtered_messages.append(msg)
                else:
                    file_logger.debug(f"跳过正在处理的消息: {msg['message_id']}")

            file_logger.debug(f"过滤后剩余 {len(filtered_messages)} 条消息")
            return filtered_messages
        except Exception as e:
            file_logger.error(f"获取未处理消息失败: {e}")
            logger.error(f"获取未处理消息失败: {e}")
            return []

    async def _merge_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        合并消息

        Args:
            messages: 消息列表

        Returns:
            List[Dict[str, Any]]: 合并后的消息列表
        """
        try:
            # 按聊天对象和时间窗口分组
            grouped_messages = {}
            now = int(time.time())

            for msg in messages:
                # 创建分组键：实例ID_聊天对象
                chat_key = f"{msg['instance_id']}_{msg['chat_name']}"

                # 检查时间窗口
                if chat_key not in grouped_messages:
                    grouped_messages[chat_key] = []

                # 添加到分组
                grouped_messages[chat_key].append(msg)

            # 合并消息
            merged_results = []
            for chat_key, msgs in grouped_messages.items():
                if len(msgs) == 1:
                    # 只有一条消息，不需要合并
                    merged_results.append(msgs[0])
                else:
                    # 按时间排序
                    sorted_msgs = sorted(msgs, key=lambda x: x['create_time'])

                    # 检查时间窗口
                    first_msg_time = sorted_msgs[0]['create_time']
                    last_msg_time = sorted_msgs[-1]['create_time']

                    if last_msg_time - first_msg_time > self.merge_window:
                        # 超出时间窗口，不合并
                        for msg in sorted_msgs:
                            merged_results.append(msg)
                    else:
                        # 合并内容
                        merged_content = "\n".join([
                            f"{msg['sender'] or '我'}: {msg['content']}"
                            for msg in sorted_msgs
                        ])

                        # 创建合并后的消息
                        merged_msg = sorted_msgs[-1].copy()  # 使用最新消息作为基础
                        merged_msg['content'] = merged_content
                        merged_msg['merged'] = 1
                        merged_msg['merged_count'] = len(sorted_msgs)
                        merged_msg['merged_ids'] = json.dumps([msg['message_id'] for msg in sorted_msgs])

                        # 添加到结果
                        merged_results.append(merged_msg)

            return merged_results
        except Exception as e:
            logger.error(f"合并消息失败: {e}")
            # 出错时返回原始消息
            return messages

    async def process_message(self, message: Dict[str, Any]) -> bool:
        """
        处理单条消息

        Args:
            message: 消息数据

        Returns:
            bool: 是否处理成功
        """
        message_id = message['message_id']

        # 使用专用日志记录器记录详细信息
        file_logger.info(f"开始处理消息: {message_id}, 类型: {message.get('mtype', '')}, 消息类型: {message.get('message_type', '')}")
        file_logger.debug(f"消息详情: {message}")

        # 添加到正在处理的集合
        self._processing_messages.add(message_id)
        file_logger.debug(f"消息 {message_id} 已添加到处理队列")

        # 获取监听对象的会话ID
        try:
            # 从数据库中获取监听对象的会话ID
            instance_id = message.get('instance_id')
            chat_name = message.get('chat_name')

            if instance_id and chat_name:
                query = "SELECT conversation_id FROM listeners WHERE instance_id = ? AND who = ?"
                listener_data = await db_manager.fetchone(query, (instance_id, chat_name))

                if listener_data and listener_data.get('conversation_id'):
                    conversation_id = listener_data.get('conversation_id')
                    # 将会话ID添加到消息中
                    message['conversation_id'] = conversation_id
                    file_logger.info(f"获取到监听对象的会话ID: {instance_id} - {chat_name} - {conversation_id}")
                    logger.info(f"获取到监听对象的会话ID: {instance_id} - {chat_name} - {conversation_id}")
                else:
                    file_logger.info(f"监听对象没有会话ID: {instance_id} - {chat_name}，将创建新会话")
                    logger.info(f"监听对象没有会话ID: {instance_id} - {chat_name}，将创建新会话")

                    # 检查监听对象是否存在，如果不存在则添加
                    from wxauto_mgt.core.message_listener import message_listener
                    if not await message_listener.has_listener(instance_id, chat_name):
                        logger.info(f"监听对象不存在，尝试添加: {instance_id} - {chat_name}")
                        add_success = await message_listener.add_listener(
                            instance_id,
                            chat_name,
                            save_pic=True,
                            save_file=True,
                            save_voice=True,
                            parse_url=True
                        )
                        if add_success:
                            logger.info(f"成功添加监听对象: {instance_id} - {chat_name}")
                        else:
                            logger.error(f"添加监听对象失败: {instance_id} - {chat_name}")
            else:
                file_logger.warning(f"消息缺少实例ID或聊天名称，无法获取会话ID")
                logger.warning(f"消息缺少实例ID或聊天名称，无法获取会话ID")
        except Exception as e:
            file_logger.error(f"获取监听对象会话ID时出错: {e}")
            logger.error(f"获取监听对象会话ID时出错: {e}")
            logger.exception(e)
            # 继续处理消息，不中断流程

        try:
            # 标记为正在投递
            await self._update_message_delivery_status(message_id, 3)  # 3表示正在投递
            file_logger.debug(f"消息 {message_id} 已标记为正在投递")

            # 匹配规则
            file_logger.debug(f"为消息 {message_id} 匹配规则, 实例: {message.get('instance_id')}, 聊天对象: {message.get('chat_name')}")
            rule = await rule_manager.match_rule(message['instance_id'], message['chat_name'])
            if not rule:
                file_logger.warning(f"消息 {message_id} 没有匹配的投递规则")
                logger.warning(f"消息 {message_id} 没有匹配的投递规则")
                # 标记为投递失败
                await self._update_message_delivery_status(message_id, 2)
                return False

            file_logger.info(f"消息 {message_id} 匹配到规则: {rule.get('id')}, 平台: {rule.get('platform_id')}")

            # 获取服务平台
            file_logger.debug(f"获取服务平台: {rule['platform_id']}")
            platform = await platform_manager.get_platform(rule['platform_id'])
            if not platform:
                file_logger.error(f"找不到服务平台: {rule['platform_id']}")
                logger.error(f"找不到服务平台: {rule['platform_id']}")
                # 标记为投递失败
                await self._update_message_delivery_status(message_id, 2)
                return False

            file_logger.info(f"获取到服务平台: {platform.name}, 类型: {platform.get_type() if hasattr(platform, 'get_type') else 'unknown'}")

            # 投递消息 - 记录详细信息
            file_logger.info(f"投递消息 {message_id} 到平台 {platform.name}")
            logger.info(f"投递消息 {message_id} 到平台 {platform.name}")

            # 检查消息类型，记录更多信息
            if message.get('mtype') in ['image', 'file'] or message.get('file_type') in ['image', 'file']:
                file_logger.info(f"投递文件类型消息: {message_id}, 类型: {message.get('mtype') or message.get('file_type')}")
                if 'local_file_path' in message:
                    file_logger.info(f"文件路径: {message.get('local_file_path')}")

            delivery_result = await self.deliver_message(message, platform)
            file_logger.debug(f"投递结果: {delivery_result}")

            if 'error' in delivery_result:
                file_logger.error(f"投递消息 {message_id} 失败: {delivery_result['error']}")
                logger.error(f"投递消息 {message_id} 失败: {delivery_result['error']}")
                # 标记为投递失败
                await self._update_message_delivery_status(message_id, 2)
                return False

            # 标记为已投递
            file_logger.info(f"消息 {message_id} 投递成功，标记为已投递")
            await self._update_message_delivery_status(
                message_id, 1, rule['platform_id']
            )

            # 发送回复 - 只记录关键信息
            reply_content = delivery_result.get('content', '')
            if reply_content:
                logger.info(f"发送回复: {message['chat_name']}, 内容: {reply_content[:50]}...")
                file_logger.info(f"准备发送回复到微信: 实例={message['instance_id']}, 聊天={message['chat_name']}")
                file_logger.debug(f"回复内容: {reply_content}")

                # 检查是否有会话ID
                if 'conversation_id' in delivery_result:
                    logger.info(f"回复包含会话ID: {delivery_result['conversation_id']}")
                    file_logger.info(f"回复包含会话ID: {delivery_result['conversation_id']}")

                # 发送回复
                reply_success = await self.send_reply(message, reply_content)

                if reply_success:
                    # 标记为已回复
                    logger.info(f"回复发送成功: {message['chat_name']}")
                    file_logger.info(f"回复发送成功: {message['chat_name']}")
                    await self._update_message_reply_status(message_id, 1, reply_content)
                else:
                    # 标记为回复失败
                    logger.error(f"回复发送失败: {message['chat_name']}")
                    file_logger.error(f"回复发送失败: {message['chat_name']}")
                    await self._update_message_reply_status(message_id, 2, reply_content)
            else:
                # 不记录警告日志，只在调试级别记录
                logger.debug(f"平台没有返回回复内容")
                file_logger.warning(f"平台没有返回回复内容: {message_id}")
                # 标记为回复失败
                await self._update_message_reply_status(message_id, 2, '')

            # 标记消息为已处理
            await self._mark_as_processed(message)

            # 只记录处理完成的关键信息
            logger.info(f"消息 {message_id} 处理完成")
            return True
        except Exception as e:
            logger.error(f"处理消息 {message_id} 时出错: {e}")
            # 标记为投递失败
            await self._update_message_delivery_status(message_id, 2)
            return False
        finally:
            # 从正在处理的集合中移除
            self._processing_messages.discard(message_id)

    async def deliver_message(self, message: Dict[str, Any], platform) -> Dict[str, Any]:
        """
        投递消息到指定平台

        Args:
            message: 消息数据
            platform: 服务平台实例

        Returns:
            Dict[str, Any]: 投递结果
        """
        try:
            # 检查消息类型，进行必要的预处理
            mtype = message.get('mtype', '')
            content = message.get('content', '')
            message_id = message.get('message_id', 'unknown')

            # 创建消息的副本，避免修改原始消息
            processed_message = message.copy()

            # 检查是否是合并消息，如果是，尝试查找相关的图片消息
            if message.get('merged', 0) == 1 and message.get('merged_ids'):
                file_logger.info(f"检测到合并消息: {message_id}, 合并数量: {message.get('merged_count', 0)}")

                try:
                    # 解析合并的消息ID
                    import json
                    merged_ids = json.loads(message.get('merged_ids', '[]'))
                    file_logger.debug(f"合并的消息ID: {merged_ids}")

                    # 查询数据库，获取合并的消息详情
                    from wxauto_mgt.data.db_manager import db_manager

                    # 查找图片或文件类型的消息
                    for merged_id in merged_ids:
                        file_logger.debug(f"查询合并消息: {merged_id}")
                        merged_messages = await db_manager.fetch_all(
                            "SELECT * FROM messages WHERE message_id = ?",
                            (merged_id,)
                        )

                        if merged_messages:
                            merged_message = merged_messages[0]
                            merged_mtype = merged_message.get('mtype', '')

                            file_logger.debug(f"合并消息详情: {merged_message}")

                            # 如果找到图片或文件类型的消息
                            if merged_mtype in ['image', 'file'] and 'local_file_path' in merged_message:
                                file_logger.info(f"在合并消息中找到图片/文件: {merged_id}, 类型: {merged_mtype}")

                                # 将图片/文件信息添加到处理消息中
                                processed_message['file_type'] = merged_mtype
                                processed_message['local_file_path'] = merged_message.get('local_file_path')
                                processed_message['original_file_path'] = merged_message.get('original_file_path')
                                processed_message['file_size'] = merged_message.get('file_size')

                                file_logger.info(f"从合并消息中提取文件信息: {processed_message.get('local_file_path')}")
                                break
                except Exception as e:
                    file_logger.error(f"处理合并消息时出错: {e}")
                    file_logger.exception(e)

            # 处理卡片类型消息
            if mtype == 'card':
                # 移除[wxauto卡片链接解析]前缀
                processed_message['content'] = content.replace('[wxauto卡片链接解析]', '').strip()
                logger.info(f"投递前处理卡片消息: {message_id}, 移除前缀")

            # 处理语音类型消息
            elif mtype == 'voice':
                # 移除[wxauto语音解析]前缀
                processed_message['content'] = content.replace('[wxauto语音解析]', '').strip()
                logger.info(f"投递前处理语音消息: {message_id}, 移除前缀")

            # 处理图片或文件类型消息
            elif mtype in ['image', 'file'] or message.get('file_type') in ['image', 'file'] or processed_message.get('file_type') in ['image', 'file']:
                # 确保文件类型信息存在
                if 'file_type' not in processed_message and mtype in ['image', 'file']:
                    processed_message['file_type'] = mtype

                file_logger.info(f"投递文件类型消息: {message_id}, 类型: {processed_message.get('file_type')}")
                logger.info(f"投递文件类型消息: {message_id}, 类型: {processed_message.get('file_type')}")

                # 记录完整的消息信息，用于调试
                file_logger.debug(f"文件类型消息完整信息: {processed_message}")

                # 确保本地文件路径信息存在
                if 'local_file_path' not in processed_message:
                    if 'original_file_path' in processed_message:
                        # 如果没有本地文件路径但有原始路径，记录警告
                        file_logger.warning(f"消息 {message_id} 缺少本地文件路径，可能无法正确处理文件")
                        logger.warning(f"消息 {message_id} 缺少本地文件路径，可能无法正确处理文件")
                    else:
                        file_logger.error(f"消息 {message_id} 既没有本地文件路径也没有原始文件路径，无法处理文件")
                        logger.error(f"消息 {message_id} 既没有本地文件路径也没有原始文件路径，无法处理文件")
                else:
                    file_logger.info(f"消息 {message_id} 的本地文件路径: {processed_message.get('local_file_path')}")
                    logger.debug(f"消息 {message_id} 的本地文件路径存在")

                    # 如果是Dify平台，需要先上传文件
                    try:
                        # 强制检查平台类型，确保是Dify平台
                        platform_type = platform.get_type() if hasattr(platform, "get_type") else "unknown"
                        file_logger.info(f"平台类型: {platform_type}")

                        if platform_type == "dify" and hasattr(platform, "upload_file_to_dify"):
                            file_path = processed_message['local_file_path']
                            file_logger.info(f"准备上传文件到Dify: {file_path}")

                            # 先上传文件到Dify
                            upload_result = await platform.upload_file_to_dify(file_path)
                            file_logger.debug(f"上传结果: {upload_result}")

                            if 'error' in upload_result:
                                file_logger.error(f"上传文件失败: {upload_result['error']}")
                                logger.error(f"上传文件失败: {upload_result['error']}")
                                # 如果上传失败，返回错误，不继续处理
                                return {"error": f"上传文件失败: {upload_result['error']}"}
                            else:
                                # 获取文件ID
                                file_id = upload_result.get('id')
                                if file_id:
                                    file_logger.info(f"文件上传成功，获取到文件ID: {file_id}")

                                    # 从上传结果中获取Dify文件类型
                                    dify_file_type = upload_result.get('dify_file_type', 'document')

                                    # 添加文件信息到消息中
                                    processed_message['dify_file'] = {
                                        "id": file_id,
                                        "type": dify_file_type,
                                        "transfer_method": "local_file"
                                    }

                                    file_logger.info(f"已添加文件信息到消息: {file_id}, 类型: {dify_file_type}")
                                    logger.info(f"已添加文件信息到消息: {file_id}")
                                else:
                                    # 如果没有获取到文件ID，返回错误，不继续处理
                                    file_logger.error("上传文件成功但未获取到文件ID")
                                    return {"error": "上传文件成功但未获取到文件ID"}
                        else:
                            file_logger.warning(f"不是Dify平台或平台不支持上传文件: platform_type={platform_type}, has_upload_method={hasattr(platform, 'upload_file_to_dify')}")
                    except Exception as e:
                        file_logger.error(f"处理文件上传时出错: {e}")
                        file_logger.exception(e)
                        # 如果处理文件上传时出错，返回错误，不继续处理
                        return {"error": f"处理文件上传时出错: {str(e)}"}

            # 处理消息
            file_logger.info(f"准备调用平台处理消息: {message_id}, 平台类型: {platform.get_type() if hasattr(platform, 'get_type') else 'unknown'}")
            file_logger.debug(f"处理前的消息数据: {processed_message}")

            # 检查是否包含文件信息
            if 'dify_file' in processed_message:
                file_logger.info(f"消息包含已上传的文件信息: {processed_message.get('dify_file')}")
            elif 'local_file_path' in processed_message:
                file_logger.info(f"消息包含本地文件路径: {processed_message.get('local_file_path')}")

            result = await platform.process_message(processed_message)
            file_logger.info(f"平台处理消息完成: {message_id}")
            file_logger.debug(f"处理结果: {result}")

            # 检查是否返回了新的会话ID
            if 'conversation_id' in result:
                new_conversation_id = result.get('conversation_id')
                instance_id = message.get('instance_id')
                chat_name = message.get('chat_name')

                if new_conversation_id and instance_id and chat_name:
                    try:
                        # 导入消息监听器
                        from wxauto_mgt.core.message_listener import message_listener

                        # 更新监听对象的会话ID
                        await message_listener.add_listener(
                            instance_id,
                            chat_name,
                            conversation_id=new_conversation_id
                        )

                        file_logger.info(f"已更新监听对象的会话ID: {instance_id} - {chat_name} - {new_conversation_id}")
                        logger.info(f"已更新监听对象的会话ID: {instance_id} - {chat_name}")
                    except Exception as e:
                        file_logger.error(f"更新监听对象会话ID时出错: {e}")
                        logger.error(f"更新监听对象会话ID时出错: {e}")

            return result
        except Exception as e:
            logger.error(f"投递消息失败: {e}")
            logger.exception(e)
            return {"error": str(e)}

    async def send_reply(self, message: Dict[str, Any], reply_content: str) -> bool:
        """
        发送回复

        Args:
            message: 原始消息
            reply_content: 回复内容

        Returns:
            bool: 是否发送成功
        """
        try:
            # 记录详细日志
            logger.info(f"开始发送回复: 实例={message['instance_id']}, 聊天={message['chat_name']}")
            file_logger.info(f"开始发送回复: 实例={message['instance_id']}, 聊天={message['chat_name']}")

            # 检查消息发送器是否已初始化
            if not hasattr(message_sender, '_initialized') or not message_sender._initialized:
                logger.warning("消息发送器未初始化，尝试初始化")
                await message_sender.initialize()

            # 使用消息发送器发送回复
            result, error_msg = await message_sender.send_message(
                message['instance_id'],
                message['chat_name'],
                reply_content
            )

            if not result:
                logger.error(f"发送回复失败: {error_msg}")
                file_logger.error(f"发送回复失败: {error_msg}")
                return False

            logger.info(f"发送回复成功: {message['chat_name']}")
            file_logger.info(f"发送回复成功: {message['chat_name']}")
            return True
        except Exception as e:
            logger.error(f"发送回复失败: {e}")
            file_logger.error(f"发送回复失败: {e}")
            logger.exception(e)
            return False

    async def _mark_as_processed(self, message: Dict[str, Any]) -> bool:
        """
        标记消息为已处理

        Args:
            message: 消息数据

        Returns:
            bool: 是否标记成功
        """
        try:
            # 如果是合并消息，标记所有合并的消息为已处理
            if message.get('merged', 0) == 1 and message.get('merged_ids'):
                merged_ids = json.loads(message['merged_ids'])
                for msg_id in merged_ids:
                    await db_manager.execute(
                        "UPDATE messages SET processed = 1 WHERE message_id = ?",
                        (msg_id,)
                    )
                return True
            else:
                # 标记单条消息为已处理
                await db_manager.execute(
                    "UPDATE messages SET processed = 1 WHERE message_id = ?",
                    (message['message_id'],)
                )
                return True
        except Exception as e:
            logger.error(f"标记消息为已处理失败: {e}")
            return False

    async def _update_message_delivery_status(self, message_id: str, status: int,
                                             platform_id: str = None) -> bool:
        """
        更新消息投递状态

        Args:
            message_id: 消息ID
            status: 投递状态（0未投递，1已投递，2投递失败，3正在投递）
            platform_id: 服务平台ID

        Returns:
            bool: 是否更新成功
        """
        try:
            now = int(time.time())

            if platform_id:
                await db_manager.execute(
                    """
                    UPDATE messages
                    SET delivery_status = ?, delivery_time = ?, platform_id = ?
                    WHERE message_id = ?
                    """,
                    (status, now, platform_id, message_id)
                )
            else:
                await db_manager.execute(
                    """
                    UPDATE messages
                    SET delivery_status = ?, delivery_time = ?
                    WHERE message_id = ?
                    """,
                    (status, now, message_id)
                )

            return True
        except Exception as e:
            logger.error(f"更新消息投递状态失败: {e}")
            return False

    async def _update_message_reply_status(self, message_id: str, status: int,
                                          reply_content: str) -> bool:
        """
        更新消息回复状态

        Args:
            message_id: 消息ID
            status: 回复状态（0未回复，1已回复，2回复失败）
            reply_content: 回复内容

        Returns:
            bool: 是否更新成功
        """
        try:
            now = int(time.time())

            await db_manager.execute(
                """
                UPDATE messages
                SET reply_status = ?, reply_time = ?, reply_content = ?
                WHERE message_id = ?
                """,
                (status, now, reply_content, message_id)
            )

            return True
        except Exception as e:
            logger.error(f"更新消息回复状态失败: {e}")
            return False


# 创建全局实例
message_delivery_service = MessageDeliveryService()
