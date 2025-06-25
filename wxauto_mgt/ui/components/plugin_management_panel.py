"""
插件管理面板

该模块提供了插件管理的UI界面，包括：
- 显示所有插件
- 启用/禁用插件
- 配置插件
- 插件健康检查
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any

from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QTabWidget, QGroupBox, QCheckBox, QProgressBar
)

from wxauto_mgt.core.plugin_system import plugin_manager, plugin_config_manager
from wxauto_mgt.utils.logging import get_logger
from qasync import asyncSlot

logger = get_logger()


class PluginManagementPanel(QWidget):
    """插件管理面板"""

    # 定义信号
    plugin_enabled = Signal(str)    # 插件ID
    plugin_disabled = Signal(str)   # 插件ID
    plugin_configured = Signal(str) # 插件ID

    def __init__(self, parent=None):
        """初始化插件管理面板"""
        super().__init__(parent)

        self._init_ui()

        # 初始加载插件列表
        QTimer.singleShot(0, self.refresh_plugins)

    def _init_ui(self):
        """初始化UI"""
        main_layout = QVBoxLayout(self)

        # 创建选项卡
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # 插件列表选项卡
        self._create_plugin_list_tab()

        # 插件健康检查选项卡
        self._create_health_check_tab()

    def _create_plugin_list_tab(self):
        """创建插件列表选项卡"""
        plugin_widget = QWidget()
        layout = QVBoxLayout(plugin_widget)

        # 工具栏
        toolbar_layout = QHBoxLayout()

        self.refresh_btn = QPushButton("刷新插件")
        self.refresh_btn.clicked.connect(self.refresh_plugins)
        toolbar_layout.addWidget(self.refresh_btn)

        self.install_btn = QPushButton("安装插件")
        self.install_btn.clicked.connect(self._install_plugin)
        toolbar_layout.addWidget(self.install_btn)

        toolbar_layout.addStretch()

        # 全局操作
        self.enable_all_btn = QPushButton("启用所有")
        self.enable_all_btn.clicked.connect(self._enable_all_plugins)
        toolbar_layout.addWidget(self.enable_all_btn)

        self.disable_all_btn = QPushButton("禁用所有")
        self.disable_all_btn.clicked.connect(self._disable_all_plugins)
        toolbar_layout.addWidget(self.disable_all_btn)

        layout.addLayout(toolbar_layout)

        # 插件列表表格
        self.plugin_table = QTableWidget(0, 7)  # 0行，7列
        self.plugin_table.setHorizontalHeaderLabels([
            "插件ID", "名称", "版本", "状态", "启用", "配置", "操作"
        ])
        self.plugin_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.plugin_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.plugin_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.plugin_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.plugin_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.plugin_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.plugin_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.plugin_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.plugin_table.setEditTriggers(QTableWidget.NoEditTriggers)

        layout.addWidget(self.plugin_table)

        # 状态标签
        self.status_label = QLabel("共 0 个插件")
        self.status_label.setStyleSheet("color: #666666;")
        layout.addWidget(self.status_label)

        self.tab_widget.addTab(plugin_widget, "插件列表")

    def _create_health_check_tab(self):
        """创建健康检查选项卡"""
        health_widget = QWidget()
        layout = QVBoxLayout(health_widget)

        # 工具栏
        toolbar_layout = QHBoxLayout()

        self.health_check_btn = QPushButton("执行健康检查")
        self.health_check_btn.clicked.connect(self._run_health_check)
        toolbar_layout.addWidget(self.health_check_btn)

        self.auto_check_checkbox = QCheckBox("自动检查")
        self.auto_check_checkbox.setChecked(False)
        self.auto_check_checkbox.toggled.connect(self._toggle_auto_check)
        toolbar_layout.addWidget(self.auto_check_checkbox)

        toolbar_layout.addStretch()

        layout.addLayout(toolbar_layout)

        # 进度条
        self.health_progress = QProgressBar()
        self.health_progress.setVisible(False)
        layout.addWidget(self.health_progress)

        # 健康检查结果表格
        self.health_table = QTableWidget(0, 4)  # 0行，4列
        self.health_table.setHorizontalHeaderLabels([
            "插件ID", "健康状态", "详细信息", "最后检查时间"
        ])
        self.health_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.health_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.health_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.health_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.health_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.health_table.setEditTriggers(QTableWidget.NoEditTriggers)

        layout.addWidget(self.health_table)

        self.tab_widget.addTab(health_widget, "健康检查")

        # 自动检查定时器
        self.auto_check_timer = QTimer()
        self.auto_check_timer.timeout.connect(self._run_health_check)

    @asyncSlot()
    async def refresh_plugins(self):
        """刷新插件列表"""
        try:
            # 清空表格
            self.plugin_table.setRowCount(0)

            # 获取所有插件信息
            plugin_info_dict = plugin_manager.get_all_plugin_info()
            plugins = plugin_manager.get_all_plugins()

            # 添加插件到表格
            for plugin_id, plugin_info in plugin_info_dict.items():
                plugin = plugins.get(plugin_id)
                await self._add_plugin_to_table(plugin_info, plugin)

            # 更新状态标签
            self.status_label.setText(f"共 {len(plugin_info_dict)} 个插件")

            logger.info(f"刷新插件列表成功，共 {len(plugin_info_dict)} 个插件")

        except Exception as e:
            logger.error(f"刷新插件列表失败: {e}")
            QMessageBox.warning(self, "错误", f"刷新插件列表失败: {str(e)}")

    async def _add_plugin_to_table(self, plugin_info, plugin):
        """添加插件到表格"""
        row = self.plugin_table.rowCount()
        self.plugin_table.insertRow(row)

        # 插件ID
        self.plugin_table.setItem(row, 0, QTableWidgetItem(plugin_info.plugin_id))

        # 名称
        self.plugin_table.setItem(row, 1, QTableWidgetItem(plugin_info.name))

        # 版本
        self.plugin_table.setItem(row, 2, QTableWidgetItem(plugin_info.version))

        # 状态
        if plugin:
            state = plugin.get_state().value
            status_item = QTableWidgetItem(state)
            if state == "active":
                status_item.setBackground(QColor(144, 238, 144))  # 浅绿色
            elif state == "error":
                status_item.setBackground(QColor(255, 182, 193))  # 浅红色
            elif state == "inactive":
                status_item.setBackground(QColor(255, 255, 224))  # 浅黄色
            self.plugin_table.setItem(row, 3, status_item)
        else:
            self.plugin_table.setItem(row, 3, QTableWidgetItem("未加载"))

        # 启用/禁用复选框
        enabled_checkbox = QCheckBox()
        enabled = await plugin_config_manager.is_plugin_enabled(plugin_info.plugin_id)
        enabled_checkbox.setChecked(enabled)
        enabled_checkbox.setProperty("plugin_id", plugin_info.plugin_id)
        enabled_checkbox.toggled.connect(self._on_plugin_enabled_changed)
        self.plugin_table.setCellWidget(row, 4, enabled_checkbox)

        # 配置按钮
        config_btn = QPushButton("配置")
        config_btn.setProperty("plugin_id", plugin_info.plugin_id)
        config_btn.clicked.connect(self._configure_plugin)
        self.plugin_table.setCellWidget(row, 5, config_btn)

        # 操作按钮
        action_widget = QWidget()
        action_layout = QHBoxLayout(action_widget)
        action_layout.setContentsMargins(2, 2, 2, 2)

        test_btn = QPushButton("测试")
        test_btn.setProperty("plugin_id", plugin_info.plugin_id)
        test_btn.clicked.connect(self._test_plugin)
        action_layout.addWidget(test_btn)

        uninstall_btn = QPushButton("卸载")
        uninstall_btn.setProperty("plugin_id", plugin_info.plugin_id)
        uninstall_btn.clicked.connect(self._uninstall_plugin)
        action_layout.addWidget(uninstall_btn)

        self.plugin_table.setCellWidget(row, 6, action_widget)

    @Slot(bool)
    def _on_plugin_enabled_changed(self, checked):
        """插件启用状态改变"""
        sender = self.sender()
        plugin_id = sender.property("plugin_id")

        if checked:
            self._enable_plugin_async(plugin_id)
        else:
            self._disable_plugin_async(plugin_id)

    @asyncSlot()
    async def _enable_plugin_async(self, plugin_id: str):
        """异步启用插件"""
        try:
            # 加载配置
            config = await plugin_config_manager.load_plugin_config(plugin_id)
            if not config:
                QMessageBox.warning(self, "警告", f"插件 {plugin_id} 没有配置，请先配置插件")
                await self.refresh_plugins()  # 刷新以重置复选框状态
                return

            # 启用插件
            success = await plugin_manager.enable_plugin(plugin_id, config)
            if success:
                await plugin_config_manager.enable_plugin(plugin_id)
                self.plugin_enabled.emit(plugin_id)
                QMessageBox.information(self, "成功", f"插件 {plugin_id} 启用成功")
            else:
                QMessageBox.warning(self, "错误", f"插件 {plugin_id} 启用失败")

            await self.refresh_plugins()

        except Exception as e:
            logger.error(f"启用插件失败: {plugin_id}, 错误: {e}")
            QMessageBox.warning(self, "错误", f"启用插件失败: {str(e)}")
            await self.refresh_plugins()

    @asyncSlot()
    async def _disable_plugin_async(self, plugin_id: str):
        """异步禁用插件"""
        try:
            success = await plugin_manager.disable_plugin(plugin_id)
            if success:
                await plugin_config_manager.disable_plugin(plugin_id)
                self.plugin_disabled.emit(plugin_id)
                QMessageBox.information(self, "成功", f"插件 {plugin_id} 禁用成功")
            else:
                QMessageBox.warning(self, "错误", f"插件 {plugin_id} 禁用失败")

            await self.refresh_plugins()

        except Exception as e:
            logger.error(f"禁用插件失败: {plugin_id}, 错误: {e}")
            QMessageBox.warning(self, "错误", f"禁用插件失败: {str(e)}")
            await self.refresh_plugins()

    @Slot()
    def _configure_plugin(self):
        """配置插件"""
        sender = self.sender()
        plugin_id = sender.property("plugin_id")

        # 导入配置对话框
        from wxauto_mgt.ui.components.dialogs.plugin_config_dialog import PluginConfigDialog

        dialog = PluginConfigDialog(self, plugin_id)
        if dialog.exec():
            self.plugin_configured.emit(plugin_id)
            QTimer.singleShot(100, self.refresh_plugins)

    @Slot()
    def _test_plugin(self):
        """测试插件"""
        sender = self.sender()
        plugin_id = sender.property("plugin_id")
        self._test_plugin_async(plugin_id)

    @asyncSlot()
    async def _test_plugin_async(self, plugin_id: str):
        """异步测试插件"""
        try:
            plugin = plugin_manager.get_plugin(plugin_id)
            if not plugin:
                QMessageBox.warning(self, "错误", f"插件 {plugin_id} 未找到")
                return

            if hasattr(plugin, 'test_connection'):
                result = await plugin.test_connection()
                if result.get('success'):
                    QMessageBox.information(self, "测试成功", 
                                          f"插件 {plugin_id} 测试成功\n{result.get('message', '')}")
                else:
                    QMessageBox.warning(self, "测试失败", 
                                      f"插件 {plugin_id} 测试失败\n{result.get('error', '')}")
            else:
                QMessageBox.information(self, "提示", f"插件 {plugin_id} 不支持连接测试")

        except Exception as e:
            logger.error(f"测试插件失败: {plugin_id}, 错误: {e}")
            QMessageBox.warning(self, "错误", f"测试插件失败: {str(e)}")

    @Slot()
    def _install_plugin(self):
        """安装插件"""
        QMessageBox.information(self, "提示", "插件安装功能正在开发中")

    @Slot()
    def _uninstall_plugin(self):
        """卸载插件"""
        sender = self.sender()
        plugin_id = sender.property("plugin_id")

        reply = QMessageBox.question(self, "确认", f"确定要卸载插件 {plugin_id} 吗？",
                                   QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self._uninstall_plugin_async(plugin_id)

    @asyncSlot()
    async def _uninstall_plugin_async(self, plugin_id: str):
        """异步卸载插件"""
        try:
            success = await plugin_manager.uninstall_plugin(plugin_id)
            if success:
                await plugin_config_manager.delete_plugin_config(plugin_id)
                QMessageBox.information(self, "成功", f"插件 {plugin_id} 卸载成功")
                await self.refresh_plugins()
            else:
                QMessageBox.warning(self, "错误", f"插件 {plugin_id} 卸载失败")

        except Exception as e:
            logger.error(f"卸载插件失败: {plugin_id}, 错误: {e}")
            QMessageBox.warning(self, "错误", f"卸载插件失败: {str(e)}")

    @asyncSlot()
    async def _enable_all_plugins(self):
        """启用所有插件"""
        try:
            plugin_info_dict = plugin_manager.get_all_plugin_info()
            for plugin_id in plugin_info_dict.keys():
                config = await plugin_config_manager.load_plugin_config(plugin_id)
                if config:
                    await plugin_manager.enable_plugin(plugin_id, config)
                    await plugin_config_manager.enable_plugin(plugin_id)

            await self.refresh_plugins()
            QMessageBox.information(self, "成功", "所有插件启用完成")

        except Exception as e:
            logger.error(f"启用所有插件失败: {e}")
            QMessageBox.warning(self, "错误", f"启用所有插件失败: {str(e)}")

    @asyncSlot()
    async def _disable_all_plugins(self):
        """禁用所有插件"""
        try:
            plugin_info_dict = plugin_manager.get_all_plugin_info()
            for plugin_id in plugin_info_dict.keys():
                await plugin_manager.disable_plugin(plugin_id)
                await plugin_config_manager.disable_plugin(plugin_id)

            await self.refresh_plugins()
            QMessageBox.information(self, "成功", "所有插件禁用完成")

        except Exception as e:
            logger.error(f"禁用所有插件失败: {e}")
            QMessageBox.warning(self, "错误", f"禁用所有插件失败: {str(e)}")

    @asyncSlot()
    async def _run_health_check(self):
        """执行健康检查"""
        try:
            self.health_progress.setVisible(True)
            self.health_progress.setValue(0)

            # 清空健康检查表格
            self.health_table.setRowCount(0)

            # 获取所有插件的健康检查结果
            health_results = await plugin_manager.health_check_all()

            total_plugins = len(health_results)
            for i, (plugin_id, result) in enumerate(health_results.items()):
                # 更新进度
                self.health_progress.setValue(int((i + 1) / total_plugins * 100))

                # 添加到健康检查表格
                row = self.health_table.rowCount()
                self.health_table.insertRow(row)

                self.health_table.setItem(row, 0, QTableWidgetItem(plugin_id))

                # 健康状态
                healthy = result.get('healthy', False)
                status_item = QTableWidgetItem("健康" if healthy else "异常")
                if healthy:
                    status_item.setBackground(QColor(144, 238, 144))  # 浅绿色
                else:
                    status_item.setBackground(QColor(255, 182, 193))  # 浅红色
                self.health_table.setItem(row, 1, status_item)

                # 详细信息
                details = []
                if 'error' in result:
                    details.append(f"错误: {result['error']}")
                if 'connection_ok' in result:
                    details.append(f"连接: {'正常' if result['connection_ok'] else '异常'}")
                if 'config_valid' in result:
                    details.append(f"配置: {'有效' if result['config_valid'] else '无效'}")

                self.health_table.setItem(row, 2, QTableWidgetItem("; ".join(details)))

                # 检查时间
                import datetime
                check_time = datetime.datetime.now().strftime("%H:%M:%S")
                self.health_table.setItem(row, 3, QTableWidgetItem(check_time))

            self.health_progress.setVisible(False)
            logger.info("插件健康检查完成")

        except Exception as e:
            self.health_progress.setVisible(False)
            logger.error(f"执行健康检查失败: {e}")
            QMessageBox.warning(self, "错误", f"执行健康检查失败: {str(e)}")

    @Slot(bool)
    def _toggle_auto_check(self, enabled):
        """切换自动检查"""
        if enabled:
            self.auto_check_timer.start(60000)  # 每分钟检查一次
            logger.info("启用自动健康检查")
        else:
            self.auto_check_timer.stop()
            logger.info("禁用自动健康检查")
