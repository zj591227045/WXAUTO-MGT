"""
插件配置对话框

该模块提供了插件配置的UI界面，包括：
- 基于JSON Schema的动态表单生成
- 配置验证
- 配置保存和加载
"""

import logging
import json
from typing import Dict, Any, Optional

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFormLayout, QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox,
    QComboBox, QTextEdit, QGroupBox, QScrollArea, QWidget,
    QDialogButtonBox, QMessageBox, QTabWidget
)

from wxauto_mgt.core.plugin_system import plugin_manager, plugin_config_manager
from wxauto_mgt.utils.logging import get_logger
from qasync import asyncSlot

logger = get_logger()


class PluginConfigDialog(QDialog):
    """插件配置对话框"""

    config_saved = Signal(str)  # 插件ID

    def __init__(self, parent=None, plugin_id: str = None):
        """
        初始化插件配置对话框

        Args:
            parent: 父窗口
            plugin_id: 插件ID
        """
        super().__init__(parent)

        self.plugin_id = plugin_id
        self.plugin = None
        self.config_schema = {}
        self.current_config = {}
        self.form_widgets = {}

        self._init_ui()
        self._load_plugin_data()

    def _init_ui(self):
        """初始化UI"""
        self.setWindowTitle("插件配置")
        self.setModal(True)
        self.resize(600, 500)

        main_layout = QVBoxLayout(self)

        # 插件信息区域
        self._create_plugin_info_section(main_layout)

        # 配置表单区域
        self._create_config_form_section(main_layout)

        # 按钮区域
        self._create_button_section(main_layout)

    def _create_plugin_info_section(self, main_layout):
        """创建插件信息区域"""
        info_group = QGroupBox("插件信息")
        info_layout = QFormLayout(info_group)

        self.plugin_name_label = QLabel("未知")
        self.plugin_name_label.setFont(QFont("", 10, QFont.Bold))
        info_layout.addRow("名称:", self.plugin_name_label)

        self.plugin_version_label = QLabel("未知")
        info_layout.addRow("版本:", self.plugin_version_label)

        self.plugin_description_label = QLabel("无描述")
        self.plugin_description_label.setWordWrap(True)
        info_layout.addRow("描述:", self.plugin_description_label)

        self.plugin_author_label = QLabel("未知")
        info_layout.addRow("作者:", self.plugin_author_label)

        main_layout.addWidget(info_group)

    def _create_config_form_section(self, main_layout):
        """创建配置表单区域"""
        config_group = QGroupBox("配置参数")
        config_layout = QVBoxLayout(config_group)

        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.form_widget = QWidget()
        self.form_layout = QFormLayout(self.form_widget)
        scroll_area.setWidget(self.form_widget)

        config_layout.addWidget(scroll_area)
        main_layout.addWidget(config_group)

    def _create_button_section(self, main_layout):
        """创建按钮区域"""
        button_layout = QHBoxLayout()

        # 测试连接按钮
        self.test_btn = QPushButton("测试连接")
        self.test_btn.clicked.connect(self._test_connection)
        button_layout.addWidget(self.test_btn)

        # 重置按钮
        self.reset_btn = QPushButton("重置")
        self.reset_btn.clicked.connect(self._reset_config)
        button_layout.addWidget(self.reset_btn)

        button_layout.addStretch()

        # 标准按钮
        self.button_box = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        self.button_box.accepted.connect(self._save_config)
        self.button_box.rejected.connect(self.reject)
        button_layout.addWidget(self.button_box)

        main_layout.addLayout(button_layout)

    @asyncSlot()
    async def _load_plugin_data(self):
        """加载插件数据"""
        try:
            if not self.plugin_id:
                return

            # 获取插件实例
            self.plugin = plugin_manager.get_plugin(self.plugin_id)
            if not self.plugin:
                QMessageBox.warning(self, "错误", f"插件 {self.plugin_id} 未找到")
                self.reject()
                return

            # 获取插件信息
            plugin_info = self.plugin.get_info()
            self.plugin_name_label.setText(plugin_info.name)
            self.plugin_version_label.setText(plugin_info.version)
            self.plugin_description_label.setText(plugin_info.description)
            self.plugin_author_label.setText(plugin_info.author)

            # 获取配置模式
            if hasattr(self.plugin, 'get_config_schema'):
                self.config_schema = self.plugin.get_config_schema()
            else:
                self.config_schema = {}

            # 加载当前配置
            self.current_config = await plugin_config_manager.load_plugin_config(self.plugin_id) or {}

            # 生成配置表单
            self._generate_config_form()

            # 设置窗口标题
            self.setWindowTitle(f"配置插件 - {plugin_info.name}")

        except Exception as e:
            logger.error(f"加载插件数据失败: {e}")
            QMessageBox.warning(self, "错误", f"加载插件数据失败: {str(e)}")
            self.reject()

    def _generate_config_form(self):
        """根据JSON Schema生成配置表单"""
        try:
            # 清空现有表单
            self._clear_form()

            if not self.config_schema:
                no_config_label = QLabel("此插件无需配置")
                no_config_label.setAlignment(Qt.AlignCenter)
                self.form_layout.addRow(no_config_label)
                return

            # 获取属性定义
            properties = self.config_schema.get('properties', {})
            required_fields = self.config_schema.get('required', [])

            # 为每个属性创建表单控件
            for field_name, field_schema in properties.items():
                widget = self._create_form_widget(field_name, field_schema, required_fields)
                if widget:
                    # 创建标签
                    label_text = field_schema.get('title', field_name)
                    if field_name in required_fields:
                        label_text += " *"

                    label = QLabel(label_text)
                    if field_schema.get('description'):
                        label.setToolTip(field_schema['description'])
                        widget.setToolTip(field_schema['description'])

                    self.form_layout.addRow(label, widget)
                    self.form_widgets[field_name] = widget

            # 加载当前配置值
            self._load_config_values()

        except Exception as e:
            logger.error(f"生成配置表单失败: {e}")
            QMessageBox.warning(self, "错误", f"生成配置表单失败: {str(e)}")

    def _create_form_widget(self, field_name: str, field_schema: Dict[str, Any], required_fields: list):
        """创建表单控件"""
        field_type = field_schema.get('type', 'string')
        field_format = field_schema.get('format', '')

        if field_type == 'string':
            if field_format == 'password':
                widget = QLineEdit()
                widget.setEchoMode(QLineEdit.Password)
            elif 'enum' in field_schema:
                widget = QComboBox()
                widget.addItems(field_schema['enum'])
            else:
                widget = QLineEdit()
            
            if 'default' in field_schema:
                if isinstance(widget, QLineEdit):
                    widget.setText(str(field_schema['default']))
                elif isinstance(widget, QComboBox):
                    default_value = str(field_schema['default'])
                    index = widget.findText(default_value)
                    if index >= 0:
                        widget.setCurrentIndex(index)

        elif field_type == 'integer':
            widget = QSpinBox()
            widget.setRange(
                field_schema.get('minimum', -2147483648),
                field_schema.get('maximum', 2147483647)
            )
            if 'default' in field_schema:
                widget.setValue(field_schema['default'])

        elif field_type == 'number':
            widget = QDoubleSpinBox()
            widget.setRange(
                field_schema.get('minimum', -1e10),
                field_schema.get('maximum', 1e10)
            )
            widget.setDecimals(2)
            if 'default' in field_schema:
                widget.setValue(field_schema['default'])

        elif field_type == 'boolean':
            widget = QCheckBox()
            if 'default' in field_schema:
                widget.setChecked(field_schema['default'])

        elif field_type == 'array':
            # 对于数组类型，使用文本编辑器，用户输入JSON格式
            widget = QTextEdit()
            widget.setMaximumHeight(100)
            if 'default' in field_schema:
                widget.setPlainText(json.dumps(field_schema['default'], indent=2))

        elif field_type == 'object':
            # 对于对象类型，使用文本编辑器，用户输入JSON格式
            widget = QTextEdit()
            widget.setMaximumHeight(150)
            if 'default' in field_schema:
                widget.setPlainText(json.dumps(field_schema['default'], indent=2))

        else:
            # 默认使用文本输入
            widget = QLineEdit()
            if 'default' in field_schema:
                widget.setText(str(field_schema['default']))

        return widget

    def _load_config_values(self):
        """加载配置值到表单"""
        for field_name, widget in self.form_widgets.items():
            if field_name in self.current_config:
                value = self.current_config[field_name]
                self._set_widget_value(widget, value)

    def _set_widget_value(self, widget, value):
        """设置控件值"""
        if isinstance(widget, QLineEdit):
            widget.setText(str(value))
        elif isinstance(widget, QSpinBox):
            widget.setValue(int(value))
        elif isinstance(widget, QDoubleSpinBox):
            widget.setValue(float(value))
        elif isinstance(widget, QCheckBox):
            widget.setChecked(bool(value))
        elif isinstance(widget, QComboBox):
            index = widget.findText(str(value))
            if index >= 0:
                widget.setCurrentIndex(index)
        elif isinstance(widget, QTextEdit):
            if isinstance(value, (dict, list)):
                widget.setPlainText(json.dumps(value, indent=2))
            else:
                widget.setPlainText(str(value))

    def _get_config_from_form(self) -> Dict[str, Any]:
        """从表单获取配置"""
        config = {}

        for field_name, widget in self.form_widgets.items():
            try:
                if isinstance(widget, QLineEdit):
                    config[field_name] = widget.text()
                elif isinstance(widget, QSpinBox):
                    config[field_name] = widget.value()
                elif isinstance(widget, QDoubleSpinBox):
                    config[field_name] = widget.value()
                elif isinstance(widget, QCheckBox):
                    config[field_name] = widget.isChecked()
                elif isinstance(widget, QComboBox):
                    config[field_name] = widget.currentText()
                elif isinstance(widget, QTextEdit):
                    text = widget.toPlainText().strip()
                    if text:
                        try:
                            # 尝试解析为JSON
                            config[field_name] = json.loads(text)
                        except json.JSONDecodeError:
                            # 如果不是有效JSON，作为字符串处理
                            config[field_name] = text
                    else:
                        config[field_name] = None

            except Exception as e:
                logger.warning(f"获取字段 {field_name} 的值失败: {e}")
                continue

        return config

    def _validate_config(self, config: Dict[str, Any]) -> tuple[bool, str]:
        """验证配置"""
        try:
            # 检查必需字段
            required_fields = self.config_schema.get('required', [])
            for field in required_fields:
                if field not in config or not config[field]:
                    field_title = self.config_schema.get('properties', {}).get(field, {}).get('title', field)
                    return False, f"必需字段 '{field_title}' 不能为空"

            # 使用插件的验证方法
            if hasattr(self.plugin, 'validate_config'):
                is_valid, error_msg = self.plugin.validate_config(config)
                if not is_valid:
                    return False, error_msg

            return True, ""

        except Exception as e:
            return False, f"配置验证失败: {str(e)}"

    @asyncSlot()
    async def _save_config(self):
        """保存配置"""
        try:
            # 获取表单配置
            config = self._get_config_from_form()

            # 验证配置
            is_valid, error_msg = self._validate_config(config)
            if not is_valid:
                QMessageBox.warning(self, "配置错误", error_msg)
                return

            # 保存配置
            success = await plugin_config_manager.save_plugin_config(
                self.plugin_id, config, self.config_schema
            )

            if success:
                self.config_saved.emit(self.plugin_id)
                QMessageBox.information(self, "成功", "配置保存成功")
                self.accept()
            else:
                QMessageBox.warning(self, "错误", "配置保存失败")

        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            QMessageBox.warning(self, "错误", f"保存配置失败: {str(e)}")

    @Slot()
    def _reset_config(self):
        """重置配置"""
        reply = QMessageBox.question(self, "确认", "确定要重置配置吗？",
                                   QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.current_config = {}
            self._load_config_values()

    @asyncSlot()
    async def _test_connection(self):
        """测试连接"""
        try:
            # 获取当前表单配置
            config = self._get_config_from_form()

            # 验证配置
            is_valid, error_msg = self._validate_config(config)
            if not is_valid:
                QMessageBox.warning(self, "配置错误", f"无法测试连接: {error_msg}")
                return

            # 临时更新插件配置进行测试
            if hasattr(self.plugin, 'update_config'):
                await self.plugin.update_config(config)

            # 执行连接测试
            if hasattr(self.plugin, 'test_connection'):
                result = await self.plugin.test_connection()
                if result.get('success'):
                    QMessageBox.information(self, "测试成功", 
                                          f"连接测试成功\n{result.get('message', '')}")
                else:
                    QMessageBox.warning(self, "测试失败", 
                                      f"连接测试失败\n{result.get('error', '')}")
            else:
                QMessageBox.information(self, "提示", "此插件不支持连接测试")

        except Exception as e:
            logger.error(f"测试连接失败: {e}")
            QMessageBox.warning(self, "错误", f"测试连接失败: {str(e)}")

    def _clear_form(self):
        """清空表单"""
        # 清除所有控件
        while self.form_layout.count():
            child = self.form_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        self.form_widgets.clear()
