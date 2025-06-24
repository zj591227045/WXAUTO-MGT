# WXAUTO-MGT 服务监控使用指南

## 概述

WXAUTO-MGT项目现在包含了完整的服务监控和诊断系统，可以帮助您实时监控消息监听服务的运行状态，快速诊断问题，并提供自动恢复能力。

## 主要功能

### 1. 配置变更热重载
- **问题解决**: 修改服务平台或消息转发规则后，无需重启Python进程
- **实现方式**: 事件驱动的配置变更通知机制
- **自动触发**: 在UI中修改配置后自动重新加载

### 2. 增强的异常处理
- **问题解决**: 运行一段时间后服务停止的问题
- **实现方式**: 多层次错误检测和自动恢复机制
- **健康检查**: API客户端连接状态监控和自动重连

### 3. 实时服务监控
- **服务状态**: 运行状态、运行时间、任务数量
- **性能指标**: 内存使用量、CPU使用率
- **错误统计**: 错误次数、最近错误信息
- **业务统计**: 消息处理量、API调用次数、监听对象数量

## 使用方法

### 1. 查看服务状态

#### 通过API接口查看
```python
from wxauto_mgt.api.monitor_api import monitor_api

# 获取服务状态
status = await monitor_api.get_service_status()
print(f"服务运行状态: {status['data']['running']}")
print(f"运行时间: {status['data']['uptime_formatted']}")
print(f"内存使用: {status['data']['memory_usage_mb']} MB")
```

#### 通过健康报告查看
```python
# 获取完整健康报告
health_report = await monitor_api.get_health_report()
print(f"健康分数: {health_report['data']['health_score']}/100")
print(f"整体状态: {health_report['data']['overall_status']}")
```

### 2. 监控API客户端状态

```python
# 获取所有API客户端状态
clients_status = await monitor_api.get_api_clients_status()
for client in clients_status['data']:
    print(f"实例 {client['instance_id']}: 连接状态 {client['connected']}")
```

### 3. 查看监听对象状态

```python
# 获取所有监听对象状态
listeners_status = await monitor_api.get_listeners_status()
print(f"总监听对象: {listeners_status['total_count']}")
print(f"活跃监听对象: {listeners_status['active_count']}")
```

### 4. 查看统计信息

```python
# 获取详细统计信息
statistics = await monitor_api.get_statistics()
print(f"处理消息总数: {statistics['data']['total_messages_processed']}")
print(f"错误率: {statistics['data']['error_rate']:.2%}")
print(f"最近1小时错误数: {statistics['data']['recent_errors_count']}")
```

### 5. 查看最近错误

```python
# 获取最近10条错误记录
recent_errors = await monitor_api.get_recent_errors(10)
for error in recent_errors['data']:
    print(f"{error['datetime']}: {error['error_message']}")
```

### 6. 服务管理操作

#### 重启服务
```python
# 重启消息监听服务
result = await monitor_api.restart_service()
if result['success']:
    print("服务重启成功")
```

#### 重新加载配置
```python
# 重新加载配置（无需重启）
result = await monitor_api.reload_config()
if result['success']:
    print("配置重新加载成功")
```

## 健康分数说明

健康分数是一个0-100的综合评分，计算规则如下：

- **消息监听器状态 (40分)**
  - 服务未运行: -40分
  - 错误数量 > 10: -20分
  - 错误数量 > 5: -10分

- **API客户端状态 (30分)**
  - 根据连接成功率扣分: (1 - 连接率) × 30

- **监听对象状态 (20分)**
  - 根据活跃率扣分: (1 - 活跃率) × 20

- **错误率 (10分)**
  - 错误率 > 10%: -10分
  - 错误率 > 5%: -5分

### 健康状态分级
- **healthy (健康)**: 分数 ≥ 80
- **warning (警告)**: 分数 60-79
- **critical (严重)**: 分数 < 60

## 自动化监控

### 1. 配置变更自动处理

当您在UI中修改服务平台或规则配置时，系统会自动：
1. 发送配置变更通知
2. 重新加载平台管理器和规则管理器
3. 更新内存缓存
4. 记录配置重新加载统计

### 2. 错误自动恢复

当检测到错误时，系统会自动：
1. 记录错误信息和时间
2. 尝试重新初始化失效的API客户端
3. 根据连续错误次数调整重试间隔
4. 跳过有问题的实例，继续处理其他实例

### 3. 健康检查

系统会定期进行健康检查：
1. 验证API客户端连接状态
2. 检查监听对象活跃状态
3. 监控系统资源使用情况
4. 生成健康报告

## 故障排查指南

### 1. 服务无法启动
- 检查数据库连接
- 查看日志文件中的错误信息
- 确认端口是否被占用

### 2. 配置修改不生效
- 检查配置变更通知是否正常工作
- 手动调用 `reload_config()` 重新加载配置
- 查看配置重新加载统计

### 3. 消息监听停止
- 查看健康报告中的错误信息
- 检查API客户端连接状态
- 查看最近错误记录

### 4. 性能问题
- 监控内存使用量和CPU使用率
- 查看消息处理统计
- 检查错误率是否过高

## 日志文件位置

- **主日志**: `data/logs/wxauto_mgt_YYYYMMDD.log`
- **文件处理日志**: `data/logs/file_processing.log`
- **健康报告示例**: `data/logs/health_report_sample.json`

## 测试验证

项目包含了完整的测试套件：

```bash
# 测试配置变更通知
python tests/test_config_notifier_integration.py

# 测试消息监听器健康检查
python tests/test_message_listener_health.py

# 测试服务监控功能
python tests/test_service_monitor.py
```

## 最佳实践

1. **定期检查健康报告**: 建议每天查看一次健康报告
2. **监控错误率**: 错误率超过5%时需要关注
3. **及时处理警告**: 健康分数低于80时应该调查原因
4. **保持日志清理**: 定期清理过期的日志文件
5. **配置备份**: 重要配置修改前先备份

## 技术架构

### 核心组件
- **ConfigNotifier**: 配置变更通知系统
- **ServiceMonitor**: 服务状态监控器
- **MonitorAPI**: 监控API接口
- **MessageListener**: 增强的消息监听器

### 数据流
1. UI配置修改 → 配置变更通知 → 自动重新加载
2. 服务运行 → 状态监控 → 健康报告生成
3. 错误发生 → 错误记录 → 自动恢复尝试

这个监控系统大大提高了WXAUTO-MGT项目的稳定性和可维护性，让您能够更好地管理和监控消息监听服务。
