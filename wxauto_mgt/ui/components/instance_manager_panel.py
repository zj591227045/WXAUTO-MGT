"""
实例管理面板

该模块提供了实例管理的UI界面，包括：
- 实例列表（卡片布局）
- 实例状态监控
- 服务平台配置
- 消息转发规则配置
"""

import logging
import asyncio
import json
from typing import Dict, List, Optional, Any
from datetime import datetime

from PySide6.QtCore import Qt, Signal, Slot, QSize, QTimer, QObject
from PySide6.QtGui import QColor, QIcon, QPalette
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSplitter, QMessageBox, QDialog, QFormLayout, QLineEdit,
    QComboBox, QSpinBox, QCheckBox, QScrollArea, QFrame, QGroupBox
)

from wxauto_mgt.core.api_client import instance_manager
from wxauto_mgt.core.status_monitor import StatusMonitor, InstanceStatus, MetricType, status_monitor
from wxauto_mgt.utils.logging import get_logger
from qasync import asyncSlot

# 导入自定义组件
from wxauto_mgt.ui.components.instance_card_list import InstanceCardList
from wxauto_mgt.ui.components.service_platform_panel import ServicePlatformPanel
from wxauto_mgt.ui.components.delivery_rule_panel import DeliveryRulePanel
from wxauto_mgt.ui.components.dialogs import AddInstanceDialog, EditInstanceDialog

logger = get_logger()

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

            # 获取数据库中该实例的消息总数
            message_count = 0
            listener_count = 0
            try:
                # 从数据库中查询该实例的消息总数和监听对象数量
                from wxauto_mgt.data.db_manager import db_manager

                # 查询消息总数
                query = "SELECT COUNT(*) as count FROM messages WHERE instance_id = ?"
                result = await db_manager.fetchone(query, (instance_id,))

                if result and "count" in result:
                    message_count = result["count"]
                    logger.debug(f"状态面板检测到实例 {instance_id} 在数据库中有 {message_count} 条消息记录")
                else:
                    logger.debug(f"状态面板未检测到实例 {instance_id} 的消息记录")

                # 查询监听对象数量
                listener_query = "SELECT COUNT(*) as count FROM listeners WHERE instance_id = ?"
                listener_result = await db_manager.fetchone(listener_query, (instance_id,))

                if listener_result and "count" in listener_result:
                    listener_count = listener_result["count"]
                    logger.debug(f"状态面板检测到实例 {instance_id} 有 {listener_count} 个监听对象")
                else:
                    logger.debug(f"状态面板未检测到实例 {instance_id} 的监听对象")
            except Exception as e:
                logger.error(f"获取数据库消息总数或监听对象数量失败: {e}")

            # 准备合并后的数据
            metrics = {
                "cpu_usage": metrics_data.get("cpu_usage", 0),
                "memory_usage": metrics_data.get("memory_usage", 0),  # MB
                "memory_total": 4 * 1024,  # 默认4GB，单位MB
                "message_count": message_count,
                "listener_count": listener_count,  # 添加监听对象数量
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


class InstanceManagerPanel(QWidget):
    """实例管理面板"""

    # 定义信号
    instance_added = Signal(str)      # 实例ID
    instance_removed = Signal(str)    # 实例ID
    instance_updated = Signal(str)    # 实例ID

    def __init__(self, parent=None):
        """初始化实例管理面板"""
        super().__init__(parent)

        self._init_ui()

    def _init_ui(self):
        """初始化UI"""
        # 主布局 - 水平分割
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # 左侧实例列表 (1/5宽度)
        self.instance_list = InstanceCardList(self)

        # 右侧内容区域 - 垂直布局
        right_content = QWidget()
        right_layout = QVBoxLayout(right_content)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        # 创建垂直分割器，上方放状态监控，下方放服务平台和规则配置
        self.vertical_splitter = QSplitter(Qt.Vertical)

        # 状态监控区域
        self.status_monitor_area = self._create_status_monitor_area()
        self.vertical_splitter.addWidget(self.status_monitor_area)

        # 中间和右侧分割窗口 - 水平分割
        self.content_splitter = QSplitter(Qt.Horizontal)

        # 中间部分 - 服务平台配置
        self.platform_panel = ServicePlatformPanel(self)

        # 右侧部分 - 消息转发规则配置
        self.rule_panel = DeliveryRulePanel(self)

        # 添加到水平分割器
        self.content_splitter.addWidget(self.platform_panel)
        self.content_splitter.addWidget(self.rule_panel)

        # 设置水平分割比例
        self.content_splitter.setSizes([300, 300])

        # 将水平分割器添加到垂直分割器
        self.vertical_splitter.addWidget(self.content_splitter)

        # 设置垂直分割比例 - 状态监控区域占1/3，服务平台和规则配置占2/3
        self.vertical_splitter.setSizes([200, 400])

        # 添加垂直分割器到右侧布局
        right_layout.addWidget(self.vertical_splitter)

        # 添加到主布局 - 进一步缩减卡片列表的宽度比例
        main_layout.addWidget(self.instance_list, 1)  # 1/6宽度
        main_layout.addWidget(right_content, 5)  # 5/6宽度

        # 连接信号
        self.instance_list.instance_selected.connect(self._on_instance_selected)
        self.instance_list.edit_requested.connect(self._edit_instance)
        self.instance_list.delete_requested.connect(self._delete_instance)
        self.instance_list.initialize_requested.connect(self._initialize_instance)

        # 连接添加实例按钮
        self.instance_list.add_btn.clicked.connect(self._add_instance)

        # 创建状态更新器
        self._updater = StatusUpdater()
        self._updater.update_complete.connect(self._handle_status_update)
        self._updater.update_failed.connect(self._handle_update_error)

        # 启动定时刷新
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh_status)
        self._timer.start(30000)  # 每30秒刷新一次

        # 初始加载实例列表
        self.instance_list.refresh_instances()

        # 初始刷新状态
        self.refresh_status()

    def _on_instance_selected(self, instance_id: str):
        """
        实例选中事件

        Args:
            instance_id: 实例ID
        """
        # 更新规则面板的过滤器
        self.rule_panel.set_instance_filter(instance_id)

        # 更新添加规则按钮的文本
        if instance_id:
            instance_name = self._get_instance_name(instance_id)
            self.rule_panel.set_add_button_text(f"为 {instance_name} 添加规则")
        else:
            self.rule_panel.set_add_button_text("添加规则")

        # 刷新状态监控，只显示选中的实例
        self.refresh_status()

    def _get_instance_name(self, instance_id: str) -> str:
        """
        获取实例名称

        Args:
            instance_id: 实例ID

        Returns:
            str: 实例名称，如果找不到则返回实例ID
        """
        try:
            # 从数据库获取实例名称
            from wxauto_mgt.data.db_manager import db_manager
            import asyncio

            # 创建异步任务获取实例名称
            async def _get_name():
                try:
                    instance = await db_manager.fetchone(
                        "SELECT name FROM instances WHERE instance_id = ?",
                        (instance_id,)
                    )
                    if instance and "name" in instance:
                        return instance["name"]
                    return instance_id
                except Exception as e:
                    logger.error(f"获取实例名称失败: {e}")
                    return instance_id

            # 使用同步方式执行异步任务
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果事件循环正在运行，使用Future
                future = asyncio.run_coroutine_threadsafe(_get_name(), loop)
                try:
                    return future.result(timeout=1.0)  # 设置超时时间
                except Exception:
                    return instance_id
            else:
                # 如果事件循环未运行，直接运行协程
                return loop.run_until_complete(_get_name())
        except Exception as e:
            logger.error(f"获取实例名称失败: {e}")
            return instance_id

    def _edit_instance(self, instance_id: str):
        """
        编辑实例

        Args:
            instance_id: 实例ID
        """
        # 使用asyncSlot装饰器处理异步调用
        self._get_instance_and_edit_async(instance_id)

    @asyncSlot()
    async def _get_instance_and_edit_async(self, instance_id: str):
        """
        异步获取实例配置并打开编辑对话框

        Args:
            instance_id: 实例ID
        """
        try:
            # 从数据库获取实例配置
            from wxauto_mgt.data.db_manager import db_manager

            instance_config = await db_manager.fetchone(
                "SELECT * FROM instances WHERE instance_id = ?",
                (instance_id,)
            )

            if not instance_config:
                logger.error(f"找不到实例配置: {instance_id}")
                QTimer.singleShot(0, lambda: QMessageBox.warning(
                    self, "错误", f"找不到实例配置: {instance_id}"
                ))
                return

            # 处理配置字段
            if "config" in instance_config and instance_config["config"]:
                try:
                    if isinstance(instance_config["config"], str):
                        instance_config["config"] = json.loads(instance_config["config"])
                except Exception as e:
                    logger.error(f"解析配置失败: {e}")
                    instance_config["config"] = {}

            # 在主线程中打开对话框
            def open_dialog():
                # 导入对话框
                dialog = EditInstanceDialog(self, instance_config)
                if dialog.exec():
                    updated_data = dialog.get_instance_data()
                    # 更新实例配置
                    self._update_instance_async(instance_id, updated_data)

            QTimer.singleShot(0, open_dialog)

        except Exception as e:
            logger.error(f"获取实例配置失败: {e}")
            QTimer.singleShot(0, lambda: QMessageBox.warning(
                self, "错误", f"获取实例配置失败: {str(e)}"
            ))

    async def _update_instance_async(self, instance_id, updated_data):
        """异步更新实例"""
        from wxauto_mgt.core.config_manager import config_manager

        try:
            # 更新实例配置
            result = await config_manager.update_instance(instance_id, updated_data)

            if result:
                logger.info(f"成功更新实例: {updated_data.get('name')} ({instance_id})")
                self.instance_updated.emit(instance_id)

                # 刷新实例列表
                QTimer.singleShot(0, lambda: self.instance_list.refresh_instances())

                # 刷新状态监控
                QTimer.singleShot(0, lambda: self.refresh_status())

                # 显示成功消息
                QTimer.singleShot(0, lambda: QMessageBox.information(
                    self, "成功", f"已成功更新实例: {updated_data.get('name')}"
                ))
            else:
                error_message = f"无法更新实例: {updated_data.get('name')}"
                QTimer.singleShot(0, lambda: QMessageBox.warning(self, "错误", error_message))
        except Exception as e:
            logger.error(f"更新实例时出错: {e}")
            QTimer.singleShot(0, lambda: QMessageBox.warning(self, "错误", f"更新实例时出错: {str(e)}"))

    def _delete_instance(self, instance_id: str):
        """
        删除实例

        Args:
            instance_id: 实例ID
        """
        # 确认对话框
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除实例 {instance_id} 吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # 使用asyncSlot装饰器处理异步调用
            self._delete_instance_async(instance_id)

    @asyncSlot()
    async def _delete_instance_async(self, instance_id):
        """异步删除实例"""
        from wxauto_mgt.core.config_manager import config_manager

        try:
            result = await config_manager.remove_instance(instance_id)

            if result:
                logger.info(f"成功删除实例: {instance_id}")
                self.instance_removed.emit(instance_id)

                # 刷新实例列表
                QTimer.singleShot(0, lambda: self.instance_list.refresh_instances())

                # 刷新状态监控
                QTimer.singleShot(0, lambda: self.refresh_status())

                # 显示成功消息
                QTimer.singleShot(0, lambda: QMessageBox.information(
                    self, "成功", f"已成功删除实例: {instance_id}"
                ))
            else:
                error_message = f"无法删除实例: {instance_id}"
                QTimer.singleShot(0, lambda: QMessageBox.warning(self, "错误", error_message))
        except Exception as e:
            logger.error(f"删除实例时出错: {e}")
            QTimer.singleShot(0, lambda: QMessageBox.warning(self, "错误", f"删除实例时出错: {str(e)}"))

    def _initialize_instance(self, instance_id: str):
        """
        初始化实例

        Args:
            instance_id: 实例ID
        """
        # 获取API客户端
        client = instance_manager.get_instance(instance_id)
        if not client:
            try:
                # 从配置获取实例信息
                from wxauto_mgt.core.config_manager import config_manager

                instance_config = config_manager.get_instance_config(instance_id)
                if not instance_config:
                    logger.error(f"找不到实例配置: {instance_id}")
                    QMessageBox.warning(self, "错误", f"找不到实例配置: {instance_id}")
                    return

                # 创建新的API客户端
                base_url = instance_config.get("base_url")
                api_key = instance_config.get("api_key")
                timeout = instance_config.get("timeout", 30)

                logger.debug(f"创建新API客户端: {instance_id}")

                # 创建新的API客户端
                client = instance_manager.add_instance(instance_id, base_url, api_key, timeout)
            except Exception as e:
                logger.error(f"创建API客户端失败: {e}")
                QMessageBox.warning(self, "错误", f"创建API客户端失败: {str(e)}")
                return

        # 使用asyncSlot装饰器处理异步调用
        self._initialize_instance_async(instance_id, client)

    @asyncSlot()
    async def _initialize_instance_async(self, instance_id, client):
        """异步初始化实例"""
        try:
            # 打印调试信息
            logger.debug(f"开始初始化实例: {instance_id}")
            logger.debug(f"实例基础URL: {client.base_url}")

            await client.initialize()
            logger.info(f"实例初始化成功: {instance_id}")

            # 在主线程更新UI
            QTimer.singleShot(0, lambda: self.instance_list.refresh_instances())

            # 显示成功消息
            QTimer.singleShot(0, lambda: QMessageBox.information(
                self, "成功", f"已成功初始化实例: {instance_id}"
            ))

            # 执行状态检查
            await self._check_instance_status(instance_id, client)
        except Exception as e:
            logger.error(f"实例初始化失败: {instance_id}, 错误: {e}")

            # 显示错误消息
            QTimer.singleShot(0, lambda: QMessageBox.warning(
                self, "初始化失败", f"实例初始化失败: {str(e)}"
            ))

    async def _check_instance_status(self, instance_id, client):
        """检查实例状态"""
        try:
            result = await client.get_status()
            is_online = result.get("isOnline", False)
            logger.info(f"实例状态检查: {instance_id}, 在线: {is_online}")
        except Exception as e:
            logger.error(f"实例状态检查失败: {instance_id}, 错误: {e}")

    def _add_instance(self):
        """添加新实例"""
        # 导入对话框
        dialog = AddInstanceDialog(self)

        if dialog.exec():
            instance_data = dialog.get_instance_data()
            logger.debug(f"获取到新实例数据: {instance_data}")

            # 使用asyncSlot装饰器处理异步调用
            self._add_instance_async(instance_data)

    def _create_status_monitor_area(self) -> QWidget:
        """创建状态监控区域"""
        # 创建容器
        container = QWidget()
        # 不再限制最大高度，使用自适应高度

        # 创建布局
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

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

        layout.addLayout(toolbar_layout)

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
        layout.addWidget(self.scroll_area)

        # 状态标签
        self.status_label = QLabel("共 0 个实例")
        layout.addWidget(self.status_label)

        # 存储实例面板的引用
        self._instance_panels = {}

        return container

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

        # 消息数 - 数据库中的消息总数
        msg_widget = MetricWidget("消息总数")
        layout.addWidget(msg_widget)

        # 监听对象数量
        listener_widget = MetricWidget("监听对象")
        layout.addWidget(listener_widget)

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
        panel.listener_widget = listener_widget
        panel.uptime_widget = uptime_widget
        panel.cpu_widget = cpu_widget
        panel.memory_widget = memory_widget

        return panel

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

    def _change_refresh_interval(self, _):
        """更改刷新间隔"""
        if self.auto_refresh_check.isChecked():
            interval = self._get_refresh_interval()
            self._timer.start(interval)
            logger.debug(f"刷新间隔已更改为: {interval/1000}秒")

    def _get_refresh_interval(self):
        """获取刷新间隔（毫秒）"""
        text = self.refresh_interval.currentText()
        seconds = int(text.replace("秒", ""))
        return seconds * 1000

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

    @asyncSlot()
    async def refresh_status(self):
        """刷新状态信息"""
        try:
            logger.debug("开始刷新状态...")

            # 获取所有实例ID
            all_instances = await self._get_all_instances()
            if not all_instances:
                logger.warning("未找到实例")
                self.status_label.setText("共 0 个实例")
                # 清空所有面板
                self._clear_instance_panels()
                return

            # 检查是否有选中的实例
            selected_instance_id = self.instance_list.get_selected_instance_id()

            # 确定要显示的实例列表
            if selected_instance_id:
                # 只显示选中的实例
                instances = [(id, name) for id, name in all_instances if id == selected_instance_id]
                if instances:
                    self.status_label.setText(f"显示实例: {instances[0][1]}")
                else:
                    # 如果选中的实例不在列表中，显示所有实例
                    instances = all_instances
                    self.status_label.setText(f"共 {len(instances)} 个实例")
            else:
                # 显示所有实例
                instances = all_instances
                self.status_label.setText(f"共 {len(instances)} 个实例")

            # 清除不在当前显示列表中的面板
            instance_ids = [id for id, _ in instances]
            panels_to_remove = [id for id in self._instance_panels.keys() if id not in instance_ids]
            for instance_id in panels_to_remove:
                if instance_id in self._instance_panels:
                    panel = self._instance_panels.pop(instance_id)
                    panel.deleteLater()
                    logger.debug(f"移除实例面板: {instance_id}")

            # 创建或更新实例面板
            for instance_id, instance_name in instances:
                if instance_id not in self._instance_panels:
                    # 为新实例创建面板
                    panel = self._create_instance_panel(instance_name)
                    self._instance_panels[instance_id] = panel
                    # 添加到界面
                    self.content_layout.insertWidget(self.content_layout.count() - 1, panel)
                    logger.debug(f"创建实例面板: {instance_id}")

                # 触发该实例的状态更新
                asyncio.create_task(self._updater.update_status(instance_id))

            logger.debug(f"刷新了 {len(instances)} 个实例的状态")

        except Exception as e:
            logger.error(f"刷新状态时出错: {e}")

    def _clear_instance_panels(self):
        """清除所有实例面板"""
        for panel in self._instance_panels.values():
            panel.deleteLater()
        self._instance_panels.clear()
        logger.debug("清除所有实例面板")

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
            # 检查连接状态 (这里只是为了记录，不使用变量)
            _ = status_info.get("isOnline", False) or wechat_status == "connected"

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

            # 消息数 - 显示数据库中的消息总数
            message_count = metrics.get("message_count", 0)
            panel.msg_widget.update_value(f"{message_count} 条")

            # 监听对象数量
            listener_count = metrics.get("listener_count", 0)
            panel.listener_widget.update_value(f"{listener_count} 个")

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

    async def _add_instance_async(self, instance_data):
        """
        异步添加实例

        Args:
            instance_data: 实例数据
        """
        try:
            # 从配置管理器获取实例
            from wxauto_mgt.core.config_manager import config_manager

            # 添加实例到配置管理器
            result = await config_manager.add_instance(
                instance_data["instance_id"],
                instance_data["name"],
                instance_data["base_url"],
                instance_data["api_key"],
                instance_data.get("enabled", True),
                **instance_data.get("config", {})
            )

            if result:
                logger.info(f"添加实例成功: {instance_data['name']} ({instance_data['instance_id']})")

                # 添加实例到API客户端
                instance_manager.add_instance(
                    instance_data["instance_id"],
                    instance_data["base_url"],
                    instance_data["api_key"],
                    instance_data.get("timeout", 30)
                )

                # 发送实例添加信号
                self.instance_added.emit(instance_data["instance_id"])

                # 刷新实例列表
                QTimer.singleShot(0, lambda: self.instance_list.refresh_instances())

                # 刷新状态监控
                QTimer.singleShot(0, lambda: self.refresh_status())

                # 显示成功消息
                QTimer.singleShot(0, lambda: QMessageBox.information(
                    self, "成功", f"已成功添加实例: {instance_data['name']}"
                ))
            else:
                error_message = f"无法添加实例: {instance_data['name']}"
                QTimer.singleShot(0, lambda: QMessageBox.warning(self, "错误", error_message))
        except Exception as e:
            logger.error(f"添加实例失败: {e}")
            QTimer.singleShot(0, lambda: QMessageBox.warning(self, "错误", f"添加实例失败: {str(e)}"))
