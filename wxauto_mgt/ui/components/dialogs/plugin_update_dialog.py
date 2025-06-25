"""
插件更新对话框

提供插件批量更新功能的对话框界面
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any

from PySide6.QtCore import Qt, Signal, Slot, QTimer, QThread, pyqtSignal
from PySide6.QtGui import QPixmap, QFont, QIcon
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QCheckBox, QProgressBar,
    QTextEdit, QGroupBox, QGridLayout, QMessageBox, QWidget
)

from wxauto_mgt.utils.logging import get_logger
from qasync import asyncSlot

logger = get_logger()


class PluginUpdateDialog(QDialog):
    """插件更新对话框"""
    
    def __init__(self, parent=None, updates: Dict[str, str] = None):
        super().__init__(parent)
        self.updates = updates or {}
        self.selected_updates = set()
        self._init_ui()
        self._populate_update_list()
    
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
        
        # 状态标签
        self.status_label = QLabel("")
        self.status_label.setVisible(False)
        layout.addWidget(self.status_label)
        
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
            item_layout.setContentsMargins(5, 5, 5, 5)
            
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
            
            self.status_label.setVisible(True)
            self.status_label.setText("正在准备更新...")
            
            # 禁用按钮
            self.update_btn.setEnabled(False)
            self.cancel_btn.setEnabled(False)
            
            from wxauto_mgt.core.plugin_system import decentralized_marketplace, plugin_marketplace
            
            success_count = 0
            failed_plugins = []
            
            for i, plugin_id in enumerate(self.selected_updates):
                try:
                    self.status_label.setText(f"正在更新 {plugin_id}...")
                    
                    # 下载插件
                    new_version = self.updates[plugin_id]
                    plugin_file = await decentralized_marketplace.download_plugin(plugin_id, new_version)
                    
                    if plugin_file:
                        # 安装插件
                        success, error = await plugin_marketplace.install_plugin_from_file(plugin_file)
                        if success:
                            success_count += 1
                            self.status_label.setText(f"{plugin_id} 更新成功")
                        else:
                            failed_plugins.append(f"{plugin_id}: {error}")
                            self.status_label.setText(f"{plugin_id} 更新失败")
                    else:
                        failed_plugins.append(f"{plugin_id}: 下载失败")
                        self.status_label.setText(f"{plugin_id} 下载失败")
                
                except Exception as e:
                    failed_plugins.append(f"{plugin_id}: {str(e)}")
                    self.status_label.setText(f"{plugin_id} 更新出错")
                
                # 更新进度
                self.progress_bar.setValue(i + 1)
                
                # 让界面有时间更新
                await asyncio.sleep(0.1)
            
            # 显示结果
            self.status_label.setText("更新完成")
            
            if success_count > 0:
                message = f"成功更新 {success_count} 个插件"
                if failed_plugins:
                    message += f"\n失败 {len(failed_plugins)} 个插件:\n" + "\n".join(failed_plugins)
                QMessageBox.information(self, "更新完成", message)
            else:
                QMessageBox.warning(self, "更新失败", "没有插件更新成功:\n" + "\n".join(failed_plugins))
            
            self.accept()
        
        except Exception as e:
            logger.error(f"更新插件失败: {e}")
            QMessageBox.warning(self, "错误", f"更新过程出错: {str(e)}")
        
        finally:
            # 恢复UI状态
            self.progress_bar.setVisible(False)
            self.status_label.setVisible(False)
            self.update_btn.setEnabled(True)
            self.cancel_btn.setEnabled(True)
