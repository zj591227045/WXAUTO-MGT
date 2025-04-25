"""
状态监控面板模块

实现微信实例的状态监控界面，包括实例状态展示、性能监控和警报设置。
"""

from typing import Dict, List, Optional

from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtGui import QIcon, QAction, QColor, QPalette
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, 
    QTableWidgetItem, QLabel, QHeaderView, QMessageBox, QMenu,
    QToolBar, QLineEdit, QComboBox, QSplitter, QTextEdit, QCheckBox,
    QGroupBox, QTabWidget, QFrame
)

from app.core.status_monitor import StatusMonitor, InstanceStatus, MetricType
from app.core.api_client import instance_manager
from app.core.config_manager import config_manager
from app.utils.logging import get_logger

logger = get_logger()


class StatusWidget(QFrame):
    """状态显示小部件"""
    
    def __init__(self, title: str, value: str, status_color: QColor = QColor(0, 170, 0), parent=None):
        """
        初始化状态小部件
        
        Args:
            title: 状态标题
            value: 状态值
            status_color: 状态颜色
            parent: 父窗口
        """
        super().__init__(parent)
        
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Raised)
        
        # 设置背景色
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor(245, 245, 245))
        self.setPalette(palette)
        self.setAutoFillBackground(True)
        
        # 布局
        layout = QVBoxLayout(self)
        
        # 标题标签
        self.title_label = QLabel(title)
        self.title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_label)
        
        # 状态值标签
        self.value_label = QLabel(value)
        self.value_label.setAlignment(Qt.AlignCenter)
        font = self.value_label.font()
        font.setPointSize(font.pointSize() + 4)
        font.setBold(True)
        self.value_label.setFont(font)
        
        # 设置状态颜色
        palette = self.value_label.palette()
        palette.setColor(QPalette.WindowText, status_color)
        self.value_label.setPalette(palette)
        
        layout.addWidget(self.value_label)
    
    def update_value(self, value: str, status_color: QColor = None):
        """
        更新状态值
        
        Args:
            value: 新的状态值
            status_color: 新的状态颜色（可选）
        """
        self.value_label.setText(value)
        
        if status_color:
            palette = self.value_label.palette()
            palette.setColor(QPalette.WindowText, status_color)
            self.value_label.setPalette(palette)


class StatusMonitorPanel(QWidget):
    """
    状态监控面板，用于监控实例状态和性能
    """
    
    def __init__(self, parent=None):
        """初始化状态监控面板"""
        super().__init__(parent)
        
        self._status_colors = {
            InstanceStatus.ONLINE.value: QColor(0, 170, 0),  # 绿色
            InstanceStatus.OFFLINE.value: QColor(128, 128, 128),  # 灰色
            InstanceStatus.ERROR.value: QColor(255, 0, 0),  # 红色
            InstanceStatus.UNKNOWN.value: QColor(0, 0, 255),  # 蓝色
        }
        
        self._selected_instance_id = None
        
        self._init_ui()
        
        # 定时刷新状态
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._update_status)
        self._refresh_timer.start(5000)  # 每5秒刷新一次
        
        # 加载初始数据
        self._refresh_instances()
        
        logger.debug("状态监控面板已初始化")
    
    def _init_ui(self):
        """初始化UI组件"""
        # 主布局
        main_layout = QVBoxLayout(self)
        
        # 工具栏
        toolbar_layout = QHBoxLayout()
        
        # 选择实例下拉框
        self.instance_combo = QComboBox()
        self.instance_combo.addItem("选择实例...", "")
        self.instance_combo.currentIndexChanged.connect(self._on_instance_changed)
        toolbar_layout.addWidget(QLabel("实例:"))
        toolbar_layout.addWidget(self.instance_combo)
        
        # 刷新按钮
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self._update_status)
        toolbar_layout.addWidget(self.refresh_btn)
        
        # 自动刷新复选框
        self.auto_refresh_check = QCheckBox("自动刷新")
        self.auto_refresh_check.setChecked(True)
        self.auto_refresh_check.stateChanged.connect(self._toggle_auto_refresh)
        toolbar_layout.addWidget(self.auto_refresh_check)
        
        toolbar_layout.addStretch()
        
        main_layout.addLayout(toolbar_layout)
        
        # 状态卡片
        status_layout = QHBoxLayout()
        
        # 状态小部件
        self.status_widget = StatusWidget("状态", "未知", QColor(0, 0, 255))
        status_layout.addWidget(self.status_widget)
        
        # 消息统计小部件
        self.message_widget = StatusWidget("消息数", "0", QColor(0, 0, 255))
        status_layout.addWidget(self.message_widget)
        
        # 响应时间小部件
        self.response_widget = StatusWidget("响应时间", "0 ms", QColor(0, 0, 255))
        status_layout.addWidget(self.response_widget)
        
        # CPU使用率小部件
        self.cpu_widget = StatusWidget("CPU", "0%", QColor(0, 0, 255))
        status_layout.addWidget(self.cpu_widget)
        
        # 内存使用率小部件
        self.memory_widget = StatusWidget("内存", "0 MB", QColor(0, 0, 255))
        status_layout.addWidget(self.memory_widget)
        
        main_layout.addLayout(status_layout)
        
        # 选项卡控件
        self.tab_widget = QTabWidget()
        
        # 状态历史选项卡
        self.status_history_tab = QWidget()
        status_history_layout = QVBoxLayout(self.status_history_tab)
        
        # 状态历史表格
        self.status_history_table = QTableWidget(0, 4)  # 0行，4列
        self.status_history_table.setHorizontalHeaderLabels(["时间", "状态", "详情", "备注"])
        self.status_history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.status_history_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.status_history_table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        status_history_layout.addWidget(self.status_history_table)
        
        self.tab_widget.addTab(self.status_history_tab, "状态历史")
        
        # 性能监控选项卡
        self.performance_tab = QWidget()
        performance_layout = QVBoxLayout(self.performance_tab)
        
        # 性能指标表格
        self.performance_table = QTableWidget(0, 4)  # 0行，4列
        self.performance_table.setHorizontalHeaderLabels(["时间", "指标", "值", "备注"])
        self.performance_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.performance_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.performance_table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        performance_layout.addWidget(self.performance_table)
        
        self.tab_widget.addTab(self.performance_tab, "性能监控")
        
        # 警报设置选项卡
        self.alerts_tab = QWidget()
        alerts_layout = QVBoxLayout(self.alerts_tab)
        
        # 警报表格
        self.alerts_table = QTableWidget(0, 4)  # 0行，4列
        self.alerts_table.setHorizontalHeaderLabels(["指标", "阈值", "状态", "操作"])
        self.alerts_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.alerts_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.alerts_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.alerts_table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        alerts_layout.addWidget(self.alerts_table)
        
        # 警报操作按钮
        alerts_btn_layout = QHBoxLayout()
        
        self.add_alert_btn = QPushButton("添加警报")
        self.add_alert_btn.clicked.connect(self._add_alert)
        alerts_btn_layout.addWidget(self.add_alert_btn)
        
        self.edit_alert_btn = QPushButton("编辑警报")
        self.edit_alert_btn.clicked.connect(self._edit_alert)
        alerts_btn_layout.addWidget(self.edit_alert_btn)
        
        self.delete_alert_btn = QPushButton("删除警报")
        self.delete_alert_btn.clicked.connect(self._delete_alert)
        alerts_btn_layout.addWidget(self.delete_alert_btn)
        
        alerts_btn_layout.addStretch()
        
        alerts_layout.addLayout(alerts_btn_layout)
        
        self.tab_widget.addTab(self.alerts_tab, "警报设置")
        
        # 详细信息选项卡
        self.details_tab = QWidget()
        details_layout = QVBoxLayout(self.details_tab)
        
        # 详细信息文本框
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        details_layout.addWidget(self.details_text)
        
        self.tab_widget.addTab(self.details_tab, "详细信息")
        
        main_layout.addWidget(self.tab_widget)
        
        # 状态栏
        status_layout = QHBoxLayout()
        self.status_label = QLabel("就绪")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        
        main_layout.addLayout(status_layout)
    
    def _refresh_instances(self):
        """刷新实例列表"""
        # 保存当前选择
        current_instance_id = self.instance_combo.currentData()
        
        # 清空下拉框
        self.instance_combo.clear()
        self.instance_combo.addItem("选择实例...", "")
        
        # 获取实例列表
        instances = config_manager.get_enabled_instances()
        
        # 添加实例到下拉框
        for instance in instances:
            instance_id = instance.get("instance_id", "")
            name = instance.get("name", instance_id)
            self.instance_combo.addItem(name, instance_id)
        
        # 恢复之前的选择
        if current_instance_id:
            index = self.instance_combo.findData(current_instance_id)
            if index >= 0:
                self.instance_combo.setCurrentIndex(index)
    
    def _on_instance_changed(self, index):
        """
        实例选择变更事件
        
        Args:
            index: 当前选择的索引
        """
        instance_id = self.instance_combo.currentData()
        self._selected_instance_id = instance_id
        
        if instance_id:
            # 更新状态显示
            self._update_status()
        else:
            # 清空状态显示
            self._clear_status_display()
    
    def _update_status(self):
        """更新状态显示"""
        if not self._selected_instance_id:
            return
        
        if not self.auto_refresh_check.isChecked():
            return
        
        # 获取实例状态
        from app.core.status_monitor import status_monitor
        status_data = status_monitor.get_instance_status(self._selected_instance_id)
        
        if not status_data:
            self._clear_status_display()
            return
        
        # 更新状态小部件
        status = status_data.get("status", InstanceStatus.UNKNOWN)
        status_text = {
            InstanceStatus.ONLINE: "在线",
            InstanceStatus.OFFLINE: "离线",
            InstanceStatus.ERROR: "错误",
            InstanceStatus.UNKNOWN: "未知"
        }.get(status, "未知")
        
        status_color = self._status_colors.get(status.value, QColor(0, 0, 255))
        self.status_widget.update_value(status_text, status_color)
        
        # 获取性能指标
        metrics = status_monitor.get_instance_metrics(self._selected_instance_id)
        
        # 更新消息统计
        message_count = metrics.get(MetricType.MESSAGE_COUNT.value, [0])[-1] if MetricType.MESSAGE_COUNT.value in metrics else 0
        self.message_widget.update_value(str(message_count))
        
        # 更新响应时间
        response_time = metrics.get(MetricType.RESPONSE_TIME.value, [0])[-1] if MetricType.RESPONSE_TIME.value in metrics else 0
        self.response_widget.update_value(f"{response_time} ms")
        
        # 更新CPU使用率
        cpu_usage = metrics.get(MetricType.CPU_USAGE.value, [0])[-1] if MetricType.CPU_USAGE.value in metrics else 0
        cpu_color = QColor(0, 170, 0) if cpu_usage < 70 else (QColor(255, 165, 0) if cpu_usage < 90 else QColor(255, 0, 0))
        self.cpu_widget.update_value(f"{cpu_usage}%", cpu_color)
        
        # 更新内存使用率
        memory_usage = metrics.get(MetricType.MEMORY_USAGE.value, [0])[-1] if MetricType.MEMORY_USAGE.value in metrics else 0
        memory_color = QColor(0, 170, 0) if memory_usage < 70 else (QColor(255, 165, 0) if memory_usage < 90 else QColor(255, 0, 0))
        self.memory_widget.update_value(f"{memory_usage} MB", memory_color)
        
        # 更新状态历史表格
        self._update_status_history()
        
        # 更新性能指标表格
        self._update_performance_history()
        
        # 更新详细信息
        self._update_details()
    
    def _clear_status_display(self):
        """清空状态显示"""
        self.status_widget.update_value("未知", QColor(0, 0, 255))
        self.message_widget.update_value("0")
        self.response_widget.update_value("0 ms")
        self.cpu_widget.update_value("0%")
        self.memory_widget.update_value("0 MB")
        
        # 清空表格
        self.status_history_table.setRowCount(0)
        self.performance_table.setRowCount(0)
        
        # 清空详细信息
        self.details_text.clear()
    
    def _update_status_history(self):
        """更新状态历史表格"""
        if not self._selected_instance_id:
            return
        
        # 获取状态历史
        from app.core.status_monitor import status_monitor
        # 此处假设status_monitor有get_status_history方法
        # TODO: 实现获取状态历史的逻辑
        history = []  # 应该从status_monitor获取状态历史
        
        # 清空表格
        self.status_history_table.setRowCount(0)
        
        # 添加历史记录到表格
        for i, record in enumerate(history):
            row = self.status_history_table.rowCount()
            self.status_history_table.insertRow(row)
            
            # TODO: 根据实际数据填充表格
    
    def _update_performance_history(self):
        """更新性能指标表格"""
        if not self._selected_instance_id:
            return
        
        # 获取性能历史
        from app.core.status_monitor import status_monitor
        # 此处假设status_monitor有get_performance_history方法
        # TODO: 实现获取性能历史的逻辑
        history = []  # 应该从status_monitor获取性能历史
        
        # 清空表格
        self.performance_table.setRowCount(0)
        
        # 添加历史记录到表格
        for i, record in enumerate(history):
            row = self.performance_table.rowCount()
            self.performance_table.insertRow(row)
            
            # TODO: 根据实际数据填充表格
    
    def _update_details(self):
        """更新详细信息"""
        if not self._selected_instance_id:
            return
        
        # 获取实例详细信息
        from app.core.status_monitor import status_monitor
        status_data = status_monitor.get_instance_status(self._selected_instance_id)
        
        if not status_data:
            self.details_text.clear()
            return
        
        # 构建详细信息文本
        details = status_data.get("details", {})
        details_text = f"实例ID: {self._selected_instance_id}\n\n"
        
        # 添加详细信息字段
        for key, value in details.items():
            details_text += f"{key}: {value}\n"
        
        # 显示详细信息
        self.details_text.setText(details_text)
    
    def _toggle_auto_refresh(self, state):
        """
        切换自动刷新状态
        
        Args:
            state: 复选框状态
        """
        if state == Qt.Checked:
            self._refresh_timer.start()
        else:
            self._refresh_timer.stop()
    
    def _add_alert(self):
        """添加警报规则"""
        # 导入对话框
        from app.ui.components.dialogs import AddAlertDialog
        
        dialog = AddAlertDialog(self)
        if dialog.exec():
            alert_data = dialog.get_alert_data()
            
            # TODO: 添加警报规则的逻辑
            
            # 刷新警报列表
            self._update_alerts()
    
    def _edit_alert(self):
        """编辑警报规则"""
        # 获取选中的警报
        selected_items = self.alerts_table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "未选择", "请先选择要编辑的警报")
            return
        
        row = selected_items[0].row()
        alert_id = self.alerts_table.item(row, 0).data(Qt.UserRole)
        
        # 导入对话框
        from app.ui.components.dialogs import EditAlertDialog
        
        # TODO: 获取警报数据
        alert_data = {}
        
        dialog = EditAlertDialog(self, alert_data)
        if dialog.exec():
            updated_data = dialog.get_alert_data()
            
            # TODO: 更新警报规则的逻辑
            
            # 刷新警报列表
            self._update_alerts()
    
    def _delete_alert(self):
        """删除警报规则"""
        # 获取选中的警报
        selected_items = self.alerts_table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "未选择", "请先选择要删除的警报")
            return
        
        row = selected_items[0].row()
        alert_id = self.alerts_table.item(row, 0).data(Qt.UserRole)
        
        # 确认对话框
        reply = QMessageBox.question(
            self,
            "确认删除",
            "确定要删除选中的警报规则吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # TODO: 删除警报规则的逻辑
            
            # 刷新警报列表
            self._update_alerts()
    
    def _update_alerts(self):
        """更新警报规则列表"""
        # 清空表格
        self.alerts_table.setRowCount(0)
        
        # TODO: 获取警报规则列表
        alerts = []
        
        # 添加警报规则到表格
        for alert in alerts:
            row = self.alerts_table.rowCount()
            self.alerts_table.insertRow(row)
            
            # TODO: 根据实际数据填充表格
    
    def select_instance(self, instance_id: str):
        """
        选择指定的实例
        
        Args:
            instance_id: 实例ID
        """
        index = self.instance_combo.findData(instance_id)
        if index >= 0:
            self.instance_combo.setCurrentIndex(index) 