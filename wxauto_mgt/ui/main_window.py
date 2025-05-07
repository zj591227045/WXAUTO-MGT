"""
主窗口模块

实现应用程序的主窗口，包含菜单栏、状态栏和基于选项卡的界面布局。
提供实例管理、消息监听和状态监控等功能的访问入口。
"""

import os
import asyncio
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
from wxauto_mgt.web import start_web_service, stop_web_service, is_web_service_running, get_web_service_config, set_web_service_config
from wxauto_mgt.core.service_platform_manager import platform_manager, rule_manager

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
            asyncio.create_task(self._delayed_config_save())

        QTimer.singleShot(2000, start_delayed_save)

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
        # 状态监控标签页已隐藏
        # from wxauto_mgt.ui.components.status_panel import StatusMonitorPanel

        # 实例管理选项卡 - 使用新的实例管理面板
        self.instance_panel = InstanceManagerPanel(self)
        self.tab_widget.addTab(self.instance_panel, "实例管理")

        # 消息监听选项卡
        self.message_panel = MessageListenerPanel(self)
        self.tab_widget.addTab(self.message_panel, "消息监听")

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
        # 导入设置对话框
        from wxauto_mgt.ui.components.dialogs import SettingsDialog

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

            # 如果Web服务正在运行，停止它
            if is_web_service_running():
                try:
                    # 创建一个事件循环来运行异步函数
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(stop_web_service())
                    loop.close()
                    logger.info("应用程序关闭时停止Web服务")
                except Exception as e:
                    logger.error(f"应用程序关闭时停止Web服务失败: {e}")

            # 执行清理操作
            event.accept()
        else:
            event.ignore()

    async def _delayed_config_save(self):
        """延迟执行的配置保存任务"""
        try:
            # 从配置存储中获取所有实例
            instances = await config_store.get_config('system', 'instances', [])

            if instances:
                logger.info(f"启动时强制保存 {len(instances)} 个实例配置")

                # 刷新UI上的实例列表
                if hasattr(self, 'instance_panel'):
                    self.instance_panel.refresh_instances()

            # 加载Web服务配置
            web_config = await config_store.get_config('system', 'web_service', {})
            if web_config:
                logger.info(f"加载Web服务配置: {web_config}")

                # 更新Web服务配置
                config = get_web_service_config()

                # 设置端口号
                if 'port' in web_config:
                    config['port'] = web_config['port']
                    self.port_spinbox.setValue(web_config['port'])

                # 更新Web服务配置
                set_web_service_config(config)
        except Exception as e:
            logger.error(f"启动时保存配置失败: {str(e)}")

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

        # 端口号标签和输入框
        port_label = QLabel("端口:")
        group_layout.addWidget(port_label)

        self.port_spinbox = QSpinBox()
        self.port_spinbox.setRange(1024, 65535)
        self.port_spinbox.setValue(8443)  # 默认端口
        self.port_spinbox.setFixedWidth(80)
        self.port_spinbox.setToolTip("Web服务端口号 (1024-65535)")
        group_layout.addWidget(self.port_spinbox)

        # 启动/停止按钮
        self.web_service_btn = QPushButton("启动服务")
        self.web_service_btn.setStyleSheet("""
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
        self.web_service_btn.clicked.connect(self._toggle_web_service)
        group_layout.addWidget(self.web_service_btn)

        # 状态标签
        self.web_service_status = QLabel("未运行")
        self.web_service_status.setStyleSheet("color: #f5222d;")  # 红色表示未运行
        group_layout.addWidget(self.web_service_status)

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

        # 添加到主布局
        web_service_layout.addWidget(web_service_group)

        # 添加重载配置按钮
        self.reload_config_btn = QPushButton("重载配置")
        self.reload_config_btn.setStyleSheet("""
            QPushButton {
                background-color: #fa8c16;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #ffa940;
            }
        """)
        self.reload_config_btn.clicked.connect(self._reload_config)
        web_service_layout.addWidget(self.reload_config_btn)

        # 将Web服务控制区域添加到工具栏
        self.toolbar.addWidget(web_service_container)

        # 初始化Web服务状态
        self._update_web_service_status()

        # 从配置中加载端口号
        self._load_web_service_config()

    def _update_web_service_status(self):
        """更新Web服务状态显示"""
        running = is_web_service_running()

        if running:
            self.web_service_status.setText("运行中")
            self.web_service_status.setStyleSheet("color: #52c41a;")  # 绿色表示运行中
            self.web_service_btn.setText("停止服务")
            self.web_service_btn.setStyleSheet("""
                QPushButton {
                    background-color: #f5222d;
                    color: white;
                    border: none;
                    padding: 6px 12px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #ff4d4f;
                }
            """)
            self.port_spinbox.setEnabled(False)
            self.open_web_btn.setEnabled(True)  # 启用打开Web界面按钮
        else:
            self.web_service_status.setText("未运行")
            self.web_service_status.setStyleSheet("color: #f5222d;")  # 红色表示未运行
            self.web_service_btn.setText("启动服务")
            self.web_service_btn.setStyleSheet("""
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
            self.port_spinbox.setEnabled(True)
            self.open_web_btn.setEnabled(False)  # 禁用打开Web界面按钮

    def _open_web_interface(self):
        """打开Web管理界面"""
        if not is_web_service_running():
            self.status_changed.emit("Web服务未运行，无法打开界面", 3000)
            return

        try:
            # 获取当前配置
            config = get_web_service_config()
            port = config.get('port', 8443)

            # 构建URL
            url = f"http://localhost:{port}"

            # 使用系统默认浏览器打开URL
            import webbrowser
            webbrowser.open(url)

            self.status_changed.emit(f"已在浏览器中打开Web管理界面: {url}", 3000)
        except Exception as e:
            self.status_changed.emit(f"打开Web界面失败: {str(e)}", 3000)
            logger.error(f"打开Web界面失败: {e}")

    def _load_web_service_config(self):
        """从配置中加载Web服务配置"""
        try:
            # 从配置存储中获取Web服务配置
            web_config = config_store.get_config_sync('system', 'web_service', {})

            # 如果配置存在，更新Web服务配置
            if web_config:
                # 更新Web服务配置
                config = get_web_service_config()

                # 设置端口号
                if 'port' in web_config:
                    config['port'] = web_config['port']
                    self.port_spinbox.setValue(web_config['port'])

                # 更新Web服务配置
                set_web_service_config(config)
            else:
                # 使用默认配置
                config = get_web_service_config()
                self.port_spinbox.setValue(config['port'])
        except Exception as e:
            logger.error(f"加载Web服务配置失败: {e}")

    def _toggle_web_service(self):
        """切换Web服务状态"""
        running = is_web_service_running()

        if running:
            # 停止Web服务
            asyncio.create_task(self._stop_web_service())
        else:
            # 启动Web服务
            port = self.port_spinbox.value()
            asyncio.create_task(self._start_web_service(port))

    async def _start_web_service(self, port):
        """
        启动Web服务

        Args:
            port: 端口号
        """
        try:
            # 确保端口是整数
            if isinstance(port, str):
                try:
                    port = int(port)
                except ValueError:
                    self.status_changed.emit(f"无效的端口号: {port}", 3000)
                    logger.error(f"无效的端口号: {port}")
                    return

            # 更新配置
            config = get_web_service_config()
            config['port'] = port
            set_web_service_config(config)

            # 保存配置到配置存储
            await config_store.set_config('system', 'web_service', {'port': port})

            # 启动Web服务
            try:
                # 确保配置中不包含debug参数
                if 'debug' in config:
                    del config['debug']

                # 检查依赖项
                try:
                    import fastapi
                    import uvicorn
                    import jose
                    import passlib
                except ImportError as e:
                    error_msg = f"缺少必要的依赖项: {e}\n请安装: pip install fastapi uvicorn python-jose[cryptography] passlib[bcrypt]"
                    self.status_changed.emit(f"启动Web服务失败: 缺少依赖项", 3000)
                    logger.error(error_msg)
                    return

                # 检查端口是否被占用
                import socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                try:
                    sock.bind(('127.0.0.1', port))
                    sock.close()
                except socket.error:
                    error_msg = f"端口 {port} 已被占用，请尝试其他端口"
                    self.status_changed.emit(error_msg, 3000)
                    logger.error(error_msg)
                    return

                success = await start_web_service(config)

                if success:
                    self.status_changed.emit(f"Web服务已启动，端口: {port}", 3000)
                    logger.info(f"Web服务已启动，端口: {port}")
                else:
                    self.status_changed.emit("启动Web服务失败", 3000)
                    logger.error("启动Web服务失败")
            except Exception as e:
                import traceback
                error_msg = f"启动Web服务时出错: {str(e)}\n{traceback.format_exc()}"
                self.status_changed.emit(f"启动Web服务失败: {str(e)}", 3000)
                logger.error(error_msg)

            # 更新状态显示
            self._update_web_service_status()
        except Exception as e:
            import traceback
            error_msg = f"启动Web服务时出错: {str(e)}\n{traceback.format_exc()}"
            self.status_changed.emit(f"启动Web服务时出错: {str(e)}", 3000)
            logger.error(error_msg)

    async def _stop_web_service(self):
        """停止Web服务"""
        try:
            # 停止Web服务
            success = await stop_web_service()

            if success:
                self.status_changed.emit("Web服务已停止", 3000)
                logger.info("Web服务已停止")
            else:
                self.status_changed.emit("停止Web服务失败", 3000)
                logger.error("停止Web服务失败")

            # 更新状态显示
            self._update_web_service_status()
        except Exception as e:
            self.status_changed.emit(f"停止Web服务时出错: {str(e)}", 3000)
            logger.error(f"停止Web服务时出错: {e}")

    def _reload_config(self):
        """重载配置"""
        # 创建异步任务重载配置
        asyncio.create_task(self._reload_config_async())

    async def _reload_config_async(self):
        """异步重载配置"""
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