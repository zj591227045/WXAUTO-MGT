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
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from datetime import datetime, timedelta

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
    
    async def start(self):
        """启动监听服务"""
        if self.running:
            logger.warning("监听服务已经在运行")
            return
        
        self.running = True
        logger.info("启动消息监听服务")
        
        # 从数据库加载监听对象
        await self._load_listeners_from_db()
        
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
                    # 将发送者添加到监听列表
                    await self.add_listener(instance_id, chat_name)
                    
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
                    
                    logger.debug(f"准备保存主窗口消息: {save_data}")
                    await self._save_message(save_data)
        
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
        过滤消息列表，处理"以下为新消息"分隔符
        
        Args:
            messages: 原始消息列表
            
        Returns:
            List[dict]: 过滤后的消息列表
        """
        if not messages:
            return []
            
        # 查找是否有"以下为新消息"标记
        new_message_index = -1
        for i, msg in enumerate(messages):
            content = msg.get('content', '')
            msg_type = msg.get('type', '')
            sender = msg.get('sender', '')
            
            # 检查是否是系统消息且内容为"以下为新消息"
            if (msg_type == 'sys' or sender == 'SYS') and '以下为新消息' in content:
                new_message_index = i
                logger.debug(f"找到'以下为新消息'分隔符，位于消息列表的第 {i+1} 条")
                break
        
        # 如果找到分隔符，只返回分隔符之后的消息
        if new_message_index >= 0:
            return messages[new_message_index + 1:]
        
        # 如果没有找到分隔符，返回所有消息
        return messages
    
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
        """
        async with self._lock:
            if instance_id not in self.listeners or who not in self.listeners[instance_id]:
                return
            
            # 获取API客户端
            api_client = instance_manager.get_instance(instance_id)
            if api_client:
                await api_client.remove_listener(who)
            
            # 从内存中移除
            del self.listeners[instance_id][who]
            
            # 从数据库中移除
            await self._remove_listener_from_db(instance_id, who)
            
            logger.info(f"已移除实例 {instance_id} 的监听对象: {who}")
    
    async def _remove_inactive_listeners(self) -> int:
        """
        清理所有实例中的不活跃监听对象
        
        Returns:
            int: 清理的监听对象数量
        """
        removed_count = 0
        current_time = time.time()
        timeout = self.timeout_minutes * 60
        
        async with self._lock:
            for instance_id in list(self.listeners.keys()):
                for who, info in list(self.listeners[instance_id].items()):
                    if current_time - info.last_message_time > timeout:
                        await self.remove_listener(instance_id, who)
                        removed_count += 1
        
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
            # 确保包含create_time字段
            if 'create_time' not in message_data:
                message_data['create_time'] = int(time.time())
                
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
            await db_manager.execute(sql, (instance_id, who))
            return True
        except Exception as e:
            logger.error(f"从数据库移除监听对象失败: {e}")
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
            
        except Exception as e:
            logger.error(f"从数据库加载监听对象时出错: {e}")
            # 出错时也要确保监听器字典被初始化
            self.listeners = {}

# 创建全局实例
message_listener = MessageListener() 