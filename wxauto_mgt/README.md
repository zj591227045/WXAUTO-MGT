# WxAuto 管理工具

这是一个用于管理多个微信自动化实例的工具，支持消息监听、存储和处理等功能。

## 目录结构

```
wxauto_mgt/
├── core/                   # 核心功能模块
│   ├── api_client.py      # API客户端，处理与wxauto实例的通信
│   ├── message_listener.py # 消息监听器，管理多实例消息监听
│   └── message_store.py   # 消息存储管理，处理消息的存储和检索
├── data/                   # 数据管理模块
│   ├── db_manager.py      # 数据库管理器，处理SQLite数据库操作
│   ├── config_store.py    # 配置存储管理，处理系统配置
│   └── version_manager.py # 版本管理，处理版本信息
├── utils/                  # 工具模块
│   └── logging.py         # 日志配置，支持多实例日志管理
├── ui/                     # 用户界面模块
│   ├── components/        # UI组件
│   ├── assets/           # 资源文件
│   └── main_window.py    # 主窗口实现
├── tests/                  # 测试目录
│   └── ...                # 各模块的测试文件
├── scripts/               # 脚本和工具
│   └── ...               # 各种辅助脚本
├── requirements.txt       # 项目依赖
└── README.md             # 项目文档
```

## 主要功能

### 多实例管理
- 支持同时管理多个wxauto实例
- 每个实例独立运行，互不影响
- 通过instance_id区分不同实例

### 消息监听
- 支持监听多个微信实例的消息
- 可为每个实例配置多个消息监听器
- 支持按聊天对象分别监听
- 自动清理不活跃的监听器

### 消息存储
- 消息数据持久化到SQLite数据库
- 支持按实例ID、聊天对象查询消息
- 自动清理过期消息
- 支持消息处理状态标记

### 数据管理
- 使用SQLite数据库存储数据
- 支持异步数据库操作
- 内置数据备份和清理机制
- 完善的错误处理和日志记录

### 配置管理
- 支持多实例配置
- 支持加密存储敏感信息
- 配置缓存机制
- 配置版本管理

### 用户界面
- 美观的现代化界面
- 实例状态监控
- 消息管理界面
- 配置管理界面

## 安装和使用

1. 安装依赖：
```bash
pip install -r requirements.txt
```

2. 初始化数据库：
```python
from wxauto_mgt.data.db_manager import db_manager

await db_manager.initialize('path/to/database.db')
```

3. 创建API客户端：
```python
from wxauto_mgt.core.api_client import WxAutoApiClient

client = WxAutoApiClient('http://localhost:8000')
```

4. 启动消息监听：
```python
from wxauto_mgt.core.message_listener import message_listener

await message_listener.start()
```

## 开发说明

### 代码规范
- 使用Python类型注解
- 遵循PEP 8编码规范
- 使用异步编程处理I/O操作
- 完善的错误处理和日志记录

### 测试
- 使用pytest进行单元测试
- 支持异步测试
- 包含代码覆盖率报告

### 日志
- 使用loguru进行日志记录
- 支持不同级别的日志
- 支持多实例日志隔离
- 包含详细的错误追踪

## 注意事项

1. 数据库文件需要定期备份
2. 建议定期清理过期消息和不活跃的监听器
3. 需要合理配置监听器数量，避免资源占用过多
4. API调用需要考虑频率限制
5. 敏感配置信息应使用加密存储

## 贡献指南

1. Fork 项目
2. 创建功能分支
3. 提交更改
4. 创建 Pull Request

## 许可证

MIT License 