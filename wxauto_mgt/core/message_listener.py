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
from wxauto_mgt.core.config_notifier import config_notifier, ConfigChangeEvent
from wxauto_mgt.core.service_monitor import service_monitor

# 配置日志 - 使用主日志记录器，确保所有日志都记录到主日志文件
logger = logging.getLogger('wxauto_mgt')
# 设置为DEBUG级别，确保捕获所有详细日志
logger.setLevel(logging.DEBUG)

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
    conversation_id: str = ""  # Dify会话ID
    manual_added: bool = False  # 是否为手动添加的监听对象（不受超时限制）
    fixed_listener: bool = False  # 是否为固定监听对象（不受超时限制且自动添加）

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

        # 添加暂停监听的锁和状态
        self._paused = False
        self._pause_lock = asyncio.Lock()
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # 初始状态为未暂停

        # 启动时间戳，用于提供宽限期
        self.startup_timestamp = 0

        # 配置变更监听标志
        self._config_listeners_registered = False

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

        # 加载固定监听配置并自动添加到监听列表
        logger.info("🔧 准备加载固定监听配置...")
        await self._load_and_apply_fixed_listeners()
        logger.info("🔧 固定监听配置加载完成")

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

        # 注册配置变更监听器
        await self._register_config_listeners()

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

        # 注销配置变更监听器
        await self._unregister_config_listeners()

        # 取消所有任务
        for task in self._tasks:
            task.cancel()

        # 等待所有任务完成
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    async def pause_listening(self):
        """暂停消息监听服务"""
        async with self._pause_lock:
            if not self._paused:
                logger.info("暂停消息监听服务")
                self._paused = True
                self._pause_event.clear()

    async def resume_listening(self):
        """恢复消息监听服务"""
        async with self._pause_lock:
            if self._paused:
                logger.info("恢复消息监听服务")
                self._paused = False
                self._pause_event.set()

    async def _internal_pause_listening(self):
        """内部暂停监听（不影响用户设置的暂停状态）"""
        # 这个方法用于内部操作时的临时暂停，不会改变用户设置的暂停状态
        pass

    async def _internal_resume_listening(self):
        """内部恢复监听（不影响用户设置的暂停状态）"""
        # 这个方法用于内部操作时的临时恢复，不会改变用户设置的暂停状态
        pass

    async def wait_if_paused(self):
        """如果监听服务被暂停，则等待恢复"""
        await self._pause_event.wait()

    async def _main_window_check_loop(self):
        """主窗口未读消息检查循环"""
        consecutive_errors = 0
        max_consecutive_errors = 5

        while self.running:
            try:
                # 检查是否暂停
                await self.wait_if_paused()

                # 获取所有活跃实例
                instances = instance_manager.get_all_instances()
                for instance_id, api_client in instances.items():
                    # 再次检查是否暂停（每个实例处理前）
                    await self.wait_if_paused()

                    # 检查API客户端连接状态
                    if not await self._check_api_client_health(instance_id, api_client):
                        logger.warning(f"实例 {instance_id} API客户端连接异常，跳过本次检查")
                        continue

                    await self.check_main_window_messages(instance_id, api_client)

                # 重置错误计数
                consecutive_errors = 0
                await asyncio.sleep(self.poll_interval)

            except asyncio.CancelledError:
                logger.info("主窗口检查循环被取消")
                break
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"检查主窗口消息时出错 (连续错误: {consecutive_errors}/{max_consecutive_errors}): {e}")
                logger.exception(e)

                # 记录错误到监控系统
                service_monitor.record_error("message_listener", f"主窗口检查错误: {e}", "main_window_check")

                # 如果连续错误过多，增加等待时间
                if consecutive_errors >= max_consecutive_errors:
                    logger.warning(f"主窗口检查连续出错 {consecutive_errors} 次，延长等待时间")
                    await asyncio.sleep(self.poll_interval * 3)
                else:
                    await asyncio.sleep(self.poll_interval)

    async def _listeners_check_loop(self):
        """监听对象消息检查循环"""
        consecutive_errors = 0
        max_consecutive_errors = 5

        while self.running:
            try:
                # 检查是否暂停
                await self.wait_if_paused()

                # 获取所有活跃实例
                instances = instance_manager.get_all_instances()
                for instance_id, api_client in instances.items():
                    # 再次检查是否暂停（每个实例处理前）
                    await self.wait_if_paused()

                    # 检查API客户端连接状态
                    if not await self._check_api_client_health(instance_id, api_client):
                        logger.warning(f"实例 {instance_id} API客户端连接异常，跳过本次检查")
                        continue

                    await self.check_listener_messages(instance_id, api_client)

                # 重置错误计数
                consecutive_errors = 0
                await asyncio.sleep(self.poll_interval)

            except asyncio.CancelledError:
                logger.info("监听对象检查循环被取消")
                break
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"检查监听对象消息时出错 (连续错误: {consecutive_errors}/{max_consecutive_errors}): {e}")
                logger.exception(e)

                # 记录错误到监控系统
                service_monitor.record_error("message_listener", f"监听对象检查错误: {e}", "listener_check")

                # 如果连续错误过多，增加等待时间
                if consecutive_errors >= max_consecutive_errors:
                    logger.warning(f"监听对象检查连续出错 {consecutive_errors} 次，延长等待时间")
                    await asyncio.sleep(self.poll_interval * 3)
                else:
                    await asyncio.sleep(self.poll_interval)

    async def _cleanup_loop(self):
        """清理过期监听对象循环"""
        consecutive_errors = 0
        max_consecutive_errors = 3

        while self.running:
            try:
                # 检查是否暂停
                await self.wait_if_paused()

                await self._remove_inactive_listeners()

                # 重置错误计数
                consecutive_errors = 0
                await asyncio.sleep(60)  # 每分钟检查一次

            except asyncio.CancelledError:
                logger.info("清理循环被取消")
                break
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"清理过期监听对象时出错 (连续错误: {consecutive_errors}/{max_consecutive_errors}): {e}")
                logger.exception(e)

                # 记录错误到监控系统
                service_monitor.record_error("message_listener", f"清理任务错误: {e}", "cleanup")

                # 如果连续错误过多，增加等待时间
                if consecutive_errors >= max_consecutive_errors:
                    logger.warning(f"清理任务连续出错 {consecutive_errors} 次，延长等待时间")
                    await asyncio.sleep(180)  # 等待3分钟
                else:
                    await asyncio.sleep(60)

    async def check_main_window_messages(self, instance_id: str, api_client):
        """
        检查指定实例主窗口未读消息

        Args:
            instance_id: 实例ID
            api_client: API客户端实例
        """
        try:
            # 获取主窗口未读消息，设置接收图片、文件、语音信息、URL信息参数为True
            messages = await api_client.get_unread_messages(
                save_pic=True,
                save_video=False,
                save_file=True,
                save_voice=True,
                parse_url=True
            )
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
                    # 在保存前再次检查消息是否应该被过滤
                    # 特别是检查sender是否为self
                    from wxauto_mgt.core.message_filter import message_filter

                    # 直接检查sender是否为self
                    sender = msg.get('sender', '')
                    if sender and (sender.lower() == 'self' or sender == 'Self'):
                        logger.debug(f"过滤掉self发送的主窗口消息: {msg.get('id')}")
                        continue

                    # 处理不同类型的消息
                    from wxauto_mgt.core.message_processor import message_processor

                    # 根据消息类型进行预处理
                    mtype = msg.get('mtype', '')
                    content = msg.get('content', '')

                    # 处理卡片类型消息
                    if mtype == 'card':
                        # 移除[wxauto卡片链接解析]前缀
                        msg['content'] = content.replace('[wxauto卡片链接解析]', '').strip()
                        logger.info(f"预处理主窗口卡片消息: {msg.get('id')}, 移除前缀")

                    # 处理语音类型消息
                    elif mtype == 'voice':
                        # 移除[wxauto语音解析]前缀
                        msg['content'] = content.replace('[wxauto语音解析]', '').strip()
                        logger.info(f"预处理主窗口语音消息: {msg.get('id')}, 移除前缀")

                    # 处理图片或文件类型消息
                    elif mtype in ['image', 'file']:
                        # 提取文件路径
                        import re
                        path_pattern = r'([A-Za-z]:\\(?:[^\\/:*?"<>|\r\n]+\\)*[^\\/:*?"<>|\r\n]*)'
                        match = re.search(path_pattern, content)
                        if match:
                            file_path = match.group(1)
                            logger.info(f"预处理主窗口{mtype}消息: {msg.get('id')}, 提取文件路径: {file_path}")

                    # 处理不同类型的消息
                    processed_msg = await message_processor.process_message(msg, api_client)

                    # 将发送者添加到监听列表 - 这是关键步骤
                    # 设置接收图片、文件、语音信息、URL信息参数为True
                    add_success = await self.add_listener(
                        instance_id,
                        chat_name,
                        conversation_id="",  # 初始时会话ID为空
                        save_pic=True,
                        save_file=True,
                        save_voice=True,
                        parse_url=True
                    )

                    logger.info(f"主窗口消息处理：添加监听对象 {chat_name} 结果: {add_success}")

                    # 只有成功添加监听对象后，才保存消息到数据库
                    if add_success:
                        # 保存消息到数据库
                        save_data = {
                            'instance_id': instance_id,
                            'chat_name': chat_name,
                            'message_type': processed_msg.get('type'),
                            'content': processed_msg.get('content'),
                            'sender': processed_msg.get('sender'),
                            'sender_remark': processed_msg.get('sender_remark'),
                            'message_id': processed_msg.get('id'),
                            'mtype': processed_msg.get('mtype')
                        }

                        # 如果是文件或图片，添加本地文件路径和文件类型
                        if 'local_file_path' in processed_msg:
                            save_data['local_file_path'] = processed_msg.get('local_file_path')
                            save_data['file_size'] = processed_msg.get('file_size')
                            save_data['original_file_path'] = processed_msg.get('original_file_path')
                            if 'file_type' in processed_msg:
                                save_data['file_type'] = processed_msg.get('file_type')

                        # 使用消息过滤模块进行二次检查
                        if message_filter.should_filter_message(save_data, log_prefix="主窗口保存前"):
                            logger.debug(f"消息过滤模块过滤掉主窗口消息: {msg.get('id')}")
                            continue

                        logger.debug(f"准备保存主窗口消息: {save_data}")
                        message_id = await self._save_message(save_data)

                        # 记录消息处理统计
                        if message_id:
                            service_monitor.record_message_processed()

                        # 直接处理消息投递和回复 - 新增部分
                        if message_id:
                            try:
                                # 导入消息投递服务
                                from wxauto_mgt.core.message_delivery_service import message_delivery_service

                                # 获取保存的消息
                                from wxauto_mgt.data.db_manager import db_manager
                                saved_message = await db_manager.fetchone(
                                    "SELECT * FROM messages WHERE message_id = ?",
                                    (processed_msg.get('id'),)
                                )

                                if saved_message:
                                    # 直接处理消息投递
                                    logger.info(f"主窗口消息直接投递处理: {processed_msg.get('id')}")
                                    # 创建异步任务处理消息，并等待处理完成
                                    try:
                                        # 直接等待处理完成，确保回复能发送回微信
                                        delivery_result = await message_delivery_service.process_message(saved_message)
                                        logger.info(f"主窗口消息投递处理完成: {processed_msg.get('id')}, 结果: {delivery_result}")
                                    except Exception as delivery_e:
                                        logger.error(f"主窗口消息投递处理异常: {delivery_e}")
                                        logger.exception(delivery_e)
                                else:
                                    logger.error(f"无法找到保存的消息: {processed_msg.get('id')}")
                            except Exception as e:
                                logger.error(f"主窗口消息投递处理失败: {e}")
                                logger.exception(e)
                    else:
                        logger.error(f"添加监听对象 {chat_name} 失败，跳过保存消息: {msg.get('id')}")
                        # 不保存消息，因为没有成功添加监听对象

        except Exception as e:
            logger.error(f"处理实例 {instance_id} 主窗口消息时出错: {e}")
            logger.exception(e)

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

            try:
                # 获取所有监听对象的新消息
                logger.debug(f"开始获取实例 {instance_id} 所有监听对象的新消息")
                all_messages = await api_client.get_all_listener_messages()

                if not all_messages:
                    logger.debug(f"实例 {instance_id} 没有任何监听对象的新消息")
                    return

                # 处理每个监听对象的消息
                for who, messages in all_messages.items():
                    # 检查这个监听对象是否在我们的监听列表中
                    if who not in self.listeners[instance_id]:
                        logger.debug(f"收到未监听对象 {who} 的消息，跳过处理")
                        continue

                    info = self.listeners[instance_id][who]
                    if not info.active:
                        logger.debug(f"监听对象 {who} 不活跃，跳过处理")
                        continue

                    if messages:
                        # 更新最后消息时间
                        info.last_message_time = time.time()

                        # 处理消息：筛选掉"以下为新消息"及之前的消息
                        filtered_messages = self._filter_messages(messages)
                        logger.debug(f"监听对象 {who} 过滤后剩余 {len(filtered_messages)} 条新消息")

                        # 记录详细的消息信息，包括会话名称、发送人和内容
                        # 只记录第一条过滤后的消息，避免日志过多
                        if filtered_messages:
                            msg = filtered_messages[0]
                            sender = msg.get('sender', '未知')
                            sender_remark = msg.get('sender_remark', '')
                            content = msg.get('content', '')
                            # 使用发送者备注名(如果有)，否则使用发送者ID
                            display_sender = sender_remark if sender_remark else sender
                            # 截断内容，避免日志过长
                            short_content = content[:50] + "..." if len(content) > 50 else content

                            # 检查消息是否符合@规则
                            from wxauto_mgt.core.message_filter import message_filter
                            from wxauto_mgt.core.service_platform_manager import rule_manager

                            # 获取匹配的规则
                            rule = await rule_manager.match_rule(instance_id, who, content)

                            # 检查是否需要@规则过滤
                            is_at_rule_filtered = False
                            if rule:
                                # 获取规则ID，但不使用它，只是为了避免IDE警告
                                _ = rule.get('rule_id', '未知')
                                only_at_messages = rule.get('only_at_messages', 0)

                                if only_at_messages == 1:
                                    at_name = rule.get('at_name', '')
                                    if at_name:
                                        # 支持多个@名称，用逗号分隔
                                        at_names = [name.strip() for name in at_name.split(',')]

                                        # 检查消息是否包含任意一个@名称
                                        at_match = False
                                        for name in at_names:
                                            if name and f"@{name}" in content:
                                                at_match = True
                                                break

                                        # 如果没有匹配到任何@名称，标记为不符合规则
                                        if not at_match:
                                            is_at_rule_filtered = True

                            # 根据是否符合@规则记录不同的日志 - 只记录一条日志
                            if is_at_rule_filtered:
                                # 只记录一条带有[不符合消息转发规则]标记的日志
                                logger.info(f"监控到来自于会话\"{who}\"，发送人是\"{display_sender}\"的新消息，内容：\"{short_content}\" [不符合消息转发规则]")

                                # 重要：将这条消息从filtered_messages中移除，避免后续处理
                                filtered_messages.remove(msg)
                            else:
                                logger.info(f"获取到新消息: 实例={instance_id}, 聊天={who}, 发送者={display_sender}, 内容={short_content}")

                        # 保存消息到数据库
                        for msg in filtered_messages:
                            # 在保存前再次检查消息是否应该被过滤
                            # 特别是检查sender是否为self
                            from wxauto_mgt.core.message_filter import message_filter

                            # 直接检查sender是否为self
                            sender = msg.get('sender', '')
                            if sender and (sender.lower() == 'self' or sender == 'Self'):
                                logger.debug(f"过滤掉self发送的消息: {msg.get('id')}")
                                continue

                            # 根据消息类型进行预处理
                            mtype = msg.get('mtype', '')
                            content = msg.get('content', '')

                            # 处理卡片类型消息
                            if mtype == 'card':
                                # 移除[wxauto卡片链接解析]前缀
                                msg['content'] = content.replace('[wxauto卡片链接解析]', '').strip()
                                logger.info(f"预处理卡片消息: {msg.get('id')}, 移除前缀")

                            # 处理语音类型消息
                            elif mtype == 'voice':
                                # 移除[wxauto语音解析]前缀
                                msg['content'] = content.replace('[wxauto语音解析]', '').strip()
                                logger.info(f"预处理语音消息: {msg.get('id')}, 移除前缀")

                            # 处理图片或文件类型消息
                            elif mtype in ['image', 'file']:
                                # 提取文件路径
                                import re
                                path_pattern = r'([A-Za-z]:\\(?:[^\\/:*?"<>|\r\n]+\\)*[^\\/:*?"<>|\r\n]*)'
                                match = re.search(path_pattern, content)
                                if match:
                                    file_path = match.group(1)
                                    logger.info(f"预处理{mtype}消息: {msg.get('id')}, 提取文件路径: {file_path}")
                                    # 文件路径将在后续处理中下载

                            # 处理不同类型的消息
                            from wxauto_mgt.core.message_processor import message_processor

                            # 处理消息内容
                            processed_msg = await message_processor.process_message(msg, api_client)

                            # 保存消息到数据库
                            save_data = {
                                'instance_id': instance_id,
                                'chat_name': who,
                                'message_type': processed_msg.get('type'),
                                'content': processed_msg.get('content'),
                                'sender': processed_msg.get('sender'),
                                'sender_remark': processed_msg.get('sender_remark'),
                                'message_id': processed_msg.get('id'),
                                'mtype': processed_msg.get('mtype')
                            }

                            # 如果是文件或图片，添加本地文件路径和文件类型
                            if 'local_file_path' in processed_msg:
                                save_data['local_file_path'] = processed_msg.get('local_file_path')
                                save_data['file_size'] = processed_msg.get('file_size')
                                save_data['original_file_path'] = processed_msg.get('original_file_path')
                                if 'file_type' in processed_msg:
                                    save_data['file_type'] = processed_msg.get('file_type')

                            # 使用消息过滤模块进行二次检查
                            if message_filter.should_filter_message(save_data, log_prefix="监听器保存前"):
                                logger.debug(f"消息过滤模块过滤掉消息: {msg.get('id')}")
                                continue

                            logger.debug(f"准备保存监听消息: {save_data}")
                            message_id = await self._save_message(save_data)
                            if message_id:
                                logger.debug(f"监听消息保存成功，ID: {message_id}")
                                # 记录消息处理统计
                                service_monitor.record_message_processed()

                                # 直接处理消息投递和回复 - 与主窗口保持一致
                                try:
                                    # 导入消息投递服务
                                    from wxauto_mgt.core.message_delivery_service import message_delivery_service

                                    # 获取保存的消息
                                    from wxauto_mgt.data.db_manager import db_manager
                                    saved_message = await db_manager.fetchone(
                                        "SELECT * FROM messages WHERE message_id = ?",
                                        (processed_msg.get('id'),)
                                    )

                                    if saved_message:
                                        # 直接处理消息投递
                                        logger.info(f"监听窗口消息直接投递处理: {processed_msg.get('id')}")
                                        # 直接等待处理完成，确保回复能发送回微信
                                        try:
                                            delivery_result = await message_delivery_service.process_message(saved_message)
                                            logger.info(f"监听窗口消息投递处理完成: {processed_msg.get('id')}, 结果: {delivery_result}")
                                        except Exception as delivery_e:
                                            logger.error(f"监听窗口消息投递处理异常: {delivery_e}")
                                            logger.exception(delivery_e)
                                    else:
                                        logger.error(f"无法找到保存的消息: {processed_msg.get('id')}")
                                except Exception as e:
                                    logger.error(f"监听窗口消息投递处理失败: {e}")
                                    logger.exception(e)
                    else:
                        logger.debug(f"实例 {instance_id} 监听对象 {who} 没有新消息")

                    # 更新检查时间
                    info.last_check_time = time.time()

                # 更新所有监听对象的检查时间
                for who, info in self.listeners[instance_id].items():
                    if info.active:
                        info.last_check_time = time.time()

            except Exception as e:
                logger.error(f"检查实例 {instance_id} 所有监听对象的消息时出错: {e}")
                logger.debug(f"错误详情", exc_info=True)

    def _filter_messages(self, messages: List[dict]) -> List[dict]:
        """
        过滤消息列表，处理"以下为新消息"分隔符，并过滤掉self发送的消息、time类型的消息和base类型的消息

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

    async def has_listener(self, instance_id: str, who: str) -> bool:
        """
        检查监听对象是否存在

        Args:
            instance_id: 实例ID
            who: 监听对象的标识

        Returns:
            bool: 监听对象是否存在
        """
        async with self._lock:
            # 检查内存中是否存在
            if instance_id in self.listeners and who in self.listeners[instance_id]:
                return True

            # 检查数据库中是否存在
            try:
                query = "SELECT id FROM listeners WHERE instance_id = ? AND who = ?"
                result = await db_manager.fetchone(query, (instance_id, who))
                return result is not None
            except Exception as e:
                logger.error(f"检查监听对象是否存在时出错: {e}")
                return False

    async def add_listener(self, instance_id: str, who: str, conversation_id: str = "", manual_added: bool = False, fixed_listener: bool = False, **kwargs) -> bool:
        """
        添加监听对象

        Args:
            instance_id: 实例ID
            who: 监听对象的标识
            conversation_id: Dify会话ID，默认为空字符串
            manual_added: 是否为手动添加的监听对象（不受超时限制）
            fixed_listener: 是否为固定监听对象（不受超时限制且自动添加）
            **kwargs: 其他参数

        Returns:
            bool: 是否添加成功
        """
        async with self._lock:
            # 初始化实例的监听字典
            if instance_id not in self.listeners:
                self.listeners[instance_id] = {}

            # 如果已经在监听列表中，更新时间和会话ID（如果提供）
            if who in self.listeners[instance_id]:
                self.listeners[instance_id][who].last_message_time = time.time()
                self.listeners[instance_id][who].active = True

                # 更新手动添加标识
                if manual_added:
                    self.listeners[instance_id][who].manual_added = True
                    logger.info(f"监听对象 {who} 已标记为手动添加（不受超时限制）")

                # 更新固定监听标识
                if fixed_listener:
                    self.listeners[instance_id][who].fixed_listener = True
                    logger.info(f"监听对象 {who} 已标记为固定监听（不受超时限制）")

                # 如果提供了新的会话ID，更新会话ID
                if conversation_id:
                    self.listeners[instance_id][who].conversation_id = conversation_id
                    # 更新数据库中的会话ID
                    await self._save_listener(instance_id, who, conversation_id, manual_added)
                    logger.debug(f"更新监听对象会话ID: {instance_id} - {who} - {conversation_id}")

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

            try:
                # 调用API添加监听
                api_success = await api_client.add_listener(who, **kwargs)
            finally:
                pass
            if not api_success:
                return False

            # 添加到内存中的监听列表
            self.listeners[instance_id][who] = ListenerInfo(
                instance_id=instance_id,
                who=who,
                last_message_time=time.time(),
                last_check_time=time.time(),
                conversation_id=conversation_id,
                manual_added=manual_added,
                fixed_listener=fixed_listener
            )

            # 添加到数据库
            await self._save_listener(instance_id, who, conversation_id, manual_added)

            if fixed_listener:
                logger.info(f"成功添加固定监听对象（不受超时限制）: {instance_id} - {who}")
            elif manual_added:
                logger.info(f"成功添加手动监听对象（不受超时限制）: {instance_id} - {who}")
            else:
                logger.info(f"成功添加实例 {instance_id} 的监听对象: {who}")

            if conversation_id:
                logger.debug(f"监听对象已设置会话ID: {instance_id} - {who} - {conversation_id}")

            # 记录监听对象添加统计
            service_monitor.record_listener_added()

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
                try:
                    # 调用API客户端的移除监听方法
                    await api_client.remove_listener(who)
                finally:
                    pass
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

                # 记录监听对象移除统计
                service_monitor.record_listener_removed()

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
                    # 检查是否为手动添加的监听对象（不受超时限制）
                    if getattr(info, 'manual_added', False):
                        logger.debug(f"跳过手动添加的监听对象（不受超时限制）: {instance_id} - {who}")
                        continue

                    # 检查是否为固定监听对象（不受超时限制）
                    if getattr(info, 'fixed_listener', False):
                        logger.debug(f"跳过固定监听对象（不受超时限制）: {instance_id} - {who}")
                        continue

                    # 检查是否超时
                    if current_time - info.last_message_time > timeout:
                        # 如果已经标记为不活跃，跳过
                        if not info.active:
                            logger.debug(f"监听对象已标记为不活跃: {instance_id} - {who}")
                            continue
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
                        # 先过滤消息
                        filtered_messages = self._filter_messages(messages)

                        # 如果有新消息，更新时间戳并跳过移除
                        logger.info(f"监听对象 {who} 有 {len(messages)} 条新消息，过滤后剩余 {len(filtered_messages)} 条，不移除")

                        # 记录第一条过滤后的消息内容
                        if filtered_messages:
                            msg = filtered_messages[0]
                            sender = msg.get('sender', '未知')
                            sender_remark = msg.get('sender_remark', '')
                            content = msg.get('content', '')
                            # 使用发送者备注名(如果有)，否则使用发送者ID
                            display_sender = sender_remark if sender_remark else sender
                            # 截断内容，避免日志过长
                            short_content = content[:50] + "..." if len(content) > 50 else content

                            # 检查消息是否符合@规则
                            from wxauto_mgt.core.message_filter import message_filter
                            from wxauto_mgt.core.service_platform_manager import rule_manager

                            # 获取匹配的规则
                            rule = await rule_manager.match_rule(instance_id, who, content)

                            # 检查是否需要@规则过滤
                            is_at_rule_filtered = False
                            if rule:
                                # 获取规则ID，但不使用它，只是为了避免IDE警告
                                _ = rule.get('rule_id', '未知')
                                only_at_messages = rule.get('only_at_messages', 0)

                                if only_at_messages == 1:
                                    at_name = rule.get('at_name', '')
                                    if at_name:
                                        # 支持多个@名称，用逗号分隔
                                        at_names = [name.strip() for name in at_name.split(',')]

                                        # 检查消息是否包含任意一个@名称
                                        at_match = False
                                        for name in at_names:
                                            if name and f"@{name}" in content:
                                                at_match = True
                                                break

                                        # 如果没有匹配到任何@名称，标记为不符合规则
                                        if not at_match:
                                            is_at_rule_filtered = True

                            # 根据是否符合@规则记录不同的日志 - 只记录一条日志
                            if is_at_rule_filtered:
                                # 只记录一条带有[不符合消息转发规则]标记的日志
                                logger.info(f"监控到来自于会话\"{who}\"，发送人是\"{display_sender}\"的新消息，内容：\"{short_content}\" [不符合消息转发规则]")

                                # 重要：将这条消息从filtered_messages中移除，避免后续处理
                                filtered_messages.remove(msg)
                            else:
                                logger.info(f"获取到新消息: 实例={instance_id}, 聊天={who}, 发送者={display_sender}, 内容={short_content}")

                        async with self._lock:
                            if instance_id in self.listeners and who in self.listeners[instance_id]:
                                # 更新内存中的时间戳
                                self.listeners[instance_id][who].last_message_time = time.time()
                                self.listeners[instance_id][who].last_check_time = time.time()

                                # 更新数据库中的时间戳
                                await self._update_listener_timestamp(instance_id, who)

                                # 处理消息
                                for msg in filtered_messages:
                                    # 在保存前检查消息是否应该被过滤
                                    from wxauto_mgt.core.message_filter import message_filter

                                    # 直接检查sender是否为self
                                    sender = msg.get('sender', '')
                                    if sender and (sender.lower() == 'self' or sender == 'Self'):
                                        logger.debug(f"过滤掉self发送的超时检查消息: {msg.get('id')}")
                                        continue

                                    # 处理不同类型的消息
                                    from wxauto_mgt.core.message_processor import message_processor

                                    # 处理消息内容
                                    processed_msg = await message_processor.process_message(msg, api_client)

                                    # 保存消息到数据库
                                    save_data = {
                                        'instance_id': instance_id,
                                        'chat_name': who,
                                        'message_type': processed_msg.get('type', 'text'),
                                        'content': processed_msg.get('content', ''),
                                        'sender': processed_msg.get('sender', ''),
                                        'sender_remark': processed_msg.get('sender_remark', ''),
                                        'message_id': processed_msg.get('id', ''),
                                        'mtype': processed_msg.get('mtype', 0)
                                    }

                                    # 如果是文件或图片，添加本地文件路径
                                    if 'local_file_path' in processed_msg:
                                        save_data['local_file_path'] = processed_msg.get('local_file_path')
                                        save_data['file_size'] = processed_msg.get('file_size')
                                        save_data['original_file_path'] = processed_msg.get('original_file_path')

                                    # 使用消息过滤模块进行二次检查
                                    if message_filter.should_filter_message(save_data, log_prefix="超时检查保存前"):
                                        logger.debug(f"消息过滤模块过滤掉超时检查消息: {msg.get('id')}")
                                        continue

                                    # 保存到数据库
                                    message_id = await self._save_message(save_data)
                                    if message_id:
                                        logger.debug(f"超时检查消息保存成功，ID: {message_id}")

                                        # 直接处理消息投递和回复 - 与主窗口保持一致
                                        try:
                                            # 导入消息投递服务
                                            from wxauto_mgt.core.message_delivery_service import message_delivery_service

                                            # 获取保存的消息
                                            from wxauto_mgt.data.db_manager import db_manager
                                            saved_message = await db_manager.fetchone(
                                                "SELECT * FROM messages WHERE message_id = ?",
                                                (processed_msg.get('id'),)
                                            )

                                            if saved_message:
                                                # 直接处理消息投递
                                                logger.info(f"超时检查消息直接投递处理: {processed_msg.get('id')}")
                                                # 直接等待处理完成，确保回复能发送回微信
                                                try:
                                                    delivery_result = await message_delivery_service.process_message(saved_message)
                                                    logger.info(f"超时检查消息投递处理完成: {processed_msg.get('id')}, 结果: {delivery_result}")
                                                except Exception as delivery_e:
                                                    logger.error(f"超时检查消息投递处理异常: {delivery_e}")
                                                    logger.exception(delivery_e)
                                            else:
                                                logger.error(f"无法找到保存的消息: {processed_msg.get('id')}")
                                        except Exception as e:
                                            logger.error(f"超时检查消息投递处理失败: {e}")
                                            logger.exception(e)

                        continue  # 跳过移除步骤

                # 执行状态更新操作（标记为非活跃）
                success = await self._mark_listener_inactive(instance_id, who)
                if success:
                    removed_count += 1
                    logger.info(f"已标记超时的监听对象为非活跃: {instance_id} - {who}")
                else:
                    logger.error(f"标记超时监听对象为非活跃失败: {instance_id} - {who}")
            except Exception as e:
                logger.error(f"处理超时监听对象时出错: {e}")
                logger.exception(e)

        if removed_count > 0:
            logger.info(f"已标记 {removed_count} 个监听对象为非活跃")

        return removed_count

    async def _save_message(self, message_data: dict) -> str:
        """
        保存消息到数据库

        Args:
            message_data: 消息数据

        Returns:
            str: 保存成功返回消息ID，失败返回空字符串
        """
        try:
            message_id = message_data.get('message_id', '')
            instance_id = message_data.get('instance_id', '')
            chat_name = message_data.get('chat_name', '')
            content = message_data.get('content', '')

            # 记录详细的消息信息，便于调试
            logger.info(f"准备保存消息: ID={message_id}, 实例={instance_id}, 聊天={chat_name}, 内容={content[:50]}...")

            # 直接检查sender是否为self（不区分大小写）
            sender = message_data.get('sender', '')
            if sender and (sender.lower() == 'self' or sender == 'Self'):
                logger.info(f"_save_message直接过滤掉self发送的消息: {message_id}")
                return ""  # 返回空字符串表示消息被过滤

            # 直接检查消息类型是否为self或base（不区分大小写）
            msg_type = message_data.get('message_type', '')
            if msg_type and (msg_type.lower() in ['self', 'base'] or msg_type in ['Self', 'Base']):
                logger.info(f"_save_message直接过滤掉{msg_type}类型的消息: {message_id}")
                return ""  # 返回空字符串表示消息被过滤

            # 使用统一的消息过滤模块进行二次检查
            from wxauto_mgt.core.message_filter import message_filter

            # 检查消息是否应该被过滤
            if message_filter.should_filter_message(message_data, log_prefix="保存前"):
                logger.info(f"消息过滤模块过滤掉消息: {message_id}")
                return ""  # 返回空字符串表示消息被过滤

            # 检查消息是否符合规则 - 强制检查
            if instance_id and chat_name:
                # 导入规则管理器
                from wxauto_mgt.core.service_platform_manager import rule_manager

                # 获取匹配的规则
                rule = await rule_manager.match_rule(instance_id, chat_name, content)

                # 如果没有匹配的规则，直接返回
                if not rule:
                    logger.info(f"消息没有匹配的规则，不保存: ID={message_id}, 实例={instance_id}, 聊天={chat_name}")
                    return ""

                # 获取规则ID和优先级
                rule_id = rule.get('rule_id', '未知')
                priority = rule.get('priority', 0)

                logger.info(f"匹配到规则: ID={rule_id}, 优先级={priority}, 实例={instance_id}, 聊天={chat_name}")

                # 检查规则是否要求@消息 - 这是针对特定聊天对象的局部设置
                only_at_messages = rule.get('only_at_messages', 0)

                # 只有当规则明确要求@消息时才进行@规则检查
                if only_at_messages == 1:
                    logger.info(f"规则 {rule_id} 要求只响应@消息")
                    at_name = rule.get('at_name', '')

                    # 如果指定了@名称，检查消息是否包含@名称
                    if at_name:
                        # 支持多个@名称，用逗号分隔
                        at_names = [name.strip() for name in at_name.split(',')]
                        logger.info(f"规则要求@消息，@名称列表: {at_names}, ID={message_id}, 规则={rule_id}")

                        # 检查消息是否包含任意一个@名称
                        at_match = False
                        for name in at_names:
                            if name and f"@{name}" in content:
                                at_match = True
                                logger.info(f"消息匹配到@{name}规则，允许保存: ID={message_id}, 规则={rule_id}")
                                break
                            else:
                                logger.info(f"消息不包含@{name}: ID={message_id}, 规则={rule_id}")

                        # 如果没有匹配到任何@名称，不保存消息
                        if not at_match:
                            # 添加"不符合消息转发规则"标记，用于UI显示
                            logger.info(f"消息不符合@规则，不保存: ID={message_id}, 规则={rule_id}, 实例={instance_id}, 聊天={chat_name}, 内容={content[:50]}..., [不符合消息转发规则]")
                            return ""
                    else:
                        logger.info(f"规则要求@消息但未指定@名称，允许保存: ID={message_id}, 规则={rule_id}")
                else:
                    # 规则不要求@消息，直接允许保存
                    logger.info(f"规则不要求@消息，允许保存: ID={message_id}, 规则={rule_id}")
            else:
                logger.warning(f"消息缺少实例ID或聊天名称，无法检查规则: ID={message_id}")

            # 到这里，消息已经通过了所有过滤条件，可以保存到数据库
            logger.info(f"消息通过所有过滤条件，准备保存到数据库: ID={message_id}")

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

            # 返回消息ID
            message_id = message_data.get('message_id', '')
            logger.debug(f"消息保存成功，ID: {message_id}")
            return message_id
        except Exception as e:
            logger.error(f"保存消息到数据库失败: {e}")
            return ""

    async def _save_listener(self, instance_id: str, who: str, conversation_id: str = "", manual_added: bool = False) -> bool:
        """
        保存监听对象到数据库

        Args:
            instance_id: 实例ID
            who: 监听对象的标识
            conversation_id: Dify会话ID，默认为空字符串
            manual_added: 是否为手动添加的监听对象

        Returns:
            bool: 是否保存成功
        """
        try:
            current_time = int(time.time())
            data = {
                'instance_id': instance_id,
                'who': who,
                'last_message_time': current_time,
                'create_time': current_time,
                'manual_added': 1 if manual_added else 0,
                'status': 'active'  # 新添加的监听对象默认为活跃状态
            }

            # 如果提供了会话ID，添加到数据中
            if conversation_id:
                data['conversation_id'] = conversation_id
                logger.debug(f"保存监听对象会话ID: {instance_id} - {who} - {conversation_id}")

            if manual_added:
                logger.debug(f"保存手动添加的监听对象: {instance_id} - {who}")

            # 先检查是否已存在
            query = "SELECT id, conversation_id, manual_added FROM listeners WHERE instance_id = ? AND who = ?"
            exists = await db_manager.fetchone(query, (instance_id, who))

            if exists:
                # 已存在，执行更新操作
                if conversation_id:
                    # 如果提供了新的会话ID，更新会话ID、手动添加标识和状态
                    update_query = "UPDATE listeners SET last_message_time = ?, conversation_id = ?, manual_added = ?, status = 'active' WHERE instance_id = ? AND who = ?"
                    await db_manager.execute(update_query, (current_time, conversation_id, 1 if manual_added else 0, instance_id, who))
                    logger.debug(f"更新监听对象和会话ID: {instance_id} - {who} - {conversation_id}")
                else:
                    # 如果没有提供新的会话ID，只更新时间戳、手动添加标识和状态
                    update_query = "UPDATE listeners SET last_message_time = ?, manual_added = ?, status = 'active' WHERE instance_id = ? AND who = ?"
                    await db_manager.execute(update_query, (current_time, 1 if manual_added else 0, instance_id, who))
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

            # 执行SQL
            await db_manager.execute(sql, (instance_id, who))

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

    def get_all_listeners_sorted(self, instance_id: str = None) -> Dict[str, List[Dict]]:
        """
        获取所有监听对象列表（包括非活跃的），按状态和最后活跃时间排序

        Args:
            instance_id: 可选的实例ID，如果提供则只返回该实例的监听对象

        Returns:
            Dict[str, List[Dict]]: 实例ID到监听对象详细信息列表的映射
        """
        result = {}

        def sort_listeners(listeners_dict):
            """排序监听器：活跃的在前，然后按最后消息时间降序"""
            listener_list = []
            for who, info in listeners_dict.items():
                listener_list.append({
                    'who': who,
                    'active': info.active,
                    'last_message_time': info.last_message_time,
                    'last_check_time': info.last_check_time,
                    'conversation_id': info.conversation_id,
                    'manual_added': info.manual_added,
                    'fixed_listener': info.fixed_listener,
                    'status': 'active' if info.active else 'inactive'
                })

            # 排序：活跃状态在前，然后按最后消息时间降序
            listener_list.sort(key=lambda x: (not x['active'], -x['last_message_time']))
            return listener_list

        if instance_id:
            if instance_id in self.listeners:
                result[instance_id] = sort_listeners(self.listeners[instance_id])
        else:
            for inst_id, listeners in self.listeners.items():
                result[inst_id] = sort_listeners(listeners)

        return result

    async def _load_listeners_from_db(self):
        """从数据库加载保存的监听对象"""
        try:
            logger.info("从数据库加载监听对象")

            # 查询所有监听对象，包括会话ID、手动添加标识和状态
            query = "SELECT instance_id, who, last_message_time, conversation_id, manual_added, status FROM listeners"
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
                    conversation_id = listener.get('conversation_id', '')
                    manual_added = bool(listener.get('manual_added', 0))
                    status = listener.get('status', 'active')  # 默认为活跃状态

                    # 跳过无效记录
                    if not instance_id or not who:
                        continue

                    # 初始化实例的监听字典
                    if instance_id not in self.listeners:
                        self.listeners[instance_id] = {}

                    # 添加监听对象
                    listener_info = ListenerInfo(
                        instance_id=instance_id,
                        who=who,
                        last_message_time=float(last_message_time),
                        last_check_time=time.time(),
                        conversation_id=conversation_id,
                        manual_added=manual_added
                    )
                    # 设置活跃状态
                    listener_info.active = (status == 'active')
                    self.listeners[instance_id][who] = listener_info

                    # 记录会话ID信息
                    if conversation_id:
                        logger.debug(f"加载监听对象会话ID: {instance_id} - {who} - {conversation_id}")

                    # 记录手动添加信息
                    if manual_added:
                        logger.info(f"加载手动添加的监听对象（不受超时限制）: {instance_id} - {who}")

            # 计算加载的监听对象数量
            total = sum(len(listeners) for listeners in self.listeners.values())
            logger.info(f"从数据库加载了 {total} 个监听对象")

            # 重新添加监听对象到API
            await self._reapply_listeners_to_api()

            # 注意：超时对象的处理已移至start方法的_refresh_all_listeners中

        except Exception as e:
            logger.error(f"从数据库加载监听对象时出错: {e}")
            logger.exception(e)
            # 出错时也要确保监听器字典被初始化

    async def _reapply_listeners_to_api(self):
        """重新将监听对象添加到API"""
        try:
            logger.info("🔧 重新将监听对象添加到API...")

            total_reapplied = 0
            total_failed = 0

            for instance_id, listeners_dict in self.listeners.items():
                # 获取API客户端
                api_client = instance_manager.get_instance(instance_id)
                if not api_client:
                    logger.warning(f"找不到实例 {instance_id} 的API客户端，跳过重新添加监听")
                    continue

                logger.info(f"为实例 {instance_id} 重新添加 {len(listeners_dict)} 个监听对象")

                for who, listener_info in listeners_dict.items():
                    try:
                        # 只重新添加活跃的监听对象
                        if not listener_info.active:
                            logger.debug(f"跳过非活跃监听对象: {instance_id} - {who}")
                            continue

                        # 调用API重新添加监听
                        api_success = await api_client.add_listener(
                            who,
                            save_pic=True,
                            save_file=True,
                            save_voice=True,
                            parse_url=True
                        )

                        if api_success:
                            total_reapplied += 1
                            if listener_info.fixed_listener:
                                logger.info(f"成功重新添加固定监听对象: {instance_id} - {who}")
                            elif listener_info.manual_added:
                                logger.info(f"成功重新添加手动监听对象: {instance_id} - {who}")
                            else:
                                logger.debug(f"成功重新添加监听对象: {instance_id} - {who}")
                        else:
                            total_failed += 1
                            logger.warning(f"重新添加监听对象失败: {instance_id} - {who}")

                    except Exception as e:
                        total_failed += 1
                        logger.error(f"重新添加监听对象 {instance_id} - {who} 时出错: {e}")

            logger.info(f"🔧 监听对象重新添加完成: 成功 {total_reapplied} 个，失败 {total_failed} 个")

        except Exception as e:
            logger.error(f"重新添加监听对象到API时出错: {e}")
            logger.exception(e)
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

                    # 再重新添加，设置接收图片、文件、语音信息、URL信息参数为True
                    logger.debug(f"尝试重新添加监听对象: {instance_id} - {who}")
                    add_success = await api_client.add_listener(
                        who,
                        save_pic=True,
                        save_file=True,
                        save_voice=True,
                        parse_url=True
                    )

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
                    # 先过滤消息
                    filtered_messages = self._filter_messages(messages)

                    # 如果获取到消息，更新最后消息时间
                    logger.info(f"监听对象 {who} 有 {len(messages)} 条新消息，过滤后剩余 {len(filtered_messages)} 条，更新最后消息时间")

                    # 记录第一条过滤后的消息内容
                    if filtered_messages:
                        msg = filtered_messages[0]
                        sender = msg.get('sender', '未知')
                        sender_remark = msg.get('sender_remark', '')
                        content = msg.get('content', '')
                        # 使用发送者备注名(如果有)，否则使用发送者ID
                        display_sender = sender_remark if sender_remark else sender
                        # 截断内容，避免日志过长
                        short_content = content[:50] + "..." if len(content) > 50 else content

                        # 检查消息是否符合@规则
                        from wxauto_mgt.core.message_filter import message_filter
                        from wxauto_mgt.core.service_platform_manager import rule_manager

                        # 获取匹配的规则
                        rule = await rule_manager.match_rule(instance_id, who, content)

                        # 检查是否需要@规则过滤
                        is_at_rule_filtered = False
                        if rule:
                            # 获取规则ID，但不使用它，只是为了避免IDE警告
                            _ = rule.get('rule_id', '未知')
                            only_at_messages = rule.get('only_at_messages', 0)

                            if only_at_messages == 1:
                                at_name = rule.get('at_name', '')
                                if at_name:
                                    # 支持多个@名称，用逗号分隔
                                    at_names = [name.strip() for name in at_name.split(',')]

                                    # 检查消息是否包含任意一个@名称
                                    at_match = False
                                    for name in at_names:
                                        if name and f"@{name}" in content:
                                            at_match = True
                                            break

                                    # 如果没有匹配到任何@名称，标记为不符合规则
                                    if not at_match:
                                        is_at_rule_filtered = True

                        # 根据是否符合@规则记录不同的日志 - 只记录一条日志
                        if is_at_rule_filtered:
                            # 只记录一条带有[不符合消息转发规则]标记的日志
                            logger.info(f"监控到来自于会话\"{who}\"，发送人是\"{display_sender}\"的新消息，内容：\"{short_content}\" [不符合消息转发规则]")

                            # 重要：将这条消息从filtered_messages中移除，避免后续处理
                            filtered_messages.remove(msg)
                        else:
                            logger.info(f"获取到新消息: 实例={instance_id}, 聊天={who}, 发送者={display_sender}, 内容={short_content}")

                    async with self._lock:
                        if instance_id in self.listeners and who in self.listeners[instance_id]:
                            self.listeners[instance_id][who].last_message_time = time.time()
                            self.listeners[instance_id][who].last_check_time = time.time()

                            # 更新数据库中的时间戳
                            await self._update_listener_timestamp(instance_id, who)
                            logger.debug(f"已更新监听对象时间戳: {instance_id} - {who}")

                            # 处理消息
                            logger.debug(f"开始处理 {len(filtered_messages)} 条过滤后的消息并保存到数据库")
                            for msg in filtered_messages:
                                # 在保存前检查消息是否应该被过滤
                                from wxauto_mgt.core.message_filter import message_filter

                                # 直接检查sender是否为self
                                sender = msg.get('sender', '')
                                if sender and (sender.lower() == 'self' or sender == 'Self'):
                                    logger.debug(f"过滤掉self发送的刷新消息: {msg.get('id')}")
                                    continue

                                # 处理不同类型的消息
                                from wxauto_mgt.core.message_processor import message_processor

                                # 处理消息内容
                                processed_msg = await message_processor.process_message(msg, api_client)

                                # 保存消息到数据库
                                save_data = {
                                    'instance_id': instance_id,
                                    'chat_name': who,
                                    'message_type': processed_msg.get('type', 'text'),
                                    'content': processed_msg.get('content', ''),
                                    'sender': processed_msg.get('sender', ''),
                                    'sender_remark': processed_msg.get('sender_remark', ''),
                                    'message_id': processed_msg.get('id', ''),
                                    'mtype': processed_msg.get('mtype', 0)
                                }

                                # 如果是文件或图片，添加本地文件路径
                                if 'local_file_path' in processed_msg:
                                    save_data['local_file_path'] = processed_msg.get('local_file_path')
                                    save_data['file_size'] = processed_msg.get('file_size')
                                    save_data['original_file_path'] = processed_msg.get('original_file_path')

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

    async def _update_listener_timestamp(self, instance_id: str, who: str, conversation_id: str = "") -> bool:
        """
        更新数据库中监听对象的时间戳和会话ID

        Args:
            instance_id: 实例ID
            who: 监听对象的标识
            conversation_id: Dify会话ID，默认为空字符串

        Returns:
            bool: 是否更新成功
        """
        try:
            current_time = int(time.time())

            if conversation_id:
                # 如果提供了会话ID，同时更新时间戳和会话ID
                update_query = "UPDATE listeners SET last_message_time = ?, conversation_id = ? WHERE instance_id = ? AND who = ?"
                await db_manager.execute(update_query, (current_time, conversation_id, instance_id, who))
                logger.debug(f"已更新监听对象时间戳和会话ID: {instance_id} - {who} - {conversation_id}")
            else:
                # 否则只更新时间戳
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

        # 为所有监听对象提供启动宽限期
        logger.info("为所有监听对象提供启动宽限期")
        async with self._lock:
            for instance_id, listeners_dict in self.listeners.items():
                for who, info in listeners_dict.items():
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
                    # 检查是否为手动添加或固定监听对象（不受超时限制）
                    if getattr(info, 'manual_added', False) or getattr(info, 'fixed_listener', False):
                        logger.debug(f"跳过手动添加或固定监听对象（不受超时限制）: {instance_id} - {who}")
                        continue

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

                # 更新最后检查时间
                async with self._lock:
                    if instance_id in self.listeners and who in self.listeners[instance_id]:
                        self.listeners[instance_id][who].last_check_time = time.time()

                if messages:
                    # 先过滤消息
                    filtered_messages = self._filter_messages(messages)

                    # 如果有新消息，更新时间戳
                    logger.info(f"监听对象 {who} 有 {len(messages)} 条新消息，过滤后剩余 {len(filtered_messages)} 条，重置超时")

                    # 记录第一条过滤后的消息内容
                    if filtered_messages:
                        msg = filtered_messages[0]
                        sender = msg.get('sender', '未知')
                        sender_remark = msg.get('sender_remark', '')
                        content = msg.get('content', '')
                        # 使用发送者备注名(如果有)，否则使用发送者ID
                        display_sender = sender_remark if sender_remark else sender
                        # 截断内容，避免日志过长
                        short_content = content[:50] + "..." if len(content) > 50 else content

                        # 检查消息是否符合@规则
                        from wxauto_mgt.core.message_filter import message_filter
                        from wxauto_mgt.core.service_platform_manager import rule_manager

                        # 获取匹配的规则
                        rule = await rule_manager.match_rule(instance_id, who, content)

                        # 检查是否需要@规则过滤
                        is_at_rule_filtered = False
                        if rule:
                            # 获取规则ID，但不使用它，只是为了避免IDE警告
                            _ = rule.get('rule_id', '未知')
                            only_at_messages = rule.get('only_at_messages', 0)

                            if only_at_messages == 1:
                                at_name = rule.get('at_name', '')
                                if at_name:
                                    # 支持多个@名称，用逗号分隔
                                    at_names = [name.strip() for name in at_name.split(',')]

                                    # 检查消息是否包含任意一个@名称
                                    at_match = False
                                    for name in at_names:
                                        if name and f"@{name}" in content:
                                            at_match = True
                                            break

                                    # 如果没有匹配到任何@名称，标记为不符合规则
                                    if not at_match:
                                        is_at_rule_filtered = True

                        # 根据是否符合@规则记录不同的日志 - 只记录一条日志
                        if is_at_rule_filtered:
                            # 只记录一条带有[不符合消息转发规则]标记的日志
                            logger.info(f"监控到来自于会话\"{who}\"，发送人是\"{display_sender}\"的新消息，内容：\"{short_content}\" [不符合消息转发规则]")

                            # 重要：将这条消息从filtered_messages中移除，避免后续处理
                            filtered_messages.remove(msg)
                        else:
                            logger.info(f"获取到新消息: 实例={instance_id}, 聊天={who}, 发送者={display_sender}, 内容={short_content}")

                    async with self._lock:
                        if instance_id in self.listeners and who in self.listeners[instance_id]:
                            self.listeners[instance_id][who].last_message_time = time.time()
                            self.listeners[instance_id][who].last_check_time = time.time()
                            # 更新数据库中的时间戳
                            await self._update_listener_timestamp(instance_id, who)

                            # 处理消息
                            for msg in filtered_messages:
                                # 在保存前检查消息是否应该被过滤
                                from wxauto_mgt.core.message_filter import message_filter

                                # 直接检查sender是否为self
                                sender = msg.get('sender', '')
                                if sender and (sender.lower() == 'self' or sender == 'Self'):
                                    logger.debug(f"过滤掉self发送的启动消息: {msg.get('id')}")
                                    continue

                                # 处理不同类型的消息
                                from wxauto_mgt.core.message_processor import message_processor

                                # 处理消息内容
                                processed_msg = await message_processor.process_message(msg, api_client)

                                # 保存消息到数据库
                                save_data = {
                                    'instance_id': instance_id,
                                    'chat_name': who,
                                    'message_type': processed_msg.get('type', 'text'),
                                    'content': processed_msg.get('content', ''),
                                    'sender': processed_msg.get('sender', ''),
                                    'sender_remark': processed_msg.get('sender_remark', ''),
                                    'message_id': processed_msg.get('id', ''),
                                    'mtype': processed_msg.get('mtype', 0)
                                }

                                # 如果是文件或图片，添加本地文件路径
                                if 'local_file_path' in processed_msg:
                                    save_data['local_file_path'] = processed_msg.get('local_file_path')
                                    save_data['file_size'] = processed_msg.get('file_size')
                                    save_data['original_file_path'] = processed_msg.get('original_file_path')

                                # 使用消息过滤模块进行二次检查
                                if message_filter.should_filter_message(save_data, log_prefix="启动保存前"):
                                    logger.debug(f"消息过滤模块过滤掉启动消息: {msg.get('id')}")
                                    continue

                                # 保存到数据库
                                message_id = await self._save_message(save_data)
                                if message_id:
                                    logger.debug(f"启动时消息保存成功，ID: {message_id}")

                                    # 直接处理消息投递和回复 - 与主窗口保持一致
                                    try:
                                        # 导入消息投递服务
                                        from wxauto_mgt.core.message_delivery_service import message_delivery_service

                                        # 获取保存的消息
                                        from wxauto_mgt.data.db_manager import db_manager
                                        saved_message = await db_manager.fetchone(
                                            "SELECT * FROM messages WHERE message_id = ?",
                                            (processed_msg.get('id'),)
                                        )

                                        if saved_message:
                                            # 直接处理消息投递
                                            logger.info(f"启动时消息直接投递处理: {processed_msg.get('id')}")
                                            # 直接等待处理完成，确保回复能发送回微信
                                            try:
                                                delivery_result = await message_delivery_service.process_message(saved_message)
                                                logger.info(f"启动时消息投递处理完成: {processed_msg.get('id')}, 结果: {delivery_result}")
                                            except Exception as delivery_e:
                                                logger.error(f"启动时消息投递处理异常: {delivery_e}")
                                                logger.exception(delivery_e)
                                        else:
                                            logger.error(f"无法找到保存的消息: {processed_msg.get('id')}")
                                    except Exception as e:
                                        logger.error(f"启动时消息投递处理失败: {e}")
                                        logger.exception(e)
                else:
                    # 无消息时，尝试重置监听对象
                    logger.info(f"监听对象 {who} 没有新消息，尝试重置")
                    try:
                        # 先移除
                        await api_client.remove_listener(who)
                        # 再添加，设置接收图片、文件、语音信息、URL信息参数为True
                        add_success = await api_client.add_listener(
                            who,
                            save_pic=True,
                            save_file=True,
                            save_voice=True,
                            parse_url=True
                        )

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

    async def _mark_listener_inactive(self, instance_id: str, who: str) -> bool:
        """
        标记监听对象为非活跃状态（而不是删除）

        Args:
            instance_id: 实例ID
            who: 监听对象的标识

        Returns:
            bool: 是否标记成功
        """
        try:
            # 更新内存中的状态
            async with self._lock:
                if instance_id in self.listeners and who in self.listeners[instance_id]:
                    self.listeners[instance_id][who].active = False
                    logger.debug(f"内存中标记监听对象为非活跃: {instance_id} - {who}")

            # 更新数据库中的状态
            update_sql = "UPDATE listeners SET status = 'inactive' WHERE instance_id = ? AND who = ?"
            await db_manager.execute(update_sql, (instance_id, who))

            # 验证更新是否成功
            verify_sql = "SELECT status FROM listeners WHERE instance_id = ? AND who = ?"
            verify_result = await db_manager.fetchone(verify_sql, (instance_id, who))

            if verify_result and verify_result.get('status') == 'inactive':
                logger.debug(f"数据库中标记监听对象为非活跃成功: {instance_id} - {who}")
                return True
            else:
                logger.warning(f"数据库中标记监听对象为非活跃可能失败: {instance_id} - {who}, 验证结果: {verify_result}")
                return False

        except Exception as e:
            logger.error(f"标记监听对象为非活跃失败: {e}")
            logger.exception(e)
            return False

    async def _register_config_listeners(self):
        """注册配置变更监听器"""
        if self._config_listeners_registered:
            return

        try:
            # 监听所有配置变更事件
            await config_notifier.subscribe_all(self._on_config_changed)
            self._config_listeners_registered = True
            logger.info("已注册配置变更监听器")
        except Exception as e:
            logger.error(f"注册配置变更监听器失败: {e}")

    async def _unregister_config_listeners(self):
        """注销配置变更监听器"""
        if not self._config_listeners_registered:
            return

        try:
            await config_notifier.unsubscribe_all(self._on_config_changed)
            self._config_listeners_registered = False
            logger.info("已注销配置变更监听器")
        except Exception as e:
            logger.error(f"注销配置变更监听器失败: {e}")

    async def _on_config_changed(self, event: ConfigChangeEvent):
        """
        处理配置变更事件

        Args:
            event: 配置变更事件
        """
        try:
            logger.info(f"收到配置变更通知: {event.change_type.value}")

            # 根据变更类型进行相应处理
            if event.change_type.value.startswith('platform_') or event.change_type.value.startswith('rule_'):
                # 平台或规则配置变更，重新加载相关配置
                await self._reload_config_cache()

        except Exception as e:
            logger.error(f"处理配置变更事件失败: {e}")
            logger.exception(e)

    async def _reload_config_cache(self):
        """重新加载配置缓存"""
        try:
            logger.info("开始重新加载配置缓存")

            # 重新初始化服务平台管理器和规则管理器
            from wxauto_mgt.core.service_platform_manager import platform_manager, rule_manager

            # 强制重新初始化（清除已初始化标志）
            platform_manager._initialized = False
            rule_manager._initialized = False

            # 重新初始化
            await platform_manager.initialize()
            await rule_manager.initialize()

            logger.info("配置缓存重新加载完成")

            # 记录配置重新加载统计
            service_monitor.record_config_reload()

        except Exception as e:
            logger.error(f"重新加载配置缓存失败: {e}")
            logger.exception(e)

    async def _check_api_client_health(self, instance_id: str, api_client) -> bool:
        """
        检查API客户端连接健康状态

        Args:
            instance_id: 实例ID
            api_client: API客户端实例

        Returns:
            bool: 连接是否健康
        """
        try:
            # 检查客户端是否已初始化
            if not hasattr(api_client, 'initialized') or not api_client.initialized:
                logger.warning(f"实例 {instance_id} API客户端未初始化，尝试重新初始化")
                try:
                    init_result = await api_client.initialize()
                    if not init_result:
                        logger.error(f"实例 {instance_id} API客户端重新初始化失败")
                        return False
                    logger.info(f"实例 {instance_id} API客户端重新初始化成功")
                except Exception as init_e:
                    logger.error(f"实例 {instance_id} API客户端初始化异常: {init_e}")
                    return False

            # 简单的健康检查 - 尝试获取实例状态
            try:
                # 这里可以调用一个轻量级的API来检查连接状态
                # 如果API客户端有健康检查方法，使用它
                if hasattr(api_client, 'health_check'):
                    health_result = await api_client.health_check()
                    return health_result
                else:
                    # 如果没有专门的健康检查方法，认为已初始化的客户端是健康的
                    return True

            except Exception as health_e:
                logger.warning(f"实例 {instance_id} 健康检查失败: {health_e}")
                # 尝试重新初始化
                try:
                    logger.info(f"尝试重新初始化实例 {instance_id}")
                    init_result = await api_client.initialize()
                    if init_result:
                        logger.info(f"实例 {instance_id} 重新初始化成功")
                        return True
                    else:
                        logger.error(f"实例 {instance_id} 重新初始化失败")
                        return False
                except Exception as reinit_e:
                    logger.error(f"实例 {instance_id} 重新初始化异常: {reinit_e}")
                    return False

        except Exception as e:
            logger.error(f"检查实例 {instance_id} API客户端健康状态时出错: {e}")
            logger.exception(e)
            return False

    # ==================== 固定监听功能 ====================

    async def _load_and_apply_fixed_listeners(self):
        """加载固定监听配置并自动添加到监听列表"""
        try:
            logger.info("🔧 开始加载固定监听配置...")

            # 检查数据库管理器是否已初始化
            if not hasattr(db_manager, '_initialized') or not db_manager._initialized:
                logger.error("数据库管理器未初始化，无法加载固定监听配置")
                return

            # 从数据库获取启用的固定监听配置
            logger.debug("查询数据库中的固定监听配置...")
            fixed_listeners = await db_manager.fetchall(
                "SELECT session_name, description FROM fixed_listeners WHERE enabled = 1"
            )
            logger.debug(f"数据库查询结果: {fixed_listeners}")

            if not fixed_listeners:
                logger.info("没有启用的固定监听配置")
                return

            logger.info(f"找到 {len(fixed_listeners)} 个启用的固定监听配置")

            # 获取所有可用的实例
            logger.debug("获取可用的微信实例...")
            available_instances = instance_manager.get_all_instances()
            logger.debug(f"可用实例: {available_instances}")

            if not available_instances:
                logger.warning("没有可用的微信实例，无法应用固定监听配置")
                return

            logger.info(f"找到 {len(available_instances)} 个可用的微信实例")

            # 为每个固定监听会话在所有实例中添加监听对象
            for fixed_listener in fixed_listeners:
                session_name = fixed_listener['session_name']
                description = fixed_listener.get('description', '')

                logger.info(f"应用固定监听配置: {session_name} ({description})")

                # 为每个实例添加此固定监听对象
                for instance_id in available_instances:
                    try:
                        # 检查是否已经存在此监听对象
                        if (instance_id in self.listeners and
                            session_name in self.listeners[instance_id]):
                            # 如果已存在，标记为固定监听对象
                            self.listeners[instance_id][session_name].fixed_listener = True
                            logger.debug(f"已存在的监听对象标记为固定监听: {instance_id} - {session_name}")
                        else:
                            # 添加新的固定监听对象
                            success = await self.add_listener(
                                instance_id=instance_id,
                                who=session_name,
                                conversation_id="",
                                save_pic=True,
                                save_file=True,
                                save_voice=True,
                                parse_url=True,
                                manual_added=True,  # 标记为手动添加，不受超时限制
                                fixed_listener=True  # 标记为固定监听对象
                            )

                            if success:
                                logger.info(f"成功添加固定监听对象: {instance_id} - {session_name}")
                            else:
                                logger.warning(f"添加固定监听对象失败: {instance_id} - {session_name}")

                    except Exception as e:
                        logger.error(f"为实例 {instance_id} 添加固定监听对象 {session_name} 时出错: {e}")

        except Exception as e:
            logger.error(f"🚨 加载和应用固定监听配置时出错: {e}")
            logger.exception(e)
            import traceback
            logger.error(f"详细错误信息: {traceback.format_exc()}")

    async def get_fixed_listeners(self) -> List[Dict]:
        """获取所有固定监听配置"""
        try:
            fixed_listeners = await db_manager.fetchall(
                "SELECT id, session_name, enabled, description, create_time, update_time FROM fixed_listeners ORDER BY session_name"
            )
            return [dict(row) for row in fixed_listeners]
        except Exception as e:
            logger.error(f"获取固定监听配置失败: {e}")
            return []

    async def add_fixed_listener(self, session_name: str, description: str = "", enabled: bool = True) -> bool:
        """添加固定监听配置"""
        try:
            current_time = int(time.time())

            # 检查是否已存在
            existing = await db_manager.fetchone(
                "SELECT id FROM fixed_listeners WHERE session_name = ?",
                (session_name,)
            )

            if existing:
                logger.warning(f"固定监听配置已存在: {session_name}")
                return False

            # 插入新配置
            await db_manager.execute(
                """INSERT INTO fixed_listeners
                   (session_name, enabled, description, create_time, update_time)
                   VALUES (?, ?, ?, ?, ?)""",
                (session_name, 1 if enabled else 0, description, current_time, current_time)
            )

            logger.info(f"成功添加固定监听配置: {session_name}")

            # 如果启用，立即应用到所有实例
            if enabled:
                await self._apply_single_fixed_listener(session_name, description)

            return True

        except Exception as e:
            logger.error(f"添加固定监听配置失败: {e}")
            return False

    async def update_fixed_listener(self, listener_id: int, session_name: str = None,
                                  description: str = None, enabled: bool = None) -> bool:
        """更新固定监听配置"""
        try:
            # 获取当前配置
            current = await db_manager.fetchone(
                "SELECT session_name, enabled, description FROM fixed_listeners WHERE id = ?",
                (listener_id,)
            )

            if not current:
                logger.warning(f"固定监听配置不存在: ID {listener_id}")
                return False

            # 准备更新数据
            update_data = {}
            if session_name is not None:
                update_data['session_name'] = session_name
            if description is not None:
                update_data['description'] = description
            if enabled is not None:
                update_data['enabled'] = 1 if enabled else 0

            if not update_data:
                return True  # 没有需要更新的数据

            update_data['update_time'] = int(time.time())

            # 构建更新SQL
            set_clause = ', '.join([f"{key} = ?" for key in update_data.keys()])
            values = list(update_data.values()) + [listener_id]

            await db_manager.execute(
                f"UPDATE fixed_listeners SET {set_clause} WHERE id = ?",
                values
            )

            logger.info(f"成功更新固定监听配置: ID {listener_id}")

            # 如果会话名称或启用状态发生变化，需要重新应用配置
            old_session_name = current['session_name']
            old_enabled = bool(current['enabled'])
            new_session_name = session_name if session_name is not None else old_session_name
            new_enabled = enabled if enabled is not None else old_enabled

            if session_name is not None or enabled is not None:
                # 移除旧的监听对象（如果会话名称改变或被禁用）
                if session_name is not None or not new_enabled:
                    await self._remove_fixed_listener_from_instances(old_session_name)

                # 添加新的监听对象（如果启用）
                if new_enabled:
                    new_description = description if description is not None else current['description']
                    await self._apply_single_fixed_listener(new_session_name, new_description)

            return True

        except Exception as e:
            logger.error(f"更新固定监听配置失败: {e}")
            return False

    async def delete_fixed_listener(self, listener_id: int) -> bool:
        """删除固定监听配置"""
        try:
            # 获取配置信息
            config = await db_manager.fetchone(
                "SELECT session_name FROM fixed_listeners WHERE id = ?",
                (listener_id,)
            )

            if not config:
                logger.warning(f"固定监听配置不存在: ID {listener_id}")
                return False

            session_name = config['session_name']

            # 从所有实例中移除此固定监听对象
            await self._remove_fixed_listener_from_instances(session_name)

            # 删除配置
            await db_manager.execute(
                "DELETE FROM fixed_listeners WHERE id = ?",
                (listener_id,)
            )

            logger.info(f"成功删除固定监听配置: {session_name}")
            return True

        except Exception as e:
            logger.error(f"删除固定监听配置失败: {e}")
            return False

    async def _apply_single_fixed_listener(self, session_name: str, description: str = ""):
        """为所有实例应用单个固定监听配置"""
        try:
            available_instances = instance_manager.get_all_instances()

            for instance_id in available_instances:
                try:
                    # 检查是否已经存在此监听对象
                    if (instance_id in self.listeners and
                        session_name in self.listeners[instance_id]):
                        # 如果已存在，标记为固定监听对象
                        self.listeners[instance_id][session_name].fixed_listener = True
                        logger.debug(f"已存在的监听对象标记为固定监听: {instance_id} - {session_name}")
                    else:
                        # 添加新的固定监听对象
                        success = await self.add_listener(
                            instance_id=instance_id,
                            who=session_name,
                            conversation_id="",
                            save_pic=True,
                            save_file=True,
                            save_voice=True,
                            parse_url=True,
                            manual_added=True,
                            fixed_listener=True
                        )

                        if success:
                            logger.info(f"成功添加固定监听对象: {instance_id} - {session_name}")
                        else:
                            logger.warning(f"添加固定监听对象失败: {instance_id} - {session_name}")

                except Exception as e:
                    logger.error(f"为实例 {instance_id} 应用固定监听对象 {session_name} 时出错: {e}")

        except Exception as e:
            logger.error(f"应用固定监听配置时出错: {e}")

    async def _remove_fixed_listener_from_instances(self, session_name: str):
        """从所有实例中移除固定监听对象"""
        try:
            for instance_id in list(self.listeners.keys()):
                if session_name in self.listeners[instance_id]:
                    listener_info = self.listeners[instance_id][session_name]
                    if listener_info.fixed_listener:
                        # 移除固定监听对象
                        await self.remove_listener(instance_id, session_name)
                        logger.info(f"移除固定监听对象: {instance_id} - {session_name}")

        except Exception as e:
            logger.error(f"移除固定监听对象时出错: {e}")

    def is_fixed_listener(self, instance_id: str, who: str) -> bool:
        """检查是否为固定监听对象"""
        try:
            if (instance_id in self.listeners and
                who in self.listeners[instance_id]):
                return self.listeners[instance_id][who].fixed_listener
            return False
        except Exception:
            return False

# 创建全局实例
message_listener = MessageListener()