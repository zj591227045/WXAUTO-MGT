import json
import time
from typing import List, Dict, Optional, Any
from ..data.db_manager import DBManager
from ..utils.logger import get_logger

logger = get_logger(__name__)

class AlertManager:
    def __init__(self, db_manager: DBManager):
        self.db = db_manager

    async def add_alert_rule(self, instance_id: str, metric_type: str, threshold: float,
                           threshold_type: str, notify_methods: List[str]) -> int:
        """
        添加新的警报规则
        
        Args:
            instance_id: 实例ID
            metric_type: 指标类型
            threshold: 阈值
            threshold_type: 阈值类型 ('gt', 'lt', 'gte', 'lte')
            notify_methods: 通知方式列表
            
        Returns:
            新添加的规则ID
        """
        now = int(time.time())
        notify_methods_json = json.dumps(notify_methods)
        
        sql = """
        INSERT INTO alert_rules (instance_id, metric_type, threshold, threshold_type, 
                               notify_methods, create_time, last_update)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        params = (instance_id, metric_type, threshold, threshold_type,
                 notify_methods_json, now, now)
        
        try:
            rule_id = await self.db.execute(sql, params)
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
            
        update_fields = []
        params = []
        for key, value in kwargs.items():
            if key == 'notify_methods' and isinstance(value, list):
                value = json.dumps(value)
            update_fields.append(f"{key} = ?")
            params.append(value)
            
        params.append(int(time.time()))  # last_update
        params.append(rule_id)
        
        sql = f"""
        UPDATE alert_rules 
        SET {', '.join(update_fields)}, last_update = ?
        WHERE id = ?
        """
        
        try:
            await self.db.execute(sql, tuple(params))
            logger.info(f"更新警报规则成功: {rule_id}")
            return True
        except Exception as e:
            logger.error(f"更新警报规则失败: {e}")
            raise

    async def get_alert_rules(self, instance_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取警报规则列表
        
        Args:
            instance_id: 可选的实例ID过滤
            
        Returns:
            警报规则列表
        """
        sql = "SELECT * FROM alert_rules WHERE enabled = 1"
        params = []
        
        if instance_id:
            sql += " AND instance_id = ?"
            params.append(instance_id)
            
        try:
            rules = await self.db.fetchall(sql, params)
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
        sql = "DELETE FROM alert_rules WHERE id = ?"
        try:
            await self.db.execute(sql, (rule_id,))
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
                await self._record_alert_history(rule['id'], instance_id,
                                              metric_type, metric_value)
                triggered_rules.append(rule)
                
        return triggered_rules

    async def _record_alert_history(self, rule_id: int, instance_id: str,
                                  metric_type: str, metric_value: float) -> None:
        """
        记录警报历史
        
        Args:
            rule_id: 规则ID
            instance_id: 实例ID
            metric_type: 指标类型
            metric_value: 指标值
        """
        now = int(time.time())
        notify_status = json.dumps({"status": "pending"})
        
        sql = """
        INSERT INTO alert_history (rule_id, instance_id, metric_type, metric_value,
                                 trigger_time, notify_status)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        params = (rule_id, instance_id, metric_type, metric_value, now, notify_status)
        
        try:
            await self.db.execute(sql, params)
            logger.info(f"记录警报历史成功: rule_id={rule_id}, instance_id={instance_id}")
        except Exception as e:
            logger.error(f"记录警报历史失败: {e}")
            raise

    async def get_alert_history(self, instance_id: Optional[str] = None,
                              start_time: Optional[int] = None,
                              end_time: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        获取警报历史记录
        
        Args:
            instance_id: 可选的实例ID过滤
            start_time: 可选的开始时间戳
            end_time: 可选的结束时间戳
            
        Returns:
            警报历史记录列表
        """
        sql = "SELECT * FROM alert_history"
        conditions = []
        params = []
        
        if instance_id:
            conditions.append("instance_id = ?")
            params.append(instance_id)
            
        if start_time:
            conditions.append("trigger_time >= ?")
            params.append(start_time)
            
        if end_time:
            conditions.append("trigger_time <= ?")
            params.append(end_time)
            
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
            
        sql += " ORDER BY trigger_time DESC"
        
        try:
            history = await self.db.fetchall(sql, params)
            for record in history:
                record['notify_status'] = json.loads(record['notify_status'])
            return history
        except Exception as e:
            logger.error(f"获取警报历史失败: {e}")
            raise 