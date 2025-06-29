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

from wxauto_mgt.core.status_monitor import StatusMonitor, InstanceStatus, MetricType, status_monitor
from wxauto_mgt.core.api_client import instance_manager
from wxauto_mgt.core.config_manager import config_manager
from wxauto_mgt.utils.logging import get_logger
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
                self.update_failed.emit("实例ID为空")
                return

            logger.debug(f"开始更新实例状态: {instance_id}")

            # 获取API客户端
            from wxauto_mgt.core.api_client import instance_manager
            client = instance_manager.get_instance(instance_id)

            if not client:
                self.update_failed.emit(f"找不到实例的API客户端: {instance_id}")
                return

            # 获取健康状态信息（包含启动时间和状态）
            health_info = await client.get_health_info()
            logger.debug(f"获取到健康状态信息: {health_info}")

            # 获取微信状态
            status_data = await client.get_status() or {}

            # 合并状态信息
            if health_info.get("wechat_status") == "connected":
                status_data["isOnline"] = True
            else:
                status_data["isOnline"] = False

            # 获取系统资源指标
            metrics_data = await client.get_system_metrics() or {}

            # 获取未读消息数
            message_count = 0
            try:
                # 只获取未读消息数量，不处理消息内容
                # 这里只是为了显示状态，不需要处理消息
                messages = await client.get_unread_messages(
                    save_pic=False,
                    save_video=False,
                    save_file=False,
                    save_voice=False,
                    parse_url=False
                )
                if isinstance(messages, list):
                    message_count = len(messages)
                    logger.debug(f"状态面板检测到 {message_count} 条未读消息，但不处理")
            except Exception as e:
                logger.error(f"获取未读消息失败: {e}")

            # 准备合并后的数据
            metrics = {
                "cpu_usage": metrics_data.get("cpu_usage", 0),
                "memory_usage": metrics_data.get("memory_usage", 0),  # MB
                "memory_total": self._get_system_memory_total(),  # 动态获取系统内存总量
                "message_count": message_count,
                "uptime": health_info.get("uptime", 0)  # 从健康状态中获取运行时间
            }

            update_data = {
                "instance_id": instance_id,
                "status": status_data,
                "metrics": metrics,
                "health_info": health_info  # 添加健康状态信息
            }

            # 发送更新完成信号
            self.update_complete.emit(update_data)
            logger.debug(f"成功更新实例状态: {instance_id}")

        except Exception as e:
            import traceback
            logger.error(f"更新状态时出错: {e}")
            logger.error(f"异常堆栈: {traceback.format_exc()}")
            self.update_failed.emit(str(e))

    def _get_system_memory_total(self) -> int:
        """
        获取系统内存总量（MB）

        Returns:
            int: 系统内存总量，单位MB
        """
        try:
            import psutil
            memory = psutil.virtual_memory()
            memory_total_mb = memory.total / (1024 * 1024)
            return round(memory_total_mb)
        except Exception as e:
            logger.warning(f"获取系统内存总量失败: {e}")
            # 如果获取失败，返回一个合理的默认值
            return 8 * 1024  # 默认8GB


class StatusMonitorPanel(QWidget):
    """状态监控面板"""

    def __init__(self, parent=None):
        """初始化面板"""
        super().__init__(parent)
        self._init_ui()
        self._instance_panels = {}  # 存储实例面板的引用

        # 启动定时刷新
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh_status)
        self._timer.start(30000)  # 每30秒刷新一次

        # 创建状态更新器
        self._updater = StatusUpdater()
        self._updater.update_complete.connect(self._handle_status_update)
        self._updater.update_failed.connect(self._handle_update_error)

    def _init_ui(self):
        """初始化UI组件"""
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        # 工具栏
        toolbar_layout = QHBoxLayout()

        # 刷新按钮
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self._force_refresh)
        toolbar_layout.addWidget(self.refresh_btn)

        # 自动刷新复选框
        self.auto_refresh_check = QCheckBox("自动刷新")
        self.auto_refresh_check.setChecked(True)
        self.auto_refresh_check.toggled.connect(self._toggle_auto_refresh)
        toolbar_layout.addWidget(self.auto_refresh_check)

        # 刷新间隔
        toolbar_layout.addWidget(QLabel("间隔:"))
        self.refresh_interval = QComboBox()
        self.refresh_interval.addItems(["5秒", "10秒", "30秒", "60秒"])
        self.refresh_interval.setCurrentIndex(2)  # 设置默认值为30秒
        self.refresh_interval.currentIndexChanged.connect(self._change_refresh_interval)
        toolbar_layout.addWidget(self.refresh_interval)

        toolbar_layout.addStretch()

        main_layout.addLayout(toolbar_layout)

        # 创建滚动区域用于实例面板
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # 创建内容容器
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setSpacing(15)
        self.content_layout.addStretch()

        self.scroll_area.setWidget(self.content_widget)
        main_layout.addWidget(self.scroll_area)

        # 状态标签
        self.status_label = QLabel("共 0 个实例")
        main_layout.addWidget(self.status_label)

    @asyncSlot()
    async def refresh_status(self):
        """刷新状态信息"""
        try:
            logger.debug("开始刷新状态...")

            # 获取所有实例ID
            instances = await self._get_all_instances()
            if not instances:
                logger.warning("未找到实例")
                self.status_label.setText("共 0 个实例")
                return

            # 更新状态标签
            self.status_label.setText(f"共 {len(instances)} 个实例")

            # 创建或更新实例面板
            for instance_id, instance_name in instances:
                if instance_id not in self._instance_panels:
                    # 为新实例创建面板
                    panel = self._create_instance_panel(instance_name)
                    self._instance_panels[instance_id] = panel
                    # 添加到界面
                    self.content_layout.insertWidget(self.content_layout.count() - 1, panel)

                # 触发该实例的状态更新
                asyncio.create_task(self._updater.update_status(instance_id))

            logger.debug(f"刷新了 {len(instances)} 个实例的状态")

        except Exception as e:
            logger.error(f"刷新状态时出错: {e}")

    async def _get_all_instances(self):
        """获取所有实例信息"""
        try:
            # 从数据库获取实例列表
            from wxauto_mgt.data.db_manager import db_manager
            instances = await db_manager.fetchall("SELECT instance_id, name FROM instances WHERE enabled = 1")

            if not instances:
                # 如果没有启用的实例，尝试获取所有实例
                instances = await db_manager.fetchall("SELECT instance_id, name FROM instances")

            # 返回(instance_id, name)元组的列表
            return [(instance["instance_id"], instance["name"]) for instance in instances]
        except Exception as e:
            logger.error(f"获取实例列表失败: {e}")
            return []

    def _handle_status_update(self, update_data):
        """处理状态更新结果"""
        try:
            instance_id = update_data.get("instance_id")
            if not instance_id or instance_id not in self._instance_panels:
                return

            panel = self._instance_panels[instance_id]

            # 获取健康状态信息
            health_info = update_data.get("health_info", {})
            wechat_status = health_info.get("wechat_status", "disconnected")

            # 更新状态
            status_info = update_data.get("status", {})
            connected = status_info.get("isOnline", False) or wechat_status == "connected"

            # 设置状态显示文本和颜色
            if wechat_status == "connected":
                status_text = "状态正常"
                raw_status = "connected"
            else:
                status_text = "离线"
                raw_status = "not_initialized"

            # 如果服务状态不正常，优先显示错误状态
            if health_info.get("status") != "ok":
                status_text = "错误"
                raw_status = "not_initialized"

            panel.status_widget.update_status(status_text, raw_status)

            # 更新指标
            metrics = update_data.get("metrics", {})

            # 消息数
            message_count = metrics.get("message_count", 0)
            panel.msg_widget.update_value(str(message_count))

            # 运行时间 - 直接从健康状态信息获取
            uptime = health_info.get("uptime", 0)
            uptime_str = self._format_uptime(uptime)
            panel.uptime_widget.update_value(uptime_str)

            # CPU使用率
            cpu_usage = metrics.get("cpu_usage", 0.0)
            panel.cpu_widget.update_value(f"{cpu_usage:.1f}%")

            # 内存使用
            memory_used = metrics.get("memory_usage", 0)
            memory_total = metrics.get("memory_total", 0)
            if memory_total > 0:
                memory_percent = (memory_used / memory_total) * 100
                panel.memory_widget.update_value(f"{memory_used/1024:.1f}/{memory_total/1024:.1f}GB ({memory_percent:.1f}%)")
            else:
                panel.memory_widget.update_value(f"{memory_used/1024:.1f}GB")

            logger.debug(f"更新了实例 {instance_id} 的状态：状态={status_text}，运行时间={uptime_str}")

        except Exception as e:
            logger.error(f"处理状态更新结果时出错: {e}")

    def _handle_update_error(self, error_msg):
        """处理更新错误"""
        logger.error(f"状态更新失败: {error_msg}")

    def _format_uptime(self, seconds):
        """格式化运行时间"""
        if seconds <= 0:
            return "00:00:00"

        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60

        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def _toggle_auto_refresh(self, enabled):
        """切换自动刷新"""
        if enabled:
            interval = self._get_refresh_interval()
            self._timer.start(interval)
            logger.debug(f"自动刷新已启用，间隔: {interval/1000}秒")
        else:
            self._timer.stop()
            logger.debug("自动刷新已禁用")

    def _change_refresh_interval(self, index):
        """更改刷新间隔"""
        if self.auto_refresh_check.isChecked():
            interval = self._get_refresh_interval()
            self._timer.start(interval)
            logger.debug(f"刷新间隔已更改为: {interval/1000}秒")

    def _get_refresh_interval(self):
        """获取刷新间隔（毫秒）"""
        text = self.refresh_interval.currentText()
        seconds = int(text.replace("秒", ""))
        # 最小间隔设为10秒，避免过于频繁的API调用
        return max(seconds * 1000, 10000)

    def select_instance(self, instance_id):
        """选择指定实例"""
        # TODO: 实现选中指定实例的功能
        self.refresh_status()

    def showEvent(self, event):
        """处理显示事件"""
        super().showEvent(event)
        # 显示时刷新状态
        self.refresh_status()

        # 显示时启动定时器（如果自动刷新已启用）
        if self.auto_refresh_check.isChecked():
            self._timer.start(self._get_refresh_interval())

    def hideEvent(self, event):
        """处理隐藏事件"""
        if self._timer.isActive():
            self._timer.stop()
        super().hideEvent(event)

    def closeEvent(self, event):
        """处理关闭事件"""
        if self._timer.isActive():
            self._timer.stop()
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

    def _force_refresh(self):
        """强制刷新所有实例状态"""
        logger.debug("手动触发刷新")
        # 停止自动刷新定时器
        if self._timer.isActive():
            self._timer.stop()

        # 刷新状态
        self.refresh_status()

        # 如果自动刷新已启用，重新启动定时器
        if self.auto_refresh_check.isChecked():
            self._timer.start(self._get_refresh_interval())