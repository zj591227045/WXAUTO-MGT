"""
服务平台添加/编辑对话框

该模块提供了添加和编辑服务平台的对话框界面。
"""

import logging
import asyncio
import json
from typing import Dict, List, Optional, Any

from PySide6.QtCore import Qt, Signal, Slot, QSize, QTimer, QMetaObject, Q_ARG
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFormLayout, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox,
    QCheckBox, QTabWidget, QTextEdit, QDialogButtonBox, QWidget,
    QMessageBox, QGroupBox
)

from wxauto_mgt.core.service_platform_manager import platform_manager
from wxauto_mgt.utils.logging import get_logger
from qasync import asyncSlot

logger = get_logger()

class AddEditPlatformDialog(QDialog):
    """添加/编辑服务平台对话框"""

    def __init__(self, parent=None, platform_data=None):
        """
        初始化对话框

        Args:
            parent: 父窗口
            platform_data: 平台数据，如果为None则为添加模式，否则为编辑模式
        """
        super().__init__(parent)

        self.platform_data = platform_data
        self.is_edit_mode = platform_data is not None

        self._init_ui()

        if self.is_edit_mode:
            self._load_platform_data()
            self.setWindowTitle("编辑服务平台")
        else:
            self.setWindowTitle("添加服务平台")

        # 设置对话框大小
        self.resize(500, 500)

    def _init_ui(self):
        """初始化UI"""
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # 表单布局
        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignRight)
        form_layout.setSpacing(10)

        # 平台名称
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("请输入平台名称")
        self.name_edit.setMinimumWidth(300)  # 设置最小宽度
        form_layout.addRow("平台名称:", self.name_edit)

        # 平台类型
        self.type_combo = QComboBox()
        self.type_combo.addItem("Dify", "dify")
        self.type_combo.addItem("OpenAI", "openai")
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        self.type_combo.setMinimumWidth(300)  # 设置最小宽度
        form_layout.addRow("平台类型:", self.type_combo)

        main_layout.addLayout(form_layout)

        # 配置选项卡
        self.config_tabs = QTabWidget()

        # Dify配置选项卡
        self.dify_tab = QWidget()
        dify_layout = QFormLayout(self.dify_tab)
        dify_layout.setLabelAlignment(Qt.AlignRight)
        dify_layout.setSpacing(10)

        # Dify API基础URL
        self.dify_api_base = QLineEdit()
        self.dify_api_base.setPlaceholderText("例如: http://10.255.0.62/v1")
        self.dify_api_base.setMinimumWidth(300)  # 设置最小宽度
        dify_layout.addRow("API基础URL:", self.dify_api_base)

        # Dify API密钥
        self.dify_api_key = QLineEdit()
        self.dify_api_key.setPlaceholderText("例如: app-o5gCcjyOUnlnVkgwXgQeGHoK")
        self.dify_api_key.setMinimumWidth(300)  # 设置最小宽度
        dify_layout.addRow("API密钥:", self.dify_api_key)

        # Dify会话ID（可选）
        self.dify_conversation_id = QLineEdit()
        self.dify_conversation_id.setPlaceholderText("可选")
        self.dify_conversation_id.setMinimumWidth(300)  # 设置最小宽度
        dify_layout.addRow("会话ID (可选):", self.dify_conversation_id)

        # Dify用户ID（可选）
        self.dify_user_id = QLineEdit()
        self.dify_user_id.setPlaceholderText("可选，默认为default_user")
        self.dify_user_id.setMinimumWidth(300)  # 设置最小宽度
        dify_layout.addRow("用户ID (可选):", self.dify_user_id)

        self.config_tabs.addTab(self.dify_tab, "Dify配置")

        # OpenAI配置选项卡
        self.openai_tab = QWidget()
        openai_layout = QFormLayout(self.openai_tab)
        openai_layout.setLabelAlignment(Qt.AlignRight)
        openai_layout.setSpacing(10)

        # OpenAI API基础URL
        self.openai_api_base = QLineEdit()
        self.openai_api_base.setPlaceholderText("可选，默认为https://api.openai.com/v1")
        self.openai_api_base.setMinimumWidth(300)  # 设置最小宽度
        openai_layout.addRow("API基础URL (可选):", self.openai_api_base)

        # OpenAI API密钥
        self.openai_api_key = QLineEdit()
        self.openai_api_key.setPlaceholderText("例如: sk-...")
        self.openai_api_key.setMinimumWidth(300)  # 设置最小宽度
        openai_layout.addRow("API密钥:", self.openai_api_key)

        # OpenAI模型
        self.openai_model = QLineEdit()
        self.openai_model.setPlaceholderText("例如: gpt-3.5-turbo")
        self.openai_model.setText("gpt-3.5-turbo")
        self.openai_model.setMinimumWidth(300)  # 设置最小宽度
        openai_layout.addRow("模型:", self.openai_model)

        # OpenAI温度
        self.openai_temperature = QDoubleSpinBox()
        self.openai_temperature.setRange(0.0, 2.0)
        self.openai_temperature.setSingleStep(0.1)
        self.openai_temperature.setValue(0.7)
        openai_layout.addRow("温度:", self.openai_temperature)

        # OpenAI系统提示
        self.openai_system_prompt = QTextEdit()
        self.openai_system_prompt.setPlaceholderText("可选，默认为'你是一个有用的助手。'")
        self.openai_system_prompt.setMaximumHeight(100)
        self.openai_system_prompt.setMinimumWidth(300)  # 设置最小宽度
        openai_layout.addRow("系统提示:", self.openai_system_prompt)

        # OpenAI最大令牌数
        self.openai_max_tokens = QSpinBox()
        self.openai_max_tokens.setRange(1, 4096)
        self.openai_max_tokens.setValue(1000)
        openai_layout.addRow("最大令牌数:", self.openai_max_tokens)

        self.config_tabs.addTab(self.openai_tab, "OpenAI配置")

        main_layout.addWidget(self.config_tabs)

        # 测试连接按钮
        self.test_btn = QPushButton("测试连接")
        self.test_btn.setStyleSheet("""
            QPushButton {
                background-color: #52c41a;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #73d13d;
            }
        """)
        self.test_btn.clicked.connect(self._test_connection)

        # 按钮布局
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.test_btn)
        button_layout.addStretch()

        # 标准按钮
        self.button_box = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        button_layout.addWidget(self.button_box)

        main_layout.addLayout(button_layout)

        # 根据平台类型显示相应的选项卡
        self._on_type_changed(0)

    def _on_type_changed(self, index):
        """
        平台类型变化事件

        Args:
            index: 选项索引
        """
        # 切换到相应的选项卡
        self.config_tabs.setCurrentIndex(index)

    def _load_platform_data(self):
        """加载平台数据"""
        if not self.platform_data:
            return

        # 设置平台名称
        self.name_edit.setText(self.platform_data.get("name", ""))

        # 设置平台类型
        platform_type = self.platform_data.get("type", "dify")
        index = 0 if platform_type == "dify" else 1
        self.type_combo.setCurrentIndex(index)

        # 禁用平台类型选择（编辑模式下不允许修改类型）
        self.type_combo.setEnabled(False)

        # 获取配置
        config = self.platform_data.get("config", {})

        # 根据平台类型加载配置
        if platform_type == "dify":
            self.dify_api_base.setText(config.get("api_base", ""))
            self.dify_api_key.setText(config.get("api_key", ""))
            self.dify_conversation_id.setText(config.get("conversation_id", ""))
            self.dify_user_id.setText(config.get("user_id", ""))
        else:  # openai
            self.openai_api_base.setText(config.get("api_base", ""))
            self.openai_api_key.setText(config.get("api_key", ""))
            self.openai_model.setText(config.get("model", "gpt-3.5-turbo"))
            self.openai_temperature.setValue(config.get("temperature", 0.7))
            self.openai_system_prompt.setPlainText(config.get("system_prompt", ""))
            self.openai_max_tokens.setValue(config.get("max_tokens", 1000))

    def get_platform_data(self) -> Dict[str, Any]:
        """
        获取平台数据

        Returns:
            Dict[str, Any]: 平台数据
        """
        # 获取平台类型
        platform_type = self.type_combo.currentData()

        # 获取配置
        config = {}

        if platform_type == "dify":
            config = {
                "api_base": self.dify_api_base.text().strip(),
                "api_key": self.dify_api_key.text().strip(),
                "conversation_id": self.dify_conversation_id.text().strip(),
                "user_id": self.dify_user_id.text().strip() or "default_user"
            }
        else:  # openai
            config = {
                "api_base": self.openai_api_base.text().strip() or "https://api.openai.com/v1",
                "api_key": self.openai_api_key.text().strip(),
                "model": self.openai_model.text().strip() or "gpt-3.5-turbo",
                "temperature": self.openai_temperature.value(),
                "system_prompt": self.openai_system_prompt.toPlainText().strip() or "你是一个有用的助手。",
                "max_tokens": self.openai_max_tokens.value()
            }

        # 返回平台数据
        return {
            "name": self.name_edit.text().strip(),
            "type": platform_type,
            "config": config
        }

    def accept(self):
        """确认按钮点击事件"""
        # 验证输入
        if not self._validate_input():
            return

        # 调用父类方法
        super().accept()

    def _validate_input(self) -> bool:
        """
        验证输入

        Returns:
            bool: 是否验证通过
        """
        # 验证平台名称
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "错误", "请输入平台名称")
            self.name_edit.setFocus()
            return False

        # 获取平台类型
        platform_type = self.type_combo.currentData()

        # 根据平台类型验证配置
        if platform_type == "dify":
            # 验证API基础URL
            if not self.dify_api_base.text().strip():
                QMessageBox.warning(self, "错误", "请输入Dify API基础URL")
                self.config_tabs.setCurrentIndex(0)
                self.dify_api_base.setFocus()
                return False

            # 验证API密钥
            if not self.dify_api_key.text().strip():
                QMessageBox.warning(self, "错误", "请输入Dify API密钥")
                self.config_tabs.setCurrentIndex(0)
                self.dify_api_key.setFocus()
                return False
        else:  # openai
            # 验证API密钥
            if not self.openai_api_key.text().strip():
                QMessageBox.warning(self, "错误", "请输入OpenAI API密钥")
                self.config_tabs.setCurrentIndex(1)
                self.openai_api_key.setFocus()
                return False

            # 验证模型
            if not self.openai_model.text().strip():
                QMessageBox.warning(self, "错误", "请输入OpenAI模型")
                self.config_tabs.setCurrentIndex(1)
                self.openai_model.setFocus()
                return False

        return True

    @asyncSlot()
    async def _test_connection(self):
        """测试连接"""
        # 验证输入
        if not self._validate_input():
            return

        try:
            # 获取平台数据
            platform_data = self.get_platform_data()

            # 创建临时平台实例
            from wxauto_mgt.core.service_platform import create_platform

            platform = create_platform(
                platform_data["type"],
                "temp_platform",
                platform_data["name"],
                platform_data["config"]
            )

            if not platform:
                QMessageBox.warning(self, "错误", "创建平台实例失败")
                return

            # 初始化平台
            if not await platform.initialize():
                QMessageBox.warning(self, "错误", "初始化平台失败")
                return

            # 测试连接
            result = await platform.test_connection()

            if not result.get("error"):
                QMessageBox.information(self, "成功", "连接测试成功")
            else:
                error_msg = result.get("error", "未知错误")
                QMessageBox.warning(self, "错误", f"连接测试失败: {error_msg}")

        except Exception as e:
            logger.error(f"测试连接失败: {e}")
            QMessageBox.warning(self, "错误", f"测试连接失败: {str(e)}")
