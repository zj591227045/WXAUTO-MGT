"""
服务监控API接口

提供服务状态查询和健康检查的API接口
"""

import asyncio
import logging
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class MonitorAPI:
    """服务监控API类"""
    
    def __init__(self):
        self._initialized = False
    
    async def initialize(self):
        """初始化监控API"""
        if self._initialized:
            return True
        
        try:
            self._initialized = True
            logger.info("服务监控API初始化成功")
            return True
        except Exception as e:
            logger.error(f"服务监控API初始化失败: {e}")
            return False
    
    async def get_service_status(self) -> Dict[str, Any]:
        """
        获取服务状态信息
        
        Returns:
            Dict[str, Any]: 服务状态信息
        """
        try:
            from wxauto_mgt.core.service_monitor import service_monitor
            
            # 获取消息监听器状态
            listener_status = await service_monitor.get_message_listener_status()
            
            return {
                'success': True,
                'data': {
                    'service_name': listener_status.service_name,
                    'running': listener_status.running,
                    'uptime_seconds': listener_status.uptime_seconds,
                    'uptime_formatted': self._format_uptime(listener_status.uptime_seconds),
                    'task_count': listener_status.task_count,
                    'error_count': listener_status.error_count,
                    'last_error_time': listener_status.last_error_time,
                    'last_error_message': listener_status.last_error_message,
                    'memory_usage_mb': round(listener_status.memory_usage_mb, 2),
                    'cpu_percent': round(listener_status.cpu_percent, 2),
                    'timestamp': datetime.now().isoformat()
                }
            }
        except Exception as e:
            logger.error(f"获取服务状态失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def get_api_clients_status(self) -> Dict[str, Any]:
        """
        获取API客户端状态信息
        
        Returns:
            Dict[str, Any]: API客户端状态信息
        """
        try:
            from wxauto_mgt.core.service_monitor import service_monitor
            
            clients_status = await service_monitor.get_api_clients_status()
            
            return {
                'success': True,
                'data': [
                    {
                        'instance_id': status.instance_id,
                        'initialized': status.initialized,
                        'connected': status.connected,
                        'last_check_time': status.last_check_time,
                        'error_count': status.error_count,
                        'last_error': status.last_error
                    }
                    for status in clients_status
                ],
                'total_count': len(clients_status),
                'connected_count': sum(1 for status in clients_status if status.connected),
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"获取API客户端状态失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def get_listeners_status(self) -> Dict[str, Any]:
        """
        获取监听对象状态信息
        
        Returns:
            Dict[str, Any]: 监听对象状态信息
        """
        try:
            from wxauto_mgt.core.service_monitor import service_monitor
            
            listeners_status = await service_monitor.get_listeners_status()
            
            return {
                'success': True,
                'data': [
                    {
                        'instance_id': status.instance_id,
                        'who': status.who,
                        'active': status.active,
                        'last_message_time': status.last_message_time,
                        'last_check_time': status.last_check_time,
                        'message_count': status.message_count,
                        'error_count': status.error_count
                    }
                    for status in listeners_status
                ],
                'total_count': len(listeners_status),
                'active_count': sum(1 for status in listeners_status if status.active),
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"获取监听对象状态失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def get_statistics(self) -> Dict[str, Any]:
        """
        获取统计信息
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        try:
            from wxauto_mgt.core.service_monitor import service_monitor
            
            stats = service_monitor.get_statistics()
            
            return {
                'success': True,
                'data': stats,
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def get_recent_errors(self, limit: int = 10) -> Dict[str, Any]:
        """
        获取最近的错误记录
        
        Args:
            limit: 返回的错误记录数量限制
            
        Returns:
            Dict[str, Any]: 最近的错误记录
        """
        try:
            from wxauto_mgt.core.service_monitor import service_monitor
            
            errors = service_monitor.get_recent_errors(limit)
            
            return {
                'success': True,
                'data': errors,
                'count': len(errors),
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"获取最近错误记录失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def get_health_report(self) -> Dict[str, Any]:
        """
        获取完整的健康状况报告
        
        Returns:
            Dict[str, Any]: 健康状况报告
        """
        try:
            from wxauto_mgt.core.service_monitor import service_monitor
            
            report = await service_monitor.generate_health_report()
            
            return {
                'success': True,
                'data': report
            }
        except Exception as e:
            logger.error(f"获取健康报告失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def restart_service(self) -> Dict[str, Any]:
        """
        重启消息监听服务
        
        Returns:
            Dict[str, Any]: 重启结果
        """
        try:
            from wxauto_mgt.core.message_listener import message_listener
            
            logger.info("开始重启消息监听服务")
            
            # 停止服务
            await message_listener.stop()
            
            # 等待一秒
            await asyncio.sleep(1)
            
            # 重新启动服务
            await message_listener.start()
            
            logger.info("消息监听服务重启完成")
            
            return {
                'success': True,
                'message': '消息监听服务重启成功',
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"重启消息监听服务失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def reload_config(self) -> Dict[str, Any]:
        """
        重新加载配置
        
        Returns:
            Dict[str, Any]: 重新加载结果
        """
        try:
            from wxauto_mgt.core.message_listener import message_listener
            
            logger.info("开始重新加载配置")
            
            # 调用配置重新加载方法
            await message_listener._reload_config_cache()
            
            logger.info("配置重新加载完成")
            
            return {
                'success': True,
                'message': '配置重新加载成功',
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"重新加载配置失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def _format_uptime(self, seconds: float) -> str:
        """
        格式化运行时间
        
        Args:
            seconds: 运行时间（秒）
            
        Returns:
            str: 格式化的运行时间
        """
        if seconds < 60:
            return f"{int(seconds)}秒"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}分{secs}秒"
        elif seconds < 86400:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}小时{minutes}分"
        else:
            days = int(seconds // 86400)
            hours = int((seconds % 86400) // 3600)
            return f"{days}天{hours}小时"

# 创建全局实例
monitor_api = MonitorAPI()
