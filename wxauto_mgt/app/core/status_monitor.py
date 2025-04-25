"""
状态监控服务模块

负责监控WxAuto实例的状态和性能指标。定期检查微信状态、收集和存储消息处理统计数据、
监控系统性能，并提供状态报告和警报功能。
"""

import asyncio
import time
import json
import aiohttp
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, Union, Any
from datetime import datetime
import logging

from app.core.api_client import WxAutoApiClient, instance_manager
from app.data.db_manager import db_manager
from app.utils.logging import get_logger
from app.core.config_manager import config_manager, ConfigManager

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
        
        # 获取API配置
        self._config = ConfigManager()._config
        
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
                "uptime": 0
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
                status_data = await self.check_instance_status(instance_id)
                results[instance_id] = status_data
            except Exception as e:
                logger.error(f"检查实例 {instance_id} 状态失败: {e}")
                results[instance_id] = {
                    "status": InstanceStatus.ERROR,
                    "error": str(e)
                }
        
        return results
    
    async def _make_api_request(self, instance_id: str, endpoint: str) -> Optional[Dict]:
        """发送API请求
        
        Args:
            instance_id: 实例ID
            endpoint: API端点
            
        Returns:
            响应数据字典，如果请求失败则返回None
        """
        try:
            # 获取实例配置
            instance = instance_manager.get_instance(instance_id)
            if not instance:
                logger.error(f"实例不存在: {instance_id}")
                return None
                
            api_url = instance.base_url
            headers = {"X-API-Key": instance.api_key}
            
            full_url = f"{api_url}{endpoint}"
            logger.debug(f"发送API请求: {full_url}")
            logger.debug(f"请求头: {headers}")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(full_url, headers=headers) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.error(f"API请求失败: 状态码={response.status}, URL={full_url}")
                        response_text = await response.text()
                        logger.error(f"响应内容: {response_text}")
                        return None
        except Exception as e:
            logger.error(f"发送API请求时出错: {str(e)}, URL={api_url}{endpoint}")
            return None
            
    async def check_instance_status(self, instance_id: str) -> Dict[str, Any]:
        """检查实例状态
        
        Args:
            instance_id: 实例ID
            
        Returns:
            包含状态信息的字典
        """
        try:
            # 获取健康状态
            health_data = await self._make_api_request(instance_id, "/api/health")
            if not health_data:
                status = "error"
                uptime = 0
            else:
                # 从响应数据中正确提取状态信息
                data = health_data.get("data", {})
                raw_status = data.get("wechat_status", "error")
                
                # 状态值映射
                if raw_status == "not_initialized":
                    status = "未初始化"
                elif raw_status == "connected":
                    status = "状态正常"
                else:
                    status = raw_status
                    
                uptime = data.get("uptime", 0)
                
            # 获取系统资源信息
            resources_data = await self._make_api_request(instance_id, "/api/system/resources")
            if not resources_data:
                cpu_usage = 0
                memory_usage = 0
                memory_total = 0
            else:
                data = resources_data.get("data", {})
                cpu_data = data.get("cpu", {})
                memory_data = data.get("memory", {})
                
                # 获取CPU使用率
                cpu_usage = cpu_data.get("usage_percent", 0)
                
                # 获取内存使用情况
                memory_total = memory_data.get("total", 0)  # MB
                memory_used = memory_data.get("used", 0)   # MB
                memory_usage = memory_data.get("usage_percent", 0)
                
            # 更新状态缓存
            status_data = {
                "status": status,
                "raw_status": raw_status,  # 保存原始状态值以便UI层使用
                "last_check": datetime.now().timestamp()
            }
            self._instance_statuses[instance_id] = status_data
            
            # 更新性能指标缓存
            metrics_data = {
                "uptime": uptime,
                "message_count": 0,  # 暂时设置为0
                "cpu_usage": cpu_usage,
                "memory_usage": memory_used,  # 使用已用内存量（MB）
                "memory_total": memory_total,  # 总内存量（MB）
                "memory_percent": memory_usage,  # 内存使用率（%）
                "last_update": datetime.now().timestamp()
            }
            self._instance_metrics[instance_id] = metrics_data
            
            return status_data
            
        except Exception as e:
            logger.error(f"检查实例状态失败: {e}")
            status_data = {
                "status": "error",
                "uptime": 0,
                "error": str(e)
            }
            self._instance_statuses[instance_id] = status_data
            return status_data

    async def _get_message_count(self, instance_id: str) -> int:
        """获取消息数量"""
        # 暂时返回0，因为消息历史功能尚未实现
        return 0

    def add_status_listener(self, listener) -> None:
        """
        添加状态变更监听器
        
        Args:
            listener: 监听器函数，接收参数 (instance_id, status_data)
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
    
    async def _notify_status_listeners(self, instance_id: str, status_data: Dict) -> None:
        """
        通知所有状态变更监听器
        
        Args:
            instance_id: 实例ID
            status_data: 状态信息
        """
        for listener in self._status_listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener(instance_id, status_data)
                else:
                    listener(instance_id, status_data)
            except Exception as e:
                logger.error(f"通知状态监听器失败: {e}")
    
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
        if instance_id not in self._instance_metrics:
            self._instance_metrics[instance_id] = {}
        
        # 添加指标值
        self._instance_metrics[instance_id][metric_type] = value
        
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
        self.record_metric(instance_id, MetricType.MESSAGE_TOTAL, message_count)
        self.record_metric(instance_id, MetricType.MESSAGE_PROCESSED, processed_count)
        self.record_metric(instance_id, MetricType.MESSAGE_FAILED, failed_count)
        
        # 计算队列大小
        queue_size = message_count - processed_count - failed_count
        self.record_metric(instance_id, MetricType.MESSAGE_QUEUE, queue_size)
        
        logger.debug(f"记录实例 {instance_id} 消息统计: 总数={message_count}, 已处理={processed_count}, 失败={failed_count}, 队列={queue_size}")
    
    async def get_instance_status(self, instance_id: str) -> Optional[Dict]:
        """
        获取实例状态
        
        Args:
            instance_id: 实例ID
            
        Returns:
            Optional[Dict]: 状态信息，如果不存在则返回None
        """
        if not self.running:
            await self.start()
            
        if instance_id not in self._instance_statuses:
            await self.check_instance_status(instance_id)
        return self._instance_statuses.get(instance_id)
    
    def get_all_instance_statuses(self) -> Dict[str, Dict]:
        """
        获取所有实例状态
        
        Returns:
            Dict[str, Dict]: 实例状态字典，键为实例ID
        """
        return self._instance_statuses.copy()
    
    async def get_instance_metrics(self, instance_id: str) -> Dict:
        """
        获取实例性能指标
        
        Args:
            instance_id: 实例ID
            
        Returns:
            Dict: 性能指标字典
        """
        if instance_id not in self._instance_metrics:
            await self.check_instance_status(instance_id)
        return self._instance_metrics.get(instance_id, {})
    
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
        if instance_id is not None:
            query = f"SELECT * FROM status_logs WHERE instance_id = ? ORDER BY create_time DESC LIMIT {limit} OFFSET {offset}"
            params = (instance_id,)
        else:
            query = f"SELECT * FROM status_logs ORDER BY create_time DESC LIMIT {limit} OFFSET {offset}"
            params = ()
            
        try:
            rows = await db_manager.fetchall(query, params)
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"获取状态历史记录失败: {e}")
            return []
    
    async def get_metrics_history(self, instance_id: str, metric_type: Union[MetricType, str],
                                  limit: int = 100, offset: int = 0) -> List[Dict]:
        """
        获取性能指标历史记录
        
        Args:
            instance_id: 实例ID
            metric_type: 指标类型
            limit: 返回记录数量限制
            offset: 返回记录偏移量
            
        Returns:
            List[Dict]: 指标记录列表
        """
        # 转换为枚举类型
        if isinstance(metric_type, str):
            try:
                metric_type = MetricType(metric_type)
            except ValueError:
                logger.warning(f"未知的指标类型: {metric_type}")
                return []
                
        query = """
            SELECT * FROM performance_metrics 
            WHERE instance_id = ? AND metric_type = ? 
            ORDER BY create_time DESC 
            LIMIT ? OFFSET ?
        """
        params = (instance_id, metric_type.value, limit, offset)
        
        try:
            rows = await db_manager.fetchall(query, params)
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"获取性能指标历史记录失败: {e}")
            return []


# 创建全局状态监控服务实例
status_monitor = StatusMonitor() 