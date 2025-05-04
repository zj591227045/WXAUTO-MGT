"""
服务平台配置面板

该模块提供了服务平台管理的UI界面，包括：
- 显示所有服务平台
- 添加、编辑和删除服务平台
- 测试服务平台连接
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
    QDoubleSpinBox, QCheckBox, QTabWidget, QTextEdit
)

from wxauto_mgt.core.service_platform_manager import platform_manager
from wxauto_mgt.utils.logging import get_logger
from qasync import asyncSlot

logger = get_logger()

class ServicePlatformPanel(QWidget):
    """服务平台管理面板"""

    # 定义信号
    platform_added = Signal(str)    # 平台ID
    platform_updated = Signal(str)  # 平台ID
    platform_removed = Signal(str)  # 平台ID
    platform_tested = Signal(str, bool)  # 平台ID, 是否成功

    def __init__(self, parent=None):
        """初始化服务平台管理面板"""
        super().__init__(parent)

        self._init_ui()

        # 初始加载平台列表
        self.refresh_platforms()

    def _init_ui(self):
        """初始化UI"""
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # 标题栏
        title_layout = QHBoxLayout()

        # 标题
        title_label = QLabel("服务平台配置")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        title_layout.addWidget(title_label)

        title_layout.addStretch()

        # 添加平台按钮
        self.add_btn = QPushButton("添加平台")
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
        self.add_btn.clicked.connect(self._add_platform)
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
        self.refresh_btn.clicked.connect(self.refresh_platforms)
        title_layout.addWidget(self.refresh_btn)

        main_layout.addLayout(title_layout)

        # 平台列表表格
        self.platform_table = QTableWidget(0, 5)  # 0行，5列
        self.platform_table.setHorizontalHeaderLabels(["ID", "名称", "类型", "状态", "操作"])
        self.platform_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.platform_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.platform_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.platform_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.platform_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.platform_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.platform_table.setEditTriggers(QTableWidget.NoEditTriggers)

        main_layout.addWidget(self.platform_table)

        # 状态标签
        self.status_label = QLabel("共 0 个服务平台")
        self.status_label.setStyleSheet("color: #666666;")
        main_layout.addWidget(self.status_label)

    @asyncSlot()
    async def refresh_platforms(self):
        """刷新平台列表"""
        try:
            # 清空表格
            self.platform_table.setRowCount(0)

            # 获取所有平台
            platforms = await platform_manager.get_all_platforms()

            # 添加平台到表格
            for platform in platforms:
                self._add_platform_to_table(platform)

            # 更新状态标签
            self.status_label.setText(f"共 {len(platforms)} 个服务平台")

            logger.info(f"刷新平台列表成功，共 {len(platforms)} 个平台")
            return platforms
        except Exception as e:
            logger.error(f"刷新平台列表失败: {e}")
            import traceback
            logger.error(f"异常堆栈: {traceback.format_exc()}")
            QMessageBox.warning(self, "错误", f"刷新平台列表失败: {str(e)}")
            return []

    def _add_platform_to_table(self, platform: Dict[str, Any]):
        """
        将平台添加到表格

        Args:
            platform: 平台数据
        """
        platform_id = platform.get("platform_id", "")
        if not platform_id:
            logger.error(f"平台数据缺少ID字段: {platform}")
            return

        row = self.platform_table.rowCount()
        self.platform_table.insertRow(row)

        # 平台ID
        id_item = QTableWidgetItem(platform_id)
        self.platform_table.setItem(row, 0, id_item)

        # 名称
        name_item = QTableWidgetItem(platform.get("name", ""))
        self.platform_table.setItem(row, 1, name_item)

        # 类型
        type_item = QTableWidgetItem(platform.get("type", "").upper())
        self.platform_table.setItem(row, 2, type_item)

        # 状态
        status = "启用" if platform.get("initialized", False) else "未初始化"
        status_item = QTableWidgetItem(status)
        status_item.setForeground(QColor("#52c41a" if status == "启用" else "#ff4d4f"))
        self.platform_table.setItem(row, 3, status_item)

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
        edit_btn.setProperty("platform_id", platform_id)
        edit_btn.clicked.connect(self._edit_platform)
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
        delete_btn.setProperty("platform_id", platform_id)
        delete_btn.clicked.connect(self._delete_platform)
        button_layout.addWidget(delete_btn)

        # 测试按钮
        test_btn = QPushButton("测试")
        test_btn.setStyleSheet("""
            QPushButton {
                background-color: #52c41a;
                color: white;
                border: none;
                padding: 4px 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #73d13d;
            }
        """)
        test_btn.setProperty("platform_id", platform_id)
        test_btn.clicked.connect(self._test_platform)
        button_layout.addWidget(test_btn)

        button_layout.addStretch()

        self.platform_table.setCellWidget(row, 4, button_widget)

    def _add_platform(self):
        """添加平台"""
        # 导入对话框
        from wxauto_mgt.ui.components.dialogs.platform_dialog import AddEditPlatformDialog

        dialog = AddEditPlatformDialog(self)
        if dialog.exec():
            platform_data = dialog.get_platform_data()

            # 创建异步任务
            asyncio.create_task(self._add_platform_async(platform_data))

    @asyncSlot()
    async def _add_platform_async(self, platform_data: Dict[str, Any]):
        """
        异步添加平台

        Args:
            platform_data: 平台数据
        """
        try:
            import asyncio

            # 创建一个新的任务来执行平台添加操作
            async def add_platform_task():
                try:
                    # 注册平台
                    platform_id = await platform_manager.register_platform(
                        platform_data["type"],
                        platform_data["name"],
                        platform_data["config"]
                    )

                    # 在UI线程中处理结果
                    if platform_id:
                        logger.info(f"添加平台成功: {platform_data['name']} ({platform_id})")

                        # 发送平台添加信号
                        self.platform_added.emit(platform_id)

                        # 刷新平台列表
                        refresh_task = asyncio.create_task(self.refresh_platforms())
                        await refresh_task

                        # 显示成功消息
                        QMessageBox.information(self, "成功", f"添加平台成功: {platform_data['name']}")
                    else:
                        logger.error(f"添加平台失败: {platform_data['name']}")
                        QMessageBox.warning(self, "错误", f"添加平台失败: {platform_data['name']}")
                except Exception as add_error:
                    logger.error(f"添加平台时出错: {add_error}")
                    import traceback
                    logger.error(f"异常堆栈: {traceback.format_exc()}")
                    QMessageBox.warning(self, "错误", f"添加平台时出错: {str(add_error)}")

            # 创建并启动任务
            try:
                # 创建任务但不等待它完成
                asyncio.create_task(add_platform_task())
                # 显示正在处理的消息
                logger.info(f"正在添加平台: {platform_data['name']}")
            except Exception as task_error:
                logger.error(f"创建添加任务时出错: {task_error}")
                QMessageBox.warning(self, "错误", f"创建添加任务时出错: {str(task_error)}")

        except Exception as e:
            logger.error(f"添加平台失败: {e}")
            import traceback
            logger.error(f"异常堆栈: {traceback.format_exc()}")
            QMessageBox.warning(self, "错误", f"添加平台失败: {str(e)}")

    def _edit_platform(self):
        """编辑平台"""
        # 获取平台ID
        sender = self.sender()
        platform_id = sender.property("platform_id")

        if not platform_id:
            logger.error("编辑平台时缺少平台ID")
            return

        # 使用asyncSlot装饰器处理异步调用
        self._edit_platform_async(platform_id)

    @asyncSlot()
    async def _edit_platform_async(self, platform_id: str):
        """
        异步编辑平台

        Args:
            platform_id: 平台ID
        """
        try:
            # 导入对话框
            from wxauto_mgt.ui.components.dialogs.platform_dialog import AddEditPlatformDialog
            import asyncio

            # 在UI线程中获取平台数据，避免与其他异步任务冲突
            platform = None
            try:
                # 使用create_task避免任务嵌套
                get_platform_task = asyncio.create_task(platform_manager.get_platform(platform_id))
                platform = await get_platform_task
            except Exception as e:
                logger.error(f"获取平台数据时出错: {e}")
                QMessageBox.warning(self, "错误", f"获取平台数据时出错: {str(e)}")
                return

            if not platform:
                logger.error(f"找不到平台: {platform_id}")
                QMessageBox.warning(self, "错误", f"找不到平台: {platform_id}")
                return

            # 获取平台数据
            platform_data = platform.to_dict()

            # 创建对话框
            dialog = AddEditPlatformDialog(self, platform_data)
            if dialog.exec():
                updated_data = dialog.get_platform_data()

                # 使用简单方法更新平台配置
                try:
                    # 直接更新数据库中的配置
                    success = await platform_manager.update_platform_simple(
                        platform_id,
                        updated_data["name"],
                        updated_data["config"]
                    )

                    if success:
                        logger.info(f"更新平台配置成功: {updated_data['name']} ({platform_id})")

                        # 发送平台更新信号
                        self.platform_updated.emit(platform_id)

                        # 刷新平台列表
                        await self.refresh_platforms()

                        # 显示成功消息
                        QMessageBox.information(self, "成功", f"更新平台配置成功: {updated_data['name']}")
                    else:
                        logger.error(f"更新平台配置失败: {updated_data['name']}")
                        QMessageBox.warning(self, "错误", f"更新平台配置失败: {updated_data['name']}")
                except Exception as update_error:
                    logger.error(f"更新平台时出错: {update_error}")
                    import traceback
                    logger.error(f"异常堆栈: {traceback.format_exc()}")
                    QMessageBox.warning(self, "错误", f"更新平台时出错: {str(update_error)}")

        except Exception as e:
            logger.error(f"编辑平台失败: {e}")
            import traceback
            logger.error(f"异常堆栈: {traceback.format_exc()}")
            QMessageBox.warning(self, "错误", f"编辑平台失败: {str(e)}")

    def _delete_platform(self):
        """删除平台"""
        # 获取平台ID
        sender = self.sender()
        platform_id = sender.property("platform_id")

        if not platform_id:
            logger.error("删除平台时缺少平台ID")
            return

        # 确认对话框
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除平台 {platform_id} 吗？\n\n注意：删除平台将同时删除与该平台关联的所有规则。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # 使用asyncSlot装饰器处理异步调用
            self._delete_platform_async(platform_id)

    @asyncSlot()
    async def _delete_platform_async(self, platform_id: str):
        """
        异步删除平台

        Args:
            platform_id: 平台ID
        """
        try:
            # 使用简单方法删除平台
            try:
                # 直接从数据库中删除平台
                success = await platform_manager.delete_platform_simple(platform_id)

                if success:
                    logger.info(f"删除平台成功: {platform_id}")

                    # 发送平台删除信号
                    self.platform_removed.emit(platform_id)

                    # 刷新平台列表
                    await self.refresh_platforms()

                    # 显示成功消息
                    QMessageBox.information(self, "成功", f"删除平台成功: {platform_id}")
                else:
                    logger.error(f"删除平台失败: {platform_id}")
                    QMessageBox.warning(self, "错误", f"删除平台失败: {platform_id}")
            except Exception as delete_error:
                logger.error(f"删除平台时出错: {delete_error}")
                import traceback
                logger.error(f"异常堆栈: {traceback.format_exc()}")
                QMessageBox.warning(self, "错误", f"删除平台时出错: {str(delete_error)}")

        except Exception as e:
            logger.error(f"删除平台失败: {e}")
            import traceback
            logger.error(f"异常堆栈: {traceback.format_exc()}")
            QMessageBox.warning(self, "错误", f"删除平台失败: {str(e)}")

    def _test_platform(self):
        """测试平台连接"""
        # 获取平台ID
        sender = self.sender()
        platform_id = sender.property("platform_id")

        if not platform_id:
            logger.error("测试平台时缺少平台ID")
            return

        # 使用asyncSlot装饰器处理异步调用
        self._test_platform_async(platform_id)

    @asyncSlot()
    async def _test_platform_async(self, platform_id: str):
        """
        异步测试平台连接

        Args:
            platform_id: 平台ID
        """
        try:
            import asyncio

            # 创建一个新的任务来执行平台测试操作
            async def test_platform_task():
                try:
                    # 获取平台
                    get_platform_task = asyncio.create_task(platform_manager.get_platform(platform_id))
                    platform = await get_platform_task

                    if not platform:
                        logger.error(f"找不到平台: {platform_id}")
                        QMessageBox.warning(self, "错误", f"找不到平台: {platform_id}")
                        return

                    # 测试连接
                    test_task = asyncio.create_task(platform.test_connection())
                    result = await test_task

                    # 在UI线程中处理结果
                    if not result.get("error"):
                        logger.info(f"测试平台连接成功: {platform_id}")

                        # 发送平台测试信号
                        self.platform_tested.emit(platform_id, True)

                        # 显示成功消息
                        QMessageBox.information(self, "成功", f"测试平台连接成功: {platform.name}")
                    else:
                        error_msg = result.get("error", "未知错误")
                        logger.error(f"测试平台连接失败: {platform_id}, 错误: {error_msg}")

                        # 发送平台测试信号
                        self.platform_tested.emit(platform_id, False)

                        # 显示错误消息
                        QMessageBox.warning(self, "错误", f"测试平台连接失败: {error_msg}")
                except Exception as test_error:
                    logger.error(f"测试平台连接时出错: {test_error}")
                    import traceback
                    logger.error(f"异常堆栈: {traceback.format_exc()}")
                    QMessageBox.warning(self, "错误", f"测试平台连接时出错: {str(test_error)}")

            # 创建并启动任务
            try:
                # 创建任务但不等待它完成
                asyncio.create_task(test_platform_task())
                # 显示正在处理的消息
                logger.info(f"正在测试平台连接: {platform_id}")
            except Exception as task_error:
                logger.error(f"创建测试任务时出错: {task_error}")
                QMessageBox.warning(self, "错误", f"创建测试任务时出错: {str(task_error)}")

        except Exception as e:
            logger.error(f"测试平台连接失败: {e}")
            import traceback
            logger.error(f"异常堆栈: {traceback.format_exc()}")
            QMessageBox.warning(self, "错误", f"测试平台连接失败: {str(e)}")
