"""
消息监听管理器模块

该模块负责管理微信消息的监听、接收和分发。主要功能包括：
- 定时获取主窗口未读消息
- 管理监听对象列表
- 定时获取监听对象的最新消息
- 处理消息超时和自动移除监听对象
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from datetime import datetime, timedelta

# 配置日志
logger = logging.getLogger(__name__)

@dataclass
class Message:
    """消息数据类"""
    id: str
    sender: str
    content: str
    timestamp: float
    processed: bool = False

@dataclass
class ListenerInfo:
    """监听对象信息"""
    who: str
    last_message_time: float
    last_check_time: float
    active: bool = True

class MessageListener:
    def __init__(
        self,
        api_client,
        message_store,
        poll_interval: int = 5,
        max_listeners: int = 30,
        timeout_minutes: int = 30
    ):
        """
        初始化消息监听器
        
        Args:
            api_client: WxAuto API客户端实例
            message_store: 消息存储实例
            poll_interval: 轮询间隔（秒）
            max_listeners: 最大监听对象数量
            timeout_minutes: 监听对象超时时间（分钟）
        """
        self.api_client = api_client
        self.message_store = message_store
        self.poll_interval = poll_interval
        self.max_listeners = max_listeners
        self.timeout_minutes = timeout_minutes
        
        # 内部状态
        self.listeners: Dict[str, ListenerInfo] = {}
        self.running: bool = False
        self._tasks: Set[asyncio.Task] = set()
        self._lock = asyncio.Lock()
    
    async def start(self):
        """启动监听服务"""
        if self.running:
            logger.warning("监听服务已经在运行")
            return
        
        self.running = True
        logger.info("启动消息监听服务")
        
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
                await self.check_main_window_messages()
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
                await self.check_listener_messages()
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
    
    async def check_main_window_messages(self):
        """检查主窗口未读消息"""
        try:
            # 获取主窗口未读消息
            messages = await self.api_client.get_unread_messages()
            if not messages:
                return
            
            # 处理每条未读消息
            for msg in messages:
                chat_name = msg.get('chat_name')
                if chat_name:
                    # 将发送者添加到监听列表
                    await self.add_listener(chat_name)
                    
                    # 保存消息到存储
                    await self.message_store.save_message({
                        'instance_id': None,
                        'chat_name': chat_name,
                        'message_type': msg.get('type'),
                        'content': msg.get('content'),
                        'sender': msg.get('sender'),
                        'sender_remark': msg.get('sender_remark'),
                        'message_id': msg.get('id'),
                        'mtype': msg.get('mtype')
                    })
                    
                    logger.debug(f"收到来自 {chat_name} 的新消息")
        
        except Exception as e:
            logger.error(f"处理主窗口消息时出错: {e}")
    
    async def check_listener_messages(self):
        """检查所有监听对象的新消息"""
        async with self._lock:
            for who, info in list(self.listeners.items()):
                if not info.active:
                    continue
                
                try:
                    # 获取该监听对象的新消息
                    messages = await self.api_client.get_listener_messages(None, who)
                    
                    if messages:
                        # 更新最后消息时间
                        info.last_message_time = time.time()
                        
                        # 保存消息到存储
                        for msg in messages:
                            await self.message_store.save_message({
                                'instance_id': None,
                                'chat_name': who,
                                'message_type': msg.get('type'),
                                'content': msg.get('content'),
                                'sender': msg.get('sender'),
                                'sender_remark': msg.get('sender_remark'),
                                'message_id': msg.get('id'),
                                'mtype': msg.get('mtype')
                            })
                        
                        logger.debug(f"从 {who} 获取到 {len(messages)} 条新消息")
                    
                    # 更新检查时间
                    info.last_check_time = time.time()
                
                except Exception as e:
                    logger.error(f"检查监听对象 {who} 的消息时出错: {e}")
    
    async def add_listener(self, who: str) -> bool:
        """
        添加监听对象
        
        Args:
            who: 监听对象的标识
            
        Returns:
            bool: 是否添加成功
        """
        async with self._lock:
            # 如果已经在监听列表中，更新时间
            if who in self.listeners:
                self.listeners[who].last_message_time = time.time()
                self.listeners[who].active = True
                return True
            
            # 检查是否超过最大监听数量
            if len(self.listeners) >= self.max_listeners:
                logger.warning(f"监听对象数量已达到上限 ({self.max_listeners})")
                return False
            
            # 添加新的监听对象
            self.listeners[who] = ListenerInfo(
                who=who,
                last_message_time=time.time(),
                last_check_time=time.time()
            )
            logger.info(f"添加新的监听对象: {who}")
            return True
    
    async def remove_listener(self, who: str):
        """
        移除监听对象
        
        Args:
            who: 监听对象的标识
        """
        async with self._lock:
            if who in self.listeners:
                del self.listeners[who]
                logger.info(f"移除监听对象: {who}")
    
    async def _remove_inactive_listeners(self) -> int:
        """移除超时的监听对象"""
        removed_count = 0
        current_time = time.time()
        
        async with self._lock:
            for (instance_id, who), info in list(self.listeners.items()):
                # 检查是否超时
                if current_time - info.last_message_time > self.timeout_minutes * 60:
                    logger.debug(f"监听对象 {who} 已超时，准备移除")
                    await self.remove_listener(who)
                    removed_count += 1
        
        return removed_count
    
    def get_active_listeners(self) -> List[str]:
        """获取当前活动的监听对象列表"""
        return [who for who, info in self.listeners.items() if info.active]
    
    async def get_pending_messages(self, limit: int = 100) -> List[Message]:
        """
        获取待处理的消息
        
        Args:
            limit: 返回消息的最大数量
            
        Returns:
            List[Message]: 待处理的消息列表
        """
        return await self.message_store.get_unprocessed_messages(limit)
    
    async def mark_message_processed(self, message_id: str):
        """
        标记消息为已处理
        
        Args:
            message_id: 消息ID
        """
        await self.message_store.mark_as_processed(message_id) 