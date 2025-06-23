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
    QCheckBox, QTextEdit, QDialogButtonBox, QWidget, QStackedWidget,
    QMessageBox, QGroupBox, QRadioButton, QTableWidget, QTableWidgetItem,
    QHeaderView
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
        # 初始化原始API密钥为空字符串
        self.original_api_key = ""

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
        self.type_combo.addItem("关键词匹配", "keyword")
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        self.type_combo.setMinimumWidth(300)  # 设置最小宽度
        form_layout.addRow("平台类型:", self.type_combo)

        # 消息发送模式
        self.message_send_mode_group = QGroupBox("消息发送模式")
        message_send_mode_layout = QHBoxLayout()

        self.normal_mode_radio = QRadioButton("普通模式")
        self.typing_mode_radio = QRadioButton("打字机模式")
        self.normal_mode_radio.setChecked(True)  # 默认选择普通模式

        message_send_mode_layout.addWidget(self.normal_mode_radio)
        message_send_mode_layout.addWidget(self.typing_mode_radio)
        self.message_send_mode_group.setLayout(message_send_mode_layout)

        form_layout.addRow("", self.message_send_mode_group)

        main_layout.addLayout(form_layout)

        # 配置选项卡 - 使用堆叠小部件而不是标签页
        self.config_stack = QStackedWidget()

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
        self.dify_api_key.setEchoMode(QLineEdit.Password)  # 设置为密码模式
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

        self.config_stack.addWidget(self.dify_tab)

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
        self.openai_api_key.setEchoMode(QLineEdit.Password)  # 设置为密码模式
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

        self.config_stack.addWidget(self.openai_tab)

        # 关键词匹配配置选项卡
        self.keyword_match_tab = QWidget()
        keyword_match_layout = QVBoxLayout(self.keyword_match_tab)

        # 回复时间范围配置
        time_range_group = QGroupBox("回复时间范围（秒）")
        time_range_layout = QHBoxLayout()

        # 最小回复时间
        min_time_layout = QFormLayout()
        self.min_reply_time = QDoubleSpinBox()
        self.min_reply_time.setRange(0.1, 60.0)
        self.min_reply_time.setSingleStep(0.1)
        self.min_reply_time.setValue(1.0)
        self.min_reply_time.setDecimals(1)
        min_time_layout.addRow("最小值:", self.min_reply_time)

        # 最大回复时间
        max_time_layout = QFormLayout()
        self.max_reply_time = QDoubleSpinBox()
        self.max_reply_time.setRange(0.1, 60.0)
        self.max_reply_time.setSingleStep(0.1)
        self.max_reply_time.setValue(3.0)
        self.max_reply_time.setDecimals(1)
        max_time_layout.addRow("最大值:", self.max_reply_time)

        time_range_layout.addLayout(min_time_layout)
        time_range_layout.addLayout(max_time_layout)
        time_range_group.setLayout(time_range_layout)
        keyword_match_layout.addWidget(time_range_group)

        # 规则列表区域
        rules_group = QGroupBox("关键词规则")
        rules_layout = QVBoxLayout()

        # 规则列表
        self.rules_list = QTableWidget()
        self.rules_list.setColumnCount(3)
        self.rules_list.setHorizontalHeaderLabels(["关键词", "匹配类型", "操作"])
        self.rules_list.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.rules_list.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.rules_list.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.rules_list.setSelectionBehavior(QTableWidget.SelectRows)
        self.rules_list.setSelectionMode(QTableWidget.SingleSelection)
        self.rules_list.setEditTriggers(QTableWidget.NoEditTriggers)
        self.rules_list.verticalHeader().setVisible(False)
        self.rules_list.setMinimumHeight(200)
        rules_layout.addWidget(self.rules_list)

        # 规则编辑区域
        rule_edit_layout = QVBoxLayout()

        # 关键词输入
        keywords_layout = QFormLayout()
        self.keywords_edit = QLineEdit()
        self.keywords_edit.setPlaceholderText("输入关键词，多个关键词用逗号分隔")
        keywords_layout.addRow("关键词:", self.keywords_edit)
        rule_edit_layout.addLayout(keywords_layout)

        # 匹配类型选择
        match_type_layout = QFormLayout()
        self.match_type_combo = QComboBox()
        self.match_type_combo.addItem("完全匹配", "exact")
        self.match_type_combo.addItem("包含匹配", "contains")
        self.match_type_combo.addItem("模糊匹配", "fuzzy")
        match_type_layout.addRow("匹配类型:", self.match_type_combo)
        rule_edit_layout.addLayout(match_type_layout)

        # 随机回复选项
        random_reply_layout = QHBoxLayout()
        self.random_reply_check = QCheckBox("随机回复")
        random_reply_layout.addWidget(self.random_reply_check)
        random_reply_layout.addStretch()
        rule_edit_layout.addLayout(random_reply_layout)

        # 回复内容区域
        replies_layout = QVBoxLayout()
        replies_label = QLabel("回复内容:")
        replies_layout.addWidget(replies_label)

        # 回复内容列表
        self.replies_list = QTableWidget()
        self.replies_list.setColumnCount(2)
        self.replies_list.setHorizontalHeaderLabels(["回复内容", "操作"])
        self.replies_list.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.replies_list.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.replies_list.setSelectionBehavior(QTableWidget.SelectRows)
        self.replies_list.setSelectionMode(QTableWidget.SingleSelection)
        self.replies_list.setEditTriggers(QTableWidget.NoEditTriggers)
        self.replies_list.verticalHeader().setVisible(False)
        self.replies_list.setMinimumHeight(100)
        replies_layout.addWidget(self.replies_list)

        # 添加回复按钮和输入框
        add_reply_layout = QHBoxLayout()
        self.reply_edit = QLineEdit()
        self.reply_edit.setPlaceholderText("输入回复内容")
        add_reply_layout.addWidget(self.reply_edit)

        self.add_reply_btn = QPushButton("添加回复")
        self.add_reply_btn.clicked.connect(self._add_reply)
        add_reply_layout.addWidget(self.add_reply_btn)
        replies_layout.addLayout(add_reply_layout)

        rule_edit_layout.addLayout(replies_layout)

        # 添加规则按钮
        rule_buttons_layout = QHBoxLayout()
        rule_buttons_layout.addStretch()

        self.add_rule_btn = QPushButton("添加规则")
        self.add_rule_btn.clicked.connect(self._add_rule)
        rule_buttons_layout.addWidget(self.add_rule_btn)

        self.update_rule_btn = QPushButton("更新规则")
        self.update_rule_btn.clicked.connect(self._update_rule)
        self.update_rule_btn.setEnabled(False)
        rule_buttons_layout.addWidget(self.update_rule_btn)

        self.cancel_edit_btn = QPushButton("取消编辑")
        self.cancel_edit_btn.clicked.connect(self._cancel_edit_rule)
        self.cancel_edit_btn.setEnabled(False)
        rule_buttons_layout.addWidget(self.cancel_edit_btn)

        rule_edit_layout.addLayout(rule_buttons_layout)

        rules_layout.addLayout(rule_edit_layout)
        rules_group.setLayout(rules_layout)
        keyword_match_layout.addWidget(rules_group)

        # 删除规则按钮
        delete_rule_layout = QHBoxLayout()
        delete_rule_layout.addStretch()

        self.delete_rule_btn = QPushButton("删除规则")
        self.delete_rule_btn.clicked.connect(self._delete_rule)
        self.delete_rule_btn.setEnabled(False)
        delete_rule_layout.addWidget(self.delete_rule_btn)

        keyword_match_layout.addLayout(delete_rule_layout)

        # 添加关键词匹配选项卡
        self.config_stack.addWidget(self.keyword_match_tab)

        # 初始化规则列表和回复列表
        self.rules = []
        self.current_rule_index = -1
        self.replies = []

        # 连接规则列表选择事件
        self.rules_list.itemSelectionChanged.connect(self._on_rule_selected)

        main_layout.addWidget(self.config_stack)

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
        # 切换到相应的配置页面
        self.config_stack.setCurrentIndex(index)

    def _add_reply(self):
        """添加回复内容"""
        reply_text = self.reply_edit.text().strip()
        if not reply_text:
            QMessageBox.warning(self, "错误", "请输入回复内容")
            return

        # 添加到回复列表
        self.replies.append(reply_text)

        # 更新回复列表UI
        self._update_replies_list()

        # 清空输入框
        self.reply_edit.clear()

    def _update_replies_list(self):
        """更新回复列表UI"""
        self.replies_list.setRowCount(0)

        for i, reply in enumerate(self.replies):
            self.replies_list.insertRow(i)

            # 回复内容
            reply_item = QTableWidgetItem(reply)
            self.replies_list.setItem(i, 0, reply_item)

            # 删除按钮
            delete_btn = QPushButton("删除")
            delete_btn.setProperty("row", i)
            delete_btn.clicked.connect(self._delete_reply)

            self.replies_list.setCellWidget(i, 1, delete_btn)

    def _delete_reply(self):
        """删除回复内容"""
        sender = self.sender()
        if sender:
            row = sender.property("row")
            if row is not None and 0 <= row < len(self.replies):
                # 从列表中删除
                del self.replies[row]

                # 更新UI
                self._update_replies_list()

    def _add_rule(self):
        """添加规则"""
        # 验证输入
        keywords_text = self.keywords_edit.text().strip()
        if not keywords_text:
            QMessageBox.warning(self, "错误", "请输入关键词")
            return

        if not self.replies:
            QMessageBox.warning(self, "错误", "请添加至少一条回复内容")
            return

        # 解析关键词
        keywords = [k.strip() for k in keywords_text.split(",") if k.strip()]

        # 获取匹配类型
        match_type = self.match_type_combo.currentData()

        # 是否随机回复
        is_random_reply = self.random_reply_check.isChecked()

        # 创建规则
        rule = {
            "keywords": keywords,
            "match_type": match_type,
            "is_random_reply": is_random_reply,
            "replies": self.replies.copy(),
            "min_reply_time": self.min_reply_time.value(),
            "max_reply_time": self.max_reply_time.value()
        }

        # 添加到规则列表
        self.rules.append(rule)

        # 更新规则列表UI
        self._update_rules_list()

        # 清空输入
        self._clear_rule_inputs()

    def _update_rule(self):
        """更新规则"""
        if self.current_rule_index < 0 or self.current_rule_index >= len(self.rules):
            return

        # 验证输入
        keywords_text = self.keywords_edit.text().strip()
        if not keywords_text:
            QMessageBox.warning(self, "错误", "请输入关键词")
            return

        if not self.replies:
            QMessageBox.warning(self, "错误", "请添加至少一条回复内容")
            return

        # 解析关键词
        keywords = [k.strip() for k in keywords_text.split(",") if k.strip()]

        # 获取匹配类型
        match_type = self.match_type_combo.currentData()

        # 是否随机回复
        is_random_reply = self.random_reply_check.isChecked()

        # 更新规则
        self.rules[self.current_rule_index] = {
            "keywords": keywords,
            "match_type": match_type,
            "is_random_reply": is_random_reply,
            "replies": self.replies.copy(),
            "min_reply_time": self.min_reply_time.value(),
            "max_reply_time": self.max_reply_time.value()
        }

        # 更新规则列表UI
        self._update_rules_list()

        # 清空输入并重置编辑状态
        self._clear_rule_inputs()
        self.current_rule_index = -1
        self.update_rule_btn.setEnabled(False)
        self.cancel_edit_btn.setEnabled(False)
        self.add_rule_btn.setEnabled(True)
        self.delete_rule_btn.setEnabled(False)

    def _cancel_edit_rule(self):
        """取消编辑规则"""
        self._clear_rule_inputs()
        self.current_rule_index = -1
        self.update_rule_btn.setEnabled(False)
        self.cancel_edit_btn.setEnabled(False)
        self.add_rule_btn.setEnabled(True)
        self.delete_rule_btn.setEnabled(False)

    def _clear_rule_inputs(self):
        """清空规则输入"""
        self.keywords_edit.clear()
        self.match_type_combo.setCurrentIndex(0)
        self.random_reply_check.setChecked(False)
        self.replies = []
        self._update_replies_list()

    def _update_rules_list(self):
        """更新规则列表UI"""
        self.rules_list.setRowCount(0)

        for i, rule in enumerate(self.rules):
            self.rules_list.insertRow(i)

            # 关键词
            keywords_text = ", ".join(rule["keywords"])
            keywords_item = QTableWidgetItem(keywords_text)
            self.rules_list.setItem(i, 0, keywords_item)

            # 匹配类型
            match_type = rule["match_type"]
            match_type_text = "完全匹配"
            if match_type == "contains":
                match_type_text = "包含匹配"
            elif match_type == "fuzzy":
                match_type_text = "模糊匹配"
            match_type_item = QTableWidgetItem(match_type_text)
            self.rules_list.setItem(i, 1, match_type_item)

            # 编辑按钮
            edit_btn = QPushButton("编辑")
            edit_btn.setProperty("row", i)
            edit_btn.clicked.connect(self._edit_rule)

            self.rules_list.setCellWidget(i, 2, edit_btn)

    def _edit_rule(self):
        """编辑规则"""
        sender = self.sender()
        if sender:
            row = sender.property("row")
            if row is not None and 0 <= row < len(self.rules):
                # 加载规则数据
                rule = self.rules[row]

                # 设置关键词
                self.keywords_edit.setText(", ".join(rule["keywords"]))

                # 设置匹配类型
                match_type = rule["match_type"]
                if match_type == "exact":
                    self.match_type_combo.setCurrentIndex(0)
                elif match_type == "contains":
                    self.match_type_combo.setCurrentIndex(1)
                elif match_type == "fuzzy":
                    self.match_type_combo.setCurrentIndex(2)

                # 设置随机回复
                self.random_reply_check.setChecked(rule["is_random_reply"])

                # 设置回复内容
                self.replies = rule["replies"].copy()
                self._update_replies_list()

                # 设置编辑状态
                self.current_rule_index = row
                self.update_rule_btn.setEnabled(True)
                self.cancel_edit_btn.setEnabled(True)
                self.add_rule_btn.setEnabled(False)
                self.delete_rule_btn.setEnabled(True)

                # 选中规则行
                self.rules_list.selectRow(row)

    def _delete_rule(self):
        """删除规则"""
        if self.current_rule_index < 0 or self.current_rule_index >= len(self.rules):
            return

        # 确认删除
        reply = QMessageBox.question(
            self,
            "确认删除",
            "确定要删除选中的规则吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # 从列表中删除
            del self.rules[self.current_rule_index]

            # 更新UI
            self._update_rules_list()

            # 重置编辑状态
            self._clear_rule_inputs()
            self.current_rule_index = -1
            self.update_rule_btn.setEnabled(False)
            self.cancel_edit_btn.setEnabled(False)
            self.add_rule_btn.setEnabled(True)
            self.delete_rule_btn.setEnabled(False)

    def _on_rule_selected(self):
        """规则选择事件"""
        selected_items = self.rules_list.selectedItems()
        if selected_items:
            row = selected_items[0].row()
            if 0 <= row < len(self.rules):
                # 设置当前规则索引
                self.current_rule_index = row
                self.delete_rule_btn.setEnabled(True)

                # 加载规则数据
                self._edit_rule()
        else:
            self.delete_rule_btn.setEnabled(False)

    def _load_platform_data(self):
        """加载平台数据"""
        if not self.platform_data:
            return

        # 设置平台名称
        self.name_edit.setText(self.platform_data.get("name", ""))

        # 设置平台类型
        platform_type = self.platform_data.get("type", "dify")
        if platform_type == "dify":
            index = 0
        elif platform_type == "openai":
            index = 1
        elif platform_type == "keyword" or platform_type == "keyword_match":
            index = 2
        else:
            index = 0
        self.type_combo.setCurrentIndex(index)

        # 禁用平台类型选择（编辑模式下不允许修改类型）
        self.type_combo.setEnabled(False)

        # 获取配置
        config = self.platform_data.get("config", {})

        # 加载消息发送模式
        message_send_mode = config.get("message_send_mode", "normal")
        if message_send_mode == "typing":
            self.typing_mode_radio.setChecked(True)
        else:
            self.normal_mode_radio.setChecked(True)

        # 根据平台类型加载配置
        if platform_type == "dify":
            self.dify_api_base.setText(config.get("api_base", ""))
            # 设置API密钥为掩码，实际值会在保存时处理
            self.dify_api_key.setText("******")
            # 保存原始API密钥，用于后续处理
            self.original_api_key = config.get("api_key", "")
            self.dify_conversation_id.setText(config.get("conversation_id", ""))
            self.dify_user_id.setText(config.get("user_id", ""))
        elif platform_type == "openai":
            self.openai_api_base.setText(config.get("api_base", ""))
            # 设置API密钥为掩码，实际值会在保存时处理
            self.openai_api_key.setText("******")
            # 保存原始API密钥，用于后续处理
            self.original_api_key = config.get("api_key", "")
            self.openai_model.setText(config.get("model", "gpt-3.5-turbo"))

            # 处理temperature字段，可能是字符串或数字
            temperature = config.get("temperature", 0.7)
            if isinstance(temperature, str):
                try:
                    temperature = float(temperature)
                except (ValueError, TypeError):
                    temperature = 0.7
            self.openai_temperature.setValue(temperature)

            self.openai_system_prompt.setPlainText(config.get("system_prompt", ""))

            # 处理max_tokens字段，可能是字符串或数字
            max_tokens = config.get("max_tokens", 1000)
            if isinstance(max_tokens, str):
                try:
                    max_tokens = int(max_tokens)
                except (ValueError, TypeError):
                    max_tokens = 1000
            self.openai_max_tokens.setValue(max_tokens)
        elif platform_type == "keyword" or platform_type == "keyword_match":
            # 加载关键词匹配配置
            self.min_reply_time.setValue(config.get("min_reply_time", 1.0))
            self.max_reply_time.setValue(config.get("max_reply_time", 3.0))

            # 加载规则
            self.rules = config.get("rules", []).copy()
            self._update_rules_list()

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

        # 获取消息发送模式
        message_send_mode = "typing" if self.typing_mode_radio.isChecked() else "normal"

        if platform_type == "dify":
            # 获取API密钥，如果是掩码且在编辑模式下，则使用原始值
            api_key = self.dify_api_key.text().strip()
            if self.is_edit_mode and api_key == "******" and hasattr(self, 'original_api_key'):
                api_key = self.original_api_key
                logger.info("使用原始API密钥而不是掩码值")

            config = {
                "api_base": self.dify_api_base.text().strip(),
                "api_key": api_key,
                "conversation_id": self.dify_conversation_id.text().strip(),
                "user_id": self.dify_user_id.text().strip() or "default_user",
                "message_send_mode": message_send_mode
            }
        elif platform_type == "openai":
            # 获取API密钥，如果是掩码且在编辑模式下，则使用原始值
            api_key = self.openai_api_key.text().strip()
            if self.is_edit_mode and api_key == "******" and hasattr(self, 'original_api_key'):
                api_key = self.original_api_key
                logger.info("使用原始API密钥而不是掩码值")

            config = {
                "api_base": self.openai_api_base.text().strip() or "https://api.openai.com/v1",
                "api_key": api_key,
                "model": self.openai_model.text().strip() or "gpt-3.5-turbo",
                "temperature": self.openai_temperature.value(),
                "system_prompt": self.openai_system_prompt.toPlainText().strip() or "你是一个有用的助手。",
                "max_tokens": self.openai_max_tokens.value(),
                "message_send_mode": message_send_mode
            }
        elif platform_type == "keyword":
            # 获取关键词匹配配置
            config = {
                "min_reply_time": self.min_reply_time.value(),
                "max_reply_time": self.max_reply_time.value(),
                "rules": self.rules,
                "message_send_mode": message_send_mode
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
                self.config_stack.setCurrentIndex(0)
                self.dify_api_base.setFocus()
                return False

            # 验证API密钥
            if not self.dify_api_key.text().strip():
                QMessageBox.warning(self, "错误", "请输入Dify API密钥")
                self.config_stack.setCurrentIndex(0)
                self.dify_api_key.setFocus()
                return False
        elif platform_type == "openai":
            # 验证API密钥
            if not self.openai_api_key.text().strip():
                QMessageBox.warning(self, "错误", "请输入OpenAI API密钥")
                self.config_stack.setCurrentIndex(1)
                self.openai_api_key.setFocus()
                return False

            # 验证模型
            if not self.openai_model.text().strip():
                QMessageBox.warning(self, "错误", "请输入OpenAI模型")
                self.config_stack.setCurrentIndex(1)
                self.openai_model.setFocus()
                return False
        elif platform_type == "keyword":
            # 验证回复时间范围
            min_time = self.min_reply_time.value()
            max_time = self.max_reply_time.value()

            if min_time <= 0:
                QMessageBox.warning(self, "错误", "最小回复时间必须大于0")
                self.config_stack.setCurrentIndex(2)
                self.min_reply_time.setFocus()
                return False

            if max_time <= 0:
                QMessageBox.warning(self, "错误", "最大回复时间必须大于0")
                self.config_stack.setCurrentIndex(2)
                self.max_reply_time.setFocus()
                return False

            if min_time > max_time:
                QMessageBox.warning(self, "错误", "最小回复时间不能大于最大回复时间")
                self.config_stack.setCurrentIndex(2)
                self.min_reply_time.setFocus()
                return False

            # 验证规则列表
            if not self.rules:
                QMessageBox.warning(self, "错误", "请添加至少一条关键词规则")
                self.config_stack.setCurrentIndex(2)
                self.keywords_edit.setFocus()
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
