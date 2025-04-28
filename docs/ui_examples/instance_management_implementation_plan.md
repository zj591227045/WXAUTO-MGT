# 实例管理界面实现计划

## 1. 文件结构

```
wxauto_mgt/
├── ui/
│   ├── components/
│   │   ├── instance_panel.py             # 修改现有文件
│   │   ├── instance_card_list.py         # 新增文件 - 实例卡片列表
│   │   ├── service_platform_panel.py     # 新增文件 - 服务平台管理面板
│   │   ├── delivery_rule_panel.py        # 新增文件 - 消息转发规则管理面板
│   │   └── dialogs/
│   │       ├── platform_dialog.py        # 新增文件 - 服务平台对话框
│   │       └── rule_dialog.py            # 新增文件 - 消息转发规则对话框
```

## 2. 实现步骤

### 2.1 阶段一：基础框架（预计耗时：4小时）

1. **修改 instance_panel.py**
   - 更新布局为水平分割
   - 左侧1/5宽度放置实例列表
   - 右侧4/5宽度放置水平分割的服务平台和规则面板
   - 实现基本的信号连接

2. **创建 instance_card_list.py**
   - 实现卡片布局的实例列表
   - 支持实例选择、添加、编辑、删除功能
   - 使用现有的实例管理逻辑

3. **创建 service_platform_panel.py 和 delivery_rule_panel.py 的基本框架**
   - 实现基本UI布局
   - 添加表格和按钮
   - 准备数据加载和操作函数

### 2.2 阶段二：功能实现（预计耗时：8小时）

1. **完善 service_platform_panel.py**
   - 实现服务平台列表加载
   - 实现添加、编辑、删除和测试连接功能
   - 创建 platform_dialog.py 实现添加/编辑对话框

2. **完善 delivery_rule_panel.py**
   - 实现规则列表加载
   - 实现添加、编辑、删除规则功能
   - 实现按实例过滤规则
   - 创建 rule_dialog.py 实现添加/编辑对话框

3. **实现数据交互**
   - 与 service_platform_manager.py 集成
   - 实现异步数据操作
   - 处理错误和异常情况

### 2.3 阶段三：集成与测试（预计耗时：4小时）

1. **集成各组件**
   - 连接信号和槽
   - 确保数据流正确
   - 实现组件间的交互

2. **测试功能**
   - 测试实例管理功能
   - 测试服务平台管理功能
   - 测试规则管理功能
   - 测试组件间交互

3. **优化UI**
   - 调整布局和间距
   - 添加样式和视觉效果
   - 优化用户体验

## 3. 关键类设计

### 3.1 InstanceCardList 类

```python
class InstanceCardList(QWidget):
    """实例卡片列表"""

    # 信号
    instance_selected = Signal(str)  # 实例ID
    instance_added = Signal(str)     # 实例ID
    instance_removed = Signal(str)   # 实例ID
    instance_updated = Signal(str)   # 实例ID

    def __init__(self, parent=None):
        super().__init__(parent)
        self._instances = {}  # 实例ID -> 卡片控件
        self._selected_id = None
        self._init_ui()

    def _init_ui(self):
        """初始化UI"""
        # 实现卡片列表UI

    @asyncSlot()
    async def refresh_instances(self):
        """刷新实例列表"""
        # 从数据库加载实例
        # 创建或更新卡片

    def _create_instance_card(self, instance_data):
        """创建实例卡片"""
        # 创建卡片控件
        # 设置样式和内容
        # 添加按钮和事件处理

    def _select_instance(self, instance_id):
        """选择实例"""
        # 更新选中状态
        # 发送信号
```

### 3.2 ServicePlatformPanel 类

```python
class ServicePlatformPanel(QWidget):
    """服务平台管理面板"""

    # 信号
    platform_added = Signal(str)    # 平台ID
    platform_updated = Signal(str)  # 平台ID
    platform_removed = Signal(str)  # 平台ID

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        """初始化UI"""
        # 实现服务平台管理UI

    @asyncSlot()
    async def refresh_platforms(self):
        """刷新平台列表"""
        # 从数据库加载平台
        # 更新表格

    def _add_platform(self):
        """添加平台"""
        # 显示添加对话框
        # 处理结果

    def _edit_platform(self, platform_id):
        """编辑平台"""
        # 显示编辑对话框
        # 处理结果

    def _delete_platform(self, platform_id):
        """删除平台"""
        # 确认删除
        # 执行删除操作

    def _test_platform(self, platform_id):
        """测试平台连接"""
        # 执行测试
        # 显示结果
```

### 3.3 DeliveryRulePanel 类

```python
class DeliveryRulePanel(QWidget):
    """消息转发规则管理面板"""

    # 信号
    rule_added = Signal(str)    # 规则ID
    rule_updated = Signal(str)  # 规则ID
    rule_removed = Signal(str)  # 规则ID

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_instance_id = None
        self._init_ui()

    def _init_ui(self):
        """初始化UI"""
        # 实现规则管理UI

    @asyncSlot()
    async def refresh_rules(self, instance_id=None):
        """刷新规则列表"""
        # 从数据库加载规则
        # 根据实例ID过滤
        # 更新表格

    def set_instance_filter(self, instance_id):
        """设置实例过滤器"""
        # 保存当前实例ID
        # 刷新规则列表

    def _add_rule(self):
        """添加规则"""
        # 显示添加对话框
        # 处理结果

    def _edit_rule(self, rule_id):
        """编辑规则"""
        # 显示编辑对话框
        # 处理结果

    def _delete_rule(self, rule_id):
        """删除规则"""
        # 确认删除
        # 执行删除操作
```

### 3.4 AddEditPlatformDialog 类

```python
class AddEditPlatformDialog(QDialog):
    """添加/编辑服务平台对话框"""

    def __init__(self, parent=None, platform_data=None):
        super().__init__(parent)
        self.platform_data = platform_data  # 如果是编辑模式，提供现有数据
        self._init_ui()

        if platform_data:
            self._load_platform_data()

    def _init_ui(self):
        """初始化UI"""
        # 实现对话框UI
        # 添加表单控件
        # 添加选项卡

    def _load_platform_data(self):
        """加载平台数据"""
        # 填充表单

    def get_platform_data(self):
        """获取平台数据"""
        # 收集表单数据
        # 返回数据字典

    @asyncSlot()
    async def _test_connection(self):
        """测试连接"""
        # 获取当前表单数据
        # 创建临时平台实例
        # 执行测试
        # 显示结果
```

### 3.5 AddEditRuleDialog 类

```python
class AddEditRuleDialog(QDialog):
    """添加/编辑消息转发规则对话框"""

    def __init__(self, parent=None, rule_data=None, current_instance_id=None):
        super().__init__(parent)
        self.rule_data = rule_data  # 如果是编辑模式，提供现有数据
        self.current_instance_id = current_instance_id  # 当前选中的实例ID
        self._init_ui()

        if rule_data:
            self._load_rule_data()

    def _init_ui(self):
        """初始化UI"""
        # 实现对话框UI
        # 添加表单控件

    async def _load_instances(self):
        """加载实例列表"""
        # 从数据库加载实例
        # 填充下拉框

    async def _load_platforms(self):
        """加载平台列表"""
        # 从数据库加载平台
        # 填充下拉框

    def _load_rule_data(self):
        """加载规则数据"""
        # 填充表单

    def get_rule_data(self):
        """获取规则数据"""
        # 收集表单数据
        # 返回数据字典
```

## 4. 数据交互

### 4.1 服务平台数据操作

```python
# 获取所有平台
platforms = await platform_manager.get_all_platforms()

# 添加平台
platform_id = await platform_manager.register_platform(
    platform_type,
    name,
    config
)

# 更新平台
success = await platform_manager.update_platform(
    platform_id,
    name,
    config
)

# 删除平台
success = await platform_manager.remove_platform(platform_id)

# 测试平台连接
result = await platform_manager.test_platform_connection(platform_id)
```

### 4.2 消息转发规则数据操作

```python
# 获取所有规则
rules = await rule_manager.get_all_rules()

# 获取特定实例的规则
rules = await rule_manager.get_rules_by_instance(instance_id)

# 添加规则
rule_id = await rule_manager.add_rule(
    name,
    instance_id,
    chat_pattern,
    platform_id,
    priority
)

# 更新规则
success = await rule_manager.update_rule(
    rule_id,
    name,
    instance_id,
    chat_pattern,
    platform_id,
    priority
)

# 删除规则
success = await rule_manager.remove_rule(rule_id)
```

## 5. 风险与应对措施

### 5.1 潜在风险

1. **异步操作导致UI卡顿**
   - 使用异步操作处理数据库交互
   - 在UI线程中显示加载指示器

2. **数据一致性问题**
   - 实现刷新机制确保数据同步
   - 添加错误处理和恢复机制

3. **用户体验问题**
   - 添加适当的提示和反馈
   - 确保操作有确认步骤

### 5.2 应对措施

1. **性能优化**
   - 使用延迟加载和分页技术
   - 缓存频繁访问的数据

2. **错误处理**
   - 添加全面的异常捕获
   - 提供用户友好的错误消息

3. **用户体验**
   - 添加加载指示器
   - 提供操作成功/失败的反馈

## 6. 测试计划

### 6.1 单元测试

1. 测试实例卡片列表的创建和更新
2. 测试服务平台面板的CRUD操作
3. 测试消息转发规则面板的CRUD操作

### 6.2 集成测试

1. 测试实例选择与规则过滤的交互
2. 测试服务平台和规则之间的关联
3. 测试数据变更后的UI更新

### 6.3 用户界面测试

1. 测试布局在不同窗口大小下的响应
2. 测试表单验证和错误提示
3. 测试操作流程的完整性
