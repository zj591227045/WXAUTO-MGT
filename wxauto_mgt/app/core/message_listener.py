"""
消息监听管理器模块

负责管理微信消息的监听、接收和分发。定时获取主窗口未读消息、管理监听对象列表、
定时获取监听对象的最新消息、处理消息超时和自动移除监听对象。
"""

import asyncio
import time
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from app.core.api_client import WxAutoApiClient, instance_manager
from app.data.db_manager import db_manager
from app.utils.logging import get_logger

logger = get_logger()


class MessageListener:
    """
    消息监听管理器，负责管理微信消息的监听、接收和分发
    """
    
    def __init__(self, 
                poll_interval: int = 5, 
                max_listeners: int = 30, 
                timeout_minutes: int = 30):
        """
        初始化消息监听管理器
        
        Args:
            poll_interval: 轮询间隔（秒）
            max_listeners: 最大监听数量
            timeout_minutes: 监听超时时间（分钟）
        """
        self.poll_interval = poll_interval
        self.max_listeners = max_listeners
        self.timeout_minutes = timeout_minutes
        self.running = False
        self._listeners = {}  # 格式: {(instance_id, wxid): {'last_time': timestamp, 'create_time': timestamp}}
        self._main_window_task = None
        self._listener_task = None
        self._cleanup_task = None
        self._pending_messages = []  # 待处理的消息列表
        self._lock = asyncio.Lock()
        
        logger.debug(f"初始化消息监听管理器: 轮询间隔={poll_interval}秒, 最大监听数={max_listeners}, 超时时间={timeout_minutes}分钟")
    
    async def start(self) -> None:
        """
        启动监听服务
        """
        if self.running:
            logger.warning("消息监听服务已在运行")
            return
        
        logger.info("启动消息监听服务")
        self.running = True
        
        # 从数据库加载已有监听对象
        await self._load_listeners_from_db()
        
        # 启动轮询任务
        self._main_window_task = asyncio.create_task(self._main_window_poll_loop())
        self._listener_task = asyncio.create_task(self._listeners_poll_loop())
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def stop(self) -> None:
        """
        停止监听服务
        """
        if not self.running:
            logger.warning("消息监听服务未运行")
            return
        
        logger.info("停止消息监听服务")
        self.running = False
        
        # 取消所有任务
        if self._main_window_task:
            self._main_window_task.cancel()
        
        if self._listener_task:
            self._listener_task.cancel()
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
        
        # 等待任务完成
        tasks = []
        for task in [self._main_window_task, self._listener_task, self._cleanup_task]:
            if task and not task.done():
                tasks.append(task)
        
        if tasks:
            try:
                await asyncio.gather(*tasks, return_exceptions=True)
            except asyncio.CancelledError:
                pass
        
        # 保存监听对象到数据库
        await self._save_listeners_to_db()
        
        self._main_window_task = None
        self._listener_task = None
        self._cleanup_task = None
        logger.info("消息监听服务已停止")
    
    async def _load_listeners_from_db(self) -> None:
        """从数据库加载监听对象"""
        try:
            # 查询所有监听对象
            rows = await db_manager.fetchall(
                "SELECT instance_id, who, last_message_time, create_time FROM listeners"
            )
            
            if not rows:
                logger.info("数据库中没有监听对象")
                return
            
            # 加载到内存
            async with self._lock:
                for row in rows:
                    instance_id = row['instance_id']
                    wxid = row['who']
                    key = (instance_id, wxid)
                    
                    self._listeners[key] = {
                        'last_time': row['last_message_time'],
                        'create_time': row['create_time']
                    }
            
            logger.info(f"从数据库加载了 {len(rows)} 个监听对象")
            
        except Exception as e:
            logger.error(f"从数据库加载监听对象失败: {e}")
    
    async def _save_listeners_to_db(self) -> None:
        """保存监听对象到数据库"""
        try:
            # 不使用锁，直接操作数据库
            # 首先清空表
            await db_manager.execute("DELETE FROM listeners")
            
            # 复制当前监听对象列表避免并发修改
            listeners_copy = dict(self._listeners)
            
            # 插入当前监听对象
            for (instance_id, wxid), data in listeners_copy.items():
                await db_manager.insert("listeners", {
                    "instance_id": instance_id,
                    "who": wxid,
                    "last_message_time": data['last_time'],
                    "create_time": data['create_time']
                })
            
            logger.info(f"已保存 {len(listeners_copy)} 个监听对象到数据库")
        except Exception as e:
            logger.error(f"保存监听对象到数据库失败: {e}")
    
    async def _main_window_poll_loop(self) -> None:
        """主窗口消息轮询循环"""
        logger.info("启动主窗口消息轮询")
        
        while self.running:
            try:
                await self.check_main_window_messages()
                await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                logger.info("主窗口消息轮询已取消")
                break
            except Exception as e:
                logger.error(f"主窗口消息轮询出错: {e}")
                await asyncio.sleep(self.poll_interval)
    
    async def _listeners_poll_loop(self) -> None:
        """监听对象消息轮询循环"""
        logger.info("启动监听对象消息轮询")
        
        while self.running:
            try:
                await self.check_listener_messages()
                await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                logger.info("监听对象消息轮询已取消")
                break
            except Exception as e:
                logger.error(f"监听对象消息轮询出错: {e}")
                await asyncio.sleep(self.poll_interval)
    
    async def _cleanup_loop(self) -> None:
        """超时清理循环"""
        logger.info("启动监听对象超时清理")
        
        cleanup_interval = 60  # 每分钟检查一次
        
        while self.running:
            try:
                await self.cleanup_timeout_listeners()
                await asyncio.sleep(cleanup_interval)
            except asyncio.CancelledError:
                logger.info("监听对象超时清理已取消")
                break
            except Exception as e:
                logger.error(f"监听对象超时清理出错: {e}")
                await asyncio.sleep(cleanup_interval)
    
    async def check_main_window_messages(self) -> List[Dict]:
        """
        检查主窗口未读消息，并将新的对话添加到监听列表
        
        Returns:
            List[Dict]: 新添加到监听列表的对话
        """
        new_listeners = []
        
        # 获取所有实例并检查主窗口消息
        for instance_id, client in instance_manager.list_instances().items():
            if not client.initialized or not client.connected:
                continue
                
            try:
                # 获取主窗口未读消息
                messages = await client.get_unread_messages(count=20)
                
                if not messages:
                    continue
                
                logger.debug(f"实例 {instance_id} 获取到 {len(messages)} 条主窗口未读消息")
                
                # 对于每条未读消息，添加发送者到监听列表
                for message in messages:
                    sender = message.get('sender')
                    if not sender:
                        continue
                    
                    # 添加到监听列表
                    added = await self.add_listener(instance_id, sender)
                    if added:
                        new_listeners.append({
                            'instance_id': instance_id,
                            'wxid': sender
                        })
                    
                    # 将消息添加到待处理列表
                    await self._add_pending_message(instance_id, message)
            
            except Exception as e:
                logger.error(f"检查实例 {instance_id} 的主窗口消息失败: {e}")
        
        return new_listeners
    
    async def add_listener(self, instance_id: str, wxid: str) -> bool:
        """
        添加监听对象
        
        Args:
            instance_id: 实例ID
            wxid: 微信ID或群ID
            
        Returns:
            bool: 是否成功添加
        """
        key = (instance_id, wxid)
        
        async with self._lock:
            # 检查是否已存在
            if key in self._listeners:
                # 更新最后消息时间
                self._listeners[key]['last_time'] = int(time.time())
                logger.debug(f"更新监听对象 {instance_id}:{wxid} 的时间")
                return False
            
            # 检查监听数量是否达到上限
            if len(self._listeners) >= self.max_listeners:
                logger.warning(f"监听对象数量已达上限 ({self.max_listeners})")
                return False
            
            # 添加新的监听对象
            now = int(time.time())
            self._listeners[key] = {
                'last_time': now,
                'create_time': now
            }
            
            logger.info(f"添加新的监听对象: {instance_id}:{wxid}")
            
            # 在API中注册监听
            client = instance_manager.get_instance(instance_id)
            if client:
                try:
                    await client.add_listener(wxid)
                except Exception as e:
                    logger.error(f"在API中注册监听对象失败: {e}")
            
            return True
    
    async def remove_listener(self, instance_id: str, wxid: str) -> bool:
        """
        移除监听对象
        
        Args:
            instance_id: 实例ID
            wxid: 微信ID或群ID
            
        Returns:
            bool: 是否成功移除
        """
        key = (instance_id, wxid)
        
        async with self._lock:
            # 检查是否存在
            if key not in self._listeners:
                logger.warning(f"监听对象不存在: {instance_id}:{wxid}")
                return False
            
            # 移除监听对象
            del self._listeners[key]
            
            logger.info(f"移除监听对象: {instance_id}:{wxid}")
            
            # 在API中移除监听
            client = instance_manager.get_instance(instance_id)
            if client:
                try:
                    await client.remove_listener(wxid)
                except Exception as e:
                    logger.error(f"在API中移除监听对象失败: {e}")
            
            return True
    
    async def check_listener_messages(self) -> int:
        """
        检查所有监听对象的新消息
        
        Returns:
            int: 获取到的新消息数量
        """
        total_new_messages = 0
        tasks = []
        
        # 为每个监听对象创建一个获取消息的任务
        async with self._lock:
            for (instance_id, wxid), data in self._listeners.items():
                client = instance_manager.get_instance(instance_id)
                if not client or not client.initialized or not client.connected:
                    continue
                
                task = self._get_listener_messages(client, instance_id, wxid)
                tasks.append(task)
        
        # 等待所有任务完成
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 处理结果
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"获取监听对象消息失败: {result}")
                elif isinstance(result, int):
                    total_new_messages += result
        
        if total_new_messages > 0:
            logger.debug(f"共获取到 {total_new_messages} 条新消息")
        
        return total_new_messages
    
    async def _get_listener_messages(self, client: WxAutoApiClient, instance_id: str, wxid: str) -> int:
        """
        获取单个监听对象的新消息
        
        Args:
            client: API客户端实例
            instance_id: 实例ID
            wxid: 微信ID或群ID
            
        Returns:
            int: 获取到的新消息数量
        """
        try:
            messages = await client.get_listener_messages(wxid, count=10)
            
            if not messages:
                return 0
            
            logger.debug(f"获取到监听对象 {instance_id}:{wxid} 的 {len(messages)} 条新消息")
            
            # 更新监听对象的最后消息时间
            async with self._lock:
                key = (instance_id, wxid)
                if key in self._listeners:
                    self._listeners[key]['last_time'] = int(time.time())
            
            # 将消息添加到待处理列表
            for message in messages:
                await self._add_pending_message(instance_id, message)
            
            return len(messages)
        
        except Exception as e:
            logger.error(f"获取监听对象 {instance_id}:{wxid} 的消息失败: {e}")
            return 0
    
    async def _add_pending_message(self, instance_id: str, message: Dict) -> None:
        """
        添加消息到待处理列表
        
        Args:
            instance_id: 实例ID
            message: 消息数据
        """
        # 添加实例ID和消息ID
        enriched_message = message.copy()
        enriched_message['instance_id'] = instance_id
        if 'id' not in enriched_message:
            enriched_message['id'] = str(uuid.uuid4())
        
        # 添加到待处理列表
        self._pending_messages.append(enriched_message)
        
        # 将消息保存到数据库
        try:
            timestamp = enriched_message.get('timestamp', int(time.time()))
            await db_manager.insert("messages", {
                "message_id": enriched_message['id'],
                "instance_id": instance_id,
                "sender": enriched_message.get('sender', ''),
                "receiver": enriched_message.get('receiver', ''),
                "content": enriched_message.get('content', ''),
                "timestamp": timestamp,
                "status": "pending",
                "retry_count": 0,
                "last_update": int(time.time())
            })
        except Exception as e:
            logger.error(f"保存消息到数据库失败: {e}")
    
    async def cleanup_timeout_listeners(self) -> int:
        """
        清理超时的监听对象
        
        Returns:
            int: 清理的监听对象数量
        """
        now = int(time.time())
        timeout_seconds = self.timeout_minutes * 60
        removed_count = 0
        
        to_remove = []
        
        async with self._lock:
            for (instance_id, wxid), data in self._listeners.items():
                last_time = data['last_time']
                
                # 检查是否超时
                if now - last_time > timeout_seconds:
                    to_remove.append((instance_id, wxid))
        
        # 移除超时的监听对象
        for instance_id, wxid in to_remove:
            if await self.remove_listener(instance_id, wxid):
                removed_count += 1
        
        if removed_count > 0:
            logger.info(f"已清理 {removed_count} 个超时的监听对象")
        
        return removed_count
    
    def get_pending_messages(self, max_count: int = 50) -> List[Dict]:
        """
        获取待处理的消息
        
        Args:
            max_count: 最大获取数量
            
        Returns:
            List[Dict]: 待处理的消息列表
        """
        if not self._pending_messages:
            return []
        
        # 获取指定数量的消息
        messages = self._pending_messages[:max_count]
        # 移除已获取的消息
        self._pending_messages = self._pending_messages[max_count:]
        
        return messages
    
    def get_listener_count(self) -> int:
        """
        获取当前监听对象数量
        
        Returns:
            int: 监听对象数量
        """
        return len(self._listeners)
    
    def get_listeners(self) -> List[Dict]:
        """
        获取当前所有监听对象
        
        Returns:
            List[Dict]: 监听对象列表
        """
        result = []
        
        for (instance_id, wxid), data in self._listeners.items():
            result.append({
                'instance_id': instance_id,
                'wxid': wxid,
                'last_time': data['last_time'],
                'create_time': data['create_time']
            })
        
        return result


# 创建全局消息监听管理器实例
message_listener = MessageListener() 