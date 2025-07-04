"""
添加实例对话框

该模块提供了添加WxAuto实例的对话框界面。
"""

import uuid
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit,
    QLabel, QCheckBox, QFormLayout, QComboBox, QSpinBox,
    QDialogButtonBox, QMessageBox, QTextEdit, QTabWidget,
    QGroupBox, QRadioButton
)

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
        self.id_edit.setPlaceholderText("自动生成")
        self.id_edit.setReadOnly(True)
        self.id_edit.setMinimumWidth(300)  # 设置最小宽度
        form_layout.addRow("实例ID:", self.id_edit)

        # 实例名称
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("给实例起个名字")
        self.name_edit.setMinimumWidth(300)  # 设置最小宽度
        form_layout.addRow("实例名称:", self.name_edit)

        # API地址
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("例如: http://localhost:8000")
        self.url_edit.setMinimumWidth(300)  # 设置最小宽度
        form_layout.addRow("API地址:", self.url_edit)

        # API密钥
        self.key_edit = QLineEdit()
        self.key_edit.setPlaceholderText("API密钥")
        self.key_edit.setMinimumWidth(300)  # 设置最小宽度
        form_layout.addRow("API密钥:", self.key_edit)

        # 高级选项
        self.advanced_group = QGroupBox("高级选项")
        advanced_layout = QFormLayout(self.advanced_group)

        # 超时时间
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(1, 300)
        self.timeout_spin.setValue(30)
        self.timeout_spin.setSuffix(" 秒")
        advanced_layout.addRow("超时时间:", self.timeout_spin)

        # 重试次数
        self.retry_spin = QSpinBox()
        self.retry_spin.setRange(0, 10)
        self.retry_spin.setValue(3)
        self.retry_spin.setSuffix(" 次")
        advanced_layout.addRow("重试次数:", self.retry_spin)

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

        # 生成一个初始ID
        self._generate_id()

    def _generate_id(self):
        """生成随机ID"""
        new_id = f"wxauto_{uuid.uuid4().hex[:8]}"
        self.id_edit.setText(new_id)

    def get_instance_data(self):
        """
        获取实例数据

        Returns:
            dict: 实例数据
        """
        # 基本数据
        data = {
            "instance_id": self.id_edit.text(),
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
