# WxAuto管理工具

<div align="center">

![WxAuto管理工具](https://img.shields.io/badge/WxAuto-管理工具-blue)
![Python](https://img.shields.io/badge/Python-3.11+-green)
![PySide6](https://img.shields.io/badge/UI-PySide6-orange)
![SQLite](https://img.shields.io/badge/Database-SQLite-lightgrey)

</div>

> 本项目基于wxauto项目做二次开发，致谢：https://github.com/cluic/wxauto

## ⚠️ 重要提示

**本项目无法独立运行，请与wxauto http api项目搭配使用：**
https://github.com/zj591227045/WXAUTO-HTTP-API

## 📝 项目简介

WxAuto管理工具是一个基于Python开发的桌面应用程序，用于管理多个WxAuto实例。它提供了微信状态监控、消息监听与转发、多实例管理等功能，支持对接Dify平台和兼容OpenAI API的服务。

## 📸 软件界面预览

### 主界面
![主界面](docs/IMG/01.png)
*主界面展示了实例管理、消息监听和服务平台等核心功能的选项卡，支持多实例管理和状态监控。*

### 消息投递规则
![消息投递规则](docs/IMG/02.png)
*消息投递规则界面允许用户配置消息如何转发到不同的AI服务平台，支持灵活的规则设置和优先级管理。*

## ✨ 功能特点

- **🔄 多实例管理**：支持同时管理多个WxAuto实例
- **📊 状态监控**：实时监控微信实例的状态和性能指标
- **💬 消息监听**：监听和管理微信消息，支持自动回复
- **🔌 集成扩展**：支持对接Dify平台和兼容OpenAI API的服务
- **💾 数据持久化**：使用SQLite存储配置和消息数据

## 🚀 安装

### 环境要求

- Python 3.11 或更高版本
- PySide6 (Qt for Python)
- aiofiles (异步文件操作)
- 其他依赖见 `requirements.txt`

### 使用Conda安装

```bash
# 创建新的Conda环境
conda create -n wxauto python=3.11
conda activate wxauto

# 安装依赖
pip install -r requirements.txt
```

## 🎮 使用方法

### 启动程序

**首选方式：**
```
# 直接运行打包好的exe文件
wxauto_mgt.exe
```

**开发方式：**
```bash
# 从项目根目录运行
python wxauto_mgt/main.py
```

### 添加微信实例

1. 点击界面中的"添加实例"按钮
2. 填写微信实例的名称、API地址和API密钥
3. 点击"确定"保存实例配置


### 配置服务平台

1. 找到"服务平台"窗口
2. 点击"添加平台"按钮
3. 选择平台类型（Dify或OpenAI）并填写相关配置
4. 设置消息投递规则

### 设置消息转发规则

1. 切换到"消息转发规则"窗口
2. 点击"添加消息转发规则"按钮
3. 选择监听的消息对象以及对应转发的服务平台
4. 开始接收消息

## 🛠️ 开发

### 项目结构

```
wxauto_mgt/
├── core/              # 核心服务层
│   ├── api_client.py  # WxAuto API客户端
│   ├── message_listener.py  # 消息监听服务
│   ├── message_delivery_service.py  # 消息投递服务
│   └── service_platform.py  # 服务平台接口
├── data/              # 数据持久化层
├── ui/                # 用户界面层
│   ├── components/    # UI组件
│   └── windows/       # 窗口定义
├── utils/             # 工具类
├── web/               # Web管理界面(开发中)
├── docs/              # 文档
└── main.py            # 程序入口点
```

### 自定义开发

1. 核心服务扩展：修改 `core/` 下的模块
2. UI自定义：修改 `ui/` 下的组件
3. 数据模型扩展：修改 `data/` 下的存储类
4. 服务平台扩展：在 `core/service_platform.py` 中添加新的平台支持

## ⚙️ 配置

配置文件位于程序运行目录下的 `data/config.json`，支持以下配置项：

- **实例配置**：管理多个WxAuto实例
- **消息监听设置**：轮询间隔、自动重试
- **服务平台设置**：Dify和OpenAI API配置
- **投递规则设置**：消息投递规则和优先级
- **安全设置**：加密配置和通信安全

## 📄 许可证

[MIT License](LICENSE)

## 🔗 相关链接

- [WxAuto原项目](https://github.com/cluic/wxauto)
- [WxAuto HTTP API](https://github.com/zj591227045/WXAUTO-HTTP-API)
- [Dify平台](https://dify.ai)
- [OpenAI API](https://platform.openai.com/docs/api-reference)
- [PySide6文档](https://doc.qt.io/qtforpython-6/)