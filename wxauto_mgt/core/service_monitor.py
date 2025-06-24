"""
服务状态监控模块

该模块负责监控消息监听服务的运行状态，提供诊断信息和健康检查功能。
"""

import asyncio
import logging
import time
import psutil
import os
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

@dataclass
class ServiceStatus:
    """服务状态信息"""
    service_name: str
    running: bool
    start_time: float
    uptime_seconds: float
    task_count: int
    error_count: int
    last_error_time: Optional[float]
    last_error_message: Optional[str]
    memory_usage_mb: float
    cpu_percent: float

@dataclass
class APIClientStatus:
    """API客户端状态信息"""
    instance_id: str
    initialized: bool
    connected: bool
    last_check_time: float
    error_count: int
    last_error: Optional[str]

@dataclass
class ListenerStatus:
    """监听对象状态信息"""
    instance_id: str
    who: str
    active: bool
    last_message_time: float
    last_check_time: float
    message_count: int
    error_count: int

class ServiceMonitor:
    """服务状态监控器"""
    
    def __init__(self):
        self._start_time = time.time()
        self._error_history: List[Dict[str, Any]] = []
        self._max_error_history = 100
        self._monitoring_enabled = True
        
        # 性能统计
        self._stats = {
            'total_messages_processed': 0,
            'total_errors': 0,
            'api_calls_made': 0,
            'listeners_added': 0,
            'listeners_removed': 0,
            'config_reloads': 0
        }
    
    def record_error(self, service_name: str, error_message: str, error_type: str = "general"):
        """记录错误信息"""
        if not self._monitoring_enabled:
            return
        
        error_record = {
            'timestamp': time.time(),
            'service_name': service_name,
            'error_type': error_type,
            'error_message': str(error_message),
            'datetime': datetime.now().isoformat()
        }
        
        self._error_history.append(error_record)
        self._stats['total_errors'] += 1
        
        # 保持错误历史记录在限制范围内
        if len(self._error_history) > self._max_error_history:
            self._error_history = self._error_history[-self._max_error_history:]
        
        logger.debug(f"记录错误: {service_name} - {error_message}")
    
    def record_message_processed(self):
        """记录处理的消息数量"""
        if self._monitoring_enabled:
            self._stats['total_messages_processed'] += 1
    
    def record_api_call(self):
        """记录API调用次数"""
        if self._monitoring_enabled:
            self._stats['api_calls_made'] += 1
    
    def record_listener_added(self):
        """记录添加的监听对象数量"""
        if self._monitoring_enabled:
            self._stats['listeners_added'] += 1
    
    def record_listener_removed(self):
        """记录移除的监听对象数量"""
        if self._monitoring_enabled:
            self._stats['listeners_removed'] += 1
    
    def record_config_reload(self):
        """记录配置重新加载次数"""
        if self._monitoring_enabled:
            self._stats['config_reloads'] += 1
    
    async def get_message_listener_status(self) -> ServiceStatus:
        """获取消息监听器状态"""
        try:
            from wxauto_mgt.core.message_listener import message_listener
            
            # 计算运行时间
            current_time = time.time()
            uptime = current_time - self._start_time
            
            # 获取最近的错误信息
            recent_errors = [e for e in self._error_history if e['service_name'] == 'message_listener']
            last_error_time = recent_errors[-1]['timestamp'] if recent_errors else None
            last_error_message = recent_errors[-1]['error_message'] if recent_errors else None
            
            # 获取系统资源使用情况
            process = psutil.Process(os.getpid())
            memory_usage = process.memory_info().rss / 1024 / 1024  # MB
            cpu_percent = process.cpu_percent()
            
            # 获取任务数量
            task_count = len(message_listener._tasks) if hasattr(message_listener, '_tasks') else 0
            
            return ServiceStatus(
                service_name="message_listener",
                running=message_listener.running,
                start_time=self._start_time,
                uptime_seconds=uptime,
                task_count=task_count,
                error_count=len(recent_errors),
                last_error_time=last_error_time,
                last_error_message=last_error_message,
                memory_usage_mb=memory_usage,
                cpu_percent=cpu_percent
            )
        except Exception as e:
            logger.error(f"获取消息监听器状态失败: {e}")
            return ServiceStatus(
                service_name="message_listener",
                running=False,
                start_time=self._start_time,
                uptime_seconds=0,
                task_count=0,
                error_count=0,
                last_error_time=None,
                last_error_message=str(e),
                memory_usage_mb=0,
                cpu_percent=0
            )
    
    async def get_api_clients_status(self) -> List[APIClientStatus]:
        """获取所有API客户端状态"""
        try:
            from wxauto_mgt.core.api_client import instance_manager
            
            statuses = []
            instances = instance_manager.get_all_instances()
            
            for instance_id, api_client in instances.items():
                # 获取该实例的错误记录
                instance_errors = [e for e in self._error_history if instance_id in e.get('error_message', '')]
                last_error = instance_errors[-1]['error_message'] if instance_errors else None
                
                # 检查连接状态
                connected = False
                try:
                    if hasattr(api_client, 'health_check'):
                        connected = await api_client.health_check()
                    else:
                        connected = getattr(api_client, 'initialized', False)
                except:
                    connected = False
                
                status = APIClientStatus(
                    instance_id=instance_id,
                    initialized=getattr(api_client, 'initialized', False),
                    connected=connected,
                    last_check_time=time.time(),
                    error_count=len(instance_errors),
                    last_error=last_error
                )
                statuses.append(status)
            
            return statuses
        except Exception as e:
            logger.error(f"获取API客户端状态失败: {e}")
            return []
    
    async def get_listeners_status(self) -> List[ListenerStatus]:
        """获取所有监听对象状态"""
        try:
            from wxauto_mgt.core.message_listener import message_listener
            
            statuses = []
            
            if hasattr(message_listener, 'listeners'):
                for instance_id, listeners_dict in message_listener.listeners.items():
                    for who, info in listeners_dict.items():
                        # 从数据库获取消息统计
                        try:
                            from wxauto_mgt.data.db_manager import db_manager
                            message_count_result = await db_manager.fetchone(
                                "SELECT COUNT(*) as count FROM messages WHERE instance_id = ? AND chat_name = ?",
                                (instance_id, who)
                            )
                            message_count = message_count_result['count'] if message_count_result else 0
                        except:
                            message_count = 0
                        
                        status = ListenerStatus(
                            instance_id=instance_id,
                            who=who,
                            active=info.active,
                            last_message_time=info.last_message_time,
                            last_check_time=info.last_check_time,
                            message_count=message_count,
                            error_count=0  # 可以后续添加监听对象级别的错误统计
                        )
                        statuses.append(status)
            
            return statuses
        except Exception as e:
            logger.error(f"获取监听对象状态失败: {e}")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        current_time = time.time()
        uptime = current_time - self._start_time
        
        stats = self._stats.copy()
        stats.update({
            'uptime_seconds': uptime,
            'uptime_formatted': str(timedelta(seconds=int(uptime))),
            'start_time': datetime.fromtimestamp(self._start_time).isoformat(),
            'current_time': datetime.fromtimestamp(current_time).isoformat(),
            'error_rate': self._stats['total_errors'] / max(1, self._stats['total_messages_processed']),
            'recent_errors_count': len([e for e in self._error_history if current_time - e['timestamp'] < 3600])  # 最近1小时的错误
        })
        
        return stats
    
    def get_recent_errors(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近的错误记录"""
        return self._error_history[-limit:] if self._error_history else []
    
    async def generate_health_report(self) -> Dict[str, Any]:
        """生成健康状况报告"""
        try:
            # 获取各组件状态
            listener_status = await self.get_message_listener_status()
            api_clients_status = await self.get_api_clients_status()
            listeners_status = await self.get_listeners_status()
            statistics = self.get_statistics()
            recent_errors = self.get_recent_errors()
            
            # 计算健康分数
            health_score = self._calculate_health_score(
                listener_status, api_clients_status, listeners_status, statistics
            )
            
            return {
                'timestamp': datetime.now().isoformat(),
                'health_score': health_score,
                'overall_status': 'healthy' if health_score >= 80 else 'warning' if health_score >= 60 else 'critical',
                'message_listener': asdict(listener_status),
                'api_clients': [asdict(status) for status in api_clients_status],
                'listeners': [asdict(status) for status in listeners_status],
                'statistics': statistics,
                'recent_errors': recent_errors
            }
        except Exception as e:
            logger.error(f"生成健康报告失败: {e}")
            return {
                'timestamp': datetime.now().isoformat(),
                'health_score': 0,
                'overall_status': 'error',
                'error': str(e)
            }
    
    def _calculate_health_score(self, listener_status: ServiceStatus, 
                               api_clients_status: List[APIClientStatus],
                               listeners_status: List[ListenerStatus],
                               statistics: Dict[str, Any]) -> int:
        """计算健康分数 (0-100)"""
        score = 100
        
        # 消息监听器状态 (40分)
        if not listener_status.running:
            score -= 40
        elif listener_status.error_count > 10:
            score -= 20
        elif listener_status.error_count > 5:
            score -= 10
        
        # API客户端状态 (30分)
        if api_clients_status:
            connected_clients = sum(1 for client in api_clients_status if client.connected)
            connection_ratio = connected_clients / len(api_clients_status)
            score -= int((1 - connection_ratio) * 30)
        
        # 监听对象状态 (20分)
        if listeners_status:
            active_listeners = sum(1 for listener in listeners_status if listener.active)
            active_ratio = active_listeners / len(listeners_status)
            score -= int((1 - active_ratio) * 20)
        
        # 错误率 (10分)
        error_rate = statistics.get('error_rate', 0)
        if error_rate > 0.1:  # 错误率超过10%
            score -= 10
        elif error_rate > 0.05:  # 错误率超过5%
            score -= 5
        
        return max(0, score)
    
    def enable_monitoring(self):
        """启用监控"""
        self._monitoring_enabled = True
        logger.info("服务监控已启用")
    
    def disable_monitoring(self):
        """禁用监控"""
        self._monitoring_enabled = False
        logger.info("服务监控已禁用")

# 创建全局实例
service_monitor = ServiceMonitor()
