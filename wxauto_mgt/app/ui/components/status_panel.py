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
    QGroupBox, QTabWidget, QFrame, QGridLayout, QScrollArea
)

from app.core.status_monitor import StatusMonitor, InstanceStatus, MetricType
from app.core.api_client import instance_manager
from app.core.config_manager import config_manager
from app.utils.logging import get_logger
import logging
from datetime import datetime
from qasync import asyncSlot
import asyncio

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
        try:
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
        except Exception as e:
            logger.error(f"更新状态显示时出错: {e}")


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
        try:
            self.value_label.setText(value)
        except Exception as e:
            logger.error(f"更新指标值显示时出错: {e}")


class StatusUpdater(QObject):
    """状态更新器，处理异步更新操作"""
    update_complete = Signal(object)  # 更新完成信号
    update_failed = Signal(str)     # 更新失败信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._monitor = StatusMonitor()
    
    async def update_status(self, instance_id: str):
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
                "instance_id": instance_id,
                "status": status_data,
                "metrics": metrics or {}
            }
            
            # 发送更新完成信号
            self.update_complete.emit(update_data)
            logger.debug(f"发送状态更新数据: {update_data}")
            
        except Exception as e:
            logger.error(f"更新状态时出错: {e}")
            self.update_failed.emit(str(e))


class StatusMonitorPanel(QWidget):
    """状态监控面板"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 创建状态更新器
        self._status_updater = StatusUpdater(self)
        self._status_updater.update_complete.connect(self._on_update_complete)
        self._status_updater.update_failed.connect(self._on_update_failed)
        
        # 实例状态小部件字典
        self._instance_widgets = {}
        
        # 创建定时器
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._trigger_update)
        
        # 初始化UI
        self._init_ui()
        
        # 延迟加载初始数据
        QTimer.singleShot(100, self._refresh_instances)
        
        logger.debug("状态监控面板已初始化")
    
    def _init_ui(self):
        """初始化UI组件"""
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # 工具栏
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setContentsMargins(0, 0, 0, 10)
        
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
        
        # 创建滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        main_layout.addWidget(scroll)
        
        # 创建实例容器
        self.instances_container = QWidget()
        self.instances_layout = QVBoxLayout(self.instances_container)
        self.instances_layout.setSpacing(10)
        self.instances_layout.setContentsMargins(0, 0, 0, 0)
        self.instances_layout.setAlignment(Qt.AlignTop)
        
        # 将实例容器添加到滚动区域
        scroll.setWidget(self.instances_container)
        
        # 启动定时器（如果自动刷新已启用）
        if self.auto_refresh_check.isChecked():
            interval_seconds = self._get_interval_seconds(self.refresh_interval_combo.currentText())
            self._refresh_timer.start(interval_seconds * 1000)
            logger.debug(f"启动自动刷新定时器，间隔: {interval_seconds}秒")
    
    def _refresh_instances(self):
        """刷新实例列表"""
        try:
            # 清空现有实例小部件
            for widget in self._instance_widgets.values():
                widget.deleteLater()
            self._instance_widgets.clear()
            
            # 清空布局
            while self.instances_layout.count():
                item = self.instances_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            
            # 获取实例列表
            instances = config_manager.get_enabled_instances()
            logger.debug(f"获取到的实例列表: {instances}")
            
            if not instances:
                # 如果没有实例，显示提示信息
                label = QLabel("没有可用的实例")
                label.setAlignment(Qt.AlignCenter)
                label.setStyleSheet("color: #666666; font-size: 14px; padding: 20px;")
                self.instances_layout.addWidget(label)
                return
            
            # 为每个实例创建状态面板
            for instance in instances:
                instance_id = instance.get("instance_id")
                name = instance.get("name", instance_id)
                
                if not instance_id:
                    continue
                
                # 创建实例状态面板
                instance_panel = self._create_instance_panel(name)
                self._instance_widgets[instance_id] = instance_panel
                self.instances_layout.addWidget(instance_panel)
                logger.debug(f"创建实例面板: {instance_id}, {name}")
            
            # 立即触发一次更新
            QTimer.singleShot(100, self._trigger_update)
            
        except Exception as e:
            logger.error(f"刷新实例列表失败: {e}")
            # 显示错误信息
            label = QLabel(f"加载实例列表失败: {str(e)}")
            label.setStyleSheet("color: red; padding: 20px;")
            self.instances_layout.addWidget(label)
        
        finally:
            # 确保布局更新
            self.instances_container.update()

    def _trigger_update(self):
        """触发状态更新"""
        try:
            logger.debug(f"开始更新所有实例状态，实例列表: {list(self._instance_widgets.keys())}")
            for instance_id in list(self._instance_widgets.keys()):
                logger.debug(f"触发实例 {instance_id} 的状态更新")
                # 使用QTimer延迟执行异步更新，避免阻塞UI
                QTimer.singleShot(0, lambda iid=instance_id: self._update_instance_status(iid))
        except Exception as e:
            logger.error(f"触发状态更新时出错: {e}")

    def _update_instance_status(self, instance_id: str):
        """更新单个实例的状态"""
        try:
            # 创建异步任务
            asyncio.create_task(self._status_updater.update_status(instance_id))
        except Exception as e:
            logger.error(f"更新实例 {instance_id} 状态时出错: {e}")

    @Slot(object)
    def _on_update_complete(self, update_data: dict):
        """处理更新完成"""
        try:
            instance_id = update_data.get("instance_id")
            logger.debug(f"收到实例 {instance_id} 的状态更新数据")
            
            if not instance_id or instance_id not in self._instance_widgets:
                logger.warning(f"找不到实例面板: {instance_id}")
                return
            
            panel = self._instance_widgets[instance_id]
            status_data = update_data.get("status", {})
            metrics = update_data.get("metrics", {})
            
            # 更新状态显示
            status = status_data.get("status", "unknown")
            raw_status = status_data.get("raw_status", "unknown")
            if hasattr(panel, 'status_widget'):
                panel.status_widget.update_status(str(status), raw_status)
                logger.debug(f"更新状态显示: status={status}, raw_status={raw_status}")
            
            # 更新指标显示
            if metrics and hasattr(panel, 'msg_widget'):
                try:
                    # 更新消息数量
                    msg_count = metrics.get(MetricType.MESSAGE_COUNT.value, 0)
                    panel.msg_widget.update_value(str(msg_count))
                    
                    # 更新运行时间
                    uptime = metrics.get(MetricType.UPTIME.value, 0)
                    hours = int(uptime / 3600)
                    minutes = int((uptime % 3600) / 60)
                    seconds = int(uptime % 60)
                    uptime_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                    panel.uptime_widget.update_value(uptime_str)
                    
                    # 更新CPU使用率
                    cpu_usage = metrics.get(MetricType.CPU_USAGE.value, 0)
                    panel.cpu_widget.update_value(f"{cpu_usage:.1f}%")
                    
                    # 更新内存使用情况（转换为GB）
                    memory_used = metrics.get("memory_usage", 0) / 1024  # MB to GB
                    memory_total = metrics.get("memory_total", 0) / 1024  # MB to GB
                    memory_percent = metrics.get("memory_percent", 0)  # %
                    
                    if memory_total > 0:
                        memory_str = f"{memory_used:.1f}/{memory_total:.1f}GB ({memory_percent:.1f}%)"
                    else:
                        memory_str = f"{memory_used:.1f}GB"
                    
                    panel.memory_widget.update_value(memory_str)
                    logger.debug(f"更新指标显示完成: {metrics}")
                    
                except Exception as e:
                    logger.error(f"更新指标显示时出错: {e}")
            
        except Exception as e:
            logger.error(f"处理更新数据时出错: {e}")

    @Slot(str)
    def _on_update_failed(self, error_msg: str):
        """处理更新失败"""
        logger.error(f"状态更新失败: {error_msg}")

    def _toggle_auto_refresh(self, state):
        """切换自动刷新状态"""
        try:
            if state == Qt.Checked:
                interval_text = self.refresh_interval_combo.currentText()
                interval_seconds = self._get_interval_seconds(interval_text)
                logger.debug(f"启动自动刷新，间隔: {interval_seconds}秒")
                self._refresh_timer.start(interval_seconds * 1000)
                # 立即触发一次更新
                QTimer.singleShot(0, self._trigger_update)
            else:
                logger.debug("停止自动刷新")
                self._refresh_timer.stop()
        except Exception as e:
            logger.error(f"切换自动刷新状态时出错: {e}")

    def _on_refresh_interval_changed(self, interval_text):
        """处理刷新间隔变更"""
        try:
            if self.auto_refresh_check.isChecked():
                interval_seconds = self._get_interval_seconds(interval_text)
                logger.debug(f"更新刷新间隔: {interval_seconds}秒")
                self._refresh_timer.start(interval_seconds * 1000)
                # 立即触发一次更新
                QTimer.singleShot(0, self._trigger_update)
        except Exception as e:
            logger.error(f"更新刷新间隔时出错: {e}")

    def _get_interval_seconds(self, interval_text: str) -> int:
        """将间隔文本转换为秒数"""
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

    def showEvent(self, event):
        """处理显示事件"""
        super().showEvent(event)
        # 显示时启动定时器（如果自动刷新已启用）
        if self.auto_refresh_check.isChecked():
            interval_seconds = self._get_interval_seconds(self.refresh_interval_combo.currentText())
            self._refresh_timer.start(interval_seconds * 1000)
            # 立即触发一次更新
            QTimer.singleShot(0, self._trigger_update)

    def hideEvent(self, event):
        """处理隐藏事件"""
        if self._refresh_timer:
            self._refresh_timer.stop()
        super().hideEvent(event)

    def closeEvent(self, event):
        """处理关闭事件"""
        if self._refresh_timer:
            self._refresh_timer.stop()
        if hasattr(self, '_status_updater'):
            self._status_updater.deleteLater()
        super().closeEvent(event)

    def _create_instance_panel(self, instance_name: str) -> QWidget:
        """创建单个实例的状态面板"""
        # 创建面板容器
        panel = QWidget()
        panel.setFixedHeight(80)  # 固定高度
        panel.setStyleSheet("""
            QWidget {
                background-color: #f5f5f5;
                border-radius: 4px;
                border: 1px solid #e0e0e0;
            }
        """)
        
        # 面板布局
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(20)
        
        # 实例名称
        name_label = QLabel(f"{instance_name}:")
        name_label.setStyleSheet("font-size: 14px; font-weight: bold; background: none; border: none;")
        name_label.setFixedWidth(100)
        layout.addWidget(name_label)
        
        # 状态显示
        status_widget = StatusWidget()
        layout.addWidget(status_widget)
        
        # 消息数
        msg_widget = MetricWidget("消息数")
        layout.addWidget(msg_widget)
        
        # 运行时间
        uptime_widget = MetricWidget("运行时间")
        layout.addWidget(uptime_widget)
        
        # CPU使用率
        cpu_widget = MetricWidget("CPU")
        layout.addWidget(cpu_widget)
        
        # 内存使用
        memory_widget = MetricWidget("内存")
        layout.addWidget(memory_widget)
        
        # 保存指标小部件的引用
        panel.status_widget = status_widget
        panel.msg_widget = msg_widget
        panel.uptime_widget = uptime_widget
        panel.cpu_widget = cpu_widget
        panel.memory_widget = memory_widget
        
        return panel 