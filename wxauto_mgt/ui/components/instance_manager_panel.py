"""
实例管理面板

该模块提供了实例管理的UI界面，包括：
- 实例列表（卡片布局）
- 服务平台配置
- 消息转发规则配置
"""

import logging
import asyncio
import json
from typing import Dict, List, Optional, Any

from PySide6.QtCore import Qt, Signal, Slot, QSize, QTimer
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSplitter, QMessageBox, QDialog, QFormLayout, QLineEdit,
    QComboBox, QSpinBox, QCheckBox
)

from wxauto_mgt.core.api_client import instance_manager
from wxauto_mgt.utils.logging import get_logger
from qasync import asyncSlot

# 导入自定义组件
from wxauto_mgt.ui.components.instance_card_list import InstanceCardList
from wxauto_mgt.ui.components.service_platform_panel import ServicePlatformPanel
from wxauto_mgt.ui.components.delivery_rule_panel import DeliveryRulePanel
from wxauto_mgt.ui.components.dialogs import AddInstanceDialog, EditInstanceDialog

logger = get_logger()

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

        # 中间和右侧分割窗口 - 水平分割
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

        # 添加到主布局 - 进一步缩减卡片列表的宽度比例
        main_layout.addWidget(self.instance_list, 1)  # 1/6宽度
        main_layout.addWidget(self.content_splitter, 5)  # 5/6宽度

        # 连接信号
        self.instance_list.instance_selected.connect(self._on_instance_selected)
        self.instance_list.edit_requested.connect(self._edit_instance)
        self.instance_list.delete_requested.connect(self._delete_instance)
        self.instance_list.initialize_requested.connect(self._initialize_instance)

        # 连接添加实例按钮
        self.instance_list.add_btn.clicked.connect(self._add_instance)

        # 初始加载实例列表
        self.instance_list.refresh_instances()

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

    @asyncSlot()
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
