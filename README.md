# WxAuto管理工具

WxAuto管理工具是一个基于Python开发的桌面应用程序，用于管理多个WxAuto实例。它提供了微信状态监控、消息监听与转发、多实例管理等功能，支持与ASTRBot和LLM服务集成。

## 功能特点

- **多实例管理**：支持同时管理多个WxAuto实例
- **状态监控**：实时监控微信实例的状态和性能指标
- **消息监听**：监听和管理微信消息，支持自动回复
- **集成扩展**：提供ASTRBot和第三方LLM服务的集成
- **数据持久化**：使用SQLite存储配置和消息数据
- **安全特性**：支持配置加密和安全通信

## 安装

### 环境要求

- Python 3.11 或更高版本
- PySide6 (Qt for Python)
- 其他依赖见 `requirements.txt`

### 使用Conda安装

```bash
# 创建新的Conda环境
conda create -n wxauto python=3.11
conda activate wxauto

# 安装依赖
pip install -r requirements.txt
```

## 使用方法

### 启动程序

```bash
# 从项目根目录运行
python wxauto_mgt/main.py
```

### 添加微信实例

1. 点击界面中的"添加实例"按钮
2. 填写微信实例的名称、API地址和API密钥
3. 点击"确定"保存实例配置

### 监听消息

1. 切换到"消息监听"选项卡
2. 点击"添加监听对象"按钮
3. 选择要监听的微信ID或群ID
4. 开始接收消息

## 开发

### 项目结构

```
wxauto_mgt/
├── app/
│   ├── core/          # 核心服务层
│   ├── data/          # 数据持久化层
│   ├── api/           # API接口层
│   ├── ui/            # 用户界面层
│   └── utils/         # 工具类
├── docs/              # 文档
├── main.py            # 程序入口点
└── config/            # 配置文件
```

### 自定义开发

1. 核心服务扩展：修改 `app/core/` 下的模块
2. UI自定义：修改 `app/ui/` 下的组件
3. 数据模型扩展：修改 `app/data/` 下的存储类

## 配置

配置文件位于 `~/.wxauto_mgt/config.json`，支持以下配置项：

- **实例配置**：管理多个WxAuto实例
- **消息监听设置**：轮询间隔、自动重试
- **接口设置**：管理第三方接口配置
- **安全设置**：加密配置和通信安全

## 许可证

[MIT License](LICENSE)

## 相关链接

- [WxAuto文档](https://github.com/yourusername/wxauto)
- [PySide6文档](https://doc.qt.io/qtforpython-6/) 