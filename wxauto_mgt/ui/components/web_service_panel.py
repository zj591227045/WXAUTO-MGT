"""
Web服务管理面板

提供Web服务管理功能，包括启动/停止Web服务、查看Web服务状态等。
"""

import asyncio
import webbrowser
from PySide6.QtCore import Qt, Signal, Slot, QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSpinBox,
    QGroupBox, QTextEdit, QSplitter, QCheckBox, QFormLayout, QLineEdit,
    QMessageBox
)

from wxauto_mgt.utils.logging import logger
from wxauto_mgt.web import start_web_service, stop_web_service, is_web_service_running, get_web_service_config, set_web_service_config
from wxauto_mgt.data.config_store import config_store

class WebServicePanel(QWidget):
    """Web服务管理面板"""

    # 定义信号
    status_changed = Signal(str, int)  # 状态消息, 超时时间

    def __init__(self, parent=None):
        """初始化Web服务管理面板"""
        super().__init__(parent)

        # 初始化UI
        self._init_ui()

        # 更新Web服务状态
        self._update_web_service_status()

        # 从配置中加载端口号
        self._load_web_service_config()

    def _init_ui(self):
        """初始化UI组件"""
        # 创建主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # 创建Web服务控制组
        control_group = QGroupBox("Web服务控制")
        control_layout = QVBoxLayout(control_group)

        # 创建Web服务配置表单
        form_layout = QFormLayout()
        form_layout.setContentsMargins(0, 10, 0, 10)
        form_layout.setSpacing(10)

        # 端口号
        port_layout = QHBoxLayout()
        port_label = QLabel("端口号:")
        self.port_spinbox = QSpinBox()
        self.port_spinbox.setRange(1024, 65535)
        self.port_spinbox.setValue(8080)  # 默认端口
        self.port_spinbox.setFixedWidth(100)
        self.port_spinbox.setToolTip("Web服务端口号 (1024-65535)")
        port_layout.addWidget(self.port_spinbox)
        port_layout.addStretch()
        form_layout.addRow(port_label, port_layout)

        # 主机地址
        host_layout = QHBoxLayout()
        host_label = QLabel("主机地址:")
        self.host_input = QLineEdit("0.0.0.0")
        self.host_input.setToolTip("Web服务主机地址，默认为0.0.0.0（监听所有网络接口）")
        self.host_input.setFixedWidth(200)
        host_layout.addWidget(self.host_input)
        host_layout.addStretch()
        form_layout.addRow(host_label, host_layout)

        # 访问密码
        password_layout = QHBoxLayout()
        password_label = QLabel("访问密码:")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setToolTip("Web服务访问密码，留空表示不需要密码验证")
        self.password_input.setFixedWidth(200)
        self.password_input.setPlaceholderText("留空表示不需要密码")
        password_layout.addWidget(self.password_input)
        password_layout.addStretch()
        form_layout.addRow(password_label, password_layout)

        # 自动启动
        auto_start_layout = QHBoxLayout()
        self.auto_start_checkbox = QCheckBox("程序启动时自动启动Web服务")
        # 不在这里硬编码设置，等待配置加载后更新
        auto_start_layout.addWidget(self.auto_start_checkbox)
        auto_start_layout.addStretch()
        form_layout.addRow("", auto_start_layout)

        control_layout.addLayout(form_layout)

        # 创建按钮组
        buttons_layout = QHBoxLayout()
        buttons_layout.setContentsMargins(0, 10, 0, 10)
        buttons_layout.setSpacing(10)

        # 启动/停止按钮
        self.web_service_btn = QPushButton("启动服务")
        self.web_service_btn.setStyleSheet("""
            QPushButton {
                background-color: #1890ff;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #40a9ff;
            }
        """)
        self.web_service_btn.clicked.connect(self._toggle_web_service)
        buttons_layout.addWidget(self.web_service_btn)

        # 打开Web界面按钮
        self.open_web_btn = QPushButton("打开Web界面")
        self.open_web_btn.setStyleSheet("""
            QPushButton {
                background-color: #52c41a;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
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
        buttons_layout.addWidget(self.open_web_btn)

        # 保存配置按钮
        self.save_config_btn = QPushButton("保存配置")
        self.save_config_btn.setStyleSheet("""
            QPushButton {
                background-color: #fa8c16;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ffa940;
            }
        """)
        self.save_config_btn.clicked.connect(self._save_config)
        buttons_layout.addWidget(self.save_config_btn)

        buttons_layout.addStretch()

        control_layout.addLayout(buttons_layout)

        # 状态显示
        status_layout = QHBoxLayout()
        status_layout.setContentsMargins(0, 10, 0, 10)
        status_layout.setSpacing(10)

        status_label = QLabel("服务状态:")
        status_label.setStyleSheet("font-weight: bold;")
        status_layout.addWidget(status_label)

        self.web_service_status = QLabel("未运行")
        self.web_service_status.setStyleSheet("color: #f5222d; font-weight: bold;")  # 红色表示未运行
        status_layout.addWidget(self.web_service_status)

        status_layout.addStretch()

        control_layout.addLayout(status_layout)

        main_layout.addWidget(control_group)

        # 创建日志显示区域
        log_group = QGroupBox("Web服务日志")
        log_layout = QVBoxLayout(log_group)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #f8f9fa;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                font-family: Consolas, Monaco, monospace;
                font-size: 12px;
            }
        """)
        log_layout.addWidget(self.log_text)

        # 清空日志按钮
        clear_log_btn = QPushButton("清空日志")
        clear_log_btn.clicked.connect(self.log_text.clear)
        log_layout.addWidget(clear_log_btn)

        main_layout.addWidget(log_group)

        # 设置比例
        main_layout.setStretch(0, 1)  # 控制组
        main_layout.setStretch(1, 3)  # 日志组

        # 添加初始日志
        self.add_log("Web服务管理面板已初始化")



    def add_log(self, message):
        """添加日志"""
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}"

        # 添加到日志显示
        self.log_text.append(log_entry)

        # 滚动到底部
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )

    def _update_web_service_status(self):
        """更新Web服务状态显示"""
        running = is_web_service_running()

        if running:
            self.web_service_status.setText("运行中")
            self.web_service_status.setStyleSheet("color: #52c41a; font-weight: bold;")  # 绿色表示运行中
            self.web_service_btn.setText("停止服务")
            self.web_service_btn.setStyleSheet("""
                QPushButton {
                    background-color: #f5222d;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #ff4d4f;
                }
            """)
            self.port_spinbox.setEnabled(False)
            self.host_input.setEnabled(False)
            self.open_web_btn.setEnabled(True)  # 启用打开Web界面按钮
        else:
            self.web_service_status.setText("未运行")
            self.web_service_status.setStyleSheet("color: #f5222d; font-weight: bold;")  # 红色表示未运行
            self.web_service_btn.setText("启动服务")
            self.web_service_btn.setStyleSheet("""
                QPushButton {
                    background-color: #1890ff;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #40a9ff;
                }
            """)
            self.port_spinbox.setEnabled(True)
            self.host_input.setEnabled(True)
            self.open_web_btn.setEnabled(False)  # 禁用打开Web界面按钮

    def _load_web_service_config(self):
        """从配置中加载Web服务配置"""
        try:
            # 从配置存储中获取Web服务配置
            web_config = config_store.get_config_sync('system', 'web_service', {})

            # 如果配置存在，更新Web服务配置
            if web_config and isinstance(web_config, dict) and web_config:
                # 更新Web服务配置
                config = get_web_service_config()

                # 设置端口号
                if 'port' in web_config and isinstance(web_config['port'], int):
                    config['port'] = web_config['port']
                    self.port_spinbox.setValue(web_config['port'])
                    logger.debug(f"已设置端口号: {web_config['port']}")

                # 设置主机地址
                if 'host' in web_config and web_config['host']:
                    config['host'] = web_config['host']
                    self.host_input.setText(web_config['host'])
                    logger.debug(f"已设置主机地址: {web_config['host']}")

                # 设置自动启动
                if 'auto_start' in web_config:
                    self.auto_start_checkbox.setChecked(bool(web_config['auto_start']))
                    logger.debug(f"已设置自动启动: {web_config['auto_start']}")

                # 设置密码（不显示实际密码，只显示是否已设置）
                if 'password' in web_config and web_config['password']:
                    self.password_input.setPlaceholderText("已设置密码（输入新密码可修改）")
                    logger.debug("已检测到设置的密码")
                else:
                    self.password_input.setPlaceholderText("留空表示不需要密码")

                # 更新Web服务配置
                set_web_service_config(config)

                self.add_log(f"已加载Web服务配置: host={web_config.get('host', 'N/A')}, port={web_config.get('port', 'N/A')}, auto_start={web_config.get('auto_start', 'N/A')}")
                logger.info(f"Web服务面板已加载配置: {web_config}")
            else:
                # 同步加载失败，使用Web服务配置类的默认值
                logger.warning("同步配置加载失败或配置为空，将在延迟刷新时更新")
                config = get_web_service_config()
                self.port_spinbox.setValue(config['port'])
                self.host_input.setText(config['host'])
                # 对于auto_start，使用配置类的值而不是硬编码False
                self.auto_start_checkbox.setChecked(config['auto_start'])
                self.add_log("等待配置刷新...")
                logger.info("Web服务面板等待延迟配置刷新")
        except Exception as e:
            self.add_log(f"加载Web服务配置失败: {e}")
            logger.error(f"加载Web服务配置失败: {e}")
            # 发生异常时，至少使用Web服务配置类的默认值
            try:
                config = get_web_service_config()
                self.port_spinbox.setValue(config['port'])
                self.host_input.setText(config['host'])
                self.auto_start_checkbox.setChecked(config['auto_start'])
                logger.info("使用Web服务配置类的默认值")
            except Exception as fallback_e:
                logger.error(f"使用默认配置也失败: {fallback_e}")
            import traceback
            logger.error(f"配置加载异常详情: {traceback.format_exc()}")

    def refresh_config_from_database(self, web_config):
        """从数据库配置刷新UI显示

        Args:
            web_config: 从数据库加载的Web服务配置字典
        """
        try:
            if web_config and isinstance(web_config, dict):
                # 更新端口号
                if 'port' in web_config and isinstance(web_config['port'], int):
                    self.port_spinbox.setValue(web_config['port'])
                    logger.debug(f"刷新端口号: {web_config['port']}")

                # 更新主机地址
                if 'host' in web_config and web_config['host']:
                    self.host_input.setText(web_config['host'])
                    logger.debug(f"刷新主机地址: {web_config['host']}")

                # 更新自动启动
                if 'auto_start' in web_config:
                    self.auto_start_checkbox.setChecked(bool(web_config['auto_start']))
                    logger.debug(f"刷新自动启动: {web_config['auto_start']}")

                # 更新密码显示
                if 'password' in web_config and web_config['password']:
                    self.password_input.setPlaceholderText("已设置密码（输入新密码可修改）")
                    logger.debug("刷新密码状态: 已设置")
                else:
                    self.password_input.setPlaceholderText("留空表示不需要密码")
                    logger.debug("刷新密码状态: 未设置")

                self.add_log(f"已从数据库刷新配置: host={web_config.get('host', 'N/A')}, port={web_config.get('port', 'N/A')}, auto_start={web_config.get('auto_start', 'N/A')}")
                logger.info(f"Web服务面板已从数据库刷新配置: {web_config}")
            else:
                logger.warning("刷新配置失败：配置为空或格式不正确")
        except Exception as e:
            logger.error(f"刷新Web服务配置失败: {e}")
            import traceback
            logger.error(f"刷新配置异常详情: {traceback.format_exc()}")

    def _toggle_web_service(self):
        """切换Web服务状态"""
        running = is_web_service_running()

        if running:
            # 停止Web服务
            asyncio.create_task(self._stop_web_service())
        else:
            # 启动Web服务
            port = self.port_spinbox.value()
            host = self.host_input.text()
            asyncio.create_task(self._start_web_service(host, port))

    async def _start_web_service(self, host, port):
        """
        启动Web服务

        Args:
            host: 主机地址
            port: 端口号
        """
        try:
            # 确保端口是整数
            if isinstance(port, str):
                try:
                    port = int(port)
                except ValueError:
                    self.add_log(f"无效的端口号: {port}")
                    logger.error(f"无效的端口号: {port}")
                    return

            # 保存配置到配置存储
            auto_start = self.auto_start_checkbox.isChecked()
            password = self.password_input.text().strip()

            # 使用新的配置管理
            from wxauto_mgt.web.config import get_web_service_config as get_new_web_config
            web_config = get_new_web_config()

            # 保存配置
            await web_config.save_config(
                host=host,
                port=port,
                auto_start=auto_start,
                password=password if password else None
            )

            if password:
                self.add_log("已更新访问密码")

            # 更新旧的配置格式（兼容性）
            config = get_web_service_config()
            config['port'] = port
            config['host'] = host
            set_web_service_config(config)

            # 启动Web服务
            # 确保配置中不包含debug参数
            if 'debug' in config:
                del config['debug']

            # 检查依赖项
            try:
                import fastapi
                import uvicorn
                import jinja2
            except ImportError as e:
                error_msg = f"缺少必要的依赖项: {e}\n请安装: pip install fastapi uvicorn jinja2"
                self.add_log(f"启动Web服务失败: 缺少依赖项 - {e}")
                logger.error(error_msg)
                return

            # 移除端口检查机制，直接尝试启动Web服务
            # 端口检查经常出现误报，让Web服务器自己处理端口冲突
            self.add_log(f"准备启动Web服务，地址: http://{host}:{port}")

            self.add_log(f"正在启动Web服务，地址: http://{host}:{port}...")
            # 不传递config参数，避免覆盖现有的密码配置
            success = await start_web_service()

            if success:
                self.add_log(f"Web服务已启动，地址: http://{host}:{port}")
                logger.info(f"Web服务已启动，地址: http://{host}:{port}")
            else:
                self.add_log("启动Web服务失败")
                logger.error("启动Web服务失败")

                # 如果启动失败，提供端口冲突的解决建议
                self.add_log(f"提示: 如果端口 {port} 被占用，请尝试以下解决方案:")
                self.add_log("1. 更改端口号到其他值（如8081、8082、9090等）")
                self.add_log("2. 检查是否有其他程序占用该端口")
                self.add_log("3. 重启计算机释放被占用的端口")

            # 更新状态显示
            self._update_web_service_status()
        except Exception as e:
            import traceback
            error_msg = f"启动Web服务时出错: {str(e)}\n{traceback.format_exc()}"
            self.add_log(f"启动Web服务时出错: {str(e)}")
            logger.error(error_msg)

    async def _stop_web_service(self):
        """停止Web服务"""
        try:
            self.add_log("正在停止Web服务...")

            # 停止Web服务
            success = await stop_web_service()

            if success:
                self.add_log("Web服务已停止")
                logger.info("Web服务已停止")
            else:
                self.add_log("停止Web服务失败")
                logger.error("停止Web服务失败")

            # 更新状态显示
            self._update_web_service_status()
        except Exception as e:
            self.add_log(f"停止Web服务时出错: {str(e)}")
            logger.error(f"停止Web服务时出错: {e}")

    def _open_web_interface(self):
        """打开Web管理界面"""
        if not is_web_service_running():
            self.add_log("Web服务未运行，无法打开界面")
            return

        try:
            # 获取当前配置
            config = get_web_service_config()
            host = config.get('host', '0.0.0.0')
            port = config.get('port', 8080)

            # 如果监听地址是0.0.0.0，替换为localhost
            if host == '0.0.0.0':
                host = 'localhost'
                self.add_log("监听地址为0.0.0.0，将使用localhost访问")

            # 构建URL
            url = f"http://{host}:{port}"

            # 使用系统默认浏览器打开URL
            webbrowser.open(url)

            self.add_log(f"已在浏览器中打开Web管理界面: {url}")
        except Exception as e:
            self.add_log(f"打开Web界面失败: {str(e)}")
            logger.error(f"打开Web界面失败: {e}")

    def _save_config(self):
        """保存Web服务配置"""
        try:
            # 获取配置
            port = self.port_spinbox.value()
            host = self.host_input.text()
            auto_start = self.auto_start_checkbox.isChecked()
            password = self.password_input.text().strip()

            # 更新配置
            config = get_web_service_config()
            config['port'] = port
            config['host'] = host
            set_web_service_config(config)

            # 保存配置到配置存储
            asyncio.create_task(self._save_config_async(port, host, auto_start, password))

            self.add_log("Web服务配置已保存")
        except Exception as e:
            self.add_log(f"保存Web服务配置失败: {str(e)}")
            logger.error(f"保存Web服务配置失败: {e}")

    async def _save_config_async(self, port, host, auto_start, password):
        """异步保存配置"""
        try:
            from wxauto_mgt.web.config import get_web_service_config as get_new_web_config
            web_config = get_new_web_config()

            # 保存配置
            success = await web_config.save_config(
                host=host,
                port=port,
                auto_start=auto_start,
                password=password if password else None
            )

            if success:
                if password:
                    self.add_log("已更新访问密码")
                    # 清空密码输入框
                    self.password_input.clear()
                    self.password_input.setPlaceholderText("已设置密码（输入新密码可修改）")
                self.add_log("配置已保存")
            else:
                self.add_log("配置保存失败")

        except Exception as e:
            self.add_log(f"异步保存配置失败: {str(e)}")
            logger.error(f"异步保存配置失败: {e}")
