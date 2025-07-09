"""
主窗口模块

实现应用程序的主窗口，包含菜单栏、状态栏和基于选项卡的界面布局。
提供实例管理、消息监听和状态监控等功能的访问入口。
"""

import os
import sys
import asyncio
import subprocess
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, Signal, Slot, QSize, QTimer
from PySide6.QtGui import QIcon, QAction, QPixmap
from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QStatusBar, QMenuBar, QMenu, QToolBar,
    QMessageBox, QLabel, QWidget, QApplication, QDockWidget, QVBoxLayout,
    QHBoxLayout, QPushButton, QSpinBox, QCheckBox, QGroupBox, QLineEdit
)

from wxauto_mgt.core.api_client import instance_manager
from wxauto_mgt.data.config_store import config_store
from wxauto_mgt.utils.logging import logger
from wxauto_mgt.web import is_web_service_running
from wxauto_mgt.core.service_platform_manager import platform_manager, rule_manager
from wxauto_mgt.ui.utils.ui_monitor import start_ui_monitoring, stop_ui_monitoring

# 延迟导入UI组件，避免循环导入
# 实际使用时在方法内导入

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
        # 使用包装函数来正确处理协程
        def start_delayed_save():
            logger.info("启动延迟配置保存任务（2秒后执行）")
            asyncio.create_task(self._delayed_config_save())

        logger.info("设置延迟配置保存定时器")
        QTimer.singleShot(2000, start_delayed_save)

        # 启动UI响应性监控
        start_ui_monitoring()

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

        # 创建Web服务控制区域
        self._create_web_service_controls()

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
        # 创建工具栏
        self.toolbar = QToolBar("主工具栏", self)
        self.toolbar.setMovable(False)
        self.addToolBar(Qt.TopToolBarArea, self.toolbar)

        # 添加实例管理按钮
        manage_action = QAction("实例管理", self)
        manage_action.triggered.connect(self._manage_instances)
        self.toolbar.addAction(manage_action)

        # 添加消息监听按钮
        message_action = QAction("消息监听", self)
        message_action.triggered.connect(lambda: self.tab_widget.setCurrentIndex(1))
        self.toolbar.addAction(message_action)

        # 添加分隔符
        self.toolbar.addSeparator()

        # 添加设置按钮
        settings_action = QAction("设置", self)
        settings_action.triggered.connect(self._open_settings)
        self.toolbar.addAction(settings_action)

    def _create_tabs(self):
        """创建功能选项卡"""
        # 导入组件
        from wxauto_mgt.ui.components.instance_manager_panel import InstanceManagerPanel
        from wxauto_mgt.ui.components.message_panel import MessageListenerPanel
        from wxauto_mgt.ui.components.web_service_panel import WebServicePanel
        # 状态监控标签页已隐藏
        # from wxauto_mgt.ui.components.status_panel import StatusMonitorPanel

        # 实例管理选项卡 - 使用新的实例管理面板
        self.instance_panel = InstanceManagerPanel(self)
        self.tab_widget.addTab(self.instance_panel, "实例管理")

        # 消息监听选项卡
        self.message_panel = MessageListenerPanel(self)
        self.tab_widget.addTab(self.message_panel, "消息监听")

        # Web服务管理选项卡
        self.web_service_panel = WebServicePanel(self)
        self.tab_widget.addTab(self.web_service_panel, "Web管理")

        # 状态监控选项卡已隐藏
        # self.status_panel = StatusMonitorPanel(self)
        # self.tab_widget.addTab(self.status_panel, "状态监控")

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
        from wxauto_mgt.ui.components.dialogs import AddInstanceDialog

        dialog = AddInstanceDialog(self)
        if dialog.exec():
            instance_data = dialog.get_instance_data()
            # 创建异步任务添加实例
            asyncio.create_task(self._add_instance_async(instance_data))

    async def _add_instance_async(self, instance_data):
        """异步添加实例"""
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
                # 添加实例到API客户端
                instance_manager.add_instance(
                    instance_data["instance_id"],
                    instance_data["base_url"],
                    instance_data["api_key"],
                    instance_data.get("timeout", 30)
                )

                # 显示成功消息
                self.status_changed.emit(f"添加实例成功: {instance_data['name']}", 3000)

                # 刷新实例列表
                self.instance_panel.refresh_instances()
            else:
                self.status_changed.emit(f"添加实例失败: {instance_data['name']}", 3000)
        except Exception as e:
            logger.error(f"添加实例失败: {e}")
            self.status_changed.emit(f"添加实例失败: {str(e)}", 3000)

    def _manage_instances(self):
        """管理实例"""
        # 切换到实例管理选项卡
        self.tab_widget.setCurrentIndex(0)

    def _open_settings(self):
        """打开设置对话框"""
        try:
            # 从dialogs模块导入设置对话框
            from wxauto_mgt.ui.components.dialogs import SettingsDialog

            dialog = SettingsDialog(self)
            if dialog.exec():
                # 应用设置...
                self.status_changed.emit("设置已更新", 3000)

        except Exception as e:
            logger.error(f"打开设置对话框失败: {e}")
            QMessageBox.critical(self, "错误", f"无法打开设置对话框: {str(e)}\n\n请检查设置对话框模块是否正确安装。")

    def _show_about(self):
        """显示关于对话框"""
        # 从配置模块获取版本信息
        from wxauto_mgt.config import get_version
        version = get_version()

        QMessageBox.about(
            self,
            "关于 WxAuto管理工具",
            f"""<h3>WxAuto管理工具</h3>
            <p>版本: {version}</p>
            <p>一个用于管理多个WxAuto实例的工具，提供消息监听、状态监控等功能。</p>
            """
        )

    def closeEvent(self, event):
        """窗口关闭事件 - 强制快速关闭"""
        reply = QMessageBox.question(
            self,
            '确认退出',
            "确定要退出应用程序吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            logger.info("用户请求关闭应用程序，开始强制关闭流程")

            # 立即停止所有定时器
            if hasattr(self, 'web_status_timer'):
                self.web_status_timer.stop()

            # 停止UI监控
            stop_ui_monitoring()

            # 强制关闭事件循环
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                if loop and not loop.is_closed():
                    logger.info("强制停止事件循环")
                    loop.stop()
            except Exception as e:
                logger.warning(f"停止事件循环时出错: {e}")

            # 立即接受关闭事件
            event.accept()

            # 强制退出程序（如果其他方法失败）
            import os
            import sys

            def force_exit():
                """延迟强制退出，给清理过程一些时间"""
                import time
                time.sleep(3)  # 给清理过程3秒时间
                logger.warning("强制退出程序")
                if getattr(sys, 'frozen', False):
                    os._exit(0)
                else:
                    sys.exit(0)

            # 在后台线程中启动强制退出
            import threading
            threading.Thread(target=force_exit, daemon=True).start()

        else:
            event.ignore()

    async def _delayed_config_save(self):
        """延迟执行的配置保存任务"""
        logger.info("开始执行延迟配置保存任务")
        try:
            # 从配置存储中获取所有实例
            logger.debug("正在获取实例配置...")
            instances = await config_store.get_config('system', 'instances', [])

            if instances:
                logger.info(f"启动时强制保存 {len(instances)} 个实例配置")

                # 刷新UI上的实例列表
                if hasattr(self, 'instance_panel'):
                    self.instance_panel.refresh_instances()

            # 加载Web服务配置
            logger.debug("正在获取Web服务配置...")
            web_config = await config_store.get_config('system', 'web_service', {})
            logger.debug(f"获取到Web服务配置: {web_config}")

            if web_config:
                logger.info(f"加载Web服务配置: {web_config}")

                # 更新Web服务面板的UI显示
                if hasattr(self, 'web_service_panel'):
                    logger.debug("正在刷新Web服务面板UI...")
                    self.web_service_panel.refresh_config_from_database(web_config)
                    logger.info("已更新Web服务面板UI配置")
                else:
                    logger.warning("Web服务面板尚未初始化，跳过UI更新")

                # 检查是否需要自动启动Web服务
                if 'auto_start' in web_config and web_config['auto_start']:
                    logger.info("检测到Web服务自动启动配置")

                    # 如果Web服务面板已初始化，使用其方法启动Web服务
                    if hasattr(self, 'web_service_panel'):
                        # 获取配置
                        host = web_config.get('host', '127.0.0.1')
                        port = web_config.get('port', 8443)

                        # 启动Web服务
                        await self.web_service_panel._start_web_service(host, port)
            else:
                logger.warning("未获取到Web服务配置或配置为空")

            logger.info("延迟配置保存任务完成")
        except Exception as e:
            logger.error(f"启动时保存配置失败: {str(e)}")
            import traceback
            logger.error(f"异常详情: {traceback.format_exc()}")

    def _create_web_service_controls(self):
        """创建Web服务控制区域"""
        # 创建Web服务控制区域容器
        web_service_container = QWidget()
        web_service_layout = QHBoxLayout(web_service_container)
        web_service_layout.setContentsMargins(5, 0, 5, 0)

        # 创建Web服务控制组
        web_service_group = QGroupBox("Web管理服务")
        web_service_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                margin-top: 0.5em;
                padding-top: 0.5em;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px 0 3px;
            }
        """)

        # Web服务控制布局
        group_layout = QHBoxLayout(web_service_group)
        group_layout.setContentsMargins(10, 5, 10, 5)
        group_layout.setSpacing(10)

        # 状态标签
        status_label = QLabel("状态:")
        group_layout.addWidget(status_label)

        self.web_service_status = QLabel("未运行")
        self.web_service_status.setStyleSheet("color: #f5222d; font-weight: bold;")  # 红色表示未运行
        group_layout.addWidget(self.web_service_status)

        # 创建定时器，定期更新Web服务状态
        self.web_status_timer = QTimer(self)
        self.web_status_timer.timeout.connect(self._update_web_service_status)
        self.web_status_timer.start(2000)  # 每2秒更新一次状态

        # 打开Web界面按钮
        self.open_web_btn = QPushButton("打开界面")
        self.open_web_btn.setStyleSheet("""
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
            QPushButton:disabled {
                background-color: #d9d9d9;
                color: #ffffff;
            }
        """)
        self.open_web_btn.clicked.connect(self._open_web_interface)
        self.open_web_btn.setEnabled(False)  # 初始状态禁用
        group_layout.addWidget(self.open_web_btn)

        # 管理按钮 - 打开Web管理选项卡
        manage_web_btn = QPushButton("管理Web服务")
        manage_web_btn.setStyleSheet("""
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
        manage_web_btn.clicked.connect(self._open_web_service_tab)
        group_layout.addWidget(manage_web_btn)

        # 添加到主布局
        web_service_layout.addWidget(web_service_group)

        # 添加消息监听控制按钮
        self.message_listener_btn = QPushButton("开始监听")
        self.message_listener_btn.setStyleSheet("""
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
        self.message_listener_btn.clicked.connect(self._toggle_message_listener)
        web_service_layout.addWidget(self.message_listener_btn)

        # 添加暂停/继续监听按钮
        self.pause_resume_btn = QPushButton("暂停监听")
        self.pause_resume_btn.setStyleSheet("""
            QPushButton {
                background-color: #FFA500;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #FFB84D;
            }
        """)
        self.pause_resume_btn.setToolTip("暂停/继续消息监听服务")
        self.pause_resume_btn.clicked.connect(self._toggle_listening_service)
        web_service_layout.addWidget(self.pause_resume_btn)

        # 添加启动本地API客户端按钮
        self.start_api_client_btn = QPushButton("启动本地API客户端")
        self.start_api_client_btn.setStyleSheet("""
            QPushButton {
                background-color: #722ed1;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #9254de;
            }
        """)
        self.start_api_client_btn.setToolTip("启动本地API客户端 (wxauto_http_api.exe)")
        self.start_api_client_btn.clicked.connect(self._start_api_client)
        web_service_layout.addWidget(self.start_api_client_btn)

        # 初始化监听状态
        self._is_listening_paused = False

        # 将Web服务控制区域添加到工具栏
        self.toolbar.addWidget(web_service_container)

        # 初始化Web服务状态
        self._update_web_service_status()

        # 初始化消息监听按钮状态
        self._update_message_listener_status()

    def _update_web_service_status(self):
        """更新Web服务状态显示"""
        running = is_web_service_running()

        if running:
            self.web_service_status.setText("运行中")
            self.web_service_status.setStyleSheet("color: #52c41a; font-weight: bold;")  # 绿色表示运行中
            self.open_web_btn.setEnabled(True)  # 启用打开Web界面按钮

            # 如果Web服务面板已初始化，也更新其状态
            if hasattr(self, 'web_service_panel'):
                self.web_service_panel._update_web_service_status()
        else:
            self.web_service_status.setText("未运行")
            self.web_service_status.setStyleSheet("color: #f5222d; font-weight: bold;")  # 红色表示未运行
            self.open_web_btn.setEnabled(False)  # 禁用打开Web界面按钮

            # 如果Web服务面板已初始化，也更新其状态
            if hasattr(self, 'web_service_panel'):
                self.web_service_panel._update_web_service_status()

        # 确保状态显示正确
        QApplication.processEvents()

    def _update_message_listener_status(self):
        """更新消息监听按钮状态"""
        try:
            from wxauto_mgt.core.message_listener import message_listener

            # 检查消息监听器是否正在运行
            is_running = message_listener.running

            # 更新按钮状态
            self._update_message_listener_button(is_running)

            # 更新暂停/继续按钮的可见性
            self._update_pause_resume_buttons_visibility(is_running)

            # 如果监听服务正在运行，同步暂停/继续按钮的状态
            if is_running:
                # 检查监听服务是否暂停
                is_paused = getattr(message_listener, '_paused', False)
                self._is_listening_paused = is_paused
                self._update_pause_resume_button(is_paused)

        except Exception as e:
            logger.error(f"更新消息监听状态失败: {e}")
            # 如果出错，默认显示为未运行状态
            self._update_message_listener_button(False)
            self._update_pause_resume_buttons_visibility(False)

    def _open_web_service_tab(self):
        """打开Web服务管理选项卡"""
        # 查找Web服务选项卡的索引
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabText(i) == "Web管理":
                self.tab_widget.setCurrentIndex(i)
                return

    def _open_web_interface(self):
        """打开Web管理界面"""
        if not is_web_service_running():
            self.status_changed.emit("Web服务未运行，无法打开界面", 3000)
            return

        try:
            # 使用Web服务面板中的方法打开Web界面
            if hasattr(self, 'web_service_panel'):
                self.web_service_panel._open_web_interface()
            else:
                # 使用默认配置
                host = '127.0.0.1'
                port = 8443

                # 构建URL
                url = f"http://{host}:{port}"

                # 使用系统默认浏览器打开URL
                import webbrowser
                webbrowser.open(url)

                self.status_changed.emit(f"已在浏览器中打开Web管理界面: {url}", 3000)
        except Exception as e:
            self.status_changed.emit(f"打开Web界面失败: {str(e)}", 3000)
            logger.error(f"打开Web界面失败: {e}")

    def _load_web_service_config(self):
        """从配置中加载Web服务配置"""
        # 这个方法现在由Web服务面板处理，这里只是为了兼容性保留
        pass

    def _toggle_web_service(self):
        """切换Web服务状态"""
        # 打开Web服务选项卡
        self._open_web_service_tab()

        # 使用Web服务面板中的方法切换Web服务状态
        if hasattr(self, 'web_service_panel'):
            self.web_service_panel._toggle_web_service()

    # 这些方法已移至Web服务面板，这里删除

    def _toggle_message_listener(self):
        """切换消息监听状态"""
        asyncio.create_task(self._toggle_message_listener_async())

    async def _toggle_message_listener_async(self):
        """异步切换消息监听状态"""
        try:
            from wxauto_mgt.core.message_listener import message_listener

            # 记录当前状态，用于异常时恢复
            original_running_state = message_listener.running

            if message_listener.running:
                # 停止监听 - 立即更新按钮状态为"正在停止"
                self._update_message_listener_button_processing("正在停止...")
                self.status_changed.emit("正在停止消息监听...", 0)

                try:
                    await message_listener.stop()
                    self.status_changed.emit("消息监听已停止", 3000)
                    logger.info("消息监听已停止")

                    # 更新按钮状态为最终状态
                    self._update_message_listener_button(False)

                    # 隐藏暂停/继续监听按钮
                    self._update_pause_resume_buttons_visibility(False)

                    # 通知消息面板刷新监听列表
                    self._notify_message_panel_refresh()

                except Exception as e:
                    # 停止失败，恢复到原始状态
                    self._update_message_listener_button(original_running_state)
                    raise e

            else:
                # 开始监听 - 立即更新按钮状态为"正在启动"
                self._update_message_listener_button_processing("正在启动...")
                self.status_changed.emit("正在启动消息监听...", 0)

                try:
                    await message_listener.start()
                    self.status_changed.emit("消息监听已启动", 3000)
                    logger.info("消息监听已启动")

                    # 更新按钮状态为最终状态
                    self._update_message_listener_button(True)

                    # 显示暂停/继续监听按钮
                    self._update_pause_resume_buttons_visibility(True)

                    # 通知消息面板刷新监听列表
                    self._notify_message_panel_refresh()

                except Exception as e:
                    # 启动失败，恢复到原始状态
                    self._update_message_listener_button(original_running_state)
                    raise e

        except Exception as e:
            error_msg = f"切换消息监听状态失败: {str(e)}"
            self.status_changed.emit(error_msg, 5000)
            logger.error(error_msg)

    def _notify_message_panel_refresh(self):
        """通知消息面板刷新监听列表"""
        try:
            # 延迟一段时间后刷新，确保监听服务完全启动
            QTimer.singleShot(500, self._refresh_message_panel)
        except Exception as e:
            logger.error(f"通知消息面板刷新时出错: {e}")

    def _refresh_message_panel(self):
        """刷新消息面板的监听列表"""
        try:
            # 查找消息面板并刷新监听列表
            for i in range(self.tab_widget.count()):
                widget = self.tab_widget.widget(i)
                if hasattr(widget, 'refresh_listeners'):
                    # 使用QTimer延迟执行，避免异步任务冲突
                    QTimer.singleShot(10, lambda: widget.refresh_listeners())
                    logger.debug("已通知消息面板刷新监听列表")
                    break
        except Exception as e:
            logger.error(f"刷新消息面板时出错: {e}")

    def _update_message_listener_button(self, is_running: bool):
        """更新消息监听按钮状态"""
        if is_running:
            self.message_listener_btn.setText("结束监听")
            self.message_listener_btn.setStyleSheet("""
                QPushButton {
                    background-color: #ff4d4f;
                    color: white;
                    border: none;
                    padding: 6px 12px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #ff7875;
                }
            """)
            self.message_listener_btn.setEnabled(True)
        else:
            self.message_listener_btn.setText("开始监听")
            self.message_listener_btn.setStyleSheet("""
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
            self.message_listener_btn.setEnabled(True)

    def _update_message_listener_button_processing(self, text: str):
        """更新消息监听按钮为处理中状态"""
        self.message_listener_btn.setText(text)
        self.message_listener_btn.setStyleSheet("""
            QPushButton {
                background-color: #faad14;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #ffc53d;
            }
        """)
        # 禁用按钮，防止重复点击
        self.message_listener_btn.setEnabled(False)

    def _update_pause_resume_buttons_visibility(self, visible: bool):
        """更新暂停/继续监听按钮的可见性"""
        # 查找消息面板中的暂停/继续按钮并设置可见性
        if hasattr(self, 'message_panel'):
            if hasattr(self.message_panel, 'pause_btn'):
                self.message_panel.pause_btn.setVisible(visible)
            if hasattr(self.message_panel, 'resume_btn'):
                self.message_panel.resume_btn.setVisible(visible)

    def _update_pause_resume_button(self, is_paused: bool):
        """更新暂停/继续监听按钮状态"""
        if is_paused:
            # 暂停状态 - 显示"继续监听"
            self.pause_resume_btn.setText("继续监听")
            self.pause_resume_btn.setStyleSheet("""
                QPushButton {
                    background-color: #FF4500;
                    color: white;
                    border: none;
                    padding: 6px 12px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #FF6347;
                }
            """)
        else:
            # 运行状态 - 显示"暂停监听"
            self.pause_resume_btn.setText("暂停监听")
            self.pause_resume_btn.setStyleSheet("""
                QPushButton {
                    background-color: #FFA500;
                    color: white;
                    border: none;
                    padding: 6px 12px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #FFB84D;
                }
            """)
        self.pause_resume_btn.setEnabled(True)

    def _update_pause_resume_button_processing(self, text: str):
        """更新暂停/继续监听按钮为处理中状态"""
        self.pause_resume_btn.setText(text)
        self.pause_resume_btn.setStyleSheet("""
            QPushButton {
                background-color: #faad14;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #ffc53d;
            }
        """)
        # 禁用按钮，防止重复点击
        self.pause_resume_btn.setEnabled(False)

    def _toggle_listening_service(self):
        """暂停/继续消息监听服务"""
        # 创建异步任务处理监听服务切换
        asyncio.create_task(self._toggle_listening_service_async())

    async def _toggle_listening_service_async(self):
        """异步暂停/继续消息监听服务"""
        try:
            # 导入消息监听器
            from wxauto_mgt.core.message_listener import message_listener

            # 记录当前状态，用于异常时恢复
            original_paused_state = self._is_listening_paused

            if self._is_listening_paused:
                # 如果当前是暂停状态，则恢复监听 - 立即更新按钮状态
                self._update_pause_resume_button_processing("正在恢复...")

                try:
                    await message_listener.resume_listening()
                    self._is_listening_paused = False
                    self._update_pause_resume_button(False)  # False表示未暂停状态
                    logger.info("已恢复消息监听服务")
                    self.status_changed.emit("已恢复消息监听服务", 3000)

                    # 同步消息面板的状态
                    if hasattr(self, 'message_panel'):
                        self.message_panel._is_listening_paused = False
                        if hasattr(self.message_panel, 'pause_resume_btn'):
                            self.message_panel.pause_resume_btn.setText("暂停监听")
                            self.message_panel.pause_resume_btn.setStyleSheet("QPushButton { background-color: #FFA500; }")

                except Exception as e:
                    # 恢复失败，恢复到原始状态
                    self._is_listening_paused = original_paused_state
                    self._update_pause_resume_button(original_paused_state)
                    raise e

            else:
                # 如果当前是运行状态，则暂停监听 - 立即更新按钮状态
                self._update_pause_resume_button_processing("正在暂停...")

                try:
                    await message_listener.pause_listening()
                    self._is_listening_paused = True
                    self._update_pause_resume_button(True)  # True表示暂停状态
                    logger.info("已暂停消息监听服务")
                    self.status_changed.emit("已暂停消息监听服务", 3000)

                    # 同步消息面板的状态
                    if hasattr(self, 'message_panel'):
                        self.message_panel._is_listening_paused = True
                        if hasattr(self.message_panel, 'pause_resume_btn'):
                            self.message_panel.pause_resume_btn.setText("继续监听")
                            self.message_panel.pause_resume_btn.setStyleSheet("QPushButton { background-color: #FF4500; }")

                except Exception as e:
                    # 暂停失败，恢复到原始状态
                    self._is_listening_paused = original_paused_state
                    self._update_pause_resume_button(original_paused_state)
                    raise e

        except Exception as e:
            logger.error(f"切换监听服务状态时出错: {e}")
            QMessageBox.critical(self, "操作失败", f"切换监听服务状态时出错: {str(e)}")

    def _start_api_client(self):
        """启动本地API客户端"""
        try:
            # 获取当前程序所在目录
            if getattr(sys, 'frozen', False):
                # 打包环境 - 使用可执行文件所在目录
                app_dir = os.path.dirname(sys.executable)
            else:
                # 开发环境 - 使用项目根目录
                app_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

            # API客户端可执行文件路径
            api_client_path = os.path.join(app_dir, "wxauto_http_api.exe")

            # 检查文件是否存在
            if not os.path.exists(api_client_path):
                QMessageBox.warning(
                    self,
                    "文件不存在",
                    f"未找到API客户端文件:\n{api_client_path}\n\n请确保wxauto_http_api.exe文件位于程序同目录下。"
                )
                logger.warning(f"API客户端文件不存在: {api_client_path}")
                return

            # 启动API客户端进程
            try:
                # 使用subprocess.Popen启动进程，不等待完成
                process = subprocess.Popen(
                    [api_client_path],
                    cwd=app_dir,
                    creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
                )

                logger.info(f"已启动本地API客户端: {api_client_path} (PID: {process.pid})")
                self.status_changed.emit("本地API客户端已启动", 3000)

                # 显示成功消息
                QMessageBox.information(
                    self,
                    "启动成功",
                    f"本地API客户端已成功启动！\n\n进程ID: {process.pid}\n文件路径: {api_client_path}"
                )

            except subprocess.SubprocessError as e:
                error_msg = f"启动API客户端失败: {str(e)}"
                logger.error(error_msg)
                QMessageBox.critical(self, "启动失败", error_msg)

        except Exception as e:
            error_msg = f"启动本地API客户端时出错: {str(e)}"
            logger.error(error_msg)
            QMessageBox.critical(self, "操作失败", error_msg)

    async def _restart_application(self):
        """重启应用程序"""
        try:
            self.status_changed.emit("正在准备重启程序...", 0)
            logger.info("开始准备重启程序")

            # 保存所有配置
            await self._save_all_configs()

            # 获取当前程序路径和参数
            import sys
            import os
            import time

            # 显示重启消息
            self.status_changed.emit("正在重启程序...", 0)
            logger.info("正在重启程序...")

            # 使用批处理文件方式重启程序
            try:
                # 获取当前可执行文件的完整路径
                if getattr(sys, 'frozen', False):
                    # 打包环境 - 使用可执行文件路径
                    exe_path = sys.executable
                    work_dir = os.path.dirname(exe_path)
                    exe_name = os.path.basename(exe_path)
                    start_cmd = f'"{exe_path}"'
                else:
                    # 开发环境 - 使用Python解释器和脚本路径
                    python_exe = sys.executable
                    script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'main.py')
                    work_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
                    start_cmd = f'"{python_exe}" "{script_path}"'

                # 创建临时目录用于存放批处理文件
                temp_dir = os.environ.get('TEMP', os.path.dirname(os.path.abspath(__file__)))
                batch_file = os.path.join(temp_dir, 'restart_wxauto.bat')

                # 创建调试日志目录 - 使用data/logs路径
                log_dir = os.path.join(work_dir, 'data', 'logs')
                os.makedirs(log_dir, exist_ok=True)
                restart_log_path = os.path.join(log_dir, 'restart_debug.log')

                # 创建批处理文件 - 针对打包环境进行特殊处理
                with open(batch_file, 'w', encoding='gbk') as f:
                    f.write('@echo off\n')
                    f.write('title WxAuto重启程序\n')  # 设置窗口标题

                    # 添加日志记录功能
                    f.write('echo ===== 批处理重启脚本开始执行 ===== > "' + os.path.join(log_dir, 'restart_batch.log') + '"\n')
                    f.write('echo 时间: %date% %time% >> "' + os.path.join(log_dir, 'restart_batch.log') + '"\n')
                    f.write('echo 工作目录: ' + work_dir + ' >> "' + os.path.join(log_dir, 'restart_batch.log') + '"\n')

                    f.write('echo 正在重启 WxAuto管理工具...\n')
                    f.write('echo 正在重启 WxAuto管理工具... >> "' + os.path.join(log_dir, 'restart_batch.log') + '"\n')

                    f.write('cd /d "' + work_dir + '"\n')  # 切换到工作目录
                    f.write('echo 已切换到工作目录: %cd% >> "' + os.path.join(log_dir, 'restart_batch.log') + '"\n')

                    f.write('echo 等待2秒... >> "' + os.path.join(log_dir, 'restart_batch.log') + '"\n')
                    f.write('timeout /t 2 /nobreak > nul\n')  # 等待2秒

                    f.write('echo 启动新进程...\n')
                    f.write('echo 启动新进程... >> "' + os.path.join(log_dir, 'restart_batch.log') + '"\n')

                    if getattr(sys, 'frozen', False):
                        # 打包环境下使用更可靠的方式启动exe - 使用完整路径
                        start_command = f'start "" "{exe_path}"'
                        f.write(f'echo 执行命令: {start_command} >> "' + os.path.join(log_dir, 'restart_batch.log') + '"\n')
                        f.write(f'{start_command}\n')
                        f.write(f'if %errorlevel% neq 0 echo 启动失败，错误码: %errorlevel% >> "' + os.path.join(log_dir, 'restart_batch.log') + '"\n')
                        f.write(f'if %errorlevel% equ 0 echo 启动成功 >> "' + os.path.join(log_dir, 'restart_batch.log') + '"\n')
                        f.write(f'echo 进程已启动 >> "' + os.path.join(log_dir, 'restart_batch.log') + '"\n')

                        # 添加备用启动命令
                        f.write(f'echo 添加备用启动命令... >> "' + os.path.join(log_dir, 'restart_batch.log') + '"\n')
                        f.write(f'timeout /t 1 /nobreak > nul\n')
                        f.write(f'cd /d "{work_dir}"\n')
                        f.write(f'echo 当前目录: %cd% >> "' + os.path.join(log_dir, 'restart_batch.log') + '"\n')
                        f.write(f'echo 尝试使用explorer启动... >> "' + os.path.join(log_dir, 'restart_batch.log') + '"\n')
                        f.write(f'explorer "{exe_path}"\n')

                        # 添加进程检查 - 增加等待时间
                        f.write(f'echo 检查进程是否启动... >> "' + os.path.join(log_dir, 'restart_batch.log') + '"\n')
                        f.write(f'echo 等待5秒... >> "' + os.path.join(log_dir, 'restart_batch.log') + '"\n')
                        f.write(f'timeout /t 5 /nobreak > nul\n')  # 等待5秒

                        # 使用更可靠的方式检查进程
                        f.write(f'echo 使用wmic检查进程... >> "' + os.path.join(log_dir, 'restart_batch.log') + '"\n')
                        f.write(f'wmic process where name="{exe_name}" list brief > "' + os.path.join(log_dir, 'process_check.txt') + '"\n')
                        f.write(f'type "' + os.path.join(log_dir, 'process_check.txt') + '" >> "' + os.path.join(log_dir, 'restart_batch.log') + '"\n')

                        # 使用findstr检查进程
                        f.write(f'tasklist | findstr "{exe_name}" > "' + os.path.join(log_dir, 'tasklist_check.txt') + '"\n')
                        f.write(f'type "' + os.path.join(log_dir, 'tasklist_check.txt') + '" >> "' + os.path.join(log_dir, 'restart_batch.log') + '"\n')

                        # 检查进程是否存在
                        f.write(f'tasklist | findstr "{exe_name}" > nul\n')
                        f.write(f'if %errorlevel% neq 0 (\n')
                        f.write(f'  echo 进程未找到，尝试再次启动... >> "' + os.path.join(log_dir, 'restart_batch.log') + '"\n')
                        f.write(f'  cd /d "{work_dir}"\n')
                        f.write(f'  echo 使用完整路径启动... >> "' + os.path.join(log_dir, 'restart_batch.log') + '"\n')
                        f.write(f'  start "" "{exe_path}"\n')
                        f.write(f') else (\n')
                        f.write(f'  echo 进程已成功启动 >> "' + os.path.join(log_dir, 'restart_batch.log') + '"\n')
                        f.write(f')\n')
                    else:
                        # 开发环境
                        start_command = 'start "" ' + start_cmd
                        f.write(f'echo 执行命令: {start_command} >> "' + os.path.join(log_dir, 'restart_batch.log') + '"\n')
                        f.write(f'{start_command}\n')
                        f.write(f'if %errorlevel% neq 0 echo 启动失败，错误码: %errorlevel% >> "' + os.path.join(log_dir, 'restart_batch.log') + '"\n')
                        f.write(f'if %errorlevel% eq 0 echo 启动成功 >> "' + os.path.join(log_dir, 'restart_batch.log') + '"\n')

                    f.write('echo 启动完成，窗口将在3秒后自动关闭\n')
                    f.write('echo 启动完成，窗口将在3秒后自动关闭 >> "' + os.path.join(log_dir, 'restart_batch.log') + '"\n')

                    f.write('echo 等待3秒进行最终检查... >> "' + os.path.join(log_dir, 'restart_batch.log') + '"\n')
                    f.write('timeout /t 3 /nobreak > nul\n')  # 等待10秒
                    f.write('echo 批处理脚本执行完毕 >> "' + os.path.join(log_dir, 'restart_batch.log') + '"\n')

                    # 最后再次检查进程 - 使用多种方式
                    f.write(f'echo 最终检查进程... >> "' + os.path.join(log_dir, 'restart_batch.log') + '"\n')

                    # 使用wmic检查进程
                    f.write(f'wmic process where name="{exe_name}" list brief > "' + os.path.join(log_dir, 'final_check.txt') + '"\n')
                    f.write(f'type "' + os.path.join(log_dir, 'final_check.txt') + '" >> "' + os.path.join(log_dir, 'restart_batch.log') + '"\n')

                    # 使用tasklist检查进程
                    f.write(f'tasklist | findstr "{exe_name}" >> "' + os.path.join(log_dir, 'restart_batch.log') + '"\n')

                    # 检查进程是否存在
                    f.write(f'tasklist | findstr "{exe_name}" > nul\n')
                    f.write(f'if %errorlevel% neq 0 (\n')
                    f.write(f'  echo 最终检查：进程未找到，最后一次尝试启动... >> "' + os.path.join(log_dir, 'restart_batch.log') + '"\n')
                    f.write(f'  cd /d "{work_dir}"\n')
                    f.write(f'  echo 使用ShellExecute方式启动... >> "' + os.path.join(log_dir, 'restart_batch.log') + '"\n')
                    f.write(f'  explorer "{exe_path}"\n')
                    f.write(f'  echo 使用cmd /c start方式启动... >> "' + os.path.join(log_dir, 'restart_batch.log') + '"\n')
                    f.write(f'  cmd /c start "" "{exe_path}"\n')
                    f.write(f') else (\n')
                    f.write(f'  echo 最终检查：进程已成功运行 >> "' + os.path.join(log_dir, 'restart_batch.log') + '"\n')
                    f.write(f')\n')

                    # 使用更可靠的方式关闭批处理窗口和当前命令行窗口
                    f.write('echo 批处理窗口即将关闭 >> "' + os.path.join(log_dir, 'restart_batch.log') + '"\n')
                    f.write('echo 重启过程完成 >> "' + os.path.join(log_dir, 'restart_batch.log') + '"\n')
                    f.write('timeout /t 1 /nobreak > nul\n')
                    # 使用多种方式确保批处理窗口关闭
                    f.write('exit\n')

                logger.info(f"创建重启批处理文件: {batch_file}")

                # 记录批处理文件内容到日志
                with open(restart_log_path, 'a', encoding='utf-8') as log_file:
                    log_file.write(f"批处理文件路径: {batch_file}\n")
                    log_file.write("批处理文件内容:\n")
                    with open(batch_file, 'r', encoding='gbk') as bat_file:
                        log_file.write(bat_file.read())
                    log_file.write("\n")

                # 使用更可靠的方式启动批处理文件
                if getattr(sys, 'frozen', False):
                    # 打包环境下使用更可靠的方式启动批处理
                    # 不使用/min参数，让批处理窗口可见，便于调试
                    start_cmd = f'cmd /c start "" "{batch_file}"'
                    with open(restart_log_path, 'a', encoding='utf-8') as log_file:
                        log_file.write(f"启动命令: {start_cmd}\n")

                    # 使用subprocess模块启动进程，更可靠
                    try:
                        import subprocess
                        with open(restart_log_path, 'a', encoding='utf-8') as log_file:
                            log_file.write(f"使用subprocess启动批处理文件\n")

                        # 使用subprocess.Popen启动进程
                        subprocess.Popen(start_cmd, shell=True)

                        with open(restart_log_path, 'a', encoding='utf-8') as log_file:
                            log_file.write(f"subprocess.Popen启动成功\n")
                    except Exception as sub_e:
                        # 如果subprocess失败，回退到os.system
                        with open(restart_log_path, 'a', encoding='utf-8') as log_file:
                            log_file.write(f"subprocess启动失败: {sub_e}，回退到os.system\n")
                        os.system(start_cmd)
                else:
                    # 开发环境
                    start_cmd = f'start "" "{batch_file}"'
                    with open(restart_log_path, 'a', encoding='utf-8') as log_file:
                        log_file.write(f"启动命令: {start_cmd}\n")
                    os.system(start_cmd)

                logger.info("批处理文件已启动，程序将在2秒后重启")
                with open(restart_log_path, 'a', encoding='utf-8') as log_file:
                    log_file.write("批处理文件已启动，程序将在2秒后重启\n")

            except Exception as e:
                error_msg = f"创建或启动批处理文件失败: {e}"
                logger.error(error_msg)

                # 记录错误到日志文件
                try:
                    with open(restart_log_path, 'a', encoding='utf-8') as log_file:
                        log_file.write(f"错误: {error_msg}\n")
                        log_file.write(f"异常类型: {type(e).__name__}\n")
                        import traceback
                        log_file.write(f"异常堆栈:\n{traceback.format_exc()}\n")
                        log_file.write("尝试备用启动方案...\n")
                except Exception as log_e:
                    logger.error(f"写入日志文件失败: {log_e}")

                # 尝试直接启动
                try:
                    logger.info("尝试直接启动新进程...")
                    if getattr(sys, 'frozen', False):
                        # 打包环境 - 使用更可靠的方式启动exe
                        exe_dir = os.path.dirname(sys.executable)
                        exe_name = os.path.basename(sys.executable)

                        # 创建一个简单的启动器批处理文件
                        launcher_bat = os.path.join(temp_dir, 'launch_wxauto.bat')

                        # 记录到日志
                        with open(restart_log_path, 'a', encoding='utf-8') as log_file:
                            log_file.write(f"创建备用启动器批处理文件: {launcher_bat}\n")

                        with open(launcher_bat, 'w', encoding='gbk') as f:
                            f.write('@echo off\n')
                            f.write('title WxAuto备用启动器\n')
                            f.write(f'echo ===== 备用启动器开始执行 ===== > "{os.path.join(log_dir, "backup_launcher.log")}"\n')
                            f.write(f'echo 时间: %date% %time% >> "{os.path.join(log_dir, "backup_launcher.log")}"\n')
                            f.write(f'cd /d "{exe_dir}"\n')
                            f.write(f'echo 当前目录: %cd% >> "{os.path.join(log_dir, "backup_launcher.log")}"\n')

                            # 先检查进程是否已经在运行
                            f.write(f'echo 检查进程是否已在运行... >> "{os.path.join(log_dir, "backup_launcher.log")}"\n')
                            f.write(f'tasklist | findstr "{exe_name}" > nul\n')
                            f.write(f'if %errorlevel% equ 0 (\n')
                            f.write(f'  echo 进程已在运行，无需再次启动 >> "{os.path.join(log_dir, "backup_launcher.log")}"\n')
                            f.write(f') else (\n')
                            f.write(f'  echo 进程未运行，开始启动... >> "{os.path.join(log_dir, "backup_launcher.log")}"\n')
                            f.write(f'  echo 启动命令: start "" "{exe_name}" >> "{os.path.join(log_dir, "backup_launcher.log")}"\n')
                            f.write(f'  start "" "{exe_name}"\n')
                            f.write(f'  if %errorlevel% neq 0 echo 启动失败，错误码: %errorlevel% >> "{os.path.join(log_dir, "backup_launcher.log")}"\n')
                            f.write(f'  if %errorlevel% equ 0 echo 启动成功 >> "{os.path.join(log_dir, "backup_launcher.log")}"\n')
                            f.write(f')\n')

                            # 等待并再次检查
                            f.write(f'echo 等待5秒... >> "{os.path.join(log_dir, "backup_launcher.log")}"\n')
                            f.write(f'timeout /t 5 /nobreak > nul\n')
                            f.write(f'echo 再次检查进程... >> "{os.path.join(log_dir, "backup_launcher.log")}"\n')
                            f.write(f'tasklist | findstr "{exe_name}" > nul\n')
                            f.write(f'if %errorlevel% neq 0 (\n')
                            f.write(f'  echo 进程未找到，尝试使用完整路径启动... >> "{os.path.join(log_dir, "backup_launcher.log")}"\n')
                            f.write(f'  start "" "{exe_path}"\n')
                            f.write(f') else (\n')
                            f.write(f'  echo 进程已成功运行 >> "{os.path.join(log_dir, "backup_launcher.log")}"\n')
                            f.write(f')\n')

                            f.write(f'echo 备用启动器执行完毕 >> "{os.path.join(log_dir, "backup_launcher.log")}"\n')
                            f.write(f'echo 窗口将在3秒后关闭\n')
                            f.write(f'timeout /t 1 /nobreak > nul\n')
                            f.write('exit\n')

                        # 记录批处理文件内容到日志
                        with open(restart_log_path, 'a', encoding='utf-8') as log_file:
                            log_file.write("备用启动器批处理文件内容:\n")
                            with open(launcher_bat, 'r', encoding='gbk') as bat_file:
                                log_file.write(bat_file.read())
                            log_file.write("\n")

                        # 使用cmd /c启动批处理文件
                        start_cmd = f'cmd /c start /min "" "{launcher_bat}"'
                        with open(restart_log_path, 'a', encoding='utf-8') as log_file:
                            log_file.write(f"启动命令: {start_cmd}\n")
                        os.system(start_cmd)

                        logger.info(f"已通过启动器批处理文件启动: {launcher_bat}")
                    else:
                        # 开发环境 - 使用os.system启动Python脚本
                        start_cmd = f'start "" "{python_exe}" "{script_path}"'
                        with open(restart_log_path, 'a', encoding='utf-8') as log_file:
                            log_file.write(f"开发环境启动命令: {start_cmd}\n")
                        os.system(start_cmd)

                    logger.info("已直接启动新进程")
                    with open(restart_log_path, 'a', encoding='utf-8') as log_file:
                        log_file.write("已直接启动新进程\n")
                except Exception as direct_e:
                    error_msg = f"直接启动新进程失败: {direct_e}"
                    logger.error(error_msg)

                    # 记录错误到日志文件
                    try:
                        with open(restart_log_path, 'a', encoding='utf-8') as log_file:
                            log_file.write(f"错误: {error_msg}\n")
                            log_file.write(f"异常类型: {type(direct_e).__name__}\n")
                            import traceback
                            log_file.write(f"异常堆栈:\n{traceback.format_exc()}\n")
                            log_file.write("尝试最后的备用启动方案...\n")
                    except Exception as log_e:
                        logger.error(f"写入日志文件失败: {log_e}")

                    # 最后的尝试 - 使用explorer启动
                    try:
                        logger.info("尝试使用explorer启动...")
                        if getattr(sys, 'frozen', False):
                            # 记录到日志
                            with open(restart_log_path, 'a', encoding='utf-8') as log_file:
                                log_file.write(f"尝试使用explorer启动: explorer \"{exe_path}\"\n")

                            os.system(f'explorer "{exe_path}"')
                        else:
                            # 创建一个临时批处理文件
                            last_bat = os.path.join(temp_dir, 'last_resort.bat')

                            # 记录到日志
                            with open(restart_log_path, 'a', encoding='utf-8') as log_file:
                                log_file.write(f"创建最终备用启动器批处理文件: {last_bat}\n")

                            with open(last_bat, 'w', encoding='gbk') as f:
                                f.write('@echo off\n')
                                f.write(f'echo ===== 最终备用启动器开始执行 ===== > "{os.path.join(log_dir, "last_resort.log")}"\n')
                                f.write(f'echo 时间: %date% %time% >> "{os.path.join(log_dir, "last_resort.log")}"\n')
                                f.write(f'cd /d "{work_dir}"\n')
                                f.write(f'echo 当前目录: %cd% >> "{os.path.join(log_dir, "last_resort.log")}"\n')
                                f.write(f'echo 启动命令: "{python_exe}" "{script_path}" >> "{os.path.join(log_dir, "last_resort.log")}"\n')
                                f.write(f'"{python_exe}" "{script_path}"\n')
                                f.write(f'if %errorlevel% neq 0 echo 启动失败，错误码: %errorlevel% >> "{os.path.join(log_dir, "last_resort.log")}"\n')
                                f.write(f'if %errorlevel% eq 0 echo 启动成功 >> "{os.path.join(log_dir, "last_resort.log")}"\n')
                                f.write(f'echo 最终备用启动器执行完毕 >> "{os.path.join(log_dir, "last_resort.log")}"\n')
                                f.write('del "%~f0"\n')

                            # 记录批处理文件内容到日志
                            with open(restart_log_path, 'a', encoding='utf-8') as log_file:
                                log_file.write("最终备用启动器批处理文件内容:\n")
                                with open(last_bat, 'r', encoding='gbk') as bat_file:
                                    log_file.write(bat_file.read())
                                log_file.write("\n")
                                log_file.write(f"启动命令: explorer \"{last_bat}\"\n")

                            os.system(f'explorer "{last_bat}"')

                        logger.info("已使用explorer启动新进程")
                        with open(restart_log_path, 'a', encoding='utf-8') as log_file:
                            log_file.write("已使用explorer启动新进程\n")
                    except Exception as last_e:
                        error_msg = f"所有重启方法都失败: {last_e}"
                        logger.error(error_msg)

                        # 记录错误到日志文件
                        try:
                            with open(restart_log_path, 'a', encoding='utf-8') as log_file:
                                log_file.write(f"错误: {error_msg}\n")
                                log_file.write(f"异常类型: {type(last_e).__name__}\n")
                                import traceback
                                log_file.write(f"异常堆栈:\n{traceback.format_exc()}\n")
                                log_file.write("所有重启方法都失败\n")
                        except Exception as log_e:
                            logger.error(f"写入日志文件失败: {log_e}")

                        raise

            # 等待一小段时间确保脚本已经启动
            time.sleep(1)

            # 关闭当前程序 - 直接退出，让批处理文件启动新进程
            logger.info("正在彻底关闭当前程序...")

            # 记录到日志文件
            try:
                with open(restart_log_path, 'a', encoding='utf-8') as log_file:
                    log_file.write("正在彻底关闭当前程序...\n")
                    log_file.write(f"退出时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    log_file.write("不尝试停止服务，直接退出，避免事件循环问题\n")
                    log_file.write(f"打包环境: {getattr(sys, 'frozen', False)}\n")
                    log_file.write("===== 重启操作结束 =====\n\n")
            except Exception as log_e:
                logger.error(f"写入日志文件失败: {log_e}")

            # 不尝试停止服务，直接退出
            # 这样可以避免事件循环问题，新进程会重新初始化所有服务

            # 使用sys.exit退出，确保触发清理代码
            logger.info("程序即将退出...")

            # 在打包环境下，使用特殊方式退出
            if getattr(sys, 'frozen', False):
                # 使用os._exit强制退出，确保不会有任何阻塞
                import os
                os._exit(0)
            else:
                # 开发环境下使用sys.exit，这样可以触发清理代码
                import sys
                sys.exit(0)

        except Exception as e:
            error_msg = f"重启程序失败: {str(e)}"
            self.status_changed.emit(error_msg, 3000)
            logger.error(error_msg)
            import traceback
            logger.error(f"异常堆栈: {traceback.format_exc()}")

            # 记录错误到日志文件
            try:
                # 确保日志目录存在 - 使用data/logs路径
                log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', 'logs')
                os.makedirs(log_dir, exist_ok=True)
                restart_log_path = os.path.join(log_dir, 'restart_debug.log')

                with open(restart_log_path, 'a', encoding='utf-8') as log_file:
                    log_file.write(f"\n\n===== 重启操作失败: {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n")
                    log_file.write(f"错误: {error_msg}\n")
                    log_file.write(f"异常类型: {type(e).__name__}\n")
                    log_file.write(f"异常堆栈:\n{traceback.format_exc()}\n")
                    log_file.write("===== 重启操作结束(失败) =====\n\n")
            except Exception as log_e:
                logger.error(f"写入日志文件失败: {log_e}")

    async def _save_all_configs(self):
        """保存所有配置"""
        try:
            logger.info("保存所有配置...")

            # 保存Web服务配置 - 使用正确的配置管理方式
            if hasattr(self, 'web_service_panel'):
                # 如果有Web服务面板，让它处理配置保存
                await self.web_service_panel._save_config_async(
                    self.web_service_panel.port_spinbox.value(),
                    self.web_service_panel.host_input.text(),
                    self.web_service_panel.auto_start_checkbox.isChecked(),
                    None  # 不更新密码
                )
            else:
                # 如果没有Web服务面板，使用Web服务配置类
                from wxauto_mgt.web.config import get_web_service_config
                web_config = get_web_service_config()

                # 获取现有配置并只更新必要的字段
                existing_config = await config_store.get_config('system', 'web_service', {})
                if hasattr(self, 'port_spinbox'):
                    port = self.port_spinbox.value()
                    await web_config.save_config(port=port)

            # 保存其他配置...
            # 这里可以添加其他需要保存的配置

            logger.info("所有配置已保存")
            return True
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            return False

    async def _reload_config_async(self):
        """异步重载配置（不重启程序的版本，已不使用）"""
        try:
            self.status_changed.emit("正在重载配置...", 0)
            logger.info("开始重载配置")

            # 重新初始化服务平台管理器
            logger.info("重新初始化服务平台管理器")
            await platform_manager.initialize()

            # 重新初始化投递规则管理器
            logger.info("重新初始化投递规则管理器")
            await rule_manager.initialize()

            # 重新加载消息监听器的监听对象
            logger.info("重新加载消息监听对象")
            from wxauto_mgt.core.message_listener import message_listener
            # 清空并强制从数据库重新加载
            message_listener.listeners = {}
            await message_listener._load_listeners_from_db()

            # 刷新UI上的实例列表
            if hasattr(self, 'instance_panel') and hasattr(self.instance_panel, 'instance_list'):
                self.instance_panel.instance_list.refresh_instances()

            # 刷新实例状态
            if hasattr(self, 'instance_panel'):
                self.instance_panel.refresh_status()

            # 刷新消息监听面板
            if hasattr(self, 'message_panel'):
                await self.message_panel.refresh_listeners(force_reload=True, silent=False)

            self.status_changed.emit("配置重载完成", 3000)
            logger.info("配置重载完成")

        except Exception as e:
            error_msg = f"重载配置失败: {str(e)}"
            self.status_changed.emit(error_msg, 3000)
            logger.error(error_msg)
            import traceback
            logger.error(f"异常堆栈: {traceback.format_exc()}")