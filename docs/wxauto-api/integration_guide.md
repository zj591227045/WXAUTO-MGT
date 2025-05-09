# wxauto_http_api 集成指南

## 项目概述

wxauto_http_api 是一个基于 wxauto/wxautox 的微信自动化 HTTP API 服务，提供了完整的 HTTP 接口，使开发者能够通过 HTTP 请求控制微信客户端，实现消息发送、接收、文件传输等功能。本文档将介绍如何将 wxauto_http_api 作为子项目集成到 wxauto-mgt 项目中。

### 核心功能

- 微信消息发送与接收
- 文件、图片、语音传输
- 群聊管理与监控
- 联系人管理
- 支持 wxauto（开源）和 wxautox（付费）两种库的动态切换

### 技术架构

- **后端框架**：Flask
- **微信自动化**：wxauto/wxautox
- **UI 界面**：Tkinter (独立运行时)
- **配置管理**：JSON 配置文件 + 环境变量

## 模块化集成方案

将 wxauto_http_api 集成到 wxauto-mgt 项目中，需要进行模块化设计，使其能够作为一个标签页存在于 PySide6 构建的 UI 中，并且能够根据配置灵活启用或禁用。

### 目录结构设计

建议在 wxauto-mgt 项目中创建如下目录结构：

```
wxauto-mgt/
├── main.py                  # 主程序入口
├── ui/                      # UI 相关代码
│   ├── main_window.py       # 主窗口
│   └── tabs/                # 各个标签页
│       ├── wxauto_http_tab.py  # wxauto_http_api 标签页
│       └── ...
├── modules/                 # 功能模块
│   ├── wxauto_http_api/     # wxauto_http_api 子模块
│   │   ├── __init__.py      # 模块初始化
│   │   ├── api_server.py    # API 服务器
│   │   ├── app/             # 应用代码
│   │   └── ...
│   └── ...
└── config/                  # 配置文件
    ├── settings.json        # 全局设置
    └── modules_config.json  # 模块配置
```

### 模块化接口设计

为了实现模块化集成，wxauto_http_api 需要提供以下接口：

#### 1. 模块初始化接口

```python
def initialize(config=None):
    """
    初始化 wxauto_http_api 模块
    
    Args:
        config (dict, optional): 模块配置
    
    Returns:
        bool: 初始化是否成功
    """
```

#### 2. 服务启动/停止接口

```python
def start_server(host='0.0.0.0', port=5000, debug=False):
    """
    启动 API 服务器
    
    Args:
        host (str): 监听地址
        port (int): 监听端口
        debug (bool): 是否启用调试模式
    
    Returns:
        bool: 启动是否成功
    """

def stop_server():
    """
    停止 API 服务器
    
    Returns:
        bool: 停止是否成功
    """
```

#### 3. 状态查询接口

```python
def get_status():
    """
    获取服务状态
    
    Returns:
        dict: 状态信息，包括服务是否运行、微信连接状态等
    """
```

#### 4. 日志接口

```python
def get_logs(max_lines=100, filter_options=None):
    """
    获取日志
    
    Args:
        max_lines (int): 最大行数
        filter_options (dict, optional): 过滤选项
    
    Returns:
        list: 日志条目
    """
```

### 集成实现

#### 1. 创建 API 服务器模块

在 `modules/wxauto_http_api/api_server.py` 中实现 API 服务器：

```python
import threading
import time
from flask import Flask
from app import create_app
from app.config import Config
from app.logs import logger
from app.wechat import wechat_manager
from app.api_queue import start_queue_processors, stop_queue_processors

class ApiServer:
    def __init__(self):
        self.app = None
        self.server_thread = None
        self.running = False
        self.port = 5000
        self.host = '0.0.0.0'
        self.debug = False
        
    def initialize(self, config=None):
        """初始化服务器"""
        if config:
            self.port = config.get('port', 5000)
            self.host = config.get('host', '0.0.0.0')
            self.debug = config.get('debug', False)
            
        # 创建 Flask 应用
        self.app = create_app()
        return True
        
    def start(self):
        """启动服务器"""
        if self.running:
            logger.warning("服务器已经在运行")
            return False
            
        if not self.app:
            logger.error("服务器未初始化")
            return False
            
        # 启动队列处理器
        start_queue_processors()
        
        # 在新线程中启动 Flask 服务器
        def run_server():
            self.app.run(
                host=self.host,
                port=self.port,
                debug=self.debug,
                use_reloader=False,
                threaded=True
            )
            
        self.server_thread = threading.Thread(target=run_server)
        self.server_thread.daemon = True
        self.server_thread.start()
        self.running = True
        logger.info(f"API 服务器已启动，监听地址: {self.host}:{self.port}")
        return True
        
    def stop(self):
        """停止服务器"""
        if not self.running:
            logger.warning("服务器未运行")
            return False
            
        # 停止队列处理器
        stop_queue_processors()
        
        # 停止 Flask 服务器
        # 注意：Flask 没有优雅的停止方法，这里使用一个变通方法
        import requests
        try:
            requests.get(f"http://localhost:{self.port}/shutdown")
        except:
            pass
            
        self.running = False
        logger.info("API 服务器已停止")
        return True
        
    def get_status(self):
        """获取服务器状态"""
        status = {
            'running': self.running,
            'host': self.host,
            'port': self.port,
            'wechat_connected': False
        }
        
        # 检查微信连接状态
        if wechat_manager.get_instance():
            status['wechat_connected'] = wechat_manager.check_connection()
            status['wechat_lib'] = wechat_manager.get_instance().get_lib_name()
            
        return status

# 创建全局服务器实例
api_server = ApiServer()
```

#### 2. 创建模块初始化文件

在 `modules/wxauto_http_api/__init__.py` 中实现模块接口：

```python
from .api_server import api_server
from app.logs import logger
import os
import sys

# 确保当前目录在 Python 路径中
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

def initialize(config=None):
    """初始化模块"""
    try:
        return api_server.initialize(config)
    except Exception as e:
        print(f"初始化 wxauto_http_api 模块失败: {str(e)}")
        return False

def start_server(host='0.0.0.0', port=5000, debug=False):
    """启动 API 服务器"""
    api_server.host = host
    api_server.port = port
    api_server.debug = debug
    return api_server.start()

def stop_server():
    """停止 API 服务器"""
    return api_server.stop()

def get_status():
    """获取服务状态"""
    return api_server.get_status()

def get_logs(max_lines=100, filter_options=None):
    """获取日志"""
    from app.logs import get_recent_logs
    return get_recent_logs(max_lines, filter_options)
```

#### 3. 创建 UI 标签页

在 `ui/tabs/wxauto_http_tab.py` 中实现 PySide6 标签页：

```python
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                              QPushButton, QComboBox, QLineEdit, QTextEdit,
                              QGroupBox, QCheckBox, QSpinBox)
from PySide6.QtCore import Qt, QTimer, Signal, Slot

class WxautoHttpTab(QWidget):
    """wxauto_http_api 标签页"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.api_running = False
        self.current_lib = "wxauto"
        self.current_port = 5000
        self.timer = None
        
        self.init_ui()
        self.load_config()
        self.update_status()
        
        # 启动定时器，定期更新状态
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_status)
        self.timer.start(1000)  # 每秒更新一次
        
    def init_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout(self)
        
        # 控制面板
        control_group = QGroupBox("控制面板")
        control_layout = QVBoxLayout(control_group)
        
        # 第一行：库选择和服务控制
        row1 = QHBoxLayout()
        
        # 库选择
        lib_layout = QHBoxLayout()
        lib_layout.addWidget(QLabel("微信库:"))
        self.lib_combo = QComboBox()
        self.lib_combo.addItems(["wxauto", "wxautox"])
        lib_layout.addWidget(self.lib_combo)
        row1.addLayout(lib_layout)
        
        # 端口设置
        port_layout = QHBoxLayout()
        port_layout.addWidget(QLabel("端口:"))
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(5000)
        port_layout.addWidget(self.port_spin)
        row1.addLayout(port_layout)
        
        # 服务控制
        self.start_btn = QPushButton("启动服务")
        self.start_btn.clicked.connect(self.toggle_service)
        row1.addWidget(self.start_btn)
        
        # 初始化微信
        self.init_wx_btn = QPushButton("初始化微信")
        self.init_wx_btn.clicked.connect(self.initialize_wechat)
        row1.addWidget(self.init_wx_btn)
        
        control_layout.addLayout(row1)
        
        # 第二行：状态显示
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("服务状态:"))
        self.status_label = QLabel("未启动")
        row2.addWidget(self.status_label)
        
        row2.addWidget(QLabel("微信连接:"))
        self.wx_status_label = QLabel("未连接")
        row2.addWidget(self.wx_status_label)
        
        row2.addWidget(QLabel("当前库:"))
        self.current_lib_label = QLabel("wxauto")
        row2.addWidget(self.current_lib_label)
        
        row2.addStretch()
        control_layout.addLayout(row2)
        
        layout.addWidget(control_group)
        
        # 日志显示
        log_group = QGroupBox("API 日志")
        log_layout = QVBoxLayout(log_group)
        
        # 日志过滤
        filter_layout = QHBoxLayout()
        self.hide_status_check = QCheckBox("隐藏状态检查")
        filter_layout.addWidget(self.hide_status_check)
        
        self.hide_debug_check = QCheckBox("隐藏调试信息")
        filter_layout.addWidget(self.hide_debug_check)
        
        filter_layout.addWidget(QLabel("自定义过滤:"))
        self.filter_edit = QLineEdit()
        filter_layout.addWidget(self.filter_edit)
        
        self.apply_filter_btn = QPushButton("应用过滤")
        self.apply_filter_btn.clicked.connect(self.apply_filter)
        filter_layout.addWidget(self.apply_filter_btn)
        
        log_layout.addLayout(filter_layout)
        
        # 日志文本框
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        
        layout.addWidget(log_group)
        
    def load_config(self):
        """加载配置"""
        try:
            import json
            from pathlib import Path
            
            config_path = Path("data/api/config/app_config.json")
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    
                # 设置微信库
                lib_name = config.get("wechat_lib", "wxauto")
                self.current_lib = lib_name
                self.lib_combo.setCurrentText(lib_name)
                self.current_lib_label.setText(lib_name)
                
                # 设置端口
                port = config.get("port", 5000)
                self.current_port = port
                self.port_spin.setValue(port)
        except Exception as e:
            self.add_log(f"加载配置失败: {str(e)}")
            
    def save_config(self):
        """保存配置"""
        try:
            import json
            from pathlib import Path
            
            # 确保目录存在
            config_dir = Path("data/api/config")
            config_dir.mkdir(parents=True, exist_ok=True)
            
            config_path = config_dir / "app_config.json"
            
            # 读取现有配置
            config = {}
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
            
            # 更新配置
            config["wechat_lib"] = self.lib_combo.currentText()
            config["port"] = self.port_spin.value()
            
            # 保存配置
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
                
            self.add_log("配置已保存")
        except Exception as e:
            self.add_log(f"保存配置失败: {str(e)}")
            
    def toggle_service(self):
        """切换服务状态"""
        if self.api_running:
            self.stop_service()
        else:
            self.start_service()
            
    def start_service(self):
        """启动服务"""
        try:
            # 保存配置
            self.save_config()
            
            # 导入模块
            from modules.wxauto_http_api import start_server
            
            # 获取配置
            host = "0.0.0.0"
            port = self.port_spin.value()
            
            # 启动服务
            success = start_server(host=host, port=port)
            
            if success:
                self.api_running = True
                self.start_btn.setText("停止服务")
                self.status_label.setText("运行中")
                self.add_log(f"API 服务已启动，监听地址: {host}:{port}")
            else:
                self.add_log("启动 API 服务失败")
        except Exception as e:
            self.add_log(f"启动服务失败: {str(e)}")
            
    def stop_service(self):
        """停止服务"""
        try:
            # 导入模块
            from modules.wxauto_http_api import stop_server
            
            # 停止服务
            success = stop_server()
            
            if success:
                self.api_running = False
                self.start_btn.setText("启动服务")
                self.status_label.setText("已停止")
                self.add_log("API 服务已停止")
            else:
                self.add_log("停止 API 服务失败")
        except Exception as e:
            self.add_log(f"停止服务失败: {str(e)}")
            
    def initialize_wechat(self):
        """初始化微信"""
        try:
            # 导入模块
            from modules.wxauto_http_api import initialize_wechat
            
            # 初始化微信
            success = initialize_wechat()
            
            if success:
                self.add_log("微信初始化成功")
                self.update_status()
            else:
                self.add_log("微信初始化失败")
        except Exception as e:
            self.add_log(f"初始化微信失败: {str(e)}")
            
    def update_status(self):
        """更新状态"""
        try:
            # 导入模块
            from modules.wxauto_http_api import get_status
            
            # 获取状态
            status = get_status()
            
            # 更新 UI
            if status["running"]:
                self.api_running = True
                self.start_btn.setText("停止服务")
                self.status_label.setText("运行中")
            else:
                self.api_running = False
                self.start_btn.setText("启动服务")
                self.status_label.setText("已停止")
                
            if status.get("wechat_connected", False):
                self.wx_status_label.setText("已连接")
                self.wx_status_label.setStyleSheet("color: green")
            else:
                self.wx_status_label.setText("未连接")
                self.wx_status_label.setStyleSheet("color: red")
                
            self.current_lib_label.setText(status.get("wechat_lib", "wxauto"))
            
            # 更新日志
            self.update_logs()
        except Exception as e:
            pass  # 忽略状态更新错误
            
    def update_logs(self):
        """更新日志"""
        try:
            # 导入模块
            from modules.wxauto_http_api import get_logs
            
            # 获取过滤选项
            filter_options = {
                "hide_status_check": self.hide_status_check.isChecked(),
                "hide_debug": self.hide_debug_check.isChecked(),
                "custom_filter": self.filter_edit.text()
            }
            
            # 获取日志
            logs = get_logs(max_lines=200, filter_options=filter_options)
            
            # 更新日志显示
            if logs:
                # 保存当前滚动位置
                scrollbar = self.log_text.verticalScrollBar()
                at_bottom = scrollbar.value() >= scrollbar.maximum() - 10
                
                # 更新文本
                self.log_text.setText("\n".join(logs))
                
                # 如果之前在底部，则滚动到底部
                if at_bottom:
                    self.log_text.verticalScrollBar().setValue(
                        self.log_text.verticalScrollBar().maximum()
                    )
        except Exception as e:
            pass  # 忽略日志更新错误
            
    def apply_filter(self):
        """应用日志过滤"""
        self.update_logs()
        
    def add_log(self, message):
        """添加日志"""
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        
        # 添加到日志显示
        self.log_text.append(log_entry)
        
        # 滚动到底部
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )
```

## 集成到 wxauto-mgt 的步骤

### 1. 复制 wxauto_http_api 代码

将 wxauto_http_api 项目的核心代码复制到 wxauto-mgt 项目的 `modules/wxauto_http_api` 目录中，保持以下结构：

```
modules/wxauto_http_api/
├── __init__.py       # 模块接口
├── api_server.py     # API 服务器
├── app/              # 应用代码
│   ├── __init__.py
│   ├── api/
│   ├── config.py
│   ├── logs.py
│   ├── wechat.py
│   └── ...
├── wxauto/           # wxauto 库
└── data/             # 数据目录
    └── api/
        ├── config/
        ├── logs/
        └── temp/
```

### 2. 修改配置管理

修改 `config_manager.py` 文件，使其能够适应作为子模块运行的情况：

```python
import os
import json
from pathlib import Path

# 获取模块根目录
MODULE_ROOT = Path(os.path.dirname(os.path.abspath(__file__)))

# 配置目录
DATA_DIR = MODULE_ROOT / "data"
API_DIR = DATA_DIR / "api"
CONFIG_DIR = API_DIR / "config"
LOGS_DIR = API_DIR / "logs"
TEMP_DIR = API_DIR / "temp"

# 配置文件路径
LOG_FILTER_CONFIG = CONFIG_DIR / "log_filter.json"
APP_CONFIG_FILE = CONFIG_DIR / "app_config.json"

# 确保目录存在
def ensure_dirs():
    """确保所有必要的目录都存在"""
    for directory in [DATA_DIR, API_DIR, CONFIG_DIR, LOGS_DIR, TEMP_DIR]:
        directory.mkdir(exist_ok=True, parents=True)
```

### 3. 在主窗口中添加标签页

在 wxauto-mgt 项目的主窗口中添加 wxauto_http_api 标签页：

```python
from PySide6.QtWidgets import QMainWindow, QTabWidget
from ui.tabs.wxauto_http_tab import WxautoHttpTab

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("wxauto-mgt")
        self.resize(800, 600)
        
        # 创建标签页
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)
        
        # 添加 wxauto_http_api 标签页
        self.wxauto_http_tab = WxautoHttpTab()
        self.tab_widget.addTab(self.wxauto_http_tab, "微信 HTTP API")
        
        # 添加其他标签页...
        
    def closeEvent(self, event):
        """窗口关闭事件"""
        # 停止 API 服务
        try:
            from modules.wxauto_http_api import stop_server
            stop_server()
        except:
            pass
        
        super().closeEvent(event)
```

### 4. 添加模块配置

在 wxauto-mgt 项目的配置文件中添加 wxauto_http_api 模块的配置：

```json
{
    "modules": {
        "wxauto_http_api": {
            "enabled": true,
            "auto_start": false,
            "port": 5000,
            "wechat_lib": "wxauto"
        }
    }
}
```

## 使用说明

### 1. 启动服务

在 wxauto-mgt 的 UI 中，切换到"微信 HTTP API"标签页，点击"启动服务"按钮启动 API 服务。

### 2. 初始化微信

点击"初始化微信"按钮初始化微信实例。确保微信客户端已经登录。

### 3. 调用 API

API 服务启动后，可以通过 HTTP 请求调用微信功能，例如：

```
POST http://localhost:5000/api/message/send
Content-Type: application/json
X-API-Key: your-api-key

{
    "receiver": "接收者名称",
    "message": "消息内容"
}
```

## 注意事项

1. 确保 wxauto_http_api 模块的路径正确配置，特别是 wxauto 库的路径
2. 在集成过程中，需要处理好线程安全和资源释放问题
3. 当 wxauto-mgt 关闭时，确保正确停止 API 服务
4. 配置文件应该能够在 wxauto-mgt 和 wxauto_http_api 之间共享

## 故障排除

### 服务无法启动

- 检查端口是否被占用
- 确保 wxauto 或 wxautox 库已正确安装
- 查看日志获取详细错误信息

### 微信无法初始化

- 确保微信客户端已登录
- 检查 wxauto 或 wxautox 库是否能正常工作
- 尝试重启微信客户端

### API 调用失败

- 检查 API 密钥是否正确
- 确保微信已初始化
- 查看日志获取详细错误信息
