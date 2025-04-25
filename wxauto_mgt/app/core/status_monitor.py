"""
状态监控服务模块

负责监控WxAuto实例的状态和性能指标。定期检查微信状态、收集和存储消息处理统计数据、
监控系统性能，并提供状态报告和警报功能。
"""

import asyncio
import time
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, Union

from app.core.api_client import WxAutoApiClient, instance_manager
from app.data.db_manager import db_manager
from app.utils.logging import get_logger

logger = get_logger()


class InstanceStatus(Enum):
    """微信实例状态枚举"""
    OFFLINE = "offline"    # 离线
    ONLINE = "online"      # 在线
    ERROR = "error"        # 错误
    UNKNOWN = "unknown"    # 未知


class MetricType(Enum):
    """性能指标类型枚举"""
    MESSAGE_COUNT = "message_count"            # 消息数量
    MESSAGE_PROCESSED = "message_processed"    # 已处理消息
    MESSAGE_FAILED = "message_failed"          # 处理失败消息
    QUEUE_SIZE = "queue_size"                  # 队列大小
    RESPONSE_TIME = "response_time"            # 响应时间
    CPU_USAGE = "cpu_usage"                    # CPU使用率
    MEMORY_USAGE = "memory_usage"              # 内存使用率


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
        self._instance_statuses = {}  # 格式: {instance_id: {"status": InstanceStatus, "last_check": timestamp, "details": {...}}}
        self._performance_metrics = {}  # 格式: {instance_id: {metric_type: [values]}}
        self._status_listeners = set()  # 状态变更监听器
        
        logger.debug(f"初始化状态监控服务: 检查间隔={check_interval}秒")
    
    async def start(self) -> None:
        """
        启动监控服务
        """
        if self.running:
            logger.warning("状态监控服务已在运行")
            return
        
        logger.info("启动状态监控服务")
        self.running = True
        
        # 初始化实例状态
        for instance_id in instance_manager.list_instances():
            self._instance_statuses[instance_id] = {
                "status": InstanceStatus.UNKNOWN,
                "last_check": 0,
                "details": {}
            }
        
        # 启动状态检查任务
        self._status_task = asyncio.create_task(self._status_check_loop())
    
    async def stop(self) -> None:
        """
        停止监控服务
        """
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
        
        for instance_id, client in instance_manager.list_instances().items():
            try:
                status_data = await self.check_instance_status(instance_id, client)
                results[instance_id] = status_data
            except Exception as e:
                logger.error(f"检查实例 {instance_id} 状态失败: {e}")
                results[instance_id] = {
                    "status": InstanceStatus.ERROR,
                    "error": str(e)
                }
        
        return results
    
    async def check_instance_status(self, instance_id: str, client: WxAutoApiClient) -> Dict:
        """
        检查单个实例的状态
        
        Args:
            instance_id: 实例ID
            client: API客户端实例
            
        Returns:
            Dict: 状态信息
        """
        now = int(time.time())
        old_status = self._instance_statuses.get(instance_id, {}).get("status", InstanceStatus.UNKNOWN)
        
        try:
            # 获取微信状态
            status_result = await client.get_status()
            
            # 解析状态信息
            is_online = status_result.get("isOnline", False)
            
            if is_online:
                new_status = InstanceStatus.ONLINE
            else:
                new_status = InstanceStatus.OFFLINE
            
            # 构建状态数据
            status_data = {
                "status": new_status,
                "last_check": now,
                "details": status_result
            }
            
            # 更新状态字典
            self._instance_statuses[instance_id] = status_data
            
            # 记录状态变更
            if old_status != new_status:
                await self._record_status_change(instance_id, old_status, new_status, status_result)
                # 通知监听器
                await self._notify_status_listeners(instance_id, old_status, new_status)
            
            # 更新数据库中的实例状态
            await db_manager.update(
                "instances", 
                {"last_online_time": now if new_status == InstanceStatus.ONLINE else None},
                "instance_id = ?",
                [instance_id]
            )
            
            return status_data
            
        except Exception as e:
            # 发生错误
            new_status = InstanceStatus.ERROR
            
            # 构建错误状态数据
            status_data = {
                "status": new_status,
                "last_check": now,
                "details": {"error": str(e)}
            }
            
            # 更新状态字典
            self._instance_statuses[instance_id] = status_data
            
            # 记录状态变更
            if old_status != new_status:
                await self._record_status_change(instance_id, old_status, new_status, {"error": str(e)})
                # 通知监听器
                await self._notify_status_listeners(instance_id, old_status, new_status)
            
            raise
    
    async def _record_status_change(self, instance_id: str, old_status: InstanceStatus, 
                                  new_status: InstanceStatus, details: Dict) -> None:
        """
        记录状态变更
        
        Args:
            instance_id: 实例ID
            old_status: 旧状态
            new_status: 新状态
            details: 状态详情
        """
        try:
            # 保存到数据库
            await db_manager.insert("status_logs", {
                "instance_id": instance_id,
                "status": new_status.value,
                "details": str(details),
                "create_time": int(time.time())
            })
            
            logger.info(f"实例 {instance_id} 状态从 {old_status.value} 变更为 {new_status.value}")
        except Exception as e:
            logger.error(f"记录状态变更失败: {e}")
    
    def add_status_listener(self, listener) -> None:
        """
        添加状态变更监听器
        
        Args:
            listener: 监听器函数，接收参数 (instance_id, old_status, new_status)
        """
        self._status_listeners.add(listener)
    
    def remove_status_listener(self, listener) -> None:
        """
        移除状态变更监听器
        
        Args:
            listener: 监听器函数
        """
        if listener in self._status_listeners:
            self._status_listeners.remove(listener)
    
    async def _notify_status_listeners(self, instance_id: str, old_status: InstanceStatus, 
                                     new_status: InstanceStatus) -> None:
        """
        通知所有状态变更监听器
        
        Args:
            instance_id: 实例ID
            old_status: 旧状态
            new_status: 新状态
        """
        for listener in self._status_listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener(instance_id, old_status, new_status)
                else:
                    listener(instance_id, old_status, new_status)
            except Exception as e:
                logger.error(f"调用状态监听器失败: {e}")
    
    def record_metric(self, instance_id: str, metric_type: Union[MetricType, str], value: float) -> None:
        """
        记录性能指标
        
        Args:
            instance_id: 实例ID
            metric_type: 指标类型
            value: 指标值
        """
        # 转换为枚举类型
        if isinstance(metric_type, str):
            try:
                metric_type = MetricType(metric_type)
            except ValueError:
                logger.warning(f"未知的指标类型: {metric_type}")
                return
        
        # 初始化实例指标字典
        if instance_id not in self._performance_metrics:
            self._performance_metrics[instance_id] = {}
        
        # 初始化指标类型列表
        if metric_type not in self._performance_metrics[instance_id]:
            self._performance_metrics[instance_id][metric_type] = []
        
        # 添加指标值
        self._performance_metrics[instance_id][metric_type].append(value)
        
        # 最多保留100个值
        if len(self._performance_metrics[instance_id][metric_type]) > 100:
            self._performance_metrics[instance_id][metric_type].pop(0)
        
        # 异步保存到数据库
        asyncio.create_task(self._save_metric_to_db(instance_id, metric_type, value))
    
    async def _save_metric_to_db(self, instance_id: str, metric_type: MetricType, value: float) -> None:
        """
        保存指标到数据库
        
        Args:
            instance_id: 实例ID
            metric_type: 指标类型
            value: 指标值
        """
        try:
            await db_manager.insert("performance_metrics", {
                "instance_id": instance_id,
                "metric_type": metric_type.value,
                "metric_value": value,
                "create_time": int(time.time())
            })
        except Exception as e:
            logger.error(f"保存性能指标到数据库失败: {e}")
    
    def record_message_stats(self, instance_id: str, message_count: int, 
                           processed_count: int, failed_count: int) -> None:
        """
        记录消息统计数据
        
        Args:
            instance_id: 实例ID
            message_count: 消息总数
            processed_count: 已处理消息数
            failed_count: 处理失败消息数
        """
        # 记录各项指标
        self.record_metric(instance_id, MetricType.MESSAGE_COUNT, message_count)
        self.record_metric(instance_id, MetricType.MESSAGE_PROCESSED, processed_count)
        self.record_metric(instance_id, MetricType.MESSAGE_FAILED, failed_count)
        
        # 计算队列大小
        queue_size = message_count - processed_count - failed_count
        self.record_metric(instance_id, MetricType.QUEUE_SIZE, queue_size)
        
        logger.debug(f"记录实例 {instance_id} 消息统计: 总数={message_count}, 已处理={processed_count}, 失败={failed_count}, 队列={queue_size}")
    
    def get_instance_status(self, instance_id: str) -> Optional[Dict]:
        """
        获取实例状态
        
        Args:
            instance_id: 实例ID
            
        Returns:
            Optional[Dict]: 状态信息，如果不存在则返回None
        """
        return self._instance_statuses.get(instance_id)
    
    def get_all_instance_statuses(self) -> Dict[str, Dict]:
        """
        获取所有实例状态
        
        Returns:
            Dict[str, Dict]: 实例状态字典，键为实例ID
        """
        return self._instance_statuses.copy()
    
    def get_instance_metrics(self, instance_id: str, metric_type: Optional[Union[MetricType, str]] = None) -> Dict:
        """
        获取实例性能指标
        
        Args:
            instance_id: 实例ID
            metric_type: 指标类型，如果为None则返回所有类型
            
        Returns:
            Dict: 性能指标字典
        """
        if instance_id not in self._performance_metrics:
            return {}
        
        if metric_type is None:
            return self._performance_metrics[instance_id].copy()
        
        # 转换为枚举类型
        if isinstance(metric_type, str):
            try:
                metric_type = MetricType(metric_type)
            except ValueError:
                logger.warning(f"未知的指标类型: {metric_type}")
                return {}
        
        return {metric_type: self._performance_metrics[instance_id].get(metric_type, [])}
    
    async def get_status_history(self, instance_id: Optional[str] = None, 
                             limit: int = 100, offset: int = 0) -> List[Dict]:
        """
        获取状态历史记录
        
        Args:
            instance_id: 实例ID，如果为None则返回所有实例
            limit: 返回记录数量限制
            offset: 返回记录偏移量
            
        Returns:
            List[Dict]: 状态记录列表
        """
        if limit > 0:
            query = f"SELECT * FROM status_logs WHERE instance_id = ? ORDER BY create_time DESC LIMIT {limit} OFFSET {offset}"
            params = (instance_id,)
        else:
            query = "SELECT * FROM status_logs ORDER BY create_time DESC LIMIT ? OFFSET ?"
            params = (limit, offset)
        
        try:
            rows = await db_manager.fetchall(query, params)
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"获取状态历史记录失败: {e}")
            return []
    
    async def get_performance_history(self, instance_id: str, metric_type: Union[MetricType, str],
                                  limit: int = 100, offset: int = 0) -> List[Dict]:
        """
        获取性能指标历史记录
        
        Args:
            instance_id: 实例ID
            metric_type: 指标类型
            limit: 返回记录数量限制
            offset: 返回记录偏移量
            
        Returns:
            List[Dict]: 性能指标记录列表
        """
        # 转换为枚举值
        if isinstance(metric_type, MetricType):
            metric_type = metric_type.value
        
        try:
            query = """
            SELECT * FROM performance_metrics 
            WHERE instance_id = ? AND metric_type = ?
            ORDER BY create_time DESC LIMIT ? OFFSET ?
            """
            params = (instance_id, metric_type, limit, offset)
            
            rows = await db_manager.fetchall(query, params)
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"获取性能指标历史记录失败: {e}")
            return []


# 创建全局状态监控服务实例
status_monitor = StatusMonitor() 