"""
投递规则管理面板

该模块提供了投递规则管理的UI界面，包括：
- 显示所有投递规则
- 添加、编辑和删除投递规则
"""

import logging
import asyncio
import json
from typing import Dict, List, Optional, Any

from PySide6.QtCore import Qt, Signal, Slot, QSize
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QDialog, QFormLayout, QLineEdit, QComboBox, QSpinBox, 
    QCheckBox, QTabWidget, QTextEdit
)

from wxauto_mgt.core.service_platform_manager import platform_manager, rule_manager
from wxauto_mgt.core.api_client import instance_manager

logger = logging.getLogger(__name__)

class RuleDialog(QDialog):
    """投递规则编辑对话框"""
    
    def __init__(self, parent=None, rule_data=None):
        """
        初始化对话框
        
        Args:
            parent: 父窗口
            rule_data: 规则数据，如果为None则表示新建规则
        """
        super().__init__(parent)
        self.rule_data = rule_data
        self.setWindowTitle("投递规则配置")
        self.setMinimumWidth(500)
        self.setup_ui()
        
        # 如果是编辑模式，填充数据
        if rule_data:
            self.fill_data(rule_data)
    
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 基本信息
        form_layout = QFormLayout()
        
        self.name_edit = QLineEdit()
        form_layout.addRow("规则名称:", self.name_edit)
        
        # 实例选择
        self.instance_combo = QComboBox()
        self.instance_combo.addItem("所有实例", "*")
        # 异步加载实例列表
        asyncio.create_task(self.load_instances())
        form_layout.addRow("微信实例:", self.instance_combo)
        
        # 聊天对象匹配模式
        self.chat_pattern_edit = QLineEdit()
        self.chat_pattern_edit.setPlaceholderText("精确匹配、* 或 regex:正则表达式")
        form_layout.addRow("聊天对象匹配:", self.chat_pattern_edit)
        
        # 服务平台选择
        self.platform_combo = QComboBox()
        # 异步加载平台列表
        asyncio.create_task(self.load_platforms())
        form_layout.addRow("服务平台:", self.platform_combo)
        
        # 优先级
        self.priority_spin = QSpinBox()
        self.priority_spin.setRange(0, 100)
        self.priority_spin.setValue(0)
        form_layout.addRow("优先级:", self.priority_spin)
        
        layout.addLayout(form_layout)
        
        # 帮助信息
        help_label = QLabel(
            "聊天对象匹配说明：\n"
            "1. 精确匹配：直接填写聊天对象名称\n"
            "2. 通配符匹配：使用 * 表示匹配所有聊天对象\n"
            "3. 正则表达式匹配：使用 regex: 前缀，例如 regex:^群聊.*"
        )
        help_label.setStyleSheet("color: gray; font-size: 12px;")
        layout.addWidget(help_label)
        
        # 按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        self.save_button = QPushButton("保存")
        self.save_button.clicked.connect(self.accept)
        self.save_button.setDefault(True)
        button_layout.addWidget(self.save_button)
        
        layout.addLayout(button_layout)
    
    async def load_instances(self):
        """加载实例列表"""
        try:
            # 获取所有实例
            instances = instance_manager.get_all_instances()
            
            # 添加到下拉框
            for instance_id in instances:
                self.instance_combo.addItem(instance_id, instance_id)
        except Exception as e:
            logger.error(f"加载实例列表失败: {e}")
    
    async def load_platforms(self):
        """加载平台列表"""
        try:
            # 获取所有平台
            platforms = await platform_manager.get_all_platforms()
            
            # 添加到下拉框
            for platform in platforms:
                self.platform_combo.addItem(
                    f"{platform['name']} ({platform['type']})", 
                    platform['platform_id']
                )
        except Exception as e:
            logger.error(f"加载平台列表失败: {e}")
    
    def fill_data(self, rule_data):
        """
        填充规则数据
        
        Args:
            rule_data: 规则数据
        """
        self.name_edit.setText(rule_data.get('name', ''))
        
        # 设置实例
        instance_id = rule_data.get('instance_id', '')
        index = self.instance_combo.findData(instance_id)
        if index >= 0:
            self.instance_combo.setCurrentIndex(index)
        
        # 设置聊天对象匹配模式
        self.chat_pattern_edit.setText(rule_data.get('chat_pattern', ''))
        
        # 设置优先级
        self.priority_spin.setValue(rule_data.get('priority', 0))
        
        # 异步设置平台
        async def set_platform():
            # 等待平台加载完成
            for _ in range(10):  # 最多等待10次
                if self.platform_combo.count() > 0:
                    break
                await asyncio.sleep(0.1)
            
            # 设置平台
            platform_id = rule_data.get('platform_id', '')
            index = self.platform_combo.findData(platform_id)
            if index >= 0:
                self.platform_combo.setCurrentIndex(index)
        
        asyncio.create_task(set_platform())
    
    def get_rule_data(self):
        """
        获取规则数据
        
        Returns:
            Dict: 规则数据
        """
        data = {
            'name': self.name_edit.text().strip(),
            'instance_id': self.instance_combo.currentData(),
            'chat_pattern': self.chat_pattern_edit.text().strip(),
            'platform_id': self.platform_combo.currentData(),
            'priority': self.priority_spin.value()
        }
        
        # 如果是编辑模式，保留规则ID
        if self.rule_data:
            data['rule_id'] = self.rule_data.get('rule_id', '')
        
        return data


class RulePanel(QWidget):
    """投递规则管理面板"""
    
    def __init__(self, parent=None):
        """初始化面板"""
        super().__init__(parent)
        self.setup_ui()
        self.load_rules()
    
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 标题
        title_layout = QHBoxLayout()
        title_label = QLabel("投递规则管理")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        
        # 添加按钮
        self.add_button = QPushButton("添加规则")
        self.add_button.clicked.connect(self.add_rule)
        title_layout.addWidget(self.add_button)
        
        layout.addLayout(title_layout)
        
        # 规则列表
        self.rule_table = QTableWidget()
        self.rule_table.setColumnCount(7)
        self.rule_table.setHorizontalHeaderLabels(["ID", "名称", "实例", "聊天匹配", "平台", "优先级", "操作"])
        self.rule_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.rule_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.rule_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.rule_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.rule_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.rule_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.rule_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.rule_table.verticalHeader().setVisible(False)
        self.rule_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.rule_table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        layout.addWidget(self.rule_table)
    
    def load_rules(self):
        """加载规则列表"""
        # 创建异步任务
        async def load():
            try:
                # 获取所有规则
                rules = await rule_manager.get_all_rules()
                
                # 清空表格
                self.rule_table.setRowCount(0)
                
                # 填充表格
                for i, rule in enumerate(rules):
                    self.rule_table.insertRow(i)
                    
                    # ID
                    id_item = QTableWidgetItem(rule['rule_id'])
                    self.rule_table.setItem(i, 0, id_item)
                    
                    # 名称
                    name_item = QTableWidgetItem(rule['name'])
                    self.rule_table.setItem(i, 1, name_item)
                    
                    # 实例
                    instance_item = QTableWidgetItem(rule['instance_id'])
                    self.rule_table.setItem(i, 2, instance_item)
                    
                    # 聊天匹配
                    chat_pattern_item = QTableWidgetItem(rule['chat_pattern'])
                    self.rule_table.setItem(i, 3, chat_pattern_item)
                    
                    # 平台
                    platform = await platform_manager.get_platform(rule['platform_id'])
                    platform_name = platform.name if platform else rule['platform_id']
                    platform_item = QTableWidgetItem(platform_name)
                    self.rule_table.setItem(i, 4, platform_item)
                    
                    # 优先级
                    priority_item = QTableWidgetItem(str(rule['priority']))
                    self.rule_table.setItem(i, 5, priority_item)
                    
                    # 操作按钮
                    action_widget = QWidget()
                    action_layout = QHBoxLayout(action_widget)
                    action_layout.setContentsMargins(0, 0, 0, 0)
                    action_layout.setSpacing(5)
                    
                    # 编辑按钮
                    edit_button = QPushButton("编辑")
                    edit_button.setProperty("rule_id", rule['rule_id'])
                    edit_button.clicked.connect(self.edit_rule)
                    action_layout.addWidget(edit_button)
                    
                    # 删除按钮
                    delete_button = QPushButton("删除")
                    delete_button.setProperty("rule_id", rule['rule_id'])
                    delete_button.clicked.connect(self.delete_rule)
                    action_layout.addWidget(delete_button)
                    
                    self.rule_table.setCellWidget(i, 6, action_widget)
            except Exception as e:
                logger.error(f"加载规则列表失败: {e}")
                QMessageBox.critical(self, "错误", f"加载规则列表失败: {e}")
        
        # 运行异步任务
        asyncio.create_task(load())
    
    def add_rule(self):
        """添加规则"""
        dialog = RuleDialog(self)
        if dialog.exec() == QDialog.Accepted:
            rule_data = dialog.get_rule_data()
            
            # 创建异步任务
            async def add():
                try:
                    # 添加规则
                    rule_id = await rule_manager.add_rule(
                        rule_data['name'],
                        rule_data['instance_id'],
                        rule_data['chat_pattern'],
                        rule_data['platform_id'],
                        rule_data['priority']
                    )
                    
                    if rule_id:
                        QMessageBox.information(self, "成功", "添加规则成功")
                        self.load_rules()
                    else:
                        QMessageBox.critical(self, "错误", "添加规则失败")
                except Exception as e:
                    logger.error(f"添加规则失败: {e}")
                    QMessageBox.critical(self, "错误", f"添加规则失败: {e}")
            
            # 运行异步任务
            asyncio.create_task(add())
    
    def edit_rule(self):
        """编辑规则"""
        # 获取规则ID
        button = self.sender()
        rule_id = button.property("rule_id")
        
        # 创建异步任务
        async def edit():
            try:
                # 获取规则数据
                rule = await rule_manager.get_rule(rule_id)
                if not rule:
                    QMessageBox.critical(self, "错误", f"找不到规则: {rule_id}")
                    return
                
                # 显示编辑对话框
                dialog = RuleDialog(self, rule)
                if dialog.exec() == QDialog.Accepted:
                    rule_data = dialog.get_rule_data()
                    
                    # 更新规则
                    success = await rule_manager.update_rule(
                        rule_id,
                        rule_data['name'],
                        rule_data['instance_id'],
                        rule_data['chat_pattern'],
                        rule_data['platform_id'],
                        rule_data['priority']
                    )
                    
                    if success:
                        QMessageBox.information(self, "成功", "更新规则成功")
                        self.load_rules()
                    else:
                        QMessageBox.critical(self, "错误", "更新规则失败")
            except Exception as e:
                logger.error(f"编辑规则失败: {e}")
                QMessageBox.critical(self, "错误", f"编辑规则失败: {e}")
        
        # 运行异步任务
        asyncio.create_task(edit())
    
    def delete_rule(self):
        """删除规则"""
        # 获取规则ID
        button = self.sender()
        rule_id = button.property("rule_id")
        
        # 确认删除
        reply = QMessageBox.question(
            self, "确认删除", 
            f"确定要删除规则 {rule_id} 吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # 创建异步任务
        async def delete():
            try:
                # 删除规则
                success = await rule_manager.delete_rule(rule_id)
                
                if success:
                    QMessageBox.information(self, "成功", "删除规则成功")
                    self.load_rules()
                else:
                    QMessageBox.critical(self, "错误", "删除规则失败")
            except Exception as e:
                logger.error(f"删除规则失败: {e}")
                QMessageBox.critical(self, "错误", f"删除规则失败: {e}")
        
        # 运行异步任务
        asyncio.create_task(delete())
