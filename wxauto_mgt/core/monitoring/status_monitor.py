"""
状态监控服务模块

负责监控WxAuto实例的状态和性能指标。定期检查微信状态、收集和存储消息处理统计数据、
监控系统性能，并提供状态报告和警报功能。支持多实例管理。
"""

import asyncio
import time
import json
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, Union, Any
from datetime import datetime
import logging

from ..api_client import WxAutoApiClient, instance_manager
from ...data.db_manager import db_manager

logger = logging.getLogger(__name__)

class InstanceStatus(Enum):
    """微信实例状态枚举"""
    OFFLINE = "offline"    # 离线
    ONLINE = "online"      # 在线
    ERROR = "error"        # 错误
    UNKNOWN = "unknown"    # 未知

class MetricType(Enum):
    """性能指标类型枚举"""
    MESSAGE_COUNT = "message_count"            # 消息数量
    UPTIME = "uptime"                         # 运行时间
    CPU_USAGE = "cpu_usage"                   # CPU使用率
    MEMORY_USAGE = "memory_usage"              # 内存使用率
    MESSAGE_TOTAL = "message_total"            # 消息总数
    MESSAGE_PROCESSED = "message_processed"      # 已处理消息数
    MESSAGE_FAILED = "message_failed"            # 处理失败消息数
    MESSAGE_QUEUE = "message_queue"              # 消息队列大小

class StatusMonitor:
    """
    状态监控服务，负责监控WxAuto实例的状态和性能指标
    """
    
    def __init__(self, check_interval: int = 60):
        """
        初始化状态监控服务
        
        Args:
            check_interval: 状态检查间隔（秒）
        """
        self.check_interval = check_interval
        self.running = False
        self._status_task = None
        self._instance_statuses = {}  # 实例状态缓存
        self._instance_metrics = {}   # 实例性能指标缓存
        self._status_listeners = set()  # 状态变更监听器
        
        logger.debug(f"初始化状态监控服务: 检查间隔={check_interval}秒")
    
    async def start(self) -> None:
        """启动监控服务"""
        if self.running:
            logger.warning("状态监控服务已在运行")
            return
        
        logger.info("启动状态监控服务")
        self.running = True
        
        # 初始化实例状态
        for instance_id in instance_manager.get_all_instances():
            self._instance_statuses[instance_id] = {
                "status": InstanceStatus.UNKNOWN,
                "uptime": 0
            }
        
        # 启动状态检查任务
        self._status_task = asyncio.create_task(self._status_check_loop())
    
    async def stop(self) -> None:
        """停止监控服务"""
        if not self.running:
            logger.warning("状态监控服务未运行")
            return
        
        logger.info("停止状态监控服务")
        self.running = False
        
        # 取消状态检查任务
        if self._status_task:
            self._status_task.cancel()
            try:
                await self._status_task
            except asyncio.CancelledError:
                pass
            
            self._status_task = None
        
        logger.info("状态监控服务已停止")
    
    async def _status_check_loop(self) -> None:
        """状态检查循环"""
        logger.info("启动状态检查循环")
        
        while self.running:
            try:
                await self.check_all_instances()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                logger.info("状态检查循环已取消")
                break
            except Exception as e:
                logger.error(f"状态检查循环出错: {e}")
                await asyncio.sleep(self.check_interval)
    
    async def check_all_instances(self) -> Dict[str, Dict]:
        """
        检查所有实例的状态
        
        Returns:
            Dict[str, Dict]: 实例状态字典，键为实例ID
        """
        results = {}
        
        for instance_id, client in instance_manager.get_all_instances().items():
            try:
                status_data = await self.check_instance_status(instance_id)
                results[instance_id] = status_data
            except Exception as e:
                logger.error(f"检查实例 {instance_id} 状态失败: {e}")
                results[instance_id] = {
                    "status": InstanceStatus.ERROR,
                    "error": str(e)
                }
        
        return results
            
    async def check_instance_status(self, instance_id: str) -> Dict[str, Any]:
        """
        检查实例状态
        
        Args:
            instance_id: 实例ID
            
        Returns:
            包含状态信息的字典
        """
        try:
            client = instance_manager.get_instance(instance_id)
            if not client:
                raise ValueError(f"实例不存在: {instance_id}")
            
            # 获取微信状态
            status_data = await client.get_status()
            status = "online" if status_data.get("isOnline", False) else "offline"
            
            # 获取系统资源信息
            metrics = await client.get_system_metrics()
            
            # 更新状态缓存
            status_data = {
                "status": status,
                "last_check": datetime.now().timestamp(),
                "metrics": metrics
            }
            self._instance_statuses[instance_id] = status_data
            
            # 保存性能指标
            await self._save_metrics(instance_id, metrics)
            
            # 通知状态监听器
            await self._notify_status_listeners(instance_id, status_data)
            
            return status_data
        except Exception as e:
            logger.error(f"检查实例状态失败: {e}")
            return {
                "status": "error",
                "error": str(e),
                "last_check": datetime.now().timestamp()
            }
    
    async def _save_metrics(self, instance_id: str, metrics: Dict[str, Any]) -> None:
        """
        保存性能指标到数据库
        
        Args:
            instance_id: 实例ID
            metrics: 性能指标数据
        """
        try:
            now = int(time.time())
            
            # 保存CPU使用率
            await db_manager.insert("performance_metrics", {
                "instance_id": instance_id,
                "metric_type": MetricType.CPU_USAGE.value,
                "value": metrics.get("cpu_usage", 0),
                "create_time": now
            })
            
            # 保存内存使用率
            await db_manager.insert("performance_metrics", {
                "instance_id": instance_id,
                "metric_type": MetricType.MEMORY_USAGE.value,
                "value": metrics.get("memory_usage", 0),
                "create_time": now
            })
            
        except Exception as e:
            logger.error(f"保存性能指标失败: {e}")
    
    def add_status_listener(self, listener) -> None:
        """添加状态监听器"""
        self._status_listeners.add(listener)
    
    def remove_status_listener(self, listener) -> None:
        """移除状态监听器"""
        self._status_listeners.discard(listener)
    
    async def _notify_status_listeners(self, instance_id: str, status_data: Dict) -> None:
        """通知状态监听器"""
        for listener in self._status_listeners:
            try:
                await listener(instance_id, status_data)
            except Exception as e:
                logger.error(f"通知状态监听器失败: {e}")
    
    async def get_instance_status(self, instance_id: str) -> Optional[Dict]:
        """获取实例状态"""
        return self._instance_statuses.get(instance_id)
    
    def get_all_instance_statuses(self) -> Dict[str, Dict]:
        """获取所有实例状态"""
        return self._instance_statuses.copy()
    
    async def get_metrics_history(self, 
                                instance_id: str,
                                metric_type: Union[MetricType, str],
                                start_time: Optional[int] = None,
                                end_time: Optional[int] = None,
                                limit: int = 100) -> List[Dict]:
        """
        获取性能指标历史数据
        
        Args:
            instance_id: 实例ID
            metric_type: 指标类型
            start_time: 开始时间戳
            end_time: 结束时间戳
            limit: 返回记录数量限制
            
        Returns:
            List[Dict]: 指标历史数据列表
        """
        try:
            conditions = ["instance_id = ?", "metric_type = ?"]
            params = [instance_id, metric_type.value if isinstance(metric_type, MetricType) else metric_type]
            
            if start_time:
                conditions.append("create_time >= ?")
                params.append(start_time)
            
            if end_time:
                conditions.append("create_time <= ?")
                params.append(end_time)
            
            sql = f"""
                SELECT * FROM performance_metrics 
                WHERE {' AND '.join(conditions)}
                ORDER BY create_time DESC
                LIMIT ?
            """
            params.append(limit)
            
            return await db_manager.fetchall(sql, params)
        except Exception as e:
            logger.error(f"获取性能指标历史失败: {e}")
            return []

# 创建全局实例
status_monitor = StatusMonitor() 