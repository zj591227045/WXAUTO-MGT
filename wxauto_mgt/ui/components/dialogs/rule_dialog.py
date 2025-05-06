"""
消息转发规则添加/编辑对话框

该模块提供了添加和编辑消息转发规则的对话框界面。
"""

import logging
import asyncio
import json
from typing import Dict, List, Optional, Any

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFormLayout, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox,
    QCheckBox, QTabWidget, QTextEdit, QDialogButtonBox, QWidget,
    QMessageBox, QGroupBox, QRadioButton, QSlider
)

from wxauto_mgt.core.service_platform_manager import platform_manager, rule_manager
from wxauto_mgt.core.api_client import instance_manager
from wxauto_mgt.utils.logging import get_logger
from qasync import asyncSlot

logger = get_logger(__name__)

class AddEditRuleDialog(QDialog):
    """添加/编辑消息转发规则对话框"""

    def __init__(self, parent=None, rule_data=None, current_instance_id=None):
        """
        初始化对话框

        Args:
            parent: 父窗口
            rule_data: 规则数据，如果为None则为添加模式，否则为编辑模式
            current_instance_id: 当前选中的实例ID，用于预设实例选择
        """
        super().__init__(parent)

        self.rule_data = rule_data
        self.is_edit_mode = rule_data is not None
        self.current_instance_id = current_instance_id

        self._init_ui()

        if self.is_edit_mode:
            self._load_rule_data()
            self.setWindowTitle("编辑消息转发规则")
        else:
            self.setWindowTitle("添加消息转发规则")

            # 如果有当前实例ID，预设实例选择
            if current_instance_id and current_instance_id != "*":
                self.specific_instance_radio.setChecked(True)
                self._on_instance_scope_changed()
                # 异步加载实例后设置当前实例
                self._set_current_instance_later()

        # 设置对话框大小
        self.resize(500, 600)

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

        # 规则名称
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("请输入规则名称")
        self.name_edit.setMinimumWidth(300)  # 设置最小宽度
        form_layout.addRow("规则名称:", self.name_edit)

        # 实例选择
        instance_group = QGroupBox("适用实例:")
        instance_layout = QVBoxLayout(instance_group)

        # 所有实例选项
        self.all_instances_radio = QRadioButton("所有实例")
        instance_layout.addWidget(self.all_instances_radio)

        # 特定实例选项
        specific_layout = QHBoxLayout()
        self.specific_instance_radio = QRadioButton("特定实例:")
        specific_layout.addWidget(self.specific_instance_radio)

        self.instance_combo = QComboBox()
        self.instance_combo.setEnabled(False)  # 初始禁用
        self.instance_combo.setMinimumWidth(200)  # 设置最小宽度
        specific_layout.addWidget(self.instance_combo)

        instance_layout.addLayout(specific_layout)

        # 连接单选按钮信号
        self.all_instances_radio.toggled.connect(self._on_instance_scope_changed)
        self.specific_instance_radio.toggled.connect(self._on_instance_scope_changed)

        # 默认选择"所有实例"
        self.all_instances_radio.setChecked(True)

        form_layout.addRow("", instance_group)

        # 聊天对象匹配
        self.chat_pattern_edit = QLineEdit()
        self.chat_pattern_edit.setPlaceholderText("支持精确匹配、* 或 regex:正则表达式，多个对象用逗号分隔")
        self.chat_pattern_edit.setMinimumWidth(300)  # 设置最小宽度
        form_layout.addRow("聊天对象匹配:", self.chat_pattern_edit)

        # 添加提示标签
        pattern_hint = QLabel("支持三种匹配模式：\n1. 精确匹配：输入完整的聊天对象名称，多个对象用逗号分隔\n2. 通配符：输入 * 匹配所有聊天对象\n3. 正则表达式：输入 regex: 开头，后跟正则表达式")
        pattern_hint.setStyleSheet("color: #666666; font-size: 12px;")
        form_layout.addRow("", pattern_hint)

        # 群消息@设置
        at_group = QGroupBox("群消息@设置:")
        at_layout = QVBoxLayout(at_group)

        # 仅响应@消息复选框
        self.only_at_messages_check = QCheckBox("仅响应@的消息")
        self.only_at_messages_check.setToolTip("勾选后，只有当消息中包含@指定名称时才会处理")
        self.only_at_messages_check.stateChanged.connect(self._on_only_at_messages_changed)
        at_layout.addWidget(self.only_at_messages_check)

        # @名称输入框
        at_name_layout = QHBoxLayout()
        at_name_layout.setContentsMargins(20, 0, 0, 0)  # 左侧缩进

        at_name_label = QLabel("@名称:")
        at_name_layout.addWidget(at_name_label)

        self.at_name_edit = QLineEdit()
        self.at_name_edit.setPlaceholderText("输入被@的名称，多个名称用逗号分隔")
        # 初始状态下不禁用，让用户可以输入
        self.at_name_edit.setEnabled(True)
        at_name_layout.addWidget(self.at_name_edit)

        at_layout.addLayout(at_name_layout)

        # 回复时@发送者复选框
        self.reply_at_sender_check = QCheckBox("回复时@发送者")
        self.reply_at_sender_check.setToolTip("勾选后，回复消息时会自动@消息发送者")
        at_layout.addWidget(self.reply_at_sender_check)

        # 添加提示标签
        at_hint = QLabel("注意: 勾选此选项后，聊天对象必须为群聊，且消息内容中必须包含\"@名称\"才会处理\n支持多个@名称，用逗号分隔，消息中包含任意一个名称即可触发")
        at_hint.setStyleSheet("color: #666666; font-size: 12px;")
        at_layout.addWidget(at_hint)

        form_layout.addRow("", at_group)

        # 服务平台
        self.platform_combo = QComboBox()
        self.platform_combo.setMinimumWidth(300)  # 设置最小宽度
        form_layout.addRow("服务平台:", self.platform_combo)

        # 优先级
        priority_group = QGroupBox("优先级设置:")
        priority_layout = QVBoxLayout(priority_group)

        # 优先级数值输入
        priority_input_layout = QHBoxLayout()
        self.priority_spin = QSpinBox()
        self.priority_spin.setRange(0, 100)
        self.priority_spin.setValue(0)
        self.priority_spin.valueChanged.connect(self._on_priority_changed)
        priority_input_layout.addWidget(self.priority_spin)

        # 上下调整按钮
        up_down_layout = QVBoxLayout()
        up_down_layout.setSpacing(2)

        self.priority_up_btn = QPushButton("▲")
        self.priority_up_btn.setFixedSize(24, 24)
        self.priority_up_btn.clicked.connect(self._increase_priority)
        up_down_layout.addWidget(self.priority_up_btn)

        self.priority_down_btn = QPushButton("▼")
        self.priority_down_btn.setFixedSize(24, 24)
        self.priority_down_btn.clicked.connect(self._decrease_priority)
        up_down_layout.addWidget(self.priority_down_btn)

        priority_input_layout.addLayout(up_down_layout)
        priority_layout.addLayout(priority_input_layout)

        # 优先级滑块
        slider_layout = QHBoxLayout()
        slider_layout.setContentsMargins(10, 0, 10, 0)

        low_label = QLabel("0")
        low_label.setAlignment(Qt.AlignLeft)
        slider_layout.addWidget(low_label)

        self.priority_slider = QSlider(Qt.Horizontal)
        self.priority_slider.setRange(0, 100)
        self.priority_slider.setValue(0)
        self.priority_slider.valueChanged.connect(self._on_slider_changed)
        slider_layout.addWidget(self.priority_slider)

        high_label = QLabel("100")
        high_label.setAlignment(Qt.AlignRight)
        slider_layout.addWidget(high_label)

        priority_layout.addLayout(slider_layout)

        # 优先级标签
        labels_layout = QHBoxLayout()
        labels_layout.setContentsMargins(10, 0, 10, 0)

        low_priority = QLabel("低优先级")
        low_priority.setAlignment(Qt.AlignLeft)
        low_priority.setStyleSheet("color: #1890ff;")
        labels_layout.addWidget(low_priority)

        labels_layout.addStretch()

        high_priority = QLabel("高优先级")
        high_priority.setAlignment(Qt.AlignRight)
        high_priority.setStyleSheet("color: #f5222d;")
        labels_layout.addWidget(high_priority)

        priority_layout.addLayout(labels_layout)

        # 优先级提示
        priority_hint = QLabel("提示: 数字越大优先级越高。推荐值:\n默认规则: 0-19, 普通规则: 20-49, 重要规则: 50-79, 关键规则: 80-100")
        priority_hint.setStyleSheet("color: #666666; font-size: 12px;")
        priority_layout.addWidget(priority_hint)

        form_layout.addRow("", priority_group)

        main_layout.addLayout(form_layout)

        # 按钮布局
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        # 标准按钮
        self.button_box = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        button_layout.addWidget(self.button_box)

        main_layout.addLayout(button_layout)

        # 使用定时器延迟加载实例和平台列表，避免直接创建异步任务
        QTimer.singleShot(100, self._delayed_load_data)

    def _delayed_load_data(self):
        """延迟加载数据，避免直接在构造函数中创建异步任务"""
        # 使用asyncSlot装饰器处理异步调用
        self._load_data_async()

    @asyncSlot()
    async def _load_data_async(self):
        """异步加载数据"""
        try:
            # 先加载实例列表
            await self._load_instances()
            # 再加载平台列表
            await self._load_platforms()
        except Exception as e:
            logger.error(f"加载数据失败: {e}")

    def _on_instance_scope_changed(self):
        """实例范围选择变化事件"""
        self.instance_combo.setEnabled(self.specific_instance_radio.isChecked())

    def _on_only_at_messages_changed(self, state):
        """
        仅响应@消息复选框状态变化事件

        Args:
            state: 复选框状态
        """
        # 获取复选框是否被选中
        is_checked = self.only_at_messages_check.isChecked()

        # 启用或禁用@名称输入框
        self.at_name_edit.setEnabled(is_checked)

        # 输出调试信息
        logger.debug(f"复选框状态变化: {state}, 是否选中: {is_checked}, 输入框是否启用: {self.at_name_edit.isEnabled()}")

    def _on_priority_changed(self, value):
        """
        优先级数值变化事件

        Args:
            value: 优先级值
        """
        # 更新滑块值
        self.priority_slider.setValue(value)

        # 根据优先级值设置颜色
        if value >= 80:
            self.priority_spin.setStyleSheet("color: #f5222d;")  # 高优先级 - 红色
        elif value >= 50:
            self.priority_spin.setStyleSheet("color: #fa8c16;")  # 中高优先级 - 橙色
        elif value >= 20:
            self.priority_spin.setStyleSheet("color: #52c41a;")  # 中优先级 - 绿色
        else:
            self.priority_spin.setStyleSheet("color: #1890ff;")  # 低优先级 - 蓝色

    def _on_slider_changed(self, value):
        """
        优先级滑块变化事件

        Args:
            value: 滑块值
        """
        # 更新数值输入框
        self.priority_spin.setValue(value)

    def _increase_priority(self):
        """增加优先级"""
        self.priority_spin.setValue(self.priority_spin.value() + 1)

    def _decrease_priority(self):
        """减少优先级"""
        self.priority_spin.setValue(self.priority_spin.value() - 1)

    async def _load_instances(self):
        """加载实例列表"""
        try:
            # 从数据库加载实例
            from wxauto_mgt.data.db_manager import db_manager
            instances = await db_manager.fetchall("SELECT * FROM instances WHERE enabled = 1")

            # 准备实例数据
            instance_data = []
            for instance in instances:
                instance_id = instance.get("instance_id", "")
                instance_name = instance.get("name", instance_id)
                instance_data.append((instance_name, instance_id))

            # 在主线程中更新UI
            def update_ui():
                try:
                    # 清空下拉框
                    self.instance_combo.clear()

                    # 添加实例到下拉框
                    for name, id in instance_data:
                        self.instance_combo.addItem(name, id)

                    # 如果是编辑模式且有当前实例ID，设置选中项
                    if self.is_edit_mode and self.rule_data and self.rule_data.get("instance_id") != "*":
                        instance_id = self.rule_data.get("instance_id")
                        index = self.instance_combo.findData(instance_id)
                        if index >= 0:
                            self.instance_combo.setCurrentIndex(index)
                    # 如果有当前实例ID，设置选中项
                    elif self.current_instance_id and self.current_instance_id != "*":
                        index = self.instance_combo.findData(self.current_instance_id)
                        if index >= 0:
                            self.instance_combo.setCurrentIndex(index)
                except Exception as e:
                    logger.error(f"更新实例下拉框失败: {e}")

            # 在主线程中执行UI更新
            QTimer.singleShot(0, update_ui)

        except Exception as e:
            logger.error(f"加载实例列表失败: {e}")

    async def _load_platforms(self):
        """加载平台列表"""
        try:
            # 从数据库直接加载平台
            from wxauto_mgt.data.db_manager import db_manager
            platforms = await db_manager.fetchall("SELECT * FROM service_platforms WHERE enabled = 1")

            # 准备平台数据
            platform_data = []
            for platform in platforms:
                platform_id = platform.get("platform_id")
                platform_name = platform.get("name")
                platform_type = platform.get("type", "")
                display_name = f"{platform_name} ({platform_type})"
                platform_data.append((display_name, platform_id))

            # 在主线程中更新UI
            def update_ui():
                try:
                    # 清空下拉框
                    self.platform_combo.clear()

                    # 添加平台到下拉框
                    for name, id in platform_data:
                        self.platform_combo.addItem(name, id)

                    # 如果是编辑模式，设置选中项
                    if self.is_edit_mode and self.rule_data:
                        platform_id = self.rule_data.get("platform_id")
                        index = self.platform_combo.findData(platform_id)
                        if index >= 0:
                            self.platform_combo.setCurrentIndex(index)
                    # 如果有平台，默认选择第一个
                    elif self.platform_combo.count() > 0:
                        self.platform_combo.setCurrentIndex(0)
                except Exception as e:
                    logger.error(f"更新平台下拉框失败: {e}")

            # 在主线程中执行UI更新
            QTimer.singleShot(0, update_ui)

        except Exception as e:
            logger.error(f"加载平台列表失败: {e}")

    def _set_current_instance_later(self):
        """在实例加载完成后设置当前实例"""
        def _set_current():
            # 查找当前实例的索引
            index = self.instance_combo.findData(self.current_instance_id)
            if index >= 0:
                self.instance_combo.setCurrentIndex(index)

        # 使用定时器延迟执行
        QTimer.singleShot(500, _set_current)

    def _load_rule_data(self):
        """加载规则数据"""
        if not self.rule_data:
            return

        # 设置规则名称
        self.name_edit.setText(self.rule_data.get("name", ""))

        # 设置实例选择
        instance_id = self.rule_data.get("instance_id", "*")
        if instance_id == "*":
            self.all_instances_radio.setChecked(True)
        else:
            self.specific_instance_radio.setChecked(True)
            self._on_instance_scope_changed()

        # 设置聊天对象匹配
        self.chat_pattern_edit.setText(self.rule_data.get("chat_pattern", ""))

        # 设置优先级
        priority = self.rule_data.get("priority", 0)
        self.priority_spin.setValue(priority)
        self.priority_slider.setValue(priority)

        # 设置@消息设置
        only_at_messages = self.rule_data.get("only_at_messages", 0)
        at_name = self.rule_data.get("at_name", "")
        reply_at_sender = self.rule_data.get("reply_at_sender", 0)

        # 设置@名称
        self.at_name_edit.setText(at_name)

        # 先启用输入框，以便能够设置文本
        self.at_name_edit.setEnabled(True)

        # 设置复选框状态 - 这会触发状态变化事件，进而控制输入框的启用状态
        self.only_at_messages_check.setChecked(only_at_messages == 1)

        # 设置回复时@发送者复选框状态
        self.reply_at_sender_check.setChecked(reply_at_sender == 1)

    def get_rule_data(self) -> Dict[str, Any]:
        """
        获取规则数据

        Returns:
            Dict[str, Any]: 规则数据
        """
        # 获取实例ID
        instance_id = "*"
        if self.specific_instance_radio.isChecked():
            instance_id = self.instance_combo.currentData()

        # 获取平台ID
        platform_id = self.platform_combo.currentData()

        # 处理聊天对象匹配模式
        chat_pattern = self.chat_pattern_edit.text().strip()

        # 获取@消息设置
        only_at_messages = 1 if self.only_at_messages_check.isChecked() else 0
        at_name = self.at_name_edit.text().strip()
        reply_at_sender = 1 if self.reply_at_sender_check.isChecked() else 0

        # 返回规则数据
        return {
            "name": self.name_edit.text().strip(),
            "instance_id": instance_id,
            "chat_pattern": chat_pattern,
            "platform_id": platform_id,
            "priority": self.priority_spin.value(),
            "only_at_messages": only_at_messages,
            "at_name": at_name,
            "reply_at_sender": reply_at_sender
        }

    def accept(self):
        """确认按钮点击事件"""
        # 验证输入
        if not self._validate_input():
            return

        # 检查规则冲突
        asyncio.create_task(self._check_rule_conflicts())

    def _validate_input(self) -> bool:
        """
        验证输入

        Returns:
            bool: 是否验证通过
        """
        # 验证规则名称
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "错误", "请输入规则名称")
            self.name_edit.setFocus()
            return False

        # 验证聊天对象匹配
        if not self.chat_pattern_edit.text().strip():
            QMessageBox.warning(self, "错误", "请输入聊天对象匹配模式")
            self.chat_pattern_edit.setFocus()
            return False

        # 验证服务平台
        if self.platform_combo.currentIndex() < 0:
            QMessageBox.warning(self, "错误", "请选择服务平台")
            self.platform_combo.setFocus()
            return False

        # 验证实例选择
        if self.specific_instance_radio.isChecked() and self.instance_combo.currentIndex() < 0:
            QMessageBox.warning(self, "错误", "请选择实例")
            self.instance_combo.setFocus()
            return False

        # 验证@消息设置
        if self.only_at_messages_check.isChecked() and not self.at_name_edit.text().strip():
            QMessageBox.warning(self, "错误", "请输入被@的名称")
            self.at_name_edit.setFocus()
            return False

        return True

    async def _check_rule_conflicts(self):
        """检查规则冲突"""
        try:
            # 获取规则数据
            rule_data = self.get_rule_data()

            # 获取所有规则
            rules = await rule_manager.get_all_rules()

            # 查找可能冲突的规则
            conflicts = []
            rule_id = self.rule_data.get("rule_id") if self.is_edit_mode else None

            for rule in rules:
                # 跳过当前规则
                if self.is_edit_mode and rule.get("rule_id") == rule_id:
                    continue

                # 检查实例ID是否冲突
                instance_match = (
                    rule.get("instance_id") == rule_data["instance_id"] or
                    rule.get("instance_id") == "*" or
                    rule_data["instance_id"] == "*"
                )

                # 检查聊天对象匹配是否冲突
                rule_pattern = rule.get("chat_pattern", "")
                new_pattern = rule_data["chat_pattern"]

                # 通配符冲突
                if rule_pattern == "*" or new_pattern == "*":
                    pattern_match = True
                # 正则表达式冲突
                elif rule_pattern.startswith("regex:") or new_pattern.startswith("regex:"):
                    pattern_match = True
                # 完全相同
                elif rule_pattern == new_pattern:
                    pattern_match = True
                # 逗号分隔的多个对象，检查是否有交集
                elif "," in rule_pattern or "," in new_pattern:
                    rule_patterns = [p.strip() for p in rule_pattern.split(",")] if "," in rule_pattern else [rule_pattern]
                    new_patterns = [p.strip() for p in new_pattern.split(",")] if "," in new_pattern else [new_pattern]
                    # 检查两个列表是否有交集
                    pattern_match = any(p in new_patterns for p in rule_patterns)
                else:
                    pattern_match = False

                # 如果实例和聊天对象都匹配，则存在冲突
                if instance_match and pattern_match:
                    conflicts.append(rule)

            # 如果存在冲突，显示警告
            if conflicts:
                # 按优先级排序
                conflicts.sort(key=lambda x: -x.get("priority", 0))

                # 构建冲突信息
                conflict_info = ""
                for rule in conflicts:
                    priority = rule.get("priority", 0)
                    name = rule.get("name", "")
                    instance_id = rule.get("instance_id", "")
                    instance_name = "全部" if instance_id == "*" else self._get_instance_name(instance_id)
                    chat_pattern = rule.get("chat_pattern", "")

                    conflict_info += f"• \"{name}\" (优先级: {priority})\n"
                    conflict_info += f"  适用于: {instance_name} / {chat_pattern}\n\n"

                # 显示冲突警告
                msg_box = QMessageBox(self)
                msg_box.setIcon(QMessageBox.Warning)
                msg_box.setWindowTitle("规则冲突警告")
                msg_box.setText("您正在创建的规则与以下现有规则存在冲突:")
                msg_box.setInformativeText(conflict_info)

                # 添加详细信息
                priority = rule_data["priority"]
                highest_conflict_priority = conflicts[0].get("priority", 0)

                if priority < highest_conflict_priority:
                    detail_text = "由于新规则优先级较低，它可能不会被应用。\n\n"
                    detail_text += "建议:\n"
                    detail_text += f"• 提高新规则的优先级 (>{highest_conflict_priority})\n"
                    detail_text += "• 修改规则的适用范围以避免冲突\n"
                    detail_text += "• 保持现状，接受基于优先级的规则应用"
                else:
                    detail_text = "新规则的优先级高于现有冲突规则，将会优先应用。\n\n"
                    detail_text += "建议:\n"
                    detail_text += "• 确认这是您期望的行为\n"
                    detail_text += "• 考虑调整现有规则的优先级\n"
                    detail_text += "• 修改规则的适用范围以避免冲突"

                msg_box.setDetailedText(detail_text)

                # 添加按钮
                msg_box.addButton("取消", QMessageBox.RejectRole)
                continue_btn = msg_box.addButton("继续保存", QMessageBox.AcceptRole)

                # 显示对话框
                msg_box.exec()

                # 如果用户选择继续，则接受对话框
                if msg_box.clickedButton() == continue_btn:
                    super().accept()
            else:
                # 没有冲突，直接接受
                super().accept()

        except Exception as e:
            logger.error(f"检查规则冲突失败: {e}")
            # 出错时也接受，避免阻塞用户操作
            super().accept()

    def _save_rule_to_database(self):
        """直接保存规则到数据库"""
        try:
            # 获取规则数据
            rule_data = self.get_rule_data()

            # 获取数据库连接
            import sqlite3
            import os
            import json
            import time
            import uuid
            from ....utils.logging import get_logger

            logger = get_logger(__name__)

            # 获取数据库路径
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
            db_path = os.path.join(base_dir, 'data', 'wxauto_mgt.db')

            # 连接数据库
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 检查表结构，确保必要的列存在
            self._ensure_table_columns(cursor)

            # 准备数据
            now = int(time.time())

            if self.is_edit_mode:
                # 更新现有规则
                rule_id = self.rule_data.get("rule_id")

                # 执行更新
                cursor.execute(
                    """
                    UPDATE delivery_rules
                    SET name = ?, instance_id = ?, chat_pattern = ?, platform_id = ?,
                        priority = ?, only_at_messages = ?, at_name = ?, update_time = ?
                    WHERE rule_id = ?
                    """,
                    (
                        rule_data["name"],
                        rule_data["instance_id"],
                        rule_data["chat_pattern"],
                        rule_data["platform_id"],
                        rule_data["priority"],
                        1 if rule_data["only_at_messages"] else 0,
                        rule_data["at_name"],
                        now,
                        rule_id
                    )
                )

                logger.info(f"更新规则: {rule_data['name']} ({rule_id})")
            else:
                # 添加新规则
                rule_id = f"rule_{uuid.uuid4().hex[:8]}"

                # 执行插入
                cursor.execute(
                    """
                    INSERT INTO delivery_rules
                    (rule_id, name, instance_id, chat_pattern, platform_id, priority,
                     enabled, only_at_messages, at_name, create_time, update_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        rule_id,
                        rule_data["name"],
                        rule_data["instance_id"],
                        rule_data["chat_pattern"],
                        rule_data["platform_id"],
                        rule_data["priority"],
                        1,  # enabled
                        1 if rule_data["only_at_messages"] else 0,
                        rule_data["at_name"],
                        now,
                        now
                    )
                )

                logger.info(f"添加规则: {rule_data['name']} ({rule_id})")

            # 提交事务
            conn.commit()

            # 关闭数据库连接
            conn.close()

            # 触发规则管理器重新加载规则
            from ....core.service_platform_manager import rule_manager
            import asyncio

            # 创建一个异步任务来重新加载规则
            def reload_rules():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(rule_manager._load_rules())
                finally:
                    loop.close()

            # 在新线程中执行异步任务
            import threading
            thread = threading.Thread(target=reload_rules)
            thread.daemon = True
            thread.start()

            # 关闭对话框
            super().accept()

        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            logger.error(f"保存规则失败: {e}")
            QMessageBox.warning(self, "错误", f"保存规则失败: {str(e)}")

    def _ensure_table_columns(self, cursor):
        """确保数据库表有必要的列"""
        try:
            # 获取表结构
            cursor.execute("PRAGMA table_info(delivery_rules)")
            columns = cursor.fetchall()

            # 转换为列名列表
            column_names = [col['name'] for col in columns]

            # 检查并添加缺失的列
            if 'only_at_messages' not in column_names:
                cursor.execute("ALTER TABLE delivery_rules ADD COLUMN only_at_messages INTEGER DEFAULT 0")

            if 'at_name' not in column_names:
                cursor.execute("ALTER TABLE delivery_rules ADD COLUMN at_name TEXT DEFAULT ''")

        except Exception as e:
            from ....utils.logging import get_logger
            logger = get_logger(__name__)
            logger.error(f"检查和更新表结构失败: {e}")
            raise

    def _get_instance_name(self, instance_id: str) -> str:
        """
        获取实例名称

        Args:
            instance_id: 实例ID

        Returns:
            str: 实例名称，如果找不到则返回实例ID
        """
        # 从实例管理器获取实例名称
        instance = instance_manager.get_instance_config(instance_id)
        if instance:
            return instance.get("name", instance_id)
        return instance_id
