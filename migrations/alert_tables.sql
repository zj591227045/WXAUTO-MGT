-- 警报规则表
CREATE TABLE IF NOT EXISTS alert_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    instance_id TEXT NOT NULL,
    metric_type TEXT NOT NULL,
    threshold REAL NOT NULL,
    threshold_type TEXT NOT NULL,
    notify_methods TEXT NOT NULL,  -- JSON 格式的通知方式列表
    enabled INTEGER DEFAULT 1,     -- 1: 启用, 0: 禁用
    create_time INTEGER NOT NULL,
    last_update INTEGER NOT NULL
);

-- 警报历史记录表
CREATE TABLE IF NOT EXISTS alert_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id INTEGER NOT NULL,
    instance_id TEXT NOT NULL,
    metric_type TEXT NOT NULL,
    metric_value REAL NOT NULL,
    trigger_time INTEGER NOT NULL,
    notify_status TEXT NOT NULL,   -- JSON 格式的通知状态
    FOREIGN KEY (rule_id) REFERENCES alert_rules(id)
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_alert_rules_instance ON alert_rules(instance_id);
CREATE INDEX IF NOT EXISTS idx_alert_history_instance ON alert_history(instance_id);
CREATE INDEX IF NOT EXISTS idx_alert_history_time ON alert_history(trigger_time); 