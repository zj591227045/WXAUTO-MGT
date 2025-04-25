# WxAuto管理程序

WxAuto管理程序是一个基于Python的应用程序，作为WxAuto HTTP API的客户端，用于管理多个WxAuto实例，提供微信消息监听、状态监控和第三方服务集成功能。

## 主要功能

- **多实例管理**：同时管理多个不同服务器上的WxAuto HTTP API实例
- **消息监听服务**：自动监听微信消息并转发到第三方服务
- **状态监控**：监控WxAuto实例的运行状态和性能指标
- **第三方集成**：支持ASTRBot平台适配器和其他LLM服务集成
- **用户友好界面**：提供简洁美观的UI界面，支持各种管理操作

## 技术栈

- Python 3.11+
- PySide6（UI框架）
- SQLite（数据存储）
- asyncio和aiohttp（异步处理）

## 安装和运行

### 环境要求

- Python 3.11 或更高版本
- Conda 环境管理（推荐）

### 安装步骤

1. 克隆仓库

```bash
git clone https://github.com/yourusername/wxauto_mgt.git
cd wxauto_mgt
```

2. 创建并激活conda环境

```bash
conda create -n wxauto_mgt python=3.11
conda activate wxauto_mgt
```

3. 安装依赖

```bash
pip install -r requirements.txt
```

4. 运行程序

```bash
python main.py
```

## 项目结构

```
wxauto_mgt/
├── app/                 # 应用程序代码
│   ├── core/            # 核心服务层
│   ├── api/             # 接口层
│   ├── ui/              # UI界面层
│   ├── data/            # 数据持久层
│   └── utils/           # 工具函数
├── tests/               # 单元测试和集成测试
├── config/              # 配置文件
├── docs/                # 文档
├── main.py              # 程序入口
└── README.md            # 项目说明
```

## 许可证

[MIT](LICENSE) 