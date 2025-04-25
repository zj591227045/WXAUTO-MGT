import pytest
import json
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock

from wxauto_mgt.app.core.alert_manager import AlertManager

@pytest.fixture
def db_manager():
    db = MagicMock()
    db.execute = AsyncMock()
    db.fetchall = AsyncMock()
    return db

@pytest.fixture
def alert_manager(db_manager):
    return AlertManager(db_manager)

@pytest.mark.asyncio
async def test_add_alert_rule(alert_manager, db_manager):
    instance_id = "test_instance"
    metric_type = "cpu_usage"
    threshold = 80.0
    threshold_type = "gte"
    notify_methods = ["email", "webhook"]
    
    db_manager.execute.return_value = 1
    
    rule_id = await alert_manager.add_alert_rule(
        instance_id, metric_type, threshold, threshold_type, notify_methods
    )
    
    assert rule_id == 1
    db_manager.execute.assert_called_once()
    call_args = db_manager.execute.call_args[0]
    assert "INSERT INTO alert_rules" in call_args[0]
    assert call_args[1] == (instance_id, metric_type, threshold, threshold_type, 
                           json.dumps(notify_methods))

@pytest.mark.asyncio
async def test_update_alert_rule(alert_manager, db_manager):
    rule_id = 1
    instance_id = "test_instance"
    metric_type = "memory_usage"
    threshold = 90.0
    threshold_type = "gte"
    notify_methods = ["email"]
    enabled = True
    
    db_manager.execute.return_value = 1
    
    success = await alert_manager.update_alert_rule(
        rule_id, instance_id, metric_type, threshold, 
        threshold_type, notify_methods, enabled
    )
    
    assert success is True
    db_manager.execute.assert_called_once()
    call_args = db_manager.execute.call_args[0]
    assert "UPDATE alert_rules" in call_args[0]

@pytest.mark.asyncio
async def test_get_alert_rules(alert_manager, db_manager):
    mock_rules = [
        {
            "id": 1,
            "instance_id": "test_instance",
            "metric_type": "cpu_usage",
            "threshold": 80.0,
            "threshold_type": "gte",
            "notify_methods": json.dumps(["email"]),
            "enabled": 1,
            "create_time": int(datetime.now().timestamp()),
            "last_update": int(datetime.now().timestamp())
        }
    ]
    db_manager.fetchall.return_value = mock_rules
    
    rules = await alert_manager.get_alert_rules()
    
    assert len(rules) == 1
    assert isinstance(rules[0]["notify_methods"], list)
    db_manager.fetchall.assert_called_once()

@pytest.mark.asyncio
async def test_check_metric_alert(alert_manager, db_manager):
    instance_id = "test_instance"
    metric_type = "cpu_usage"
    metric_value = 85.0
    
    mock_rules = [
        {
            "id": 1,
            "instance_id": instance_id,
            "metric_type": metric_type,
            "threshold": 80.0,
            "threshold_type": "gte",
            "notify_methods": json.dumps(["email"]),
            "enabled": 1
        }
    ]
    db_manager.fetchall.return_value = mock_rules
    db_manager.execute.return_value = 1
    
    await alert_manager.check_metric_alert(instance_id, metric_type, metric_value)
    
    # 验证是否添加了警报历史记录
    assert db_manager.execute.called
    call_args = db_manager.execute.call_args[0]
    assert "INSERT INTO alert_history" in call_args[0] 