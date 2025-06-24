# 消息监听服务错误检测和处理机制

## 概述

我们的消息监听服务实现了多层次的错误检测和处理机制，确保服务在遇到各种异常情况时能够自动恢复并继续运行。

## 错误检测层次

### 1. 循环任务级别的错误检测

每个主要循环任务都有独立的错误计数器和处理机制：

#### 主窗口检查循环 (`_main_window_check_loop`)
```python
consecutive_errors = 0
max_consecutive_errors = 5

while self.running:
    try:
        # 执行主窗口消息检查
        # ...
        consecutive_errors = 0  # 成功时重置计数器
    except asyncio.CancelledError:
        # 正常取消，不算错误
        break
    except Exception as e:
        consecutive_errors += 1  # 错误计数递增
        # 根据错误次数调整等待时间
```

#### 监听对象检查循环 (`_listeners_check_loop`)
```python
consecutive_errors = 0
max_consecutive_errors = 5
# 类似的错误处理机制
```

#### 清理循环 (`_cleanup_loop`)
```python
consecutive_errors = 0
max_consecutive_errors = 3  # 清理任务容错性更低
# 类似的错误处理机制
```

### 2. API客户端健康检查

在每次消息检查前，都会验证API客户端的健康状态：

```python
if not await self._check_api_client_health(instance_id, api_client):
    logger.warning(f"实例 {instance_id} API客户端连接异常，跳过本次检查")
    continue
```

#### 健康检查判断条件：

1. **初始化状态检查**
   ```python
   if not hasattr(api_client, 'initialized') or not api_client.initialized:
       # 客户端未初始化，尝试重新初始化
   ```

2. **连接状态检查**
   ```python
   if hasattr(api_client, 'health_check'):
       health_result = await api_client.health_check()
       return health_result
   ```

3. **异常恢复机制**
   ```python
   try:
       init_result = await api_client.initialize()
       if init_result:
           return True
   except Exception as reinit_e:
       return False
   ```

### 3. 具体操作级别的错误检测

#### 消息获取错误
```python
try:
    messages = await api_client.get_unread_messages(...)
except Exception as e:
    logger.error(f"获取未读消息失败: {e}")
    # 错误会被上层循环捕获并计数
```

#### 消息处理错误
```python
try:
    processed_msg = await message_processor.process_message(msg, api_client)
except Exception as e:
    logger.error(f"消息处理失败: {e}")
    # 继续处理下一条消息
```

#### 数据库操作错误
```python
try:
    message_id = await self._save_message(save_data)
except Exception as e:
    logger.error(f"保存消息失败: {e}")
    # 继续处理下一条消息
```

## 错误判断条件详解

### 1. 连续错误计数机制

**判断标准：**
- 任何在 `try-except` 块中捕获的 `Exception`（除了 `asyncio.CancelledError`）
- 每次循环迭代中发生的任何未预期异常

**计数逻辑：**
```python
try:
    # 执行任务
    consecutive_errors = 0  # 成功时重置
except asyncio.CancelledError:
    # 正常取消，不计入错误
    break
except Exception as e:
    consecutive_errors += 1  # 任何其他异常都计入错误
```

### 2. 渐进式错误处理

**阈值设置：**
- 主窗口检查循环：最大连续错误 5 次
- 监听对象检查循环：最大连续错误 5 次  
- 清理循环：最大连续错误 3 次

**处理策略：**
```python
if consecutive_errors >= max_consecutive_errors:
    # 连续错误过多，延长等待时间
    await asyncio.sleep(self.poll_interval * 3)  # 3倍等待时间
else:
    # 正常等待时间
    await asyncio.sleep(self.poll_interval)
```

### 3. API客户端健康状态判断

**健康状态判断条件：**

1. **客户端已初始化**
   ```python
   api_client.initialized == True
   ```

2. **健康检查通过**（如果支持）
   ```python
   await api_client.health_check() == True
   ```

3. **能够成功重新初始化**（故障恢复）
   ```python
   await api_client.initialize() == True
   ```

**故障判断条件：**
- 客户端未初始化且无法重新初始化
- 健康检查抛出异常且重新初始化失败
- 连续多次初始化失败

## 错误恢复策略

### 1. 自动重试机制

**重试条件：**
- 连续错误次数未达到阈值
- API客户端健康检查失败时自动重新初始化

**重试策略：**
```python
# 第1-4次错误：正常间隔重试
if consecutive_errors < max_consecutive_errors:
    await asyncio.sleep(self.poll_interval)

# 第5次及以上错误：延长间隔重试
else:
    await asyncio.sleep(self.poll_interval * 3)
```

### 2. 服务降级

**降级策略：**
- 跳过有问题的API客户端实例
- 继续处理其他正常的实例
- 保持服务整体可用性

```python
if not await self._check_api_client_health(instance_id, api_client):
    logger.warning(f"实例 {instance_id} API客户端连接异常，跳过本次检查")
    continue  # 跳过当前实例，处理下一个
```

### 3. 状态监控和日志记录

**监控指标：**
- 连续错误次数
- 错误类型和频率
- API客户端健康状态
- 服务运行时间

**日志级别：**
```python
# 单次错误：ERROR级别
logger.error(f"检查主窗口消息时出错 (连续错误: {consecutive_errors}/{max_consecutive_errors}): {e}")

# 连续错误达到阈值：WARNING级别
logger.warning(f"主窗口检查连续出错 {consecutive_errors} 次，延长等待时间")

# 健康检查失败：WARNING级别
logger.warning(f"实例 {instance_id} API客户端连接异常，跳过本次检查")
```

## 配置参数

### 可调整的错误处理参数

```python
# 错误阈值
max_consecutive_errors = 5  # 主窗口和监听对象检查
max_consecutive_errors = 3  # 清理任务

# 等待时间倍数
error_wait_multiplier = 3   # 错误时等待时间倍数

# 轮询间隔
poll_interval = 5          # 正常轮询间隔（秒）
cleanup_interval = 60      # 清理任务间隔（秒）
error_cleanup_interval = 180  # 错误时清理任务间隔（秒）
```

这种多层次的错误检测和处理机制确保了消息监听服务在面对各种异常情况时都能保持稳定运行，并具备自动恢复能力。
