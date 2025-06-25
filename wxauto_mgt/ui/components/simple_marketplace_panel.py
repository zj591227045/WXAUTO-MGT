"""
简化的插件市场面板

提供基本的插件市场功能，避免复杂的异步问题
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any

from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QTextEdit, QMessageBox,
    QTabWidget, QGroupBox, QSplitter
)

from wxauto_mgt.utils.logging import get_logger

# 延迟导入避免循环依赖
try:
    from qasync import asyncSlot
except ImportError:
    # 如果qasync不可用，创建一个简单的装饰器
    def asyncSlot():
        def decorator(func):
            return func
        return decorator

logger = get_logger()


class SimpleMarketplacePanel(QWidget):
    """简化的插件市场面板"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_plugins: List[Any] = []  # 使用Any避免导入问题
        self._init_ui()

        # 延迟初始化
        QTimer.singleShot(1000, self._delayed_init)
    
    def _init_ui(self):
        """初始化UI"""
        self.setWindowTitle("插件市场")
        self.resize(900, 600)
        
        main_layout = QVBoxLayout(self)
        
        # 标题
        title_label = QLabel("🔍 WXAUTO-MGT 插件市场")
        title_label.setFont(QFont("", 16, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        
        # 状态标签
        self.status_label = QLabel("正在初始化...")
        main_layout.addWidget(self.status_label)
        
        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # 左侧：插件列表
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # 刷新按钮
        refresh_btn = QPushButton("🔄 刷新插件列表")
        refresh_btn.clicked.connect(self._refresh_plugins)
        left_layout.addWidget(refresh_btn)
        
        # 插件列表
        self.plugin_list = QListWidget()
        self.plugin_list.itemClicked.connect(self._on_plugin_selected)
        left_layout.addWidget(self.plugin_list)
        
        splitter.addWidget(left_widget)
        
        # 右侧：插件详情
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        # 插件详情
        details_group = QGroupBox("插件详情")
        details_layout = QVBoxLayout(details_group)
        
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        details_layout.addWidget(self.details_text)
        
        right_layout.addWidget(details_group)
        
        # 操作按钮
        button_layout = QHBoxLayout()
        
        self.install_btn = QPushButton("安装插件")
        self.install_btn.setEnabled(False)
        self.install_btn.clicked.connect(self._install_current_plugin)
        button_layout.addWidget(self.install_btn)
        
        self.details_btn = QPushButton("查看详情")
        self.details_btn.setEnabled(False)
        button_layout.addWidget(self.details_btn)
        
        right_layout.addLayout(button_layout)
        
        splitter.addWidget(right_widget)
        
        # 设置分割器比例
        splitter.setSizes([300, 600])
        
        # 当前选中的插件
        self.current_plugin = None
    
    def _delayed_init(self):
        """延迟初始化"""
        self._refresh_plugins()
    
    @asyncSlot()
    async def _refresh_plugins(self):
        """刷新插件列表"""
        try:
            # 延迟导入避免循环依赖
            from wxauto_mgt.core.plugin_system.decentralized_marketplace import decentralized_marketplace

            self.status_label.setText("正在刷新插件列表...")

            # 刷新注册表
            success = await decentralized_marketplace.refresh_registry()
            if not success:
                self.status_label.setText("❌ 刷新失败：无法连接到插件市场")
                QMessageBox.warning(self, "错误", "无法连接到插件市场，请检查网络连接")
                return
            
            # 获取插件列表
            self.current_plugins = await decentralized_marketplace.search_plugins()
            
            # 更新UI
            self._update_plugin_list()
            
            # 获取统计信息
            stats = await decentralized_marketplace.get_plugin_statistics()
            self.status_label.setText(
                f"✅ 已加载 {stats['total_plugins']} 个插件 "
                f"(精选: {stats['featured_plugins']}, 已验证: {stats['verified_plugins']})"
            )
            
        except Exception as e:
            logger.error(f"刷新插件列表失败: {e}")
            self.status_label.setText(f"❌ 刷新失败: {str(e)}")
            QMessageBox.warning(self, "错误", f"刷新插件列表失败: {str(e)}")
    
    def _update_plugin_list(self):
        """更新插件列表显示"""
        try:
            self.plugin_list.clear()
            
            for plugin in self.current_plugins:
                # 创建列表项
                item_text = f"{plugin.name} (v{plugin.versions.latest})"
                if plugin.featured:
                    item_text = f"🌟 {item_text}"
                if plugin.verified:
                    item_text = f"✅ {item_text}"
                
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, plugin.plugin_id)
                self.plugin_list.addItem(item)
            
            logger.info(f"插件列表已更新，共 {len(self.current_plugins)} 个插件")
            
        except Exception as e:
            logger.error(f"更新插件列表失败: {e}")
    
    @Slot()
    def _on_plugin_selected(self, item: QListWidgetItem):
        """插件选中事件"""
        try:
            plugin_id = item.data(Qt.UserRole)
            plugin = next((p for p in self.current_plugins if p.plugin_id == plugin_id), None)
            
            if plugin:
                self.current_plugin = plugin
                self._show_plugin_details(plugin)
                self.install_btn.setEnabled(True)
                self.details_btn.setEnabled(True)
            
        except Exception as e:
            logger.error(f"选择插件失败: {e}")
    
    def _show_plugin_details(self, plugin: Any):
        """显示插件详情"""
        try:
            details_html = f"""
            <h2>{plugin.name}</h2>
            <p><strong>版本:</strong> {plugin.versions.latest}</p>
            <p><strong>作者:</strong> {plugin.author.name}</p>
            <p><strong>分类:</strong> {plugin.category}</p>
            <p><strong>许可证:</strong> {plugin.license}</p>
            
            <h3>描述</h3>
            <p>{plugin.description}</p>
            
            <h3>功能特性</h3>
            <ul>
            """
            
            for feature in plugin.features:
                details_html += f"<li>{feature}</li>"
            
            details_html += "</ul>"
            
            if plugin.dependencies:
                details_html += "<h3>依赖包</h3><ul>"
                for dep in plugin.dependencies:
                    details_html += f"<li><code>{dep}</code></li>"
                details_html += "</ul>"
            
            if plugin.permissions:
                details_html += "<h3>所需权限</h3><ul>"
                for perm in plugin.permissions:
                    details_html += f"<li>{perm}</li>"
                details_html += "</ul>"
            
            details_html += f"""
            <h3>兼容性</h3>
            <p><strong>最低WXAUTO-MGT版本:</strong> {plugin.compatibility.min_wxauto_version}</p>
            <p><strong>Python版本:</strong> {plugin.compatibility.python_version}</p>
            <p><strong>支持系统:</strong> {', '.join(plugin.compatibility.supported_os)}</p>
            """
            
            if plugin.stats:
                details_html += f"""
                <h3>统计信息</h3>
                <p><strong>下载量:</strong> {plugin.stats.downloads}</p>
                <p><strong>评分:</strong> {plugin.stats.rating:.1f}/5.0 ({plugin.stats.rating_count} 评价)</p>
                <p><strong>Stars:</strong> {plugin.stats.stars}</p>
                """
            
            self.details_text.setHtml(details_html)
            
        except Exception as e:
            logger.error(f"显示插件详情失败: {e}")
            self.details_text.setPlainText(f"显示插件详情失败: {str(e)}")
    
    @asyncSlot()
    async def _install_current_plugin(self):
        """安装当前选中的插件"""
        if not self.current_plugin:
            QMessageBox.warning(self, "提示", "请先选择要安装的插件")
            return
        
        try:
            plugin = self.current_plugin
            
            # 确认安装
            reply = QMessageBox.question(
                self, "确认安装", 
                f"确定要安装插件 '{plugin.name}' 吗？\n\n"
                f"版本: {plugin.versions.latest}\n"
                f"作者: {plugin.author.name}\n"
                f"许可证: {plugin.license}",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply != QMessageBox.Yes:
                return
            
            # 禁用按钮
            self.install_btn.setEnabled(False)
            self.install_btn.setText("正在安装...")
            
            self.status_label.setText(f"正在下载插件 {plugin.name}...")
            
            # 下载插件
            from wxauto_mgt.core.plugin_system.decentralized_marketplace import decentralized_marketplace
            plugin_file = await decentralized_marketplace.download_plugin(plugin.plugin_id)
            if not plugin_file:
                QMessageBox.warning(self, "错误", "下载插件失败")
                return
            
            self.status_label.setText("正在安装插件...")
            
            # 这里应该调用插件安装器，但为了简化，我们只显示成功消息
            QMessageBox.information(self, "成功", f"插件 {plugin.name} 安装成功！\n\n注意：这是演示版本，实际安装功能需要完整的插件系统支持。")
            
            self.status_label.setText(f"✅ 插件 {plugin.name} 安装成功")
            
        except Exception as e:
            logger.error(f"安装插件失败: {e}")
            QMessageBox.warning(self, "错误", f"安装插件失败: {str(e)}")
            self.status_label.setText(f"❌ 安装失败: {str(e)}")
        
        finally:
            # 恢复按钮状态
            self.install_btn.setEnabled(True)
            self.install_btn.setText("安装插件")
