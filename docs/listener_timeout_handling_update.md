# 监听器超时处理逻辑更新

## 概述

本次更新修改了WXAUTO-MGT项目中的监听列表处理逻辑，解决了监听对象超时后被删除导致无法保留历史记录的问题。

## 问题描述

**原有问题：**
- 程序在监听对象超时后，会从内存中移除监听对象，同时从数据库的listeners表中删除对应的记录
- 这导致监听窗口中无法保留历史监听记录
- 用户无法查看哪些是已超时的历史记录

## 解决方案

### 1. 超时处理逻辑修改

**修改前：**
- 超时监听对象会被从数据库中删除
- 历史记录完全丢失

**修改后：**
- 保持现有的从内存中移除监听对象的操作不变
- **不再删除**数据库listeners表中的记录
- 将超时记录的status字段更新为"inactive"状态
- 使用`_mark_listener_inactive`方法替代删除操作

### 2. 排序规则修改

**Python端：**
- 新增`get_all_listeners_sorted`方法
- 按照活跃状态排序（活跃在前）
- 相同状态内按最后活跃时间（last_message_time）降序排列

**Web端：**
- 修改API查询，添加ORDER BY子句
- 排序逻辑：`ORDER BY CASE WHEN status = 'active' THEN 0 ELSE 1 END, last_message_time DESC`
- JavaScript前端排序逻辑已经正确实现

### 3. 数据库优化

**新增索引：**
- `idx_listeners_last_message_time`：优化按最后消息时间排序的性能

**现有字段确认：**
- `status`字段：用于标记监听状态（'active'/'inactive'）
- `last_message_time`字段：记录最后活跃时间
- `manual_added`字段：标记手动添加的监听器（不受超时限制）

## 修改的文件

### 1. 数据库管理器 (`wxauto_mgt/data/db_manager.py`)
```python
# 添加last_message_time字段的索引
conn.execute("CREATE INDEX IF NOT EXISTS idx_listeners_last_message_time ON listeners(last_message_time)")
```

### 2. Web API (`wxauto_mgt/web/api.py`)
```python
# 添加排序逻辑到监听器列表查询
query += " ORDER BY CASE WHEN status = 'active' THEN 0 ELSE 1 END, last_message_time DESC"
```

### 3. 消息监听器 (`wxauto_mgt/core/message_listener.py`)
```python
# 新增排序方法
def get_all_listeners_sorted(self, instance_id: str = None) -> Dict[str, List[Dict]]:
    """获取所有监听对象列表（包括非活跃的），按状态和最后活跃时间排序"""
```

## 测试验证

### 测试脚本
- `wxauto_mgt/scripts/update_listener_timeout_handling.py`：验证修改和数据库结构
- `wxauto_mgt/scripts/test_timeout_handling.py`：测试超时处理逻辑

### 测试结果
✅ 所有测试通过：
1. 超时监听器正确标记为inactive
2. 手动添加的监听器不受超时影响  
3. 活跃监听器保持active状态
4. 所有记录都保留在数据库中，没有被删除
5. 排序逻辑正确（活跃在前，按时间降序）

## 最终效果

### 用户体验改进
1. **历史记录保留**：监听窗口中能够保留所有历史监听记录
2. **状态区分**：用户可以清楚看到哪些是当前活跃监听，哪些是已超时的历史记录
3. **智能排序**：记录按最后活跃时间排序，便于用户查看最近的监听活动
4. **性能优化**：通过数据库索引优化排序查询性能

### 技术改进
1. **数据完整性**：不再丢失历史监听数据
2. **状态管理**：清晰的活跃/非活跃状态管理
3. **查询性能**：优化的数据库索引提升查询速度
4. **代码一致性**：Python端和Web端排序逻辑保持一致

## 兼容性说明

- **向后兼容**：现有的监听器功能完全保持不变
- **数据迁移**：现有数据自动适配新的状态管理机制
- **API兼容**：Web API接口保持兼容，只是增加了排序功能

## 注意事项

1. **手动删除**：`remove_listener`方法仍然会完全删除监听器记录（用于用户主动删除）
2. **超时处理**：只有自动超时处理才会标记为inactive而不删除
3. **固定监听**：固定监听器和手动添加的监听器不受超时限制
4. **内存管理**：超时的监听器仍然会从内存中移除以节省资源

## 后续建议

1. 可以考虑添加批量清理inactive记录的功能（可选）
2. 可以在UI中添加过滤器，允许用户选择只显示活跃监听器
3. 可以添加监听器活跃状态的统计信息显示
