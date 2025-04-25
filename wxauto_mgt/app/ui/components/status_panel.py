"""
状态监控面板模块

实现微信实例的状态监控界面，包括实例状态展示、性能监控和警报设置。
"""

from typing import Dict, List, Optional

from PySide6.QtCore import Qt, Signal, Slot, QTimer, QObject
from PySide6.QtGui import QIcon, QAction, QColor, QPalette
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, 
    QTableWidgetItem, QLabel, QHeaderView, QMessageBox, QMenu,
    QToolBar, QLineEdit, QComboBox, QSplitter, QTextEdit, QCheckBox,
    QGroupBox, QTabWidget, QFrame, QGridLayout
)

from app.core.status_monitor import StatusMonitor, InstanceStatus, MetricType
from app.core.api_client import instance_manager
from app.core.config_manager import config_manager
from app.utils.logging import get_logger
import logging
from datetime import datetime
from qasync import asyncSlot

logger = logging.getLogger(__name__)


class StatusWidget(QWidget):
    """状态显示小部件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        
    def _init_ui(self):
        layout = QHBoxLayout()
        self.status_label = QLabel()
        self.status_label.setStyleSheet("padding: 2px 8px; border-radius: 4px;")
        layout.addWidget(self.status_label)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        
    def update_status(self, status: str, raw_status: str = None):
        """更新状态显示
        
        Args:
            status: 显示的状态文本
            raw_status: 原始状态值，用于确定显示颜色
        """
        # 设置状态文本
        self.status_label.setText(status)
        
        # 根据原始状态值设置颜色
        if raw_status == "not_initialized":
            color = "#ff4d4f"  # 红色
        elif raw_status == "connected":
            color = "#52c41a"  # 绿色
        else:
            color = "#666666"  # 默认灰色
            
        self.status_label.setStyleSheet(f"""
            QLabel {{
                color: white;
                background-color: {color};
                padding: 2px 8px;
                border-radius: 4px;
            }}
        """)


class MetricWidget(QWidget):
    """指标显示组件"""
    
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._init_ui(title)
        
    def _init_ui(self, title: str):
        layout = QVBoxLayout()
        layout.setSpacing(2)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # 标题标签
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("color: #666666; font-size: 12px;")
        layout.addWidget(self.title_label)
        
        # 值标签
        self.value_label = QLabel()
        self.value_label.setStyleSheet("color: #000000; font-size: 16px; font-weight: bold;")
        layout.addWidget(self.value_label)
        
        self.setLayout(layout)
        self.setStyleSheet("background-color: #f5f5f5; border-radius: 4px;")
        
    def update_value(self, value: str):
        """更新指标值显示"""
        self.value_label.setText(value)

    def _setup_metrics(self):
        """初始化性能指标组件"""
        metrics_group = QGroupBox("性能指标")
        metrics_layout = QGridLayout()
        metrics_group.setLayout(metrics_layout)
        
        # 创建各个指标组件
        self.msg_count_widget = MetricWidget("消息数")
        self.response_time_widget = MetricWidget("响应时间")
        self.cpu_usage_widget = MetricWidget("CPU使用率")
        self.memory_usage_widget = MetricWidget("内存使用率")
        
        # 添加到网格布局
        metrics_layout.addWidget(self.msg_count_widget, 0, 0)
        metrics_layout.addWidget(self.response_time_widget, 0, 1)
        metrics_layout.addWidget(self.cpu_usage_widget, 1, 0)
        metrics_layout.addWidget(self.memory_usage_widget, 1, 1)
        
        return metrics_group

    def update_status(self):
        """更新状态和性能指标"""
        try:
            # 获取最新状态
            status = self.status_monitor.get_instance_status(self.instance_id)
            if status:
                self._update_status_display(status)
            
            # 获取最新指标
            metrics = self.status_monitor.get_instance_metrics(self.instance_id)
            if metrics:
                self._update_metrics_display(metrics)
                
        except Exception as e:
            logger.error(f"更新状态面板失败: {e}")
            
    def _update_status_display(self, status: InstanceStatus):
        """更新状态显示"""
        color = self.STATUS_COLORS.get(status.value, QColor("gray"))
        palette = self.status_label.palette()
        palette.setColor(QPalette.ColorRole.WindowText, color)
        self.status_label.setPalette(palette)
        self.status_label.setText(f"状态: {status.value}")
        
    def _update_metrics_display(self, metrics: Dict[MetricType, float]):
        """更新性能指标显示"""
        if MetricType.MESSAGE_COUNT in metrics:
            self.msg_count_widget.update_value(f"{metrics[MetricType.MESSAGE_COUNT]:.0f}")
        if MetricType.RESPONSE_TIME in metrics:
            self.response_time_widget.update_value(f"{metrics[MetricType.RESPONSE_TIME]:.2f}ms")
        if MetricType.CPU_USAGE in metrics:
            self.cpu_usage_widget.update_value(f"{metrics[MetricType.CPU_USAGE]:.1f}%")
        if MetricType.MEMORY_USAGE in metrics:
            self.memory_usage_widget.update_value(f"{metrics[MetricType.MEMORY_USAGE]:.1f}MB")


class StatusUpdater(QObject):
    """状态更新器，处理异步更新操作"""
    update_complete = Signal(dict)  # 更新完成信号
    update_failed = Signal(str)     # 更新失败信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._monitor = StatusMonitor()
    
    @asyncSlot()
    async def update_status(self, instance_id):
        """异步更新状态"""
        try:
            if not instance_id:
                return
                
            # 获取实例状态
            status_data = await self._monitor.get_instance_status(instance_id)
            if not status_data:
                self.update_failed.emit(f"无法获取实例 {instance_id} 的状态")
                return
                
            # 获取性能指标
            metrics = await self._monitor.get_instance_metrics(instance_id)
            
            # 合并数据
            update_data = {
                "status": status_data,
                "metrics": metrics
            }
            
            # 发送更新完成信号
            self.update_complete.emit(update_data)
            
        except Exception as e:
            logger.error(f"更新状态时出错: {e}")
            self.update_failed.emit(str(e))


class StatusMonitorPanel(QWidget):
    """
    状态监控面板，用于监控实例状态和性能
    """
    
    def __init__(self, parent=None):
        """初始化状态监控面板"""
        super().__init__(parent)
        
        # 创建状态更新器
        self._status_updater = StatusUpdater(self)
        self._status_updater.update_complete.connect(self._handle_update_complete)
        self._status_updater.update_failed.connect(self._handle_update_failed)
        
        self._status_colors = {
            "connected": QColor(0, 170, 0),    # 绿色
            "offline": QColor(128, 128, 128),  # 灰色
            "error": QColor(255, 0, 0),        # 红色
            "unknown": QColor(255, 165, 0)     # 橙色
        }
        
        self._selected_instance_id = None
        
        self._init_ui()
        
        # 定时刷新状态
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._trigger_update)
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
        self.refresh_btn.clicked.connect(self._trigger_update)
        toolbar_layout.addWidget(self.refresh_btn)
        
        # 自动刷新复选框
        self.auto_refresh_check = QCheckBox("自动刷新")
        self.auto_refresh_check.setChecked(True)
        self.auto_refresh_check.stateChanged.connect(self._toggle_auto_refresh)
        toolbar_layout.addWidget(self.auto_refresh_check)
        
        # 刷新间隔设置
        toolbar_layout.addWidget(QLabel("间隔:"))
        self.refresh_interval_combo = QComboBox()
        self.refresh_interval_combo.addItems(["5秒", "10秒", "30秒", "1分钟", "5分钟"])
        self.refresh_interval_combo.setCurrentText("5秒")
        self.refresh_interval_combo.currentTextChanged.connect(self._on_refresh_interval_changed)
        toolbar_layout.addWidget(self.refresh_interval_combo)
        
        toolbar_layout.addStretch()
        
        main_layout.addLayout(toolbar_layout)
        
        # 状态卡片
        status_layout = QHBoxLayout()
        
        # 状态小部件
        self.status_widget = StatusWidget()
        status_layout.addWidget(self.status_widget)
        
        # 消息统计小部件
        self.message_widget = MetricWidget("消息数")
        status_layout.addWidget(self.message_widget)
        
        # 运行时间小部件
        self.response_widget = MetricWidget("运行时间")
        status_layout.addWidget(self.response_widget)
        
        # CPU使用率小部件
        self.cpu_widget = MetricWidget("CPU")
        status_layout.addWidget(self.cpu_widget)
        
        # 内存使用率小部件
        self.memory_widget = MetricWidget("内存")
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
            # 立即触发一次更新
            self._trigger_update()
        else:
            # 清空状态显示
            self._clear_status_display()
    
    def _trigger_update(self):
        """触发状态更新"""
        if self._selected_instance_id:
            self._status_updater.update_status(self._selected_instance_id)
            logger.debug(f"已触发实例 {self._selected_instance_id} 的状态更新")
    
    @Slot(dict)
    def _handle_update_complete(self, update_data):
        """处理更新完成"""
        try:
            status_data = update_data.get("status", {})
            metrics = update_data.get("metrics", {})
            
            # 更新状态显示
            status = status_data.get("status", "unknown")
            raw_status = status_data.get("raw_status", "unknown")
            self.status_widget.update_status(str(status), raw_status)
            
            # 更新指标显示
            if metrics:
                # 更新消息数量
                msg_count = metrics.get(MetricType.MESSAGE_COUNT.value, 0)
                self.message_widget.update_value(f"{msg_count:,}")
                
                # 更新运行时间
                uptime = metrics.get(MetricType.UPTIME.value, 0)
                hours = int(uptime / 3600)
                minutes = int((uptime % 3600) / 60)
                seconds = int(uptime % 60)
                uptime_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                self.response_widget.update_value(uptime_str)
                
                # 更新CPU使用率
                cpu_usage = metrics.get(MetricType.CPU_USAGE.value, 0)
                self.cpu_widget.update_value(f"{cpu_usage:.1f}%")
                
                # 更新内存使用情况（转换为GB）
                memory_used = metrics.get("memory_usage", 0) / 1024  # MB to GB
                memory_total = metrics.get("memory_total", 0) / 1024  # MB to GB
                memory_percent = metrics.get("memory_percent", 0)  # %
                
                if memory_total > 0:
                    memory_str = f"{memory_used:.1f}/{memory_total:.1f}GB ({memory_percent:.1f}%)"
                else:
                    memory_str = f"{memory_used:.1f}GB"
                    
                self.memory_widget.update_value(memory_str)
            
            logger.debug("状态更新完成")
            
        except Exception as e:
            logger.error(f"处理更新数据时出错: {e}")
            self.status_widget.update_status("更新失败", "error")

    @Slot(str)
    def _handle_update_failed(self, error_msg):
        """处理更新失败"""
        logger.error(f"状态更新失败: {error_msg}")
        self.status_widget.update_status("更新失败", "error")
    
    def _clear_status_display(self):
        """清空状态显示"""
        self.status_widget.update_status("未知", "unknown")
        self.message_widget.update_value("--")
        self.response_widget.update_value("--:--:--")
        self.cpu_widget.update_value("--")
        self.memory_widget.update_value("-- MB")
        
        # 清空表格
        self.status_history_table.setRowCount(0)
        self.performance_table.setRowCount(0)
        
        # 清空详细信息
        self.details_text.clear()
    
    async def _update_status_history(self):
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
    
    async def _update_performance_history(self):
        """更新性能指标表格"""
        if not self._selected_instance_id:
            return
        
        # 获取性能历史
        from app.core.status_monitor import status_monitor
        # 此处假设status_monitor有get_metrics_history方法
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
            # 获取当前选择的刷新间隔
            interval_text = self.refresh_interval_combo.currentText()
            interval_seconds = self._get_interval_seconds(interval_text)
            self._refresh_timer.start(interval_seconds * 1000)
        else:
            self._refresh_timer.stop()
            
    def _on_refresh_interval_changed(self, interval_text):
        """
        处理刷新间隔变更
        
        Args:
            interval_text: 间隔文本
        """
        if self.auto_refresh_check.isChecked():
            interval_seconds = self._get_interval_seconds(interval_text)
            self._refresh_timer.start(interval_seconds * 1000)
            
    def _get_interval_seconds(self, interval_text: str) -> int:
        """
        将间隔文本转换为秒数
        
        Args:
            interval_text: 间隔文本
            
        Returns:
            int: 间隔秒数
        """
        if interval_text == "5秒":
            return 5
        elif interval_text == "10秒":
            return 10
        elif interval_text == "30秒":
            return 30
        elif interval_text == "1分钟":
            return 60
        elif interval_text == "5分钟":
            return 300
        else:
            return 5  # 默认5秒
    
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

    def _update_charts(self, metrics):
        """更新性能图表"""
        try:
            # 更新消息统计
            if MetricType.MESSAGE_COUNT.value in metrics:
                message_count = metrics[MetricType.MESSAGE_COUNT.value][-1]
                self.message_widget.update_value(str(message_count))
            
            # 更新响应时间
            if MetricType.RESPONSE_TIME.value in metrics:
                response_time = metrics[MetricType.RESPONSE_TIME.value][-1]
                self.response_widget.update_value(f"{response_time:.2f} ms")
            
            # 更新CPU使用率
            if MetricType.CPU_USAGE.value in metrics:
                cpu_usage = metrics[MetricType.CPU_USAGE.value][-1]
                self.cpu_widget.update_value(f"{cpu_usage:.1f}%")
                
            # 更新内存使用率
            if MetricType.MEMORY_USAGE.value in metrics:
                memory_usage = metrics[MetricType.MEMORY_USAGE.value][-1]
                self.memory_widget.update_value(f"{memory_usage:.1f} MB")
                
        except Exception as e:
            logger.error(f"更新图表时出错: {str(e)}") 

    def closeEvent(self, event):
        """处理关闭事件"""
        # 停止定时器
        if self._refresh_timer:
            self._refresh_timer.stop()
        
        # 清理更新器
        if hasattr(self, '_status_updater'):
            self._status_updater.deleteLater()
        
        super().closeEvent(event)
        
    def hideEvent(self, event):
        """处理隐藏事件"""
        # 停止定时器
        if self._refresh_timer:
            self._refresh_timer.stop()
        super().hideEvent(event)
        
    def showEvent(self, event):
        """处理显示事件"""
        # 重新启动定时器
        if self._refresh_timer and self.auto_refresh_check.isChecked():
            self._refresh_timer.start()
        super().showEvent(event)

class StatusPanel(QWidget):
    """实例状态监控面板"""
    
    def __init__(self, instance_id: str, status_monitor: StatusMonitor, parent=None):
        super().__init__(parent)
        self.instance_id = instance_id
        self.status_monitor = status_monitor
        
        # 设置主布局
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # 添加状态显示
        status_group = QGroupBox("实例状态")
        status_layout = QVBoxLayout()
        status_group.setLayout(status_layout)
        
        self.status_label = QLabel("状态: 未知")
        status_layout.addWidget(self.status_label)
        layout.addWidget(status_group)
        
        # 添加性能指标组件
        layout.addWidget(self._setup_metrics())
        
        # 设置定时更新
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_status)
        self.update_timer.start(5000)  # 每5秒更新一次
        
        # 立即更新一次状态
        self.update_status()

    def _setup_metrics(self):
        """初始化性能指标组件"""
        metrics_group = QGroupBox("性能指标")
        metrics_layout = QGridLayout()
        metrics_group.setLayout(metrics_layout)
        
        # 创建各个指标组件
        self.msg_count_widget = MetricWidget("消息数")
        self.response_time_widget = MetricWidget("响应时间")
        self.cpu_usage_widget = MetricWidget("CPU使用率")
        self.memory_usage_widget = MetricWidget("内存使用率")
        
        # 添加到网格布局
        metrics_layout.addWidget(self.msg_count_widget, 0, 0)
        metrics_layout.addWidget(self.response_time_widget, 0, 1)
        metrics_layout.addWidget(self.cpu_usage_widget, 1, 0)
        metrics_layout.addWidget(self.memory_usage_widget, 1, 1)
        
        return metrics_group

    def update_status(self):
        """更新状态和性能指标"""
        try:
            # 获取最新状态
            status = self.status_monitor.get_instance_status(self.instance_id)
            if status:
                self._update_status_display(status)
            
            # 获取最新指标
            metrics = self.status_monitor.get_instance_metrics(self.instance_id)
            if metrics:
                self._update_metrics_display(metrics)
                
        except Exception as e:
            logger.error(f"更新状态面板失败: {e}")
            
    def _update_status_display(self, status: InstanceStatus):
        """更新状态显示"""
        color = self.STATUS_COLORS.get(status.value, QColor("gray"))
        palette = self.status_label.palette()
        palette.setColor(QPalette.ColorRole.WindowText, color)
        self.status_label.setPalette(palette)
        self.status_label.setText(f"状态: {status.value}")
        
    def _update_metrics_display(self, metrics: Dict[MetricType, float]):
        """更新性能指标显示"""
        if MetricType.MESSAGE_COUNT in metrics:
            self.msg_count_widget.update_value(f"{metrics[MetricType.MESSAGE_COUNT]:.0f}")
        if MetricType.RESPONSE_TIME in metrics:
            self.response_time_widget.update_value(f"{metrics[MetricType.RESPONSE_TIME]:.2f}ms")
        if MetricType.CPU_USAGE in metrics:
            self.cpu_usage_widget.update_value(f"{metrics[MetricType.CPU_USAGE]:.1f}%")
        if MetricType.MEMORY_USAGE in metrics:
            self.memory_usage_widget.update_value(f"{metrics[MetricType.MEMORY_USAGE]:.1f}MB")

    def _update_display(self, status, metrics=None):
        """更新显示内容"""
        try:
            if isinstance(status, InstanceStatus):
                status = status.value
            self.status_label.setText(f"状态: {status}")
            
            # 更新指标显示
            if metrics:
                # 更新消息数量
                msg_count = metrics.get(MetricType.MESSAGE_COUNT.value, 0)
                self.msg_count_widget.update_value(f"{msg_count:,}")
                
                # 更新运行时间
                uptime = metrics.get(MetricType.UPTIME.value, 0)
                hours = int(uptime / 3600)
                minutes = int((uptime % 3600) / 60)
                seconds = int(uptime % 60)
                uptime_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                self.response_time_widget.update_value(uptime_str)
                
                # 更新CPU使用率
                cpu_usage = metrics.get(MetricType.CPU_USAGE.value, 0)
                self.cpu_usage_widget.update_value(f"{cpu_usage:.1f}%")
                
                # 更新内存使用
                memory_usage = metrics.get(MetricType.MEMORY_USAGE.value, 0)
                memory_mb = memory_usage / (1024 * 1024)  # 转换为MB
                self.memory_usage_widget.update_value(f"{memory_mb:.1f} MB")
                
        except Exception as e:
            logger.error(f"处理更新数据时出错: {e}")
            self.status_label.setText("更新失败")

    def _clear_status_display(self):
        """清空状态显示"""
        self.status_label.setText("未知")
        self.msg_count_widget.update_value("--")
        self.response_time_widget.update_value("--:--:--")
        self.cpu_usage_widget.update_value("--")
        self.memory_usage_widget.update_value("-- MB")