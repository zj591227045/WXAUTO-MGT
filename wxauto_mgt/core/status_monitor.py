"""
状态监控模块

负责监控微信实例的状态，包括在线状态、性能指标等。
"""

import asyncio
import logging
import time
from enum import Enum
from typing import Dict, Optional, List

from wxauto_mgt.core.api_client import instance_manager
from wxauto_mgt.data.db_manager import db_manager

logger = logging.getLogger(__name__)

class InstanceStatus(Enum):
    """实例状态枚举"""
    ONLINE = "online"      # 在线
    OFFLINE = "offline"    # 离线
    ERROR = "error"        # 错误
    UNKNOWN = "unknown"    # 未知

class MetricType(Enum):
    """性能指标类型枚举"""
    CPU_USAGE = "cpu_usage"        # CPU使用率
    MEMORY_USAGE = "memory_usage"  # 内存使用率
    MESSAGE_COUNT = "msg_count"    # 消息数量
    UPTIME = "uptime"             # 运行时间

class StatusMonitor:
    """状态监控器，负责监控实例状态"""
    
    def __init__(self, check_interval: int = 30):
        """
        初始化状态监控器
        
        Args:
            check_interval: 状态检查间隔（秒）
        """
        self.check_interval = check_interval
        self._status_cache: Dict[str, Dict] = {}
        self._metrics_cache: Dict[str, Dict[str, float]] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        self._statuses = {}  # 存储每个实例的状态
    
    async def start(self):
        """启动监控"""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("状态监控已启动")
    
    async def stop(self):
        """停止监控"""
        if not self._running:
            return
        
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("状态监控已停止")
    
    async def _monitor_loop(self):
        """监控循环"""
        while self._running:
            try:
                await self._check_all_instances()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"状态检查失败: {e}")
                await asyncio.sleep(self.check_interval)
    
    async def _check_all_instances(self):
        """检查所有实例状态"""
        instances = instance_manager.get_all_instances()
        
        async with self._lock:
            for instance_id, api_client in instances.items():
                try:
                    # 检查实例状态
                    status = await self._check_instance(instance_id, api_client)
                    
                    # 更新缓存
                    self._status_cache[instance_id] = {
                        "status": status,
                        "last_check": time.time()
                    }
                    
                    # 获取性能指标
                    metrics = await self._get_instance_metrics(instance_id, api_client)
                    if metrics:
                        self._metrics_cache[instance_id] = metrics
                    
                    # 保存到数据库
                    await self._save_status(instance_id, status)
                    if metrics:
                        await self._save_metrics(instance_id, metrics)
                    
                except Exception as e:
                    logger.error(f"检查实例 {instance_id} 状态失败: {e}")
                    self._status_cache[instance_id] = {
                        "status": InstanceStatus.ERROR,
                        "last_check": time.time()
                    }
    
    async def _check_instance(self, instance_id: str, api_client) -> InstanceStatus:
        """
        检查单个实例状态
        
        Args:
            instance_id: 实例ID
            api_client: API客户端
            
        Returns:
            InstanceStatus: 实例状态
        """
        try:
            # 调用API检查状态
            status = await api_client.get_status()
            return InstanceStatus.ONLINE if status else InstanceStatus.OFFLINE
        except Exception as e:
            logger.error(f"获取实例 {instance_id} 状态失败: {e}")
            return InstanceStatus.ERROR
    
    async def _get_instance_metrics(self, instance_id: str, api_client) -> Optional[Dict[str, float]]:
        """
        获取实例性能指标
        
        Args:
            instance_id: 实例ID
            api_client: API客户端
            
        Returns:
            Optional[Dict[str, float]]: 性能指标数据
        """
        try:
            # 调用API获取性能指标
            metrics = await api_client.get_metrics()
            if not metrics:
                return None
                
            return {
                MetricType.CPU_USAGE.value: metrics.get("cpu_usage", 0.0),
                MetricType.MEMORY_USAGE.value: metrics.get("memory_usage", 0.0),
                MetricType.MESSAGE_COUNT.value: metrics.get("msg_count", 0),
                MetricType.UPTIME.value: metrics.get("uptime", 0)
            }
        except Exception as e:
            logger.error(f"获取实例 {instance_id} 性能指标失败: {e}")
            return None
    
    async def _save_status(self, instance_id: str, status: InstanceStatus):
        """
        保存状态到数据库
        
        Args:
            instance_id: 实例ID
            status: 实例状态
        """
        try:
            data = {
                "instance_id": instance_id,
                "status": status.value,
                "create_time": int(time.time())
            }
            await db_manager.insert("status_logs", data)
            
            # 更新实例表
            await db_manager.execute(
                "UPDATE instances SET status = ?, last_active = ? WHERE instance_id = ?",
                (status.value, int(time.time()), instance_id)
            )
        except Exception as e:
            logger.error(f"保存状态失败: {e}")
    
    async def _save_metrics(self, instance_id: str, metrics: Dict[str, float]):
        """
        保存性能指标到数据库
        
        Args:
            instance_id: 实例ID
            metrics: 性能指标数据
        """
        try:
            current_time = int(time.time())
            for metric_type, value in metrics.items():
                data = {
                    "instance_id": instance_id,
                    "metric_type": metric_type,
                    "value": value,
                    "create_time": current_time
                }
                await db_manager.insert("performance_metrics", data)
        except Exception as e:
            logger.error(f"保存性能指标失败: {e}")
    
    async def get_instance_status(self, instance_id: str) -> Dict:
        """获取实例状态"""
        try:
            # 获取API客户端
            client = instance_manager.get_instance(instance_id)
            
            if not client:
                logger.warning(f"找不到实例的API客户端: {instance_id}")
                return {"isOnline": False, "status": InstanceStatus.OFFLINE.value}
            
            # 通过API获取状态
            status_data = await client.get_status()
            if not status_data:
                status_data = {"isOnline": False}
                
            # 更新内部状态记录
            async with self._lock:
                self._statuses[instance_id] = {
                    "status": InstanceStatus.ONLINE if status_data.get("isOnline") else InstanceStatus.OFFLINE,
                    "last_check": int(time.time())
                }
                
            logger.debug(f"获取实例状态: {instance_id}, 状态: {status_data}")
            return status_data
        except Exception as e:
            logger.error(f"获取实例状态失败: {e}")
            
            # 更新为错误状态
            async with self._lock:
                self._statuses[instance_id] = {
                    "status": InstanceStatus.ERROR,
                    "last_check": int(time.time()),
                    "error": str(e)
                }
                
            return {"isOnline": False, "status": InstanceStatus.ERROR.value, "error": str(e)}
    
    def get_all_instance_statuses(self) -> Dict[str, Dict]:
        """
        获取所有实例的状态
        
        Returns:
            Dict[str, Dict]: 实例状态字典，key为实例ID
        """
        return self._statuses.copy()
        
    async def get_instance_metrics(self, instance_id: str) -> Optional[Dict]:
        """
        获取实例性能指标
        
        Args:
            instance_id: 实例ID
            
        Returns:
            Optional[Dict]: 性能指标字典
        """
        try:
            client = instance_manager.get_instance(instance_id)
            
            if not client:
                logger.warning(f"找不到实例的API客户端: {instance_id}")
                return None
                
            # 获取系统资源指标
            metrics = await client.get_system_metrics()
            return metrics
        except Exception as e:
            logger.error(f"获取实例性能指标失败: {e}")
            return None

# 创建全局实例
status_monitor = StatusMonitor() 