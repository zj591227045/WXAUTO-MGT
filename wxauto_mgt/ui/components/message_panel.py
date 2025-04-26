"""
消息监听面板模块

实现消息监听功能的UI界面，包括监听对象列表、消息列表等。
"""

from typing import Dict, List, Optional, Tuple
import json
import csv
from datetime import datetime
from collections import defaultdict

from PySide6.QtCore import Qt, Signal, Slot, QTimer, QMetaObject, Q_ARG
from PySide6.QtGui import QIcon, QAction, QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, 
    QTableWidgetItem, QLabel, QHeaderView, QMessageBox, QMenu,
    QToolBar, QLineEdit, QComboBox, QSplitter, QTextEdit, QCheckBox,
    QGroupBox, QTabWidget, QFileDialog
)

from wxauto_mgt.core.api_client import instance_manager
from wxauto_mgt.core.message_listener import MessageListener, message_listener
from wxauto_mgt.utils.logging import get_logger
from wxauto_mgt.core.config_manager import config_manager

logger = get_logger()


class MessageListenerPanel(QWidget):
    """
    消息监听面板，用于管理微信消息监听
    """
    
    # 定义信号
    listener_added = Signal(str, str)  # 实例ID, wxid
    listener_removed = Signal(str, str)  # 实例ID, wxid
    message_processed = Signal(str)  # 消息ID
    
    def __init__(self, parent=None):
        """初始化消息监听面板"""
        super().__init__(parent)
        
        self._init_ui()
        
        # 定时刷新消息列表
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_messages)
        self._refresh_timer.start(5000)  # 每5秒刷新一次
        
        logger.debug("消息监听面板已初始化")
    
    def _init_ui(self):
        """初始化UI组件"""
        # 主布局
        main_layout = QVBoxLayout(self)
        
        # 上部工具栏
        toolbar_layout = QHBoxLayout()
        
        # 启动/停止按钮
        self.start_btn = QPushButton("启动监听")
        self.start_btn.clicked.connect(self._toggle_listener)
        toolbar_layout.addWidget(self.start_btn)
        
        # 添加监听对象按钮
        self.add_btn = QPushButton("添加监听对象")
        self.add_btn.clicked.connect(self._add_listener)
        toolbar_layout.addWidget(self.add_btn)
        
        # 刷新按钮
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self.refresh_listeners)
        toolbar_layout.addWidget(self.refresh_btn)
        
        # 导出按钮
        self.export_btn = QPushButton("导出消息")
        self.export_btn.clicked.connect(self._export_messages)
        toolbar_layout.addWidget(self.export_btn)
        
        # 统计按钮
        self.stats_btn = QPushButton("消息统计")
        self.stats_btn.clicked.connect(self._show_message_stats)
        toolbar_layout.addWidget(self.stats_btn)
        
        # 搜索框
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索消息...")
        self.search_edit.textChanged.connect(self._filter_messages)
        toolbar_layout.addWidget(self.search_edit)
        
        # 实例过滤下拉框
        self.instance_filter = QComboBox()
        self.instance_filter.addItem("全部实例", "")
        self.instance_filter.currentIndexChanged.connect(self._filter_messages)
        toolbar_layout.addWidget(self.instance_filter)
        
        # 自动刷新复选框
        self.auto_refresh_check = QCheckBox("自动刷新")
        self.auto_refresh_check.setChecked(True)
        self.auto_refresh_check.stateChanged.connect(self._toggle_auto_refresh)
        toolbar_layout.addWidget(self.auto_refresh_check)
        
        toolbar_layout.addStretch()
        
        main_layout.addLayout(toolbar_layout)
        
        # 创建分割器
        splitter = QSplitter(Qt.Vertical)
        
        # 上部分：监听对象列表
        listener_group = QGroupBox("监听对象")
        listener_layout = QVBoxLayout(listener_group)
        
        # 监听对象表格
        self.listener_table = QTableWidget(0, 4)  # 0行，4列
        self.listener_table.setHorizontalHeaderLabels(["实例", "监听对象", "最后消息", "操作"])
        self.listener_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.listener_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.listener_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.listener_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.listener_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.listener_table.customContextMenuRequested.connect(self._show_listener_context_menu)
        self.listener_table.cellClicked.connect(self._on_listener_selected)
        
        listener_layout.addWidget(self.listener_table)
        
        splitter.addWidget(listener_group)
        
        # 下部分：消息列表和消息内容
        message_splitter = QSplitter(Qt.Horizontal)
        
        # 消息列表分组
        message_group = QGroupBox("消息列表")
        message_layout = QVBoxLayout(message_group)
        
        # 消息表格
        self.message_table = QTableWidget(0, 5)  # 0行，5列
        self.message_table.setHorizontalHeaderLabels(["时间", "发送者", "接收者", "类型", "状态"])
        self.message_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.message_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.message_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.message_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.message_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.message_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.message_table.customContextMenuRequested.connect(self._show_message_context_menu)
        self.message_table.cellClicked.connect(self._on_message_selected)
        
        message_layout.addWidget(self.message_table)
        
        # 消息操作按钮
        message_btn_layout = QHBoxLayout()
        
        # 处理按钮
        self.process_btn = QPushButton("标记为已处理")
        self.process_btn.clicked.connect(self._process_message)
        message_btn_layout.addWidget(self.process_btn)
        
        # 回复按钮
        self.reply_btn = QPushButton("回复")
        self.reply_btn.clicked.connect(self._reply_message)
        message_btn_layout.addWidget(self.reply_btn)
        
        # 删除按钮
        self.delete_btn = QPushButton("删除")
        self.delete_btn.clicked.connect(self._delete_message)
        message_btn_layout.addWidget(self.delete_btn)
        
        message_btn_layout.addStretch()
        
        message_layout.addLayout(message_btn_layout)
        
        message_splitter.addWidget(message_group)
        
        # 消息内容分组
        content_group = QGroupBox("消息内容")
        content_layout = QVBoxLayout(content_group)
        
        # 消息内容编辑框
        self.content_text = QTextEdit()
        self.content_text.setReadOnly(True)
        content_layout.addWidget(self.content_text)
        
        message_splitter.addWidget(content_group)
        
        splitter.addWidget(message_splitter)
        
        # 设置分割器的初始大小
        splitter.setSizes([200, 400])
        message_splitter.setSizes([300, 300])
        
        main_layout.addWidget(splitter)
        
        # 状态栏
        status_layout = QHBoxLayout()
        self.status_label = QLabel("共 0 个监听对象")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        
        main_layout.addLayout(status_layout)
        
        # 加载数据
        self._load_instance_filter()
        self.refresh_listeners()
    
    def _load_instance_filter(self):
        """加载实例过滤器选项"""
        # 清除现有项
        current_data = self.instance_filter.currentData()
        self.instance_filter.clear()
        self.instance_filter.addItem("全部实例", "")
        
        # 获取实例列表
        instances = config_manager.get_enabled_instances()
        
        # 添加实例到下拉框
        for instance in instances:
            instance_id = instance.get("instance_id", "")
            name = instance.get("name", instance_id)
            self.instance_filter.addItem(name, instance_id)
        
        # 恢复之前的选择
        if current_data:
            index = self.instance_filter.findData(current_data)
            if index >= 0:
                self.instance_filter.setCurrentIndex(index)
    
    def refresh_listeners(self):
        """刷新监听对象列表"""
        # 清空表格
        self.listener_table.setRowCount(0)
        
        # 获取所有监听对象
        listeners = message_listener.get_active_listeners()
        
        # 更新表格
        for instance_id, who_list in listeners.items():
            for who in who_list:
                row = self.listener_table.rowCount()
                self.listener_table.insertRow(row)
                
                # 实例ID
                self.listener_table.setItem(row, 0, QTableWidgetItem(instance_id))
                
                # 监听对象
                self.listener_table.setItem(row, 1, QTableWidgetItem(who))
                
                # 最后消息时间
                self.listener_table.setItem(row, 2, QTableWidgetItem("未知"))
                
                # 操作按钮
                remove_btn = QPushButton("移除")
                remove_btn.clicked.connect(lambda checked, i=instance_id, w=who: self._remove_listener(i, w))
                self.listener_table.setCellWidget(row, 3, remove_btn)
        
        # 更新状态标签
        total = sum(len(who_list) for who_list in listeners.values())
        self.status_label.setText(f"共 {total} 个监听对象")
    
    async def _toggle_listener(self):
        """切换监听服务状态"""
        if message_listener.running:
            await message_listener.stop()
            self.start_btn.setText("启动监听")
        else:
            await message_listener.start()
            self.start_btn.setText("停止监听")
    
    def _add_listener(self):
        """添加监听对象"""
        from wxauto_mgt.ui.components.dialogs import AddListenerDialog
        
        dialog = AddListenerDialog(self)
        if dialog.exec():
            listener_data = dialog.get_listener_data()
            # 添加监听对象...
            self.refresh_listeners()
    
    async def _remove_listener(self, instance_id: str, who: str):
        """
        移除监听对象
        
        Args:
            instance_id: 实例ID
            who: 监听对象
        """
        await message_listener.remove_listener(instance_id, who)
        self.refresh_listeners()
    
    def _refresh_messages(self):
        """刷新消息列表"""
        if not self.auto_refresh_check.isChecked():
            return
            
        # 获取当前选中的监听对象
        selected_rows = self.listener_table.selectedItems()
        if not selected_rows:
            return
            
        row = selected_rows[0].row()
        instance_id = self.listener_table.item(row, 0).text()
        wxid = self.listener_table.item(row, 1).text()
        
        # 这里应该从消息监听器或数据库获取消息
        # 为了演示，使用模拟数据
        # TODO: 实现实际的消息获取逻辑
        messages = self._get_messages(instance_id, wxid)
        
        # 更新消息列表
        self._update_message_table(messages)
        
        # 更新状态标签
        self.status_label.setText(f"共 {self.listener_table.rowCount()} 个监听对象，{len(messages)} 条消息")
    
    def _get_messages(self, instance_id: str, wxid: str) -> List[Dict]:
        """
        获取消息列表
        
        Args:
            instance_id: 实例ID
            wxid: 微信ID
            
        Returns:
            List[Dict]: 消息列表
        """
        # 这里应该从消息监听器或数据库获取消息
        # 为了演示，返回一些模拟数据
        # TODO: 实现实际的消息获取逻辑
        
        # 获取消息列表
        # 注意：实际项目中需实现此功能
        messages = []
        for i in range(5):
            messages.append({
                "message_id": f"msg_{i}",
                "instance_id": instance_id,
                "sender": wxid if i % 2 == 0 else "system",
                "receiver": "me" if i % 2 == 0 else wxid,
                "content": f"测试消息 {i}",
                "timestamp": int(QDateTime.currentDateTime().toSecsSinceEpoch()) - i * 3600,
                "status": "pending" if i % 3 == 0 else ("processing" if i % 3 == 1 else "processed")
            })
        
        return messages
    
    def _update_message_table(self, messages: List[Dict]):
        """
        更新消息表格
        
        Args:
            messages: 消息列表
        """
        # 清空表格
        self.message_table.setRowCount(0)
        
        # 添加消息到表格
        for message in messages:
            self._add_message_to_table(message)
    
    def _add_message_to_table(self, message: Dict):
        """
        将消息添加到表格
        
        Args:
            message: 消息数据字典
        """
        row = self.message_table.rowCount()
        self.message_table.insertRow(row)
        
        # 时间
        timestamp = message.get("timestamp", 0)
        time_str = QDateTime.fromSecsSinceEpoch(timestamp).toString("yyyy-MM-dd hh:mm:ss")
        time_item = QTableWidgetItem(time_str)
        time_item.setData(Qt.UserRole, message.get("message_id", ""))
        self.message_table.setItem(row, 0, time_item)
        
        # 发送者
        sender = message.get("sender", "")
        sender_item = QTableWidgetItem(sender)
        self.message_table.setItem(row, 1, sender_item)
        
        # 接收者
        receiver = message.get("receiver", "")
        receiver_item = QTableWidgetItem(receiver)
        self.message_table.setItem(row, 2, receiver_item)
        
        # 类型
        message_type = message.get("type", "text")
        type_item = QTableWidgetItem(message_type)
        self.message_table.setItem(row, 3, type_item)
        
        # 状态
        status = message.get("status", "pending")
        status_text = {
            "pending": "待处理",
            "processing": "处理中",
            "processed": "已处理",
            "failed": "失败"
        }.get(status, status)
        
        status_item = QTableWidgetItem(status_text)
        status_color = {
            "pending": QColor(0, 0, 255),  # 蓝色
            "processing": QColor(255, 165, 0),  # 橙色
            "processed": QColor(0, 170, 0),  # 绿色
            "failed": QColor(255, 0, 0)  # 红色
        }.get(status, QColor(0, 0, 0))
        
        status_item.setForeground(status_color)
        self.message_table.setItem(row, 4, status_item)
    
    def _filter_messages(self):
        """过滤消息列表"""
        search_text = self.search_edit.text().lower()
        instance_id = self.instance_filter.currentData()
        
        # 使用缓存优化性能
        if not hasattr(self, '_message_cache'):
            self._message_cache = []
        
        # 应用过滤
        for row in range(self.message_table.rowCount()):
            show_row = True
            if instance_id:
                msg_instance = self.message_table.item(row, 0).data(Qt.UserRole)
                if msg_instance != instance_id:
                    show_row = False
            
            if search_text:
                found = False
                for col in range(self.message_table.columnCount()):
                    item = self.message_table.item(row, col)
                    if item and search_text in item.text().lower():
                        found = True
                        break
                if not found:
                    show_row = False
            
            self.message_table.setRowHidden(row, not show_row)
    
    def _toggle_auto_refresh(self, state):
        """切换自动刷新状态"""
        if state == Qt.Checked:
            self._refresh_timer.start()
        else:
            self._refresh_timer.stop()
    
    def _on_listener_selected(self, row, column):
        """
        监听对象选中事件
        
        Args:
            row: 行索引
            column: 列索引
        """
        # 获取所选监听对象的信息
        instance_id = self.listener_table.item(row, 0).text()
        wxid = self.listener_table.item(row, 1).text()
        
        # 刷新该监听对象的消息
        self._view_listener_messages(instance_id=instance_id, wxid=wxid)
    
    def _on_message_selected(self, row, column):
        """
        消息选中事件
        
        Args:
            row: 行索引
            column: 列索引
        """
        # 获取所选消息的内容
        message_id = self.message_table.item(row, 0).data(Qt.UserRole)
        
        # 这里应该从消息监听器或数据库获取消息内容
        # 为了演示，使用模拟数据
        # TODO: 实现实际的消息获取逻辑
        content = f"消息ID: {message_id}\n\n"
        content += "这是消息内容..."
        
        # 显示消息内容
        self.content_text.setText(content)
    
    def _show_listener_context_menu(self, position):
        """
        显示监听对象上下文菜单
        
        Args:
            position: 点击位置
        """
        menu = QMenu(self)
        
        refresh_action = menu.addAction("刷新")
        refresh_action.triggered.connect(self.refresh_listeners)
        
        row = self.listener_table.rowAt(position.y())
        if row >= 0:
            instance_id = self.listener_table.item(row, 0).text()
            wxid = self.listener_table.item(row, 1).text()
            
            menu.addSeparator()
            
            view_action = menu.addAction("查看消息")
            view_action.triggered.connect(lambda: self._view_listener_messages(instance_id=instance_id, wxid=wxid))
            
            remove_action = menu.addAction("移除")
            remove_action.triggered.connect(lambda: self._remove_listener(instance_id=instance_id, wxid=wxid))
        
        menu.exec(self.listener_table.mapToGlobal(position))
    
    def _show_message_context_menu(self, position):
        """
        显示消息上下文菜单
        
        Args:
            position: 点击位置
        """
        menu = QMenu(self)
        
        refresh_action = menu.addAction("刷新")
        refresh_action.triggered.connect(self._refresh_messages)
        
        row = self.message_table.rowAt(position.y())
        if row >= 0:
            message_id = self.message_table.item(row, 0).data(Qt.UserRole)
            
            menu.addSeparator()
            
            process_action = menu.addAction("标记为已处理")
            process_action.triggered.connect(lambda: self._process_message(message_id=message_id))
            
            reply_action = menu.addAction("回复")
            reply_action.triggered.connect(lambda: self._reply_message(message_id=message_id))
            
            menu.addSeparator()
            
            delete_action = menu.addAction("删除")
            delete_action.triggered.connect(lambda: self._delete_message(message_id=message_id))
        
        menu.exec(self.message_table.mapToGlobal(position))
    
    def _view_listener_messages(self, checked=False, instance_id=None, wxid=None):
        """
        查看监听对象的消息
        
        Args:
            checked: 按钮是否被选中
            instance_id: 实例ID
            wxid: 微信ID
        """
        # 如果参数为None，从发送者获取
        sender = self.sender()
        if (instance_id is None or wxid is None) and sender:
            instance_id = sender.property("instance_id")
            wxid = sender.property("wxid")
        
        if not instance_id or not wxid:
            logger.error("查看消息时缺少实例ID或微信ID")
            return
        
        # 获取消息列表
        messages = self._get_messages(instance_id, wxid)
        
        # 更新消息表格
        self._update_message_table(messages)
        
        # 更新状态标签
        self.status_label.setText(f"共 {self.listener_table.rowCount()} 个监听对象，{len(messages)} 条消息")
    
    def _process_message(self, checked=False, message_id=None):
        """
        标记消息为已处理
        
        Args:
            checked: 按钮是否被选中
            message_id: 消息ID
        """
        # 如果message_id为None，从所选行获取
        if message_id is None:
            selected_items = self.message_table.selectedItems()
            if not selected_items:
                return
            
            row = selected_items[0].row()
            message_id = self.message_table.item(row, 0).data(Qt.UserRole)
        
        if not message_id:
            logger.error("处理消息时缺少消息ID")
            return
        
        # 标记消息为已处理
        # TODO: 实现消息处理逻辑
        success = True  # 假设总是成功
        
        if success:
            self.message_processed.emit(message_id)
            self._refresh_messages()
            QMessageBox.information(self, "处理成功", f"消息 {message_id} 已标记为已处理")
        else:
            QMessageBox.warning(self, "处理失败", f"无法处理消息: {message_id}")
    
    def _reply_message(self, checked=False, message_id=None):
        """
        回复消息
        
        Args:
            checked: 按钮是否被选中
            message_id: 消息ID
        """
        # 如果message_id为None，从所选行获取
        if message_id is None:
            selected_items = self.message_table.selectedItems()
            if not selected_items:
                return
            
            row = selected_items[0].row()
            message_id = self.message_table.item(row, 0).data(Qt.UserRole)
            sender = self.message_table.item(row, 1).text()
        
        if not message_id:
            logger.error("回复消息时缺少消息ID")
            return
        
        # 导入回复对话框
        from wxauto_mgt.ui.components.dialogs import ReplyMessageDialog
        
        dialog = ReplyMessageDialog(self, message_id, sender)
        if dialog.exec():
            reply_text = dialog.get_reply_text()
            
            # 发送回复
            # TODO: 实现消息回复逻辑
            success = True  # 假设总是成功
            
            if success:
                QMessageBox.information(self, "回复成功", "消息已发送")
                self._refresh_messages()
            else:
                QMessageBox.warning(self, "回复失败", "无法发送回复消息")
    
    def _delete_message(self, checked=False, message_id=None):
        """
        删除消息
        
        Args:
            checked: 按钮是否被选中
            message_id: 消息ID
        """
        # 如果message_id为None，从所选行获取
        if message_id is None:
            selected_items = self.message_table.selectedItems()
            if not selected_items:
                return
            
            row = selected_items[0].row()
            message_id = self.message_table.item(row, 0).data(Qt.UserRole)
        
        if not message_id:
            logger.error("删除消息时缺少消息ID")
            return
        
        # 确认对话框
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除消息 {message_id} 吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 删除消息
            # TODO: 实现消息删除逻辑
            success = True  # 假设总是成功
            
            if success:
                QMessageBox.information(self, "删除成功", f"消息 {message_id} 已删除")
                self._refresh_messages()
            else:
                QMessageBox.warning(self, "删除失败", f"无法删除消息: {message_id}")
    
    def _export_messages(self):
        """导出消息列表"""
        # 选择保存路径
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出消息",
            "",
            "CSV 文件 (*.csv);;JSON 文件 (*.json)"
        )
        
        if not file_path:
            return
        
        try:
            messages = []
            for row in range(self.message_table.rowCount()):
                if self.message_table.isRowHidden(row):
                    continue
                    
                message = {
                    'time': self.message_table.item(row, 0).text(),
                    'sender': self.message_table.item(row, 1).text(),
                    'receiver': self.message_table.item(row, 2).text(),
                    'type': self.message_table.item(row, 3).text(),
                    'status': self.message_table.item(row, 4).text(),
                    'content': self.message_table.item(row, 0).data(Qt.UserRole + 1)
                }
                messages.append(message)
            
            if file_path.endswith('.csv'):
                with open(file_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=messages[0].keys())
                    writer.writeheader()
                    writer.writerows(messages)
            else:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(messages, f, ensure_ascii=False, indent=2)
            
            QMessageBox.information(self, "导出成功", f"成功导出 {len(messages)} 条消息")
            
        except Exception as e:
            logger.error(f"导出消息失败: {e}")
            QMessageBox.warning(self, "导出失败", f"导出消息时发生错误: {str(e)}")
    
    def _show_message_stats(self):
        """显示消息统计信息"""
        stats = defaultdict(lambda: defaultdict(int))
        total = 0
        
        # 统计消息
        for row in range(self.message_table.rowCount()):
            if self.message_table.isRowHidden(row):
                continue
            
            msg_type = self.message_table.item(row, 3).text()
            status = self.message_table.item(row, 4).text()
            
            stats['type'][msg_type] += 1
            stats['status'][status] += 1
            total += 1
        
        # 显示统计结果
        stats_text = f"消息总数: {total}\n\n"
        stats_text += "按类型统计:\n"
        for type_name, count in stats['type'].items():
            percentage = (count / total) * 100
            stats_text += f"- {type_name}: {count} ({percentage:.1f}%)\n"
        
        stats_text += "\n按状态统计:\n"
        for status_name, count in stats['status'].items():
            percentage = (count / total) * 100
            stats_text += f"- {status_name}: {count} ({percentage:.1f}%)\n"
        
        QMessageBox.information(self, "消息统计", stats_text) 