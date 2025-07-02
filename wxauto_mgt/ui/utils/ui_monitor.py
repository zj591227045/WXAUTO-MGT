"""
UI响应性监控工具

用于监控UI线程的响应性，检测可能的阻塞问题。
"""

import time
import threading
from typing import Optional, Callable
from PySide6.QtCore import QTimer, QObject, Signal
from PySide6.QtWidgets import QApplication

from wxauto_mgt.utils.logging import get_logger
from wxauto_mgt.utils.performance_monitor import performance_monitor

logger = get_logger()


class UIResponsivenessMonitor(QObject):
    """UI响应性监控器"""
    
    # 信号定义
    ui_blocked = Signal(float)  # UI被阻塞信号，参数为阻塞时间
    ui_responsive = Signal()    # UI恢复响应信号
    
    def __init__(self, parent=None, check_interval: int = 100, block_threshold: float = 0.2):
        """
        初始化UI响应性监控器
        
        Args:
            parent: 父对象
            check_interval: 检查间隔（毫秒）
            block_threshold: 阻塞阈值（秒）
        """
        super().__init__(parent)
        
        self.check_interval = check_interval
        self.block_threshold = block_threshold
        self.last_check_time = time.time()
        self.is_monitoring = False
        self.blocked_count = 0
        self.total_checks = 0
        
        # 创建定时器
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._check_responsiveness)
        
        # 连接信号
        self.ui_blocked.connect(self._on_ui_blocked)
        self.ui_responsive.connect(self._on_ui_responsive)
    
    def start_monitoring(self):
        """开始监控"""
        if not self.is_monitoring:
            self.is_monitoring = True
            self.last_check_time = time.time()
            self.timer.start(self.check_interval)
            logger.info(f"UI响应性监控已启动，检查间隔: {self.check_interval}ms")
    
    def stop_monitoring(self):
        """停止监控"""
        if self.is_monitoring:
            self.is_monitoring = False
            self.timer.stop()
            logger.info("UI响应性监控已停止")
    
    def _check_responsiveness(self):
        """检查UI响应性"""
        current_time = time.time()
        time_since_last_check = current_time - self.last_check_time
        
        self.total_checks += 1
        
        # 如果时间间隔超过阈值，认为UI被阻塞
        if time_since_last_check > self.block_threshold:
            self.blocked_count += 1
            self.ui_blocked.emit(time_since_last_check)
        else:
            self.ui_responsive.emit()
        
        self.last_check_time = current_time
        
        # 更新性能监控器
        performance_monitor.check_ui_responsiveness()
    
    def _on_ui_blocked(self, block_time: float):
        """UI被阻塞时的处理"""
        #logger.warning(f"检测到UI阻塞，阻塞时间: {block_time:.3f}秒")
        
        # 记录到性能监控器
        performance_monitor.record_operation(
            "ui_responsiveness", 
            block_time, 
            False, 
            f"UI阻塞 {block_time:.3f}秒"
        )
    
    def _on_ui_responsive(self):
        """UI响应正常时的处理"""
        # 重置性能监控器的UI计时器
        performance_monitor.reset_ui_timer()
    
    def get_statistics(self) -> dict:
        """获取监控统计信息"""
        if self.total_checks == 0:
            return {
                'total_checks': 0,
                'blocked_count': 0,
                'block_rate': 0.0,
                'responsiveness_rate': 0.0
            }
        
        responsiveness_rate = (self.total_checks - self.blocked_count) / self.total_checks
        block_rate = self.blocked_count / self.total_checks
        
        return {
            'total_checks': self.total_checks,
            'blocked_count': self.blocked_count,
            'block_rate': block_rate,
            'responsiveness_rate': responsiveness_rate
        }
    
    def reset_statistics(self):
        """重置统计信息"""
        self.blocked_count = 0
        self.total_checks = 0
        logger.info("UI响应性监控统计信息已重置")


class AsyncTaskMonitor:
    """异步任务监控器"""
    
    def __init__(self):
        """初始化异步任务监控器"""
        self.active_tasks = {}
        self.completed_tasks = []
        self.failed_tasks = []
        self._lock = threading.Lock()
    
    def register_task(self, task_id: str, description: str):
        """
        注册异步任务
        
        Args:
            task_id: 任务ID
            description: 任务描述
        """
        with self._lock:
            self.active_tasks[task_id] = {
                'description': description,
                'start_time': time.time(),
                'status': 'running'
            }
            logger.debug(f"注册异步任务: {task_id} - {description}")
    
    def complete_task(self, task_id: str, success: bool = True, error_message: Optional[str] = None):
        """
        完成异步任务
        
        Args:
            task_id: 任务ID
            success: 是否成功
            error_message: 错误信息（如果失败）
        """
        with self._lock:
            if task_id in self.active_tasks:
                task_info = self.active_tasks.pop(task_id)
                task_info['end_time'] = time.time()
                task_info['duration'] = task_info['end_time'] - task_info['start_time']
                task_info['success'] = success
                task_info['error_message'] = error_message
                
                if success:
                    self.completed_tasks.append(task_info)
                    logger.debug(f"异步任务完成: {task_id}, 耗时: {task_info['duration']:.3f}秒")
                else:
                    self.failed_tasks.append(task_info)
                    logger.warning(f"异步任务失败: {task_id}, 错误: {error_message}")
    
    def get_active_tasks(self) -> dict:
        """获取活跃任务列表"""
        with self._lock:
            return self.active_tasks.copy()
    
    def get_task_statistics(self) -> dict:
        """获取任务统计信息"""
        with self._lock:
            total_completed = len(self.completed_tasks)
            total_failed = len(self.failed_tasks)
            total_tasks = total_completed + total_failed
            
            avg_duration = 0
            if self.completed_tasks:
                avg_duration = sum(task['duration'] for task in self.completed_tasks) / len(self.completed_tasks)
            
            return {
                'active_tasks': len(self.active_tasks),
                'completed_tasks': total_completed,
                'failed_tasks': total_failed,
                'total_tasks': total_tasks,
                'success_rate': total_completed / total_tasks if total_tasks > 0 else 0,
                'average_duration': avg_duration
            }


# 全局实例
ui_monitor = UIResponsivenessMonitor()
task_monitor = AsyncTaskMonitor()


def start_ui_monitoring():
    """启动UI监控"""
    ui_monitor.start_monitoring()


def stop_ui_monitoring():
    """停止UI监控"""
    ui_monitor.stop_monitoring()


def monitor_async_task(task_id: str, description: str):
    """
    异步任务监控装饰器
    
    Args:
        task_id: 任务ID
        description: 任务描述
    """
    def decorator(func: Callable):
        async def wrapper(*args, **kwargs):
            task_monitor.register_task(task_id, description)
            try:
                result = await func(*args, **kwargs)
                task_monitor.complete_task(task_id, True)
                return result
            except Exception as e:
                task_monitor.complete_task(task_id, False, str(e))
                raise
        return wrapper
    return decorator
