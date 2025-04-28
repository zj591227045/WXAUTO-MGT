"""
消息监听管理器模块

该模块负责管理多个微信实例的消息监听、接收和分发。主要功能包括：
- 支持多个wxauto实例的消息监听
- 定时获取各实例主窗口未读消息
- 管理每个实例的监听对象列表
- 定时获取监听对象的最新消息
- 处理消息超时和自动移除监听对象
"""

import asyncio
import logging
import time
import json
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import defaultdict

from wxauto_mgt.core.api_client import instance_manager
from wxauto_mgt.data.db_manager import db_manager

# 配置日志
logger = logging.getLogger(__name__)

@dataclass
class ListenerInfo:
    """监听对象信息"""
    instance_id: str
    who: str
    last_message_time: float
    last_check_time: float
    active: bool = True
    marked_for_removal: bool = False
    processed_at_startup: bool = False  # 是否在启动时处理过
    reset_attempts: int = 0  # 重置尝试次数

class MessageListener:
    def __init__(
        self,
        poll_interval: int = 5,
        max_listeners_per_instance: int = 30,
        timeout_minutes: int = 30
    ):
        """
        初始化消息监听器

        Args:
            poll_interval: 轮询间隔（秒）
            max_listeners_per_instance: 每个实例的最大监听对象数量
            timeout_minutes: 监听对象超时时间（分钟）
        """
        self.poll_interval = poll_interval
        self.max_listeners_per_instance = max_listeners_per_instance
        self.timeout_minutes = timeout_minutes

        # 内部状态
        self.listeners: Dict[str, Dict[str, ListenerInfo]] = {}  # instance_id -> {who -> ListenerInfo}
        self.running: bool = False
        self._tasks: Set[asyncio.Task] = set()
        self._lock = asyncio.Lock()
        self._starting_up = False

        # 启动时间戳，用于提供宽限期
        self.startup_timestamp = 0

    async def start(self):
        """启动监听服务"""
        if self.running:
            logger.warning("监听服务已经在运行")
            return

        # 设置启动时间戳
        self.startup_timestamp = time.time()
        logger.info(f"设置启动时间戳: {datetime.fromtimestamp(self.startup_timestamp).strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("已启用10秒钟宽限期，在此期间不会移除任何超时监听对象")

        self.running = True
        logger.info("启动消息监听服务")

        # 从数据库加载监听对象
        await self._load_listeners_from_db()

        # 加载完成后，暂时锁定超时处理
        # 设置一个标志，防止UI线程同时处理超时对象
        self._starting_up = True
        try:
            # 在启动时手动检查并刷新可能超时的监听对象
            logger.info("启动时检查所有监听对象...")
            await self._refresh_all_listeners()
        finally:
            # 处理完成后，释放锁
            self._starting_up = False

        # 创建主要任务
        main_window_task = asyncio.create_task(self._main_window_check_loop())
        listeners_task = asyncio.create_task(self._listeners_check_loop())
        cleanup_task = asyncio.create_task(self._cleanup_loop())

        self._tasks.update({main_window_task, listeners_task, cleanup_task})

    async def stop(self):
        """停止监听服务"""
        if not self.running:
            return

        self.running = False
        logger.info("停止消息监听服务")

        # 取消所有任务
        for task in self._tasks:
            task.cancel()

        # 等待所有任务完成
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    async def _main_window_check_loop(self):
        """主窗口未读消息检查循环"""
        while self.running:
            try:
                # 获取所有活跃实例
                instances = instance_manager.get_all_instances()
                for instance_id, api_client in instances.items():
                    await self.check_main_window_messages(instance_id, api_client)
                await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"检查主窗口消息时出错: {e}")
                await asyncio.sleep(self.poll_interval)

    async def _listeners_check_loop(self):
        """监听对象消息检查循环"""
        while self.running:
            try:
                # 获取所有活跃实例
                instances = instance_manager.get_all_instances()
                for instance_id, api_client in instances.items():
                    await self.check_listener_messages(instance_id, api_client)
                await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"检查监听对象消息时出错: {e}")
                await asyncio.sleep(self.poll_interval)

    async def _cleanup_loop(self):
        """清理过期监听对象循环"""
        while self.running:
            try:
                await self._remove_inactive_listeners()
                await asyncio.sleep(60)  # 每分钟检查一次
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"清理过期监听对象时出错: {e}")
                await asyncio.sleep(60)

    async def check_main_window_messages(self, instance_id: str, api_client):
        """
        检查指定实例主窗口未读消息

        Args:
            instance_id: 实例ID
            api_client: API客户端实例
        """
        try:
            # 获取主窗口未读消息
            messages = await api_client.get_unread_messages()
            if not messages:
                return

            logger.info(f"从实例 {instance_id} 主窗口获取到 {len(messages)} 条未读消息")

            # 过滤消息
            filtered_messages = self._filter_messages(messages)
            logger.info(f"过滤后主窗口有 {len(filtered_messages)} 条未读消息")

            # 处理每条未读消息
            for msg in filtered_messages:
                chat_name = msg.get('chat_name')
                if chat_name:
                    # 将发送者添加到监听列表 - 这是关键步骤
                    add_success = await self.add_listener(instance_id, chat_name)

                    # 只有成功添加监听对象后，才保存消息到数据库
                    if add_success:
                        # 在保存前再次检查消息是否应该被过滤
                        # 特别是检查sender是否为self
                        from wxauto_mgt.core.message_filter import message_filter

                        # 保存消息到数据库
                        save_data = {
                            'instance_id': instance_id,
                            'chat_name': chat_name,
                            'message_type': msg.get('type'),
                            'content': msg.get('content'),
                            'sender': msg.get('sender'),
                            'sender_remark': msg.get('sender_remark'),
                            'message_id': msg.get('id'),
                            'mtype': msg.get('mtype')
                        }

                        # 直接检查sender是否为self
                        sender = msg.get('sender', '')
                        if sender and (sender.lower() == 'self' or sender == 'Self'):
                            logger.debug(f"过滤掉self发送的主窗口消息: {msg.get('id')}")
                            continue

                        # 使用消息过滤模块进行二次检查
                        if message_filter.should_filter_message(save_data, log_prefix="主窗口保存前"):
                            logger.debug(f"消息过滤模块过滤掉主窗口消息: {msg.get('id')}")
                            continue

                        logger.debug(f"准备保存主窗口消息: {save_data}")
                        await self._save_message(save_data)
                    else:
                        logger.error(f"添加监听对象 {chat_name} 失败，跳过保存消息: {msg.get('id')}")
                        # 不保存消息，因为没有成功添加监听对象

        except Exception as e:
            logger.error(f"处理实例 {instance_id} 主窗口消息时出错: {e}")

    async def check_listener_messages(self, instance_id: str, api_client):
        """
        检查指定实例所有监听对象的新消息

        Args:
            instance_id: 实例ID
            api_client: API客户端实例
        """
        async with self._lock:
            if instance_id not in self.listeners:
                return

            for who, info in list(self.listeners[instance_id].items()):
                if not info.active:
                    continue

                try:
                    # 获取该监听对象的新消息
                    logger.debug(f"开始获取实例 {instance_id} 监听对象 {who} 的新消息")
                    messages = await api_client.get_listener_messages(who)

                    if messages:
                        # 更新最后消息时间
                        info.last_message_time = time.time()
                        logger.info(f"获取到实例 {instance_id} 监听对象 {who} 的 {len(messages)} 条新消息")

                        # 处理消息：筛选掉"以下为新消息"及之前的消息
                        filtered_messages = self._filter_messages(messages)
                        logger.debug(f"过滤后剩余 {len(filtered_messages)} 条新消息")

                        # 保存消息到数据库
                        for msg in filtered_messages:
                            # 在保存前再次检查消息是否应该被过滤
                            # 特别是检查sender是否为self
                            from wxauto_mgt.core.message_filter import message_filter

                            save_data = {
                                'instance_id': instance_id,
                                'chat_name': who,
                                'message_type': msg.get('type'),
                                'content': msg.get('content'),
                                'sender': msg.get('sender'),
                                'sender_remark': msg.get('sender_remark'),
                                'message_id': msg.get('id'),
                                'mtype': msg.get('mtype')
                            }

                            # 直接检查sender是否为self
                            sender = msg.get('sender', '')
                            if sender and (sender.lower() == 'self' or sender == 'Self'):
                                logger.debug(f"过滤掉self发送的消息: {msg.get('id')}")
                                continue

                            # 使用消息过滤模块进行二次检查
                            if message_filter.should_filter_message(save_data, log_prefix="监听器保存前"):
                                logger.debug(f"消息过滤模块过滤掉消息: {msg.get('id')}")
                                continue

                            logger.debug(f"准备保存监听消息: {save_data}")
                            await self._save_message(save_data)
                    else:
                        logger.debug(f"实例 {instance_id} 监听对象 {who} 没有新消息")

                    # 更新检查时间
                    info.last_check_time = time.time()

                except Exception as e:
                    logger.error(f"检查实例 {instance_id} 监听对象 {who} 的消息时出错: {e}")
                    logger.debug(f"错误详情", exc_info=True)

    def _filter_messages(self, messages: List[dict]) -> List[dict]:
        """
        过滤消息列表，处理"以下为新消息"分隔符，并过滤掉self发送的消息和time类型的消息

        Args:
            messages: 原始消息列表

        Returns:
            List[dict]: 过滤后的消息列表
        """
        if not messages:
            return []

        # 使用统一的消息过滤模块
        from wxauto_mgt.core.message_filter import message_filter

        # 先处理"以下为新消息"分隔符
        messages_after_marker = message_filter.process_new_messages_marker(messages, log_prefix="监听器")

        # 再过滤掉self和time类型的消息
        filtered_messages = message_filter.filter_messages(messages_after_marker, log_prefix="监听器")

        return filtered_messages

    async def add_listener(self, instance_id: str, who: str, **kwargs) -> bool:
        """
        添加监听对象

        Args:
            instance_id: 实例ID
            who: 监听对象的标识
            **kwargs: 其他参数

        Returns:
            bool: 是否添加成功
        """
        async with self._lock:
            # 初始化实例的监听字典
            if instance_id not in self.listeners:
                self.listeners[instance_id] = {}

            # 如果已经在监听列表中，更新时间
            if who in self.listeners[instance_id]:
                self.listeners[instance_id][who].last_message_time = time.time()
                self.listeners[instance_id][who].active = True
                return True

            # 检查是否超过最大监听数量
            if len(self.listeners[instance_id]) >= self.max_listeners_per_instance:
                logger.warning(f"实例 {instance_id} 监听对象数量已达到上限 ({self.max_listeners_per_instance})")
                return False

            # 获取API客户端
            api_client = instance_manager.get_instance(instance_id)
            if not api_client:
                logger.error(f"找不到实例 {instance_id} 的API客户端")
                return False

            # 调用API添加监听
            api_success = await api_client.add_listener(who, **kwargs)
            if not api_success:
                return False

            # 添加到内存中的监听列表
            self.listeners[instance_id][who] = ListenerInfo(
                instance_id=instance_id,
                who=who,
                last_message_time=time.time(),
                last_check_time=time.time()
            )

            # 添加到数据库
            await self._save_listener(instance_id, who)

            logger.info(f"成功添加实例 {instance_id} 的监听对象: {who}")
            return True

    async def remove_listener(self, instance_id: str, who: str):
        """
        移除监听对象

        Args:
            instance_id: 实例ID
            who: 监听对象的标识

        Returns:
            bool: 是否移除成功
        """
        async with self._lock:
            if instance_id not in self.listeners or who not in self.listeners[instance_id]:
                return False

            # 获取API客户端
            api_client = instance_manager.get_instance(instance_id)
            if not api_client:
                logger.error(f"找不到实例 {instance_id} 的API客户端")
                return False

            try:
                # 调用API客户端的移除监听方法
                api_success = await api_client.remove_listener(who)

                # 无论API调用成功与否，都尝试清理本地数据
                try:
                    # 从内存中移除
                    if instance_id in self.listeners and who in self.listeners[instance_id]:
                        del self.listeners[instance_id][who]
                        logger.info(f"从内存中移除监听对象: {instance_id} - {who}")

                    # 从数据库中移除
                    db_success = await self._remove_listener_from_db(instance_id, who)
                    if db_success:
                        logger.info(f"从数据库中移除监听对象: {instance_id} - {who}")
                    else:
                        logger.error(f"从数据库中移除监听对象失败: {instance_id} - {who}")
                except Exception as e:
                    logger.error(f"清理监听对象本地数据时出错: {e}")
                    logger.exception(e)

                # 只要完成了本地清理，就认为移除成功
                logger.info(f"已移除实例 {instance_id} 的监听对象: {who}")
                return True

            except Exception as e:
                logger.error(f"移除监听对象时出错: {e}")
                logger.exception(e)  # 记录完整堆栈
                return False

    async def _remove_inactive_listeners(self) -> int:
        """
        清理所有实例中的不活跃监听对象

        Returns:
            int: 清理的监听对象数量
        """
        removed_count = 0
        current_time = time.time()
        timeout = self.timeout_minutes * 60
        pending_check = []

        # 第一阶段：收集可能需要移除的监听对象
        async with self._lock:
            for instance_id in list(self.listeners.keys()):
                for who, info in list(self.listeners[instance_id].items()):
                    # 检查是否超时
                    if current_time - info.last_message_time > timeout:
                        # 如果已经标记为不活跃，直接准备移除
                        if not info.active:
                            logger.debug(f"监听对象已标记为不活跃: {instance_id} - {who}")
                            pending_check.append((instance_id, who, False))  # 不需要再次检查
                        else:
                            # 标记为需要检查
                            logger.debug(f"监听对象可能超时，将检查最新消息: {instance_id} - {who}")
                            pending_check.append((instance_id, who, True))  # 需要检查最新消息

        # 第二阶段：处理需要检查的监听对象
        for instance_id, who, need_check in pending_check:
            try:
                if need_check:
                    # 获取API客户端
                    api_client = instance_manager.get_instance(instance_id)
                    if not api_client:
                        logger.error(f"找不到实例 {instance_id} 的API客户端")
                        continue

                    # 尝试获取最新消息
                    logger.info(f"在移除前检查监听对象最新消息: {instance_id} - {who}")
                    messages = await api_client.get_listener_messages(who)

                    if messages:
                        # 如果有新消息，更新时间戳并跳过移除
                        logger.info(f"监听对象 {who} 有 {len(messages)} 条新消息，不移除")

                        async with self._lock:
                            if instance_id in self.listeners and who in self.listeners[instance_id]:
                                # 更新内存中的时间戳
                                self.listeners[instance_id][who].last_message_time = time.time()
                                self.listeners[instance_id][who].last_check_time = time.time()

                                # 更新数据库中的时间戳
                                await self._update_listener_timestamp(instance_id, who)

                                # 处理消息
                                for msg in messages:
                                    # 在保存前检查消息是否应该被过滤
                                    from wxauto_mgt.core.message_filter import message_filter

                                    save_data = {
                                        'instance_id': instance_id,
                                        'chat_name': who,
                                        'message_type': msg.get('type', 'text'),
                                        'content': msg.get('content', ''),
                                        'sender': msg.get('sender', ''),
                                        'sender_remark': msg.get('sender_remark', ''),
                                        'message_id': msg.get('id', ''),
                                        'mtype': msg.get('mtype', 0)
                                    }

                                    # 直接检查sender是否为self
                                    sender = msg.get('sender', '')
                                    if sender and (sender.lower() == 'self' or sender == 'Self'):
                                        logger.debug(f"过滤掉self发送的超时检查消息: {msg.get('id')}")
                                        continue

                                    # 使用消息过滤模块进行二次检查
                                    if message_filter.should_filter_message(save_data, log_prefix="超时检查保存前"):
                                        logger.debug(f"消息过滤模块过滤掉超时检查消息: {msg.get('id')}")
                                        continue

                                    # 保存到数据库
                                    await self._save_message(save_data)

                        continue  # 跳过移除步骤

                # 执行移除操作并检查结果
                success = await self.remove_listener(instance_id, who)
                if success:
                    removed_count += 1
                    logger.info(f"已移除超时的监听对象: {instance_id} - {who}")
                else:
                    logger.error(f"移除超时监听对象失败: {instance_id} - {who}")
            except Exception as e:
                logger.error(f"处理超时监听对象时出错: {e}")
                logger.exception(e)

        if removed_count > 0:
            logger.info(f"已清理 {removed_count} 个不活跃的监听对象")

        return removed_count

    async def _save_message(self, message_data: dict) -> bool:
        """
        保存消息到数据库

        Args:
            message_data: 消息数据

        Returns:
            bool: 是否保存成功
        """
        try:
            # 直接检查sender是否为self（不区分大小写）
            sender = message_data.get('sender', '')
            if sender and (sender.lower() == 'self' or sender == 'Self'):
                logger.debug(f"_save_message直接过滤掉self发送的消息: {message_data.get('message_id', '')}")
                return True  # 返回True表示处理成功，只是不保存

            # 直接检查消息类型是否为self（不区分大小写）
            msg_type = message_data.get('message_type', '')
            if msg_type and (msg_type.lower() == 'self' or msg_type == 'Self'):
                logger.debug(f"_save_message直接过滤掉self类型的消息: {message_data.get('message_id', '')}")
                return True  # 返回True表示处理成功，只是不保存

            # 使用统一的消息过滤模块进行二次检查
            from wxauto_mgt.core.message_filter import message_filter

            # 检查消息是否应该被过滤
            if message_filter.should_filter_message(message_data, log_prefix="保存前"):
                return True  # 返回True表示处理成功，只是不保存

            # 确保包含create_time字段
            if 'create_time' not in message_data:
                message_data['create_time'] = int(time.time())

            # 记录要保存的消息信息，便于调试
            logger.debug(f"保存消息到数据库: ID={message_data.get('message_id', '')}, 发送者={message_data.get('sender', '')}, 类型={message_data.get('message_type', '')}")

            # 检查消息内容是否与最近的回复内容匹配，如果匹配则标记为已处理
            # 这是为了避免系统自己发送的回复消息被再次处理
            content = message_data.get('content', '')
            if content:
                try:
                    # 查询最近5分钟内的回复内容
                    five_minutes_ago = int(time.time()) - 300  # 5分钟 = 300秒
                    query = """
                    SELECT reply_content FROM messages
                    WHERE reply_status = 1 AND reply_time > ?
                    ORDER BY reply_time DESC LIMIT 10
                    """
                    recent_replies = await db_manager.fetchall(query, (five_minutes_ago,))

                    # 检查当前消息内容是否与最近的回复内容匹配
                    for reply in recent_replies:
                        reply_content = reply.get('reply_content', '')
                        if reply_content and content == reply_content:
                            logger.info(f"检测到消息内容与最近回复匹配，标记为已处理: {message_data.get('message_id', '')}")
                            # 插入消息但标记为已处理
                            message_data['processed'] = 1
                            break
                except Exception as e:
                    logger.error(f"检查回复匹配时出错: {e}")

            # 插入消息到数据库
            await db_manager.insert('messages', message_data)
            return True
        except Exception as e:
            logger.error(f"保存消息到数据库失败: {e}")
            return False

    async def _save_listener(self, instance_id: str, who: str) -> bool:
        """
        保存监听对象到数据库

        Args:
            instance_id: 实例ID
            who: 监听对象的标识

        Returns:
            bool: 是否保存成功
        """
        try:
            current_time = int(time.time())
            data = {
                'instance_id': instance_id,
                'who': who,
                'last_message_time': current_time,
                'create_time': current_time
            }

            # 先检查是否已存在
            query = "SELECT id FROM listeners WHERE instance_id = ? AND who = ?"
            exists = await db_manager.fetchone(query, (instance_id, who))

            if exists:
                # 已存在，执行更新操作
                update_query = "UPDATE listeners SET last_message_time = ? WHERE instance_id = ? AND who = ?"
                await db_manager.execute(update_query, (current_time, instance_id, who))
                logger.debug(f"更新监听对象: {instance_id} - {who}")
            else:
                # 不存在，插入新记录
                await db_manager.insert('listeners', data)
                logger.debug(f"插入监听对象: {instance_id} - {who}")

            return True
        except Exception as e:
            logger.error(f"保存监听对象到数据库失败: {e}")
            return False

    async def _remove_listener_from_db(self, instance_id: str, who: str) -> bool:
        """
        从数据库中移除监听对象

        Args:
            instance_id: 实例ID
            who: 监听对象的标识

        Returns:
            bool: 是否移除成功
        """
        try:
            sql = "DELETE FROM listeners WHERE instance_id = ? AND who = ?"
            logger.debug(f"执行SQL: {sql} 参数: ({instance_id}, {who})")

            # 执行SQL并检查结果
            result = await db_manager.execute(sql, (instance_id, who))

            # 验证是否删除成功
            verify_sql = "SELECT COUNT(*) as count FROM listeners WHERE instance_id = ? AND who = ?"
            verify_result = await db_manager.fetchone(verify_sql, (instance_id, who))

            if verify_result and verify_result.get('count', 0) == 0:
                logger.debug(f"数据库记录已删除: {instance_id} - {who}")
                return True
            else:
                logger.warning(f"数据库记录可能未删除: {instance_id} - {who}, 验证结果: {verify_result}")
                # 如果验证失败，再次尝试强制删除
                force_sql = "DELETE FROM listeners WHERE instance_id = ? AND who = ?"
                await db_manager.execute(force_sql, (instance_id, who))
                logger.debug(f"已强制执行二次删除操作")
                return True
        except Exception as e:
            logger.error(f"从数据库移除监听对象失败: {e}")
            logger.exception(e)  # 记录完整堆栈
            return False

    def get_active_listeners(self, instance_id: str = None) -> Dict[str, List[str]]:
        """
        获取活跃的监听对象列表

        Args:
            instance_id: 可选的实例ID，如果提供则只返回该实例的监听对象

        Returns:
            Dict[str, List[str]]: 实例ID到监听对象列表的映射
        """
        result = {}
        if instance_id:
            if instance_id in self.listeners:
                result[instance_id] = [
                    who for who, info in self.listeners[instance_id].items()
                    if info.active
                ]
        else:
            for inst_id, listeners in self.listeners.items():
                result[inst_id] = [
                    who for who, info in listeners.items()
                    if info.active
                ]
        return result

    async def _load_listeners_from_db(self):
        """从数据库加载保存的监听对象"""
        try:
            logger.info("从数据库加载监听对象")

            # 查询所有监听对象
            query = "SELECT instance_id, who, last_message_time FROM listeners"
            listeners = await db_manager.fetchall(query)

            if not listeners:
                logger.info("数据库中没有监听对象")
                return

            # 加载到内存
            async with self._lock:
                for listener in listeners:
                    instance_id = listener.get('instance_id')
                    who = listener.get('who')
                    last_message_time = listener.get('last_message_time', time.time())

                    # 跳过无效记录
                    if not instance_id or not who:
                        continue

                    # 初始化实例的监听字典
                    if instance_id not in self.listeners:
                        self.listeners[instance_id] = {}

                    # 添加监听对象
                    self.listeners[instance_id][who] = ListenerInfo(
                        instance_id=instance_id,
                        who=who,
                        last_message_time=float(last_message_time),
                        last_check_time=time.time()
                    )

            # 计算加载的监听对象数量
            total = sum(len(listeners) for listeners in self.listeners.values())
            logger.info(f"从数据库加载了 {total} 个监听对象")

            # 注意：超时对象的处理已移至start方法的_refresh_all_listeners中

        except Exception as e:
            logger.error(f"从数据库加载监听对象时出错: {e}")
            logger.exception(e)
            # 出错时也要确保监听器字典被初始化
            self.listeners = {}

    async def _refresh_potentially_expired_listeners(self, potentially_expired):
        """
        刷新可能已超时的监听对象的消息

        Args:
            potentially_expired: 可能已超时的监听对象列表，每项为 (instance_id, who) 元组
        """
        logger.info(f"开始刷新 {len(potentially_expired)} 个可能超时的监听对象")

        for instance_id, who in potentially_expired:
            try:
                # 获取API客户端
                api_client = instance_manager.get_instance(instance_id)
                if not api_client:
                    logger.error(f"找不到实例 {instance_id} 的API客户端")
                    continue

                # 首先检查监听对象是否有效（例如尝试初始化验证）
                logger.info(f"验证监听对象是否有效: {instance_id} - {who}")

                # 添加一个移除再添加的验证步骤，确保监听对象在API端仍然有效
                try:
                    # 先尝试移除（如果存在）
                    logger.debug(f"尝试重置监听对象: 先移除 {instance_id} - {who}")
                    remove_result = await api_client.remove_listener(who)
                    logger.debug(f"移除结果: {remove_result}")

                    # 再重新添加
                    logger.debug(f"尝试重新添加监听对象: {instance_id} - {who}")
                    add_success = await api_client.add_listener(who)

                    if add_success:
                        logger.info(f"监听对象验证成功，已重置: {instance_id} - {who}")
                        # 更新时间戳
                        async with self._lock:
                            if instance_id in self.listeners and who in self.listeners[instance_id]:
                                self.listeners[instance_id][who].last_message_time = time.time()
                                self.listeners[instance_id][who].last_check_time = time.time()
                                # 更新数据库
                                await self._update_listener_timestamp(instance_id, who)
                                logger.debug(f"已更新监听对象时间戳: {instance_id} - {who}")
                        # 跳过后续处理，不需要再获取消息
                        continue
                    else:
                        logger.warning(f"监听对象验证失败，无法添加: {instance_id} - {who}")
                except Exception as e:
                    logger.error(f"监听对象验证时出错: {e}")
                    logger.exception(e)

                # 尝试获取该监听对象的最新消息
                logger.info(f"尝试获取可能已超时的监听对象消息: {instance_id} - {who}")
                messages = await api_client.get_listener_messages(who)

                if messages:
                    # 如果获取到消息，更新最后消息时间
                    logger.info(f"监听对象 {who} 有 {len(messages)} 条新消息，更新最后消息时间")

                    async with self._lock:
                        if instance_id in self.listeners and who in self.listeners[instance_id]:
                            self.listeners[instance_id][who].last_message_time = time.time()
                            self.listeners[instance_id][who].last_check_time = time.time()

                            # 更新数据库中的时间戳
                            await self._update_listener_timestamp(instance_id, who)
                            logger.debug(f"已更新监听对象时间戳: {instance_id} - {who}")

                            # 处理消息
                            logger.debug(f"开始处理 {len(messages)} 条消息并保存到数据库")
                            for msg in messages:
                                # 在保存前检查消息是否应该被过滤
                                from wxauto_mgt.core.message_filter import message_filter

                                save_data = {
                                    'instance_id': instance_id,
                                    'chat_name': who,
                                    'message_type': msg.get('type', 'text'),
                                    'content': msg.get('content', ''),
                                    'sender': msg.get('sender', ''),
                                    'sender_remark': msg.get('sender_remark', ''),
                                    'message_id': msg.get('id', ''),
                                    'mtype': msg.get('mtype', 0)
                                }

                                # 直接检查sender是否为self
                                sender = msg.get('sender', '')
                                if sender and (sender.lower() == 'self' or sender == 'Self'):
                                    logger.debug(f"过滤掉self发送的刷新消息: {msg.get('id')}")
                                    continue

                                # 使用消息过滤模块进行二次检查
                                if message_filter.should_filter_message(save_data, log_prefix="刷新保存前"):
                                    logger.debug(f"消息过滤模块过滤掉刷新消息: {msg.get('id')}")
                                    continue

                                # 保存到数据库
                                await self._save_message(save_data)
                else:
                    # 没有消息，但我们已经验证了监听对象是有效的，也应该重置超时
                    logger.info(f"监听对象 {who} 没有新消息，但已验证有效，重置超时")
                    # 如果对象仍在监听列表中，更新时间戳
                    async with self._lock:
                        if instance_id in self.listeners and who in self.listeners[instance_id]:
                            # 将最后检查时间设为当前，但只将最后消息时间往后延一半超时时间
                            # 这样如果真的长时间没消息，最终还是会超时，但有更多缓冲时间
                            buffer_time = self.timeout_minutes * 30  # 半个超时时间(秒)
                            self.listeners[instance_id][who].last_message_time = time.time() - buffer_time
                            self.listeners[instance_id][who].last_check_time = time.time()

                            # 更新数据库
                            await self._update_listener_timestamp(instance_id, who)
                            logger.debug(f"已延长监听对象超时时间: {instance_id} - {who}")

            except Exception as e:
                logger.error(f"刷新监听对象 {who} 消息时出错: {e}")
                logger.exception(e)

        logger.info(f"已完成所有可能超时监听对象的刷新")

    async def _update_listener_timestamp(self, instance_id: str, who: str) -> bool:
        """
        更新数据库中监听对象的时间戳

        Args:
            instance_id: 实例ID
            who: 监听对象的标识

        Returns:
            bool: 是否更新成功
        """
        try:
            current_time = int(time.time())
            update_query = "UPDATE listeners SET last_message_time = ? WHERE instance_id = ? AND who = ?"
            await db_manager.execute(update_query, (current_time, instance_id, who))
            logger.debug(f"已更新监听对象时间戳: {instance_id} - {who}")
            return True
        except Exception as e:
            logger.error(f"更新监听对象时间戳失败: {e}")
            return False

    async def _refresh_all_listeners(self):
        """在启动时刷新所有监听对象"""
        # 首先确保所有API实例已初始化
        logger.info("检查API实例初始化状态")
        for instance_id in self.listeners.keys():
            api_client = instance_manager.get_instance(instance_id)
            if not api_client:
                logger.error(f"找不到实例 {instance_id} 的API客户端")
                continue

            # 确保API客户端已初始化
            if not api_client.initialized:
                try:
                    logger.info(f"正在初始化API实例: {instance_id}")
                    init_result = await api_client.initialize()
                    if init_result:
                        logger.info(f"API实例初始化成功: {instance_id}")
                    else:
                        logger.error(f"API实例初始化失败: {instance_id}")
                except Exception as e:
                    logger.error(f"初始化API实例时出错: {e}")

        # 为所有监听对象标记为已在启动时处理，提供宽限期
        logger.info("为所有监听对象提供启动宽限期，标记为已处理")
        async with self._lock:
            for instance_id, listeners_dict in self.listeners.items():
                for who, info in listeners_dict.items():
                    # 设置所有监听对象为已处理状态
                    info.processed_at_startup = True
                    # 更新最后消息时间，提供一个缓冲时间
                    buffer_time = self.timeout_minutes * 30  # 半个超时时间(秒)
                    info.last_message_time = time.time() - buffer_time
                    logger.info(f"监听对象 {instance_id} - {who} 已设置启动宽限期")

        # 准备可能超时的监听对象列表
        potentially_expired = []
        current_time = time.time()
        timeout = self.timeout_minutes * 60

        logger.info("启动时识别可能已超时的监听对象")
        async with self._lock:
            for instance_id, listeners_dict in self.listeners.items():
                for who, info in listeners_dict.items():
                    # 检查最后消息时间
                    if current_time - info.last_message_time > timeout:
                        logger.info(f"启动时发现可能超时的监听对象: {instance_id} - {who}, 最后消息时间: {datetime.fromtimestamp(info.last_message_time).strftime('%Y-%m-%d %H:%M:%S')}")
                        potentially_expired.append((instance_id, who))
                    else:
                        logger.debug(f"监听对象正常: {instance_id} - {who}, 剩余时间: {int((info.last_message_time + timeout - current_time) / 60)} 分钟")

        if not potentially_expired:
            logger.info("未发现超时的监听对象，无需处理")
            return

        # 启动时强制刷新所有可能超时的监听对象
        logger.info(f"启动时处理 {len(potentially_expired)} 个可能超时的监听对象")
        for instance_id, who in potentially_expired:
            try:
                # 获取API客户端
                api_client = instance_manager.get_instance(instance_id)
                if not api_client:
                    logger.error(f"找不到实例 {instance_id} 的API客户端")
                    continue

                # 直接获取最新消息
                logger.info(f"启动时获取监听对象消息: {instance_id} - {who}")
                messages = await api_client.get_listener_messages(who)

                # 无论是否有消息，都标记为已在启动时处理过
                async with self._lock:
                    if instance_id in self.listeners and who in self.listeners[instance_id]:
                        self.listeners[instance_id][who].processed_at_startup = True

                if messages:
                    # 如果有新消息，更新时间戳
                    logger.info(f"监听对象 {who} 有 {len(messages)} 条新消息，重置超时")

                    async with self._lock:
                        if instance_id in self.listeners and who in self.listeners[instance_id]:
                            self.listeners[instance_id][who].last_message_time = time.time()
                            self.listeners[instance_id][who].last_check_time = time.time()
                            # 更新数据库中的时间戳
                            await self._update_listener_timestamp(instance_id, who)

                            # 处理消息
                            for msg in messages:
                                # 在保存前检查消息是否应该被过滤
                                from wxauto_mgt.core.message_filter import message_filter

                                save_data = {
                                    'instance_id': instance_id,
                                    'chat_name': who,
                                    'message_type': msg.get('type', 'text'),
                                    'content': msg.get('content', ''),
                                    'sender': msg.get('sender', ''),
                                    'sender_remark': msg.get('sender_remark', ''),
                                    'message_id': msg.get('id', ''),
                                    'mtype': msg.get('mtype', 0)
                                }

                                # 直接检查sender是否为self
                                sender = msg.get('sender', '')
                                if sender and (sender.lower() == 'self' or sender == 'Self'):
                                    logger.debug(f"过滤掉self发送的启动消息: {msg.get('id')}")
                                    continue

                                # 使用消息过滤模块进行二次检查
                                if message_filter.should_filter_message(save_data, log_prefix="启动保存前"):
                                    logger.debug(f"消息过滤模块过滤掉启动消息: {msg.get('id')}")
                                    continue

                                # 保存到数据库
                                await self._save_message(save_data)
                else:
                    # 无消息时，尝试重置监听对象
                    logger.info(f"监听对象 {who} 没有新消息，尝试重置")
                    try:
                        # 先移除
                        await api_client.remove_listener(who)
                        # 再添加
                        add_success = await api_client.add_listener(who)

                        if add_success:
                            logger.info(f"成功重置监听对象: {instance_id} - {who}")
                            # 延长超时时间
                            async with self._lock:
                                if instance_id in self.listeners and who in self.listeners[instance_id]:
                                    # 延长一半超时时间
                                    buffer_time = self.timeout_minutes * 30  # 半个超时时间(秒)
                                    self.listeners[instance_id][who].last_message_time = time.time() - buffer_time
                                    self.listeners[instance_id][who].last_check_time = time.time()
                                    await self._update_listener_timestamp(instance_id, who)
                        else:
                            logger.warning(f"无法重置监听对象: {instance_id} - {who}")
                    except Exception as e:
                        logger.error(f"重置监听对象出错: {e}")
                        logger.exception(e)

            except Exception as e:
                logger.error(f"启动时处理监听对象 {who} 时出错: {e}")
                logger.exception(e)

        logger.info("启动时监听对象处理完成")

# 创建全局实例
message_listener = MessageListener()