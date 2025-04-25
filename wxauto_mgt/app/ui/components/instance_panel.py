"""
实例管理面板模块

实现微信实例的管理界面，包括实例列表、添加、编辑、删除等功能。
"""

from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import Qt, Signal, Slot, QTimer, QMetaObject, Q_ARG
from PySide6.QtGui import QIcon, QAction, QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, 
    QTableWidgetItem, QLabel, QHeaderView, QMessageBox, QMenu,
    QToolBar, QLineEdit, QComboBox
)

from app.core.api_client import instance_manager
from app.core.config_manager import config_manager
from app.core.status_monitor import StatusMonitor, InstanceStatus
from app.utils.logging import get_logger

logger = get_logger()


class InstanceManagerPanel(QWidget):
    """
    实例管理面板，用于管理微信实例
    """
    
    # 定义信号
    instance_added = Signal(str)      # 实例ID
    instance_removed = Signal(str)    # 实例ID
    instance_updated = Signal(str)    # 实例ID
    
    def __init__(self, parent=None):
        """初始化实例管理面板"""
        super().__init__(parent)
        
        self._status_map = {
            InstanceStatus.ONLINE.value: ("在线", QColor(0, 170, 0)),  # 绿色
            InstanceStatus.OFFLINE.value: ("离线", QColor(128, 128, 128)),  # 灰色
            InstanceStatus.ERROR.value: ("错误", QColor(255, 0, 0)),  # 红色
            InstanceStatus.UNKNOWN.value: ("未知", QColor(0, 0, 255)),  # 蓝色
        }
        
        self._init_ui()
        
        # 定时刷新状态
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._update_instance_status)
        self._refresh_timer.start(5000)  # 每5秒刷新一次
        
        # 初始加载实例
        self.refresh_instances()
        
        logger.debug("实例管理面板已初始化")
    
    def _init_ui(self):
        """初始化UI组件"""
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
        
        # 强制保存按钮
        self.save_btn = QPushButton("强制保存")
        self.save_btn.clicked.connect(self._save_instances_force)
        toolbar_layout.addWidget(self.save_btn)
        
        # 搜索框
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索实例...")
        self.search_edit.textChanged.connect(self._filter_instances)
        toolbar_layout.addWidget(self.search_edit)
        
        # 状态过滤下拉框
        self.status_filter = QComboBox()
        self.status_filter.addItem("全部状态", "")
        self.status_filter.addItem("在线", InstanceStatus.ONLINE.value)
        self.status_filter.addItem("离线", InstanceStatus.OFFLINE.value)
        self.status_filter.addItem("错误", InstanceStatus.ERROR.value)
        self.status_filter.currentIndexChanged.connect(self._filter_instances)
        toolbar_layout.addWidget(self.status_filter)
        
        toolbar_layout.addStretch()
        
        main_layout.addLayout(toolbar_layout)
        
        # 实例表格
        self.instance_table = QTableWidget(0, 6)  # 0行，6列
        self.instance_table.setHorizontalHeaderLabels(["实例ID", "名称", "状态", "URL", "上次连接", "操作"])
        self.instance_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.instance_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.instance_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.instance_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.instance_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.instance_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.instance_table.customContextMenuRequested.connect(self._show_context_menu)
        
        main_layout.addWidget(self.instance_table)
        
        # 状态提示
        self.status_label = QLabel("共 0 个实例")
        main_layout.addWidget(self.status_label)
    
    def refresh_instances(self):
        """刷新实例列表"""
        import asyncio
        
        # 清空表格
        self.instance_table.setRowCount(0)
        
        # 启动异步任务加载实例
        asyncio.create_task(self._refresh_instances_async())

    async def _refresh_instances_async(self):
        """异步加载实例"""
        # 获取实例列表
        instances = config_manager.get_enabled_instances()
        
        logger.debug(f"加载了 {len(instances)} 个实例")
        
        if not instances:
            logger.info("未找到已启用的实例配置，可能是首次启动或未添加实例")
            # 不再显示提示对话框，以免干扰用户体验
            return
        
        # 在主线程中添加实例到表格
        for i, instance in enumerate(instances):
            # 不使用invokeMethod传递复杂对象，改为直接调用添加函数
            # 通过QTimer.singleShot在主线程中安全调用
            from PySide6.QtCore import QTimer
            instance_id = instance.get("instance_id", "")
            logger.debug(f"添加实例到UI: {instance_id} - {instance.get('name', '')}")
            QTimer.singleShot(0, lambda id=instance_id: self._add_instance_by_id(id))
        
        # 更新状态标签
        QMetaObject.invokeMethod(self, "_update_status_label",
                               Qt.ConnectionType.QueuedConnection,
                               Q_ARG(int, len(instances)))
        
        # 更新实例状态
        await self._update_instance_status_async()

    def _add_instance_by_id(self, instance_id):
        """根据实例ID添加实例到表格"""
        instance_config = config_manager.get_instance_config(instance_id)
        if instance_config:
            self._add_instance_to_table(instance_config)

    @Slot(dict)
    def _add_instance_to_table_safe(self, instance):
        """在主线程中安全地添加实例到表格"""
        self._add_instance_to_table(instance)

    @Slot(int)
    def _update_status_label(self, count):
        """更新状态标签"""
        self.status_label.setText(f"共 {count} 个实例")

    def _update_instance_status(self):
        """更新实例状态信息"""
        import asyncio
        
        # 启动异步任务更新状态
        asyncio.create_task(self._update_instance_status_async())

    async def _update_instance_status_async(self):
        """异步更新实例状态信息"""
        from app.core.status_monitor import status_monitor
        from PySide6.QtCore import QTimer
        
        # 获取所有实例状态
        statuses = status_monitor.get_all_instance_statuses()
        
        # 遍历表格，更新状态
        for row in range(self.instance_table.rowCount()):
            instance_id = self.instance_table.item(row, 0).text()
            
            # 获取状态
            instance_status = statuses.get(instance_id, {})
            status = instance_status.get("status", InstanceStatus.UNKNOWN).value
            
            # 更新状态单元格
            status_text, status_color = self._status_map.get(
                status, ("未知", QColor(0, 0, 255))
            )
            
            # 在主线程中更新UI - 使用QTimer.singleShot代替invokeMethod传递复杂对象
            r, st = row, status_text
            QTimer.singleShot(0, lambda row=r, text=st: self._update_status_cell_safe(row, text, status))
            
            # 更新上次连接时间
            last_time = instance_status.get("last_check", 0)
            last_time_str = "从未连接" if last_time == 0 else str(last_time)
            
            r, lt = row, last_time_str
            QTimer.singleShot(0, lambda row=r, time=lt: self._update_last_conn_cell(row, time))

    def _update_status_cell_safe(self, row, status_text, status_value):
        """安全地更新状态单元格"""
        status_item = self.instance_table.item(row, 2)
        if status_item:
            status_item.setText(status_text)
            # 根据状态值获取颜色
            _, color = self._status_map.get(status_value, ("未知", QColor(0, 0, 255)))
            status_item.setForeground(color)

    @Slot(int, str)
    def _update_last_conn_cell(self, row, last_time_str):
        """更新上次连接时间单元格"""
        last_conn_item = self.instance_table.item(row, 4)
        if last_conn_item:
            last_conn_item.setText(last_time_str)
    
    def _filter_instances(self):
        """过滤实例列表"""
        # 获取搜索文本和状态过滤器
        search_text = self.search_edit.text().lower()
        status_filter = self.status_filter.currentData()
        
        # 遍历表格，隐藏不匹配的行
        for row in range(self.instance_table.rowCount()):
            show_row = True
            
            # 检查搜索文本
            if search_text:
                match_found = False
                for col in [0, 1, 3]:  # 实例ID、名称、URL
                    item = self.instance_table.item(row, col)
                    if item and search_text in item.text().lower():
                        match_found = True
                        break
                
                if not match_found:
                    show_row = False
            
            # 检查状态过滤器
            if show_row and status_filter:
                status_item = self.instance_table.item(row, 2)
                status_text = status_item.text() if status_item else ""
                
                # 将状态文本转换为状态值进行比较
                status_value = None
                for key, (text, _) in self._status_map.items():
                    if text == status_text:
                        status_value = key
                        break
                
                if status_value != status_filter:
                    show_row = False
            
            # 设置行可见性
            self.instance_table.setRowHidden(row, not show_row)
    
    def _show_context_menu(self, position):
        """
        显示上下文菜单
        
        Args:
            position: 点击位置
        """
        menu = QMenu(self)
        
        refresh_action = menu.addAction("刷新")
        refresh_action.triggered.connect(self.refresh_instances)
        
        menu.addSeparator()
        
        row = self.instance_table.rowAt(position.y())
        if row >= 0:
            instance_id = self.instance_table.item(row, 0).text()
            
            edit_action = menu.addAction("编辑")
            edit_action.triggered.connect(lambda: self._edit_instance(instance_id=instance_id))
            
            delete_action = menu.addAction("删除")
            delete_action.triggered.connect(lambda: self._delete_instance(instance_id=instance_id))
            
            menu.addSeparator()
            
            init_action = menu.addAction("初始化")
            init_action.triggered.connect(lambda: self._initialize_instance(instance_id=instance_id))
            
            status_action = menu.addAction("查看状态")
            status_action.triggered.connect(lambda: self._view_instance_status(instance_id))
        
        menu.exec(self.instance_table.mapToGlobal(position))
    
    def _add_instance(self):
        """添加实例"""
        import asyncio
        
        # 导入对话框
        from app.ui.components.dialogs import AddInstanceDialog
        
        dialog = AddInstanceDialog(self)
        if dialog.exec():
            instance_data = dialog.get_instance_data()
            
            # 添加实例
            asyncio.create_task(self._add_instance_async(instance_data))
    
    async def _add_instance_async(self, instance_data):
        """
        异步添加实例
        
        Args:
            instance_data: 实例数据
        """
        try:
            # 添加实例到ConfigManager
            result = await config_manager.add_instance(
                instance_data["instance_id"],
                instance_data["name"],
                instance_data["base_url"],
                instance_data["api_key"]
            )
            
            if result:
                # 添加实例到API客户端
                instance_manager.add_instance(
                    instance_data["instance_id"],
                    instance_data["base_url"],
                    instance_data["api_key"],
                    instance_data.get("timeout", 30)
                )
                
                # 发送实例添加信号
                self.instance_added.emit(instance_data["instance_id"])
                
                # 更新UI
                QMetaObject.invokeMethod(
                    self, "_add_instance_by_id",
                    Qt.ConnectionType.QueuedConnection,
                    Q_ARG(str, instance_data["instance_id"])
                )
                
                # 在UI上显示成功提示
                def show_success():
                    from PySide6.QtWidgets import QMessageBox
                    QMessageBox.information(
                        self, "添加成功", 
                        f"已成功添加实例: {instance_data['name']}"
                    )
                
                # 在主线程中执行
                from PySide6.QtCore import QTimer
                QTimer.singleShot(0, show_success)
                
                # 强制刷新实例列表
                QTimer.singleShot(500, self.refresh_instances)
                
                logger.info(f"已添加实例: {instance_data['instance_id']}")
            else:
                # 在UI上显示错误提示
                def show_error():
                    from PySide6.QtWidgets import QMessageBox
                    QMessageBox.warning(
                        self, "添加失败", 
                        f"添加实例失败: {instance_data['name']}"
                    )
                
                # 在主线程中执行
                from PySide6.QtCore import QTimer
                QTimer.singleShot(0, show_error)
                
                logger.error(f"添加实例失败: {instance_data['instance_id']}")
        except Exception as e:
            logger.exception(f"添加实例时发生错误: {e}")
            
            # 在UI上显示错误提示
            def show_exception():
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.critical(
                    self, "错误", 
                    f"添加实例时发生错误: {str(e)}"
                )
            
            # 在主线程中执行
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, show_exception)

    def _edit_instance(self, checked=False, instance_id=None):
        """
        编辑实例
        
        Args:
            checked: 按钮是否被选中（QT信号参数）
            instance_id: 实例ID，如果为None则从按钮属性获取
        """
        import asyncio
        
        # 如果instance_id为None，从发送者获取
        sender = self.sender()
        if instance_id is None and sender:
            instance_id = sender.property("instance_id")
        
        if not instance_id:
            logger.error("编辑实例时缺少实例ID")
            return
        
        # 获取实例配置
        instance_config = config_manager.get_instance_config(instance_id)
        if not instance_config:
            logger.error(f"找不到实例配置: {instance_id}")
            return
        
        # 导入对话框
        from app.ui.components.dialogs import EditInstanceDialog
        
        dialog = EditInstanceDialog(self, instance_config)
        if dialog.exec():
            updated_data = dialog.get_instance_data()
            
            # 更新实例配置
            asyncio.create_task(self._update_instance_async(instance_id, updated_data))

    async def _update_instance_async(self, instance_id, updated_data):
        """异步更新实例"""
        # 这里假设config_manager有update_instance方法
        result = await config_manager.update_instance(instance_id, updated_data)
        
        if result:
            logger.info(f"成功更新实例: {updated_data.get('name')} ({instance_id})")
            self.instance_updated.emit(instance_id)
            QMetaObject.invokeMethod(self, "refresh_instances", 
                                   Qt.ConnectionType.QueuedConnection)
        else:
            error_message = f"无法更新实例: {updated_data.get('name')}"
            QMetaObject.invokeMethod(self, "show_error_message", 
                                   Qt.ConnectionType.QueuedConnection,
                                   Q_ARG(str, error_message))
    
    def _delete_instance(self, checked=False, instance_id=None):
        """
        删除实例
        
        Args:
            checked: 按钮是否被选中（QT信号参数）
            instance_id: 实例ID，如果为None则从按钮属性获取
        """
        import asyncio
        
        # 如果instance_id为None，从发送者获取
        sender = self.sender()
        if instance_id is None and sender:
            instance_id = sender.property("instance_id")
        
        if not instance_id:
            logger.error("删除实例时缺少实例ID")
            return
        
        # 确认对话框
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除实例 {instance_id} 吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 删除实例
            asyncio.create_task(self._delete_instance_async(instance_id))

    async def _delete_instance_async(self, instance_id):
        """异步删除实例"""
        result = await config_manager.remove_instance(instance_id)
        
        if result:
            logger.info(f"成功删除实例: {instance_id}")
            self.instance_removed.emit(instance_id)
            QMetaObject.invokeMethod(self, "refresh_instances", 
                                   Qt.ConnectionType.QueuedConnection)
        else:
            error_message = f"无法删除实例: {instance_id}"
            QMetaObject.invokeMethod(self, "show_error_message", 
                                   Qt.ConnectionType.QueuedConnection,
                                   Q_ARG(str, error_message))
    
    @Slot(str)
    def show_error_message(self, message):
        """显示错误消息"""
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.warning(self, "错误", message)

    def _initialize_instance(self, checked=False, instance_id=None):
        """
        初始化实例
        
        Args:
            checked: 按钮是否被选中（QT信号参数）
            instance_id: 实例ID，如果为None则从按钮属性获取
        """
        import asyncio
        
        # 如果instance_id为None，从发送者获取
        sender = self.sender()
        if instance_id is None and sender:
            instance_id = sender.property("instance_id")
        
        if not instance_id:
            logger.error("初始化实例时缺少实例ID")
            return
        
        # 获取API客户端
        client = instance_manager.get_instance(instance_id)
        if not client:
            # 从配置获取实例信息
            instance_config = config_manager.get_instance_config(instance_id)
            if not instance_config:
                logger.error(f"找不到实例配置: {instance_id}")
                self.show_error_message(f"找不到实例配置: {instance_id}")
                return
            
            # 创建新的API客户端
            base_url = instance_config.get("base_url")
            api_key = instance_config.get("api_key")
            timeout = instance_config.get("timeout", 30)
            
            logger.debug(f"创建新API客户端: {instance_id}, API密钥: {api_key[:3]}***{api_key[-3:] if api_key and len(api_key)>6 else ''})")
            
            # 使用正确的API前缀
            client = instance_manager.add_instance(instance_id, base_url, api_key, timeout, api_prefix="api/wechat")
        
        # 执行初始化
        asyncio.create_task(self._initialize_instance_async(instance_id, client))

    async def _initialize_instance_async(self, instance_id, client):
        """异步初始化实例"""
        try:
            # 打印调试信息
            api_key = client.api_key
            logger.debug(f"开始初始化实例: {instance_id}")
            logger.debug(f"实例基础URL: {client.base_url}")
            logger.debug(f"实例API密钥: {api_key[:3]}***{api_key[-3:] if api_key and len(api_key)>6 else ''}")
            logger.debug(f"实例API前缀: {client.api_prefix}")
            
            result = await client.initialize()
            logger.info(f"实例初始化成功: {instance_id}")
            
            # 在主线程更新UI
            QMetaObject.invokeMethod(self, "refresh_instances", 
                                   Qt.ConnectionType.QueuedConnection)
            
            # 执行状态检查
            await self._check_instance_status(instance_id, client)
        except Exception as e:
            logger.error(f"实例初始化失败: {instance_id}, 错误: {e}")
            error_message = f"实例初始化失败: {str(e)}"
            
            # 使用主线程安全的方式显示错误
            def show_instance_error():
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "初始化失败", error_message)
            
            # 在主线程中执行
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, show_instance_error)

    async def _check_instance_status(self, instance_id, client):
        """检查实例状态"""
        try:
            result = await client.get_status()
            is_online = result.get("isOnline", False)
            logger.info(f"实例状态检查: {instance_id}, 在线: {is_online}")
        except Exception as e:
            logger.error(f"实例状态检查失败: {instance_id}, 错误: {e}")
    
    def _view_instance_status(self, instance_id):
        """
        查看实例状态
        
        Args:
            instance_id: 实例ID
        """
        # 切换到状态监控选项卡
        parent = self.parent()
        if hasattr(parent, "tab_widget"):
            for i in range(parent.tab_widget.count()):
                widget = parent.tab_widget.widget(i)
                if widget.__class__.__name__ == "StatusMonitorPanel":
                    parent.tab_widget.setCurrentIndex(i)
                    # 如果状态面板有选择实例的方法，调用它
                    if hasattr(widget, "select_instance"):
                        widget.select_instance(instance_id)
                    break 

    def _add_instance_to_table(self, instance: Dict):
        """
        将实例添加到表格
        
        Args:
            instance: 实例数据字典
        """
        row = self.instance_table.rowCount()
        self.instance_table.insertRow(row)
        
        # 实例ID
        id_item = QTableWidgetItem(instance.get("instance_id", ""))
        self.instance_table.setItem(row, 0, id_item)
        
        # 名称
        name_item = QTableWidgetItem(instance.get("name", ""))
        self.instance_table.setItem(row, 1, name_item)
        
        # 状态（初始为未知）
        status_item = QTableWidgetItem("未知")
        status_item.setForeground(QColor(0, 0, 255))  # 蓝色
        self.instance_table.setItem(row, 2, status_item)
        
        # URL
        url_item = QTableWidgetItem(instance.get("base_url", ""))
        self.instance_table.setItem(row, 3, url_item)
        
        # 上次连接
        last_time = instance.get("last_online_time", 0)
        last_time_str = "从未连接" if last_time == 0 else str(last_time)
        last_conn_item = QTableWidgetItem(last_time_str)
        self.instance_table.setItem(row, 4, last_conn_item)
        
        # 操作按钮
        # 在单元格内创建一个小部件来容纳按钮
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        button_layout.setContentsMargins(2, 2, 2, 2)
        button_layout.setSpacing(2)
        
        # 编辑按钮
        edit_btn = QPushButton("编辑")
        edit_btn.setProperty("instance_id", instance.get("instance_id", ""))
        edit_btn.clicked.connect(self._edit_instance)
        button_layout.addWidget(edit_btn)
        
        # 删除按钮
        delete_btn = QPushButton("删除")
        delete_btn.setProperty("instance_id", instance.get("instance_id", ""))
        delete_btn.clicked.connect(self._delete_instance)
        button_layout.addWidget(delete_btn)
        
        # 初始化按钮
        init_btn = QPushButton("初始化")
        init_btn.setProperty("instance_id", instance.get("instance_id", ""))
        init_btn.clicked.connect(self._initialize_instance)
        button_layout.addWidget(init_btn)
        
        button_layout.addStretch()
        
        self.instance_table.setCellWidget(row, 5, button_widget)

    def _save_instances_force(self):
        """强制保存所有实例配置到数据库"""
        import asyncio
        
        # 从ConfigManager中获取所有实例
        instances = config_manager.get('instances', [])
        
        logger.info(f"强制保存 {len(instances)} 个实例配置")
        
        # 启动异步任务保存配置
        async def save_task():
            try:
                # 强制保存配置
                result = await config_manager.save_config()
                
                # 在主线程中显示结果
                def show_result():
                    from PySide6.QtWidgets import QMessageBox
                    if result:
                        QMessageBox.information(self, "保存成功", f"已成功保存 {len(instances)} 个实例配置")
                    else:
                        QMessageBox.warning(self, "保存失败", "保存实例配置失败，请查看日志")
                
                # 在主线程中执行
                from PySide6.QtCore import QTimer
                QTimer.singleShot(0, show_result)
                
                # 刷新实例列表
                self.refresh_instances()
            except Exception as e:
                logger.error(f"强制保存实例配置失败: {e}")
                # 在主线程中显示错误
                def show_error():
                    from PySide6.QtWidgets import QMessageBox
                    QMessageBox.critical(self, "错误", f"保存实例配置时出错: {str(e)}")
                
                # 在主线程中执行
                from PySide6.QtCore import QTimer
                QTimer.singleShot(0, show_error)
        
        # 启动异步任务
        asyncio.create_task(save_task()) 