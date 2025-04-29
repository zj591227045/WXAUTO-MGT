"""
消息转发规则添加/编辑对话框

该模块提供了添加和编辑消息转发规则的对话框界面。
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
    QMessageBox, QGroupBox, QRadioButton, QSlider
)

from wxauto_mgt.core.service_platform_manager import platform_manager, rule_manager
from wxauto_mgt.core.api_client import instance_manager
from wxauto_mgt.utils.logging import get_logger
from qasync import asyncSlot

logger = get_logger()

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
        self.chat_pattern_edit.setPlaceholderText("支持精确匹配、* 或 regex:正则表达式")
        form_layout.addRow("聊天对象匹配:", self.chat_pattern_edit)
        
        # 添加提示标签
        pattern_hint = QLabel("支持三种匹配模式：\n1. 精确匹配：输入完整的聊天对象名称\n2. 通配符：输入 * 匹配所有聊天对象\n3. 正则表达式：输入 regex: 开头，后跟正则表达式")
        pattern_hint.setStyleSheet("color: #666666; font-size: 12px;")
        form_layout.addRow("", pattern_hint)
        
        # 服务平台
        self.platform_combo = QComboBox()
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
        
        # 异步加载实例和平台列表
        asyncio.create_task(self._load_instances())
        asyncio.create_task(self._load_platforms())
    
    def _on_instance_scope_changed(self):
        """实例范围选择变化事件"""
        self.instance_combo.setEnabled(self.specific_instance_radio.isChecked())
    
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
            # 从实例管理器获取实例列表
            instances = instance_manager.get_all_instances()
            
            # 在主线程中更新UI
            QMetaObject.invokeMethod(
                self.instance_combo,
                "clear",
                Qt.QueuedConnection
            )
            
            # 添加实例到下拉框
            for instance_id in instances:
                # 获取实例配置
                instance_config = instance_manager.get_instance_config(instance_id)
                if instance_config:
                    instance_name = instance_config.get("name", instance_id)
                    
                    # 在主线程中添加项
                    QMetaObject.invokeMethod(
                        self.instance_combo,
                        "addItem",
                        Qt.QueuedConnection,
                        Q_ARG(str, instance_name),
                        Q_ARG(str, instance_id)
                    )
            
            # 如果是编辑模式且有当前实例ID，设置选中项
            if self.is_edit_mode and self.rule_data and self.rule_data.get("instance_id") != "*":
                instance_id = self.rule_data.get("instance_id")
                # 在主线程中设置当前索引
                QMetaObject.invokeMethod(
                    self,
                    "_set_combo_by_data",
                    Qt.QueuedConnection,
                    Q_ARG(QComboBox, self.instance_combo),
                    Q_ARG(str, instance_id)
                )
        
        except Exception as e:
            logger.error(f"加载实例列表失败: {e}")
    
    async def _load_platforms(self):
        """加载平台列表"""
        try:
            # 获取所有平台
            platforms = await platform_manager.get_all_platforms()
            
            # 在主线程中更新UI
            QMetaObject.invokeMethod(
                self.platform_combo,
                "clear",
                Qt.QueuedConnection
            )
            
            # 添加平台到下拉框
            for platform in platforms:
                platform_id = platform.get("platform_id")
                platform_name = platform.get("name")
                
                # 在主线程中添加项
                QMetaObject.invokeMethod(
                    self.platform_combo,
                    "addItem",
                    Qt.QueuedConnection,
                    Q_ARG(str, platform_name),
                    Q_ARG(str, platform_id)
                )
            
            # 如果是编辑模式，设置选中项
            if self.is_edit_mode and self.rule_data:
                platform_id = self.rule_data.get("platform_id")
                # 在主线程中设置当前索引
                QMetaObject.invokeMethod(
                    self,
                    "_set_combo_by_data",
                    Qt.QueuedConnection,
                    Q_ARG(QComboBox, self.platform_combo),
                    Q_ARG(str, platform_id)
                )
        
        except Exception as e:
            logger.error(f"加载平台列表失败: {e}")
    
    @Slot(QComboBox, str)
    def _set_combo_by_data(self, combo: QComboBox, data: str):
        """
        根据数据设置下拉框选中项
        
        Args:
            combo: 下拉框
            data: 数据
        """
        index = combo.findData(data)
        if index >= 0:
            combo.setCurrentIndex(index)
    
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
        
        # 返回规则数据
        return {
            "name": self.name_edit.text().strip(),
            "instance_id": instance_id,
            "chat_pattern": self.chat_pattern_edit.text().strip(),
            "platform_id": platform_id,
            "priority": self.priority_spin.value()
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
        
        return True
    
    @asyncSlot()
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
                pattern_match = (
                    rule.get("chat_pattern") == rule_data["chat_pattern"] or
                    rule.get("chat_pattern") == "*" or
                    rule_data["chat_pattern"] == "*" or
                    (rule.get("chat_pattern").startswith("regex:") and rule_data["chat_pattern"] != "*") or
                    (rule_data["chat_pattern"].startswith("regex:") and rule.get("chat_pattern") != "*")
                )
                
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
