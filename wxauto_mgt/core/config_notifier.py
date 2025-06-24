"""
配置变更通知模块

该模块负责在配置发生变更时通知相关服务进行重新加载。
"""

import asyncio
import logging
import time
from typing import Dict, List, Callable, Any
from enum import Enum

logger = logging.getLogger(__name__)

class ConfigChangeType(Enum):
    """配置变更类型"""
    PLATFORM_ADDED = "platform_added"
    PLATFORM_UPDATED = "platform_updated"
    PLATFORM_DELETED = "platform_deleted"
    PLATFORM_ENABLED = "platform_enabled"
    PLATFORM_DISABLED = "platform_disabled"
    
    RULE_ADDED = "rule_added"
    RULE_UPDATED = "rule_updated"
    RULE_DELETED = "rule_deleted"
    RULE_ENABLED = "rule_enabled"
    RULE_DISABLED = "rule_disabled"
    
    INSTANCE_ADDED = "instance_added"
    INSTANCE_UPDATED = "instance_updated"
    INSTANCE_DELETED = "instance_deleted"

class ConfigChangeEvent:
    """配置变更事件"""
    
    def __init__(self, change_type: ConfigChangeType, data: Dict[str, Any], timestamp: float = None):
        self.change_type = change_type
        self.data = data
        self.timestamp = timestamp or time.time()
    
    def __str__(self):
        return f"ConfigChangeEvent({self.change_type.value}, {self.data}, {self.timestamp})"

class ConfigNotifier:
    """配置变更通知器"""
    
    def __init__(self):
        self._listeners: Dict[ConfigChangeType, List[Callable]] = {}
        self._global_listeners: List[Callable] = []
        self._lock = asyncio.Lock()
        self._enabled = True
    
    async def subscribe(self, change_type: ConfigChangeType, callback: Callable):
        """
        订阅特定类型的配置变更事件
        
        Args:
            change_type: 变更类型
            callback: 回调函数，接收 ConfigChangeEvent 参数
        """
        async with self._lock:
            if change_type not in self._listeners:
                self._listeners[change_type] = []
            self._listeners[change_type].append(callback)
            logger.debug(f"订阅配置变更事件: {change_type.value}")
    
    async def subscribe_all(self, callback: Callable):
        """
        订阅所有配置变更事件
        
        Args:
            callback: 回调函数，接收 ConfigChangeEvent 参数
        """
        async with self._lock:
            self._global_listeners.append(callback)
            logger.debug("订阅所有配置变更事件")
    
    async def unsubscribe(self, change_type: ConfigChangeType, callback: Callable):
        """
        取消订阅特定类型的配置变更事件
        
        Args:
            change_type: 变更类型
            callback: 回调函数
        """
        async with self._lock:
            if change_type in self._listeners:
                try:
                    self._listeners[change_type].remove(callback)
                    logger.debug(f"取消订阅配置变更事件: {change_type.value}")
                except ValueError:
                    pass
    
    async def unsubscribe_all(self, callback: Callable):
        """
        取消订阅所有配置变更事件
        
        Args:
            callback: 回调函数
        """
        async with self._lock:
            try:
                self._global_listeners.remove(callback)
                logger.debug("取消订阅所有配置变更事件")
            except ValueError:
                pass
    
    async def notify(self, change_type: ConfigChangeType, data: Dict[str, Any]):
        """
        发送配置变更通知
        
        Args:
            change_type: 变更类型
            data: 变更数据
        """
        if not self._enabled:
            return
        
        event = ConfigChangeEvent(change_type, data)
        logger.info(f"发送配置变更通知: {event}")
        
        # 通知特定类型的监听器
        async with self._lock:
            listeners = self._listeners.get(change_type, []).copy()
            global_listeners = self._global_listeners.copy()
        
        # 异步通知所有监听器
        tasks = []
        
        # 通知特定类型监听器
        for callback in listeners:
            tasks.append(self._safe_notify(callback, event))
        
        # 通知全局监听器
        for callback in global_listeners:
            tasks.append(self._safe_notify(callback, event))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _safe_notify(self, callback: Callable, event: ConfigChangeEvent):
        """
        安全地调用回调函数
        
        Args:
            callback: 回调函数
            event: 配置变更事件
        """
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(event)
            else:
                callback(event)
        except Exception as e:
            logger.error(f"配置变更通知回调函数执行失败: {e}")
            logger.exception(e)
    
    def enable(self):
        """启用通知器"""
        self._enabled = True
        logger.info("配置变更通知器已启用")
    
    def disable(self):
        """禁用通知器"""
        self._enabled = False
        logger.info("配置变更通知器已禁用")
    
    def is_enabled(self) -> bool:
        """检查通知器是否启用"""
        return self._enabled
    
    async def clear_all_listeners(self):
        """清除所有监听器"""
        async with self._lock:
            self._listeners.clear()
            self._global_listeners.clear()
            logger.info("已清除所有配置变更监听器")

# 创建全局实例
config_notifier = ConfigNotifier()
