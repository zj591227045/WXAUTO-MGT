# 实例管理界面UI设计与集成方案

## 1. 概述

本文档提供了wxauto_Mgt项目实例管理界面的UI设计和集成方案，根据需求将实现以下功能：

1. 将实例管理列表修改为竖向的卡片布局
2. 在右侧添加两个窗口，分别用于显示服务平台配置和消息转发规则配置
3. 支持新建、编辑、删除服务平台和消息转发规则
4. 支持将规则绑定到对应的实例

## 2. UI设计图

### 2.1 整体布局

```
+----------------------------------------------------------------------+
|                           实例管理                                     |
+----------+------------------------+----------------------------------+
|          |                        |                                  |
|  实例列表  |     服务平台配置         |       消息转发规则配置              |
| (卡片布局) |                        |                                  |
|          |                        |                                  |
|          |                        |                                  |
|          |                        |                                  |
|          |                        |                                  |
|          |                        |                                  |
|          |                        |                                  |
+----------+------------------------+----------------------------------+
```

### 2.2 实例列表（卡片布局）

```
+---------------------------+
|  实例1                     |
|  名称: 微信实例1            |
|  状态: 在线                |
|  [编辑] [删除]             |
+---------------------------+
|  实例2                     |
|  名称: 微信实例2            |
|  状态: 离线                |
|  [编辑] [删除]             |
+---------------------------+
|  [+ 添加实例]              |
+---------------------------+
```

### 2.3 服务平台配置

```
+-----------------------------------------------------------+
|  服务平台配置                                  [+ 添加平台]  |
+-----------------------------------------------------------+
|                                                           |
|  平台列表:                                                 |
|  +-------------------------------------------------------+|
|  | ID | 名称 | 类型 | 状态 | 操作                          ||
|  |----+------+------+------+---------------------------+||
|  | 1  | Dify | dify | 启用 | [编辑] [删除] [测试连接]      ||
|  | 2  | GPT  |openai| 启用 | [编辑] [删除] [测试连接]      ||
|  +-------------------------------------------------------+|
|                                                           |
+-----------------------------------------------------------+
```

### 2.4 消息转发规则配置

```
+-----------------------------------------------------------+
|  消息转发规则配置                                [+ 添加规则] |
+-----------------------------------------------------------+
|                                                           |
|  规则列表:                                                 |
|  +-------------------------------------------------------+|
|  | ID | 名称 | 实例 | 聊天匹配 | 平台 | 优先级 | 操作        ||
|  |----+------+------+---------+------+--------+----------+||
|  | 1  |默认规则| 全部 |    *    | Dify |   0    |[编辑][删除]||
|  | 2  |VIP规则|实例1 |VIP客户群 | GPT  |   10   |[编辑][删除]||
|  +-------------------------------------------------------+|
|                                                           |
+-----------------------------------------------------------+
```

### 2.5 添加/编辑服务平台对话框

```
+-------------------------------------------+
|  添加服务平台                               |
+-------------------------------------------+
|  平台名称: [                    ]          |
|  平台类型: [下拉选择: dify/openai]          |
|                                           |
|  [选项卡: Dify配置]                         |
|  API基础URL: [                    ]        |
|  API密钥:    [                    ]        |
|  会话ID:     [                    ]        |
|                                           |
|  [选项卡: OpenAI配置]                       |
|  API密钥:    [                    ]        |
|  模型:       [                    ]        |
|  系统提示:    [                    ]        |
|                                           |
|  [测试连接]    [取消]    [确定]              |
+-------------------------------------------+
```

### 2.6 添加/编辑消息转发规则对话框

```
+-------------------------------------------+
|  添加消息转发规则                           |
+-------------------------------------------+
|  规则名称: [                    ]          |
|  微信实例: [下拉选择: 全部/实例1/实例2]       |
|  聊天对象匹配: [                    ]       |
|  服务平台: [下拉选择: Dify/GPT]             |
|  优先级:  [数字输入框]                      |
|                                           |
|  [取消]    [确定]                          |
+-------------------------------------------+
```

## 3. 技术实现方案

### 3.1 组件结构

1. **主面板类**: `InstanceManagerPanel` - 继承自 `QWidget`，包含整体布局和子组件
2. **实例列表组件**: `InstanceCardList` - 自定义组件，显示实例卡片列表
3. **服务平台配置组件**: `ServicePlatformPanel` - 自定义组件，管理服务平台
4. **消息转发规则组件**: `DeliveryRulePanel` - 自定义组件，管理消息转发规则
5. **对话框组件**:
   - `AddEditPlatformDialog` - 添加/编辑服务平台对话框
   - `AddEditRuleDialog` - 添加/编辑消息转发规则对话框

### 3.2 数据流

1. 实例管理面板初始化时，加载实例列表、服务平台列表和规则列表
2. 当用户选择一个实例时，更新规则列表以显示与该实例相关的规则
3. 添加/编辑/删除操作通过异步方式与数据库交互
4. 使用信号槽机制在组件之间传递事件和数据更新

### 3.3 关键类设计

#### 3.3.1 InstanceManagerPanel

```python
class InstanceManagerPanel(QWidget):
    """实例管理面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        """初始化UI"""
        # 主布局 - 水平分割
        main_layout = QHBoxLayout(self)

        # 左侧实例列表 (1/5宽度)
        self.instance_list = InstanceCardList(self)

        # 中间和右侧分割窗口
        self.content_splitter = QSplitter(Qt.Horizontal)

        # 中间部分 - 服务平台配置
        self.platform_panel = ServicePlatformPanel(self)

        # 右侧部分 - 消息转发规则配置
        self.rule_panel = DeliveryRulePanel(self)

        # 添加到分割器
        self.content_splitter.addWidget(self.platform_panel)
        self.content_splitter.addWidget(self.rule_panel)

        # 设置分割比例
        self.content_splitter.setSizes([300, 300])

        # 添加到主布局
        main_layout.addWidget(self.instance_list, 1)  # 1/5宽度
        main_layout.addWidget(self.content_splitter, 4)  # 4/5宽度

        # 连接信号
        self.instance_list.instance_selected.connect(self._on_instance_selected)
        self.instance_list.instance_added.connect(self._on_instance_added)
        self.instance_list.instance_removed.connect(self._on_instance_removed)
        self.instance_list.instance_updated.connect(self._on_instance_updated)
```

#### 3.3.2 InstanceCardList

```python
class InstanceCardList(QWidget):
    """实例卡片列表"""

    # 信号定义
    instance_selected = Signal(str)  # 实例ID
    instance_added = Signal(str)     # 实例ID
    instance_removed = Signal(str)   # 实例ID
    instance_updated = Signal(str)   # 实例ID

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        """初始化UI"""
        # 主布局
        main_layout = QVBoxLayout(self)

        # 工具栏
        toolbar_layout = QHBoxLayout()

        # 添加实例按钮
        self.add_btn = QPushButton("添加实例")
        self.add_btn.clicked.connect(self._add_instance)
        toolbar_layout.addWidget(self.add_btn)

        # 刷新按钮
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self.refresh_instances)
        toolbar_layout.addWidget(self.refresh_btn)

        toolbar_layout.addStretch()

        main_layout.addLayout(toolbar_layout)

        # 实例卡片滚动区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # 卡片容器
        self.card_container = QWidget()
        self.card_layout = QVBoxLayout(self.card_container)
        self.card_layout.setSpacing(10)
        self.card_layout.addStretch()

        self.scroll_area.setWidget(self.card_container)
        main_layout.addWidget(self.scroll_area)

        # 状态标签
        self.status_label = QLabel("共 0 个实例")
        main_layout.addWidget(self.status_label)
```

#### 3.3.3 ServicePlatformPanel

```python
class ServicePlatformPanel(QWidget):
    """服务平台配置面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        """初始化UI"""
        # 主布局
        main_layout = QVBoxLayout(self)

        # 标题栏
        title_layout = QHBoxLayout()
        title_label = QLabel("服务平台配置")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        title_layout.addWidget(title_label)

        title_layout.addStretch()

        # 添加平台按钮
        self.add_btn = QPushButton("添加平台")
        self.add_btn.clicked.connect(self._add_platform)
        title_layout.addWidget(self.add_btn)

        main_layout.addLayout(title_layout)

        # 平台列表表格
        self.platform_table = QTableWidget(0, 5)  # 0行，5列
        self.platform_table.setHorizontalHeaderLabels(["ID", "名称", "类型", "状态", "操作"])
        self.platform_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.platform_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.platform_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.platform_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.platform_table.setEditTriggers(QTableWidget.NoEditTriggers)

        main_layout.addWidget(self.platform_table)
```

#### 3.3.4 DeliveryRulePanel

```python
class DeliveryRulePanel(QWidget):
    """消息转发规则配置面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        """初始化UI"""
        # 主布局
        main_layout = QVBoxLayout(self)

        # 标题栏
        title_layout = QHBoxLayout()
        title_label = QLabel("消息转发规则配置")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        title_layout.addWidget(title_label)

        title_layout.addStretch()

        # 添加规则按钮
        self.add_btn = QPushButton("添加规则")
        self.add_btn.clicked.connect(self._add_rule)
        title_layout.addWidget(self.add_btn)

        main_layout.addLayout(title_layout)

        # 规则列表表格
        self.rule_table = QTableWidget(0, 7)  # 0行，7列
        self.rule_table.setHorizontalHeaderLabels(["ID", "名称", "实例", "聊天匹配", "平台", "优先级", "操作"])
        self.rule_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.rule_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.rule_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.rule_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.rule_table.setEditTriggers(QTableWidget.NoEditTriggers)

        main_layout.addWidget(self.rule_table)
```

## 4. 集成方案

### 4.1 文件结构

```
wxauto_mgt/
├── ui/
│   ├── components/
│   │   ├── instance_panel.py         # 修改现有文件
│   │   ├── instance_card_list.py     # 新增文件
│   │   ├── service_platform_panel.py # 新增文件
│   │   ├── delivery_rule_panel.py    # 新增文件
│   │   └── dialogs/                  # 对话框组件
│   │       ├── platform_dialog.py    # 新增文件
│   │       └── rule_dialog.py        # 新增文件
```

### 4.2 集成步骤

1. **修改现有的实例管理面板**:
   - 更新 `instance_panel.py` 文件，实现新的布局和组件集成
   - 保留现有的实例管理功能，但改为卡片布局

2. **实现新组件**:
   - 创建 `instance_card_list.py` 实现实例卡片列表
   - 创建 `service_platform_panel.py` 实现服务平台管理
   - 创建 `delivery_rule_panel.py` 实现消息转发规则管理

3. **实现对话框组件**:
   - 创建 `platform_dialog.py` 实现服务平台添加/编辑对话框
   - 创建 `rule_dialog.py` 实现消息转发规则添加/编辑对话框

4. **数据库交互**:
   - 使用现有的 `service_platform_manager.py` 和相关类进行数据操作
   - 确保异步操作正确处理UI更新

### 4.3 UI样式

为了保持一致的视觉风格，将使用以下样式指南：

1. **卡片样式**:
   ```css
   QWidget.card {
       background-color: #f5f5f5;
       border-radius: 4px;
       border: 1px solid #e0e0e0;
       padding: 10px;
   }
   ```

2. **标题样式**:
   ```css
   QLabel.title {
       font-size: 14px;
       font-weight: bold;
   }
   ```

3. **按钮样式**:
   ```css
   QPushButton.action-button {
       padding: 4px 8px;
       border-radius: 3px;
   }
   ```

## 5. 实现计划

### 5.1 阶段一：基础框架

1. 修改 `instance_panel.py` 实现新的布局结构
2. 创建 `instance_card_list.py` 实现卡片列表基本功能
3. 创建 `service_platform_panel.py` 和 `delivery_rule_panel.py` 的基本框架

### 5.2 阶段二：功能实现

1. 完善实例卡片列表，支持添加、编辑、删除实例
2. 实现服务平台管理功能，包括添加、编辑、删除和测试连接
3. 实现消息转发规则管理功能，包括添加、编辑、删除规则

### 5.3 阶段三：集成与测试

1. 集成各组件，实现数据流和交互
2. 测试各功能点，确保正常工作
3. 优化UI细节和用户体验

## 6. 注意事项

1. **异步处理**:
   - 所有数据库操作应使用异步方式进行
   - 使用 `asyncSlot` 装饰器处理异步UI更新

2. **错误处理**:
   - 添加适当的错误处理和用户反馈
   - 使用日志记录关键操作和错误

3. **性能考虑**:
   - 避免在UI线程中进行耗时操作
   - 使用延迟加载和分页技术处理大量数据

4. **兼容性**:
   - 确保新UI与现有功能兼容
   - 保留现有的API和数据结构
