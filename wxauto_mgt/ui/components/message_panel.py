"""
消息监听面板模块

实现消息监听功能的UI界面，包括监听对象列表、消息列表等。
"""

from typing import Dict, List, Optional, Tuple
import json
import csv
from datetime import datetime
from collections import defaultdict
import asyncio
import time

from PySide6.QtCore import Qt, Signal, Slot, QTimer, QMetaObject, Q_ARG
from PySide6.QtGui import QIcon, QAction, QColor, QIntValidator
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, 
    QTableWidgetItem, QLabel, QHeaderView, QMessageBox, QMenu,
    QToolBar, QLineEdit, QComboBox, QSplitter, QTextEdit, QCheckBox,
    QGroupBox, QTabWidget, QFileDialog
)
from qasync import asyncSlot

from wxauto_mgt.core.api_client import instance_manager
from wxauto_mgt.core.message_listener import MessageListener, message_listener
from wxauto_mgt.utils.logging import get_logger
from wxauto_mgt.core.config_manager import config_manager

# 尝试导入配置存储，如果不可用则忽略
try:
    from wxauto_mgt.core.config_store import config_store
except ImportError:
    config_store = None

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
        
        # 内部状态
        self.current_instance_id = None
        self.selected_listener = None
        self.selected_message_id = None
        self.listener_data = {}  # 保存监听对象数据
        self.messages = []
        self.timeout_minutes = 30  # 默认超时时间，与message_listener一致
        self.poll_interval = 5  # 默认轮询间隔(秒)
        
        # 创建定时器
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self._auto_refresh)
        self.refresh_timer.start(self.poll_interval * 1000)  # 转换为毫秒
        
        # 倒计时刷新定时器
        self.countdown_timer = QTimer()
        self.countdown_timer.timeout.connect(self._update_countdown)
        self.countdown_timer.start(1000)  # 每秒更新一次倒计时
        
        # 初始化实例下拉框
        self._init_instance_filter()
        
        # 初始化
        self.refresh_listeners()
        
        logger.debug("消息监听面板已初始化")
    
    def _init_ui(self):
        """初始化UI组件"""
        # 主布局
        main_layout = QVBoxLayout(self)
        
        # 上部工具栏
        toolbar_layout = QHBoxLayout()
        
        # 设置按钮与选项
        settings_group = QGroupBox("设置")
        settings_layout = QHBoxLayout(settings_group)
        
        # 轮询间隔设置
        settings_layout.addWidget(QLabel("轮询间隔(秒):"))
        self.poll_interval_edit = QLineEdit()
        self.poll_interval_edit.setMaximumWidth(50)
        self.poll_interval_edit.setText(str(5))  # 默认值5秒
        self.poll_interval_edit.setValidator(QIntValidator(1, 60))  # 限制输入1-60之间的整数
        self.poll_interval_edit.editingFinished.connect(self._update_poll_interval)
        settings_layout.addWidget(self.poll_interval_edit)
        
        # 超时时间设置
        settings_layout.addWidget(QLabel("超时时间(分钟):"))
        self.timeout_edit = QLineEdit()
        self.timeout_edit.setMaximumWidth(50)
        self.timeout_edit.setText(str(30))  # 默认值30分钟
        self.timeout_edit.setValidator(QIntValidator(1, 1440))  # 限制输入1-1440之间的整数(1天)
        self.timeout_edit.editingFinished.connect(self._update_timeout)
        settings_layout.addWidget(self.timeout_edit)
        
        # 刷新按钮
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self.refresh_listeners)
        settings_layout.addWidget(self.refresh_btn)
        
        # 统计按钮
        self.stats_btn = QPushButton("消息统计")
        self.stats_btn.clicked.connect(self._show_message_stats)
        settings_layout.addWidget(self.stats_btn)
        
        # 实例过滤下拉框
        self.instance_filter = QComboBox()
        self.instance_filter.addItem("全部实例", "")
        self.instance_filter.currentIndexChanged.connect(self._filter_messages)
        settings_layout.addWidget(self.instance_filter)
        
        # 自动刷新复选框
        self.auto_refresh_check = QCheckBox("自动刷新")
        self.auto_refresh_check.setChecked(True)
        self.auto_refresh_check.stateChanged.connect(self._toggle_auto_refresh)
        settings_layout.addWidget(self.auto_refresh_check)
        
        settings_layout.addStretch()
        
        toolbar_layout.addWidget(settings_group)
        main_layout.addLayout(toolbar_layout)
        
        # 创建分割器
        splitter = QSplitter(Qt.Vertical)
        
        # 上部分：监听对象列表
        listener_group = QGroupBox("监听对象")
        listener_layout = QVBoxLayout(listener_group)
        
        # 监听对象表格
        self.listener_table = QTableWidget(0, 5)  # 0行，5列(增加超时倒计时列)
        self.listener_table.setHorizontalHeaderLabels(["实例", "监听对象", "最后消息", "超时倒计时", "操作"])
        self.listener_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.listener_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
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
        
    def _init_instance_filter(self):
        """初始化实例过滤器选项"""
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
    
    def _update_poll_interval(self):
        """更新轮询间隔设置"""
        try:
            poll_interval = int(self.poll_interval_edit.text())
            if poll_interval < 1:
                poll_interval = 5
                self.poll_interval_edit.setText(str(poll_interval))
            
            # 更新轮询间隔
            self.poll_interval = poll_interval
            
            # 更新消息监听器的轮询间隔
            from wxauto_mgt.core.message_listener import message_listener
            message_listener.poll_interval = poll_interval
            
            # 保存到当前选中实例的配置
            if self.current_instance_id:
                asyncio.create_task(self._save_instance_config(self.current_instance_id, {
                    'poll_interval': poll_interval
                }))
            else:
                # 保存到所有实例
                instances = instance_manager.get_all_instances()
                for instance_id in instances:
                    asyncio.create_task(self._save_instance_config(instance_id, {
                        'poll_interval': poll_interval
                    }))
            
            # 重新设置定时器
            if self.auto_refresh_check.isChecked():
                self.refresh_timer.setInterval(poll_interval * 1000)
            
            logger.debug(f"轮询间隔已更新为 {poll_interval} 秒")
        except Exception as e:
            logger.error(f"更新轮询间隔时出错: {e}")
    
    def _update_timeout(self):
        """更新超时时间设置"""
        try:
            timeout_minutes = int(self.timeout_edit.text())
            if timeout_minutes < 1:
                timeout_minutes = 30
                self.timeout_edit.setText(str(timeout_minutes))
            
            # 更新本地和消息监听器的超时设置
            self.timeout_minutes = timeout_minutes
            from wxauto_mgt.core.message_listener import message_listener
            message_listener.timeout_minutes = timeout_minutes
            
            # 保存到当前选中实例的配置
            if self.current_instance_id:
                asyncio.create_task(self._save_instance_config(self.current_instance_id, {
                    'timeout_minutes': timeout_minutes
                }))
            else:
                # 保存到所有实例
                instances = instance_manager.get_all_instances()
                for instance_id in instances:
                    asyncio.create_task(self._save_instance_config(instance_id, {
                        'timeout_minutes': timeout_minutes
                    }))
            
            logger.debug(f"超时时间已更新为 {timeout_minutes} 分钟")
            
            # 刷新倒计时显示
            self._update_countdown()
        except Exception as e:
            logger.error(f"更新超时时间时出错: {e}")
    
    async def _save_instance_config(self, instance_id, config_update):
        """保存实例配置
        
        Args:
            instance_id: 实例ID
            config_update: 要更新的配置字典
        """
        try:
            from wxauto_mgt.data.db_manager import db_manager
            
            # 首先获取当前配置
            query = "SELECT config FROM instances WHERE instance_id = ?"
            result = await db_manager.fetchone(query, (instance_id,))
            
            if not result:
                logger.error(f"找不到实例: {instance_id}")
                return
            
            # 解析当前配置
            current_config = {}
            try:
                if result['config']:
                    current_config = json.loads(result['config'])
            except Exception as e:
                logger.error(f"解析配置时出错: {e}")
            
            # 更新配置
            current_config.update(config_update)
            
            # 保存回数据库
            update_query = "UPDATE instances SET config = ? WHERE instance_id = ?"
            await db_manager.execute(update_query, (json.dumps(current_config), instance_id))
            
            logger.debug(f"已更新实例 {instance_id} 的配置: {config_update}")
        except Exception as e:
            logger.error(f"保存实例配置时出错: {e}")
    
    @asyncSlot()
    async def refresh_listeners(self):
        """刷新监听对象列表"""
        try:
            # 获取超时设置
            from wxauto_mgt.core.message_listener import message_listener  # 这里访问listener实例
            
            # 获取所有实例
            instances = instance_manager.get_all_instances()
            
            # 从选中的实例或第一个实例中获取配置
            instance_id = self.current_instance_id
            if not instance_id and instances:
                instance_id = list(instances.keys())[0]
                
            if instance_id:
                # 获取实例配置
                from wxauto_mgt.data.db_manager import db_manager
                query = "SELECT config FROM instances WHERE instance_id = ?"
                result = await db_manager.fetchone(query, (instance_id,))
                
                if result and result['config']:
                    try:
                        config = json.loads(result['config'])
                        
                        # 读取轮询间隔设置
                        if 'poll_interval' in config and isinstance(config['poll_interval'], int) and config['poll_interval'] > 0:
                            self.poll_interval = config['poll_interval']
                            self.poll_interval_edit.setText(str(self.poll_interval))
                            message_listener.poll_interval = self.poll_interval
                            if self.auto_refresh_check.isChecked():
                                self.refresh_timer.setInterval(self.poll_interval * 1000)
                            
                        # 读取超时时间设置
                        if 'timeout_minutes' in config and isinstance(config['timeout_minutes'], int) and config['timeout_minutes'] > 0:
                            self.timeout_minutes = config['timeout_minutes']
                            self.timeout_edit.setText(str(self.timeout_minutes))
                            message_listener.timeout_minutes = self.timeout_minutes
                        
                        logger.debug(f"从实例 {instance_id} 加载配置: {config}")
                    except Exception as e:
                        logger.error(f"解析实例配置时出错: {e}")
            
            # 保存选中项
            selected_row = self.listener_table.currentRow()
            selected_instance = None
            selected_who = None
            
            if selected_row >= 0:
                selected_instance = self.listener_table.item(selected_row, 0).text()
                selected_who = self.listener_table.item(selected_row, 1).text()
            
            # 清空表格
            self.listener_table.setRowCount(0)
            self.listener_data = {}
            
            # 获取所有监听对象
            result = message_listener.get_active_listeners()
            if not result:
                self.status_label.setText("共 0 个监听对象")
                return
                
            row = 0
            total_listeners = 0
            
            for instance_id, listeners in result.items():
                if not listeners:
                    continue
                
                api_client = instances.get(instance_id)
                if not api_client:
                    continue
                
                for who in listeners:
                    self.listener_table.insertRow(row)
                    
                    # 保存原始数据
                    listener_info = message_listener.listeners.get(instance_id, {}).get(who)
                    if listener_info:
                        self.listener_data[(instance_id, who)] = listener_info
                    
                    # 实例ID
                    self.listener_table.setItem(row, 0, QTableWidgetItem(instance_id))
                    
                    # 监听对象
                    self.listener_table.setItem(row, 1, QTableWidgetItem(who))
                    
                    # 最后消息时间
                    time_str = "未知"
                    if listener_info:
                        last_time = listener_info.last_message_time
                        if last_time > 0:
                            dt = datetime.fromtimestamp(last_time)
                            time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                    self.listener_table.setItem(row, 2, QTableWidgetItem(time_str))
                    
                    # 超时倒计时
                    countdown = self._calculate_countdown(listener_info)
                    self.listener_table.setItem(row, 3, QTableWidgetItem(countdown))
                    
                    # 操作按钮
                    remove_btn = QPushButton("移除")
                    remove_btn.clicked.connect(lambda checked, i=instance_id, w=who: self._remove_listener(i, w))
                    self.listener_table.setCellWidget(row, 4, remove_btn)
                    
                    # 检查是否是之前选中的项
                    if selected_instance == instance_id and selected_who == who:
                        self.listener_table.selectRow(row)
                        self.selected_listener = (instance_id, who)
                    
                    row += 1
                    total_listeners += 1
            
            # 更新状态栏
            self.status_label.setText(f"共 {total_listeners} 个监听对象")
            
        except Exception as e:
            logger.error(f"刷新监听对象列表失败: {e}")
            logger.exception(e)
    
    def _calculate_countdown(self, listener_info):
        """计算监听超时倒计时"""
        if not listener_info or not hasattr(listener_info, 'last_message_time'):
            return "未知"
        
        last_message_time = listener_info.last_message_time
        if not last_message_time:
            return "未知"
            
        current_time = time.time()
        
        # 计算剩余时间（秒）
        remaining_seconds = (last_message_time + self.timeout_minutes * 60) - current_time
        
        if remaining_seconds <= 0:
            return "已超时"
        
        # 格式化为分:秒
        minutes = int(remaining_seconds // 60)
        seconds = int(remaining_seconds % 60)
        
        return f"{minutes}分{seconds}秒"
    
    def _update_countdown(self):
        """更新所有监听对象的倒计时"""
        for row in range(self.listener_table.rowCount()):
            try:
                instance_id = self.listener_table.item(row, 0).text()
                who = self.listener_table.item(row, 1).text()
                
                listener_info = self.listener_data.get((instance_id, who))
                if listener_info:
                    countdown = self._calculate_countdown(listener_info)
                    self.listener_table.item(row, 3).setText(countdown)
            except Exception as e:
                logger.debug(f"更新倒计时时出错: {e}")
    
    @asyncSlot()
    async def _toggle_listener(self):
        """切换监听服务状态"""
        try:
            if message_listener.running:
                logger.info("停止消息监听服务")
                await message_listener.stop()
                self.start_btn.setText("启动监听")
            else:
                logger.info("启动消息监听服务")
                await message_listener.start()
                self.start_btn.setText("停止监听")
                # 启动后立即刷新一次监听对象
                self.refresh_listeners()
        except Exception as e:
            logger.error(f"切换监听服务状态时出错: {e}")
            QMessageBox.critical(self, "操作失败", f"切换监听服务状态时出错: {str(e)}")
    
    def _add_listener(self):
        """添加监听对象"""
        try:
            from wxauto_mgt.ui.components.dialogs import AddListenerDialog
            
            dialog = AddListenerDialog(self)
            if dialog.exec():
                listener_data = dialog.get_listener_data()
                
                instance_id = listener_data.get("instance_id")
                chat_name = listener_data.get("chat_name")
                
                if not instance_id or not chat_name:
                    QMessageBox.warning(self, "参数错误", "实例ID和聊天名称不能为空")
                    return
                
                # 异步添加监听对象
                asyncio.create_task(self._add_listener_async(
                    instance_id=instance_id,
                    chat_name=chat_name,
                    save_pic=listener_data.get("save_pic", True),
                    save_video=listener_data.get("save_video", True),
                    save_file=listener_data.get("save_file", True),
                    save_voice=listener_data.get("save_voice", True),
                    parse_url=listener_data.get("parse_url", True)
                ))
        except Exception as e:
            logger.error(f"添加监听对象时出错: {e}")
            QMessageBox.critical(self, "操作失败", f"添加监听对象时出错: {str(e)}")
    
    async def _add_listener_async(self, instance_id: str, chat_name: str, **kwargs):
        """异步添加监听对象"""
        try:
            logger.info(f"正在添加监听对象: 实例={instance_id}, 聊天={chat_name}")
            
            # 调用消息监听器添加监听对象
            success = await message_listener.add_listener(
                instance_id=instance_id,
                who=chat_name,
                **kwargs
            )
            
            if success:
                logger.info(f"成功添加监听对象: {chat_name}")
                QMetaObject.invokeMethod(
                    self, 
                    "showSuccessMessage", 
                    Qt.QueuedConnection,
                    Q_ARG(str, "添加成功"),
                    Q_ARG(str, f"成功添加监听对象: {chat_name}")
                )
                # 发送信号
                self.listener_added.emit(instance_id, chat_name)
                # 刷新监听对象列表
                QMetaObject.invokeMethod(self, "refresh_listeners", Qt.QueuedConnection)
            else:
                logger.warning(f"添加监听对象失败: {chat_name}")
                QMetaObject.invokeMethod(
                    self, 
                    "showWarningMessage", 
                    Qt.QueuedConnection,
                    Q_ARG(str, "添加失败"),
                    Q_ARG(str, f"无法添加监听对象: {chat_name}")
                )
        except Exception as e:
            logger.error(f"异步添加监听对象时出错: {e}")
            QMetaObject.invokeMethod(
                self, 
                "showErrorMessage", 
                Qt.QueuedConnection,
                Q_ARG(str, "添加失败"),
                Q_ARG(str, f"添加监听对象时出错: {str(e)}")
            )
    
    async def _remove_listener(self, instance_id: str, who: str):
        """
        移除监听对象
        
        Args:
            instance_id: 实例ID
            who: 监听对象
        """
        try:
            logger.info(f"正在移除监听对象: 实例={instance_id}, 聊天={who}")
            
            # 移除监听对象
            success = await message_listener.remove_listener(instance_id, who)
            
            if success:
                logger.info(f"成功移除监听对象: {who}")
                # 发送信号
                self.listener_removed.emit(instance_id, who)
                # 刷新监听对象列表
                self.refresh_listeners()
                QMessageBox.information(self, "移除成功", f"成功移除监听对象: {who}")
            else:
                logger.warning(f"移除监听对象失败: {who}")
                QMessageBox.warning(self, "移除失败", f"无法移除监听对象: {who}")
        except Exception as e:
            logger.error(f"移除监听对象时出错: {e}")
            QMessageBox.critical(self, "操作失败", f"移除监听对象时出错: {str(e)}")
    
    async def _view_listener_messages(self, checked=False, instance_id=None, wxid=None):
        """
        查看监听对象的消息
        
        Args:
            checked: 按钮是否被选中
            instance_id: 实例ID
            wxid: 微信ID
        """
        try:
            # 记住当前选中的行
            selected_row = -1
            selected_message_id = None
            if self.message_table.selectedItems():
                selected_row = self.message_table.selectedItems()[0].row()
                if selected_row >= 0:
                    selected_message_id = self.message_table.item(selected_row, 0).data(Qt.UserRole)
            
            # 如果参数为None，从发送者获取
            sender = self.sender()
            if (instance_id is None or wxid is None) and sender:
                instance_id = sender.property("instance_id")
                wxid = sender.property("wxid")
            
            if not instance_id or not wxid:
                logger.error("查看消息时缺少实例ID或微信ID")
                return
            
            logger.debug(f"正在查看消息: 实例={instance_id}, 聊天={wxid}")
            
            # 获取消息列表
            messages = await self._get_messages(instance_id, wxid)
            logger.debug(f"获取到 {len(messages)} 条消息")
            
            # 按照多个维度进行去重处理
            unique_messages = {}
            for msg in messages:
                # 使用组合键作为去重标识：实例ID + 聊天名称 + 发送者 + 发送时间戳 + 内容摘要(前20字符)
                msg_content = msg.get("content", "")[:20]  # 使用内容前20个字符作为内容摘要
                sender_id = msg.get("sender", "")
                timestamp = msg.get("timestamp", 0)
                message_id = msg.get("message_id", "")
                
                # 创建消息的唯一标识符
                unique_key = f"{instance_id}:{wxid}:{sender_id}:{timestamp}:{msg_content}"
                
                # 如果这个标识符已经存在，并且当前消息有ID，并且之前存储的消息没有ID，则更新
                if unique_key in unique_messages and message_id:
                    stored_msg = unique_messages[unique_key]
                    if not stored_msg.get("message_id"):
                        unique_messages[unique_key] = msg
                else:
                    unique_messages[unique_key] = msg
            
            # 按时间戳排序
            sorted_messages = sorted(
                unique_messages.values(), 
                key=lambda x: x.get("timestamp", 0), 
                reverse=True
            )
            
            logger.debug(f"去重后剩余 {len(sorted_messages)} 条消息")
            
            # 在UI线程中直接更新表格
            def update_ui():
                try:
                    # 清空表格 - 确保先将行数设为0，避免在添加新消息时引起内存泄漏
                    self.message_table.setRowCount(0)
                    self.message_table.clearContents()
                    
                    # 添加消息到表格
                    new_selected_row = -1
                    for i, msg in enumerate(sorted_messages):
                        self._add_message_to_table(msg)
                        # 检查是否是之前选中的消息
                        if selected_message_id and msg.get("message_id") == selected_message_id:
                            new_selected_row = i
                    
                    # 还原选中状态
                    if new_selected_row >= 0 and new_selected_row < self.message_table.rowCount():
                        self.message_table.selectRow(new_selected_row)
                        self._on_message_selected(new_selected_row, 0)
                    
                    # 更新状态标签
                    count = len(sorted_messages)
                    listener_count = self.listener_table.rowCount()
                    self.status_label.setText(f"共 {listener_count} 个监听对象，{count} 条消息")
                except Exception as e:
                    logger.error(f"更新UI时出错: {e}")
            
            # 使用QTimer在主线程中安全更新UI
            QTimer.singleShot(0, update_ui)
            
        except Exception as e:
            logger.error(f"查看监听对象消息时出错: {e}")
            logger.error(f"错误详细信息", exc_info=True)
    
    @asyncSlot()
    async def _auto_refresh(self):
        """自动刷新监听对象和消息"""
        if not self.auto_refresh_check.isChecked():
            return
            
        # 刷新监听对象列表
        await self.refresh_listeners()
        
        # 更新倒计时
        self._update_countdown()
        
        # 刷新消息列表（如果有选中的监听对象）
        if self.selected_listener:
            instance_id, wxid = self.selected_listener
            await self._view_listener_messages(instance_id=instance_id, wxid=wxid)
    
    @Slot("QVariant")
    def _add_message_to_table_safe(self, message):
        """在主线程中安全地添加消息到表格"""
        try:
            self._add_message_to_table(message)
        except Exception as e:
            logger.error(f"安全添加消息到表格时出错: {e}")
    
    async def _process_message(self, checked=False, message_id=None):
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
        
        try:
            # 获取消息所属的实例ID
            from wxauto_mgt.data.db_manager import db_manager
            message = await db_manager.fetchone(
                "SELECT instance_id, chat_name FROM messages WHERE message_id = ?", 
                (message_id,)
            )
            
            if not message:
                QMessageBox.warning(self, "处理失败", f"找不到消息: {message_id}")
                return
            
            instance_id = message.get("instance_id")
            chat_name = message.get("chat_name")
            
            # 更新消息状态
            result = await db_manager.execute(
                "UPDATE messages SET processed = 1 WHERE message_id = ?",
                (message_id,)
            )
            
            if result:
                self.message_processed.emit(message_id)
                
                # 在UI中直接更新消息状态
                for row in range(self.message_table.rowCount()):
                    item = self.message_table.item(row, 0)
                    if item and item.data(Qt.UserRole) == message_id:
                        status_item = self.message_table.item(row, 4)
                        if status_item:
                            status_item.setText("已处理")
                            status_item.setForeground(QColor(0, 170, 0))  # 绿色
                            break
                
                QMessageBox.information(self, "处理成功", f"消息 {message_id} 已标记为已处理")
                
                # 刷新消息列表
                if instance_id and chat_name:
                    await self._view_listener_messages(instance_id=instance_id, wxid=chat_name)
            else:
                QMessageBox.warning(self, "处理失败", f"无法处理消息: {message_id}")
        except Exception as e:
            logger.error(f"处理消息时出错: {e}")
            QMessageBox.critical(self, "操作失败", f"处理消息时出错: {str(e)}")
    
    @Slot("QVariantList")
    def _update_message_table(self, messages):
        """使用消息数据更新UI表格"""
        try:
            # 清空表格
            self.message_table.setRowCount(0)
            
            # 添加消息到表格
            for msg in messages:
                self._add_message_to_table(msg)
                
        except Exception as e:
            logger.error(f"更新消息表格时出错: {e}")
            QMessageBox.critical(self, "刷新失败", f"更新消息显示时出错: {str(e)}")
    
    @Slot(int)
    def _update_status_count(self, count):
        """更新状态栏消息计数"""
        try:
            self.status_label.setText(f"共 {self.listener_table.rowCount()} 个监听对象，{count} 条消息")
        except Exception as e:
            logger.error(f"更新状态标签时出错: {e}")
    
    async def _get_messages(self, instance_id: str, wxid: str) -> List[Dict]:
        """
        获取消息列表
        
        Args:
            instance_id: 实例ID
            wxid: 微信ID
            
        Returns:
            List[Dict]: 消息列表
        """
        try:
            logger.debug(f"获取消息: 实例={instance_id}, 聊天={wxid}")
            
            # 从数据库获取消息
            from wxauto_mgt.data.db_manager import db_manager
            
            # 构建SQL查询
            query = """
                SELECT * FROM messages 
                WHERE instance_id = ? AND chat_name = ?
                ORDER BY create_time DESC LIMIT 100
            """
            
            # 执行查询
            messages = await db_manager.fetchall(query, (instance_id, wxid))
            logger.debug(f"获取到 {len(messages)} 条消息")
            
            # 格式化消息
            formatted_messages = []
            for msg in messages:
                # 尝试解析JSON内容
                content = msg.get("content", "")
                try:
                    if content and isinstance(content, str) and (content.startswith('{') or content.startswith('[')):
                        content_obj = json.loads(content)
                        if isinstance(content_obj, dict) and "content" in content_obj:
                            content = content_obj["content"]
                except:
                    pass  # 如果解析失败，保持原始内容
                
                formatted_msg = {
                    "message_id": msg.get("message_id", ""),
                    "instance_id": msg.get("instance_id", ""),
                    "sender": msg.get("sender", ""),
                    "sender_remark": msg.get("sender_remark", ""),
                    "receiver": wxid if msg.get("sender", "") != wxid else "me",
                    "content": content,
                    "type": msg.get("message_type", "text"),
                    "timestamp": int(msg.get("create_time", 0)),
                    "status": "processed" if msg.get("processed", 0) else "pending"
                }
                formatted_messages.append(formatted_msg)
            
            return formatted_messages
        except Exception as e:
            logger.error(f"获取消息时出错: {e}")
            return []
    
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
        try:
            # 转换时间戳为日期时间字符串
            if timestamp > 0:
                time_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
            else:
                time_str = "未知时间"
        except Exception as e:
            logger.error(f"时间戳转换错误: {timestamp}, {e}")
            time_str = "时间格式错误"
            
        time_item = QTableWidgetItem(time_str)
        time_item.setData(Qt.UserRole, message.get("message_id", ""))
        time_item.setData(Qt.UserRole + 1, message.get("content", ""))
        self.message_table.setItem(row, 0, time_item)
        
        # 发送者
        sender = message.get("sender", "")
        sender_remark = message.get("sender_remark", "")
        display_sender = sender_remark if sender_remark else sender
        sender_item = QTableWidgetItem(display_sender)
        self.message_table.setItem(row, 1, sender_item)
        
        # 接收者
        receiver = message.get("receiver", "")
        receiver_item = QTableWidgetItem(receiver)
        self.message_table.setItem(row, 2, receiver_item)
        
        # 类型
        message_type = message.get("type", "text")
        type_map = {
            "text": "文本",
            "image": "图片",
            "video": "视频",
            "voice": "语音",
            "file": "文件",
            "link": "链接",
            "friend": "好友消息",
            "sys": "系统消息"
        }
        type_display = type_map.get(message_type, message_type)
        type_item = QTableWidgetItem(type_display)
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
        instance_id = self.instance_filter.currentData()
        
        # 应用过滤
        for row in range(self.message_table.rowCount()):
            show_row = True
            if instance_id:
                msg_instance = self.message_table.item(row, 0).data(Qt.UserRole)
                if msg_instance != instance_id:
                    show_row = False
                
            self.message_table.setRowHidden(row, not show_row)
            
    def _toggle_auto_refresh(self, state):
        """切换自动刷新状态"""
        if state == Qt.Checked:
            self.refresh_timer.start(self.poll_interval * 1000)  # 转换为毫秒
        else:
            self.refresh_timer.stop()
    
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
        
        # 更新当前选中的实例ID
        if instance_id != self.current_instance_id:
            self.current_instance_id = instance_id
            # 异步加载该实例的配置
            asyncio.create_task(self._load_instance_config(instance_id))
        
        # 使用异步任务刷新该监听对象的消息
        asyncio.create_task(self._view_listener_messages(instance_id=instance_id, wxid=wxid))
    
    async def _load_instance_config(self, instance_id):
        """加载实例配置
        
        Args:
            instance_id: 实例ID
        """
        try:
            from wxauto_mgt.data.db_manager import db_manager
            query = "SELECT config FROM instances WHERE instance_id = ?"
            result = await db_manager.fetchone(query, (instance_id,))
            
            if result and result['config']:
                try:
                    config = json.loads(result['config'])
                    
                    # 读取轮询间隔设置
                    if 'poll_interval' in config and isinstance(config['poll_interval'], int) and config['poll_interval'] > 0:
                        self.poll_interval = config['poll_interval']
                        self.poll_interval_edit.setText(str(self.poll_interval))
                        # 更新消息监听器
                        from wxauto_mgt.core.message_listener import message_listener
                        message_listener.poll_interval = self.poll_interval
                        # 更新定时器
                        if self.auto_refresh_check.isChecked():
                            self.refresh_timer.setInterval(self.poll_interval * 1000)
                        
                    # 读取超时时间设置
                    if 'timeout_minutes' in config and isinstance(config['timeout_minutes'], int) and config['timeout_minutes'] > 0:
                        self.timeout_minutes = config['timeout_minutes']
                        self.timeout_edit.setText(str(self.timeout_minutes))
                        # 更新消息监听器
                        from wxauto_mgt.core.message_listener import message_listener
                        message_listener.timeout_minutes = self.timeout_minutes
                        # 刷新倒计时显示
                        self._update_countdown()
                    
                    logger.debug(f"已加载实例 {instance_id} 的配置: {config}")
                except Exception as e:
                    logger.error(f"解析实例配置时出错: {e}")
        except Exception as e:
            logger.error(f"加载实例配置时出错: {e}")
    
    def _on_message_selected(self, row, column):
        """
        消息选中事件
        
        Args:
            row: 行索引
            column: 列索引
        """
        if row < 0:
            return
            
        # 获取所选消息的内容
        message_id = self.message_table.item(row, 0).data(Qt.UserRole)
        content = self.message_table.item(row, 0).data(Qt.UserRole + 1)
        
        # 如果存储的内容为空，尝试从数据库获取
        if not content:
            asyncio.create_task(self._load_message_content(message_id))
            return
        
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
        refresh_action.triggered.connect(self._auto_refresh)
        
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
    
    async def _load_message_content(self, message_id: str):
        """
        从数据库加载消息内容
        
        Args:
            message_id: 消息ID
        """
        try:
            from wxauto_mgt.data.db_manager import db_manager
            query = "SELECT content FROM messages WHERE message_id = ?"
            result = await db_manager.fetchone(query, (message_id,))
            
            if result and 'content' in result:
                content = result['content']
                # 更新UI
                QMetaObject.invokeMethod(
                    self.content_text,
                    "setText",
                    Qt.QueuedConnection,
                    Q_ARG(str, content)
                )
            else:
                # 未找到消息
                QMetaObject.invokeMethod(
                    self.content_text,
                    "setText",
                    Qt.QueuedConnection,
                    Q_ARG(str, f"无法加载消息内容: 消息ID {message_id} 不存在")
                )
        except Exception as e:
            logger.error(f"加载消息内容时出错: {e}")
            QMetaObject.invokeMethod(
                self.content_text,
                "setText",
                Qt.QueuedConnection,
                Q_ARG(str, f"加载消息内容时出错: {str(e)}")
            )
    
    def _export_messages(self):
        """导出消息到CSV文件"""
        try:
            # 检查是否有消息
            if self.message_table.rowCount() == 0:
                QMessageBox.information(self, "导出消息", "没有消息可以导出")
                return
                
            # 打开文件对话框
            file_path, _ = QFileDialog.getSaveFileName(
                self, 
                "导出消息", 
                "", 
                "CSV文件 (*.csv);;所有文件 (*)"
            )
            
            if not file_path:
                return  # 用户取消
                
            # 添加后缀名（如果没有）
            if not file_path.lower().endswith('.csv'):
                file_path += '.csv'
            
            # 收集消息数据
            messages = []
            for row in range(self.message_table.rowCount()):
                if self.message_table.isRowHidden(row):
                    continue
                    
                time_item = self.message_table.item(row, 0)
                sender_item = self.message_table.item(row, 1)
                receiver_item = self.message_table.item(row, 2)
                type_item = self.message_table.item(row, 3)
                status_item = self.message_table.item(row, 4)
                
                # 获取消息ID和内容
                message_id = time_item.data(Qt.UserRole) if time_item else ""
                content = time_item.data(Qt.UserRole + 1) if time_item else ""
                
                messages.append({
                    'time': time_item.text() if time_item else "",
                    'sender': sender_item.text() if sender_item else "",
                    'receiver': receiver_item.text() if receiver_item else "",
                    'type': type_item.text() if type_item else "",
                    'status': status_item.text() if status_item else "",
                    'message_id': message_id,
                    'content': content
                })
            
            # 写入CSV文件
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=['time', 'sender', 'receiver', 'type', 'status', 'message_id', 'content'])
                writer.writeheader()
                writer.writerows(messages)
            
            QMessageBox.information(self, "导出成功", f"成功导出 {len(messages)} 条消息到 {file_path}")
            
        except Exception as e:
            logger.error(f"导出消息时出错: {e}")
            QMessageBox.critical(self, "导出失败", f"导出消息时出错: {str(e)}")
    
    def _reply_message(self, message_id=None):
        """回复消息"""
        # 如果message_id为None，从所选行获取
        if message_id is None:
            selected_items = self.message_table.selectedItems()
            if not selected_items:
                return
            
            row = selected_items[0].row()
            message_id = self.message_table.item(row, 0).data(Qt.UserRole)
        
        logger.debug(f"回复消息: {message_id}")
        QMessageBox.information(self, "回复消息", "消息回复功能尚未实现")
    
    def _delete_message(self, message_id=None):
        """删除消息"""
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
        
        # 确认是否删除
        reply = QMessageBox.question(
            self, 
            "确认删除", 
            "确定要删除此消息吗？",
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
            
        # 使用异步任务执行删除操作
        asyncio.create_task(self._delete_message_async(message_id))
    
    async def _delete_message_async(self, message_id: str):
        """
        异步删除消息
        
        Args:
            message_id: 消息ID
        """
        try:
            # 获取消息所属的实例ID和聊天名称
            from wxauto_mgt.data.db_manager import db_manager
            message = await db_manager.fetchone(
                "SELECT instance_id, chat_name FROM messages WHERE message_id = ?", 
                (message_id,)
            )
            
            if not message:
                QMetaObject.invokeMethod(
                    self,
                    "showWarningMessage",
                    Qt.QueuedConnection,
                    Q_ARG(str, "删除失败"),
                    Q_ARG(str, f"找不到消息: {message_id}")
                )
                return
            
            instance_id = message.get("instance_id")
            chat_name = message.get("chat_name")
            
            # 删除消息
            result = await db_manager.execute(
                "DELETE FROM messages WHERE message_id = ?",
                (message_id,)
            )
            
            if result:
                # 定义成功消息回调
                def show_success():
                    # 从表格中删除对应行
                    for row in range(self.message_table.rowCount()):
                        item = self.message_table.item(row, 0)
                        if item and item.data(Qt.UserRole) == message_id:
                            self.message_table.removeRow(row)
                            break
                            
                    QMessageBox.information(self, "删除成功", f"消息已删除")
                
                # 在主线程中显示成功消息
                QTimer.singleShot(0, show_success)
                
                # 刷新消息列表
                if instance_id and chat_name:
                    await self._view_listener_messages(instance_id=instance_id, wxid=chat_name)
            else:
                QMetaObject.invokeMethod(
                    self,
                    "showWarningMessage",
                    Qt.QueuedConnection,
                    Q_ARG(str, "删除失败"),
                    Q_ARG(str, f"无法删除消息: {message_id}")
                )
        except Exception as e:
            logger.error(f"删除消息时出错: {e}")
            QMetaObject.invokeMethod(
                self,
                "showErrorMessage",
                Qt.QueuedConnection,
                Q_ARG(str, "删除失败"),
                Q_ARG(str, f"删除消息时出错: {str(e)}")
            )
                
    @Slot(str, str)
    def showWarningMessage(self, title, message):
        """显示警告消息"""
        QMessageBox.warning(self, title, message)
    
    @Slot(str, str)
    def showErrorMessage(self, title, message):
        """显示错误消息"""
        QMessageBox.critical(self, title, message)
    
    @Slot(str, str)
    def showSuccessMessage(self, title, message):
        """显示成功消息"""
        QMessageBox.information(self, title, message) 