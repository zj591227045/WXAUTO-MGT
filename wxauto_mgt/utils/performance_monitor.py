"""
性能监控工具

用于监控API调用性能和检测UI阻塞问题。
"""

import time
import asyncio
import threading
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from collections import defaultdict, deque

from wxauto_mgt.utils.logging import get_logger

logger = get_logger()


@dataclass
class PerformanceMetric:
    """性能指标数据类"""
    operation: str
    start_time: float
    end_time: float
    duration: float
    success: bool
    error_message: Optional[str] = None


class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self, max_history: int = 1000):
        """
        初始化性能监控器
        
        Args:
            max_history: 最大历史记录数量
        """
        self.max_history = max_history
        self.metrics: deque = deque(maxlen=max_history)
        self.operation_stats: Dict[str, List[float]] = defaultdict(list)
        self._lock = threading.Lock()
        
        # UI响应性监控
        self.ui_response_threshold = 0.1  # 100ms阈值
        self.ui_blocked_count = 0
        self.last_ui_update = time.time()
    
    def record_operation(self, operation: str, duration: float, success: bool, error_message: Optional[str] = None):
        """
        记录操作性能指标
        
        Args:
            operation: 操作名称
            duration: 执行时间（秒）
            success: 是否成功
            error_message: 错误信息（如果有）
        """
        with self._lock:
            metric = PerformanceMetric(
                operation=operation,
                start_time=time.time() - duration,
                end_time=time.time(),
                duration=duration,
                success=success,
                error_message=error_message
            )
            
            self.metrics.append(metric)
            
            if success:
                self.operation_stats[operation].append(duration)
                # 保持统计数据在合理范围内
                if len(self.operation_stats[operation]) > 100:
                    self.operation_stats[operation] = self.operation_stats[operation][-100:]
    
    def get_operation_stats(self, operation: str) -> Dict[str, float]:
        """
        获取操作统计信息
        
        Args:
            operation: 操作名称
            
        Returns:
            包含平均值、最小值、最大值等统计信息的字典
        """
        with self._lock:
            durations = self.operation_stats.get(operation, [])
            
            if not durations:
                return {}
            
            return {
                'count': len(durations),
                'avg': sum(durations) / len(durations),
                'min': min(durations),
                'max': max(durations),
                'recent_avg': sum(durations[-10:]) / min(len(durations), 10)
            }
    
    def get_slow_operations(self, threshold: float = 1.0) -> List[PerformanceMetric]:
        """
        获取慢操作列表
        
        Args:
            threshold: 时间阈值（秒）
            
        Returns:
            慢操作列表
        """
        with self._lock:
            return [metric for metric in self.metrics if metric.duration > threshold]
    
    def check_ui_responsiveness(self):
        """检查UI响应性"""
        current_time = time.time()
        time_since_last_update = current_time - self.last_ui_update
        
        if time_since_last_update > self.ui_response_threshold:
            self.ui_blocked_count += 1
            #logger.warning(f"UI可能被阻塞，距离上次更新: {time_since_last_update:.3f}秒")
    
        self.last_ui_update = current_time
    
    def reset_ui_timer(self):
        """重置UI计时器"""
        self.last_ui_update = time.time()
    
    def get_summary(self) -> Dict:
        """获取性能摘要"""
        with self._lock:
            total_operations = len(self.metrics)
            successful_operations = sum(1 for m in self.metrics if m.success)
            failed_operations = total_operations - successful_operations
            
            # 按操作类型分组统计
            operation_summary = {}
            for operation in self.operation_stats:
                operation_summary[operation] = self.get_operation_stats(operation)
            
            return {
                'total_operations': total_operations,
                'successful_operations': successful_operations,
                'failed_operations': failed_operations,
                'success_rate': successful_operations / total_operations if total_operations > 0 else 0,
                'ui_blocked_count': self.ui_blocked_count,
                'operation_summary': operation_summary
            }


class AsyncPerformanceDecorator:
    """异步性能装饰器"""
    
    def __init__(self, monitor: PerformanceMonitor, operation_name: str):
        """
        初始化装饰器
        
        Args:
            monitor: 性能监控器实例
            operation_name: 操作名称
        """
        self.monitor = monitor
        self.operation_name = operation_name
    
    def __call__(self, func: Callable):
        """装饰器调用"""
        if asyncio.iscoroutinefunction(func):
            async def async_wrapper(*args, **kwargs):
                start_time = time.time()
                success = True
                error_message = None
                
                try:
                    result = await func(*args, **kwargs)
                    return result
                except Exception as e:
                    success = False
                    error_message = str(e)
                    raise
                finally:
                    duration = time.time() - start_time
                    self.monitor.record_operation(
                        self.operation_name, duration, success, error_message
                    )
            
            return async_wrapper
        else:
            def sync_wrapper(*args, **kwargs):
                start_time = time.time()
                success = True
                error_message = None
                
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    success = False
                    error_message = str(e)
                    raise
                finally:
                    duration = time.time() - start_time
                    self.monitor.record_operation(
                        self.operation_name, duration, success, error_message
                    )
            
            return sync_wrapper


# 全局性能监控器实例
performance_monitor = PerformanceMonitor()


def monitor_performance(operation_name: str):
    """
    性能监控装饰器
    
    Args:
        operation_name: 操作名称
        
    Returns:
        装饰器函数
    """
    return AsyncPerformanceDecorator(performance_monitor, operation_name)


def log_performance_summary():
    """记录性能摘要到日志"""
    summary = performance_monitor.get_summary()
    logger.info(f"性能摘要: {summary}")
