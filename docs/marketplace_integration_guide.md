# WXAUTO-MGT 插件市场集成指南

## 概述

本指南详细说明如何在WXAUTO-MGT的Python端和Web端集成去中心化插件市场功能，实现插件的搜索、安装、管理等功能。

## Python端集成

### 1. 主窗口集成

首先在主窗口中添加插件市场入口：

```python
# wxauto_mgt/ui/main_window.py

from PySide6.QtWidgets import QAction, QMenuBar
from wxauto_mgt.ui.components.decentralized_marketplace_panel import DecentralizedMarketplacePanel

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._init_ui()
        self._init_marketplace()

    def _init_ui(self):
        # 现有UI初始化代码...

        # 添加插件市场菜单
        self._create_marketplace_menu()

    def _create_marketplace_menu(self):
        """创建插件市场菜单"""
        # 在菜单栏添加插件市场
        marketplace_menu = self.menuBar().addMenu("插件市场")

        # 浏览插件
        browse_action = QAction("🔍 浏览插件", self)
        browse_action.triggered.connect(self._open_marketplace)
        marketplace_menu.addAction(browse_action)

        # 我的插件
        my_plugins_action = QAction("📦 我的插件", self)
        my_plugins_action.triggered.connect(self._open_plugin_manager)
        marketplace_menu.addAction(my_plugins_action)

        marketplace_menu.addSeparator()

        # 检查更新
        check_updates_action = QAction("🔄 检查更新", self)
        check_updates_action.triggered.connect(self._check_plugin_updates)
        marketplace_menu.addAction(check_updates_action)

        # 市场设置
        settings_action = QAction("⚙️ 市场设置", self)
        settings_action.triggered.connect(self._open_marketplace_settings)
        marketplace_menu.addAction(settings_action)

    def _init_marketplace(self):
        """初始化插件市场"""
        # 创建插件市场面板（但不显示）
        self.marketplace_panel = DecentralizedMarketplacePanel(self)
        self.marketplace_panel.hide()

        # 启动时检查插件更新（可选）
        QTimer.singleShot(5000, self._auto_check_updates)  # 5秒后检查

    @asyncSlot()
    async def _open_marketplace(self):
        """打开插件市场"""
        try:
            # 显示插件市场面板
            if hasattr(self, 'marketplace_panel'):
                self.marketplace_panel.show()
                self.marketplace_panel.raise_()
                self.marketplace_panel.activateWindow()
            else:
                # 创建新的市场窗口
                self.marketplace_panel = DecentralizedMarketplacePanel(self)
                self.marketplace_panel.show()

        except Exception as e:
            logger.error(f"打开插件市场失败: {e}")
            QMessageBox.warning(self, "错误", f"打开插件市场失败: {str(e)}")

    def _open_plugin_manager(self):
        """打开插件管理器"""
        # 切换到现有的插件管理面板
        from wxauto_mgt.ui.components.plugin_management_panel import PluginManagementPanel

        if not hasattr(self, 'plugin_manager_panel'):
            self.plugin_manager_panel = PluginManagementPanel(self)

        self.plugin_manager_panel.show()
        self.plugin_manager_panel.raise_()
        self.plugin_manager_panel.activateWindow()

    @asyncSlot()
    async def _check_plugin_updates(self):
        """检查插件更新"""
        try:
            from wxauto_mgt.core.plugin_system import plugin_manager, decentralized_marketplace

            # 获取已安装插件
            installed_plugins = {}
            for plugin_id, plugin in plugin_manager.get_all_plugins().items():
                if plugin and hasattr(plugin, '_info'):
                    installed_plugins[plugin_id] = plugin._info.version

            if not installed_plugins:
                QMessageBox.information(self, "提示", "没有已安装的插件")
                return

            # 检查更新
            self.statusBar().showMessage("正在检查插件更新...")
            updates = await decentralized_marketplace.check_plugin_updates(installed_plugins)

            if updates:
                # 显示更新对话框
                self._show_update_dialog(updates)
            else:
                QMessageBox.information(self, "更新检查", "所有插件都是最新版本")

            self.statusBar().clearMessage()

        except Exception as e:
            logger.error(f"检查插件更新失败: {e}")
            QMessageBox.warning(self, "错误", f"检查插件更新失败: {str(e)}")
            self.statusBar().clearMessage()

    def _show_update_dialog(self, updates: Dict[str, str]):
        """显示更新对话框"""
        from wxauto_mgt.ui.components.dialogs.plugin_update_dialog import PluginUpdateDialog

        dialog = PluginUpdateDialog(self, updates)
        dialog.exec()

    @asyncSlot()
    async def _auto_check_updates(self):
        """自动检查更新（静默）"""
        try:
            from wxauto_mgt.core.plugin_system import plugin_manager, decentralized_marketplace

            # 获取已安装插件
            installed_plugins = {}
            for plugin_id, plugin in plugin_manager.get_all_plugins().items():
                if plugin and hasattr(plugin, '_info'):
                    installed_plugins[plugin_id] = plugin._info.version

            if not installed_plugins:
                return

            # 静默检查更新
            updates = await decentralized_marketplace.check_plugin_updates(installed_plugins)

            if updates:
                # 在状态栏显示更新提示
                self.statusBar().showMessage(f"发现 {len(updates)} 个插件更新", 10000)

                # 可选：显示系统通知
                self._show_update_notification(len(updates))

        except Exception as e:
            logger.debug(f"自动检查更新失败: {e}")  # 静默失败

    def _show_update_notification(self, count: int):
        """显示更新通知"""
        try:
            from PySide6.QtWidgets import QSystemTrayIcon

            if QSystemTrayIcon.isSystemTrayAvailable():
                # 如果有系统托盘，显示通知
                if hasattr(self, 'tray_icon') and self.tray_icon:
                    self.tray_icon.showMessage(
                        "插件更新",
                        f"发现 {count} 个插件更新，点击查看详情",
                        QSystemTrayIcon.Information,
                        5000
                    )
        except Exception as e:
            logger.debug(f"显示更新通知失败: {e}")

    def _open_marketplace_settings(self):
        """打开市场设置"""
        if hasattr(self, 'marketplace_panel'):
            self.marketplace_panel.show()
            self.marketplace_panel.tab_widget.setCurrentIndex(2)  # 切换到设置选项卡
        else:
            self._open_marketplace()
```

### 2. 创建插件更新对话框

```python
# wxauto_mgt/ui/components/dialogs/plugin_update_dialog.py

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QCheckBox, QProgressBar,
    QTextEdit, QGroupBox, QMessageBox
)
from typing import Dict
import asyncio
from qasync import asyncSlot

class PluginUpdateDialog(QDialog):
    """插件更新对话框"""

    def __init__(self, parent=None, updates: Dict[str, str] = None):
        super().__init__(parent)
        self.updates = updates or {}
        self.selected_updates = set()
        self._init_ui()

    def _init_ui(self):
        """初始化UI"""
        self.setWindowTitle("插件更新")
        self.setModal(True)
        self.resize(600, 400)

        layout = QVBoxLayout(self)

        # 标题
        title_label = QLabel(f"发现 {len(self.updates)} 个插件更新")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; margin: 10px;")
        layout.addWidget(title_label)

        # 更新列表
        self.update_list = QListWidget()
        self._populate_update_list()
        layout.addWidget(self.update_list)

        # 全选/取消全选
        select_layout = QHBoxLayout()

        self.select_all_btn = QPushButton("全选")
        self.select_all_btn.clicked.connect(self._select_all)
        select_layout.addWidget(self.select_all_btn)

        self.deselect_all_btn = QPushButton("取消全选")
        self.deselect_all_btn.clicked.connect(self._deselect_all)
        select_layout.addWidget(self.deselect_all_btn)

        select_layout.addStretch()
        layout.addLayout(select_layout)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # 按钮
        button_layout = QHBoxLayout()

        self.update_btn = QPushButton("更新选中插件")
        self.update_btn.clicked.connect(self._update_selected)
        button_layout.addWidget(self.update_btn)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        layout.addLayout(button_layout)

    def _populate_update_list(self):
        """填充更新列表"""
        for plugin_id, new_version in self.updates.items():
            item_widget = QWidget()
            item_layout = QHBoxLayout(item_widget)

            # 复选框
            checkbox = QCheckBox()
            checkbox.setChecked(True)  # 默认选中
            checkbox.toggled.connect(lambda checked, pid=plugin_id: self._on_item_toggled(pid, checked))
            item_layout.addWidget(checkbox)

            # 插件信息
            info_label = QLabel(f"{plugin_id} → v{new_version}")
            info_label.setStyleSheet("font-weight: bold;")
            item_layout.addWidget(info_label)

            item_layout.addStretch()

            # 添加到列表
            list_item = QListWidgetItem()
            list_item.setSizeHint(item_widget.sizeHint())
            self.update_list.addItem(list_item)
            self.update_list.setItemWidget(list_item, item_widget)

            # 默认选中
            self.selected_updates.add(plugin_id)

    def _on_item_toggled(self, plugin_id: str, checked: bool):
        """处理项目选中状态改变"""
        if checked:
            self.selected_updates.add(plugin_id)
        else:
            self.selected_updates.discard(plugin_id)

    def _select_all(self):
        """全选"""
        for i in range(self.update_list.count()):
            item = self.update_list.item(i)
            widget = self.update_list.itemWidget(item)
            checkbox = widget.findChild(QCheckBox)
            if checkbox:
                checkbox.setChecked(True)

    def _deselect_all(self):
        """取消全选"""
        for i in range(self.update_list.count()):
            item = self.update_list.item(i)
            widget = self.update_list.itemWidget(item)
            checkbox = widget.findChild(QCheckBox)
            if checkbox:
                checkbox.setChecked(False)

    @asyncSlot()
    async def _update_selected(self):
        """更新选中的插件"""
        if not self.selected_updates:
            QMessageBox.warning(self, "提示", "请选择要更新的插件")
            return

        try:
            # 显示进度条
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, len(self.selected_updates))
            self.progress_bar.setValue(0)

            # 禁用按钮
            self.update_btn.setEnabled(False)
            self.cancel_btn.setEnabled(False)

            from wxauto_mgt.core.plugin_system import decentralized_marketplace, plugin_marketplace

            success_count = 0
            failed_plugins = []

            for i, plugin_id in enumerate(self.selected_updates):
                try:
                    # 下载插件
                    new_version = self.updates[plugin_id]
                    plugin_file = await decentralized_marketplace.download_plugin(plugin_id, new_version)

                    if plugin_file:
                        # 安装插件
                        success, error = await plugin_marketplace.install_plugin_from_file(plugin_file)
                        if success:
                            success_count += 1
                        else:
                            failed_plugins.append(f"{plugin_id}: {error}")
                    else:
                        failed_plugins.append(f"{plugin_id}: 下载失败")

                except Exception as e:
                    failed_plugins.append(f"{plugin_id}: {str(e)}")

                # 更新进度
                self.progress_bar.setValue(i + 1)

            # 显示结果
            if success_count > 0:
                message = f"成功更新 {success_count} 个插件"
                if failed_plugins:
                    message += f"\n失败 {len(failed_plugins)} 个插件:\n" + "\n".join(failed_plugins)
                QMessageBox.information(self, "更新完成", message)
            else:
                QMessageBox.warning(self, "更新失败", "没有插件更新成功:\n" + "\n".join(failed_plugins))

            self.accept()

        except Exception as e:
            QMessageBox.warning(self, "错误", f"更新过程出错: {str(e)}")

        finally:
            # 恢复UI状态
            self.progress_bar.setVisible(False)
            self.update_btn.setEnabled(True)
            self.cancel_btn.setEnabled(True)
```

### 3. 系统托盘集成

```python
# wxauto_mgt/ui/system_tray.py

from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import QTimer
import asyncio

class SystemTrayManager:
    """系统托盘管理器"""

    def __init__(self, main_window):
        self.main_window = main_window
        self.tray_icon = None
        self._init_tray()

        # 定期检查更新
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._check_updates_background)
        self.update_timer.start(3600000)  # 每小时检查一次

    def _init_tray(self):
        """初始化系统托盘"""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        # 创建托盘图标
        self.tray_icon = QSystemTrayIcon(self.main_window)
        self.tray_icon.setIcon(QIcon("resources/icons/app.png"))

        # 创建托盘菜单
        tray_menu = QMenu()

        # 显示主窗口
        show_action = QAction("显示主窗口", self.main_window)
        show_action.triggered.connect(self.main_window.show)
        tray_menu.addAction(show_action)

        tray_menu.addSeparator()

        # 插件市场
        marketplace_action = QAction("🔍 插件市场", self.main_window)
        marketplace_action.triggered.connect(self.main_window._open_marketplace)
        tray_menu.addAction(marketplace_action)

        # 检查更新
        update_action = QAction("🔄 检查插件更新", self.main_window)
        update_action.triggered.connect(self.main_window._check_plugin_updates)
        tray_menu.addAction(update_action)

        tray_menu.addSeparator()

        # 退出
        quit_action = QAction("退出", self.main_window)
        quit_action.triggered.connect(QApplication.quit)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

        # 双击显示主窗口
        self.tray_icon.activated.connect(self._on_tray_activated)

    def _on_tray_activated(self, reason):
        """托盘图标激活"""
        if reason == QSystemTrayIcon.DoubleClick:
            self.main_window.show()
            self.main_window.raise_()
            self.main_window.activateWindow()

    def _check_updates_background(self):
        """后台检查更新"""
        asyncio.create_task(self.main_window._auto_check_updates())

    def show_message(self, title: str, message: str, icon=QSystemTrayIcon.Information, timeout=5000):
        """显示托盘消息"""
        if self.tray_icon:
            self.tray_icon.showMessage(title, message, icon, timeout)


## Web端集成

### 1. Web API接口

为Web端提供插件市场相关的API接口：

```python
# wxauto_mgt/web/api/marketplace.py

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from wxauto_mgt.core.plugin_system import decentralized_marketplace, plugin_marketplace
from wxauto_mgt.web.auth import get_current_user

router = APIRouter(prefix="/api/marketplace", tags=["marketplace"])


class PluginSearchRequest(BaseModel):
    query: Optional[str] = ""
    category: Optional[str] = ""
    tags: Optional[List[str]] = []
    featured_only: bool = False
    verified_only: bool = False
    page: int = 1
    limit: int = 20


class PluginInstallRequest(BaseModel):
    plugin_id: str
    version: Optional[str] = None
    source_type: str = "primary"


class SourceSwitchRequest(BaseModel):
    source_name: str


@router.get("/plugins")
async def search_plugins(
    query: str = "",
    category: str = "",
    featured_only: bool = False,
    verified_only: bool = False,
    page: int = 1,
    limit: int = 20,
    current_user = Depends(get_current_user)
):
    """搜索插件"""
    try:
        # 刷新市场数据
        await decentralized_marketplace.refresh_registry()

        # 搜索插件
        plugins = await decentralized_marketplace.search_plugins(
            query=query,
            category=category,
            featured_only=featured_only,
            verified_only=verified_only
        )

        # 分页
        start = (page - 1) * limit
        end = start + limit
        paginated_plugins = plugins[start:end]

        # 转换为字典格式
        result = []
        for plugin in paginated_plugins:
            plugin_dict = {
                "plugin_id": plugin.plugin_id,
                "name": plugin.name,
                "short_description": plugin.short_description,
                "description": plugin.description,
                "category": plugin.category,
                "tags": plugin.tags,
                "author": {
                    "name": plugin.author.name,
                    "github": plugin.author.github,
                    "email": plugin.author.email
                },
                "license": plugin.license,
                "homepage": plugin.homepage,
                "versions": {
                    "latest": plugin.versions.latest,
                    "stable": plugin.versions.stable
                },
                "compatibility": {
                    "min_wxauto_version": plugin.compatibility.min_wxauto_version,
                    "python_version": plugin.compatibility.python_version,
                    "supported_os": plugin.compatibility.supported_os
                },
                "features": plugin.features,
                "screenshots": plugin.screenshots,
                "stats": {
                    "downloads": plugin.stats.downloads if plugin.stats else 0,
                    "stars": plugin.stats.stars if plugin.stats else 0,
                    "rating": plugin.stats.rating if plugin.stats else 0.0
                } if plugin.stats else None,
                "verified": plugin.verified,
                "featured": plugin.featured,
                "status": plugin.status,
                "created_at": plugin.created_at,
                "updated_at": plugin.updated_at
            }
            result.append(plugin_dict)

        return {
            "plugins": result,
            "total": len(plugins),
            "page": page,
            "limit": limit,
            "has_more": end < len(plugins)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/plugins/{plugin_id}")
async def get_plugin_details(
    plugin_id: str,
    current_user = Depends(get_current_user)
):
    """获取插件详情"""
    try:
        plugin = await decentralized_marketplace.get_plugin_details(plugin_id)
        if not plugin:
            raise HTTPException(status_code=404, detail="插件不存在")

        # 获取版本列表
        releases = await decentralized_marketplace.get_plugin_releases(plugin_id)

        return {
            "plugin": {
                "plugin_id": plugin.plugin_id,
                "name": plugin.name,
                "description": plugin.description,
                "category": plugin.category,
                "tags": plugin.tags,
                "author": {
                    "name": plugin.author.name,
                    "github": plugin.author.github,
                    "email": plugin.author.email,
                    "website": plugin.author.website
                },
                "license": plugin.license,
                "homepage": plugin.homepage,
                "repository": {
                    "primary": plugin.repository.get("primary").__dict__ if plugin.repository.get("primary") else None,
                    "mirror": plugin.repository.get("mirror").__dict__ if plugin.repository.get("mirror") else None
                },
                "versions": {
                    "latest": plugin.versions.latest,
                    "stable": plugin.versions.stable,
                    "minimum_supported": plugin.versions.minimum_supported
                },
                "compatibility": {
                    "min_wxauto_version": plugin.compatibility.min_wxauto_version,
                    "max_wxauto_version": plugin.compatibility.max_wxauto_version,
                    "python_version": plugin.compatibility.python_version,
                    "supported_os": plugin.compatibility.supported_os
                },
                "dependencies": plugin.dependencies,
                "permissions": plugin.permissions,
                "features": plugin.features,
                "screenshots": plugin.screenshots,
                "demo_video": plugin.demo_video,
                "documentation": plugin.documentation,
                "issue_tracker": plugin.issue_tracker,
                "stats": {
                    "downloads": plugin.stats.downloads,
                    "stars": plugin.stats.stars,
                    "forks": plugin.stats.forks,
                    "rating": plugin.stats.rating,
                    "rating_count": plugin.stats.rating_count
                } if plugin.stats else None,
                "verified": plugin.verified,
                "featured": plugin.featured,
                "status": plugin.status,
                "created_at": plugin.created_at,
                "updated_at": plugin.updated_at,
                "review": {
                    "reviewer": plugin.review.reviewer,
                    "review_date": plugin.review.review_date,
                    "security_score": plugin.review.security_score,
                    "quality_score": plugin.review.quality_score,
                    "comments": plugin.review.comments
                } if plugin.review else None
            },
            "releases": releases
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/plugins/{plugin_id}/install")
async def install_plugin(
    plugin_id: str,
    request: PluginInstallRequest,
    current_user = Depends(get_current_user)
):
    """安装插件"""
    try:
        # 下载插件
        plugin_file = await decentralized_marketplace.download_plugin(
            plugin_id=plugin_id,
            version=request.version,
            source_type=request.source_type
        )

        if not plugin_file:
            raise HTTPException(status_code=400, detail="下载插件失败")

        # 安装插件
        success, error = await plugin_marketplace.install_plugin_from_file(plugin_file)

        if success:
            return {"success": True, "message": f"插件 {plugin_id} 安装成功"}
        else:
            raise HTTPException(status_code=400, detail=f"安装插件失败: {error}")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/plugins/{plugin_id}")
async def uninstall_plugin(
    plugin_id: str,
    current_user = Depends(get_current_user)
):
    """卸载插件"""
    try:
        success, error = await plugin_marketplace.uninstall_plugin(plugin_id)

        if success:
            return {"success": True, "message": f"插件 {plugin_id} 卸载成功"}
        else:
            raise HTTPException(status_code=400, detail=f"卸载插件失败: {error}")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/categories")
async def get_categories(current_user = Depends(get_current_user)):
    """获取插件分类"""
    try:
        await decentralized_marketplace.refresh_registry()
        categories = decentralized_marketplace.get_categories()
        return {"categories": categories}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/featured")
async def get_featured_plugins(current_user = Depends(get_current_user)):
    """获取精选插件"""
    try:
        await decentralized_marketplace.refresh_registry()
        plugins = decentralized_marketplace.get_featured_plugins()

        result = []
        for plugin in plugins:
            plugin_dict = {
                "plugin_id": plugin.plugin_id,
                "name": plugin.name,
                "short_description": plugin.short_description,
                "category": plugin.category,
                "author": plugin.author.name,
                "versions": {"latest": plugin.versions.latest},
                "stats": {
                    "downloads": plugin.stats.downloads if plugin.stats else 0,
                    "rating": plugin.stats.rating if plugin.stats else 0.0
                },
                "screenshots": plugin.screenshots[:1] if plugin.screenshots else []
            }
            result.append(plugin_dict)

        return {"plugins": result}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/updates")
async def check_updates(current_user = Depends(get_current_user)):
    """检查插件更新"""
    try:
        from wxauto_mgt.core.plugin_system import plugin_manager

        # 获取已安装插件
        installed_plugins = {}
        for plugin_id, plugin in plugin_manager.get_all_plugins().items():
            if plugin and hasattr(plugin, '_info'):
                installed_plugins[plugin_id] = plugin._info.version

        # 检查更新
        updates = await decentralized_marketplace.check_plugin_updates(installed_plugins)

        return {"updates": updates}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sources")
async def get_sources(current_user = Depends(get_current_user)):
    """获取插件源列表"""
    try:
        sources = decentralized_marketplace.get_available_sources()
        current_source = decentralized_marketplace.get_current_source()

        result = []
        for source in sources:
            source_dict = {
                "name": source.name,
                "type": source.type,
                "priority": source.priority,
                "enabled": source.enabled,
                "current": current_source and current_source.name == source.name
            }
            result.append(source_dict)

        return {"sources": result}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sources/switch")
async def switch_source(
    request: SourceSwitchRequest,
    current_user = Depends(get_current_user)
):
    """切换插件源"""
    try:
        success = decentralized_marketplace.switch_source(request.source_name)

        if success:
            return {"success": True, "message": f"已切换到源: {request.source_name}"}
        else:
            raise HTTPException(status_code=400, detail="切换源失败")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics")
async def get_statistics(current_user = Depends(get_current_user)):
    """获取市场统计信息"""
    try:
        stats = await decentralized_marketplace.get_plugin_statistics()
        return {"statistics": stats}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### 2. Web前端页面

创建插件市场的前端页面：

```html
<!-- wxauto_mgt/web/templates/marketplace.html -->

<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>插件市场 - WXAUTO-MGT</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.7.2/font/bootstrap-icons.css" rel="stylesheet">
    <style>
        .plugin-card {
            transition: transform 0.2s, box-shadow 0.2s;
            height: 100%;
        }
        .plugin-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }
        .plugin-screenshot {
            width: 100%;
            height: 200px;
            object-fit: cover;
            border-radius: 8px;
        }
        .plugin-tag {
            font-size: 0.75rem;
            padding: 0.25rem 0.5rem;
            margin: 0.125rem;
            background-color: #e9ecef;
            border-radius: 12px;
            display: inline-block;
        }
        .verified-badge {
            color: #28a745;
        }
        .featured-badge {
            color: #ff6b35;
        }
        .rating-stars {
            color: #ffc107;
        }
        .sidebar {
            background-color: #f8f9fa;
            min-height: calc(100vh - 56px);
        }
        .search-section {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 3rem 0;
        }
    </style>
</head>
<body>
    <!-- 导航栏 -->
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
        <div class="container">
            <a class="navbar-brand" href="/">
                <i class="bi bi-robot"></i> WXAUTO-MGT
            </a>
            <div class="navbar-nav ms-auto">
                <a class="nav-link" href="/dashboard">控制台</a>
                <a class="nav-link active" href="/marketplace">插件市场</a>
                <a class="nav-link" href="/plugins">我的插件</a>
            </div>
        </div>
    </nav>

    <!-- 搜索区域 -->
    <section class="search-section">
        <div class="container">
            <div class="row justify-content-center">
                <div class="col-lg-8">
                    <h1 class="text-center mb-4">
                        <i class="bi bi-shop"></i> 插件市场
                    </h1>
                    <p class="text-center mb-4">发现和安装优质插件，扩展WXAUTO-MGT功能</p>

                    <div class="row">
                        <div class="col-md-8">
                            <div class="input-group input-group-lg">
                                <input type="text" class="form-control" id="searchInput"
                                       placeholder="搜索插件...">
                                <button class="btn btn-light" type="button" onclick="searchPlugins()">
                                    <i class="bi bi-search"></i>
                                </button>
                            </div>
                        </div>
                        <div class="col-md-4">
                            <select class="form-select form-select-lg" id="categorySelect" onchange="searchPlugins()">
                                <option value="">所有分类</option>
                            </select>
                        </div>
                    </div>

                    <div class="row mt-3">
                        <div class="col-12 text-center">
                            <div class="form-check form-check-inline">
                                <input class="form-check-input" type="checkbox" id="featuredOnly" onchange="searchPlugins()">
                                <label class="form-check-label" for="featuredOnly">
                                    <i class="bi bi-star-fill"></i> 仅精选
                                </label>
                            </div>
                            <div class="form-check form-check-inline">
                                <input class="form-check-input" type="checkbox" id="verifiedOnly" onchange="searchPlugins()">
                                <label class="form-check-label" for="verifiedOnly">
                                    <i class="bi bi-patch-check-fill"></i> 仅已验证
                                </label>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <!-- 主要内容 -->
    <div class="container-fluid mt-4">
        <div class="row">
            <!-- 侧边栏 -->
            <div class="col-lg-3">
                <div class="sidebar p-3">
                    <!-- 统计信息 -->
                    <div class="card mb-3">
                        <div class="card-header">
                            <h6 class="mb-0"><i class="bi bi-graph-up"></i> 市场统计</h6>
                        </div>
                        <div class="card-body" id="statisticsCard">
                            <div class="text-center">
                                <div class="spinner-border spinner-border-sm" role="status"></div>
                                <small class="d-block mt-2">加载中...</small>
                            </div>
                        </div>
                    </div>

                    <!-- 精选插件 -->
                    <div class="card mb-3">
                        <div class="card-header">
                            <h6 class="mb-0"><i class="bi bi-star-fill text-warning"></i> 精选插件</h6>
                        </div>
                        <div class="card-body" id="featuredPlugins">
                            <div class="text-center">
                                <div class="spinner-border spinner-border-sm" role="status"></div>
                                <small class="d-block mt-2">加载中...</small>
                            </div>
                        </div>
                    </div>

                    <!-- 插件源设置 -->
                    <div class="card">
                        <div class="card-header">
                            <h6 class="mb-0"><i class="bi bi-cloud"></i> 插件源</h6>
                        </div>
                        <div class="card-body" id="sourcesCard">
                            <div class="text-center">
                                <div class="spinner-border spinner-border-sm" role="status"></div>
                                <small class="d-block mt-2">加载中...</small>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- 插件列表 -->
            <div class="col-lg-9">
                <div class="d-flex justify-content-between align-items-center mb-3">
                    <h4 id="resultsTitle">所有插件</h4>
                    <div>
                        <button class="btn btn-outline-primary btn-sm" onclick="checkUpdates()">
                            <i class="bi bi-arrow-clockwise"></i> 检查更新
                        </button>
                        <button class="btn btn-primary btn-sm" onclick="refreshMarketplace()">
                            <i class="bi bi-arrow-clockwise"></i> 刷新
                        </button>
                    </div>
                </div>

                <!-- 插件网格 -->
                <div id="pluginsGrid" class="row">
                    <!-- 加载指示器 -->
                    <div class="col-12 text-center py-5">
                        <div class="spinner-border" role="status"></div>
                        <p class="mt-3">正在加载插件...</p>
                    </div>
                </div>

                <!-- 分页 -->
                <nav aria-label="插件分页" class="mt-4">
                    <ul class="pagination justify-content-center" id="pagination">
                    </ul>
                </nav>
            </div>
        </div>
    </div>

    <!-- 插件详情模态框 -->
    <div class="modal fade" id="pluginModal" tabindex="-1">
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title" id="pluginModalTitle">插件详情</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body" id="pluginModalBody">
                    <!-- 插件详情内容 -->
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">关闭</button>
                    <button type="button" class="btn btn-primary" id="installPluginBtn">安装插件</button>
                </div>
            </div>
        </div>
    </div>

    <!-- Toast 通知 -->
    <div class="toast-container position-fixed bottom-0 end-0 p-3">
        <div id="notificationToast" class="toast" role="alert">
            <div class="toast-header">
                <strong class="me-auto">通知</strong>
                <button type="button" class="btn-close" data-bs-dismiss="toast"></button>
            </div>
            <div class="toast-body" id="toastBody">
                <!-- 通知内容 -->
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script src="/static/js/marketplace.js"></script>
</body>
</html>


### 3. JavaScript前端逻辑

```javascript
// wxauto_mgt/web/static/js/marketplace.js

class MarketplaceManager {
    constructor() {
        this.currentPage = 1;
        this.pageSize = 12;
        this.currentPlugins = [];
        this.categories = [];
        this.init();
    }

    async init() {
        await this.loadCategories();
        await this.loadStatistics();
        await this.loadFeaturedPlugins();
        await this.loadSources();
        await this.searchPlugins();
    }

    async loadCategories() {
        try {
            const response = await fetch('/api/marketplace/categories');
            const data = await response.json();
            this.categories = data.categories;

            const categorySelect = document.getElementById('categorySelect');
            categorySelect.innerHTML = '<option value="">所有分类</option>';

            this.categories.forEach(category => {
                const option = document.createElement('option');
                option.value = category.id;
                option.textContent = `${category.icon} ${category.name}`;
                categorySelect.appendChild(option);
            });
        } catch (error) {
            console.error('加载分类失败:', error);
        }
    }

    async loadStatistics() {
        try {
            const response = await fetch('/api/marketplace/statistics');
            const data = await response.json();
            const stats = data.statistics;

            const statisticsCard = document.getElementById('statisticsCard');
            statisticsCard.innerHTML = `
                <div class="row text-center">
                    <div class="col-6">
                        <h5 class="text-primary">${stats.total_plugins}</h5>
                        <small>总插件数</small>
                    </div>
                    <div class="col-6">
                        <h5 class="text-success">${stats.verified_plugins}</h5>
                        <small>已验证</small>
                    </div>
                    <div class="col-6 mt-2">
                        <h5 class="text-warning">${stats.featured_plugins}</h5>
                        <small>精选插件</small>
                    </div>
                    <div class="col-6 mt-2">
                        <h5 class="text-info">${this.formatNumber(stats.total_downloads)}</h5>
                        <small>总下载量</small>
                    </div>
                </div>
                <hr>
                <small class="text-muted">
                    <i class="bi bi-cloud"></i> ${stats.current_source || '未知源'}
                </small>
            `;
        } catch (error) {
            console.error('加载统计信息失败:', error);
            document.getElementById('statisticsCard').innerHTML =
                '<p class="text-danger">加载失败</p>';
        }
    }

    async loadFeaturedPlugins() {
        try {
            const response = await fetch('/api/marketplace/featured');
            const data = await response.json();
            const plugins = data.plugins;

            const featuredContainer = document.getElementById('featuredPlugins');

            if (plugins.length === 0) {
                featuredContainer.innerHTML = '<p class="text-muted">暂无精选插件</p>';
                return;
            }

            let html = '';
            plugins.slice(0, 5).forEach(plugin => {
                html += `
                    <div class="d-flex align-items-center mb-2 p-2 border rounded cursor-pointer"
                         onclick="showPluginDetails('${plugin.plugin_id}')">
                        <div class="flex-grow-1">
                            <h6 class="mb-1">${plugin.name}</h6>
                            <small class="text-muted">${plugin.author}</small>
                            <div class="d-flex align-items-center mt-1">
                                <span class="badge bg-primary me-1">${plugin.versions.latest}</span>
                                <small class="text-warning">
                                    <i class="bi bi-star-fill"></i> ${plugin.stats.rating.toFixed(1)}
                                </small>
                            </div>
                        </div>
                    </div>
                `;
            });

            featuredContainer.innerHTML = html;
        } catch (error) {
            console.error('加载精选插件失败:', error);
            document.getElementById('featuredPlugins').innerHTML =
                '<p class="text-danger">加载失败</p>';
        }
    }

    async loadSources() {
        try {
            const response = await fetch('/api/marketplace/sources');
            const data = await response.json();
            const sources = data.sources;

            const sourcesCard = document.getElementById('sourcesCard');

            let html = '';
            sources.forEach(source => {
                const isActive = source.current;
                html += `
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="pluginSource"
                               id="source_${source.name}" value="${source.name}"
                               ${isActive ? 'checked' : ''}
                               onchange="switchSource('${source.name}')">
                        <label class="form-check-label" for="source_${source.name}">
                            <small>
                                ${source.name}
                                ${isActive ? '<i class="bi bi-check-circle-fill text-success"></i>' : ''}
                            </small>
                        </label>
                    </div>
                `;
            });

            sourcesCard.innerHTML = html;
        } catch (error) {
            console.error('加载插件源失败:', error);
            document.getElementById('sourcesCard').innerHTML =
                '<p class="text-danger">加载失败</p>';
        }
    }

    async searchPlugins() {
        const query = document.getElementById('searchInput').value;
        const category = document.getElementById('categorySelect').value;
        const featuredOnly = document.getElementById('featuredOnly').checked;
        const verifiedOnly = document.getElementById('verifiedOnly').checked;

        try {
            const params = new URLSearchParams({
                query: query,
                category: category,
                featured_only: featuredOnly,
                verified_only: verifiedOnly,
                page: this.currentPage,
                limit: this.pageSize
            });

            const response = await fetch(`/api/marketplace/plugins?${params}`);
            const data = await response.json();

            this.currentPlugins = data.plugins;
            this.renderPlugins();
            this.renderPagination(data.total, data.page, data.has_more);

            // 更新结果标题
            const resultsTitle = document.getElementById('resultsTitle');
            let title = '所有插件';
            if (query) title = `搜索结果: "${query}"`;
            else if (category) {
                const cat = this.categories.find(c => c.id === category);
                if (cat) title = `${cat.icon} ${cat.name}`;
            }
            if (featuredOnly) title += ' (精选)';
            if (verifiedOnly) title += ' (已验证)';
            resultsTitle.textContent = `${title} (${data.total})`;

        } catch (error) {
            console.error('搜索插件失败:', error);
            this.showError('搜索插件失败');
        }
    }

    renderPlugins() {
        const grid = document.getElementById('pluginsGrid');

        if (this.currentPlugins.length === 0) {
            grid.innerHTML = `
                <div class="col-12 text-center py-5">
                    <i class="bi bi-search display-1 text-muted"></i>
                    <h4 class="mt-3">未找到匹配的插件</h4>
                    <p class="text-muted">尝试调整搜索条件或浏览其他分类</p>
                </div>
            `;
            return;
        }

        let html = '';
        this.currentPlugins.forEach(plugin => {
            const screenshot = plugin.screenshots && plugin.screenshots.length > 0
                ? plugin.screenshots[0]
                : '/static/images/plugin-placeholder.png';

            html += `
                <div class="col-lg-4 col-md-6 mb-4">
                    <div class="card plugin-card h-100">
                        <img src="${screenshot}" class="card-img-top plugin-screenshot"
                             alt="${plugin.name}" onerror="this.src='/static/images/plugin-placeholder.png'">
                        <div class="card-body d-flex flex-column">
                            <div class="d-flex justify-content-between align-items-start mb-2">
                                <h5 class="card-title">${plugin.name}</h5>
                                <div>
                                    ${plugin.featured ? '<i class="bi bi-star-fill featured-badge" title="精选插件"></i>' : ''}
                                    ${plugin.verified ? '<i class="bi bi-patch-check-fill verified-badge" title="已验证"></i>' : ''}
                                </div>
                            </div>

                            <p class="card-text text-muted small">${plugin.short_description}</p>

                            <div class="mb-2">
                                ${plugin.tags.slice(0, 3).map(tag =>
                                    `<span class="plugin-tag">#${tag}</span>`
                                ).join('')}
                            </div>

                            <div class="mt-auto">
                                <div class="d-flex justify-content-between align-items-center mb-2">
                                    <small class="text-muted">
                                        <i class="bi bi-person"></i> ${plugin.author.name}
                                    </small>
                                    <span class="badge bg-secondary">${plugin.versions.latest}</span>
                                </div>

                                <div class="d-flex justify-content-between align-items-center mb-3">
                                    <div class="rating-stars">
                                        ${this.renderStars(plugin.stats ? plugin.stats.rating : 0)}
                                        <small class="text-muted">(${plugin.stats ? plugin.stats.rating.toFixed(1) : '0.0'})</small>
                                    </div>
                                    <small class="text-muted">
                                        <i class="bi bi-download"></i> ${this.formatNumber(plugin.stats ? plugin.stats.downloads : 0)}
                                    </small>
                                </div>

                                <div class="d-grid gap-2 d-md-flex">
                                    <button class="btn btn-outline-primary btn-sm flex-fill"
                                            onclick="showPluginDetails('${plugin.plugin_id}')">
                                        详情
                                    </button>
                                    <button class="btn btn-primary btn-sm flex-fill"
                                            onclick="installPlugin('${plugin.plugin_id}')">
                                        安装
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        });

        grid.innerHTML = html;
    }

    renderPagination(total, currentPage, hasMore) {
        const pagination = document.getElementById('pagination');
        const totalPages = Math.ceil(total / this.pageSize);

        if (totalPages <= 1) {
            pagination.innerHTML = '';
            return;
        }

        let html = '';

        // 上一页
        html += `
            <li class="page-item ${currentPage === 1 ? 'disabled' : ''}">
                <a class="page-link" href="#" onclick="changePage(${currentPage - 1})">上一页</a>
            </li>
        `;

        // 页码
        const startPage = Math.max(1, currentPage - 2);
        const endPage = Math.min(totalPages, currentPage + 2);

        if (startPage > 1) {
            html += '<li class="page-item"><a class="page-link" href="#" onclick="changePage(1)">1</a></li>';
            if (startPage > 2) {
                html += '<li class="page-item disabled"><span class="page-link">...</span></li>';
            }
        }

        for (let i = startPage; i <= endPage; i++) {
            html += `
                <li class="page-item ${i === currentPage ? 'active' : ''}">
                    <a class="page-link" href="#" onclick="changePage(${i})">${i}</a>
                </li>
            `;
        }

        if (endPage < totalPages) {
            if (endPage < totalPages - 1) {
                html += '<li class="page-item disabled"><span class="page-link">...</span></li>';
            }
            html += `<li class="page-item"><a class="page-link" href="#" onclick="changePage(${totalPages})">${totalPages}</a></li>`;
        }

        // 下一页
        html += `
            <li class="page-item ${!hasMore ? 'disabled' : ''}">
                <a class="page-link" href="#" onclick="changePage(${currentPage + 1})">下一页</a>
            </li>
        `;

        pagination.innerHTML = html;
    }

    renderStars(rating) {
        const fullStars = Math.floor(rating);
        const hasHalfStar = rating % 1 >= 0.5;
        const emptyStars = 5 - fullStars - (hasHalfStar ? 1 : 0);

        let html = '';
        for (let i = 0; i < fullStars; i++) {
            html += '<i class="bi bi-star-fill"></i>';
        }
        if (hasHalfStar) {
            html += '<i class="bi bi-star-half"></i>';
        }
        for (let i = 0; i < emptyStars; i++) {
            html += '<i class="bi bi-star"></i>';
        }

        return html;
    }

    formatNumber(num) {
        if (num >= 1000000) {
            return (num / 1000000).toFixed(1) + 'M';
        } else if (num >= 1000) {
            return (num / 1000).toFixed(1) + 'K';
        }
        return num.toString();
    }

    showError(message) {
        this.showToast(message, 'danger');
    }

    showSuccess(message) {
        this.showToast(message, 'success');
    }

    showToast(message, type = 'info') {
        const toastBody = document.getElementById('toastBody');
        const toast = document.getElementById('notificationToast');

        toastBody.innerHTML = `
            <div class="alert alert-${type} mb-0" role="alert">
                ${message}
            </div>
        `;

        const bsToast = new bootstrap.Toast(toast);
        bsToast.show();
    }
}

// 全局实例
let marketplace;

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    marketplace = new MarketplaceManager();

    // 搜索框回车事件
    document.getElementById('searchInput').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            marketplace.currentPage = 1;
            marketplace.searchPlugins();
        }
    });
});

// 全局函数
function searchPlugins() {
    marketplace.currentPage = 1;
    marketplace.searchPlugins();
}

function changePage(page) {
    marketplace.currentPage = page;
    marketplace.searchPlugins();
}

function refreshMarketplace() {
    marketplace.init();
}

async function showPluginDetails(pluginId) {
    try {
        const response = await fetch(`/api/marketplace/plugins/${pluginId}`);
        const data = await response.json();
        const plugin = data.plugin;
        const releases = data.releases;

        // 设置模态框标题
        document.getElementById('pluginModalTitle').textContent = plugin.name;

        // 设置模态框内容
        const modalBody = document.getElementById('pluginModalBody');
        modalBody.innerHTML = `
            <div class="row">
                <div class="col-md-8">
                    <div class="mb-3">
                        <h6>描述</h6>
                        <p>${plugin.description}</p>
                    </div>

                    <div class="mb-3">
                        <h6>功能特性</h6>
                        <ul>
                            ${plugin.features.map(feature => `<li>${feature}</li>`).join('')}
                        </ul>
                    </div>

                    <div class="mb-3">
                        <h6>兼容性</h6>
                        <p>
                            <strong>最低WXAUTO-MGT版本:</strong> ${plugin.compatibility.min_wxauto_version}<br>
                            <strong>Python版本:</strong> ${plugin.compatibility.python_version}<br>
                            <strong>支持系统:</strong> ${plugin.compatibility.supported_os.join(', ')}
                        </p>
                    </div>

                    ${plugin.dependencies.length > 0 ? `
                        <div class="mb-3">
                            <h6>依赖包</h6>
                            <ul>
                                ${plugin.dependencies.map(dep => `<li><code>${dep}</code></li>`).join('')}
                            </ul>
                        </div>
                    ` : ''}
                </div>

                <div class="col-md-4">
                    <div class="card">
                        <div class="card-body">
                            <h6>插件信息</h6>
                            <p class="mb-2"><strong>作者:</strong> ${plugin.author.name}</p>
                            <p class="mb-2"><strong>版本:</strong> ${plugin.versions.latest}</p>
                            <p class="mb-2"><strong>许可证:</strong> ${plugin.license}</p>
                            <p class="mb-2"><strong>分类:</strong> ${plugin.category}</p>

                            ${plugin.stats ? `
                                <hr>
                                <p class="mb-1"><strong>下载量:</strong> ${marketplace.formatNumber(plugin.stats.downloads)}</p>
                                <p class="mb-1"><strong>评分:</strong> ${plugin.stats.rating.toFixed(1)}/5.0</p>
                                <p class="mb-1"><strong>Stars:</strong> ${plugin.stats.stars}</p>
                            ` : ''}

                            <hr>
                            <div class="d-grid gap-2">
                                ${plugin.homepage ? `<a href="${plugin.homepage}" target="_blank" class="btn btn-outline-primary btn-sm">项目主页</a>` : ''}
                                ${plugin.documentation ? `<a href="${plugin.documentation}" target="_blank" class="btn btn-outline-info btn-sm">查看文档</a>` : ''}
                                ${plugin.issue_tracker ? `<a href="${plugin.issue_tracker}" target="_blank" class="btn btn-outline-warning btn-sm">问题反馈</a>` : ''}
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            ${plugin.screenshots.length > 0 ? `
                <div class="mt-4">
                    <h6>截图</h6>
                    <div class="row">
                        ${plugin.screenshots.map(screenshot => `
                            <div class="col-md-6 mb-3">
                                <img src="${screenshot}" class="img-fluid rounded" alt="插件截图">
                            </div>
                        `).join('')}
                    </div>
                </div>
            ` : ''}
        `;

        // 设置安装按钮
        const installBtn = document.getElementById('installPluginBtn');
        installBtn.onclick = () => installPlugin(pluginId);

        // 显示模态框
        const modal = new bootstrap.Modal(document.getElementById('pluginModal'));
        modal.show();

    } catch (error) {
        console.error('获取插件详情失败:', error);
        marketplace.showError('获取插件详情失败');
    }
}

async function installPlugin(pluginId) {
    try {
        const response = await fetch(`/api/marketplace/plugins/${pluginId}/install`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                plugin_id: pluginId
            })
        });

        const data = await response.json();

        if (response.ok) {
            marketplace.showSuccess(data.message);
            // 关闭模态框
            const modal = bootstrap.Modal.getInstance(document.getElementById('pluginModal'));
            if (modal) modal.hide();
        } else {
            marketplace.showError(data.detail || '安装失败');
        }

    } catch (error) {
        console.error('安装插件失败:', error);
        marketplace.showError('安装插件失败');
    }
}

async function switchSource(sourceName) {
    try {
        const response = await fetch('/api/marketplace/sources/switch', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                source_name: sourceName
            })
        });

        const data = await response.json();

        if (response.ok) {
            marketplace.showSuccess(data.message);
            // 刷新市场数据
            setTimeout(() => {
                marketplace.init();
            }, 1000);
        } else {
            marketplace.showError(data.detail || '切换源失败');
        }

    } catch (error) {
        console.error('切换源失败:', error);
        marketplace.showError('切换源失败');
    }
}

async function checkUpdates() {
    try {
        const response = await fetch('/api/marketplace/updates');
        const data = await response.json();
        const updates = data.updates;

        if (Object.keys(updates).length === 0) {
            marketplace.showSuccess('所有插件都是最新版本');
        } else {
            const updateList = Object.entries(updates)
                .map(([pluginId, version]) => `${pluginId} → v${version}`)
                .join('<br>');

            marketplace.showToast(`
                发现 ${Object.keys(updates).length} 个插件更新:<br>
                ${updateList}
            `, 'warning');
        }

    } catch (error) {
        console.error('检查更新失败:', error);
        marketplace.showError('检查更新失败');
    }
}
```

## 集成步骤

### Python端集成步骤

1. **修改主窗口**
   ```python
   # 在 wxauto_mgt/ui/main_window.py 中添加市场菜单和功能
   ```

2. **添加系统托盘支持**
   ```python
   # 在 wxauto_mgt/ui/system_tray.py 中集成市场功能
   ```

3. **创建更新对话框**
   ```python
   # 创建 wxauto_mgt/ui/components/dialogs/plugin_update_dialog.py
   ```

### Web端集成步骤

1. **添加API路由**
   ```python
   # 在 wxauto_mgt/web/main.py 中注册市场API
   from wxauto_mgt.web.api.marketplace import router as marketplace_router
   app.include_router(marketplace_router)
   ```

2. **添加前端页面**
   ```html
   <!-- 创建 wxauto_mgt/web/templates/marketplace.html -->
   ```

3. **添加JavaScript逻辑**
   ```javascript
   // 创建 wxauto_mgt/web/static/js/marketplace.js
   ```

4. **添加导航链接**
   ```html
   <!-- 在主导航中添加插件市场链接 -->
   <a href="/marketplace">插件市场</a>
   ```

### 启动时初始化

```python
# wxauto_mgt/main.py

async def initialize_marketplace():
    """初始化插件市场"""
    from wxauto_mgt.core.plugin_system import decentralized_marketplace

    # 刷新插件注册表
    await decentralized_marketplace.refresh_registry()

    logger.info("插件市场初始化完成")

# 在应用启动时调用
if __name__ == "__main__":
    # ... 其他初始化代码

    # 初始化插件市场
    asyncio.create_task(initialize_marketplace())
```

这样就完成了Python端和Web端的插件市场集成，用户可以通过两种方式访问和管理插件！
```
```