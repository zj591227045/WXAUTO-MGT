"""
警报管理器模块

负责管理和处理系统警报，包括警报规则的管理、警报触发检查和警报历史记录。
支持多实例管理和多种警报通知方式。
"""

import json
import time
import logging
from typing import List, Dict, Optional, Any, Union
from enum import Enum

from ...data.db_manager import db_manager

logger = logging.getLogger(__name__)

class AlertType(Enum):
    """警报类型枚举"""
    SYSTEM = "system"          # 系统警报
    PERFORMANCE = "performance"  # 性能警报
    MESSAGE = "message"         # 消息警报
    CUSTOM = "custom"          # 自定义警报

class AlertSeverity(Enum):
    """警报严重程度枚举"""
    INFO = "info"        # 信息
    WARNING = "warning"  # 警告
    ERROR = "error"      # 错误
    CRITICAL = "critical"  # 严重

class AlertManager:
    """警报管理器，负责管理和处理系统警报"""
    
    def __init__(self):
        """初始化警报管理器"""
        self._alert_handlers = {}  # 警报处理器字典
        logger.debug("初始化警报管理器")
    
    async def add_alert_rule(self, instance_id: str, metric_type: str, threshold: float,
                           threshold_type: str, notify_methods: List[str],
                           alert_type: AlertType = AlertType.PERFORMANCE,
                           severity: AlertSeverity = AlertSeverity.WARNING) -> int:
        """
        添加新的警报规则
        
        Args:
            instance_id: 实例ID
            metric_type: 指标类型
            threshold: 阈值
            threshold_type: 阈值类型 ('gt', 'lt', 'gte', 'lte')
            notify_methods: 通知方式列表
            alert_type: 警报类型
            severity: 警报严重程度
            
        Returns:
            新添加的规则ID
        """
        now = int(time.time())
        notify_methods_json = json.dumps(notify_methods)
        
        data = {
            "instance_id": instance_id,
            "metric_type": metric_type,
            "threshold": threshold,
            "threshold_type": threshold_type,
            "notify_methods": notify_methods_json,
            "alert_type": alert_type.value,
            "severity": severity.value,
            "create_time": now,
            "last_update": now,
            "enabled": True
        }
        
        try:
            rule_id = await db_manager.insert("alert_rules", data)
            logger.info(f"添加警报规则成功: {rule_id}")
            return rule_id
        except Exception as e:
            logger.error(f"添加警报规则失败: {e}")
            raise

    async def update_alert_rule(self, rule_id: int, **kwargs) -> bool:
        """
        更新警报规则
        
        Args:
            rule_id: 规则ID
            **kwargs: 需要更新的字段
            
        Returns:
            更新是否成功
        """
        if not kwargs:
            return False
            
        update_data = {}
        for key, value in kwargs.items():
            if key == 'notify_methods' and isinstance(value, list):
                value = json.dumps(value)
            elif key == 'alert_type' and isinstance(value, AlertType):
                value = value.value
            elif key == 'severity' and isinstance(value, AlertSeverity):
                value = value.value
            update_data[key] = value
            
        update_data['last_update'] = int(time.time())
        
        try:
            conditions = "id = ?"
            await db_manager.execute(
                f"UPDATE alert_rules SET {', '.join(f'{k} = ?' for k in update_data.keys())} WHERE {conditions}",
                list(update_data.values()) + [rule_id]
            )
            logger.info(f"更新警报规则成功: {rule_id}")
            return True
        except Exception as e:
            logger.error(f"更新警报规则失败: {e}")
            raise

    async def get_alert_rules(self, instance_id: Optional[str] = None,
                            alert_type: Optional[AlertType] = None,
                            enabled_only: bool = True) -> List[Dict[str, Any]]:
        """
        获取警报规则列表
        
        Args:
            instance_id: 可选的实例ID过滤
            alert_type: 可选的警报类型过滤
            enabled_only: 是否只返回启用的规则
            
        Returns:
            警报规则列表
        """
        conditions = []
        params = []
        
        if enabled_only:
            conditions.append("enabled = 1")
        
        if instance_id:
            conditions.append("instance_id = ?")
            params.append(instance_id)
            
        if alert_type:
            conditions.append("alert_type = ?")
            params.append(alert_type.value)
            
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        try:
            sql = f"SELECT * FROM alert_rules WHERE {where_clause}"
            rules = await db_manager.fetchall(sql, params)
            
            # 处理JSON字段
            for rule in rules:
                rule['notify_methods'] = json.loads(rule['notify_methods'])
            return rules
        except Exception as e:
            logger.error(f"获取警报规则失败: {e}")
            raise

    async def delete_alert_rule(self, rule_id: int) -> bool:
        """
        删除警报规则
        
        Args:
            rule_id: 规则ID
            
        Returns:
            删除是否成功
        """
        try:
            await db_manager.execute("DELETE FROM alert_rules WHERE id = ?", (rule_id,))
            logger.info(f"删除警报规则成功: {rule_id}")
            return True
        except Exception as e:
            logger.error(f"删除警报规则失败: {e}")
            raise

    async def check_metric_alert(self, instance_id: str, metric_type: str,
                               metric_value: float) -> List[Dict[str, Any]]:
        """
        检查指标是否触发警报
        
        Args:
            instance_id: 实例ID
            metric_type: 指标类型
            metric_value: 指标值
            
        Returns:
            触发的警报规则列表
        """
        rules = await self.get_alert_rules(instance_id)
        triggered_rules = []
        
        for rule in rules:
            if rule['metric_type'] != metric_type:
                continue
                
            threshold = float(rule['threshold'])
            threshold_type = rule['threshold_type']
            
            is_triggered = False
            if threshold_type == 'gt' and metric_value > threshold:
                is_triggered = True
            elif threshold_type == 'lt' and metric_value < threshold:
                is_triggered = True
            elif threshold_type == 'gte' and metric_value >= threshold:
                is_triggered = True
            elif threshold_type == 'lte' and metric_value <= threshold:
                is_triggered = True
                
            if is_triggered:
                await self._record_alert(rule['id'], instance_id, metric_type, 
                                      metric_value, threshold, threshold_type)
                triggered_rules.append(rule)
                
        return triggered_rules

    async def _record_alert(self, rule_id: int, instance_id: str,
                          metric_type: str, metric_value: float,
                          threshold: float, threshold_type: str) -> None:
        """
        记录警报
        
        Args:
            rule_id: 规则ID
            instance_id: 实例ID
            metric_type: 指标类型
            metric_value: 指标值
            threshold: 阈值
            threshold_type: 阈值类型
        """
        now = int(time.time())
        
        data = {
            "rule_id": rule_id,
            "instance_id": instance_id,
            "metric_type": metric_type,
            "metric_value": metric_value,
            "threshold": threshold,
            "threshold_type": threshold_type,
            "status": "triggered",
            "create_time": now
        }
        
        try:
            await db_manager.insert("alert_history", data)
            logger.info(f"记录警报成功: rule_id={rule_id}, instance_id={instance_id}")
        except Exception as e:
            logger.error(f"记录警报失败: {e}")
            raise

    async def get_alert_history(self, instance_id: Optional[str] = None,
                              start_time: Optional[int] = None,
                              end_time: Optional[int] = None,
                              alert_type: Optional[AlertType] = None,
                              limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取警报历史记录
        
        Args:
            instance_id: 可选的实例ID过滤
            start_time: 可选的开始时间戳
            end_time: 可选的结束时间戳
            alert_type: 可选的警报类型过滤
            limit: 返回记录数量限制
            
        Returns:
            警报历史记录列表
        """
        conditions = []
        params = []
        
        if instance_id:
            conditions.append("h.instance_id = ?")
            params.append(instance_id)
            
        if start_time:
            conditions.append("h.create_time >= ?")
            params.append(start_time)
            
        if end_time:
            conditions.append("h.create_time <= ?")
            params.append(end_time)
            
        if alert_type:
            conditions.append("r.alert_type = ?")
            params.append(alert_type.value)
            
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        sql = f"""
            SELECT h.*, r.alert_type, r.severity, r.notify_methods
            FROM alert_history h
            LEFT JOIN alert_rules r ON h.rule_id = r.id
            WHERE {where_clause}
            ORDER BY h.create_time DESC
            LIMIT ?
        """
        params.append(limit)
        
        try:
            history = await db_manager.fetchall(sql, params)
            for record in history:
                if record['notify_methods']:
                    record['notify_methods'] = json.loads(record['notify_methods'])
            return history
        except Exception as e:
            logger.error(f"获取警报历史失败: {e}")
            raise

    def register_alert_handler(self, alert_type: AlertType, handler: callable) -> None:
        """
        注册警报处理器
        
        Args:
            alert_type: 警报类型
            handler: 处理器函数
        """
        self._alert_handlers[alert_type] = handler
        logger.debug(f"注册警报处理器: {alert_type}")

    async def handle_alert(self, alert_type: AlertType, alert_data: Dict) -> bool:
        """
        处理警报
        
        Args:
            alert_type: 警报类型
            alert_data: 警报数据
            
        Returns:
            处理是否成功
        """
        handler = self._alert_handlers.get(alert_type)
        if not handler:
            logger.warning(f"未找到警报类型 {alert_type} 的处理器")
            return False
            
        try:
            await handler(alert_data)
            return True
        except Exception as e:
            logger.error(f"处理警报失败: {e}")
            return False

# 创建全局实例
alert_manager = AlertManager() 