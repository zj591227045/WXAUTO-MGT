# 实例绑定消息规则的最佳实践（更新版）

## 1. 绑定方式设计

实例与消息规则的绑定应该直观、高效且符合用户操作习惯。以下是几种推荐的绑定方式，按照用户友好度排序：

### 1.1 实例选择驱动的绑定（推荐）

当用户在左侧选择一个实例时，右侧的规则面板自动过滤显示与该实例相关的规则，并提供"为此实例添加规则"的快捷按钮。

**优点**：
- 符合用户思维方式："我想为这个实例设置规则"
- 操作路径清晰
- 上下文关联明确

### 1.2 规则创建时的实例选择

在创建/编辑规则对话框中，提供实例选择下拉框，允许用户选择"全部实例"或特定实例。

**优点**：
- 灵活性高
- 可以一次创建适用于多个实例的规则

### 1.3 拖放绑定（高级交互）

允许用户从左侧实例列表拖动实例到右侧规则上，实现快速绑定。

**优点**：
- 操作直观
- 视觉反馈明确
- 提高高级用户的效率

## 2. 多规则支持与优先级

### 2.1 多规则支持

系统应支持为一个实例添加多个规则，以满足不同场景的需求：

1. **基于聊天对象的不同规则**：
   - 同一个微信实例中，VIP客户群使用高级GPT模型
   - 普通客户群使用标准Dify模型
   - 技术支持群使用专门训练的技术支持模型

2. **基于优先级的规则层级**：
   - 高优先级规则处理特定场景
   - 低优先级规则作为默认处理方式

### 2.2 规则优先级

规则优先级是解决规则冲突的关键机制：

1. **优先级定义**：
   - 优先级是一个整数值，数值越大表示优先级越高
   - 默认优先级为0
   - 推荐的优先级范围：0-100，便于用户理解和管理

2. **优先级分配建议**：
   | 优先级范围 | 适用场景 |
   |----------|---------|
   | 80-100   | 关键规则，必须优先应用 |
   | 50-79    | 重要规则，通常应该应用 |
   | 20-49    | 普通规则，在没有更高优先级规则时应用 |
   | 0-19     | 默认规则，作为兜底方案 |

### 2.3 规则匹配逻辑

当系统需要为一条消息确定应用哪条规则时，将按照以下逻辑进行匹配：

1. **筛选阶段**：首先筛选出所有可能适用的规则
   - 实例ID匹配：规则的实例ID等于消息的实例ID，或规则适用于所有实例（实例ID为"*"）
   - 聊天对象匹配：规则的聊天对象模式匹配消息的聊天对象名称

2. **排序阶段**：对筛选出的规则按照以下顺序进行排序
   - 首先按优先级降序排序（优先级高的规则排在前面）
   - 优先级相同时，按匹配精确度排序（精确匹配 > 正则表达式匹配 > 通配符匹配）
   - 如果以上条件都相同，则按规则ID排序，确保行为一致性

3. **选择阶段**：选择排序后的第一条规则应用

## 3. UI实现建议

### 3.1 实例选择状态

```
+---------------------------+
|  微信实例1                  |  <- 选中状态，背景色变化
|  状态: 在线                |     边框高亮，左侧添加蓝色指示条
|                           |
|  [编辑] [删除]             |
+---------------------------+
```

### 3.2 规则过滤与添加

```
+-----------------------------------------------------------+
|  消息转发规则配置                     [为当前实例添加规则] [+] |
+-----------------------------------------------------------+
|  当前过滤: 微信实例1                   [显示全部规则]        |
+-----------------------------------------------------------+
|  +-------------------------------------------------------+|
|  | ID | 名称     | 实例    | 聊天匹配  | 平台  | 优先级 | 操作  ||
|  |----+----------+---------+----------+------+-------+------+||
|  | 2  | VIP规则   | 微信实例1| VIP客户群 | GPT-4|  80 ⭐ |[编辑] ||
|  |    |          |         |          |      |       |[删除] ||
|  +-------------------------------------------------------+|
|                                                           |
|  [显示全部规则]                                             |
+-----------------------------------------------------------+
```

### 3.3 规则创建/编辑对话框

```
+-------------------------------------------+
|  添加消息转发规则                           |
+-------------------------------------------+
|  规则名称: [VIP客户规则           ]         |
|                                           |
|  适用实例:                                 |
|  ○ 所有实例                               |
|  ● 特定实例: [微信实例1 ▼         ]         |
|                                           |
|  聊天对象匹配:                             |
|  [VIP客户群                      ]         |
|  (支持精确匹配、* 或 regex:正则表达式)        |
|                                           |
|  服务平台: [GPT-4 ▼              ]         |
|                                           |
|  优先级:  [  80    ] ▲ ▼                  |
|  +---------------------------------------+|
|  |  0         低优先级            高优先级  ||
|  |  ●---------------------------------○  ||
|  |                       |               ||
|  |                      80              100|
|  +---------------------------------------+|
|  提示: 数字越大优先级越高                    |
|                                           |
|  [取消]                          [确定]     |
+-------------------------------------------+
```

### 3.4 冲突提示UI

当检测到规则冲突时，系统应提供清晰的视觉提示：

```
+-------------------------------------------+
|  ⚠️ 规则冲突警告                           |
+-------------------------------------------+
|  您正在创建的规则与以下现有规则存在冲突:     |
|                                           |
|  • "VIP规则" (优先级: 80)                  |
|    适用于: 微信实例1 / VIP客户群            |
|                                           |
|  您的新规则:                               |
|  • "测试规则" (优先级: 50)                  |
|    适用于: 微信实例1 / VIP客户群            |
|                                           |
|  由于新规则优先级较低，它可能不会被应用。     |
|                                           |
|  建议:                                     |
|  • 提高新规则的优先级 (>80)                 |
|  • 修改规则的适用范围以避免冲突              |
|  • 保持现状，接受基于优先级的规则应用         |
|                                           |
|  [取消]  [保持现状]  [提高优先级]  [修改范围] |
+-------------------------------------------+
```

## 4. 代码实现示例

### 4.1 规则匹配逻辑

```python
async def match_rule_for_message(instance_id: str, chat_name: str) -> Optional[Dict]:
    """
    为消息匹配适用的规则
    
    Args:
        instance_id: 实例ID
        chat_name: 聊天对象名称
        
    Returns:
        Optional[Dict]: 匹配的规则，如果没有匹配则返回None
    """
    # 获取所有启用的规则
    rules = await db_manager.fetchall(
        """
        SELECT * FROM delivery_rules 
        WHERE enabled = 1 
        AND (instance_id = ? OR instance_id = '*')
        ORDER BY priority DESC
        """,
        (instance_id,)
    )
    
    # 按匹配精确度分类规则
    exact_matches = []
    regex_matches = []
    wildcard_matches = []
    
    for rule in rules:
        pattern = rule['chat_pattern']
        
        # 精确匹配
        if pattern == chat_name:
            exact_matches.append(rule)
        # 通配符匹配
        elif pattern == '*':
            wildcard_matches.append(rule)
        # 正则表达式匹配
        elif pattern.startswith('regex:'):
            regex = pattern[6:]
            try:
                if re.match(regex, chat_name):
                    regex_matches.append(rule)
            except Exception as e:
                logger.error(f"正则表达式匹配失败: {e}")
    
    # 按优先级排序各类匹配
    exact_matches.sort(key=lambda x: (-x['priority'], x['rule_id']))
    regex_matches.sort(key=lambda x: (-x['priority'], x['rule_id']))
    wildcard_matches.sort(key=lambda x: (-x['priority'], x['rule_id']))
    
    # 按匹配精确度返回最佳匹配
    if exact_matches:
        return exact_matches[0]  # 返回优先级最高的精确匹配
    if regex_matches:
        return regex_matches[0]  # 返回优先级最高的正则匹配
    if wildcard_matches:
        return wildcard_matches[0]  # 返回优先级最高的通配符匹配
    
    return None  # 没有匹配的规则
```

### 4.2 冲突检测逻辑

```python
async def check_rule_conflicts(rule_data: Dict, rule_id: Optional[str] = None) -> List[Dict]:
    """
    检查规则冲突
    
    Args:
        rule_data: 规则数据
        rule_id: 当前规则ID（编辑模式下使用）
        
    Returns:
        List[Dict]: 冲突规则列表
    """
    instance_id = rule_data.get('instance_id', '*')
    chat_pattern = rule_data.get('chat_pattern', '*')
    priority = rule_data.get('priority', 0)
    
    # 查询可能冲突的规则
    query = """
    SELECT * FROM delivery_rules 
    WHERE enabled = 1 
    AND (instance_id = ? OR instance_id = '*' OR ? = '*')
    """
    params = [instance_id, instance_id]
    
    # 如果是编辑模式，排除当前规则
    if rule_id:
        query += " AND rule_id != ?"
        params.append(rule_id)
    
    rules = await db_manager.fetchall(query, tuple(params))
    
    # 检查冲突
    conflicts = []
    for rule in rules:
        # 检查聊天对象模式是否冲突
        if _patterns_conflict(chat_pattern, rule['chat_pattern']):
            # 如果冲突，添加到冲突列表
            conflicts.append(rule)
    
    # 按优先级排序冲突规则
    conflicts.sort(key=lambda x: -x['priority'])
    
    return conflicts

def _patterns_conflict(pattern1: str, pattern2: str) -> bool:
    """
    检查两个模式是否冲突
    
    Args:
        pattern1: 第一个模式
        pattern2: 第二个模式
        
    Returns:
        bool: 是否冲突
    """
    # 如果任一模式是通配符，则冲突
    if pattern1 == '*' or pattern2 == '*':
        return True
    
    # 如果两个模式完全相同，则冲突
    if pattern1 == pattern2:
        return True
    
    # 检查正则表达式冲突（简化版，实际实现可能更复杂）
    if pattern1.startswith('regex:') or pattern2.startswith('regex:'):
        # 这里需要更复杂的逻辑来检查正则表达式是否冲突
        # 简化起见，我们假设正则表达式可能冲突
        return True
    
    # 默认不冲突
    return False
```

## 5. 最佳实践建议

1. **使用有意义的优先级**：
   - 为不同类型的规则分配不同范围的优先级
   - 避免所有规则使用相同的优先级

2. **优先使用精确匹配**：
   - 尽可能使用精确的聊天对象名称，而不是通配符
   - 仅在必要时使用正则表达式和通配符

3. **设置默认规则**：
   - 创建一个低优先级的默认规则，确保所有消息都能被处理
   - 默认规则应使用通配符匹配所有聊天对象

4. **使用优先级间隔**：
   - 在相关规则之间留出优先级间隔（如10或20）
   - 这样可以在不调整其他规则的情况下插入新规则

5. **定期检查规则冲突**：
   - 使用"检查冲突"功能定期审查规则
   - 解决发现的冲突，确保系统行为符合预期
