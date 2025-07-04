"""
对话框组件模块

实现各种对话框组件，如添加实例、编辑实例、设置和消息回复等。
"""

import uuid
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit,
    QLabel, QCheckBox, QFormLayout, QComboBox, QSpinBox,
    QDialogButtonBox, QMessageBox, QTextEdit, QTabWidget,
    QGroupBox, QRadioButton, QWidget, QFileDialog
)

from wxauto_mgt.core.api_client import instance_manager
from wxauto_mgt.core.config_manager import config_manager
from wxauto_mgt.utils.logging import get_logger

logger = get_logger()


class AddInstanceDialog(QDialog):
    """添加实例对话框"""

    def __init__(self, parent=None):
        """初始化对话框"""
        super().__init__(parent)

        self.setWindowTitle("添加WxAuto实例")
        self.resize(500, 300)

        self._init_ui()

    def _init_ui(self):
        """初始化UI组件"""
        # 主布局
        main_layout = QVBoxLayout(self)

        # 表单布局
        form_layout = QFormLayout()

        # 实例ID
        self.id_edit = QLineEdit()
        self.id_edit.setPlaceholderText("输入实例ID或留空自动生成")
        form_layout.addRow("实例ID:", self.id_edit)

        # 实例名称
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("如：我的手机微信")
        form_layout.addRow("名称:", self.name_edit)

        # API地址
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("如：http://localhost:8080/api")
        form_layout.addRow("API地址:", self.url_edit)

        # API密钥
        self.key_edit = QLineEdit()
        self.key_edit.setPlaceholderText("WxAuto API密钥")
        self.key_edit.setEchoMode(QLineEdit.Password)
        form_layout.addRow("API密钥:", self.key_edit)

        # 高级选项
        self.advanced_group = QGroupBox("高级选项")
        advanced_layout = QFormLayout(self.advanced_group)

        # 超时时间
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(5, 120)
        self.timeout_spin.setValue(30)
        self.timeout_spin.setSuffix(" 秒")
        advanced_layout.addRow("请求超时:", self.timeout_spin)

        # 重试次数
        self.retry_spin = QSpinBox()
        self.retry_spin.setRange(0, 10)
        self.retry_spin.setValue(3)
        self.retry_spin.setSuffix(" 次")
        advanced_layout.addRow("失败重试:", self.retry_spin)

        # 轮询间隔
        self.poll_interval_spin = QSpinBox()
        self.poll_interval_spin.setRange(5, 60)  # 强制最小5秒
        self.poll_interval_spin.setValue(5)
        self.poll_interval_spin.setSuffix(" 秒")
        advanced_layout.addRow("轮询间隔:", self.poll_interval_spin)

        # 消息超时时间
        self.timeout_minutes_spin = QSpinBox()
        self.timeout_minutes_spin.setRange(1, 1440)  # 1分钟到24小时
        self.timeout_minutes_spin.setValue(30)
        self.timeout_minutes_spin.setSuffix(" 分钟")
        advanced_layout.addRow("消息超时:", self.timeout_minutes_spin)

        # 启用实例
        self.enabled_check = QCheckBox("启用该实例")
        self.enabled_check.setChecked(True)
        advanced_layout.addRow("", self.enabled_check)

        main_layout.addLayout(form_layout)
        main_layout.addWidget(self.advanced_group)

        # 按钮布局
        button_layout = QHBoxLayout()

        # 生成ID按钮
        self.gen_id_btn = QPushButton("生成ID")
        self.gen_id_btn.clicked.connect(self._generate_id)
        button_layout.addWidget(self.gen_id_btn)

        button_layout.addStretch()

        # 确定取消按钮
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        button_layout.addWidget(self.button_box)

        main_layout.addLayout(button_layout)

    def _generate_id(self):
        """生成随机实例ID"""
        random_id = f"wxauto_{uuid.uuid4().hex[:8]}"
        self.id_edit.setText(random_id)

    def get_instance_data(self):
        """
        获取实例数据

        Returns:
            dict: 实例数据
        """
        # 基本数据
        data = {
            "instance_id": f"wxauto_{uuid.uuid4().hex[:8]}",
            "name": self.name_edit.text().strip(),
            "base_url": self.url_edit.text().strip(),
            "api_key": self.key_edit.text().strip(),
            "enabled": 1 if self.enabled_check.isChecked() else 0,
        }

        # 高级配置
        extra_config = {
            "timeout": self.timeout_spin.value(),
            "retry_limit": self.retry_spin.value(),
            "poll_interval": self.poll_interval_spin.value(),
            "timeout_minutes": self.timeout_minutes_spin.value()
        }

        data["config"] = extra_config

        return data

    def accept(self):
        """验证并接受对话框"""
        # 验证必填字段
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "验证错误", "请输入实例名称")
            self.name_edit.setFocus()
            return

        if not self.url_edit.text().strip():
            QMessageBox.warning(self, "验证错误", "请输入API地址")
            self.url_edit.setFocus()
            return

        if not self.key_edit.text().strip():
            QMessageBox.warning(self, "验证错误", "请输入API密钥")
            self.key_edit.setFocus()
            return

        super().accept()


class EditInstanceDialog(QDialog):
    """编辑实例对话框"""

    def __init__(self, parent=None, instance_data: Dict = None):
        """
        初始化对话框

        Args:
            parent: 父窗口
            instance_data: 实例数据字典
        """
        super().__init__(parent)

        self.setWindowTitle("编辑WxAuto实例")
        self.resize(500, 300)

        self._instance_data = instance_data or {}
        self._init_ui()
        self._load_instance_data()

    def _init_ui(self):
        """初始化UI组件"""
        # 主布局
        main_layout = QVBoxLayout(self)

        # 表单布局
        form_layout = QFormLayout()

        # 实例ID（只读）
        self.id_label = QLabel()
        form_layout.addRow("实例ID:", self.id_label)

        # 实例名称
        self.name_edit = QLineEdit()
        form_layout.addRow("名称:", self.name_edit)

        # API地址
        self.url_edit = QLineEdit()
        form_layout.addRow("API地址:", self.url_edit)

        # API密钥
        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.Password)
        form_layout.addRow("API密钥:", self.key_edit)

        # 高级选项
        self.advanced_group = QGroupBox("高级选项")
        advanced_layout = QFormLayout(self.advanced_group)

        # 超时时间
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(5, 120)
        self.timeout_spin.setValue(30)
        self.timeout_spin.setSuffix(" 秒")
        advanced_layout.addRow("请求超时:", self.timeout_spin)

        # 重试次数
        self.retry_spin = QSpinBox()
        self.retry_spin.setRange(0, 10)
        self.retry_spin.setValue(3)
        self.retry_spin.setSuffix(" 次")
        advanced_layout.addRow("失败重试:", self.retry_spin)

        # 轮询间隔
        self.poll_interval_spin = QSpinBox()
        self.poll_interval_spin.setRange(5, 60)  # 强制最小5秒
        self.poll_interval_spin.setValue(5)
        self.poll_interval_spin.setSuffix(" 秒")
        advanced_layout.addRow("轮询间隔:", self.poll_interval_spin)

        # 消息超时时间
        self.timeout_minutes_spin = QSpinBox()
        self.timeout_minutes_spin.setRange(1, 1440)  # 1分钟到24小时
        self.timeout_minutes_spin.setValue(30)
        self.timeout_minutes_spin.setSuffix(" 分钟")
        advanced_layout.addRow("消息超时:", self.timeout_minutes_spin)

        # 启用实例
        self.enabled_check = QCheckBox("启用该实例")
        self.enabled_check.setChecked(True)
        advanced_layout.addRow("", self.enabled_check)

        main_layout.addLayout(form_layout)
        main_layout.addWidget(self.advanced_group)

        # 按钮布局
        button_layout = QHBoxLayout()

        button_layout.addStretch()

        # 确定取消按钮
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        button_layout.addWidget(self.button_box)

        main_layout.addLayout(button_layout)

    def _load_instance_data(self):
        """加载实例数据"""
        if not self._instance_data:
            return

        self.id_label.setText(self._instance_data.get("instance_id", ""))
        self.name_edit.setText(self._instance_data.get("name", ""))
        self.url_edit.setText(self._instance_data.get("base_url", ""))
        self.key_edit.setText(self._instance_data.get("api_key", ""))
        self.timeout_spin.setValue(self._instance_data.get("timeout", 30))
        self.retry_spin.setValue(self._instance_data.get("retry_limit", 3))
        self.enabled_check.setChecked(self._instance_data.get("enabled", True))

    def get_instance_data(self) -> Dict:
        """
        获取实例数据

        Returns:
            Dict: 实例数据字典
        """
        return {
            "instance_id": self.id_label.text(),
            "name": self.name_edit.text().strip(),
            "base_url": self.url_edit.text().strip(),
            "api_key": self.key_edit.text().strip(),
            "timeout": self.timeout_spin.value(),
            "retry_limit": self.retry_spin.value(),
            "enabled": self.enabled_check.isChecked()
        }

    def accept(self):
        """验证并接受对话框"""
        # 验证必填字段
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "验证错误", "请输入实例名称")
            self.name_edit.setFocus()
            return

        if not self.url_edit.text().strip():
            QMessageBox.warning(self, "验证错误", "请输入API地址")
            self.url_edit.setFocus()
            return

        if not self.key_edit.text().strip():
            QMessageBox.warning(self, "验证错误", "请输入API密钥")
            self.key_edit.setFocus()
            return

        super().accept()


class SettingsDialog(QDialog):
    """设置对话框"""

    def __init__(self, parent=None):
        """初始化对话框"""
        super().__init__(parent)

        self.setWindowTitle("设置")
        self.resize(600, 400)

        self._init_ui()
        self._load_settings()

        # 连接信号，实现实时保存
        self._connect_auto_save_signals()

    def _init_ui(self):
        """初始化UI组件"""
        # 主布局
        main_layout = QVBoxLayout(self)

        # 选项卡
        self.tab_widget = QTabWidget()

        # 常规设置选项卡
        self.general_tab = QWidget()
        general_layout = QFormLayout(self.general_tab)

        # 日志级别
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        general_layout.addRow("日志级别:", self.log_level_combo)

        # 自动启动监听
        self.auto_start_check = QCheckBox("启动时自动开始消息监听")
        general_layout.addRow("", self.auto_start_check)

        # 自动刷新状态
        self.auto_refresh_check = QCheckBox("自动刷新状态")
        general_layout.addRow("", self.auto_refresh_check)

        # 使用临时目录作为下载目录
        self.use_temp_dir_check = QCheckBox("使用临时目录作为文件下载目录")
        self.use_temp_dir_check.setToolTip("启用后，所有文件将下载到系统临时目录而不是data/downloads目录")
        general_layout.addRow("", self.use_temp_dir_check)

        self.tab_widget.addTab(self.general_tab, "常规设置")

        # 消息监听选项卡
        self.message_tab = QWidget()
        message_layout = QFormLayout(self.message_tab)

        # 轮询间隔
        self.poll_interval_spin = QSpinBox()
        self.poll_interval_spin.setRange(5, 60)  # 强制最小5秒
        self.poll_interval_spin.setValue(5)
        self.poll_interval_spin.setSuffix(" 秒")
        message_layout.addRow("轮询间隔:", self.poll_interval_spin)

        # 最大监听数
        self.max_listeners_spin = QSpinBox()
        self.max_listeners_spin.setRange(1, 100)
        self.max_listeners_spin.setValue(30)
        message_layout.addRow("最大监听数:", self.max_listeners_spin)

        # 监听超时时间
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(1, 1440)
        self.timeout_spin.setValue(30)
        self.timeout_spin.setSuffix(" 分钟")
        message_layout.addRow("监听超时:", self.timeout_spin)

        # 消息通知设置
        self.notify_group = QGroupBox("消息通知")
        notify_layout = QVBoxLayout(self.notify_group)

        self.notify_new_check = QCheckBox("接收新消息通知")
        self.notify_new_check.setToolTip("启用后，当监听到新消息时会在UI中显示通知")
        notify_layout.addWidget(self.notify_new_check)

        self.notify_status_check = QCheckBox("接收状态变更通知")
        self.notify_status_check.setToolTip("启用后，当实例状态或监听对象状态发生变化时会显示通知")
        notify_layout.addWidget(self.notify_status_check)

        message_layout.addRow(self.notify_group)

        self.tab_widget.addTab(self.message_tab, "消息监听")

        # 数据库设置选项卡
        self.database_tab = QWidget()
        database_layout = QFormLayout(self.database_tab)

        # 数据库路径
        self.db_path_edit = QLineEdit()
        database_layout.addRow("数据库路径:", self.db_path_edit)

        # 自动清理消息
        self.auto_clean_check = QCheckBox("自动清理旧消息")
        database_layout.addRow("", self.auto_clean_check)

        # 保留时间
        self.retention_spin = QSpinBox()
        self.retention_spin.setRange(1, 365)
        self.retention_spin.setValue(7)
        self.retention_spin.setSuffix(" 天")
        database_layout.addRow("保留时间:", self.retention_spin)

        self.tab_widget.addTab(self.database_tab, "数据库")

        # Web服务设置选项卡
        self.web_service_tab = QWidget()
        web_service_layout = QVBoxLayout(self.web_service_tab)
        web_service_layout.setContentsMargins(10, 10, 10, 10)
        web_service_layout.setSpacing(10)

        # 创建Web服务配置表单
        form_layout = QFormLayout()
        form_layout.setContentsMargins(0, 10, 0, 10)
        form_layout.setSpacing(10)

        # 主机地址
        host_layout = QHBoxLayout()
        self.web_host_edit = QLineEdit("0.0.0.0")
        self.web_host_edit.setToolTip("Web服务主机地址，默认为0.0.0.0（监听所有网络接口）")
        self.web_host_edit.setFixedWidth(200)
        host_layout.addWidget(self.web_host_edit)
        host_layout.addStretch()
        form_layout.addRow("主机地址:", host_layout)

        # 端口号
        port_layout = QHBoxLayout()
        self.web_port_spin = QSpinBox()
        self.web_port_spin.setRange(1024, 65535)
        self.web_port_spin.setValue(8080)  # 默认端口
        self.web_port_spin.setFixedWidth(100)
        self.web_port_spin.setToolTip("Web服务端口号 (1024-65535)")
        port_layout.addWidget(self.web_port_spin)
        port_layout.addStretch()
        form_layout.addRow("端口号:", port_layout)

        # 访问密码
        password_layout = QHBoxLayout()
        self.web_password_edit = QLineEdit()
        self.web_password_edit.setEchoMode(QLineEdit.Password)
        self.web_password_edit.setToolTip("Web服务访问密码，留空表示不需要密码验证")
        self.web_password_edit.setFixedWidth(200)
        self.web_password_edit.setPlaceholderText("留空表示不需要密码")
        password_layout.addWidget(self.web_password_edit)
        password_layout.addStretch()
        form_layout.addRow("访问密码:", password_layout)

        # 自动启动
        auto_start_layout = QHBoxLayout()
        self.web_auto_start_check = QCheckBox("程序启动时自动启动Web服务")
        self.web_auto_start_check.setChecked(False)
        auto_start_layout.addWidget(self.web_auto_start_check)
        auto_start_layout.addStretch()
        form_layout.addRow("", auto_start_layout)

        web_service_layout.addLayout(form_layout)
        web_service_layout.addStretch()

        self.tab_widget.addTab(self.web_service_tab, "Web服务")

        main_layout.addWidget(self.tab_widget)

        # 按钮布局
        button_layout = QHBoxLayout()

        button_layout.addStretch()

        # 确定取消按钮
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Apply)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.button_box.button(QDialogButtonBox.Apply).clicked.connect(self._apply_settings)
        button_layout.addWidget(self.button_box)

        main_layout.addLayout(button_layout)

    def _load_settings(self):
        """加载设置"""
        # 从配置管理器加载设置
        from wxauto_mgt.core.config_manager import config_manager

        # 加载常规设置
        try:
            # 日志级别
            log_level = config_manager.get('app.log_level', 'INFO')
            index = self.log_level_combo.findText(log_level)
            if index >= 0:
                self.log_level_combo.setCurrentIndex(index)

            # 自动启动监听
            auto_start = config_manager.get('message_listener.auto_start', True)  # 默认为True，与默认配置一致
            self.auto_start_check.setChecked(auto_start)

            # 自动刷新状态
            auto_refresh = config_manager.get('app.auto_refresh', True)
            self.auto_refresh_check.setChecked(auto_refresh)

            # 使用临时目录作为下载目录
            use_temp_dir = config_manager.get('app.use_temp_dir_for_downloads', False)
            self.use_temp_dir_check.setChecked(use_temp_dir)
            logger.debug(f"加载使用临时目录设置: {use_temp_dir}")
        except Exception as e:
            logger.error(f"加载常规设置失败: {e}")

        # 加载消息监听设置
        try:
            # 轮询间隔
            poll_interval = config_manager.get('message_listener.poll_interval', 5)
            self.poll_interval_spin.setValue(poll_interval)

            # 最大监听数
            max_listeners = config_manager.get('message_listener.max_listeners', 30)
            self.max_listeners_spin.setValue(max_listeners)

            # 监听超时时间
            listener_timeout = config_manager.get('message_listener.listener_timeout_minutes', 30)
            self.timeout_spin.setValue(listener_timeout)

            # 消息通知设置
            notify_new = config_manager.get('message_listener.notify_new_messages', True)
            self.notify_new_check.setChecked(notify_new)

            notify_status = config_manager.get('message_listener.notify_status_changes', True)
            self.notify_status_check.setChecked(notify_status)
        except Exception as e:
            logger.error(f"加载消息监听设置失败: {e}")

        # 加载数据库设置
        try:
            # 数据库路径
            db_path = config_manager.get('db.path', './data/wxauto_mgt.db')
            self.db_path_edit.setText(db_path)

            # 自动清理旧消息
            auto_clean = config_manager.get('db.auto_clean_messages', False)
            self.auto_clean_check.setChecked(auto_clean)

            # 保留时间
            retention_days = config_manager.get('db.retention_days', 7)
            self.retention_spin.setValue(retention_days)
        except Exception as e:
            logger.error(f"加载数据库设置失败: {e}")

        # 加载Web服务设置
        try:
            # 从config_store同步加载Web服务配置（与主窗口保持一致）
            from wxauto_mgt.data.config_store import config_store
            import json

            # 使用同步方法加载配置
            web_config_raw = config_store.get_config_sync('system', 'web_service', {})

            # 如果返回的是字符串，解析为字典
            if isinstance(web_config_raw, str):
                web_config = json.loads(web_config_raw)
            else:
                web_config = web_config_raw

            if web_config:
                # 设置主机地址
                if 'host' in web_config:
                    self.web_host_edit.setText(web_config['host'])
                else:
                    self.web_host_edit.setText('0.0.0.0')

                # 设置端口号
                if 'port' in web_config:
                    self.web_port_spin.setValue(web_config['port'])
                else:
                    self.web_port_spin.setValue(8080)

                # 设置自动启动
                if 'auto_start' in web_config:
                    self.web_auto_start_check.setChecked(web_config['auto_start'])
                else:
                    self.web_auto_start_check.setChecked(False)

                # 设置密码（不显示实际密码，只显示是否已设置）
                if 'password' in web_config and web_config['password']:
                    self.web_password_edit.setPlaceholderText("已设置密码（输入新密码可修改）")
                else:
                    self.web_password_edit.setPlaceholderText("留空表示不需要密码")

                logger.debug(f"已加载Web服务配置: {web_config}")
            else:
                # 使用默认值
                self.web_host_edit.setText('0.0.0.0')
                self.web_port_spin.setValue(8080)
                self.web_auto_start_check.setChecked(False)
                logger.debug("未找到Web服务配置，使用默认值")
        except Exception as e:
            logger.error(f"加载Web服务设置失败: {e}")
            # 使用默认值
            self.web_host_edit.setText('0.0.0.0')
            self.web_port_spin.setValue(8080)
            self.web_auto_start_check.setChecked(False)

    def _connect_auto_save_signals(self):
        """连接自动保存信号"""
        # 连接重要设置的变更信号，实现实时保存
        self.auto_start_check.toggled.connect(self._auto_save_auto_start)

    def _auto_save_auto_start(self, checked):
        """自动保存auto_start设置"""
        try:
            from wxauto_mgt.core.config_manager import config_manager
            import asyncio

            # 保存设置
            config_manager.set('message_listener.auto_start', checked)

            # 异步保存到数据库
            asyncio.create_task(config_manager.save_config())

            logger.info(f"自动保存auto_start设置: {checked}")
        except Exception as e:
            logger.error(f"自动保存auto_start设置失败: {e}")

    async def _save_web_service_config_async(self, host, port, auto_start, password):
        """异步保存Web服务配置"""
        try:
            from wxauto_mgt.web.config import get_web_service_config
            web_config = get_web_service_config()

            # 保存配置
            success = await web_config.save_config(
                host=host,
                port=port,
                auto_start=auto_start,
                password=password if password else None
            )

            if success:
                if password:
                    logger.info("已更新Web服务访问密码")
                    # 清空密码输入框
                    self.web_password_edit.clear()
                    self.web_password_edit.setPlaceholderText("已设置密码（输入新密码可修改）")
                logger.debug(f"已保存Web服务配置: host={host}, port={port}, auto_start={auto_start}")
            else:
                logger.error("保存Web服务配置失败")

        except Exception as e:
            logger.error(f"异步保存Web服务配置失败: {e}")

    async def _start_cleanup_task(self, retention_days):
        """启动数据库清理任务"""
        try:
            from wxauto_mgt.core.message_store import message_store

            # 执行清理
            success = await message_store.cleanup_old_messages(retention_days)
            if success:
                logger.info(f"数据库清理完成，保留{retention_days}天内的消息")
            else:
                logger.error("数据库清理失败")
        except Exception as e:
            logger.error(f"启动数据库清理任务失败: {e}")

    def _apply_settings(self):
        """应用设置"""
        # 将设置保存到配置管理器
        from wxauto_mgt.core.config_manager import config_manager
        import asyncio

        # 保存常规设置
        try:
            # 日志级别
            log_level = self.log_level_combo.currentText()
            config_manager.set('app.log_level', log_level)

            # 自动启动监听
            auto_start = self.auto_start_check.isChecked()
            config_manager.set('message_listener.auto_start', auto_start)

            # 自动刷新状态
            auto_refresh = self.auto_refresh_check.isChecked()
            config_manager.set('app.auto_refresh', auto_refresh)

            # 使用临时目录作为下载目录
            use_temp_dir = self.use_temp_dir_check.isChecked()
            config_manager.set('app.use_temp_dir_for_downloads', use_temp_dir)
            logger.debug(f"保存使用临时目录设置: {use_temp_dir}")

            # 设置环境变量，使当前会话立即生效
            import os
            os.environ['WXAUTO_USE_TEMP_DIR'] = 'true' if use_temp_dir else 'false'

            # 重新初始化消息处理器
            from wxauto_mgt.core.message_processor import MessageProcessor
            try:
                # 创建新的消息处理器实例
                new_processor = MessageProcessor(use_temp_dir=use_temp_dir)
                # 替换全局实例
                import wxauto_mgt.core.message_processor
                wxauto_mgt.core.message_processor.message_processor = new_processor
                logger.info(f"已重新初始化消息处理器，使用临时目录: {use_temp_dir}")
            except Exception as e:
                logger.error(f"重新初始化消息处理器失败: {e}")
        except Exception as e:
            logger.error(f"保存常规设置失败: {e}")

        # 保存消息监听设置
        try:
            # 轮询间隔
            poll_interval = self.poll_interval_spin.value()
            config_manager.set('message_listener.poll_interval', poll_interval)

            # 最大监听数
            max_listeners = self.max_listeners_spin.value()
            config_manager.set('message_listener.max_listeners', max_listeners)

            # 监听超时时间
            listener_timeout = self.timeout_spin.value()
            config_manager.set('message_listener.listener_timeout_minutes', listener_timeout)

            # 消息通知设置
            notify_new = self.notify_new_check.isChecked()
            config_manager.set('message_listener.notify_new_messages', notify_new)

            notify_status = self.notify_status_check.isChecked()
            config_manager.set('message_listener.notify_status_changes', notify_status)

            # 更新消息监听器设置
            from wxauto_mgt.core.message_listener import message_listener
            message_listener.poll_interval = poll_interval
            message_listener.max_listeners = max_listeners
            message_listener.listener_timeout_minutes = listener_timeout
        except Exception as e:
            logger.error(f"保存消息监听设置失败: {e}")

        # 保存数据库设置
        try:
            # 数据库路径
            db_path = self.db_path_edit.text().strip()
            config_manager.set('db.path', db_path)

            # 自动清理旧消息
            auto_clean = self.auto_clean_check.isChecked()
            config_manager.set('db.auto_clean_messages', auto_clean)

            # 保留时间
            retention_days = self.retention_spin.value()
            config_manager.set('db.retention_days', retention_days)

            # 如果启用了自动清理，启动清理任务
            if auto_clean:
                asyncio.create_task(self._start_cleanup_task(retention_days))
        except Exception as e:
            logger.error(f"保存数据库设置失败: {e}")

        # 保存Web服务设置
        try:
            # 获取配置
            web_host = self.web_host_edit.text().strip() or '0.0.0.0'
            web_port = self.web_port_spin.value()
            web_auto_start = self.web_auto_start_check.isChecked()
            web_password = self.web_password_edit.text().strip()

            # 保存到config_store（与Web服务面板同步）
            asyncio.create_task(self._save_web_service_config_async(web_host, web_port, web_auto_start, web_password))

            logger.info(f"保存Web服务设置: host={web_host}, port={web_port}, auto_start={web_auto_start}")
        except Exception as e:
            logger.error(f"保存Web服务设置失败: {e}")

        # 异步保存配置
        asyncio.create_task(config_manager.save_config())

        QMessageBox.information(self, "保存成功", "设置已应用")

    def accept(self):
        """验证并接受对话框"""
        # 应用设置
        self._apply_settings()

        # 关闭对话框
        super().accept()


class AddListenerDialog(QDialog):
    """添加监听对话框"""

    def __init__(self, parent=None):
        """初始化对话框"""
        super().__init__(parent)

        self.setWindowTitle("添加监听对象")
        self.resize(400, 200)

        self._init_ui()

    def _init_ui(self):
        """初始化UI组件"""
        # 主布局
        main_layout = QVBoxLayout(self)

        # 表单布局
        form_layout = QFormLayout()

        # 实例选择
        self.instance_combo = QComboBox()
        self._load_instances()
        form_layout.addRow("实例:", self.instance_combo)

        # 微信ID
        self.wxid_edit = QLineEdit()
        self.wxid_edit.setPlaceholderText("微信ID或群ID")
        form_layout.addRow("微信ID:", self.wxid_edit)

        # 备注
        self.remark_edit = QLineEdit()
        self.remark_edit.setPlaceholderText("可选")
        form_layout.addRow("备注:", self.remark_edit)

        main_layout.addLayout(form_layout)

        # 按钮布局
        button_layout = QHBoxLayout()

        button_layout.addStretch()

        # 确定取消按钮
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        button_layout.addWidget(self.button_box)

        main_layout.addLayout(button_layout)

    def _load_instances(self):
        """加载实例列表"""
        # 清空下拉框
        self.instance_combo.clear()

        # 获取实例列表
        from wxauto_mgt.core.config_manager import config_manager
        instances = config_manager.get_enabled_instances()

        # 添加实例到下拉框
        for instance in instances:
            instance_id = instance.get("instance_id", "")
            name = instance.get("name", instance_id)
            self.instance_combo.addItem(name, instance_id)

    def get_listener_data(self) -> Dict:
        """
        获取监听对象数据

        Returns:
            Dict: 监听对象数据字典
        """
        return {
            "instance_id": self.instance_combo.currentData(),
            "wxid": self.wxid_edit.text().strip(),
            "remark": self.remark_edit.text().strip()
        }

    def accept(self):
        """验证并接受对话框"""
        # 验证必填字段
        if self.instance_combo.currentIndex() < 0:
            QMessageBox.warning(self, "验证错误", "请选择一个实例")
            self.instance_combo.setFocus()
            return

        if not self.wxid_edit.text().strip():
            QMessageBox.warning(self, "验证错误", "请输入微信ID")
            self.wxid_edit.setFocus()
            return

        super().accept()


class ReplyMessageDialog(QDialog):
    """消息回复对话框"""

    def __init__(self, parent=None, message_id: str = "", receiver: str = ""):
        """
        初始化对话框

        Args:
            parent: 父窗口
            message_id: 消息ID
            receiver: 接收者微信ID
        """
        super().__init__(parent)

        self.setWindowTitle("回复消息")
        self.resize(500, 300)

        self._message_id = message_id
        self._receiver = receiver

        self._init_ui()

    def _init_ui(self):
        """初始化UI组件"""
        # 主布局
        main_layout = QVBoxLayout(self)

        # 接收者标签
        receiver_layout = QHBoxLayout()
        receiver_layout.addWidget(QLabel("接收者:"))
        receiver_label = QLabel(self._receiver)
        receiver_label.setStyleSheet("font-weight: bold;")
        receiver_layout.addWidget(receiver_label)
        receiver_layout.addStretch()
        main_layout.addLayout(receiver_layout)

        # 回复类型选择
        type_group = QGroupBox("回复类型")
        type_layout = QHBoxLayout(type_group)

        self.text_radio = QRadioButton("文本")
        self.text_radio.setChecked(True)
        type_layout.addWidget(self.text_radio)

        self.image_radio = QRadioButton("图片")
        type_layout.addWidget(self.image_radio)

        self.file_radio = QRadioButton("文件")
        type_layout.addWidget(self.file_radio)

        type_layout.addStretch()

        main_layout.addWidget(type_group)

        # 回复内容
        content_label = QLabel("回复内容:")
        main_layout.addWidget(content_label)

        self.content_text = QTextEdit()
        main_layout.addWidget(self.content_text)

        # 文件选择按钮（默认隐藏）
        self.file_select_btn = QPushButton("选择文件")
        self.file_select_btn.setVisible(False)
        main_layout.addWidget(self.file_select_btn)

        # 连接信号
        self.text_radio.toggled.connect(self._on_type_changed)
        self.image_radio.toggled.connect(self._on_type_changed)
        self.file_radio.toggled.connect(self._on_type_changed)
        self.file_select_btn.clicked.connect(self._select_file)

        # 按钮布局
        button_layout = QHBoxLayout()

        button_layout.addStretch()

        # 确定取消按钮
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        button_layout.addWidget(self.button_box)

        main_layout.addLayout(button_layout)

    def _on_type_changed(self):
        """回复类型变更事件"""
        is_text = self.text_radio.isChecked()
        is_file = self.file_radio.isChecked() or self.image_radio.isChecked()

        self.content_text.setEnabled(is_text)
        self.file_select_btn.setVisible(is_file)

        if is_file:
            file_type = "图片" if self.image_radio.isChecked() else "文件"
            self.file_select_btn.setText(f"选择{file_type}")

    def _select_file(self):
        """选择文件"""
        # 导入文件对话框
        from PySide6.QtWidgets import QFileDialog

        # 根据类型设置过滤器
        if self.image_radio.isChecked():
            file_filter = "图片文件 (*.jpg *.jpeg *.png *.gif *.bmp)"
        else:
            file_filter = "所有文件 (*.*)"

        # 打开文件对话框
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择文件", "", file_filter
        )

        if file_path:
            self.content_text.setText(file_path)

    def get_reply_text(self) -> str:
        """
        获取回复文本

        Returns:
            str: 回复文本
        """
        return self.content_text.toPlainText()

    def get_reply_type(self) -> str:
        """
        获取回复类型

        Returns:
            str: 回复类型（text/image/file）
        """
        if self.text_radio.isChecked():
            return "text"
        elif self.image_radio.isChecked():
            return "image"
        else:
            return "file"

    def accept(self):
        """验证并接受对话框"""
        # 验证必填字段
        if not self.content_text.toPlainText().strip():
            QMessageBox.warning(self, "验证错误", "请输入回复内容")
            self.content_text.setFocus()
            return

        super().accept()


class AddAlertDialog(QDialog):
    """添加警报对话框"""

    def __init__(self, parent=None):
        """初始化对话框"""
        super().__init__(parent)

        self.setWindowTitle("添加警报规则")
        self.resize(400, 300)

        self._init_ui()

    def _init_ui(self):
        """初始化UI组件"""
        # 主布局
        main_layout = QVBoxLayout(self)

        # 表单布局
        form_layout = QFormLayout()

        # 实例选择
        self.instance_combo = QComboBox()
        self._load_instances()
        form_layout.addRow("实例:", self.instance_combo)

        # 指标选择
        self.metric_combo = QComboBox()
        self.metric_combo.addItems(["消息数量", "响应时间", "CPU使用率", "内存使用率"])
        form_layout.addRow("监控指标:", self.metric_combo)

        # 阈值
        self.threshold_spin = QSpinBox()
        self.threshold_spin.setRange(0, 1000000)
        self.threshold_spin.setValue(90)
        form_layout.addRow("阈值:", self.threshold_spin)

        # 阈值类型
        self.threshold_type_combo = QComboBox()
        self.threshold_type_combo.addItems(["大于等于", "小于等于"])
        form_layout.addRow("阈值类型:", self.threshold_type_combo)

        # 通知方式
        self.notify_group = QGroupBox("通知方式")
        notify_layout = QVBoxLayout(self.notify_group)

        self.notify_ui_check = QCheckBox("UI通知")
        self.notify_ui_check.setChecked(True)
        notify_layout.addWidget(self.notify_ui_check)

        self.notify_email_check = QCheckBox("邮件通知")
        notify_layout.addWidget(self.notify_email_check)

        self.notify_webhook_check = QCheckBox("Webhook通知")
        notify_layout.addWidget(self.notify_webhook_check)

        form_layout.addRow(self.notify_group)

        main_layout.addLayout(form_layout)

        # 按钮布局
        button_layout = QHBoxLayout()

        button_layout.addStretch()

        # 确定取消按钮
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        button_layout.addWidget(self.button_box)

        main_layout.addLayout(button_layout)

    def _load_instances(self):
        """加载实例列表"""
        # 清空下拉框
        self.instance_combo.clear()

        # 添加全部选项
        self.instance_combo.addItem("全部实例", "all")

        # 获取实例列表
        from wxauto_mgt.core.config_manager import config_manager
        instances = config_manager.get_enabled_instances()

        # 添加实例到下拉框
        for instance in instances:
            instance_id = instance.get("instance_id", "")
            name = instance.get("name", instance_id)
            self.instance_combo.addItem(name, instance_id)

    def get_alert_data(self) -> Dict:
        """
        获取警报规则数据

        Returns:
            Dict: 警报规则数据字典
        """
        # 获取选择的指标对应的MetricType枚举值
        metric_map = {
            0: "message_count",  # 消息数量
            1: "response_time",  # 响应时间
            2: "cpu_usage",      # CPU使用率
            3: "memory_usage"    # 内存使用率
        }
        metric_type = metric_map.get(self.metric_combo.currentIndex(), "message_count")

        # 获取通知方式
        notify_methods = []
        if self.notify_ui_check.isChecked():
            notify_methods.append("ui")
        if self.notify_email_check.isChecked():
            notify_methods.append("email")
        if self.notify_webhook_check.isChecked():
            notify_methods.append("webhook")

        return {
            "instance_id": self.instance_combo.currentData(),
            "metric_type": metric_type,
            "threshold": self.threshold_spin.value(),
            "threshold_type": "gte" if self.threshold_type_combo.currentIndex() == 0 else "lte",
            "notify_methods": notify_methods,
            "enabled": True
        }

    def accept(self):
        """验证并接受对话框"""
        # 验证必填字段
        if not any([self.notify_ui_check.isChecked(),
                   self.notify_email_check.isChecked(),
                   self.notify_webhook_check.isChecked()]):
            QMessageBox.warning(self, "验证错误", "请至少选择一种通知方式")
            return

        super().accept()


class EditAlertDialog(AddAlertDialog):
    """编辑警报对话框"""

    def __init__(self, parent=None, alert_data: Dict = None):
        """
        初始化对话框

        Args:
            parent: 父窗口
            alert_data: 警报规则数据字典
        """
        super().__init__(parent)

        self.setWindowTitle("编辑警报规则")

        if alert_data:
            self._load_alert_data(alert_data)

    def _load_alert_data(self, alert_data: Dict):
        """
        加载警报规则数据

        Args:
            alert_data: 警报规则数据字典
        """
        # 设置实例
        instance_id = alert_data.get("instance_id", "all")
        index = self.instance_combo.findData(instance_id)
        if index >= 0:
            self.instance_combo.setCurrentIndex(index)

        # 设置指标类型
        metric_type = alert_data.get("metric_type", "message_count")
        metric_map = {
            "message_count": 0,  # 消息数量
            "response_time": 1,   # 响应时间
            "cpu_usage": 2,       # CPU使用率
            "memory_usage": 3     # 内存使用率
        }
        self.metric_combo.setCurrentIndex(metric_map.get(metric_type, 0))

        # 设置阈值
        self.threshold_spin.setValue(alert_data.get("threshold", 90))

        # 设置阈值类型
        threshold_type = alert_data.get("threshold_type", "gte")
        self.threshold_type_combo.setCurrentIndex(0 if threshold_type == "gte" else 1)

        # 设置通知方式
        notify_methods = alert_data.get("notify_methods", [])
        self.notify_ui_check.setChecked("ui" in notify_methods)
        self.notify_email_check.setChecked("email" in notify_methods)
        self.notify_webhook_check.setChecked("webhook" in notify_methods)