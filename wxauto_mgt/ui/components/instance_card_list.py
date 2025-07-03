"""
实例卡片列表组件

该模块实现了实例卡片列表，用于在实例管理面板中以卡片形式显示实例。
"""

from typing import Dict, Optional, Any

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QSizePolicy, QMessageBox
)

from wxauto_mgt.utils.logging import get_logger
from qasync import asyncSlot

logger = get_logger()

class InstanceCard(QFrame):
    """实例卡片组件"""

    # 定义信号
    selected = Signal(str)  # 实例ID
    edit_requested = Signal(str)  # 实例ID
    delete_requested = Signal(str)  # 实例ID
    initialize_requested = Signal(str)  # 实例ID
    auto_login_requested = Signal(str)  # 实例ID
    qrcode_requested = Signal(str)  # 实例ID

    def __init__(self, instance_data: Dict[str, Any], parent=None):
        """
        初始化实例卡片

        Args:
            instance_data: 实例数据
            parent: 父组件
        """
        super().__init__(parent)

        self.instance_id = instance_data.get("instance_id", "")
        self.instance_name = instance_data.get("name", "")
        self.instance_url = instance_data.get("base_url", "")
        self.is_selected = False

        # 设置对象名称以便样式表可以精确定位
        self.setObjectName("instance_card")

        self._init_ui()

    def _init_ui(self):
        """初始化UI"""
        # 设置卡片样式
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Raised)
        # 设置卡片基本样式
        self.setStyleSheet("""
            QFrame#instance_card {
                background-color: #ffffff;
                border-radius: 4px;
                border: 1px solid #e0e0e0;
                padding: 4px;
            }
            QLabel {
                color: #333333;
                background-color: transparent;
                border: none;
            }
        """)
        # 使用自适应高度，允许卡片根据内容自动调整高度
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        # 设置最小高度以容纳所有按钮
        self.setMinimumHeight(160)  # 增加最小高度以容纳三行按钮

        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)  # 增加内边距
        main_layout.setSpacing(8)  # 增加组件间距

        # 标题行
        title_layout = QHBoxLayout()

        # 实例名称
        self.name_label = QLabel(self.instance_name)
        self.name_label.setStyleSheet("""
            font-weight: bold;
            color: #1a1a1a;
            padding: 2px;
        """)
        # 设置字体自适应
        font = self.name_label.font()
        font.setPointSize(int(font.pointSize() * 1.2))  # 增大字体但不固定大小
        self.name_label.setFont(font)
        self.name_label.setWordWrap(True)  # 允许文本换行
        title_layout.addWidget(self.name_label)

        title_layout.addStretch()

        main_layout.addLayout(title_layout)

        # 实例ID
        id_layout = QHBoxLayout()
        id_label = QLabel("ID:")
        id_label.setStyleSheet("color: #444444; font-weight: bold;")
        # 使用相对字体大小
        font = id_label.font()
        font.setPointSize(int(font.pointSize() * 0.9))  # 稍微小一点的字体
        id_label.setFont(font)
        id_layout.addWidget(id_label)

        self.id_value = QLabel(self.instance_id)
        self.id_value.setStyleSheet("color: #333333;")
        # 使用相对字体大小
        font = self.id_value.font()
        font.setPointSize(int(font.pointSize() * 0.9))  # 稍微小一点的字体
        self.id_value.setFont(font)
        self.id_value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.id_value.setCursor(Qt.IBeamCursor)
        self.id_value.setWordWrap(True)  # 允许文本换行
        id_layout.addWidget(self.id_value, 1)  # 添加拉伸因子

        id_layout.addStretch(1)

        main_layout.addLayout(id_layout)

        # 保存URL值的标签，但不显示在UI中
        self.url_value = QLabel(self.instance_url)
        self.url_value.hide()

        # 添加一些垂直空间
        main_layout.addSpacing(5)

        # 按钮区域 - 多行布局
        buttons_container = QVBoxLayout()
        buttons_container.setSpacing(8)  # 行间距

        # 第一行按钮：编辑和删除
        first_row_layout = QHBoxLayout()
        first_row_layout.setSpacing(10)
        first_row_layout.addStretch(1)  # 左侧弹性空间

        # 编辑按钮
        self.edit_btn = QPushButton("编辑")
        self.edit_btn.setStyleSheet("""
            QPushButton {
                background-color: #1890ff;
                color: white;
                border: none;
                padding: 6px 15px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 60px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #40a9ff;
            }
            QPushButton:pressed {
                background-color: #096dd9;
            }
        """)
        font = self.edit_btn.font()
        font.setPointSize(int(font.pointSize() * 1.0))
        self.edit_btn.setFont(font)
        self.edit_btn.clicked.connect(self._on_edit_clicked)
        self.edit_btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.edit_btn.setMinimumHeight(30)
        first_row_layout.addWidget(self.edit_btn)

        # 删除按钮
        self.delete_btn = QPushButton("删除")
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff4d4f;
                color: white;
                border: none;
                padding: 6px 15px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 60px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #ff7875;
            }
            QPushButton:pressed {
                background-color: #cf1322;
            }
        """)
        font = self.delete_btn.font()
        font.setPointSize(int(font.pointSize() * 1.0))
        self.delete_btn.setFont(font)
        self.delete_btn.clicked.connect(self._on_delete_clicked)
        self.delete_btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.delete_btn.setMinimumHeight(30)
        first_row_layout.addWidget(self.delete_btn)

        first_row_layout.addStretch(1)  # 右侧弹性空间
        buttons_container.addLayout(first_row_layout)

        # 第二行按钮：自动登录（占满整行）
        second_row_layout = QHBoxLayout()
        second_row_layout.setSpacing(0)

        self.auto_login_btn = QPushButton("自动登录")
        self.auto_login_btn.setStyleSheet("""
            QPushButton {
                background-color: #52c41a;
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #73d13d;
            }
            QPushButton:pressed {
                background-color: #389e0d;
            }
        """)
        font = self.auto_login_btn.font()
        font.setPointSize(int(font.pointSize() * 1.0))
        self.auto_login_btn.setFont(font)
        self.auto_login_btn.clicked.connect(self._on_auto_login_clicked)
        self.auto_login_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.auto_login_btn.setMinimumHeight(32)
        second_row_layout.addWidget(self.auto_login_btn)

        buttons_container.addLayout(second_row_layout)

        # 第三行按钮：登录码（占满整行）
        third_row_layout = QHBoxLayout()
        third_row_layout.setSpacing(0)

        self.qrcode_btn = QPushButton("获取登录二维码")
        self.qrcode_btn.setStyleSheet("""
            QPushButton {
                background-color: #722ed1;
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #9254de;
            }
            QPushButton:pressed {
                background-color: #531dab;
            }
        """)
        font = self.qrcode_btn.font()
        font.setPointSize(int(font.pointSize() * 1.0))
        self.qrcode_btn.setFont(font)
        self.qrcode_btn.clicked.connect(self._on_qrcode_clicked)
        self.qrcode_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.qrcode_btn.setMinimumHeight(32)
        third_row_layout.addWidget(self.qrcode_btn)

        buttons_container.addLayout(third_row_layout)

        # 隐藏初始化按钮，但保留属性以便代码兼容
        self.init_btn = QPushButton("初始化")
        self.init_btn.hide()
        self.init_btn.clicked.connect(self._on_initialize_clicked)

        main_layout.addLayout(buttons_container)

        # 设置鼠标点击事件
        self.mousePressEvent = self._on_mouse_press

    def _on_mouse_press(self, _):
        """
        鼠标点击事件

        Args:
            _: 鼠标事件对象（未使用）
        """
        # 发送选中信号
        self.selected.emit(self.instance_id)

    def _on_edit_clicked(self):
        """编辑按钮点击事件"""
        self.edit_requested.emit(self.instance_id)

    def _on_delete_clicked(self):
        """删除按钮点击事件"""
        self.delete_requested.emit(self.instance_id)

    def _on_initialize_clicked(self):
        """初始化按钮点击事件"""
        self.initialize_requested.emit(self.instance_id)

    def _on_auto_login_clicked(self):
        """自动登录按钮点击事件"""
        self.auto_login_requested.emit(self.instance_id)

    def _on_qrcode_clicked(self):
        """二维码按钮点击事件"""
        self.qrcode_requested.emit(self.instance_id)

    def set_selected(self, selected: bool):
        """
        设置选中状态

        Args:
            selected: 是否选中
        """
        self.is_selected = selected

        # 根据选中状态改变背景色和边框，但保持标签样式不变
        if selected:
            # 选中状态：蓝色背景和边框
            self.setStyleSheet("""
                QFrame#instance_card {
                    background-color: #e6f7ff;
                    border-radius: 4px;
                    border: 2px solid #1890ff;
                    padding: 4px;
                }
                QLabel {
                    background-color: transparent;
                    border: none;
                    color: #333333;
                }
            """)
        else:
            # 非选中状态：白色背景和灰色边框
            self.setStyleSheet("""
                QFrame#instance_card {
                    background-color: #ffffff;
                    border-radius: 4px;
                    border: 1px solid #e0e0e0;
                    padding: 4px;
                }
                QLabel {
                    background-color: transparent;
                    border: none;
                    color: #333333;
                }
            """)

        # 设置对象名称以便样式表可以精确定位
        self.setObjectName("instance_card")

    def update_data(self, instance_data: Dict[str, Any]):
        """
        更新实例数据

        Args:
            instance_data: 实例数据
        """
        self.instance_name = instance_data.get("name", self.instance_name)
        self.instance_url = instance_data.get("base_url", self.instance_url)

        # 更新UI
        self.name_label.setText(self.instance_name)
        self.url_value.setText(self.instance_url)


class InstanceCardList(QWidget):
    """实例卡片列表组件"""

    # 定义信号
    instance_selected = Signal(str)  # 实例ID
    instance_added = Signal(str)  # 实例ID
    instance_removed = Signal(str)  # 实例ID
    instance_updated = Signal(str)  # 实例ID
    edit_requested = Signal(str)  # 实例ID
    delete_requested = Signal(str)  # 实例ID
    initialize_requested = Signal(str)  # 实例ID
    auto_login_requested = Signal(str)  # 实例ID
    qrcode_requested = Signal(str)  # 实例ID
    add_local_requested = Signal()  # 添加本机实例请求

    def __init__(self, parent=None):
        """初始化实例卡片列表"""
        super().__init__(parent)

        self._instances = {}  # 实例ID -> 卡片组件
        self._selected_id = None

        self._init_ui()

    def _init_ui(self):
        """初始化UI"""
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(10)

        # 工具栏
        toolbar_layout = QHBoxLayout()

        # 添加实例按钮
        self.add_btn = QPushButton("添加实例")
        self.add_btn.setStyleSheet("""
            QPushButton {
                background-color: #1890ff;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #40a9ff;
            }
        """)
        self.add_btn.clicked.connect(self._on_add_clicked)
        toolbar_layout.addWidget(self.add_btn)

        # 添加本机按钮
        self.add_local_btn = QPushButton("添加本机")
        self.add_local_btn.setStyleSheet("""
            QPushButton {
                background-color: #fa8c16;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #ffa940;
            }
        """)
        self.add_local_btn.clicked.connect(self._on_add_local_clicked)
        toolbar_layout.addWidget(self.add_local_btn)

        # 刷新按钮
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #52c41a;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #73d13d;
            }
        """)
        self.refresh_btn.clicked.connect(self.refresh_instances)
        toolbar_layout.addWidget(self.refresh_btn)

        toolbar_layout.addStretch()

        main_layout.addLayout(toolbar_layout)

        # 卡片滚动区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)

        # 卡片容器
        self.card_container = QWidget()
        self.card_layout = QVBoxLayout(self.card_container)
        self.card_layout.setContentsMargins(8, 8, 8, 8)
        self.card_layout.setSpacing(12)  # 增加卡片间距以适应新的高度
        # 设置卡片容器的自适应策略
        self.card_container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.card_layout.addStretch()

        self.scroll_area.setWidget(self.card_container)
        main_layout.addWidget(self.scroll_area)

        # 状态标签
        self.status_label = QLabel("共 0 个实例")
        self.status_label.setStyleSheet("color: #666666;")
        main_layout.addWidget(self.status_label)

    def _on_add_clicked(self):
        """添加实例按钮点击事件"""
        # 这个事件会被父组件捕获并处理
        # 不需要在这里实现，因为我们已经在 InstanceManagerPanel 中连接了这个按钮的点击事件

    def _on_add_local_clicked(self):
        """添加本机按钮点击事件"""
        # 显示确认对话框
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("添加本机实例")
        msg_box.setIcon(QMessageBox.Question)

        # 设置详细信息
        msg_text = "将要添加以下默认本机实例：\n\n"
        msg_text += "• 实例名称：本机\n"
        msg_text += "• API地址：http://localhost:5000\n"
        msg_text += "• API密钥：test-key-2\n\n"
        msg_text += "⚠️ 重要提醒：请勿修改默认的API密钥（test-key-2），\n"
        msg_text += "以确保本机服务正常运行。\n\n"
        msg_text += "确定要添加此实例吗？"

        msg_box.setText(msg_text)
        msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg_box.setDefaultButton(QMessageBox.Yes)

        # 设置按钮文本
        yes_btn = msg_box.button(QMessageBox.Yes)
        no_btn = msg_box.button(QMessageBox.No)
        yes_btn.setText("确定添加")
        no_btn.setText("取消")

        # 显示对话框并处理结果
        if msg_box.exec() == QMessageBox.Yes:
            # 发送添加本机实例的信号
            self.add_local_requested.emit()

    @asyncSlot()
    async def refresh_instances(self):
        """刷新实例列表"""
        try:
            # 清空卡片容器
            for card in self._instances.values():
                card.deleteLater()
            self._instances.clear()

            # 从数据库获取实例列表
            from wxauto_mgt.data.db_manager import db_manager

            # 检查数据库管理器是否已初始化
            if not hasattr(db_manager, '_initialized') or not db_manager._initialized:
                logger.warning("数据库管理器未初始化，尝试初始化...")
                try:
                    await db_manager.initialize()
                    logger.info("数据库管理器初始化成功")
                except Exception as db_init_error:
                    logger.error(f"数据库管理器初始化失败: {db_init_error}")
                    import traceback
                    logger.error(f"异常堆栈: {traceback.format_exc()}")
                    # 显示空列表
                    self.status_label.setText("数据库连接失败，无法加载实例")
                    return

            # 查询所有启用的实例
            try:
                query = "SELECT * FROM instances WHERE enabled = 1"
                logger.debug(f"执行查询: {query}")
                instances = await db_manager.fetchall(query)
                logger.debug(f"查询结果: {len(instances)} 个实例")

                # 如果没有实例，尝试查询所有实例(不限制enabled)
                if not instances:
                    query = "SELECT * FROM instances"
                    logger.debug(f"执行查询: {query}")
                    instances = await db_manager.fetchall(query)
                    logger.debug(f"查询结果: {len(instances)} 个实例")
            except Exception as query_error:
                logger.error(f"查询实例失败: {query_error}")
                import traceback
                logger.error(f"异常堆栈: {traceback.format_exc()}")
                # 显示空列表
                self.status_label.setText("查询实例失败")
                return

            # 检查实例列表是否为空
            if not instances:
                logger.warning("没有找到任何实例")
                self.status_label.setText("没有找到任何实例")
                return

            logger.debug(f"加载了 {len(instances)} 个实例")

            # 记录实例详情
            for i, instance in enumerate(instances):
                logger.debug(f"实例 {i+1}: ID={instance.get('instance_id')}, 名称={instance.get('name')}")

            # 添加实例卡片
            for instance in instances:
                # 确保实例数据包含必要的字段
                if not instance.get("instance_id"):
                    logger.warning(f"实例数据缺少ID字段: {instance}")
                    continue

                # 确保实例数据包含名称和URL
                if not instance.get("name"):
                    instance["name"] = f"实例 {instance.get('instance_id')}"

                if not instance.get("base_url"):
                    instance["base_url"] = "未设置"

                # 添加实例卡片
                try:
                    self._add_instance_card(instance)
                    logger.debug(f"已添加实例卡片: {instance.get('instance_id')}")
                except Exception as card_error:
                    logger.error(f"添加实例卡片失败: {card_error}")
                    import traceback
                    logger.error(f"异常堆栈: {traceback.format_exc()}")
                    # 继续添加其他卡片

            # 更新状态标签
            self.status_label.setText(f"共 {len(instances)} 个实例")

            # 更新实例状态
            try:
                await self._update_instance_status()
            except Exception as status_error:
                logger.error(f"更新实例状态失败: {status_error}")
                import traceback
                logger.error(f"异常堆栈: {traceback.format_exc()}")

        except Exception as e:
            logger.error(f"刷新实例列表失败: {e}")
            import traceback
            logger.error(f"异常堆栈: {traceback.format_exc()}")
            # 显示错误信息
            self.status_label.setText("刷新实例列表失败")

    def _add_instance_card(self, instance_data: Dict[str, Any]):
        """
        添加实例卡片

        Args:
            instance_data: 实例数据
        """
        instance_id = instance_data.get("instance_id", "")
        if not instance_id:
            logger.error(f"实例数据缺少ID字段: {instance_data}")
            return

        # 创建卡片
        card = InstanceCard(instance_data, self)

        # 连接信号
        card.selected.connect(self._on_instance_selected)
        card.edit_requested.connect(self._on_instance_edit)
        card.delete_requested.connect(self._on_instance_delete)
        card.initialize_requested.connect(self._on_instance_initialize)
        card.auto_login_requested.connect(self._on_instance_auto_login)
        card.qrcode_requested.connect(self._on_instance_qrcode)

        # 添加到布局
        self.card_layout.insertWidget(self.card_layout.count() - 1, card)

        # 保存到实例字典
        self._instances[instance_id] = card

        # 如果是第一个实例，自动选中
        if len(self._instances) == 1 and self._selected_id is None:
            self._on_instance_selected(instance_id)

    def _on_instance_selected(self, instance_id: str):
        """
        实例选中事件

        Args:
            instance_id: 实例ID
        """
        # 更新选中状态
        if self._selected_id and self._selected_id in self._instances:
            self._instances[self._selected_id].set_selected(False)

        self._selected_id = instance_id

        if instance_id in self._instances:
            self._instances[instance_id].set_selected(True)

        # 发送选中信号
        self.instance_selected.emit(instance_id)

    def _on_instance_edit(self, instance_id: str):
        """
        实例编辑事件

        Args:
            instance_id: 实例ID
        """
        # 发送编辑请求信号
        self.edit_requested.emit(instance_id)

    def _on_instance_delete(self, instance_id: str):
        """
        实例删除事件

        Args:
            instance_id: 实例ID
        """
        # 发送删除请求信号
        self.delete_requested.emit(instance_id)

    def _on_instance_initialize(self, instance_id: str):
        """
        实例初始化事件

        Args:
            instance_id: 实例ID
        """
        # 发送初始化请求信号
        self.initialize_requested.emit(instance_id)

    def _on_instance_auto_login(self, instance_id: str):
        """
        实例自动登录事件

        Args:
            instance_id: 实例ID
        """
        # 发送自动登录请求信号
        self.auto_login_requested.emit(instance_id)

    def _on_instance_qrcode(self, instance_id: str):
        """
        实例二维码事件

        Args:
            instance_id: 实例ID
        """
        # 发送二维码请求信号
        self.qrcode_requested.emit(instance_id)

    async def _update_instance_status(self):
        """更新实例状态 - 已禁用状态显示"""
        # 此方法保留但不执行任何操作，以保持代码兼容性
        pass

    def get_selected_instance_id(self) -> Optional[str]:
        """
        获取当前选中的实例ID

        Returns:
            Optional[str]: 实例ID，如果没有选中则返回None
        """
        return self._selected_id
