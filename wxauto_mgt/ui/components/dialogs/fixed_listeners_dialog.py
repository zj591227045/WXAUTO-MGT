"""
固定监听配置对话框

该模块提供了管理固定监听配置的对话框界面，支持添加、删除、编辑固定监听会话名称。
"""

import logging
import asyncio
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTextEdit, QListWidget, QListWidgetItem, QMessageBox,
    QGroupBox, QCheckBox, QDialogButtonBox, QWidget, QSplitter,
    QFormLayout, QFrame
)

from wxauto_mgt.core.message_listener import message_listener
from wxauto_mgt.utils.logging import get_logger
from qasync import asyncSlot

logger = get_logger(__name__)


class FixedListenersDialog(QDialog):
    """固定监听配置对话框"""
    
    # 定义信号
    config_changed = Signal()  # 配置发生变化时发出

    def __init__(self, parent=None):
        """
        初始化对话框

        Args:
            parent: 父窗口
        """
        super().__init__(parent)
        
        self.fixed_listeners = []  # 存储固定监听配置列表
        self.current_item = None   # 当前选中的项目
        
        self._init_ui()
        self._load_fixed_listeners()
        
        # 设置对话框属性
        self.setWindowTitle("固定监听配置")
        self.setModal(True)
        self.resize(600, 400)

    def _init_ui(self):
        """初始化UI"""
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)
        
        # 标题和说明
        title_label = QLabel("固定监听配置管理")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50;")
        main_layout.addWidget(title_label)
        
        desc_label = QLabel("配置固定监听的会话名称，这些会话将在服务启动时自动添加到所有实例的监听列表中，且不受超时机制影响。")
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #7f8c8d; margin-bottom: 10px;")
        main_layout.addWidget(desc_label)
        
        # 分割器
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # 左侧：列表区域
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # 列表标题和按钮
        list_header = QHBoxLayout()
        list_title = QLabel("固定监听列表")
        list_title.setStyleSheet("font-weight: bold;")
        list_header.addWidget(list_title)
        
        list_header.addStretch()
        
        # 添加按钮
        self.add_btn = QPushButton("添加")
        self.add_btn.setIcon(QIcon(":/icons/add.png"))
        self.add_btn.clicked.connect(self._add_fixed_listener)
        list_header.addWidget(self.add_btn)
        
        # 删除按钮
        self.delete_btn = QPushButton("删除")
        self.delete_btn.setIcon(QIcon(":/icons/delete.png"))
        self.delete_btn.clicked.connect(self._delete_fixed_listener)
        self.delete_btn.setEnabled(False)
        list_header.addWidget(self.delete_btn)
        
        left_layout.addLayout(list_header)
        
        # 固定监听列表
        self.list_widget = QListWidget()
        self.list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        left_layout.addWidget(self.list_widget)
        
        splitter.addWidget(left_widget)
        
        # 右侧：详情编辑区域
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # 详情标题
        details_title = QLabel("详情编辑")
        details_title.setStyleSheet("font-weight: bold;")
        right_layout.addWidget(details_title)
        
        # 编辑表单
        form_group = QGroupBox()
        form_layout = QFormLayout(form_group)
        
        # 会话名称
        self.session_name_edit = QLineEdit()
        self.session_name_edit.setPlaceholderText("请输入会话名称")
        self.session_name_edit.textChanged.connect(self._on_session_name_changed)
        form_layout.addRow("会话名称:", self.session_name_edit)
        
        # 启用状态
        self.enabled_checkbox = QCheckBox("启用此固定监听")
        self.enabled_checkbox.setChecked(True)
        self.enabled_checkbox.stateChanged.connect(self._on_enabled_changed)
        form_layout.addRow("", self.enabled_checkbox)
        
        # 描述
        self.description_edit = QTextEdit()
        self.description_edit.setPlaceholderText("可选：输入描述信息")
        self.description_edit.setMaximumHeight(80)
        self.description_edit.textChanged.connect(self._on_description_changed)
        form_layout.addRow("描述:", self.description_edit)
        
        right_layout.addWidget(form_group)
        
        # 保存按钮
        save_btn = QPushButton("保存更改")
        save_btn.clicked.connect(self._save_current_item)
        right_layout.addWidget(save_btn)
        
        right_layout.addStretch()
        
        splitter.addWidget(right_widget)
        
        # 设置分割器比例
        splitter.setSizes([300, 300])
        
        # 底部按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)
        
        # 初始状态：禁用编辑区域
        self._set_edit_enabled(False)

    def _set_edit_enabled(self, enabled: bool):
        """设置编辑区域的启用状态"""
        self.session_name_edit.setEnabled(enabled)
        self.enabled_checkbox.setEnabled(enabled)
        self.description_edit.setEnabled(enabled)

    @asyncSlot()
    async def _load_fixed_listeners(self):
        """加载固定监听配置列表"""
        try:
            self.fixed_listeners = await message_listener.get_fixed_listeners()
            self._refresh_list()
        except Exception as e:
            logger.error(f"加载固定监听配置失败: {e}")
            QMessageBox.warning(self, "错误", f"加载固定监听配置失败: {str(e)}")

    def _refresh_list(self):
        """刷新列表显示"""
        self.list_widget.clear()
        
        for config in self.fixed_listeners:
            item = QListWidgetItem()
            session_name = config.get('session_name', '')
            enabled = bool(config.get('enabled', 1))
            description = config.get('description', '')
            
            # 设置显示文本
            display_text = session_name
            if not enabled:
                display_text += " (已禁用)"
            
            item.setText(display_text)
            item.setData(Qt.UserRole, config)
            
            # 设置图标和样式
            if enabled:
                item.setIcon(QIcon(":/icons/check.png"))
            else:
                item.setIcon(QIcon(":/icons/disable.png"))
                item.setForeground(Qt.gray)
            
            # 设置工具提示
            tooltip = f"会话名称: {session_name}"
            if description:
                tooltip += f"\n描述: {description}"
            tooltip += f"\n状态: {'启用' if enabled else '禁用'}"
            item.setToolTip(tooltip)
            
            self.list_widget.addItem(item)

    def _on_selection_changed(self):
        """列表选择变化处理"""
        current_item = self.list_widget.currentItem()
        
        if current_item:
            self.current_item = current_item
            config = current_item.data(Qt.UserRole)
            
            # 更新编辑区域
            self.session_name_edit.setText(config.get('session_name', ''))
            self.enabled_checkbox.setChecked(bool(config.get('enabled', 1)))
            self.description_edit.setPlainText(config.get('description', ''))
            
            self._set_edit_enabled(True)
            self.delete_btn.setEnabled(True)
        else:
            self.current_item = None
            self._clear_edit_area()
            self._set_edit_enabled(False)
            self.delete_btn.setEnabled(False)

    def _clear_edit_area(self):
        """清空编辑区域"""
        self.session_name_edit.clear()
        self.enabled_checkbox.setChecked(True)
        self.description_edit.clear()

    def _on_session_name_changed(self):
        """会话名称变化处理"""
        if self.current_item:
            config = self.current_item.data(Qt.UserRole)
            config['session_name'] = self.session_name_edit.text().strip()
            self._update_item_display()
        else:
            # 如果没有选中项，可能是新添加的配置，需要找到对应的配置对象
            # 这种情况下，我们需要更新最后一个配置（新添加的）
            if self.fixed_listeners:
                last_config = self.fixed_listeners[-1]
                if last_config.get('id') is None:  # 确认是新配置
                    last_config['session_name'] = self.session_name_edit.text().strip()

    def _on_enabled_changed(self):
        """启用状态变化处理"""
        if self.current_item:
            config = self.current_item.data(Qt.UserRole)
            config['enabled'] = 1 if self.enabled_checkbox.isChecked() else 0
            self._update_item_display()
        else:
            # 如果没有选中项，可能是新添加的配置
            if self.fixed_listeners:
                last_config = self.fixed_listeners[-1]
                if last_config.get('id') is None:  # 确认是新配置
                    last_config['enabled'] = 1 if self.enabled_checkbox.isChecked() else 0

    def _on_description_changed(self):
        """描述变化处理"""
        if self.current_item:
            config = self.current_item.data(Qt.UserRole)
            config['description'] = self.description_edit.toPlainText().strip()
        else:
            # 如果没有选中项，可能是新添加的配置
            if self.fixed_listeners:
                last_config = self.fixed_listeners[-1]
                if last_config.get('id') is None:  # 确认是新配置
                    last_config['description'] = self.description_edit.toPlainText().strip()

    def _update_item_display(self):
        """更新列表项显示"""
        if not self.current_item:
            return
            
        config = self.current_item.data(Qt.UserRole)
        session_name = config.get('session_name', '')
        enabled = bool(config.get('enabled', 1))
        description = config.get('description', '')
        
        # 更新显示文本
        display_text = session_name
        if not enabled:
            display_text += " (已禁用)"
        
        self.current_item.setText(display_text)
        
        # 更新图标和样式
        if enabled:
            self.current_item.setIcon(QIcon(":/icons/check.png"))
            self.current_item.setForeground(Qt.black)
        else:
            self.current_item.setIcon(QIcon(":/icons/disable.png"))
            self.current_item.setForeground(Qt.gray)
        
        # 更新工具提示
        tooltip = f"会话名称: {session_name}"
        if description:
            tooltip += f"\n描述: {description}"
        tooltip += f"\n状态: {'启用' if enabled else '禁用'}"
        self.current_item.setToolTip(tooltip)

    @asyncSlot()
    async def _add_fixed_listener(self):
        """添加新的固定监听配置"""
        try:
            # 创建新配置
            new_config = {
                'id': None,  # 新配置没有ID
                'session_name': '新会话',
                'enabled': 1,
                'description': '',
                'create_time': None,
                'update_time': None
            }

            # 添加到列表
            self.fixed_listeners.append(new_config)

            # 刷新显示
            self._refresh_list()

            # 选中新添加的项目
            last_index = self.list_widget.count() - 1
            if last_index >= 0:
                self.list_widget.setCurrentRow(last_index)
                # 自动选中会话名称文本框以便编辑
                self.session_name_edit.selectAll()
                self.session_name_edit.setFocus()

        except Exception as e:
            logger.error(f"添加固定监听配置失败: {e}")
            QMessageBox.warning(self, "错误", f"添加固定监听配置失败: {str(e)}")

    @asyncSlot()
    async def _delete_fixed_listener(self):
        """删除选中的固定监听配置"""
        if not self.current_item:
            return

        config = self.current_item.data(Qt.UserRole)
        session_name = config.get('session_name', '')

        # 确认删除
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除固定监听配置 '{session_name}' 吗？\n\n"
            "删除后，该会话将从所有实例的监听列表中移除。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        try:
            # 如果有ID，说明是已保存的配置，需要从数据库删除
            config_id = config.get('id')
            if config_id:
                success = await message_listener.delete_fixed_listener(config_id)
                if not success:
                    QMessageBox.warning(self, "错误", "删除固定监听配置失败")
                    return

            # 从列表中移除
            self.fixed_listeners.remove(config)

            # 刷新显示
            self._refresh_list()

            # 清空编辑区域
            self._clear_edit_area()
            self._set_edit_enabled(False)
            self.delete_btn.setEnabled(False)

            # 发出配置变化信号
            self.config_changed.emit()

        except Exception as e:
            logger.error(f"删除固定监听配置失败: {e}")
            QMessageBox.warning(self, "错误", f"删除固定监听配置失败: {str(e)}")

    @asyncSlot()
    async def _save_current_item(self):
        """保存当前编辑的项目"""
        # 获取当前配置
        config = None
        if self.current_item:
            config = self.current_item.data(Qt.UserRole)
        else:
            # 如果没有选中项，可能是新添加的配置
            if self.fixed_listeners:
                last_config = self.fixed_listeners[-1]
                if last_config.get('id') is None:  # 确认是新配置
                    config = last_config

        if not config:
            QMessageBox.warning(self, "错误", "没有可保存的配置")
            return

        # 从表单获取最新的值
        session_name = self.session_name_edit.text().strip()
        enabled = self.enabled_checkbox.isChecked()
        description = self.description_edit.toPlainText().strip()

        # 更新配置对象
        config['session_name'] = session_name
        config['enabled'] = 1 if enabled else 0
        config['description'] = description

        # 验证输入
        if not session_name:
            QMessageBox.warning(self, "输入错误", "会话名称不能为空")
            self.session_name_edit.setFocus()
            return

        # 检查重复
        for other_config in self.fixed_listeners:
            if (other_config != config and
                other_config.get('session_name', '').strip() == session_name):
                QMessageBox.warning(self, "输入错误", f"会话名称 '{session_name}' 已存在")
                self.session_name_edit.setFocus()
                return

        try:
            config_id = config.get('id')

            if config_id:
                # 更新现有配置
                success = await message_listener.update_fixed_listener(
                    config_id, session_name, description, enabled
                )
            else:
                # 添加新配置
                success = await message_listener.add_fixed_listener(
                    session_name, description, enabled
                )

            if success:
                # 重新加载配置列表以获取最新数据
                await self._load_fixed_listeners()

                # 尝试重新选中当前项目
                for i in range(self.list_widget.count()):
                    item = self.list_widget.item(i)
                    item_config = item.data(Qt.UserRole)
                    if item_config.get('session_name') == session_name:
                        self.list_widget.setCurrentRow(i)
                        break

                # 发出配置变化信号
                self.config_changed.emit()

                QMessageBox.information(self, "成功", "固定监听配置保存成功")
            else:
                QMessageBox.warning(self, "错误", "保存固定监听配置失败")

        except Exception as e:
            logger.error(f"保存固定监听配置失败: {e}")
            QMessageBox.warning(self, "错误", f"保存固定监听配置失败: {str(e)}")

    def accept(self):
        """对话框确认时的处理"""
        # 如果有未保存的更改，提示用户
        if self.current_item:
            config = self.current_item.data(Qt.UserRole)
            if not config.get('id'):  # 新配置但未保存
                reply = QMessageBox.question(
                    self,
                    "未保存的更改",
                    "有未保存的新配置，是否要保存？",
                    QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                    QMessageBox.Yes
                )

                if reply == QMessageBox.Cancel:
                    return
                elif reply == QMessageBox.Yes:
                    # 异步保存
                    asyncio.create_task(self._save_and_close())
                    return

        super().accept()

    @asyncSlot()
    async def _save_and_close(self):
        """保存并关闭对话框"""
        await self._save_current_item()
        super().accept()
