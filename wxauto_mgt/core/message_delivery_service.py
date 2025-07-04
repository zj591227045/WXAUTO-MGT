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

# 导入标准日志记录器 - 使用主日志记录器，确保所有日志都记录到主日志文件
logger = logging.getLogger('wxauto_mgt')
# 设置为DEBUG级别，确保捕获所有详细日志
logger.setLevel(logging.DEBUG)

# 导入文件处理专用日志记录器 - 现在也使用主日志记录器
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

        # 启动独立的轮询循环
        await self._start_independent_polling()

        # 启动卡住消息监控
        await self.start_stuck_message_monitor()

        logger.info("消息投递服务启动完成")

    async def _start_independent_polling(self):
        """启动完全独立的轮询循环"""
        logger.info("🚀 启动独立的消息投递轮询循环")

        # 创建独立的轮询任务（保留这个，因为它是长期运行的后台任务）
        poll_task = asyncio.create_task(self._independent_poll_loop())
        self._tasks.add(poll_task)

        # 添加任务监控
        def task_monitor(task):
            self._tasks.discard(task)
            if task.cancelled():
                logger.warning("⚠️ 独立轮询任务被取消")
            elif task.exception():
                logger.error(f"❌ 独立轮询任务异常: {task.exception()}")
                import traceback
                logger.error(f"异常堆栈: {traceback.format_exc()}")
                # 自动重启
                if self._running:
                    logger.info("🔄 自动重启独立轮询任务...")
                    asyncio.create_task(self._restart_polling())
            else:
                logger.info("✅ 独立轮询任务正常完成")

        poll_task.add_done_callback(task_monitor)
        logger.info("✅ 独立轮询任务已创建并启动")

    async def _restart_polling(self):
        """重启轮询任务"""
        await asyncio.sleep(1)  # 短暂延迟
        if self._running:
            await self._start_independent_polling()

    async def _independent_poll_loop(self):
        """完全独立的轮询循环"""
        logger.info("🔄 独立轮询循环开始运行")
        loop_count = 0

        while self._running:
            loop_count += 1
            try:
                logger.debug(f"🔍 独立轮询循环第 {loop_count} 次迭代开始")

                # 直接处理消息，不依赖其他服务
                await self._process_messages_independently()

                logger.debug(f"✅ 独立轮询循环第 {loop_count} 次迭代完成")

                # 等待下一次轮询
                await asyncio.sleep(self.poll_interval)

            except asyncio.CancelledError:
                logger.info("🛑 独立轮询循环被取消")
                break
            except Exception as e:
                logger.error(f"❌ 独立轮询循环第 {loop_count} 次迭代出错: {e}")
                import traceback
                logger.error(f"错误堆栈: {traceback.format_exc()}")
                # 继续运行，不退出
                await asyncio.sleep(self.poll_interval)

        logger.info("🏁 独立轮询循环结束")

    async def _process_messages_independently(self):
        """独立处理消息，不依赖其他服务"""
        try:
            # 直接查询数据库获取未处理消息
            # 包括投递失败(2)和正在投递(3)的消息，以便重新处理
            sql = """
            SELECT * FROM messages
            WHERE processed = 0 AND delivery_status IN (0, 2, 3)
            ORDER BY create_time ASC
            LIMIT ?
            """

            messages = await db_manager.fetchall(sql, (self.batch_size,))

            if not messages:
                logger.debug("🔍 独立轮询: 没有未处理的消息")
                return

            logger.info(f"🎯 独立轮询: 发现 {len(messages)} 条未处理消息")

            # 处理每条消息
            for message in messages:
                message_dict = dict(message)
                message_id = message_dict.get('message_id', 'unknown')

                # 检查是否正在处理
                if message_id in self._processing_messages:
                    logger.debug(f"⏭️ 跳过正在处理的消息: {message_id}")
                    continue

                logger.info(f"🚀 独立处理消息: {message_id}")

                # 直接处理消息，避免异步任务冲突
                try:
                    await self.process_message(message_dict)
                except Exception as e:
                    logger.error(f"❌ 处理消息 {message_id} 时出错: {e}")
                    import traceback
                    logger.error(f"错误堆栈: {traceback.format_exc()}")

        except Exception as e:
            logger.error(f"❌ 独立消息处理出错: {e}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")

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
        logger.info("消息投递服务轮询循环已启动")
        while self._running:
            try:
                # 获取所有实例
                instances = instance_manager.get_all_instances()
                file_logger.debug(f"获取到 {len(instances)} 个实例")
                logger.debug(f"消息投递轮询: 获取到 {len(instances)} 个实例")

                for instance_id in instances:
                    file_logger.debug(f"开始处理实例: {instance_id}")
                    logger.debug(f"消息投递轮询: 开始处理实例 {instance_id}")

                    # 获取未处理的消息
                    messages = await self._get_unprocessed_messages(instance_id)

                    if not messages:
                        file_logger.debug(f"实例 {instance_id} 没有未处理的消息")
                        logger.debug(f"消息投递轮询: 实例 {instance_id} 没有未处理的消息")
                        continue

                    file_logger.info(f"获取到 {len(messages)} 条未处理消息，实例: {instance_id}")
                    logger.info(f"消息投递轮询: 获取到 {len(messages)} 条未处理消息，实例: {instance_id}")

                    # 处理消息
                    if self.merge_messages:
                        # 合并消息
                        file_logger.debug(f"开始合并消息")
                        merged_messages = await self._merge_messages(messages)
                        file_logger.info(f"合并后有 {len(merged_messages)} 条消息")
                        logger.info(f"合并后有 {len(merged_messages)} 条消息")

                        for message in merged_messages:
                            file_logger.debug(f"处理消息: {message.get('message_id')}")
                            # 直接处理消息，避免异步任务冲突
                            try:
                                await self.process_message(message)
                            except Exception as e:
                                logger.error(f"❌ 处理合并消息 {message.get('message_id')} 时出错: {e}")
                                import traceback
                                logger.error(f"错误堆栈: {traceback.format_exc()}")
                    else:
                        # 逐条处理
                        for message in messages:
                            file_logger.debug(f"处理消息: {message.get('message_id')}")
                            # 直接处理消息，避免异步任务冲突
                            try:
                                await self.process_message(message)
                            except Exception as e:
                                logger.error(f"❌ 处理消息 {message.get('message_id')} 时出错: {e}")
                                import traceback
                                logger.error(f"错误堆栈: {traceback.format_exc()}")

                # 等待下一次轮询
                file_logger.debug(f"等待下一次轮询，间隔: {self.poll_interval}秒")
                logger.debug(f"消息投递轮询: 等待下一次轮询，间隔: {self.poll_interval}秒")
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
            # 查询未处理的消息，包括投递失败和正在投递的消息
            sql = """
            SELECT * FROM messages
            WHERE instance_id = ? AND processed = 0 AND delivery_status IN (0, 2, 3)
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
        处理单条消息（带超时机制）

        Args:
            message: 消息数据

        Returns:
            bool: 是否处理成功
        """
        message_id = message['message_id']

        # 记录消息处理开始
        logger.debug(f"开始处理消息: {message_id}")

        # 使用超时机制包装实际的处理逻辑
        try:
            # 设置30秒超时
            async with asyncio.timeout(30):
                return await self._process_message_internal(message)
        except asyncio.TimeoutError:
            logger.error(f"❌ 消息处理超时: {message_id} (30秒)")
            # 超时处理：重置状态，清理资源
            await self._handle_timeout(message_id)
            return False
        except Exception as e:
            logger.error(f"❌ 消息处理异常: {message_id}, 错误: {e}")
            import traceback
            logger.error(f"异常堆栈: {traceback.format_exc()}")
            # 异常处理：重置状态，清理资源
            await self._handle_exception(message_id, e)
            return False

    async def _process_message_internal(self, message: Dict[str, Any]) -> bool:
        """
        内部消息处理逻辑

        Args:
            message: 消息数据

        Returns:
            bool: 是否处理成功
        """
        message_id = message['message_id']

        # 使用主日志记录器记录详细信息
        logger.info(f"开始处理消息: ID={message_id}, 实例={message.get('instance_id')}, 聊天={message.get('chat_name')}, 发送者={message.get('sender')}, 类型={message.get('mtype', '')}, 消息类型={message.get('message_type', '')}")
        logger.debug(f"消息内容: {message.get('content', '')[:100]}{'...' if len(message.get('content', '')) > 100 else ''}")

        # 如果是文件类型消息，记录文件信息
        if message.get('mtype') in ['image', 'file'] or message.get('file_type') in ['image', 'file']:
            logger.debug(f"文件消息: ID={message_id}, 本地路径={message.get('local_file_path', '未知')}, 文件大小={message.get('file_size', '未知')}")

        # 记录完整消息详情到调试日志
        logger.debug(f"消息完整详情: {message}")

        # 添加到正在处理的集合
        self._processing_messages.add(message_id)
        logger.debug(f"消息 {message_id} 已添加到处理队列")

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
            file_logger.info(f"为消息 {message_id} 匹配规则, 实例: {message.get('instance_id')}, 聊天对象: {message.get('chat_name')}")
            logger.info(f"为消息 {message_id} 匹配规则, 实例: {message.get('instance_id')}, 聊天对象: {message.get('chat_name')}")
            # 传递消息内容，用于检查@消息
            content = message.get('content', '')
            rule = await rule_manager.match_rule(message['instance_id'], message['chat_name'], content)
            if not rule:
                file_logger.warning(f"消息 {message_id} 没有匹配的投递规则，将删除该消息")
                logger.warning(f"消息 {message_id} 没有匹配的投递规则，将删除该消息")
                # 直接删除消息，而不是标记为已处理
                delete_result = await self._delete_message(message)
                logger.info(f"删除消息 {message_id} 结果: {delete_result}")
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
            logger.info(f"投递消息: ID={message_id}, 实例={message.get('instance_id')}, 聊天={message.get('chat_name')}, 平台={platform.name}, 平台类型={platform.get_type() if hasattr(platform, 'get_type') else 'unknown'}")

            # 记录消息内容摘要
            content = message.get('content', '')
            logger.debug(f"投递消息内容: {content[:100]}{'...' if len(content) > 100 else ''}")

            # 检查消息类型，记录更多信息
            if message.get('mtype') in ['image', 'file'] or message.get('file_type') in ['image', 'file']:
                logger.info(f"投递文件类型消息: ID={message_id}, 类型={message.get('mtype') or message.get('file_type')}, 文件大小={message.get('file_size', '未知')}")
                if 'local_file_path' in message:
                    logger.debug(f"文件路径: {message.get('local_file_path')}")

            logger.debug(f"🚀 开始调用deliver_message方法: {message_id}")
            delivery_result = await self.deliver_message(message, platform)
            logger.debug(f"📊 deliver_message返回结果: {delivery_result}")
            file_logger.debug(f"投递结果: {delivery_result}")

            # 记录投递完成，开始后续处理
            logger.debug(f"平台处理完成，开始后续处理: {message_id}")

            logger.debug(f"🔍 检查投递结果是否包含错误: {'error' in delivery_result}")
            if 'error' in delivery_result:
                file_logger.error(f"投递消息 {message_id} 失败: {delivery_result['error']}")
                logger.error(f"投递消息 {message_id} 失败: {delivery_result['error']}")
                # 标记为投递失败
                await self._update_message_delivery_status(message_id, 2)
                return False

            # 标记为已投递
            file_logger.info(f"消息 {message_id} 投递成功，标记为已投递")
            # 使用特殊格式的日志，确保能被UI识别
            logger.info(f"【转发消息到{platform.name}平台成功】: ID={message_id}, 实例={message.get('instance_id')}, 聊天={message.get('chat_name')}")

            # 更新投递状态为已投递(1)
            logger.debug(f"🔄 开始更新消息 {message_id} 的投递状态为已投递(1)")
            update_result = await self._update_message_delivery_status(
                message_id, 1, rule['platform_id']
            )
            if update_result:
                logger.debug(f"✅ 消息 {message_id} 投递状态更新成功")
            else:
                logger.error(f"❌ 消息 {message_id} 投递状态更新失败")
                # 即使状态更新失败，也继续处理回复
                file_logger.error(f"消息 {message_id} 投递状态更新失败，但继续处理回复")

            # 发送回复 - 记录详细信息
            logger.debug(f"🔄 步骤4: 开始处理回复发送，消息ID: {message_id}")

            # 检查平台是否建议发送回复
            should_reply = delivery_result.get('should_reply', True)  # 默认发送回复
            reply_content = delivery_result.get('content', '') or delivery_result.get('reply_content', '')

            # 添加调试日志，帮助诊断问题
            logger.debug(f"🔍 回复检查: should_reply={should_reply}, reply_content长度={len(reply_content) if reply_content else 0}")
            logger.debug(f"🔍 delivery_result keys: {list(delivery_result.keys())}")
            if 'content' in delivery_result:
                logger.debug(f"🔍 delivery_result['content']: {delivery_result['content'][:100] if delivery_result['content'] else 'None/Empty'}")

            if should_reply and reply_content:
                logger.debug(f"✅ 满足回复条件，准备发送回复: {message_id}")
                # 记录详细的回复信息
                logger.info(f"准备发送回复: ID={message_id}, 实例={message['instance_id']}, 聊天={message['chat_name']}, 内容长度={len(reply_content)}")
                logger.debug(f"回复内容摘要: {reply_content[:100]}{'...' if len(reply_content) > 100 else ''}")

                # 记录完整回复内容到调试日志
                logger.debug(f"完整回复内容: {reply_content}")

                # 检查是否有会话ID
                if 'conversation_id' in delivery_result:
                    logger.info(f"回复使用会话ID: {delivery_result['conversation_id']}, 消息ID={message_id}")

                    # 更新数据库中的会话ID
                    try:
                        # 更新监听对象的会话ID
                        from wxauto_mgt.data.db_manager import db_manager
                        await db_manager.execute(
                            "UPDATE listeners SET conversation_id = ? WHERE instance_id = ? AND who = ?",
                            (delivery_result['conversation_id'], message['instance_id'], message['chat_name'])
                        )
                        logger.info(f"已更新监听对象的会话ID: {message['instance_id']} - {message['chat_name']} - {delivery_result['conversation_id']}")
                    except Exception as e:
                        logger.error(f"更新会话ID时出错: {e}")

                # 发送回复
                logger.debug(f"🚀 步骤5: 开始发送回复到微信，消息ID: {message_id}")
                logger.info(f"开始发送回复到微信: ID={message_id}, 实例={message['instance_id']}, 聊天={message['chat_name']}")

                logger.debug(f"🔄 调用send_reply方法: {message_id}")
                reply_success = await self.send_reply(message, reply_content)
                logger.debug(f"📊 send_reply返回结果: {reply_success}, 消息ID: {message_id}")

                logger.debug(f"🔍 检查回复发送结果: {reply_success}, 消息ID: {message_id}")
                if reply_success:
                    # 标记为已回复
                    logger.debug(f"🚀 步骤6: 更新回复状态为成功，消息ID: {message_id}")
                    logger.info(f"回复发送成功: ID={message_id}, 聊天={message['chat_name']}")

                    logger.debug(f"🔄 调用_update_message_reply_status(成功): {message_id}")
                    await self._update_message_reply_status(message_id, 1, reply_content)
                    logger.debug(f"✅ 回复状态更新完成(成功): {message_id}")
                else:
                    # 标记为回复失败
                    logger.debug(f"🚀 步骤6: 更新回复状态为失败，消息ID: {message_id}")
                    logger.error(f"回复发送失败: ID={message_id}, 聊天={message['chat_name']}")

                    logger.debug(f"🔄 调用_update_message_reply_status(失败): {message_id}")
                    await self._update_message_reply_status(message_id, 2, reply_content)
                    logger.debug(f"✅ 回复状态更新完成(失败): {message_id}")
            elif not should_reply:
                # 平台建议不发送回复（如"信息与记账无关"）
                logger.info(f"平台建议不发送回复: ID={message_id}, 实例={message['instance_id']}, 聊天={message['chat_name']}")
                # 标记为不需要回复（使用状态0表示不需要回复）
                await self._update_message_reply_status(message_id, 0, reply_content or "不需要回复")
            else:
                # 记录警告日志
                logger.warning(f"平台没有返回回复内容: ID={message_id}, 实例={message['instance_id']}, 聊天={message['chat_name']}")
                # 标记为回复失败
                await self._update_message_reply_status(message_id, 2, '')

            # 标记消息为已处理
            logger.debug(f"🚀 步骤7: 标记消息为已处理，消息ID: {message_id}")
            logger.debug(f"🔄 调用_mark_as_processed: {message_id}")
            await self._mark_as_processed(message)
            logger.debug(f"✅ 消息已标记为已处理: {message_id}")

            # 只记录处理完成的关键信息
            logger.info(f"🎉 消息 {message_id} 处理完成")
            logger.debug(f"🏁 process_message方法即将返回True: {message_id}")
            return True
        except Exception as e:
            logger.error(f"❌ 处理消息 {message_id} 时出错: {e}")
            logger.error(f"❌ 异常类型: {type(e).__name__}")
            import traceback
            logger.error(f"❌ 异常堆栈: {traceback.format_exc()}")
            # 标记为投递失败
            await self._update_message_delivery_status(message_id, 2)
            return False
        finally:
            # 从正在处理的集合中移除
            self._processing_messages.discard(message_id)

    async def _handle_timeout(self, message_id: str):
        """处理消息处理超时"""
        try:
            logger.error(f"⏰ 处理消息超时，开始清理: {message_id}")

            # 重置消息状态为未投递
            await self._update_message_delivery_status(message_id, 0)
            logger.info(f"✅ 已重置超时消息状态: {message_id}")

            # 从正在处理的集合中移除
            self._processing_messages.discard(message_id)

        except Exception as e:
            logger.error(f"❌ 处理超时清理时出错: {message_id}, 错误: {e}")

    async def _handle_exception(self, message_id: str, exception: Exception):
        """处理消息处理异常"""
        try:
            logger.error(f"💥 处理消息异常，开始清理: {message_id}, 异常: {exception}")

            # 标记为投递失败
            await self._update_message_delivery_status(message_id, 2)
            logger.info(f"✅ 已标记异常消息为失败: {message_id}")

            # 从正在处理的集合中移除
            self._processing_messages.discard(message_id)

        except Exception as e:
            logger.error(f"❌ 处理异常清理时出错: {message_id}, 错误: {e}")

    async def _monitor_stuck_messages(self):
        """监控并自动恢复卡住的消息"""
        try:
            current_time = int(time.time())
            # 查找超过2分钟仍在"正在投递"状态的消息
            threshold_time = current_time - 120  # 2分钟前

            stuck_sql = """
            SELECT message_id, create_time, delivery_time
            FROM messages
            WHERE delivery_status = 3 AND delivery_time < ?
            ORDER BY create_time ASC
            """

            stuck_messages = await db_manager.fetchall(stuck_sql, (threshold_time,))

            if stuck_messages:
                logger.warning(f"🔍 发现 {len(stuck_messages)} 条卡住的消息，开始自动恢复")

                for msg in stuck_messages:
                    msg_dict = dict(msg)
                    message_id = msg_dict['message_id']
                    stuck_duration = current_time - (msg_dict['delivery_time'] or msg_dict['create_time'])

                    logger.warning(f"⚠️ 消息 {message_id} 卡住了 {stuck_duration:.1f} 秒，开始恢复")

                    # 重置状态为未投递，让独立轮询重新处理
                    await self._update_message_delivery_status(message_id, 0)

                    # 从正在处理的集合中移除
                    self._processing_messages.discard(message_id)

                    logger.info(f"✅ 已恢复卡住的消息: {message_id}")

        except Exception as e:
            logger.error(f"❌ 监控卡住消息时出错: {e}")

    async def start_stuck_message_monitor(self):
        """启动卡住消息监控任务"""
        async def monitor_loop():
            while self._running:
                try:
                    await self._monitor_stuck_messages()
                    # 每分钟检查一次
                    await asyncio.sleep(60)
                except Exception as e:
                    logger.error(f"❌ 监控循环出错: {e}")
                    await asyncio.sleep(60)  # 出错后也等待60秒再重试

        # 创建监控任务（保留这个，因为它是长期运行的后台任务）
        monitor_task = asyncio.create_task(monitor_loop())
        self._tasks.add(monitor_task)
        monitor_task.add_done_callback(self._tasks.discard)

        logger.info("🔍 卡住消息监控任务已启动")

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
                        merged_messages = await db_manager.fetchall(
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
                        # 创建专用的Dify上传调试日志记录器
                        import logging
                        import os
                        import sys
                        from pathlib import Path

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

                            dify_debug_logger.info("Dify上传调试日志记录器已初始化 (message_delivery_service)")

                        # 强制检查平台类型，确保是Dify平台
                        platform_type = platform.get_type() if hasattr(platform, "get_type") else "unknown"
                        file_logger.info(f"平台类型: {platform_type}")
                        dify_debug_logger.info(f"平台类型: {platform_type}")

                        # 记录平台详细信息
                        dify_debug_logger.info(f"平台ID: {platform.platform_id if hasattr(platform, 'platform_id') else 'unknown'}")
                        dify_debug_logger.info(f"平台名称: {platform.name if hasattr(platform, 'name') else 'unknown'}")
                        dify_debug_logger.info(f"平台API基础URL: {platform.api_base if hasattr(platform, 'api_base') else 'unknown'}")

                        # 记录消息ID和类型
                        message_id = processed_message.get('message_id', 'unknown')
                        dify_debug_logger.info(f"处理消息: ID={message_id}, 类型={processed_message.get('mtype', 'unknown')}")

                        if platform_type == "dify" and hasattr(platform, "upload_file_to_dify"):
                            file_path = processed_message['local_file_path']
                            file_logger.info(f"准备上传文件到Dify: {file_path}")
                            dify_debug_logger.info(f"准备上传文件到Dify: {file_path}")

                            # 检查文件是否存在
                            if os.path.exists(file_path):
                                dify_debug_logger.info(f"文件存在，大小: {os.path.getsize(file_path)} 字节")
                            else:
                                dify_debug_logger.error(f"文件不存在: {file_path}")
                                # 尝试构建完整路径
                                if not os.path.dirname(file_path):
                                    # 确定项目根目录
                                    if getattr(sys, 'frozen', False):
                                        # 打包环境 - 使用可执行文件所在目录
                                        project_root = os.path.dirname(sys.executable)
                                    else:
                                        # 开发环境 - 使用项目根目录
                                        project_root = Path(__file__).parent.parent.parent

                                    download_dir = os.path.join(project_root, "data", "downloads")
                                    full_path = os.path.join(download_dir, file_path)

                                    dify_debug_logger.info(f"尝试构建完整路径: {full_path}")

                                    if os.path.exists(full_path):
                                        dify_debug_logger.info(f"找到文件的完整路径: {full_path}")
                                        file_path = full_path
                                    else:
                                        dify_debug_logger.error(f"文件不存在: 原始路径={file_path}, 尝试的完整路径={full_path}")

                            # 先上传文件到Dify
                            dify_debug_logger.info(f"调用platform.upload_file_to_dify({file_path})...")
                            print(f"[DEBUG] 开始上传文件到Dify: {file_path}")

                            # 记录文件详细信息
                            try:
                                import os
                                if os.path.exists(file_path):
                                    file_size = os.path.getsize(file_path)
                                    file_name = os.path.basename(file_path)
                                    file_ext = os.path.splitext(file_path)[1]
                                    dify_debug_logger.info(f"文件详情: 名称={file_name}, 大小={file_size}字节, 扩展名={file_ext}")
                                    print(f"[DEBUG] 文件详情: 名称={file_name}, 大小={file_size}字节, 扩展名={file_ext}")

                                    # 检查文件权限
                                    try:
                                        with open(file_path, 'rb') as f:
                                            test_read = f.read(10)
                                        dify_debug_logger.info(f"文件可读取，前10个字节: {test_read}")
                                        print(f"[DEBUG] 文件可读取")
                                    except Exception as e:
                                        dify_debug_logger.error(f"文件读取测试失败: {e}")
                                        print(f"[ERROR] 文件读取测试失败: {e}")
                                else:
                                    dify_debug_logger.error(f"文件不存在: {file_path}")
                                    print(f"[ERROR] 文件不存在: {file_path}")
                            except Exception as e:
                                dify_debug_logger.error(f"检查文件详情时出错: {e}")
                                print(f"[ERROR] 检查文件详情时出错: {e}")

                            # 执行上传
                            try:
                                upload_result = await platform.upload_file_to_dify(file_path)
                                file_logger.debug(f"上传结果: {upload_result}")
                                dify_debug_logger.info(f"上传结果: {upload_result}")
                                print(f"[DEBUG] 上传结果: {upload_result}")
                            except Exception as e:
                                dify_debug_logger.error(f"调用upload_file_to_dify时出错: {e}")
                                print(f"[ERROR] 调用upload_file_to_dify时出错: {e}")
                                import traceback
                                tb = traceback.format_exc()
                                dify_debug_logger.error(f"错误堆栈: {tb}")
                                print(f"[ERROR] 错误堆栈: {tb}")
                                raise

                            if 'error' in upload_result:
                                file_logger.error(f"上传文件失败: {upload_result['error']}")
                                logger.error(f"上传文件失败: {upload_result['error']}")
                                dify_debug_logger.error(f"上传文件失败: {upload_result['error']}")
                                # 如果上传失败，返回错误，不继续处理
                                return {"error": f"上传文件失败: {upload_result['error']}"}
                            else:
                                # 获取文件ID
                                file_id = upload_result.get('id')
                                if file_id:
                                    file_logger.info(f"文件上传成功，获取到文件ID: {file_id}")
                                    dify_debug_logger.info(f"文件上传成功，获取到文件ID: {file_id}")

                                    # 从上传结果中获取Dify文件类型
                                    dify_file_type = upload_result.get('dify_file_type', 'document')
                                    dify_debug_logger.info(f"文件类型: {dify_file_type}")

                                    # 添加文件信息到消息中
                                    processed_message['dify_file'] = {
                                        "id": file_id,
                                        "type": dify_file_type,
                                        "transfer_method": "local_file"
                                    }

                                    file_logger.info(f"已添加文件信息到消息: {file_id}, 类型: {dify_file_type}")
                                    logger.info(f"已添加文件信息到消息: {file_id}")
                                    dify_debug_logger.info(f"已添加文件信息到消息: {file_id}, 类型: {dify_file_type}")
                                    dify_debug_logger.info(f"消息处理完成，准备发送到Dify")
                                else:
                                    # 如果没有获取到文件ID，返回错误，不继续处理
                                    file_logger.error("上传文件成功但未获取到文件ID")
                                    dify_debug_logger.error("上传文件成功但未获取到文件ID")
                                    return {"error": "上传文件成功但未获取到文件ID"}
                        else:
                            file_logger.warning(f"不是Dify平台或平台不支持上传文件: platform_type={platform_type}, has_upload_method={hasattr(platform, 'upload_file_to_dify')}")
                            dify_debug_logger.warning(f"不是Dify平台或平台不支持上传文件: platform_type={platform_type}, has_upload_method={hasattr(platform, 'upload_file_to_dify')}")
                    except Exception as e:
                        file_logger.error(f"处理文件上传时出错: {e}")
                        file_logger.exception(e)

                        # 确保dify_debug_logger已初始化
                        try:
                            dify_debug_logger.error(f"处理文件上传时出错: {e}")
                            dify_debug_logger.exception(e)

                            # 记录更详细的错误信息
                            import traceback
                            error_traceback = traceback.format_exc()
                            dify_debug_logger.error(f"详细错误堆栈: {error_traceback}")

                            # 检查是否与文件相关的错误
                            error_str = str(e).lower()
                            if 'file' in error_str or 'upload' in error_str or 'permission' in error_str:
                                dify_debug_logger.error(f"检测到可能与文件相关的错误: {e}")

                            # 记录文件路径信息
                            if 'file_path' in locals():
                                dify_debug_logger.error(f"错误发生时的文件路径: {file_path}")

                            # 记录平台信息
                            if platform and hasattr(platform, 'get_type'):
                                dify_debug_logger.error(f"平台类型: {platform.get_type()}")
                            if platform and hasattr(platform, 'platform_id'):
                                dify_debug_logger.error(f"平台ID: {platform.platform_id}")
                        except Exception as inner_e:
                            file_logger.error(f"记录错误详情时出错: {inner_e}")

                        # 如果处理文件上传时出错，返回错误，不继续处理
                        return {"error": f"处理文件上传时出错: {str(e)}"}

            # 处理消息
            file_logger.info(f"准备调用平台处理消息: {message_id}, 平台类型: {platform.get_type() if hasattr(platform, 'get_type') else 'unknown'}")
            file_logger.debug(f"处理前的消息数据: {processed_message}")

            # 确保dify_debug_logger已初始化
            try:
                dify_debug_logger.info(f"准备调用平台处理消息: {message_id}, 平台类型: {platform.get_type() if hasattr(platform, 'get_type') else 'unknown'}")
                print(f"[DEBUG] 准备调用平台处理消息: {message_id}, 平台类型: {platform.get_type() if hasattr(platform, 'get_type') else 'unknown'}")
            except Exception as e:
                # 如果dify_debug_logger未定义，创建一个新的
                import logging
                import os
                import sys
                from pathlib import Path

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

                dify_debug_logger.info(f"准备调用平台处理消息: {message_id}, 平台类型: {platform.get_type() if hasattr(platform, 'get_type') else 'unknown'}")
                print(f"[DEBUG] 准备调用平台处理消息: {message_id}, 平台类型: {platform.get_type() if hasattr(platform, 'get_type') else 'unknown'}")

            # 检查是否包含文件信息
            if 'dify_file' in processed_message:
                file_logger.info(f"消息包含已上传的文件信息: {processed_message.get('dify_file')}")
                dify_debug_logger.info(f"消息包含已上传的文件信息: {processed_message.get('dify_file')}")
                print(f"[DEBUG] 消息包含已上传的文件信息: {processed_message.get('dify_file')}")
            elif 'local_file_path' in processed_message:
                file_logger.info(f"消息包含本地文件路径: {processed_message.get('local_file_path')}")
                dify_debug_logger.info(f"消息包含本地文件路径: {processed_message.get('local_file_path')}")
                print(f"[DEBUG] 消息包含本地文件路径: {processed_message.get('local_file_path')}")
            else:
                dify_debug_logger.warning(f"消息不包含文件信息，但之前已上传文件")
                print(f"[WARNING] 消息不包含文件信息，但之前已上传文件")

            # 记录会话ID
            if 'conversation_id' in processed_message:
                dify_debug_logger.info(f"使用会话ID: {processed_message['conversation_id']}")
                print(f"[DEBUG] 使用会话ID: {processed_message['conversation_id']}")
            else:
                dify_debug_logger.info("未使用会话ID，将创建新会话")
                print(f"[DEBUG] 未使用会话ID，将创建新会话")

            # 记录完整的消息数据
            dify_debug_logger.info(f"完整的消息数据: {processed_message}")
            print(f"[DEBUG] 完整的消息数据: {processed_message}")

            # 调用平台处理消息
            try:
                dify_debug_logger.info("开始调用platform.process_message...")
                print(f"[DEBUG] 开始调用platform.process_message...")
                result = await platform.process_message(processed_message)
                dify_debug_logger.info(f"平台处理消息完成: {message_id}")
                dify_debug_logger.info(f"处理结果: {result}")
                print(f"[DEBUG] 平台处理消息完成: {message_id}")
                print(f"[DEBUG] 处理结果: {result}")
            except Exception as e:
                dify_debug_logger.error(f"调用platform.process_message时出错: {e}")
                print(f"[ERROR] 调用platform.process_message时出错: {e}")
                import traceback
                tb = traceback.format_exc()
                dify_debug_logger.error(f"错误堆栈: {tb}")
                print(f"[ERROR] 错误堆栈: {tb}")
                raise

            file_logger.info(f"平台处理消息完成: {message_id}")
            file_logger.debug(f"处理结果: {result}")

            # 检查是否有错误信息
            if 'error' in result and '404' in result.get('error', '') and 'Conversation Not Exists' in result.get('error', ''):
                # 处理404错误，清除无效的会话ID
                instance_id = message.get('instance_id')
                chat_name = message.get('chat_name')
                if instance_id and chat_name:
                    file_logger.warning(f"检测到会话ID不存在错误，清除监听对象的会话ID: {instance_id} - {chat_name}")
                    logger.warning(f"检测到会话ID不存在错误，清除监听对象的会话ID: {instance_id} - {chat_name}")
                    await self._clear_invalid_conversation_id(instance_id, chat_name)

            # 检查是否返回了新的会话ID - 仅记录日志，不进行实际更新
            if 'conversation_id' in result:
                new_conversation_id = result.get('conversation_id')
                instance_id = message.get('instance_id')
                chat_name = message.get('chat_name')

                if new_conversation_id and instance_id and chat_name:
                    # 仅记录会话ID信息，不调用add_listener（因为监听对象已存在）
                    file_logger.info(f"消息处理返回会话ID: {instance_id} - {chat_name} - {new_conversation_id}")
                    logger.debug(f"消息处理返回会话ID: {instance_id} - {chat_name}")

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

            # 获取平台ID
            platform_id = message.get('platform_id')
            message_send_mode = None

            # 强制设置为True，用于测试
            reply_at_sender = True
            file_logger.info("强制设置reply_at_sender=True用于测试")
            logger.info("强制设置reply_at_sender=True用于测试")

            # 如果有平台ID，尝试获取平台的消息发送模式
            if platform_id:
                try:
                    # 获取平台信息
                    platform = await platform_manager.get_platform(platform_id)
                    if platform and hasattr(platform, 'message_send_mode'):
                        message_send_mode = platform.message_send_mode
                        file_logger.info(f"从平台获取消息发送模式: {message_send_mode}")
                        logger.info(f"从平台获取消息发送模式: {message_send_mode}")
                except Exception as e:
                    file_logger.error(f"获取平台信息失败: {e}")
                    logger.error(f"获取平台信息失败: {e}")
                    # 继续使用默认模式

            # 准备@列表
            at_list = None
            # 优先使用sender_remark字段，如果没有值则回退使用sender字段
            sender = message.get('sender_remark') or message.get('sender', '')
            if reply_at_sender and sender:
                at_list = [sender]
                file_logger.info(f"将在回复中@发送者: {sender}")
                logger.info(f"将在回复中@发送者: {sender}")

                # 记录消息类型，用于调试
                message_type = message.get('message_type', '')
                file_logger.info(f"消息类型: {message_type}")
                logger.info(f"消息类型: {message_type}")

                # 记录完整的消息数据，用于调试
                file_logger.info(f"完整的消息数据: {message}")
                logger.info(f"完整的消息数据: {message}")

            # 使用消息发送器发送回复
            result, error_msg = await message_sender.send_message(
                message['instance_id'],
                message['chat_name'],
                reply_content,
                message_send_mode,
                at_list
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

    async def _delete_message(self, message: Dict[str, Any]) -> bool:
        """
        从数据库中删除消息

        Args:
            message: 消息数据

        Returns:
            bool: 是否删除成功
        """
        try:
            message_id = message.get('message_id')
            if not message_id:
                logger.error("删除消息失败：消息ID为空")
                return False

            # 如果是合并消息，删除所有合并的消息
            if message.get('merged', 0) == 1 and message.get('merged_ids'):
                try:
                    merged_ids = json.loads(message['merged_ids'])
                    for msg_id in merged_ids:
                        await db_manager.execute(
                            "DELETE FROM messages WHERE message_id = ?",
                            (msg_id,)
                        )
                    file_logger.info(f"已删除合并消息: {message_id}，包含 {len(merged_ids)} 条子消息")
                    logger.info(f"已删除合并消息: {message_id}，包含 {len(merged_ids)} 条子消息")
                except Exception as e:
                    file_logger.error(f"删除合并消息时出错: {e}")
                    logger.error(f"删除合并消息时出错: {e}")
                    # 继续尝试删除主消息

            # 从数据库中删除消息
            await db_manager.execute(
                "DELETE FROM messages WHERE message_id = ?",
                (message_id,)
            )

            file_logger.info(f"已删除不符合规则的消息: {message_id}")
            logger.info(f"已删除不符合规则的消息: {message_id}")
            return True
        except Exception as e:
            logger.error(f"删除消息失败: {e}")
            file_logger.error(f"删除消息失败: {e}")
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

            # 添加详细的调试日志
            status_names = {0: "未投递", 1: "已投递", 2: "投递失败", 3: "正在投递"}
            status_name = status_names.get(status, f"未知状态({status})")
            logger.debug(f"🔄 更新消息 {message_id} 投递状态: {status_name}({status}), 平台ID: {platform_id}")

            if platform_id:
                sql = """
                UPDATE messages
                SET delivery_status = ?, delivery_time = ?, platform_id = ?
                WHERE message_id = ?
                """
                params = (status, now, platform_id, message_id)
                logger.debug(f"🔄 执行SQL: {sql}")
                logger.debug(f"🔄 参数: {params}")

                await db_manager.execute(sql, params)
            else:
                sql = """
                UPDATE messages
                SET delivery_status = ?, delivery_time = ?
                WHERE message_id = ?
                """
                params = (status, now, message_id)
                logger.debug(f"🔄 执行SQL: {sql}")
                logger.debug(f"🔄 参数: {params}")

                await db_manager.execute(sql, params)

            # 验证更新是否成功
            check_sql = "SELECT delivery_status FROM messages WHERE message_id = ?"
            result = await db_manager.fetchone(check_sql, (message_id,))
            if result:
                actual_status = result['delivery_status']
                if actual_status == status:
                    logger.debug(f"✅ 消息 {message_id} 投递状态更新成功: {status_name}({status})")
                else:
                    logger.error(f"❌ 消息 {message_id} 投递状态更新失败: 期望{status}，实际{actual_status}")
                    return False
            else:
                logger.error(f"❌ 消息 {message_id} 不存在，无法验证状态更新")
                return False

            return True
        except Exception as e:
            logger.error(f"❌ 更新消息投递状态失败: {e}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
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

    async def _clear_invalid_conversation_id(self, instance_id: str, chat_name: str) -> bool:
        """
        清除无效的会话ID

        Args:
            instance_id: 实例ID
            chat_name: 聊天对象名称

        Returns:
            bool: 是否清除成功
        """
        try:
            # 导入消息监听器
            from wxauto_mgt.core.message_listener import message_listener

            # 清除监听对象的会话ID（设置为空字符串）
            await message_listener.add_listener(
                instance_id,
                chat_name,
                conversation_id=""  # 清空会话ID
            )

            file_logger.info(f"已清除监听对象的无效会话ID: {instance_id} - {chat_name}")
            logger.info(f"已清除监听对象的无效会话ID: {instance_id} - {chat_name}")

            # 注意：用户会话管理器中的会话ID已经在service_platform.py中处理
            # 这里只需要清除监听对象的会话ID

            return True
        except Exception as e:
            file_logger.error(f"清除监听对象会话ID时出错: {e}")
            logger.error(f"清除监听对象会话ID时出错: {e}")
            return False


# 创建全局实例 - 🔥🔥🔥 强制重新创建实例 🔥🔥🔥
message_delivery_service = MessageDeliveryService()
