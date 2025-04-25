"""
主窗口模块

实现应用程序的主窗口，包含菜单栏、状态栏和基于选项卡的界面布局。
提供实例管理、消息监听和状态监控等功能的访问入口。
"""

import os
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, Signal, Slot, QSize, QTimer
from PySide6.QtGui import QIcon, QAction, QPixmap
from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QStatusBar, QMenuBar, QMenu, QToolBar, 
    QMessageBox, QLabel, QWidget, QApplication, QDockWidget, QVBoxLayout
)

from app.core.api_client import instance_manager
from app.core.config_manager import config_manager
from app.utils.logging import get_logger

# 延迟导入UI组件，避免循环导入
# 实际使用时在方法内导入

logger = get_logger()


class MainWindow(QMainWindow):
    """
    主窗口类，包含应用程序的主UI界面
    """
    
    # 定义信号
    status_changed = Signal(str, int)  # 状态消息, 超时时间
    
    def __init__(self, parent=None):
        """初始化主窗口"""
        super().__init__(parent)
        
        self.setWindowTitle("WxAuto管理工具")
        self.resize(1200, 800)
        
        # 初始化UI
        self._init_ui()
        
        # 启动延迟任务，强制保存一次配置
        QTimer.singleShot(2000, self._delayed_config_save)
        
        logger.info("主窗口已初始化")
    
    def _init_ui(self):
        """初始化UI组件"""
        # 创建中央选项卡控件
        self.tab_widget = QTabWidget(self)
        self.setCentralWidget(self.tab_widget)
        
        # 创建菜单栏
        self._create_menu_bar()
        
        # 创建工具栏
        self._create_tool_bar()
        
        # 创建状态栏
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)
        
        # 状态标签
        self.status_label = QLabel("就绪")
        self.status_bar.addPermanentWidget(self.status_label)
        
        # 添加各功能选项卡
        self._create_tabs()
        
        # 连接信号
        self.status_changed.connect(self._on_status_changed)
    
    def _create_menu_bar(self):
        """创建菜单栏"""
        # 文件菜单
        file_menu = self.menuBar().addMenu("文件(&F)")
        
        # 导入配置
        import_config_action = QAction("导入配置", self)
        import_config_action.triggered.connect(self._import_config)
        file_menu.addAction(import_config_action)
        
        # 导出配置
        export_config_action = QAction("导出配置", self)
        export_config_action.triggered.connect(self._export_config)
        file_menu.addAction(export_config_action)
        
        file_menu.addSeparator()
        
        # 退出
        exit_action = QAction("退出(&Q)", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 实例菜单
        instance_menu = self.menuBar().addMenu("实例(&I)")
        
        # 添加实例
        add_instance_action = QAction("添加实例", self)
        add_instance_action.triggered.connect(self._add_instance)
        instance_menu.addAction(add_instance_action)
        
        # 管理实例
        manage_instances_action = QAction("管理实例", self)
        manage_instances_action.triggered.connect(self._manage_instances)
        instance_menu.addAction(manage_instances_action)
        
        # 工具菜单
        tools_menu = self.menuBar().addMenu("工具(&T)")
        
        # 配置选项
        settings_action = QAction("设置", self)
        settings_action.triggered.connect(self._open_settings)
        tools_menu.addAction(settings_action)
        
        # 帮助菜单
        help_menu = self.menuBar().addMenu("帮助(&H)")
        
        # 关于
        about_action = QAction("关于", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
    
    def _create_tool_bar(self):
        """创建工具栏"""
        self.tool_bar = QToolBar("工具栏", self)
        self.tool_bar.setIconSize(QSize(24, 24))
        self.addToolBar(Qt.TopToolBarArea, self.tool_bar)
        
        # 添加实例按钮
        add_instance_action = QAction("添加实例", self)
        add_instance_action.triggered.connect(self._add_instance)
        self.tool_bar.addAction(add_instance_action)
        
        # 消息监听按钮
        messages_action = QAction("消息监听", self)
        messages_action.triggered.connect(lambda: self.tab_widget.setCurrentIndex(1))
        self.tool_bar.addAction(messages_action)
        
        # 状态监控按钮
        status_action = QAction("状态监控", self)
        status_action.triggered.connect(lambda: self.tab_widget.setCurrentIndex(2))
        self.tool_bar.addAction(status_action)
        
        # 设置按钮
        settings_action = QAction("设置", self)
        settings_action.triggered.connect(self._open_settings)
        self.tool_bar.addAction(settings_action)
    
    def _create_tabs(self):
        """创建功能选项卡"""
        # 导入组件
        from app.ui.components.instance_panel import InstanceManagerPanel
        from app.ui.components.message_panel import MessageListenerPanel
        from app.ui.components.status_panel import StatusMonitorPanel
        
        # 实例管理选项卡
        self.instance_panel = InstanceManagerPanel(self)
        self.tab_widget.addTab(self.instance_panel, "实例管理")
        
        # 消息监听选项卡
        self.message_panel = MessageListenerPanel(self)
        self.tab_widget.addTab(self.message_panel, "消息监听")
        
        # 状态监控选项卡
        self.status_panel = StatusMonitorPanel(self)
        self.tab_widget.addTab(self.status_panel, "状态监控")
    
    @Slot(str, int)
    def _on_status_changed(self, message, timeout=0):
        """
        显示状态栏消息
        
        Args:
            message: 状态消息
            timeout: 消息显示时间（毫秒），0表示一直显示
        """
        self.status_bar.showMessage(message, timeout)
        self.status_label.setText(message)
    
    def _import_config(self):
        """导入配置"""
        # 这里将在后续实现
        self.status_changed.emit("配置导入功能尚未实现", 3000)
    
    def _export_config(self):
        """导出配置"""
        # 这里将在后续实现
        self.status_changed.emit("配置导出功能尚未实现", 3000)
    
    def _add_instance(self):
        """添加实例"""
        # 导入对话框
        from app.ui.components.dialogs import AddInstanceDialog
        
        dialog = AddInstanceDialog(self)
        if dialog.exec():
            instance_data = dialog.get_instance_data()
            # 添加实例...
            self.status_changed.emit(f"添加实例成功: {instance_data['name']}", 3000)
            # 刷新实例列表
            self.instance_panel.refresh_instances()
    
    def _manage_instances(self):
        """管理实例"""
        # 切换到实例管理选项卡
        self.tab_widget.setCurrentIndex(0)
    
    def _open_settings(self):
        """打开设置对话框"""
        # 导入设置对话框
        from app.ui.components.dialogs import SettingsDialog
        
        dialog = SettingsDialog(self)
        if dialog.exec():
            # 应用设置...
            self.status_changed.emit("设置已更新", 3000)
    
    def _show_about(self):
        """显示关于对话框"""
        QMessageBox.about(
            self,
            "关于 WxAuto管理工具",
            """<h3>WxAuto管理工具</h3>
            <p>版本: 0.1.0</p>
            <p>一个用于管理多个WxAuto实例的工具，提供消息监听、状态监控等功能。</p>
            """
        )
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        reply = QMessageBox.question(
            self, 
            '确认退出', 
            "确定要退出应用程序吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            logger.info("用户请求关闭应用程序")
            # 执行清理操作
            event.accept()
        else:
            event.ignore() 

    def _delayed_config_save(self):
        """延迟执行的配置保存任务"""
        import asyncio
        
        # 强制执行一次配置保存
        async def save_config_task():
            try:
                # 从配置管理器中获取所有实例
                from app.core.config_manager import config_manager
                instances = config_manager.get('instances', [])
                
                if instances:
                    logger.info(f"启动时强制保存 {len(instances)} 个实例配置")
                    # 保存配置
                    await config_manager.save_config()
                    
                    # 刷新UI上的实例列表
                    if hasattr(self, 'instance_panel'):
                        self.instance_panel.refresh_instances()
            except Exception as e:
                logger.error(f"启动时保存配置失败: {e}")
        
        # 启动异步任务
        asyncio.create_task(save_config_task()) 