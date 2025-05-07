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
import logging
import sys
import traceback
import os
from io import StringIO

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
from wxauto_mgt.utils.logger import setup_logger
# 导入新的日志模块
try:
    from wxauto_mgt.utils.logger_config import get_debug_logger, log_dict, log_exception
except ImportError:
    # 如果新日志模块不可用，使用兼容函数
    def get_debug_logger(name, console=False):
        return logging.getLogger(name)

    def log_dict(logger, data, message="字典数据:", level=logging.DEBUG):
        try:
            json_str = json.dumps(data, ensure_ascii=False, indent=2)
            logger.log(level, "%s\n%s", message, json_str)
        except Exception as e:
            logger.error("无法序列化字典数据: %s", str(e))
            logger.log(level, "%s %s", message, str(data))

    def log_exception(logger, exc_info=None, level=logging.ERROR):
        if exc_info is None:
            exc_info = sys.exc_info()

        if exc_info[0] is not None:
            tb_lines = traceback.format_exception(*exc_info)
            logger.log(level, "异常详情:\n%s", ''.join(tb_lines))
from wxauto_mgt.core.config_manager import config_manager

# 尝试导入配置存储，如果不可用则忽略
try:
    from wxauto_mgt.core.config_store import config_store
except ImportError:
    config_store = None

# 设置日志
logger = setup_logger(__name__)

# 创建调试日志记录器
debug_logger = None
try:
    # 创建日志目录
    # 使用相对路径，避免硬编码
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
    log_dir = os.path.join(project_root, 'data', 'logs')
    os.makedirs(log_dir, exist_ok=True)

    # 配置调试日志记录器
    debug_logger = logging.getLogger('message_panel_debug')
    debug_logger.setLevel(logging.DEBUG)

    # 添加文件处理器
    debug_file = os.path.join(log_dir, 'message_panel_debug.log')
    file_handler = logging.FileHandler(debug_file, mode='w', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)

    # 设置格式
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s:%(funcName)s:%(lineno)d - %(message)s')
    file_handler.setFormatter(formatter)

    # 添加处理器
    debug_logger.addHandler(file_handler)
    debug_logger.propagate = False  # 不向上传播日志

    debug_logger.info("调试日志记录器已初始化")
except Exception as e:
    logger.error(f"初始化调试日志记录器失败: {e}")
    debug_logger = logger

# 创建一个自定义的日志处理器类，用于捕获日志到UI
class QTextEditLogger(logging.Handler):
    def __init__(self, parent, text_widget):
        super().__init__()
        self.text_widget = text_widget
        self.parent = parent
        self.setLevel(logging.DEBUG)  # 设置为DEBUG以捕获所有日志
        self.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        self.log_cache = set()  # 用于去重的缓存
        self.message_timestamps = {}  # 记录最近消息的时间戳，用于防止短时间内重复
        # 记录每种事件类型最后显示的时间，用于进一步去重
        self.event_timestamps = {}
        # 添加关键事件关键词过滤集合
        self.key_events = {
            "轮询": "执行主窗口消息检查",
            "新消息": "获取到新消息",
            "收到新消息": "获取到新消息",
            "收到消息": "获取到新消息",
            "获取到新消息": "获取到新消息",
            "获取消息": "获取到新消息",
            "添加监听对象": "添加监听对象",
            "成功添加监听对象": "添加监听对象",
            "保存未读消息": "保存未读消息",
            "保存消息": "保存未读消息",
            "插入记录成功": "保存未读消息",
            "数据库保存": "保存未读消息",
            "手动移除监听对象": "手动移除监听对象",
            "移除监听对象": "移除监听对象",
            "已超时": "超时移除监听对象",
            "超时移除": "超时移除监听对象",
            "即将移除": "超时移除监听对象"
        }
        # 事件分组的最小间隔时间(秒)
        self.event_grouping_interval = {
            "获取到新消息": 5,   # 获取消息类事件5秒内只显示一条
            "保存未读消息": 3,   # 保存消息类事件3秒内只显示一条
            "添加监听对象": 2,   # 添加对象类事件2秒内只显示一条
            "移除监听对象": 2,   # 移除对象类事件2秒内只显示一条
            "超时移除监听对象": 2 # 超时移除类事件2秒内只显示一条
        }
        # 保存已显示事件类型，确保每类事件只在特定时间内显示一次
        self.shown_event_types = {}  # 改为字典，存储 {事件类型: 最后显示时间}
        # 添加额外的调试信息
        logger.debug("日志处理器初始化完成，关键事件过滤词已设置")

    def emit(self, record):
        # 首先过滤掉DEBUG级别的日志
        if record.levelno == logging.DEBUG:
            return  # 不显示DEBUG级别的日志

        # 获取日志消息
        msg = self.format(record)

        # 只允许显示三类关键信息，过滤掉所有其他日志
        # 1. 监控到新消息（特定格式）
        # 2. 投递消息到平台
        # 3. 发送回复消息成功

        # 检查是否是我们想要显示的三类关键信息之一

        # 检查是否是自动刷新日志（这个需要保留）
        if "自动刷新完成" in msg:
            pass  # 允许显示
        # 检查是否是投递消息日志
        elif "投递消息" in msg and "到平台" in msg:
            pass  # 允许显示
        # 检查是否是发送回复消息日志
        elif "直接调用API发送微信消息到" in msg and "成功" in msg:
            pass  # 允许显示
        # 检查是否是原始发送消息日志
        elif "直接调用API发送消息成功" in msg:
            pass  # 允许显示
        # 检查是否是监控到新消息日志（特定格式）
        elif "获取到新消息: 实例=" in msg and "聊天=" in msg and "发送者=" in msg:
            pass  # 允许显示
        # 检查是否是添加监听对象的日志
        elif "添加监听对象: 实例=" in msg or "成功添加实例" in msg or "成功添加监听对象" in msg:
            # 提取实例ID和聊天对象名称，用于事件分组
            try:
                instance_id = ""
                chat_name = ""

                # 尝试提取实例ID和聊天对象
                if "添加监听对象: 实例=" in msg:
                    # 格式: "添加监听对象: 实例=xxx, 聊天=xxx"
                    parts = msg.split(", ")
                    for part in parts:
                        if "实例=" in part:
                            instance_id = part.split("=")[1]
                        elif "聊天=" in part:
                            chat_name = part.split("=")[1]
                elif "成功添加实例" in msg:
                    # 格式: "成功添加实例 xxx 的监听对象: xxx"
                    import re
                    match = re.search(r'成功添加实例\s+([^\s]+)\s+的监听对象:\s+([^\s]+)', msg)
                    if match:
                        instance_id = match.group(1)
                        chat_name = match.group(2)
                elif "成功添加监听对象" in msg:
                    # 格式: "成功添加监听对象: xxx"
                    chat_name = msg.split("成功添加监听对象:")[1].strip()

                # 如果能提取到聊天对象，使用它作为事件分组的键
                if chat_name:
                    # 使用更简单的键，只基于聊天对象名称，不考虑实例ID
                    # 这样可以更有效地去重，避免不同格式的日志导致去重失败
                    event_key = f"添加监听对象_{chat_name}"
                    current_time = time.time()

                    # 检查是否在最近的事件分组间隔时间内已经显示过该事件
                    if event_key in self.event_timestamps:
                        last_time = self.event_timestamps[event_key]
                        interval = self.event_grouping_interval.get("添加监听对象", 2)
                        if current_time - last_time < interval:
                            return  # 在分组间隔内，不显示

                    # 更新事件时间戳
                    self.event_timestamps[event_key] = current_time
            except Exception as e:
                # 使用print而不是logger，避免递归
                print(f"处理添加监听对象日志分组时出错: {e}")

            pass  # 允许显示
        # 检查是否是移除监听对象的日志
        elif "手动移除监听对象: 实例=" in msg or "超时移除监听对象: 实例=" in msg or "已移除实例" in msg or "成功移除监听对象" in msg or "成功超时移除监听对象" in msg or "成功移除监听对象 " in msg:
            # 提取实例ID和聊天对象名称，用于事件分组
            try:
                instance_id = ""
                chat_name = ""
                is_timeout = "超时" in msg

                # 尝试提取实例ID和聊天对象
                if "移除监听对象: 实例=" in msg:
                    # 格式: "手动移除监听对象: 实例=xxx, 聊天=xxx" 或 "超时移除监听对象: 实例=xxx, 聊天=xxx"
                    parts = msg.split(", ")
                    for part in parts:
                        if "实例=" in part:
                            instance_id = part.split("=")[1]
                        elif "聊天=" in part:
                            chat_name = part.split("=")[1]
                elif "已移除实例" in msg:
                    # 格式: "已移除实例 xxx 的监听对象: xxx"
                    import re
                    match = re.search(r'已移除实例\s+([^\s]+)\s+的监听对象:\s+([^\s]+)', msg)
                    if match:
                        instance_id = match.group(1)
                        chat_name = match.group(2)
                elif "成功移除监听对象:" in msg:
                    # 格式: "成功移除监听对象: xxx"
                    chat_name = msg.split("成功移除监听对象:")[1].strip()
                elif "成功超时移除监听对象:" in msg:
                    # 格式: "成功超时移除监听对象: xxx"
                    chat_name = msg.split("成功超时移除监听对象:")[1].strip()
                elif "成功移除监听对象 " in msg:
                    # 格式: "成功移除监听对象 xxx"
                    chat_name = msg.split("成功移除监听对象 ")[1].strip()

                # 尝试从DEBUG日志中提取聊天对象名称
                if not chat_name and "DEBUG" in msg and "成功移除监听对象" in msg:
                    import re
                    match = re.search(r'成功移除监听对象\s+([^\s]+)', msg)
                    if match:
                        chat_name = match.group(1)

                # 如果能提取到聊天对象，使用它作为事件分组的键
                if chat_name:
                    # 使用更简单的键，只基于聊天对象名称，不考虑实例ID和是否超时
                    # 这样可以更有效地去重，避免不同格式的日志导致去重失败
                    event_key = f"移除监听对象_{chat_name}"
                    current_time = time.time()

                    # 检查是否在最近的事件分组间隔时间内已经显示过该事件
                    if event_key in self.event_timestamps:
                        last_time = self.event_timestamps[event_key]
                        # 使用更长的间隔时间，确保能够有效去重
                        interval = 10  # 10秒内的相同对象移除操作视为重复
                        if current_time - last_time < interval:
                            return  # 在分组间隔内，不显示

                    # 更新事件时间戳
                    self.event_timestamps[event_key] = current_time
                else:
                    # 如果无法提取聊天对象，使用整个消息作为键进行去重
                    # 这是一个额外的保护措施，确保即使无法提取聊天对象也能去重
                    current_time = time.time()
                    # 使用消息的前50个字符作为键，避免过长
                    msg_key = f"移除监听对象_msg_{msg[:50]}"

                    if msg_key in self.event_timestamps:
                        last_time = self.event_timestamps[msg_key]
                        if current_time - last_time < 10:  # 10秒内相同消息视为重复
                            return  # 在分组间隔内，不显示

                    # 更新事件时间戳
                    self.event_timestamps[msg_key] = current_time
            except Exception as e:
                # 使用print而不是logger，避免递归
                print(f"处理移除监听对象日志分组时出错: {e}")

            pass  # 允许显示
        # 检查是否是不符合@规则的消息（特殊标记）- 直接过滤掉，不显示
        elif "[不符合消息转发规则]" in msg:
            return  # 不显示不符合规则的消息
        # 其他所有日志都过滤掉
        else:
            return

        # 检查是否是最近3秒内的重复消息
        current_time = time.time()
        message_key = msg

        if message_key in self.message_timestamps:
            last_time = self.message_timestamps[message_key]
            if current_time - last_time < 3:
                return  # 重复消息，不显示

        # 更新时间戳
        self.message_timestamps[message_key] = current_time

        # 清理过期的时间戳记录（超过30秒）
        expired_keys = [k for k, v in self.message_timestamps.items() if current_time - v > 30]
        for k in expired_keys:
            del self.message_timestamps[k]

        # 清理过期的事件时间戳记录（超过60秒）
        expired_event_keys = [k for k, v in self.event_timestamps.items() if current_time - v > 60]
        for k in expired_event_keys:
            del self.event_timestamps[k]

        # 特殊处理关键信息
        timestamp = datetime.now().strftime('%H:%M:%S')

        # 导入re模块，用于正则表达式匹配
        import re

        # 1. 监控到新消息 - 支持两种格式
        if ("获取到新消息: 实例=" in msg and "聊天=" in msg and "发送者=" in msg) or "监控到来自于会话" in msg:
            try:
                # 提取会话名称和发送人
                parts = msg.split(", ")
                chat_info = ""
                sender_info = ""
                content_info = ""
                instance_id = ""

                # 检查是否包含"不符合消息转发规则"的标记，如果有则特殊处理
                is_not_match_rule = "[不符合消息转发规则]" in msg

                # 检查是否是新格式的日志（直接包含会话和发送人信息）
                if "监控到来自于会话" in msg:
                    # 新格式: "监控到来自于会话"测试test"，发送人是"张杰"的新消息，内容："@客服 今天要去买玉米淀粉" [不符合消息转发规则]"
                    try:
                        # 提取会话名称
                        chat_match = re.search(r'监控到来自于会话"([^"]+)"', msg)
                        if chat_match:
                            chat_info = chat_match.group(1)

                        # 提取发送人
                        sender_match = re.search(r'发送人是"([^"]+)"', msg)
                        if sender_match:
                            sender_info = sender_match.group(1)

                        # 提取内容
                        content_match = re.search(r'内容："([^"]+)"', msg)
                        if content_match:
                            content_info = content_match.group(1)
                    except Exception as e:
                        logger.error(f"解析新格式日志失败: {e}")
                else:
                    # 旧格式: "获取到新消息: 实例=xxx, 聊天=xxx, 发送者=xxx, 内容=xxx"
                    for part in parts:
                        if "聊天=" in part:
                            chat_info = part.split("=")[1]
                        elif "发送者=" in part:
                            sender_info = part.split("=")[1]
                        elif "内容=" in part:
                            content_info = part.split("=")[1]
                        elif "实例=" in part:
                            instance_id = part.split("=")[1]

                if chat_info:
                    # 根据是否符合@规则设置不同的消息格式和颜色
                    if is_not_match_rule:
                        # 不显示不符合规则的消息
                        return
                    else:
                        formatted_msg = f"{timestamp} - INFO - 监控到来自于会话\"{chat_info}\"，发送人是\"{sender_info or '未知'}\"的新消息，内容：\"{content_info or ''}\""
                        color = "green"

                    # 更新UI
                    QMetaObject.invokeMethod(
                        self.text_widget,
                        "append",
                        Qt.QueuedConnection,
                        Q_ARG(str, f"<font color='{color}'>{formatted_msg}</font>")
                    )
                    return
            except Exception as e:
                # 如果解析失败，使用原始消息
                pass

        # 2. 投递消息到平台
        elif "投递消息" in msg and "到平台" in msg:
            try:
                # 提取消息ID和平台名称
                msg_id = msg.split("投递消息")[1].split("到平台")[0].strip()
                platform = msg.split("到平台")[1].strip()

                formatted_msg = f"{timestamp} - INFO - 投递消息 {msg_id} 到平台 {platform}"
                color = "green"

                # 更新UI
                QMetaObject.invokeMethod(
                    self.text_widget,
                    "append",
                    Qt.QueuedConnection,
                    Q_ARG(str, f"<font color='{color}'>{formatted_msg}</font>")
                )
                return
            except Exception:
                # 如果解析失败，使用原始消息
                pass

        # 3. 发送回复消息
        elif "直接调用API发送消息成功" in msg:
            try:
                # 提取聊天对象
                chat_name = msg.split("直接调用API发送消息成功:")[1].strip()

                formatted_msg = f"{timestamp} - INFO - 直接调用API发送微信消息到\"{chat_name}\"成功"
                color = "green"

                # 更新UI
                QMetaObject.invokeMethod(
                    self.text_widget,
                    "append",
                    Qt.QueuedConnection,
                    Q_ARG(str, f"<font color='{color}'>{formatted_msg}</font>")
                )
                return
            except Exception as e:
                # 如果解析失败，使用原始消息
                logger.debug(f"解析发送消息日志失败: {e}, 原始消息: {msg}")
                # 直接显示原始消息
                formatted_msg = f"{timestamp} - INFO - {msg}"
                color = "green"

                # 更新UI
                QMetaObject.invokeMethod(
                    self.text_widget,
                    "append",
                    Qt.QueuedConnection,
                    Q_ARG(str, f"<font color='{color}'>{formatted_msg}</font>")
                )
                return

        # 4. 添加监听对象
        elif "添加监听对象: 实例=" in msg or "成功添加实例" in msg or "成功添加监听对象" in msg:
            try:
                # 提取实例ID和聊天对象
                instance_id = ""
                chat_name = ""

                # 尝试提取实例ID和聊天对象
                if "添加监听对象: 实例=" in msg:
                    # 格式: "添加监听对象: 实例=xxx, 聊天=xxx"
                    parts = msg.split(", ")
                    for part in parts:
                        if "实例=" in part:
                            instance_id = part.split("=")[1]
                        elif "聊天=" in part:
                            chat_name = part.split("=")[1]
                elif "成功添加实例" in msg:
                    # 格式: "成功添加实例 xxx 的监听对象: xxx"
                    match = re.search(r'成功添加实例\s+([^\s]+)\s+的监听对象:\s+([^\s]+)', msg)
                    if match:
                        instance_id = match.group(1)
                        chat_name = match.group(2)
                elif "成功添加监听对象" in msg:
                    # 格式: "成功添加监听对象: xxx"
                    chat_name = msg.split("成功添加监听对象:")[1].strip()

                # 构建格式化消息
                if instance_id and chat_name:
                    formatted_msg = f"{timestamp} - INFO - 成功添加监听对象: 实例={instance_id}, 聊天={chat_name}"
                elif chat_name:
                    formatted_msg = f"{timestamp} - INFO - 成功添加监听对象: {chat_name}"
                else:
                    formatted_msg = f"{timestamp} - INFO - {msg}"

                # 使用橙黄色显示
                color = "#FFA500"  # 橙黄色

                # 更新UI
                QMetaObject.invokeMethod(
                    self.text_widget,
                    "append",
                    Qt.QueuedConnection,
                    Q_ARG(str, f"<font color='{color}'>{formatted_msg}</font>")
                )
                return
            except Exception as e:
                # 如果解析失败，使用原始消息
                logger.debug(f"解析添加监听对象日志失败: {e}, 原始消息: {msg}")
                # 直接显示原始消息，使用橙黄色
                formatted_msg = f"{timestamp} - INFO - {msg}"
                color = "#FFA500"  # 橙黄色

                # 更新UI
                QMetaObject.invokeMethod(
                    self.text_widget,
                    "append",
                    Qt.QueuedConnection,
                    Q_ARG(str, f"<font color='{color}'>{formatted_msg}</font>")
                )
                return

        # 5. 移除监听对象 - 这部分已经在前面的去重逻辑中处理过了，这里只需要格式化显示
        elif "手动移除监听对象: 实例=" in msg or "超时移除监听对象: 实例=" in msg or "已移除实例" in msg or "成功移除监听对象" in msg or "成功超时移除监听对象" in msg or "成功移除监听对象 " in msg:
            try:
                # 提取实例ID和聊天对象
                instance_id = ""
                chat_name = ""
                is_timeout = "超时" in msg

                # 尝试提取实例ID和聊天对象
                if "移除监听对象: 实例=" in msg:
                    # 格式: "手动移除监听对象: 实例=xxx, 聊天=xxx" 或 "超时移除监听对象: 实例=xxx, 聊天=xxx"
                    parts = msg.split(", ")
                    for part in parts:
                        if "实例=" in part:
                            instance_id = part.split("=")[1]
                        elif "聊天=" in part:
                            chat_name = part.split("=")[1]
                elif "已移除实例" in msg:
                    # 格式: "已移除实例 xxx 的监听对象: xxx"
                    match = re.search(r'已移除实例\s+([^\s]+)\s+的监听对象:\s+([^\s]+)', msg)
                    if match:
                        instance_id = match.group(1)
                        chat_name = match.group(2)
                elif "成功移除监听对象:" in msg:
                    # 格式: "成功移除监听对象: xxx"
                    chat_name = msg.split("成功移除监听对象:")[1].strip()
                elif "成功超时移除监听对象:" in msg:
                    # 格式: "成功超时移除监听对象: xxx"
                    chat_name = msg.split("成功超时移除监听对象:")[1].strip()
                elif "成功移除监听对象 " in msg:
                    # 格式: "成功移除监听对象 xxx"
                    chat_name = msg.split("成功移除监听对象 ")[1].strip()

                # 尝试从DEBUG日志中提取聊天对象名称
                if not chat_name and "DEBUG" in msg and "成功移除监听对象" in msg:
                    match = re.search(r'成功移除监听对象\s+([^\s]+)', msg)
                    if match:
                        chat_name = match.group(1)

                # 构建统一格式的消息，不管原始日志格式如何，都使用相同的格式输出
                # 这样可以确保去重逻辑能够正常工作
                if instance_id and chat_name:
                    # 使用统一的格式，不区分手动/超时
                    formatted_msg = f"{timestamp} - INFO - 移除监听对象: 实例={instance_id}, 聊天={chat_name}"
                elif chat_name:
                    # 只有聊天对象名称时的统一格式
                    formatted_msg = f"{timestamp} - INFO - 移除监听对象: 聊天={chat_name}"
                else:
                    # 如果无法提取信息，使用原始消息但去掉DEBUG标记
                    clean_msg = msg
                    if "DEBUG" in clean_msg:
                        clean_msg = clean_msg.replace("DEBUG - ", "")
                    formatted_msg = f"{timestamp} - INFO - {clean_msg}"

                # 使用橙黄色显示
                color = "#FFA500"  # 橙黄色

                # 更新UI
                QMetaObject.invokeMethod(
                    self.text_widget,
                    "append",
                    Qt.QueuedConnection,
                    Q_ARG(str, f"<font color='{color}'>{formatted_msg}</font>")
                )
                return
            except Exception as e:
                # 如果解析失败，使用原始消息但去掉DEBUG标记
                clean_msg = msg
                if "DEBUG" in clean_msg:
                    clean_msg = clean_msg.replace("DEBUG - ", "")
                formatted_msg = f"{timestamp} - INFO - {clean_msg}"
                color = "#FFA500"  # 橙黄色

                # 更新UI
                QMetaObject.invokeMethod(
                    self.text_widget,
                    "append",
                    Qt.QueuedConnection,
                    Q_ARG(str, f"<font color='{color}'>{formatted_msg}</font>")
                )
                return

        # 获取日志颜色
        color = "black"
        if record.levelno >= logging.ERROR:
            color = "red"
        elif record.levelno >= logging.WARNING:
            color = "orange"
        elif record.levelno == logging.INFO:
            color = "green"

        # 更新UI（在主线程中）
        QMetaObject.invokeMethod(
            self.text_widget,
            "append",
            Qt.QueuedConnection,
            Q_ARG(str, f"<font color='{color}'>{msg}</font>")
        )

        # 确保滚动到底部
        QMetaObject.invokeMethod(
            self.text_widget.verticalScrollBar(),
            "setValue",
            Qt.QueuedConnection,
            Q_ARG(int, self.text_widget.verticalScrollBar().maximum())
        )

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

        # 自动刷新日志状态跟踪
        self.last_refresh_log_key = ""  # 上一次刷新日志的关键内容
        self.refresh_count = 1          # 刷新计数器
        self.refresh_log_dict = {}      # 存储不同刷新日志的计数

        # 创建定时器
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self._auto_refresh)
        self.refresh_timer.start(self.poll_interval * 1000)  # 转换为毫秒

        # 倒计时刷新定时器
        self.countdown_timer = QTimer()
        self.countdown_timer.timeout.connect(self._update_countdown)
        # 使用poll_interval设置，单位从秒转换为毫秒
        poll_interval_ms = self.poll_interval * 1000
        self.countdown_timer.start(poll_interval_ms)  # 每 poll_interval 秒更新一次倒计时

        # 日志清理计时器 - 每10分钟清理一次过长日志
        self.log_cleanup_timer = QTimer()
        self.log_cleanup_timer.timeout.connect(self._auto_cleanup_logs)
        self.log_cleanup_timer.start(10 * 60 * 1000)  # 10分钟

        # 初始化实例下拉框
        self._init_instance_filter()

        # 初始化
        self.refresh_listeners()

        # 初始化日志系统
        self._init_logging()

        # 刷新系统状态显示
        QTimer.singleShot(500, self._refresh_system_status)

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

        # 下部分：消息列表和日志
        message_splitter = QSplitter(Qt.Horizontal)

        # 消息列表分组
        message_group = QGroupBox("消息列表")
        message_layout = QVBoxLayout(message_group)

        # 消息表格
        self.message_table = QTableWidget(0, 5)  # 0行，5列（移除了接收者列）
        self.message_table.setHorizontalHeaderLabels(["时间", "发送者", "类型", "状态", "内容"])
        self.message_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.message_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.message_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.message_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.message_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.message_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)  # 内容列自适应宽度
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

        # 右侧：日志窗口
        log_area = QWidget()
        log_layout = QVBoxLayout(log_area)

        # 日志工具栏
        log_toolbar = QHBoxLayout()

        # 清空日志按钮
        self.clear_log_btn = QPushButton("清空日志")
        self.clear_log_btn.clicked.connect(self._clear_log)
        log_toolbar.addWidget(self.clear_log_btn)

        # 刷新状态按钮
        self.refresh_status_btn = QPushButton("刷新状态")
        self.refresh_status_btn.clicked.connect(self._refresh_system_status)
        log_toolbar.addWidget(self.refresh_status_btn)

        log_toolbar.addStretch()
        log_layout.addLayout(log_toolbar)

        # 日志窗口
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)

        message_splitter.addWidget(log_area)

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

            # 更新倒计时定时器
            self.countdown_timer.setInterval(poll_interval * 1000)

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
    async def refresh_listeners(self, force_reload=False, silent=False):
        """刷新监听对象列表

        Args:
            force_reload: 是否强制从数据库重新加载
            silent: 是否静默操作，不输出非关键日志
        """
        try:
            # 如果强制刷新，先清空内存中的数据
            if force_reload:
                # 重新从消息监听器加载数据
                from wxauto_mgt.core.message_listener import message_listener
                # 强制刷新消息监听器中的监听对象
                try:
                    # 清空并强制从数据库重新加载
                    message_listener.listeners = {}
                    await message_listener._load_listeners_from_db()
                    if not silent:
                        logger.debug("已强制重新加载监听对象数据")
                except Exception as e:
                    logger.error(f"强制刷新监听对象失败: {e}")

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

                            # 更新倒计时定时器
                            self.countdown_timer.setInterval(self.poll_interval * 1000)

                        # 读取超时时间设置
                        if 'timeout_minutes' in config and isinstance(config['timeout_minutes'], int) and config['timeout_minutes'] > 0:
                            self.timeout_minutes = config['timeout_minutes']
                            self.timeout_edit.setText(str(self.timeout_minutes))
                            message_listener.timeout_minutes = self.timeout_minutes

                        if not silent:
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
                    remove_btn.clicked.connect(lambda checked, i=instance_id, w=who: asyncio.create_task(self._remove_listener(i, w)))
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
            # 捕获并记录常见连接错误，但不输出详细堆栈，减少日志量
            if "Connection refused" in str(e) or "Not connected" in str(e):
                if not silent:
                    logger.error(f"刷新监听对象列表失败(连接问题): {e}")
            else:
                logger.error(f"刷新监听对象列表失败: {e}")
                if not silent:
                    logger.exception(e)
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
            # 只记录一条日志，确保使用能匹配关键词的日志格式
            logger.info(f"添加监听对象: 实例={instance_id}, 聊天={chat_name}")

            # 在日志窗口中显示添加操作（橙黄色）- 日志处理器会自动去重
            timestamp = datetime.now().strftime('%H:%M:%S')
            formatted_msg = f"{timestamp} - INFO - 添加监听对象: 实例={instance_id}, 聊天={chat_name}"
            self.appendLogMessage(formatted_msg, "orange")

            # 调用消息监听器添加监听对象
            success = await message_listener.add_listener(
                instance_id=instance_id,
                who=chat_name,
                **kwargs
            )

            if success:
                # 不再记录成功日志，避免重复
                # 只显示成功对话框
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
                # 记录失败日志
                logger.warning(f"添加监听对象失败: {chat_name}")

                # 在日志窗口中显示失败信息（橙黄色）
                timestamp = datetime.now().strftime('%H:%M:%S')
                formatted_msg = f"{timestamp} - WARNING - 添加监听对象失败: 实例={instance_id}, 聊天={chat_name}"
                self.appendLogMessage(formatted_msg, "orange")

                QMetaObject.invokeMethod(
                    self,
                    "showWarningMessage",
                    Qt.QueuedConnection,
                    Q_ARG(str, "添加失败"),
                    Q_ARG(str, f"无法添加监听对象: {chat_name}")
                )
        except Exception as e:
            # 记录错误日志
            logger.error(f"异步添加监听对象时出错: {e}")

            # 在日志窗口中显示错误信息（橙黄色）
            timestamp = datetime.now().strftime('%H:%M:%S')
            formatted_msg = f"{timestamp} - ERROR - 添加监听对象出错: 实例={instance_id}, 聊天={chat_name}, 错误={str(e)}"
            self.appendLogMessage(formatted_msg, "orange")

            QMetaObject.invokeMethod(
                self,
                "showErrorMessage",
                Qt.QueuedConnection,
                Q_ARG(str, "添加失败"),
                Q_ARG(str, f"添加监听对象时出错: {str(e)}")
            )

    async def _remove_listener(self, instance_id: str, who: str, show_dialog: bool = True):
        """
        移除监听对象

        Args:
            instance_id: 实例ID
            who: 监听对象
            show_dialog: 是否显示对话框
        """
        try:
            # 如果是超时移除，不需要输出详细日志，由_update_countdown统一记录
            is_timeout_removal = not show_dialog
            timestamp = datetime.now().strftime('%H:%M:%S')

            # 只记录一条日志，避免重复
            if not is_timeout_removal:
                # 记录手动移除日志 - 日志处理器会自动处理并显示在UI中
                logger.info(f"手动移除监听对象: 实例={instance_id}, 聊天={who}")
                # 不再直接调用appendLogMessage，避免重复显示
            else:
                # 记录超时移除日志 - 日志处理器会自动处理并显示在UI中
                logger.info(f"超时移除监听对象: 实例={instance_id}, 聊天={who}")
                # 不再直接调用appendLogMessage，避免重复显示

            # 确保message_listener已经初始化
            from wxauto_mgt.core.message_listener import message_listener

            # 移除监听对象
            success = await message_listener.remove_listener(instance_id, who)

            if success:
                # 不再记录成功日志，避免重复
                # 发送信号
                self.listener_removed.emit(instance_id, who)
                # 强制刷新监听对象列表
                if not is_timeout_removal:
                    await self.refresh_listeners(force_reload=True)
                if show_dialog:
                    QMessageBox.information(self, "移除成功", f"成功移除监听对象: {who}")
            else:
                if not is_timeout_removal:
                    # 记录移除失败日志
                    logger.warning(f"移除监听对象失败: {who}")

                    # 在日志窗口中显示移除失败信息（橙黄色）
                    formatted_msg = f"{timestamp} - WARNING - 移除监听对象失败: 实例={instance_id}, 聊天={who}"
                    self.appendLogMessage(formatted_msg, "orange")

                # 尝试强制刷新
                if not is_timeout_removal:
                    await self.refresh_listeners(force_reload=True)
                if show_dialog:
                    QMessageBox.warning(self, "移除失败", f"无法移除监听对象: {who}")
        except Exception as e:
            # 只在手动移除时记录详细错误
            if not show_dialog:
                # 记录超时移除错误日志 - 日志处理器会自动处理并显示在UI中
                logger.error(f"超时移除监听对象时出错: 实例={instance_id}, 聊天={who}, 错误={str(e)}")
                # 不再直接调用appendLogMessage，避免重复显示
            else:
                # 记录手动移除错误日志 - 日志处理器会自动处理并显示在UI中
                logger.error(f"手动移除监听对象时出错: 实例={instance_id}, 聊天={who}, 错误={str(e)}")
                logger.exception(e)  # 只在手动移除时记录完整的错误堆栈
                # 不再直接调用appendLogMessage，避免重复显示

                if show_dialog:
                    QMessageBox.critical(self, "操作失败", f"移除监听对象时出错: {str(e)}")

    async def _view_listener_messages(self, checked=False, instance_id=None, wxid=None, silent=False):
        """
        查看监听对象的消息

        Args:
            checked: 按钮是否被选中
            instance_id: 实例ID
            wxid: 微信ID
            silent: 是否静默操作，不输出非关键日志
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

            if not silent:
                logger.debug(f"正在查看消息: 实例={instance_id}, 聊天={wxid}")

            # 获取消息列表
            messages = await self._get_messages(instance_id, wxid)
            if not silent:
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

            if not silent:
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

                    # 更新状态标签 - 使用可见消息计数
                    visible_count = self._get_visible_message_count()
                    listener_count = self.listener_table.rowCount()
                    self.status_label.setText(f"共 {listener_count} 个监听对象，{visible_count} 条消息")
                except Exception as e:
                    logger.error(f"更新UI时出错: {e}")

            # 使用QTimer在主线程中安全更新UI
            QTimer.singleShot(0, update_ui)

        except Exception as e:
            # 区分常见连接错误和其他错误
            if "Connection refused" in str(e) or "Not connected" in str(e):
                if not silent:
                    logger.error(f"查看监听对象消息时出错(连接问题): {e}")
            else:
                logger.error(f"查看监听对象消息时出错: {e}")
                if not silent:
                    logger.error(f"错误详细信息", exc_info=True)

    @asyncSlot()
    async def _auto_refresh(self):
        """自动刷新监听对象和消息"""
        if not self.auto_refresh_check.isChecked():
            return

        try:
            # 刷新监听对象列表 - 使用静默模式，不产生大量日志
            await self.refresh_listeners(force_reload=False, silent=True)

            # 更新倒计时
            self._update_countdown()

            # 刷新消息列表（如果有选中的监听对象）- 使用静默模式
            if self.selected_listener:
                instance_id, wxid = self.selected_listener
                await self._view_listener_messages(instance_id=instance_id, wxid=wxid, silent=True)

            # 添加简短状态更新到日志窗口
            refresh_time = datetime.now().strftime('%H:%M:%S')
            listener_count = self.listener_table.rowCount()

            # 获取已处理和未处理消息数量
            processed_count, pending_count = await self._get_processed_pending_count()
            total_count = processed_count + pending_count

            # 构建当前日志内容的关键部分（用于比较）
            current_log_key = f"{listener_count}_{total_count}_{processed_count}_{pending_count}"

            # 构建基本日志内容
            log_base = f"自动刷新完成: {listener_count}个监听对象, {total_count}条消息 (已处理: {processed_count}, 未处理: {pending_count})"

            # 检查是否是重复的日志内容
            if current_log_key in self.refresh_log_dict:
                # 更新计数
                self.refresh_log_dict[current_log_key] += 1
                count = self.refresh_log_dict[current_log_key]
            else:
                # 清理旧的日志计数，只保留最近的几个不同类型的日志
                if len(self.refresh_log_dict) > 5:  # 只保留最近5种不同的日志
                    self.refresh_log_dict.clear()

                # 添加新的日志类型并设置计数为1
                self.refresh_log_dict[current_log_key] = 1
                count = 1

            try:
                # 获取当前HTML内容而不是纯文本
                current_html = self.log_text.toHtml()

                # 分割成行 - 保留HTML标签
                # 使用正则表达式匹配所有行，包括它们的HTML标签
                import re
                html_lines = re.findall(r'<p[^>]*>(.*?)</p>', current_html, re.DOTALL)

                # 过滤掉所有包含"自动刷新完成"的行
                filtered_html_lines = [line for line in html_lines if "自动刷新完成" not in line]

                # 清空日志窗口
                self.log_text.clear()

                # 重新添加过滤后的行，保留原始HTML格式
                for line in filtered_html_lines:
                    if line.strip():  # 只添加非空行
                        # 直接使用HTML内容添加，保留原始颜色
                        self.log_text.append(line)

                # 添加新的自动刷新日志（带刷新次数）
                if count > 1:
                    self.log_text.append(f"<font color='blue'>{refresh_time} - {log_base} (刷新次数: {count})</font>")
                else:
                    self.log_text.append(f"<font color='blue'>{refresh_time} - {log_base}</font>")
            except Exception as e:
                # 如果处理出错，使用简单方法：直接添加新日志
                logger.error(f"处理日志时出错: {e}")
                if count > 1:
                    self.log_text.append(f"<font color='blue'>{refresh_time} - {log_base} (刷新次数: {count})</font>")
                else:
                    self.log_text.append(f"<font color='blue'>{refresh_time} - {log_base}</font>")

            # 滚动到底部
            scrollbar = self.log_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        except Exception as e:
            # 只记录严重错误，普通连接错误不记录
            if "Connection refused" not in str(e) and "Not connected" not in str(e):
                logger.error(f"自动刷新出错: {e}")

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
                "SELECT * FROM messages WHERE message_id = ?",
                (message_id,)
            )

            if not message:
                QMessageBox.warning(self, "处理失败", f"找不到消息: {message_id}")
                return

            # 使用统一的消息过滤模块检查消息是否应该被过滤
            from wxauto_mgt.core.message_filter import message_filter
            if message_filter.should_filter_message(message, log_prefix="处理消息"):
                logger.info(f"过滤掉不处理的消息: ID={message_id}")
                QMessageBox.warning(self, "处理失败", f"消息 {message_id} 被过滤，不需要处理")
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
                        status_item = self.message_table.item(row, 3)
                        if status_item:
                            status_item.setText("已完成")
                            status_item.setForeground(QColor(0, 170, 0))  # 绿色
                            # 更新状态栏显示
                            QTimer.singleShot(0, lambda: asyncio.ensure_future(self._update_status_count()))
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
    async def _update_status_count(self, count=None):
        """更新状态栏消息计数"""
        try:
            # 使用计算得到的可见消息数量
            visible_count = self._get_visible_message_count()

            # 获取已处理和未处理消息数量
            processed_count, pending_count = await self._get_processed_pending_count()

            # 记录日志，显示已处理和未处理消息数量
            logger.info(f"消息统计: 已处理: {processed_count}, 未处理: {pending_count}, 总计: {processed_count + pending_count}")

            # 更新状态栏显示
            self.status_label.setText(f"共 {self.listener_table.rowCount()} 个监听对象，{visible_count} 条消息 (已处理: {processed_count}, 未处理: {pending_count})")
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

            # 记录获取到的消息数量 - 使用匹配关键词的格式
            if messages and len(messages) > 0:
                # 避免重复日志，使用统一的"获取到新消息"关键词
                logger.info(f"获取到新消息: 实例={instance_id}, 聊天={wxid}, 数量={len(messages)}")

            # 格式化消息并过滤
            formatted_messages = []
            filtered_count = 0
            for msg in messages:
                # 使用统一的消息过滤模块
                from wxauto_mgt.core.message_filter import message_filter

                # 检查消息是否应该被过滤
                if message_filter.should_filter_message(msg, log_prefix="UI层获取"):
                    filtered_count += 1
                    continue

                # 尝试解析JSON内容
                content = msg.get("content", "")
                try:
                    if content and isinstance(content, str) and (content.startswith('{') or content.startswith('[')):
                        content_obj = json.loads(content)
                        if isinstance(content_obj, dict) and "content" in content_obj:
                            content = content_obj["content"]
                except:
                    pass  # 如果解析失败，保持原始内容

                # 确定消息状态
                status = "pending"
                if msg.get("processed", 0):
                    status = "processed"

                # 考虑投递状态
                delivery_status = msg.get("delivery_status", 0)
                if delivery_status == 1:  # 已投递
                    status = "processed"
                elif delivery_status == 2:  # 投递失败
                    status = "failed"
                elif delivery_status == 3:  # 正在投递
                    status = "pending"

                # 转换状态为中文显示
                display_status = status
                if status == 'pending':
                    display_status = '投递中'
                elif status == 'processed':
                    display_status = '已完成'
                elif status == 'failed':
                    display_status = '失败'

                formatted_msg = {
                    "message_id": msg.get("message_id", ""),
                    "instance_id": msg.get("instance_id", ""),
                    "sender": msg.get("sender", ""),
                    "sender_remark": msg.get("sender_remark", ""),
                    "receiver": wxid if msg.get("sender", "") != wxid else "me",
                    "content": content,
                    "type": msg.get("message_type", "text"),
                    "timestamp": int(msg.get("create_time", 0)),
                    "status": display_status
                }
                formatted_messages.append(formatted_msg)

            # 记录过滤情况
            if filtered_count > 0:
                logger.debug(f"过滤掉 {filtered_count} 条消息 (self发送或time类型)")

            return formatted_messages
        except Exception as e:
            logger.error(f"获取消息时出错: {e}")
            return []

    def _add_message_to_table(self, message: Dict):
        """
        添加消息到表格

        Args:
            message: 消息字典
        """
        try:
            # 检查消息ID是否已存在
            message_id = message.get('message_id', '')
            if not message_id:
                return

            # 检查是否已经在表格中
            for row in range(self.message_table.rowCount()):
                if self.message_table.item(row, 0).data(Qt.UserRole) == message_id:
                    return

            # 使用统一的消息过滤模块
            from wxauto_mgt.core.message_filter import message_filter

            # 记录详细的消息信息，便于调试
            content = message.get('content', '')
            #logger.info(f"表格检查消息: id={message_id}")

            # 使用调试日志记录器记录更详细的信息
            if debug_logger:
                debug_logger.debug(f"表格检查消息详细: id={message_id}")
                debug_logger.debug(f"消息内容: {content[:100]}")
                try:
                    debug_logger.debug(f"完整消息数据: {json.dumps(message, ensure_ascii=False)}")
                except:
                    debug_logger.debug(f"完整消息数据: {str(message)}")

            # 检查消息是否应该被过滤
            if message_filter.should_filter_message(message, log_prefix="表格添加"):
                logger.info(f"表格中过滤掉消息: ID={message_id}")
                return

            # 额外检查消息类型，过滤掉self和time类型的消息
            # 检查所有可能的类型字段
            msg_type = message.get('type', '').lower() if isinstance(message.get('type'), str) else ''
            message_type = message.get('message_type', '').lower() if isinstance(message.get('message_type'), str) else ''

            # 检查发送者是否为Self
            sender = message.get('sender', '').lower() if isinstance(message.get('sender'), str) else ''

            if msg_type in ['self', 'time'] or message_type in ['self', 'time'] or sender == 'self':
                logger.info(f"表格中过滤掉消息: ID={message_id}, 类型={msg_type or message_type}, 发送者={sender}")
                return

            # 获取消息信息
            instance_id = message.get('instance_id', '')
            chat_name = message.get('chat_name', '')
            content = message.get('content', '')
            create_time = message.get('timestamp', 0)
            sender = message.get('sender', '')
            sender_remark = message.get('sender_remark', '')
            msg_type = message.get('type', 'text')
            status = message.get('status', '待处理')

            # 转换时间戳
            time_str = datetime.fromtimestamp(create_time).strftime('%Y-%m-%d %H:%M:%S') if create_time else ''

            # 显示发送者备注或ID
            display_sender = sender_remark if sender_remark else sender

            # 添加新行
            row = self.message_table.rowCount()
            self.message_table.insertRow(row)

            # 设置时间
            time_item = QTableWidgetItem(time_str)
            time_item.setData(Qt.UserRole, message_id)  # 存储消息ID
            time_item.setData(Qt.UserRole + 1, content)  # 存储消息内容
            self.message_table.setItem(row, 0, time_item)

            # 设置发送者
            self.message_table.setItem(row, 1, QTableWidgetItem(display_sender))

            # 设置消息类型
            self.message_table.setItem(row, 2, QTableWidgetItem(msg_type))

            # 设置状态
            # 转换状态显示
            if isinstance(status, str):
                # 如果状态已经是中文，直接使用
                if status in ['投递中', '已完成', '失败']:
                    display_status = status
                # 否则转换英文状态为中文
                elif status == 'pending':
                    display_status = '投递中'
                elif status == 'processed':
                    display_status = '已完成'
                elif status == 'failed':
                    display_status = '失败'
                else:
                    display_status = status
            else:
                display_status = str(status)

            # 根据状态设置颜色
            if display_status == '投递中':
                status_item = QTableWidgetItem(display_status)
                status_item.setForeground(QColor(0, 120, 215))  # 蓝色
            elif display_status == '已完成':
                status_item = QTableWidgetItem(display_status)
                status_item.setForeground(QColor(0, 170, 0))  # 绿色
            elif display_status == '失败':
                status_item = QTableWidgetItem(display_status)
                status_item.setForeground(QColor(255, 0, 0))  # 红色
            else:
                status_item = QTableWidgetItem(display_status)
                status_item.setForeground(QColor(128, 128, 128))  # 灰色

            self.message_table.setItem(row, 3, status_item)

            # 设置内容（新增）
            # 如果内容过长，则截断显示
            display_content = content
            if len(content) > 100:
                display_content = content[:97] + "..."
            self.message_table.setItem(row, 4, QTableWidgetItem(display_content))

            # 如果是当前过滤的实例，则显示，否则隐藏
            if self.current_instance_id and instance_id != self.current_instance_id:
                self.message_table.hideRow(row)

        except Exception as e:
            logger.error(f"添加消息到表格时出错: {e}")

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

        # 过滤后更新状态栏显示的消息计数
        # 使用QTimer在主线程中安全更新状态栏
        QTimer.singleShot(0, lambda: asyncio.ensure_future(self._update_status_count()))

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
            column: 列索引（未使用）
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
                        message_listener.poll_interval = self.poll_interval
                        if self.auto_refresh_check.isChecked():
                            self.refresh_timer.setInterval(self.poll_interval * 1000)

                        # 更新倒计时定时器
                        self.countdown_timer.setInterval(self.poll_interval * 1000)

                    # 读取超时时间设置
                    if 'timeout_minutes' in config and isinstance(config['timeout_minutes'], int) and config['timeout_minutes'] > 0:
                        self.timeout_minutes = config['timeout_minutes']
                        self.timeout_edit.setText(str(self.timeout_minutes))
                        message_listener.timeout_minutes = self.timeout_minutes

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
            column: 列索引（未使用）
        """
        if row < 0:
            return

        # 已显示消息内容在表格中，不需要再单独加载和显示了
        # 但可以在状态栏显示完整信息
        message_id = self.message_table.item(row, 0).data(Qt.UserRole)
        self.selected_message_id = message_id

        # 更新按钮状态
        sender = self.message_table.item(row, 1).text()
        status = self.message_table.item(row, 4).text()

        # 更新状态栏显示
        self.status_label.setText(f"选中消息: ID={message_id} | 发送者={sender} | 状态={status}")

        logger.debug(f"选中消息: {message_id}")

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

            msg_type = self.message_table.item(row, 2).text()
            status = self.message_table.item(row, 3).text()

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
                    self.log_text,
                    "append",
                    Qt.QueuedConnection,
                    Q_ARG(str, content)
                )
            else:
                # 未找到消息
                QMetaObject.invokeMethod(
                    self.log_text,
                    "append",
                    Qt.QueuedConnection,
                    Q_ARG(str, f"无法加载消息内容: 消息ID {message_id} 不存在")
                )
        except Exception as e:
            logger.error(f"加载消息内容时出错: {e}")
            QMetaObject.invokeMethod(
                self.log_text,
                "append",
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
                type_item = self.message_table.item(row, 2)
                status_item = self.message_table.item(row, 3)

                # 获取消息ID和内容
                message_id = time_item.data(Qt.UserRole) if time_item else ""
                content = time_item.data(Qt.UserRole + 1) if time_item else ""

                messages.append({
                    'time': time_item.text() if time_item else "",
                    'sender': sender_item.text() if sender_item else "",
                    'type': type_item.text() if type_item else "",
                    'status': status_item.text() if status_item else "",
                    'message_id': message_id,
                    'content': content
                })

            # 写入CSV文件
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=['time', 'sender', 'type', 'status', 'message_id', 'content'])
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

    def _init_logging(self):
        """初始化日志系统，捕获相关日志到UI"""
        try:
            # 创建自定义日志处理器
            self.log_handler = QTextEditLogger(self, self.log_text)

            # 获取根日志记录器
            root_logger = logging.getLogger('wxauto_mgt')

            # 设置日志级别为DEBUG，确保捕获所有级别的日志
            self.log_handler.setLevel(logging.DEBUG)

            # 删除之前可能添加过的处理器，避免重复
            for handler in root_logger.handlers[:]:
                if isinstance(handler, QTextEditLogger):
                    root_logger.removeHandler(handler)

            # 添加我们的处理器到根日志记录器
            root_logger.addHandler(self.log_handler)

            # 确保根日志记录器级别设置为DEBUG
            # 这样所有的日志都能被传递到处理器
            root_logger.setLevel(logging.DEBUG)

            # 捕获消息监听模块的日志
            message_listener_logger = logging.getLogger('wxauto_mgt.core.message_listener')
            # 首先移除已有的处理器
            for handler in message_listener_logger.handlers[:]:
                if isinstance(handler, QTextEditLogger):
                    message_listener_logger.removeHandler(handler)
            message_listener_logger.addHandler(self.log_handler)
            message_listener_logger.setLevel(logging.DEBUG)

            # 捕获数据库模块的日志
            db_logger = logging.getLogger('wxauto_mgt.data')
            # 首先移除已有的处理器
            for handler in db_logger.handlers[:]:
                if isinstance(handler, QTextEditLogger):
                    db_logger.removeHandler(handler)
            db_logger.addHandler(self.log_handler)
            db_logger.setLevel(logging.DEBUG)

            # 捕获API客户端模块的日志
            api_logger = logging.getLogger('wxauto_mgt.core.api_client')
            # 首先移除已有的处理器
            for handler in api_logger.handlers[:]:
                if isinstance(handler, QTextEditLogger):
                    api_logger.removeHandler(handler)
            api_logger.addHandler(self.log_handler)
            api_logger.setLevel(logging.DEBUG)

            # 捕获其他模块的日志
            filter_logger = logging.getLogger('wxauto_mgt.filters')
            for handler in filter_logger.handlers[:]:
                if isinstance(handler, QTextEditLogger):
                    filter_logger.removeHandler(handler)
            filter_logger.addHandler(self.log_handler)
            filter_logger.setLevel(logging.DEBUG)

            utils_logger = logging.getLogger('wxauto_mgt.utils')
            for handler in utils_logger.handlers[:]:
                if isinstance(handler, QTextEditLogger):
                    utils_logger.removeHandler(handler)
            utils_logger.addHandler(self.log_handler)
            utils_logger.setLevel(logging.DEBUG)

            # 初始日志消息 - 确保有一条初始日志
            logger.info("消息监听界面已启动，日志系统已连接")

            # 添加一些系统状态信息
            try:
                from wxauto_mgt.core.message_listener import message_listener
                listener_count = len(message_listener.get_active_listeners())
                logger.info(f"当前监听对象数量: {listener_count}")
                logger.info(f"轮询间隔: {self.poll_interval}秒, 超时时间: {self.timeout_minutes}分钟")
            except Exception as e:
                logger.warning(f"获取系统状态信息失败: {e}")

            # 记录日志系统初始化成功
            logger.debug("日志系统初始化完成")
            print("日志系统初始化完成 - 控制台测试输出")

        except Exception as e:
            print(f"初始化日志系统时出错: {e}")
            # 使用QMessageBox显示错误，因为日志系统可能未初始化
            QMessageBox.critical(self, "日志系统错误", f"初始化日志系统时出错: {str(e)}")

    def _clear_log(self):
        """清空日志窗口"""
        self.log_text.clear()
        if hasattr(self, 'log_handler'):
            self.log_handler.log_cache.clear()
        # 清空刷新日志计数字典
        self.refresh_log_dict.clear()
        logger.info("日志已清空")

    @Slot(str, str)
    def appendLogMessage(self, message, color):
        """向日志窗口添加消息，使用指定颜色"""
        try:
            # 设置文本颜色
            color_obj = QColor("black")  # 默认黑色
            if color == "red":
                color_obj = QColor("red")
            elif color == "orange":
                color_obj = QColor(255, 165, 0)  # 橙色
            elif color == "blue":
                color_obj = QColor("blue")

            # 设置颜色并添加消息
            self.log_text.setTextColor(color_obj)
            self.log_text.append(message)

            # 滚动到底部
            scrollbar = self.log_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        except Exception as e:
            print(f"添加日志消息时出错: {e}")  # 使用print避免递归

    def _calculate_countdown(self, listener_info):
        """计算监听超时倒计时"""
        if not listener_info or not hasattr(listener_info, 'last_message_time'):
            return "未知"

        # 检查是否已标记为不活跃
        if hasattr(listener_info, 'active') and not listener_info.active:
            return "将移除"

        # 检查是否在启动宽限期内
        from wxauto_mgt.core.message_listener import message_listener
        current_time = time.time()
        if hasattr(message_listener, 'startup_timestamp') and message_listener.startup_timestamp > 0:
            grace_period = 10  # 10秒宽限期
            time_since_startup = current_time - message_listener.startup_timestamp
            if time_since_startup < grace_period:
                return "初始化中"

        last_message_time = listener_info.last_message_time
        if not last_message_time:
            return "未知"

        # 计算剩余时间（秒）
        remaining_seconds = (last_message_time + self.timeout_minutes * 60) - current_time

        if remaining_seconds <= 0:
            # 只返回状态，不在这里设置标记
            return "已超时"

        # 格式化为分:秒
        minutes = int(remaining_seconds // 60)
        seconds = int(remaining_seconds % 60)

        return f"{minutes}分{seconds}秒"

    def _update_countdown(self):
        """更新所有监听对象的倒计时"""
        try:
            # 获取消息监听器引用
            from wxauto_mgt.core.message_listener import message_listener

            # 如果消息监听器正在启动过程中处理超时对象，则暂时跳过UI触发的处理
            if hasattr(message_listener, '_starting_up') and message_listener._starting_up:
                # 不频繁输出日志，降低日志量
                return

            # 检查启动宽限期 - 启动后10秒内不执行超时移除
            current_time = time.time()
            if hasattr(message_listener, 'startup_timestamp') and message_listener.startup_timestamp > 0:
                grace_period = 10  # 10秒宽限期
                time_since_startup = current_time - message_listener.startup_timestamp
                if time_since_startup < grace_period:
                    # 不频繁输出日志，降低日志量
                    # 更新所有显示，但不执行超时处理
                    for row in range(self.listener_table.rowCount()):
                        try:
                            instance_id = self.listener_table.item(row, 0).text()
                            who = self.listener_table.item(row, 1).text()

                            listener_info = self.listener_data.get((instance_id, who))
                            if listener_info:
                                # 在宽限期内，所有倒计时都显示为"初始化中"
                                self.listener_table.item(row, 3).setText("初始化中")
                        except Exception as e:
                            # 不频繁记录这类错误日志
                            pass
                    return

            # 批量收集需要移除的监听对象
            to_remove = []

            # 提前记录监听对象的状态，只记录一次
            listener_status = {}

            # 第一遍扫描：更新UI并收集超时对象
            for row in range(self.listener_table.rowCount()):
                try:
                    instance_id = self.listener_table.item(row, 0).text()
                    who = self.listener_table.item(row, 1).text()

                    listener_info = self.listener_data.get((instance_id, who))
                    if listener_info:
                        countdown = self._calculate_countdown(listener_info)
                        self.listener_table.item(row, 3).setText(countdown)

                        # 记录监听对象状态
                        listener_status[(instance_id, who)] = countdown

                        # 检查是否需要移除（已超时且未标记为已处理移除）
                        if countdown == "已超时" and not getattr(listener_info, 'marked_for_removal', False):
                            # 标记为已处理，避免重复移除
                            listener_info.marked_for_removal = True
                            # 添加到待移除列表
                            to_remove.append((instance_id, who))
                            # 只有当实际要移除时，才记录日志
                            # 使用统一格式，确保日志处理器能正确去重
                            logger.info(f"超时移除监听对象: 实例={instance_id}, 聊天={who}")

                            # 不再在这里添加日志窗口消息，避免重复
                except Exception as e:
                    # 不记录此类错误日志，降低日志量
                    pass

            # 如果有超时监听对象需要移除，一次性批量处理
            if to_remove:
                if len(to_remove) > 0:
                    # 记录一条汇总日志，而不是每个监听对象一条
                    logger.warning(f"超时移除: 发现 {len(to_remove)} 个超时监听对象，开始批量移除")

                # 批量移除并最后只刷新一次
                async def remove_batch():
                    try:
                        # 记录移除开始
                        logger.info(f"超时移除开始: {len(to_remove)} 个监听对象")

                        # 批量移除，减少不必要的日志
                        for i, (instance_id, who) in enumerate(to_remove):
                            # 每5个记录一次进度，避免日志过多
                            if i % 5 == 0 or i == len(to_remove) - 1:
                                logger.info(f"超时移除进度: {i+1}/{len(to_remove)}")
                            await self._remove_listener(instance_id, who, show_dialog=False)

                        # 完成后强制刷新一次
                        await self.refresh_listeners(force_reload=True)
                        # 记录完成日志
                        logger.info(f"超时移除完成: {len(to_remove)} 个监听对象")
                    except Exception as e:
                        logger.error(f"批量移除超时监听对象时出错: {e}")

                # 启动批量移除任务
                task = asyncio.create_task(remove_batch())
                # 添加完成回调以记录任何异常
                task.add_done_callback(lambda t: logger.error(f"移除超时监听对象任务出错: {t.exception()}") if t.exception() else None)
        except Exception as e:
            logger.error(f"更新倒计时出错: {e}")
            # 仅在真正出错时记录异常堆栈
            if "Connection refused" not in str(e) and "Not connected" not in str(e):
                logger.exception(e)

    def _refresh_system_status(self):
        """刷新并显示系统状态信息到日志窗口"""
        try:
            # 添加分隔线，而不是清空日志窗口
            self.log_text.append("<font color='gray'>------------- 系统状态更新 -------------</font>")

            # 输出系统状态信息
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.log_text.append(f"<font color='blue'>系统状态更新时间: {current_time}</font>")

            # 获取监听器状态
            from wxauto_mgt.core.message_listener import message_listener
            listener_count = sum(len(listeners) for listeners in message_listener.get_active_listeners().values())
            running_status = "运行中" if message_listener.running else "已停止"

            self.log_text.append(f"<font color='black'>消息监听服务: {running_status}</font>")
            self.log_text.append(f"<font color='black'>当前监听对象数量: {listener_count}</font>")
            self.log_text.append(f"<font color='black'>轮询间隔: {self.poll_interval}秒</font>")
            self.log_text.append(f"<font color='black'>超时时间: {self.timeout_minutes}分钟</font>")

            # 获取超时统计
            timeout_count = 0
            active_count = 0
            for instance_id, listeners in message_listener.listeners.items():
                for wxid, listener_info in listeners.items():
                    if hasattr(listener_info, 'marked_for_removal') and listener_info.marked_for_removal:
                        timeout_count += 1
                    else:
                        active_count += 1

            if timeout_count > 0:
                self.log_text.append(f"<font color='orange'>当前有 {timeout_count} 个监听对象已超时</font>")

            self.log_text.append("<font color='gray'>---------------------------------------</font>")

            # 将焦点滚动到底部
            scrollbar = self.log_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

            logger.info(f"系统状态已刷新，当前有 {active_count} 个活跃监听对象")
        except Exception as e:
            self.log_text.append(f"<font color='red'>获取系统状态信息失败: {str(e)}</font>")
            logger.error(f"刷新系统状态时出错: {e}")

    def _auto_cleanup_logs(self):
        """自动清理过长日志"""
        try:
            # 获取日志文本
            log_text = self.log_text.toPlainText()

            # 检查日志长度
            if len(log_text) > 10000:  # 假设10000字符为过长日志
                # 清理日志
                self.log_text.clear()
                logger.info("日志已自动清理")
        except Exception as e:
            logger.error(f"自动清理日志时出错: {e}")

    def _get_visible_message_count(self):
        """计算当前可见的消息数量（考虑过滤条件）"""
        count = 0
        for row in range(self.message_table.rowCount()):
            if not self.message_table.isRowHidden(row):
                count += 1
        return count

    async def _get_processed_pending_count(self) -> tuple:
        """
        获取已处理和未处理消息的数量

        Returns:
            tuple: (已处理消息数, 未处理消息数)
        """
        try:
            from wxauto_mgt.data.db_manager import db_manager

            # 获取当前实例ID
            instance_id = self.current_instance_id
            if not instance_id:
                return (0, 0)

            # 查询已处理消息数量
            processed_query = """
                SELECT COUNT(*) as count FROM messages
                WHERE instance_id = ? AND (processed = 1 OR delivery_status = 1)
            """
            processed_result = await db_manager.fetchone(processed_query, (instance_id,))
            processed_count = processed_result.get('count', 0) if processed_result else 0

            # 查询未处理消息数量
            pending_query = """
                SELECT COUNT(*) as count FROM messages
                WHERE instance_id = ? AND processed = 0 AND (delivery_status = 0 OR delivery_status = 3)
            """
            pending_result = await db_manager.fetchone(pending_query, (instance_id,))
            pending_count = pending_result.get('count', 0) if pending_result else 0

            return (processed_count, pending_count)
        except Exception as e:
            logger.error(f"获取消息处理状态计数时出错: {e}")
            return (0, 0)
