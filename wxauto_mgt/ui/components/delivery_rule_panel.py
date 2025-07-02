"""
消息转发规则配置面板

该模块提供了消息转发规则管理的UI界面，包括：
- 显示所有消息转发规则
- 添加、编辑和删除消息转发规则
- 按实例过滤规则
"""

import logging
import asyncio
import json
from typing import Dict, List, Optional, Any

from PySide6.QtCore import Qt, Signal, Slot, QSize, QTimer
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QDialog, QFormLayout, QLineEdit, QComboBox, QSpinBox,
    QCheckBox, QTabWidget, QTextEdit
)

from wxauto_mgt.core.service_platform_manager import platform_manager, rule_manager
from wxauto_mgt.core.api_client import instance_manager
from wxauto_mgt.utils.logging import get_logger
from qasync import asyncSlot

logger = get_logger()

class DeliveryRulePanel(QWidget):
    """消息转发规则管理面板"""

    # 定义信号
    rule_added = Signal(str)    # 规则ID
    rule_updated = Signal(str)  # 规则ID
    rule_removed = Signal(str)  # 规则ID
    show_edit_rule_dialog = Signal(dict)  # 显示编辑规则对话框信号

    def __init__(self, parent=None):
        """初始化消息转发规则管理面板"""
        super().__init__(parent)

        self._current_instance_id = None
        self._init_ui()

        # 连接信号
        self.show_edit_rule_dialog.connect(self._show_edit_rule_dialog_in_main_thread)

        # 初始加载规则列表
        self.refresh_rules()

    def _init_ui(self):
        """初始化UI"""
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # 标题栏
        title_layout = QHBoxLayout()

        # 标题
        title_label = QLabel("消息转发规则配置")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        title_layout.addWidget(title_label)

        title_layout.addStretch()

        # 添加规则按钮
        self.add_btn = QPushButton("添加规则")
        self.add_btn.setStyleSheet("""
            QPushButton {
                background-color: #1890ff;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #40a9ff;
            }
        """)
        self.add_btn.clicked.connect(self._add_rule)
        title_layout.addWidget(self.add_btn)

        # 刷新按钮
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #52c41a;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #73d13d;
            }
        """)
        self.refresh_btn.clicked.connect(self.refresh_rules)
        title_layout.addWidget(self.refresh_btn)

        main_layout.addLayout(title_layout)

        # 过滤器状态
        self.filter_layout = QHBoxLayout()
        self.filter_label = QLabel("当前过滤: 全部实例")
        self.filter_layout.addWidget(self.filter_label)

        self.filter_layout.addStretch()

        self.clear_filter_btn = QPushButton("显示全部规则")
        self.clear_filter_btn.setStyleSheet("""
            QPushButton {
                background-color: #1890ff;
                color: white;
                border: none;
                padding: 4px 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #40a9ff;
            }
        """)
        self.clear_filter_btn.clicked.connect(self._clear_filter)
        self.clear_filter_btn.setVisible(False)  # 初始隐藏
        self.filter_layout.addWidget(self.clear_filter_btn)

        main_layout.addLayout(self.filter_layout)

        # 规则列表表格
        self.rule_table = QTableWidget(0, 7)  # 0行，7列
        self.rule_table.setHorizontalHeaderLabels(["ID", "名称", "实例", "聊天匹配", "平台", "优先级", "操作"])
        self.rule_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.rule_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.rule_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.rule_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.rule_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.rule_table.setEditTriggers(QTableWidget.NoEditTriggers)

        main_layout.addWidget(self.rule_table)

        # 状态标签
        self.status_label = QLabel("共 0 个规则")
        self.status_label.setStyleSheet("color: #666666;")
        main_layout.addWidget(self.status_label)

    @asyncSlot()
    async def refresh_rules(self, instance_id=None):
        """
        刷新规则列表

        Args:
            instance_id: 实例ID，如果为None则使用当前过滤的实例ID
        """
        try:
            # 清空表格
            self.rule_table.setRowCount(0)

            # 使用指定的实例ID或当前过滤的实例ID
            filter_id = instance_id if instance_id is not None else self._current_instance_id

            # 获取规则
            rules = await rule_manager.get_all_rules()

            # 过滤规则
            if filter_id:
                filtered_rules = [rule for rule in rules if rule['instance_id'] == filter_id or rule['instance_id'] == '*']
            else:
                filtered_rules = rules

            # 按优先级排序（降序）
            filtered_rules.sort(key=lambda x: (-x['priority'], x['rule_id']))

            # 添加规则到表格
            for rule in filtered_rules:
                self._add_rule_to_table(rule)

            # 更新状态标签
            self.status_label.setText(f"共 {len(filtered_rules)} 个规则")

        except Exception as e:
            logger.error(f"刷新规则列表失败: {e}")
            QMessageBox.warning(self, "错误", f"刷新规则列表失败: {str(e)}")

    def set_instance_filter(self, instance_id: Optional[str]):
        """
        设置实例过滤器

        Args:
            instance_id: 实例ID，如果为None则显示所有规则
        """
        self._current_instance_id = instance_id

        # 更新过滤器状态显示
        if instance_id:
            # 获取实例名称
            instance_name = self._get_instance_name(instance_id)
            self.filter_label.setText(f"当前过滤: {instance_name}")
            self.clear_filter_btn.setVisible(True)

            # 更新添加按钮文本
            self.add_btn.setText(f"为当前实例添加规则")
        else:
            self.filter_label.setText("当前过滤: 全部实例")
            self.clear_filter_btn.setVisible(False)

            # 恢复添加按钮文本
            self.add_btn.setText("添加规则")

        # 刷新规则列表
        self.refresh_rules(instance_id)

    def _clear_filter(self):
        """清除实例过滤器"""
        self.set_instance_filter(None)

    def _get_instance_name(self, instance_id: str) -> str:
        """
        获取实例名称

        Args:
            instance_id: 实例ID

        Returns:
            str: 实例名称，如果找不到则返回实例ID
        """
        # 特殊情况处理
        if not instance_id or instance_id == "*":
            return "全部"

        # 使用缓存避免频繁查询数据库
        if hasattr(self, "_instance_name_cache") and instance_id in self._instance_name_cache:
            return self._instance_name_cache[instance_id]

        # 初始化缓存（如果不存在）
        if not hasattr(self, "_instance_name_cache"):
            self._instance_name_cache = {}

        try:
            # 从数据库获取实例名称
            from wxauto_mgt.data.db_manager import db_manager
            import asyncio

            # 创建异步任务获取实例名称
            async def _get_name():
                try:
                    instance = await db_manager.fetchone(
                        "SELECT name FROM instances WHERE instance_id = ?",
                        (instance_id,)
                    )
                    if instance and "name" in instance:
                        # 更新缓存
                        self._instance_name_cache[instance_id] = instance["name"]
                        return instance["name"]
                    return instance_id
                except Exception as e:
                    logger.error(f"获取实例名称失败: {e}")
                    return instance_id

            # 使用同步方式执行异步任务，但添加更多的错误处理
            loop = asyncio.get_event_loop()
            if loop.is_running():
                try:
                    # 如果事件循环正在运行，使用Future，但设置更短的超时时间
                    future = asyncio.run_coroutine_threadsafe(_get_name(), loop)
                    try:
                        return future.result(timeout=0.5)  # 减少超时时间，避免阻塞UI
                    except asyncio.TimeoutError:
                        logger.warning(f"获取实例名称超时: {instance_id}")
                        return instance_id
                    except asyncio.CancelledError:
                        logger.warning(f"获取实例名称任务被取消: {instance_id}")
                        return instance_id
                    except Exception as e:
                        logger.error(f"获取实例名称失败: {e}")
                        return instance_id
                except Exception as e:
                    logger.error(f"创建异步任务失败: {e}")
                    return instance_id
            else:
                # 如果事件循环未运行，直接返回实例ID，避免阻塞
                logger.warning("事件循环未运行，无法获取实例名称")
                return instance_id
        except Exception as e:
            logger.error(f"获取实例名称失败: {e}")
            return instance_id

    def _get_platform_name(self, platform_id: str) -> str:
        """
        获取平台名称

        Args:
            platform_id: 平台ID

        Returns:
            str: 平台名称，如果找不到则返回平台ID
        """
        # 创建异步任务获取平台名称
        async def _get_name():
            platform = await platform_manager.get_platform(platform_id)
            if platform:
                return platform.name
            return platform_id

        # 执行异步任务
        future = asyncio.ensure_future(_get_name())

        # 这里简单返回平台ID，实际名称会在异步任务完成后更新
        return platform_id

    def _add_rule_to_table(self, rule: Dict[str, Any]):
        """
        将规则添加到表格

        Args:
            rule: 规则数据
        """
        rule_id = rule.get("rule_id", "")
        if not rule_id:
            logger.error(f"规则数据缺少ID字段: {rule}")
            return

        row = self.rule_table.rowCount()
        self.rule_table.insertRow(row)

        # 规则ID
        id_item = QTableWidgetItem(rule_id)
        self.rule_table.setItem(row, 0, id_item)

        # 名称
        name_item = QTableWidgetItem(rule.get("name", ""))
        self.rule_table.setItem(row, 1, name_item)

        # 实例
        instance_id = rule.get("instance_id", "")
        instance_name = "全部" if instance_id == "*" else self._get_instance_name(instance_id)
        instance_item = QTableWidgetItem(instance_name)
        # 为全局规则添加特殊样式
        if instance_id == "*":
            instance_item.setForeground(QColor("#1890ff"))
            instance_item.setToolTip("适用于所有实例")
        self.rule_table.setItem(row, 2, instance_item)

        # 聊天匹配
        chat_pattern = rule.get("chat_pattern", "")
        only_at_messages = rule.get("only_at_messages", 0)
        at_name = rule.get("at_name", "")

        # 构建显示文本，如果启用了@消息设置，则添加标记
        display_pattern = chat_pattern
        if only_at_messages == 1 and at_name:
            # 处理多个@名称的情况
            if ',' in at_name:
                at_names = [name.strip() for name in at_name.split(',')]
                at_display = ', '.join(at_names)
                display_pattern = f"{chat_pattern} [@{at_display}]"
            else:
                display_pattern = f"{chat_pattern} [@{at_name}]"

        pattern_item = QTableWidgetItem(display_pattern)

        # 为通配符添加特殊样式
        if chat_pattern == "*":
            pattern_item.setForeground(QColor("#1890ff"))
            pattern_item.setToolTip("匹配所有聊天对象")
        # 为正则表达式添加特殊样式
        elif chat_pattern.startswith("regex:"):
            pattern_item.setForeground(QColor("#722ed1"))
            pattern_item.setToolTip("正则表达式匹配")

        # 为@消息设置添加特殊样式
        if only_at_messages == 1:
            pattern_item.setForeground(QColor("#fa8c16"))  # 橙色

            # 处理多个@名称的情况
            if ',' in at_name:
                at_names = [name.strip() for name in at_name.split(',')]
                at_display = '、'.join(at_names)
                pattern_item.setToolTip(f"仅响应@{at_display}中任意一个的消息")
            else:
                pattern_item.setToolTip(f"仅响应@{at_name}的消息")

        self.rule_table.setItem(row, 3, pattern_item)

        # 平台
        platform_id = rule.get("platform_id", "")
        platform_name = self._get_platform_name(platform_id)
        platform_item = QTableWidgetItem(platform_name)
        self.rule_table.setItem(row, 4, platform_item)

        # 优先级
        priority = rule.get("priority", 0)
        priority_item = QTableWidgetItem(str(priority))
        # 根据优先级设置颜色
        if priority >= 80:
            priority_item.setForeground(QColor("#f5222d"))  # 高优先级 - 红色
            priority_item.setToolTip("高优先级")
        elif priority >= 50:
            priority_item.setForeground(QColor("#fa8c16"))  # 中高优先级 - 橙色
            priority_item.setToolTip("中高优先级")
        elif priority >= 20:
            priority_item.setForeground(QColor("#52c41a"))  # 中优先级 - 绿色
            priority_item.setToolTip("中优先级")
        else:
            priority_item.setForeground(QColor("#1890ff"))  # 低优先级 - 蓝色
            priority_item.setToolTip("低优先级")
        self.rule_table.setItem(row, 5, priority_item)

        # 操作按钮
        # 在单元格内创建一个小部件来容纳按钮
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        button_layout.setContentsMargins(2, 2, 2, 2)
        button_layout.setSpacing(5)

        # 编辑按钮
        edit_btn = QPushButton("编辑")
        edit_btn.setStyleSheet("""
            QPushButton {
                background-color: #1890ff;
                color: white;
                border: none;
                padding: 4px 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #40a9ff;
            }
        """)
        edit_btn.setProperty("rule_id", rule_id)
        edit_btn.clicked.connect(self._edit_rule)
        button_layout.addWidget(edit_btn)

        # 删除按钮
        delete_btn = QPushButton("删除")
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff4d4f;
                color: white;
                border: none;
                padding: 4px 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #ff7875;
            }
        """)
        delete_btn.setProperty("rule_id", rule_id)
        delete_btn.clicked.connect(self._delete_rule)
        button_layout.addWidget(delete_btn)

        button_layout.addStretch()

        self.rule_table.setCellWidget(row, 6, button_widget)

        # 异步更新平台名称
        self._update_platform_name_async(platform_id, row, 4)

    def _update_platform_name_async(self, platform_id: str, row: int, column: int):
        """
        异步更新平台名称

        Args:
            platform_id: 平台ID
            row: 行索引
            column: 列索引
        """
        # 使用asyncSlot装饰器处理异步调用
        self._update_platform_name_task(platform_id, row, column)

    @asyncSlot()
    async def _update_platform_name_task(self, platform_id: str, row: int, column: int):
        """
        异步更新平台名称任务

        Args:
            platform_id: 平台ID
            row: 行索引
            column: 列索引
        """
        try:
            platform = await platform_manager.get_platform(platform_id)
            if platform:
                # 在主线程中更新UI
                QTimer.singleShot(0, lambda: self._update_table_item(row, column, platform.name))
        except Exception as e:
            logger.error(f"获取平台名称失败: {e}")

    def _update_table_item(self, row: int, column: int, text: str):
        """
        更新表格项

        Args:
            row: 行索引
            column: 列索引
            text: 文本
        """
        if row < self.rule_table.rowCount() and column < self.rule_table.columnCount():
            item = self.rule_table.item(row, column)
            if item:
                item.setText(text)

    def _add_rule(self):
        """添加规则"""
        # 在主线程中创建和显示对话框
        def show_dialog():
            try:
                # 导入对话框
                from wxauto_mgt.ui.components.dialogs.rule_dialog import AddEditRuleDialog

                # 创建对话框
                dialog = AddEditRuleDialog(self, current_instance_id=self._current_instance_id)
                if dialog.exec():
                    # 获取规则数据
                    rule_data = dialog.get_rule_data()
                    # 使用QTimer延迟执行异步任务，避免冲突
                    QTimer.singleShot(10, lambda: self._add_rule_async(rule_data))
            except Exception as e:
                logger.error(f"显示添加对话框失败: {e}")
                QMessageBox.warning(self, "错误", f"显示添加对话框失败: {str(e)}")

        # 在主线程中执行
        QTimer.singleShot(0, show_dialog)

    @asyncSlot()
    async def _add_rule_async(self, rule_data: Dict[str, Any]):
        """
        异步添加规则

        Args:
            rule_data: 规则数据
        """
        try:
            # 添加规则
            rule_id = await rule_manager.add_rule(
                rule_data["name"],
                rule_data["instance_id"],
                rule_data["chat_pattern"],
                rule_data["platform_id"],
                rule_data["priority"],
                rule_data["only_at_messages"],
                rule_data["at_name"],
                rule_data["reply_at_sender"]
            )

            if rule_id:
                logger.info(f"添加规则成功: {rule_data['name']} ({rule_id})")

                # 发送规则添加信号
                self.rule_added.emit(rule_id)

                # 刷新规则列表
                await self.refresh_rules()

                # 显示成功消息，并提示需要点击重载配置按钮
                QMessageBox.information(self, "成功",
                                       f"添加规则成功: {rule_data['name']}\n\n请点击工具栏上的\"重载配置\"按钮应用配置，否则将无法继续监听消息。")
            else:
                logger.error(f"添加规则失败: {rule_data['name']}")
                QMessageBox.warning(self, "错误", f"添加规则失败: {rule_data['name']}")

        except RuntimeError as e:
            if "Cannot enter into task" in str(e):
                # 忽略异步任务冲突错误，这不影响实际功能
                logger.debug(f"异步任务冲突（已忽略）: {e}")
                return
            else:
                logger.error(f"添加规则失败: {e}")
                QMessageBox.warning(self, "错误", f"添加规则失败: {str(e)}")
        except Exception as e:
            logger.error(f"添加规则失败: {e}")
            QMessageBox.warning(self, "错误", f"添加规则失败: {str(e)}")

    def _edit_rule(self):
        """编辑规则"""
        # 获取规则ID
        sender = self.sender()
        rule_id = sender.property("rule_id")

        if not rule_id:
            logger.error("编辑规则时缺少规则ID")
            return

        # 使用QTimer延迟执行，避免异步任务冲突
        QTimer.singleShot(10, lambda: self._edit_rule_async(rule_id))

    def _edit_rule_async(self, rule_id: str):
        """
        异步编辑规则

        Args:
            rule_id: 规则ID
        """
        import asyncio
        import threading

        def run_async_task():
            """在新的事件循环中运行异步任务"""
            try:
                # 创建新的事件循环
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                async def edit_rule():
                    # 获取规则数据
                    rule_data = await rule_manager.get_rule(rule_id)
                    if not rule_data:
                        logger.error(f"找不到规则: {rule_id}")
                        QTimer.singleShot(0, lambda: QMessageBox.warning(self, "错误", f"找不到规则: {rule_id}"))
                        return

                    # 发出信号，在主线程中显示对话框
                    self.show_edit_rule_dialog.emit(rule_data)

                # 运行异步任务
                loop.run_until_complete(edit_rule())

            except Exception as e:
                logger.error(f"编辑规则失败: {e}")
                QTimer.singleShot(0, lambda: QMessageBox.warning(self, "错误", f"编辑规则失败: {str(e)}"))
            finally:
                loop.close()

        # 在线程池中执行
        threading.Thread(target=run_async_task, daemon=True).start()

    def _show_edit_rule_dialog_in_main_thread(self, rule_data: dict):
        """在主线程中显示编辑规则对话框"""
        try:
            import threading
            from wxauto_mgt.ui.components.dialogs.rule_dialog import AddEditRuleDialog

            dialog = AddEditRuleDialog(self, rule_data)

            if dialog.exec():
                updated_data = dialog.get_rule_data()
                rule_id = rule_data['rule_id']
                # 在新线程中继续处理更新
                threading.Thread(target=lambda: self._update_rule_data(rule_id, updated_data), daemon=True).start()

        except Exception as e:
            logger.error(f"显示编辑规则对话框失败: {e}")
            import traceback
            logger.error(f"异常堆栈: {traceback.format_exc()}")
            QMessageBox.warning(self, "错误", f"显示编辑规则对话框失败: {str(e)}")

    def _update_rule_data(self, rule_id: str, updated_data: dict):
        """更新规则数据"""
        import asyncio

        try:
            # 创建新的事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def update_rule():
                # 更新规则
                success = await rule_manager.update_rule(
                    rule_id,
                    updated_data["name"],
                    updated_data["instance_id"],
                    updated_data["chat_pattern"],
                    updated_data["platform_id"],
                    updated_data["priority"],
                    updated_data["only_at_messages"],
                    updated_data["at_name"],
                    updated_data["reply_at_sender"]
                )

                if success:
                    logger.info(f"更新规则成功: {updated_data['name']} ({rule_id})")

                    # 发送规则更新信号
                    QTimer.singleShot(0, lambda: self.rule_updated.emit(rule_id))

                    # 刷新规则列表
                    QTimer.singleShot(0, self.refresh_rules)

                    # 显示成功消息，并提示需要点击重载配置按钮
                    QTimer.singleShot(0, lambda: QMessageBox.information(self, "成功",
                                       f"更新规则成功: {updated_data['name']}\n\n请点击工具栏上的\"重载配置\"按钮应用配置，否则将无法继续监听消息。"))
                else:
                    logger.error(f"更新规则失败: {updated_data['name']}")
                    QTimer.singleShot(0, lambda: QMessageBox.warning(self, "错误", f"更新规则失败: {updated_data['name']}"))

            # 运行异步任务
            loop.run_until_complete(update_rule())

        except Exception as e:
            logger.error(f"更新规则数据失败: {e}")
            QTimer.singleShot(0, lambda: QMessageBox.warning(self, "错误", f"更新规则失败: {str(e)}"))
        finally:
            loop.close()



    def _delete_rule(self):
        """删除规则"""
        # 获取规则ID
        sender = self.sender()
        rule_id = sender.property("rule_id")

        if not rule_id:
            logger.error("删除规则时缺少规则ID")
            return

        # 确认对话框
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除规则 {rule_id} 吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # 使用QTimer延迟执行，避免异步任务冲突
            QTimer.singleShot(10, lambda: self._delete_rule_async(rule_id))

    @asyncSlot()
    async def _delete_rule_async(self, rule_id: str):
        """
        异步删除规则

        Args:
            rule_id: 规则ID
        """
        try:
            # 删除规则
            success = await rule_manager.delete_rule(rule_id)

            if success:
                logger.info(f"删除规则成功: {rule_id}")

                # 发送规则删除信号
                self.rule_removed.emit(rule_id)

                # 刷新规则列表
                await self.refresh_rules()

                # 显示成功消息
                QMessageBox.information(self, "成功", f"删除规则成功: {rule_id}")
            else:
                logger.error(f"删除规则失败: {rule_id}")
                QMessageBox.warning(self, "错误", f"删除规则失败: {rule_id}")

        except RuntimeError as e:
            if "Cannot enter into task" in str(e):
                # 忽略异步任务冲突错误，这不影响实际功能
                logger.debug(f"异步任务冲突（已忽略）: {e}")
                return
            else:
                logger.error(f"删除规则失败: {e}")
                QMessageBox.warning(self, "错误", f"删除规则失败: {str(e)}")
        except Exception as e:
            logger.error(f"删除规则失败: {e}")
            QMessageBox.warning(self, "错误", f"删除规则失败: {str(e)}")

    def set_add_button_text(self, text: str):
        """
        设置添加按钮文本

        Args:
            text: 按钮文本
        """
        self.add_btn.setText(text)
