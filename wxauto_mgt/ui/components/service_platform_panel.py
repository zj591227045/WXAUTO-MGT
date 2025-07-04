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
    platforms_loaded = Signal(list)  # 平台数据加载完成时发出信号
    show_edit_dialog = Signal(dict)  # 显示编辑对话框信号

    def __init__(self, parent=None):
        """初始化服务平台管理面板"""
        super().__init__(parent)

        self._init_ui()

        # 连接信号
        self.platforms_loaded.connect(self._update_platform_table)
        self.show_edit_dialog.connect(self._show_edit_dialog_in_main_thread)

        # 初始加载平台列表（延迟执行，确保数据库已初始化）
        self.init_timer = QTimer()
        self.init_timer.setSingleShot(True)
        self.init_timer.timeout.connect(self.refresh_platforms)
        self.init_timer.start(2000)  # 延迟2秒执行

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

    def refresh_platforms(self):
        """刷新平台列表"""
        logger.info("开始刷新服务平台列表...")
        import asyncio
        import threading

        def run_async_task():
            """在新的事件循环中运行异步任务"""
            try:
                logger.debug("创建新的事件循环...")
                # 创建新的事件循环
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                async def refresh():
                    logger.debug("开始异步刷新任务...")
                    # 确保数据库管理器已初始化
                    from wxauto_mgt.data.db_manager import db_manager
                    if not hasattr(db_manager, '_initialized') or not db_manager._initialized:
                        logger.debug("初始化数据库管理器...")
                        await db_manager.initialize()

                    # 确保平台管理器已初始化
                    if not hasattr(platform_manager, '_initialized') or not platform_manager._initialized:
                        logger.debug("初始化平台管理器...")
                        await platform_manager.initialize()

                    # 获取所有平台
                    logger.debug("获取所有平台...")
                    platforms = await platform_manager.get_all_platforms()
                    logger.info(f"获取到 {len(platforms)} 个平台")

                    # 发出信号，在主线程中更新UI
                    logger.debug("发出platforms_loaded信号...")
                    self.platforms_loaded.emit(platforms)

                # 运行异步任务
                loop.run_until_complete(refresh())
                logger.debug("异步刷新任务完成")

            except Exception as e:
                logger.error(f"刷新平台列表失败: {e}")
                import traceback
                logger.error(f"异常堆栈: {traceback.format_exc()}")
                QTimer.singleShot(0, lambda: QMessageBox.warning(self, "错误", f"刷新平台列表失败: {str(e)}"))
            finally:
                loop.close()

        # 在线程池中执行
        logger.debug("启动异步刷新线程...")
        threading.Thread(target=run_async_task, daemon=True).start()

    def _update_platform_table(self, platforms):
        """在主线程中更新平台表格"""
        try:
            # 清空表格
            self.platform_table.setRowCount(0)

            # 添加平台到表格
            for platform in platforms:
                self._add_platform_to_table(platform)

            # 更新状态标签
            self.status_label.setText(f"共 {len(platforms)} 个服务平台")

            # 强制刷新UI
            self.platform_table.repaint()
            self.repaint()

            logger.info(f"刷新平台列表成功，共 {len(platforms)} 个平台")
        except Exception as e:
            logger.error(f"更新平台表格失败: {e}")
            import traceback
            logger.error(f"异常堆栈: {traceback.format_exc()}")
            QMessageBox.warning(self, "错误", f"更新平台表格失败: {str(e)}")

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
        name = platform.get("name", "")
        name_item = QTableWidgetItem(name)
        self.platform_table.setItem(row, 1, name_item)

        # 类型
        platform_type = platform.get("type", "").upper()
        type_item = QTableWidgetItem(platform_type)
        self.platform_table.setItem(row, 2, type_item)

        # 状态
        enabled = platform.get("enabled", False)
        initialized = platform.get("initialized", False)

        if not enabled:
            status = "已禁用"
            color = "#d9d9d9"  # 灰色
        elif initialized:
            status = "已初始化"
            color = "#52c41a"  # 绿色
        else:
            status = "未初始化"
            color = "#ff4d4f"  # 红色

        status_item = QTableWidgetItem(status)
        status_item.setForeground(QColor(color))
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

    @Slot()
    def _add_platform(self):
        """添加平台"""
        # 导入对话框
        from wxauto_mgt.ui.components.dialogs.platform_dialog import AddEditPlatformDialog

        dialog = AddEditPlatformDialog(self)
        if dialog.exec():
            platform_data = dialog.get_platform_data()

            # 使用QTimer延迟执行，避免异步任务冲突
            QTimer.singleShot(10, lambda: self._add_platform_async(platform_data))

    def _add_platform_async(self, platform_data: Dict[str, Any]):
        """
        在线程池中异步添加平台

        Args:
            platform_data: 平台数据
        """
        import asyncio
        import threading

        def run_async_task():
            """在新的事件循环中运行异步任务"""
            try:
                # 创建新的事件循环
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                async def add_platform():
                    # 确保数据库管理器已初始化
                    from wxauto_mgt.data.db_manager import db_manager
                    if not hasattr(db_manager, '_initialized') or not db_manager._initialized:
                        await db_manager.initialize()

                    # 显示正在处理的消息
                    logger.info(f"正在添加平台: {platform_data['name']}")

                    # 直接执行平台注册
                    platform_id = await platform_manager.register_platform(
                        platform_data["type"],
                        platform_data["name"],
                        platform_data["config"]
                    )

                    if platform_id:
                        logger.info(f"添加平台成功: {platform_data['name']} (ID: {platform_id})")

                        # 在主线程中更新UI
                        QTimer.singleShot(0, lambda: self._on_platform_added(platform_id, platform_data['name']))
                    else:
                        logger.error(f"添加平台失败: {platform_data['name']}")
                        QTimer.singleShot(0, lambda: QMessageBox.warning(self, "错误", f"添加平台失败: {platform_data['name']}"))

                # 运行异步任务
                loop.run_until_complete(add_platform())

            except Exception as e:
                logger.error(f"添加平台失败: {e}")
                QTimer.singleShot(0, lambda: QMessageBox.warning(self, "错误", f"添加平台失败: {str(e)}"))
            finally:
                loop.close()

        # 在线程池中执行
        threading.Thread(target=run_async_task, daemon=True).start()

    def _on_platform_added(self, platform_id: str, platform_name: str):
        """平台添加成功后的UI更新"""
        # 发出信号
        self.platform_added.emit(platform_id)

        # 延迟刷新平台列表，确保数据库操作已完成
        QTimer.singleShot(500, self.refresh_platforms)

        # 显示成功消息
        QMessageBox.information(self, "成功",
                              f"添加平台成功: {platform_name}\n\n"
                              f"平台ID: {platform_id}\n\n"
                              f"请点击主界面的\"重载配置\"按钮以应用新配置。")

    @Slot()
    def _edit_platform(self):
        """编辑平台"""
        # 获取平台ID
        sender = self.sender()
        platform_id = sender.property("platform_id")

        if not platform_id:
            logger.error("编辑平台时缺少平台ID")
            return

        # 使用QTimer延迟执行，避免异步任务冲突
        QTimer.singleShot(10, lambda: self._edit_platform_async(platform_id))

    def _edit_platform_async(self, platform_id: str):
        """
        在线程池中异步编辑平台

        Args:
            platform_id: 平台ID
        """
        logger.info(f"开始异步编辑平台: {platform_id}")
        import asyncio
        import threading

        def run_async_task():
            """在新的事件循环中运行异步任务"""
            try:
                logger.debug(f"创建新的事件循环用于编辑平台: {platform_id}")
                # 创建新的事件循环
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                async def edit_platform():
                    logger.debug(f"开始编辑平台异步任务: {platform_id}")

                    # 确保数据库管理器已初始化
                    from wxauto_mgt.data.db_manager import db_manager
                    if not hasattr(db_manager, '_initialized') or not db_manager._initialized:
                        logger.debug("初始化数据库管理器...")
                        await db_manager.initialize()

                    # 导入对话框
                    logger.debug("导入平台对话框...")
                    from wxauto_mgt.ui.components.dialogs.platform_dialog import AddEditPlatformDialog

                    # 首先尝试从内存中获取平台
                    logger.debug(f"从平台管理器获取平台: {platform_id}")
                    platform = await platform_manager.get_platform(platform_id)
                    logger.debug(f"获取平台结果: {platform is not None}")

                    if platform:
                        logger.debug("从内存中的平台实例获取数据...")
                        # 从内存中的平台实例获取数据
                        platform_data = {
                            'platform_id': platform.platform_id,
                            'name': platform.name,
                            'type': platform.get_type(),
                            'config': platform.config.copy(),  # 使用原始配置，不是安全配置
                            'initialized': platform._initialized
                        }
                        logger.debug(f"构建的平台数据: {platform_data['name']} ({platform_data['type']})")
                    else:
                        # 如果内存中没有，从数据库获取平台数据
                        from wxauto_mgt.data.db_manager import db_manager
                        import json

                        platform_db_data = await db_manager.fetchone(
                            "SELECT * FROM service_platforms WHERE platform_id = ?",
                            (platform_id,)
                        )

                        if not platform_db_data:
                            logger.error(f"找不到平台: {platform_id}")
                            QTimer.singleShot(0, lambda: QMessageBox.warning(self, "错误", f"找不到平台: {platform_id}"))
                            return

                        # 从数据库数据构建平台数据
                        platform_data = {
                            'platform_id': platform_db_data['platform_id'],
                            'name': platform_db_data['name'],
                            'type': platform_db_data['type'],
                            'config': json.loads(platform_db_data['config']),
                            'initialized': False  # 数据库中的平台默认未初始化
                        }

                    # 发出信号，在主线程中显示对话框
                    logger.debug("发出显示编辑对话框信号...")
                    self.show_edit_dialog.emit(platform_data)

                # 运行异步任务
                loop.run_until_complete(edit_platform())

            except Exception as e:
                logger.error(f"编辑平台失败: {e}")
                QTimer.singleShot(0, lambda: QMessageBox.warning(self, "错误", f"编辑平台失败: {str(e)}"))
            finally:
                loop.close()

        # 在线程池中执行
        threading.Thread(target=run_async_task, daemon=True).start()

    @Slot(dict)
    def _show_edit_dialog_in_main_thread(self, platform_data: dict):
        """在主线程中显示编辑对话框"""
        try:
            import threading
            from wxauto_mgt.ui.components.dialogs.platform_dialog import AddEditPlatformDialog

            dialog = AddEditPlatformDialog(self, platform_data)

            if dialog.exec():
                updated_data = dialog.get_platform_data()
                platform_id = platform_data['platform_id']
                # 在新线程中继续处理更新
                threading.Thread(target=lambda: self._update_platform_data(platform_id, updated_data), daemon=True).start()

        except Exception as e:
            logger.error(f"显示编辑对话框失败: {e}")
            import traceback
            logger.error(f"异常堆栈: {traceback.format_exc()}")
            QMessageBox.warning(self, "错误", f"显示编辑对话框失败: {str(e)}")

    def _update_platform_data(self, platform_id: str, updated_data: dict):
        """更新平台数据"""
        import asyncio

        try:
            # 创建新的事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def update_platform():
                # 确保数据库管理器已初始化
                from wxauto_mgt.data.db_manager import db_manager
                if not hasattr(db_manager, '_initialized') or not db_manager._initialized:
                    await db_manager.initialize()

                # 直接更新数据库中的配置
                success = await platform_manager.update_platform_simple(
                    platform_id,
                    updated_data["name"],
                    updated_data["config"]
                )

                if success:
                    logger.info(f"更新平台配置成功: {updated_data['name']} ({platform_id})")
                    # 在主线程中更新UI
                    QTimer.singleShot(0, lambda: self._on_platform_updated(platform_id, updated_data['name']))
                else:
                    logger.error(f"更新平台配置失败: {updated_data['name']}")
                    QTimer.singleShot(0, lambda: QMessageBox.warning(self, "错误", f"更新平台配置失败: {updated_data['name']}"))

            # 运行异步任务
            loop.run_until_complete(update_platform())

        except Exception as e:
            logger.error(f"更新平台数据失败: {e}")
            QTimer.singleShot(0, lambda: QMessageBox.warning(self, "错误", f"更新平台数据失败: {str(e)}"))
        finally:
            loop.close()

    def _on_platform_updated(self, platform_id: str, platform_name: str):
        """平台更新成功后的UI更新"""
        # 发出信号
        self.platform_updated.emit(platform_id)

        # 延迟刷新平台列表，确保数据库操作已完成
        QTimer.singleShot(500, self.refresh_platforms)

        # 显示成功消息
        QMessageBox.information(self, "成功",
                              f"更新平台配置成功: {platform_name}\n\n"
                              f"请点击主界面的\"重载配置\"按钮以应用新配置。")

    @Slot()
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
            # 使用QTimer延迟执行，避免异步任务冲突
            QTimer.singleShot(10, lambda: self._delete_platform_async(platform_id))

    def _delete_platform_async(self, platform_id: str):
        """
        在线程池中异步删除平台

        Args:
            platform_id: 平台ID
        """
        import asyncio
        import threading

        def run_async_task():
            """在新的事件循环中运行异步任务"""
            try:
                # 创建新的事件循环
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                async def delete_platform():
                    # 确保数据库管理器已初始化
                    from wxauto_mgt.data.db_manager import db_manager
                    if not hasattr(db_manager, '_initialized') or not db_manager._initialized:
                        await db_manager.initialize()

                    # 直接从数据库中删除平台
                    success = await platform_manager.delete_platform_simple(platform_id)

                    if success:
                        logger.info(f"删除平台成功: {platform_id}")
                        # 在主线程中更新UI
                        QTimer.singleShot(0, lambda: self._on_platform_deleted(platform_id))
                    else:
                        logger.error(f"删除平台失败: {platform_id}")
                        QTimer.singleShot(0, lambda: QMessageBox.warning(self, "错误", f"删除平台失败: {platform_id}"))

                # 运行异步任务
                loop.run_until_complete(delete_platform())

            except Exception as e:
                logger.error(f"删除平台失败: {e}")
                QTimer.singleShot(0, lambda: QMessageBox.warning(self, "错误", f"删除平台失败: {str(e)}"))
            finally:
                loop.close()

        # 在线程池中执行
        threading.Thread(target=run_async_task, daemon=True).start()

    def _on_platform_deleted(self, platform_id: str):
        """平台删除成功后的UI更新"""
        # 发出信号
        self.platform_removed.emit(platform_id)

        # 刷新平台列表
        self.refresh_platforms()

        # 显示成功消息
        QMessageBox.information(self, "成功", f"删除平台成功: {platform_id}")

    @Slot()
    def _test_platform(self):
        """测试平台连接"""
        # 获取平台ID
        sender = self.sender()
        platform_id = sender.property("platform_id")

        if not platform_id:
            logger.error("测试平台时缺少平台ID")
            return

        # 使用QTimer延迟执行，避免异步任务冲突
        QTimer.singleShot(10, lambda: self._test_platform_async(platform_id))

    def _test_platform_async(self, platform_id: str):
        """
        在线程池中异步测试平台连接

        Args:
            platform_id: 平台ID
        """
        import asyncio
        import threading

        def run_async_task():
            """在新的事件循环中运行异步任务"""
            try:
                # 创建新的事件循环
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                async def test_platform():
                    # 确保数据库管理器已初始化
                    from wxauto_mgt.data.db_manager import db_manager
                    if not hasattr(db_manager, '_initialized') or not db_manager._initialized:
                        await db_manager.initialize()

                    # 显示正在处理的消息
                    logger.info(f"正在测试平台连接: {platform_id}")

                    # 获取平台
                    platform = await platform_manager.get_platform(platform_id)

                    if not platform:
                        # 如果内存中没有，尝试从数据库获取并创建临时平台实例进行测试
                        from wxauto_mgt.data.db_manager import db_manager
                        from wxauto_mgt.core.service_platform import create_platform
                        import json

                        platform_db_data = await db_manager.fetchone(
                            "SELECT * FROM service_platforms WHERE platform_id = ?",
                            (platform_id,)
                        )

                        if not platform_db_data:
                            logger.error(f"找不到平台: {platform_id}")
                            QTimer.singleShot(0, lambda: QMessageBox.warning(self, "错误", f"找不到平台: {platform_id}"))
                            return

                        # 创建临时平台实例进行测试
                        config = json.loads(platform_db_data['config'])
                        platform = create_platform(
                            platform_db_data['type'],
                            platform_id,
                            platform_db_data['name'],
                            config
                        )

                        if not platform:
                            logger.error(f"创建平台实例失败: {platform_id}")
                            QTimer.singleShot(0, lambda: QMessageBox.warning(self, "错误", f"创建平台实例失败: {platform_id}"))
                            return

                    # 测试连接
                    result = await platform.test_connection()

                    # 在主线程中处理结果
                    if not result.get("error"):
                        logger.info(f"测试平台连接成功: {platform_id}")
                        QTimer.singleShot(0, lambda: self._on_platform_test_success(platform_id, platform.name))
                    else:
                        error_msg = result.get("error", "未知错误")
                        logger.error(f"测试平台连接失败: {platform_id}, 错误: {error_msg}")
                        QTimer.singleShot(0, lambda: self._on_platform_test_failed(platform_id, error_msg))

                # 运行异步任务
                loop.run_until_complete(test_platform())

            except Exception as e:
                logger.error(f"测试平台连接失败: {e}")
                QTimer.singleShot(0, lambda: QMessageBox.warning(self, "错误", f"测试平台连接失败: {str(e)}"))
            finally:
                loop.close()

        # 在线程池中执行
        threading.Thread(target=run_async_task, daemon=True).start()

    def _on_platform_test_success(self, platform_id: str, platform_name: str):
        """平台测试成功后的UI更新"""
        # 发出信号
        self.platform_tested.emit(platform_id, True)

        # 显示成功消息
        QMessageBox.information(self, "成功", f"测试平台连接成功: {platform_name}")

    def _on_platform_test_failed(self, platform_id: str, error_msg: str):
        """平台测试失败后的UI更新"""
        # 发出信号
        self.platform_tested.emit(platform_id, False)

        # 显示错误消息
        QMessageBox.warning(self, "错误", f"测试平台连接失败: {error_msg}")
