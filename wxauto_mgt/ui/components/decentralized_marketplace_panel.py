"""
去中心化插件市场面板

基于Git仓库的去中心化插件市场UI界面，包括：
- 插件搜索和浏览
- 多源支持和源切换
- 插件详情展示
- 下载和安装功能
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any

from PySide6.QtCore import Qt, Signal, Slot, QTimer, QThread
from PySide6.QtGui import QPixmap, QFont, QIcon
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QListWidget, QListWidgetItem, QTextEdit,
    QScrollArea, QFrame, QProgressBar, QMessageBox, QTabWidget,
    QGroupBox, QGridLayout, QSplitter, QCheckBox, QSpinBox
)

from wxauto_mgt.core.plugin_system.decentralized_marketplace import (
    decentralized_marketplace, MarketplacePlugin
)
from wxauto_mgt.core.plugin_system.plugin_installer import plugin_installer
from wxauto_mgt.utils.logging import get_logger
from qasync import asyncSlot

logger = get_logger()


class PluginCard(QFrame):
    """插件卡片组件"""
    
    install_requested = Signal(str)  # plugin_id
    details_requested = Signal(str)  # plugin_id
    
    def __init__(self, plugin: MarketplacePlugin, parent=None):
        super().__init__(parent)
        self.plugin = plugin
        self._init_ui()
    
    def _init_ui(self):
        """初始化UI"""
        self.setFrameStyle(QFrame.Box)
        self.setStyleSheet("""
            QFrame {
                border: 1px solid #ddd;
                border-radius: 8px;
                background-color: white;
                margin: 4px;
            }
            QFrame:hover {
                border-color: #0078d4;
                background-color: #f8f9fa;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        
        # 标题行
        title_layout = QHBoxLayout()
        
        # 插件名称
        name_label = QLabel(self.plugin.name)
        name_label.setFont(QFont("", 12, QFont.Bold))
        title_layout.addWidget(name_label)
        
        # 标签
        if self.plugin.featured:
            featured_label = QLabel("🌟 精选")
            featured_label.setStyleSheet("color: #ff6b35; font-weight: bold;")
            title_layout.addWidget(featured_label)
        
        if self.plugin.verified:
            verified_label = QLabel("✅ 已验证")
            verified_label.setStyleSheet("color: #28a745; font-weight: bold;")
            title_layout.addWidget(verified_label)
        
        title_layout.addStretch()
        layout.addLayout(title_layout)
        
        # 简短描述
        desc_label = QLabel(self.plugin.short_description)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666; margin: 4px 0;")
        layout.addWidget(desc_label)
        
        # 信息行
        info_layout = QHBoxLayout()
        
        # 作者
        author_label = QLabel(f"👤 {self.plugin.author.name}")
        author_label.setStyleSheet("color: #888; font-size: 11px;")
        info_layout.addWidget(author_label)
        
        # 版本
        version_label = QLabel(f"📦 v{self.plugin.versions.latest}")
        version_label.setStyleSheet("color: #888; font-size: 11px;")
        info_layout.addWidget(version_label)
        
        # 下载量
        if self.plugin.stats:
            downloads_label = QLabel(f"⬇️ {self.plugin.stats.downloads}")
            downloads_label.setStyleSheet("color: #888; font-size: 11px;")
            info_layout.addWidget(downloads_label)
        
        info_layout.addStretch()
        layout.addLayout(info_layout)
        
        # 标签
        if self.plugin.tags:
            tags_text = " ".join([f"#{tag}" for tag in self.plugin.tags[:3]])
            tags_label = QLabel(tags_text)
            tags_label.setStyleSheet("color: #0078d4; font-size: 10px;")
            layout.addWidget(tags_label)
        
        # 按钮行
        button_layout = QHBoxLayout()
        
        details_btn = QPushButton("详情")
        details_btn.clicked.connect(lambda: self.details_requested.emit(self.plugin.plugin_id))
        button_layout.addWidget(details_btn)
        
        install_btn = QPushButton("安装")
        install_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
        """)
        install_btn.clicked.connect(lambda: self.install_requested.emit(self.plugin.plugin_id))
        button_layout.addWidget(install_btn)
        
        layout.addLayout(button_layout)


class DecentralizedMarketplacePanel(QWidget):
    """去中心化插件市场面板"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_plugins: List[MarketplacePlugin] = []
        self._init_ui()
        
        # 启动时刷新市场
        QTimer.singleShot(1000, self.refresh_marketplace)
    
    def _init_ui(self):
        """初始化UI"""
        main_layout = QVBoxLayout(self)
        
        # 创建选项卡
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        # 插件浏览选项卡
        self._create_browse_tab()
        
        # 插件详情选项卡
        self._create_details_tab()
        
        # 设置选项卡
        self._create_settings_tab()
    
    def _create_browse_tab(self):
        """创建插件浏览选项卡"""
        browse_widget = QWidget()
        layout = QVBoxLayout(browse_widget)
        
        # 工具栏
        toolbar_layout = QHBoxLayout()
        
        # 搜索框
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索插件...")
        self.search_input.textChanged.connect(self._on_search_changed)
        toolbar_layout.addWidget(QLabel("搜索:"))
        toolbar_layout.addWidget(self.search_input)
        
        # 分类筛选
        self.category_combo = QComboBox()
        self.category_combo.addItem("所有分类", "")
        self.category_combo.currentTextChanged.connect(self._on_filter_changed)
        toolbar_layout.addWidget(QLabel("分类:"))
        toolbar_layout.addWidget(self.category_combo)
        
        # 筛选选项
        self.featured_checkbox = QCheckBox("仅精选")
        self.featured_checkbox.toggled.connect(self._on_filter_changed)
        toolbar_layout.addWidget(self.featured_checkbox)
        
        self.verified_checkbox = QCheckBox("仅已验证")
        self.verified_checkbox.toggled.connect(self._on_filter_changed)
        toolbar_layout.addWidget(self.verified_checkbox)
        
        # 刷新按钮
        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.clicked.connect(self.refresh_marketplace)
        toolbar_layout.addWidget(refresh_btn)
        
        toolbar_layout.addStretch()
        layout.addLayout(toolbar_layout)
        
        # 状态栏
        status_layout = QHBoxLayout()
        
        self.status_label = QLabel("准备就绪")
        status_layout.addWidget(self.status_label)
        
        self.source_label = QLabel("源: 未知")
        self.source_label.setStyleSheet("color: #666;")
        status_layout.addWidget(self.source_label)
        
        status_layout.addStretch()
        layout.addLayout(status_layout)
        
        # 插件列表
        self.plugins_scroll = QScrollArea()
        self.plugins_scroll.setWidgetResizable(True)
        self.plugins_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.plugins_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        self.plugins_container = QWidget()
        self.plugins_layout = QVBoxLayout(self.plugins_container)
        self.plugins_layout.setAlignment(Qt.AlignTop)
        self.plugins_scroll.setWidget(self.plugins_container)
        
        layout.addWidget(self.plugins_scroll)
        
        self.tab_widget.addTab(browse_widget, "🔍 浏览插件")
    
    def _create_details_tab(self):
        """创建插件详情选项卡"""
        details_widget = QWidget()
        layout = QVBoxLayout(details_widget)
        
        # 返回按钮
        back_btn = QPushButton("← 返回列表")
        back_btn.clicked.connect(lambda: self.tab_widget.setCurrentIndex(0))
        layout.addWidget(back_btn)
        
        # 详情内容
        self.details_scroll = QScrollArea()
        self.details_scroll.setWidgetResizable(True)
        
        self.details_content = QWidget()
        self.details_layout = QVBoxLayout(self.details_content)
        self.details_scroll.setWidget(self.details_content)
        
        layout.addWidget(self.details_scroll)
        
        self.tab_widget.addTab(details_widget, "📋 插件详情")
    
    def _create_settings_tab(self):
        """创建设置选项卡"""
        settings_widget = QWidget()
        layout = QVBoxLayout(settings_widget)
        
        # 源设置
        source_group = QGroupBox("插件源设置")
        source_layout = QVBoxLayout(source_group)
        
        # 当前源显示
        self.current_source_label = QLabel("当前源: 未知")
        source_layout.addWidget(self.current_source_label)
        
        # 源列表
        self.source_combo = QComboBox()
        self.source_combo.currentTextChanged.connect(self._on_source_changed)
        source_layout.addWidget(QLabel("选择插件源:"))
        source_layout.addWidget(self.source_combo)
        
        # 源测试按钮
        test_source_btn = QPushButton("测试连接")
        test_source_btn.clicked.connect(self._test_current_source)
        source_layout.addWidget(test_source_btn)
        
        layout.addWidget(source_group)
        
        # 缓存设置
        cache_group = QGroupBox("缓存设置")
        cache_layout = QVBoxLayout(cache_group)
        
        # 缓存信息
        self.cache_info_label = QLabel("缓存信息: 未知")
        cache_layout.addWidget(self.cache_info_label)
        
        # 清理缓存按钮
        clear_cache_btn = QPushButton("清理缓存")
        clear_cache_btn.clicked.connect(self._clear_cache)
        cache_layout.addWidget(clear_cache_btn)
        
        layout.addWidget(cache_group)
        
        # 统计信息
        stats_group = QGroupBox("市场统计")
        stats_layout = QVBoxLayout(stats_group)
        
        self.stats_label = QLabel("正在加载统计信息...")
        stats_layout.addWidget(self.stats_label)
        
        layout.addWidget(stats_group)
        
        layout.addStretch()
        
        self.tab_widget.addTab(settings_widget, "⚙️ 设置")
    
    @asyncSlot()
    async def refresh_marketplace(self):
        """刷新插件市场"""
        try:
            self.status_label.setText("正在刷新插件市场...")
            
            # 刷新注册表
            success = await decentralized_marketplace.refresh_registry(force=True)
            if not success:
                self.status_label.setText("刷新失败")
                QMessageBox.warning(self, "错误", "无法连接到插件市场，请检查网络连接")
                return
            
            # 更新分类列表
            await self._update_categories()
            
            # 更新源信息
            await self._update_source_info()
            
            # 搜索插件
            await self._search_plugins()
            
            # 更新统计信息
            await self._update_statistics()
            
            self.status_label.setText(f"已加载 {len(self.current_plugins)} 个插件")
            
        except Exception as e:
            logger.error(f"刷新插件市场失败: {e}")
            self.status_label.setText("刷新失败")
            QMessageBox.warning(self, "错误", f"刷新插件市场失败: {str(e)}")
    
    async def _update_categories(self):
        """更新分类列表"""
        try:
            categories = decentralized_marketplace.get_categories()
            
            # 清空现有项目
            self.category_combo.clear()
            self.category_combo.addItem("所有分类", "")
            
            # 添加分类
            for category in categories:
                self.category_combo.addItem(
                    f"{category.get('icon', '')} {category['name']}", 
                    category['id']
                )
            
        except Exception as e:
            logger.error(f"更新分类列表失败: {e}")
    
    async def _update_source_info(self):
        """更新源信息"""
        try:
            current_source = decentralized_marketplace.get_current_source()
            if current_source:
                self.source_label.setText(f"源: {current_source.name}")
                self.current_source_label.setText(f"当前源: {current_source.name}")
            
            # 更新源列表
            sources = decentralized_marketplace.get_available_sources()
            self.source_combo.clear()
            for source in sources:
                self.source_combo.addItem(source.name)
            
            if current_source:
                index = self.source_combo.findText(current_source.name)
                if index >= 0:
                    self.source_combo.setCurrentIndex(index)
            
        except Exception as e:
            logger.error(f"更新源信息失败: {e}")
    
    async def _search_plugins(self):
        """搜索插件"""
        try:
            query = self.search_input.text()
            category = self.category_combo.currentData()
            featured_only = self.featured_checkbox.isChecked()
            verified_only = self.verified_checkbox.isChecked()
            
            self.current_plugins = await decentralized_marketplace.search_plugins(
                query=query,
                category=category,
                featured_only=featured_only,
                verified_only=verified_only
            )
            
            self._update_plugin_list()
            
        except Exception as e:
            logger.error(f"搜索插件失败: {e}")
    
    def _update_plugin_list(self):
        """更新插件列表显示"""
        try:
            # 清空现有插件卡片
            while self.plugins_layout.count():
                child = self.plugins_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
            
            # 添加插件卡片
            for plugin in self.current_plugins:
                card = PluginCard(plugin)
                card.install_requested.connect(self._install_plugin)
                card.details_requested.connect(self._show_plugin_details)
                self.plugins_layout.addWidget(card)
            
            # 添加弹性空间
            self.plugins_layout.addStretch()
            
        except Exception as e:
            logger.error(f"更新插件列表失败: {e}")
    
    @asyncSlot()
    async def _install_plugin(self, plugin_id: str):
        """安装插件"""
        try:
            plugin = await decentralized_marketplace.get_plugin_details(plugin_id)
            if not plugin:
                QMessageBox.warning(self, "错误", f"插件 {plugin_id} 不存在")
                return
            
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
            
            # 显示进度对话框
            progress = QMessageBox(self)
            progress.setWindowTitle("安装插件")
            progress.setText(f"正在下载插件 {plugin.name}...")
            progress.setStandardButtons(QMessageBox.NoButton)
            progress.show()
            
            # 下载插件
            plugin_file = await decentralized_marketplace.download_plugin(plugin_id)
            if not plugin_file:
                progress.close()
                QMessageBox.warning(self, "错误", "下载插件失败")
                return
            
            progress.setText("正在安装插件...")
            
            # 安装插件
            from wxauto_mgt.core.plugin_system.plugin_marketplace import plugin_marketplace
            success, error = await plugin_marketplace.install_plugin_from_file(plugin_file)
            
            progress.close()
            
            if success:
                QMessageBox.information(self, "成功", f"插件 {plugin.name} 安装成功！")
            else:
                QMessageBox.warning(self, "错误", f"安装插件失败: {error}")
            
        except Exception as e:
            logger.error(f"安装插件失败: {e}")
            QMessageBox.warning(self, "错误", f"安装插件失败: {str(e)}")
    
    @asyncSlot()
    async def _show_plugin_details(self, plugin_id: str):
        """显示插件详情"""
        try:
            plugin = await decentralized_marketplace.get_plugin_details(plugin_id)
            if not plugin:
                return
            
            # 清空详情内容
            while self.details_layout.count():
                child = self.details_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
            
            # 插件标题
            title_label = QLabel(plugin.name)
            title_label.setFont(QFont("", 16, QFont.Bold))
            self.details_layout.addWidget(title_label)
            
            # 基本信息
            info_text = f"""
            <b>作者:</b> {plugin.author.name}<br>
            <b>版本:</b> {plugin.versions.latest}<br>
            <b>分类:</b> {plugin.category}<br>
            <b>许可证:</b> {plugin.license}<br>
            <b>状态:</b> {'✅ 已验证' if plugin.verified else '⚠️ 未验证'} 
            {'🌟 精选' if plugin.featured else ''}
            """
            
            info_label = QLabel(info_text)
            info_label.setWordWrap(True)
            self.details_layout.addWidget(info_label)
            
            # 描述
            desc_label = QLabel(f"<b>描述:</b><br>{plugin.description}")
            desc_label.setWordWrap(True)
            self.details_layout.addWidget(desc_label)
            
            # 功能特性
            if plugin.features:
                features_text = "<b>功能特性:</b><br>" + "<br>".join([f"• {feature}" for feature in plugin.features])
                features_label = QLabel(features_text)
                features_label.setWordWrap(True)
                self.details_layout.addWidget(features_label)
            
            # 安装按钮
            install_btn = QPushButton(f"安装 {plugin.name}")
            install_btn.setStyleSheet("""
                QPushButton {
                    background-color: #0078d4;
                    color: white;
                    border: none;
                    padding: 10px 20px;
                    border-radius: 6px;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background-color: #106ebe;
                }
            """)
            install_btn.clicked.connect(lambda: self._install_plugin(plugin_id))
            self.details_layout.addWidget(install_btn)
            
            self.details_layout.addStretch()
            
            # 切换到详情选项卡
            self.tab_widget.setCurrentIndex(1)
            
        except Exception as e:
            logger.error(f"显示插件详情失败: {e}")
    
    @Slot()
    def _on_search_changed(self):
        """搜索内容改变"""
        # 延迟搜索，避免频繁请求
        if hasattr(self, '_search_timer'):
            self._search_timer.stop()
        
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(lambda: asyncio.create_task(self._search_plugins()))
        self._search_timer.start(500)  # 500ms延迟
    
    @Slot()
    def _on_filter_changed(self):
        """筛选条件改变"""
        QTimer.singleShot(0, lambda: asyncio.create_task(self._search_plugins()))
    
    @Slot()
    def _on_source_changed(self, source_name: str):
        """源改变"""
        if source_name:
            decentralized_marketplace.switch_source(source_name)
            # 使用QTimer延迟调用异步方法
            QTimer.singleShot(100, lambda: asyncio.create_task(self.refresh_marketplace()))
    
    @asyncSlot()
    async def _test_current_source(self):
        """测试当前源"""
        try:
            self.status_label.setText("正在测试源连接...")
            success = await decentralized_marketplace.refresh_registry()
            
            if success:
                QMessageBox.information(self, "测试成功", "源连接正常")
                self.status_label.setText("源连接正常")
            else:
                QMessageBox.warning(self, "测试失败", "无法连接到当前源")
                self.status_label.setText("源连接失败")
                
        except Exception as e:
            logger.error(f"测试源连接失败: {e}")
            QMessageBox.warning(self, "测试失败", f"测试源连接失败: {str(e)}")
    
    @Slot()
    def _clear_cache(self):
        """清理缓存"""
        try:
            import shutil
            cache_dir = decentralized_marketplace.cache_dir
            if cache_dir.exists():
                shutil.rmtree(cache_dir)
                cache_dir.mkdir(parents=True, exist_ok=True)
            
            QMessageBox.information(self, "成功", "缓存已清理")
            self.cache_info_label.setText("缓存信息: 已清理")
            
        except Exception as e:
            logger.error(f"清理缓存失败: {e}")
            QMessageBox.warning(self, "错误", f"清理缓存失败: {str(e)}")
    
    async def _update_statistics(self):
        """更新统计信息"""
        try:
            stats = await decentralized_marketplace.get_plugin_statistics()
            
            stats_text = f"""
            总插件数: {stats['total_plugins']}
            精选插件: {stats['featured_plugins']}
            已验证插件: {stats['verified_plugins']}
            总下载量: {stats['total_downloads']}
            最后更新: {stats['last_update'] or '未知'}
            """
            
            self.stats_label.setText(stats_text)
            
        except Exception as e:
            logger.error(f"更新统计信息失败: {e}")
            self.stats_label.setText("统计信息加载失败")
