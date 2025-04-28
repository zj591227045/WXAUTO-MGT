"""
服务平台管理面板

该模块提供了服务平台管理的UI界面，包括：
- 显示所有服务平台
- 添加、编辑和删除服务平台
- 测试服务平台连接
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
    QDoubleSpinBox, QCheckBox, QTabWidget, QTextEdit
)

from wxauto_mgt.core.service_platform_manager import platform_manager
from wxauto_mgt.core.service_platform import DifyPlatform, OpenAIPlatform

logger = logging.getLogger(__name__)

class PlatformDialog(QDialog):
    """服务平台编辑对话框"""
    
    def __init__(self, parent=None, platform_data=None):
        """
        初始化对话框
        
        Args:
            parent: 父窗口
            platform_data: 平台数据，如果为None则表示新建平台
        """
        super().__init__(parent)
        self.platform_data = platform_data
        self.setWindowTitle("服务平台配置")
        self.setMinimumWidth(500)
        self.setup_ui()
        
        # 如果是编辑模式，填充数据
        if platform_data:
            self.fill_data(platform_data)
    
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 基本信息
        form_layout = QFormLayout()
        
        self.name_edit = QLineEdit()
        form_layout.addRow("平台名称:", self.name_edit)
        
        self.type_combo = QComboBox()
        self.type_combo.addItems(["dify", "openai"])
        self.type_combo.currentTextChanged.connect(self.on_type_changed)
        form_layout.addRow("平台类型:", self.type_combo)
        
        layout.addLayout(form_layout)
        
        # 配置选项卡
        self.tab_widget = QTabWidget()
        
        # Dify配置
        self.dify_widget = QWidget()
        dify_layout = QFormLayout(self.dify_widget)
        
        self.dify_api_base = QLineEdit()
        self.dify_api_base.setPlaceholderText("https://api.dify.ai/v1")
        dify_layout.addRow("API基础URL:", self.dify_api_base)
        
        self.dify_api_key = QLineEdit()
        self.dify_api_key.setEchoMode(QLineEdit.Password)
        dify_layout.addRow("API密钥:", self.dify_api_key)
        
        self.dify_user_id = QLineEdit()
        self.dify_user_id.setPlaceholderText("default_user")
        dify_layout.addRow("用户ID:", self.dify_user_id)
        
        self.tab_widget.addTab(self.dify_widget, "Dify配置")
        
        # OpenAI配置
        self.openai_widget = QWidget()
        openai_layout = QFormLayout(self.openai_widget)
        
        self.openai_api_base = QLineEdit()
        self.openai_api_base.setPlaceholderText("https://api.openai.com/v1")
        openai_layout.addRow("API基础URL:", self.openai_api_base)
        
        self.openai_api_key = QLineEdit()
        self.openai_api_key.setEchoMode(QLineEdit.Password)
        openai_layout.addRow("API密钥:", self.openai_api_key)
        
        self.openai_model = QLineEdit()
        self.openai_model.setPlaceholderText("gpt-3.5-turbo")
        openai_layout.addRow("模型:", self.openai_model)
        
        self.openai_temperature = QDoubleSpinBox()
        self.openai_temperature.setRange(0.0, 2.0)
        self.openai_temperature.setSingleStep(0.1)
        self.openai_temperature.setValue(0.7)
        openai_layout.addRow("温度:", self.openai_temperature)
        
        self.openai_max_tokens = QSpinBox()
        self.openai_max_tokens.setRange(1, 4096)
        self.openai_max_tokens.setValue(1000)
        openai_layout.addRow("最大令牌数:", self.openai_max_tokens)
        
        self.openai_system_prompt = QTextEdit()
        self.openai_system_prompt.setPlaceholderText("你是一个有用的助手。")
        self.openai_system_prompt.setMaximumHeight(100)
        openai_layout.addRow("系统提示词:", self.openai_system_prompt)
        
        self.tab_widget.addTab(self.openai_widget, "OpenAI配置")
        
        layout.addWidget(self.tab_widget)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        self.test_button = QPushButton("测试连接")
        self.test_button.clicked.connect(self.test_connection)
        button_layout.addWidget(self.test_button)
        
        button_layout.addStretch()
        
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        self.save_button = QPushButton("保存")
        self.save_button.clicked.connect(self.accept)
        self.save_button.setDefault(True)
        button_layout.addWidget(self.save_button)
        
        layout.addLayout(button_layout)
        
        # 根据当前类型显示对应的配置选项卡
        self.on_type_changed(self.type_combo.currentText())
    
    def on_type_changed(self, platform_type):
        """
        平台类型变更处理
        
        Args:
            platform_type: 平台类型
        """
        if platform_type == "dify":
            self.tab_widget.setCurrentWidget(self.dify_widget)
        elif platform_type == "openai":
            self.tab_widget.setCurrentWidget(self.openai_widget)
    
    def fill_data(self, platform_data):
        """
        填充平台数据
        
        Args:
            platform_data: 平台数据
        """
        self.name_edit.setText(platform_data.get('name', ''))
        
        platform_type = platform_data.get('type', '')
        if platform_type:
            self.type_combo.setCurrentText(platform_type)
            # 禁用类型选择，编辑模式下不允许修改类型
            self.type_combo.setEnabled(False)
        
        config = platform_data.get('config', {})
        
        if platform_type == "dify":
            self.dify_api_base.setText(config.get('api_base', ''))
            # API密钥不显示，需要重新输入
            self.dify_user_id.setText(config.get('user_id', ''))
        elif platform_type == "openai":
            self.openai_api_base.setText(config.get('api_base', ''))
            # API密钥不显示，需要重新输入
            self.openai_model.setText(config.get('model', ''))
            self.openai_temperature.setValue(config.get('temperature', 0.7))
            self.openai_max_tokens.setValue(config.get('max_tokens', 1000))
            self.openai_system_prompt.setText(config.get('system_prompt', ''))
    
    def get_platform_data(self):
        """
        获取平台数据
        
        Returns:
            Dict: 平台数据
        """
        platform_type = self.type_combo.currentText()
        
        data = {
            'name': self.name_edit.text().strip(),
            'type': platform_type,
            'config': {}
        }
        
        if platform_type == "dify":
            data['config'] = {
                'api_base': self.dify_api_base.text().strip(),
                'api_key': self.dify_api_key.text().strip(),
                'user_id': self.dify_user_id.text().strip()
            }
        elif platform_type == "openai":
            data['config'] = {
                'api_base': self.openai_api_base.text().strip(),
                'api_key': self.openai_api_key.text().strip(),
                'model': self.openai_model.text().strip(),
                'temperature': self.openai_temperature.value(),
                'max_tokens': self.openai_max_tokens.value(),
                'system_prompt': self.openai_system_prompt.toPlainText().strip()
            }
        
        # 如果是编辑模式，保留平台ID
        if self.platform_data:
            data['platform_id'] = self.platform_data.get('platform_id', '')
        
        return data
    
    async def _test_connection(self, platform_data):
        """
        测试连接
        
        Args:
            platform_data: 平台数据
            
        Returns:
            Dict: 测试结果
        """
        try:
            platform_type = platform_data['type']
            config = platform_data['config']
            
            if platform_type == "dify":
                platform = DifyPlatform(
                    platform_id="test",
                    name="测试",
                    config=config
                )
            elif platform_type == "openai":
                platform = OpenAIPlatform(
                    platform_id="test",
                    name="测试",
                    config=config
                )
            else:
                return {"error": f"不支持的平台类型: {platform_type}"}
            
            # 测试连接
            result = await platform.test_connection()
            return result
        except Exception as e:
            logger.error(f"测试连接失败: {e}")
            return {"error": str(e)}
    
    def test_connection(self):
        """测试连接"""
        # 获取平台数据
        platform_data = self.get_platform_data()
        
        # 检查必要字段
        if not platform_data['name']:
            QMessageBox.warning(self, "警告", "请输入平台名称")
            return
        
        if platform_data['type'] == "dify":
            if not platform_data['config']['api_base']:
                QMessageBox.warning(self, "警告", "请输入API基础URL")
                return
            if not platform_data['config']['api_key']:
                QMessageBox.warning(self, "警告", "请输入API密钥")
                return
        elif platform_data['type'] == "openai":
            if not platform_data['config']['api_key']:
                QMessageBox.warning(self, "警告", "请输入API密钥")
                return
        
        # 禁用按钮
        self.test_button.setEnabled(False)
        self.test_button.setText("测试中...")
        
        # 创建异步任务
        async def run_test():
            result = await self._test_connection(platform_data)
            
            # 在主线程中更新UI
            self.test_button.setEnabled(True)
            self.test_button.setText("测试连接")
            
            if "error" in result:
                QMessageBox.critical(self, "测试失败", f"连接测试失败: {result['error']}")
            else:
                QMessageBox.information(self, "测试成功", "连接测试成功")
        
        # 运行异步任务
        asyncio.create_task(run_test())


class PlatformPanel(QWidget):
    """服务平台管理面板"""
    
    def __init__(self, parent=None):
        """初始化面板"""
        super().__init__(parent)
        self.setup_ui()
        self.load_platforms()
    
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 标题
        title_layout = QHBoxLayout()
        title_label = QLabel("服务平台管理")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        
        # 添加按钮
        self.add_button = QPushButton("添加平台")
        self.add_button.clicked.connect(self.add_platform)
        title_layout.addWidget(self.add_button)
        
        layout.addLayout(title_layout)
        
        # 平台列表
        self.platform_table = QTableWidget()
        self.platform_table.setColumnCount(5)
        self.platform_table.setHorizontalHeaderLabels(["ID", "名称", "类型", "状态", "操作"])
        self.platform_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.platform_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.platform_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.platform_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.platform_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.platform_table.verticalHeader().setVisible(False)
        self.platform_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.platform_table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        layout.addWidget(self.platform_table)
    
    def load_platforms(self):
        """加载平台列表"""
        # 创建异步任务
        async def load():
            try:
                # 获取所有平台
                platforms = await platform_manager.get_all_platforms()
                
                # 清空表格
                self.platform_table.setRowCount(0)
                
                # 填充表格
                for i, platform in enumerate(platforms):
                    self.platform_table.insertRow(i)
                    
                    # ID
                    id_item = QTableWidgetItem(platform['platform_id'])
                    self.platform_table.setItem(i, 0, id_item)
                    
                    # 名称
                    name_item = QTableWidgetItem(platform['name'])
                    self.platform_table.setItem(i, 1, name_item)
                    
                    # 类型
                    type_item = QTableWidgetItem(platform['type'])
                    self.platform_table.setItem(i, 2, type_item)
                    
                    # 状态
                    status_item = QTableWidgetItem("已初始化" if platform['initialized'] else "未初始化")
                    self.platform_table.setItem(i, 3, status_item)
                    
                    # 操作按钮
                    action_widget = QWidget()
                    action_layout = QHBoxLayout(action_widget)
                    action_layout.setContentsMargins(0, 0, 0, 0)
                    action_layout.setSpacing(5)
                    
                    # 编辑按钮
                    edit_button = QPushButton("编辑")
                    edit_button.setProperty("platform_id", platform['platform_id'])
                    edit_button.clicked.connect(self.edit_platform)
                    action_layout.addWidget(edit_button)
                    
                    # 删除按钮
                    delete_button = QPushButton("删除")
                    delete_button.setProperty("platform_id", platform['platform_id'])
                    delete_button.clicked.connect(self.delete_platform)
                    action_layout.addWidget(delete_button)
                    
                    self.platform_table.setCellWidget(i, 4, action_widget)
            except Exception as e:
                logger.error(f"加载平台列表失败: {e}")
                QMessageBox.critical(self, "错误", f"加载平台列表失败: {e}")
        
        # 运行异步任务
        asyncio.create_task(load())
    
    def add_platform(self):
        """添加平台"""
        dialog = PlatformDialog(self)
        if dialog.exec() == QDialog.Accepted:
            platform_data = dialog.get_platform_data()
            
            # 创建异步任务
            async def add():
                try:
                    # 注册平台
                    platform_id = await platform_manager.register_platform(
                        platform_data['type'],
                        platform_data['name'],
                        platform_data['config']
                    )
                    
                    if platform_id:
                        QMessageBox.information(self, "成功", "添加平台成功")
                        self.load_platforms()
                    else:
                        QMessageBox.critical(self, "错误", "添加平台失败")
                except Exception as e:
                    logger.error(f"添加平台失败: {e}")
                    QMessageBox.critical(self, "错误", f"添加平台失败: {e}")
            
            # 运行异步任务
            asyncio.create_task(add())
    
    def edit_platform(self):
        """编辑平台"""
        # 获取平台ID
        button = self.sender()
        platform_id = button.property("platform_id")
        
        # 创建异步任务
        async def edit():
            try:
                # 获取平台数据
                platform = await platform_manager.get_platform(platform_id)
                if not platform:
                    QMessageBox.critical(self, "错误", f"找不到平台: {platform_id}")
                    return
                
                # 显示编辑对话框
                dialog = PlatformDialog(self, platform.to_dict())
                if dialog.exec() == QDialog.Accepted:
                    platform_data = dialog.get_platform_data()
                    
                    # 更新平台
                    success = await platform_manager.update_platform(
                        platform_id,
                        platform_data['name'],
                        platform_data['config']
                    )
                    
                    if success:
                        QMessageBox.information(self, "成功", "更新平台成功")
                        self.load_platforms()
                    else:
                        QMessageBox.critical(self, "错误", "更新平台失败")
            except Exception as e:
                logger.error(f"编辑平台失败: {e}")
                QMessageBox.critical(self, "错误", f"编辑平台失败: {e}")
        
        # 运行异步任务
        asyncio.create_task(edit())
    
    def delete_platform(self):
        """删除平台"""
        # 获取平台ID
        button = self.sender()
        platform_id = button.property("platform_id")
        
        # 确认删除
        reply = QMessageBox.question(
            self, "确认删除", 
            f"确定要删除平台 {platform_id} 吗？\n注意：如果有规则使用该平台，将无法删除。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # 创建异步任务
        async def delete():
            try:
                # 删除平台
                success = await platform_manager.delete_platform(platform_id)
                
                if success:
                    QMessageBox.information(self, "成功", "删除平台成功")
                    self.load_platforms()
                else:
                    QMessageBox.critical(self, "错误", "删除平台失败，可能有规则正在使用该平台")
            except Exception as e:
                logger.error(f"删除平台失败: {e}")
                QMessageBox.critical(self, "错误", f"删除平台失败: {e}")
        
        # 运行异步任务
        asyncio.create_task(delete())
