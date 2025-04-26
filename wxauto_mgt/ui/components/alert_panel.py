"""
告警面板模块

实现告警规则管理和告警历史记录显示界面。
"""

from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QTableWidget, QTableWidgetItem, QLabel, QHeaderView,
    QMessageBox, QDialog, QLineEdit, QComboBox, QSpinBox,
    QFormLayout
)

from wxauto_mgt.core.api_client import instance_manager
from wxauto_mgt.core.config_manager import config_manager
from wxauto_mgt.core.status_monitor import StatusMonitor
from wxauto_mgt.utils.logging import get_logger

# ... existing code ... 