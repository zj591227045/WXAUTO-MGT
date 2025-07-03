# 只为记账平台集成指南

## 概述

本文档介绍如何在WXAUTO-MGT项目中集成和使用只为记账平台功能。通过此集成，您可以实现微信消息的自动记账功能。

## 功能特性

### 核心功能
- **智能记账**: 基于消息内容的智能记账分析
- **多账本支持**: 支持多个记账账本的管理
- **自动登录**: 支持token自动刷新和管理
- **错误处理**: 完善的错误处理和重试机制
- **统计分析**: 提供记账成功率、金额统计等数据

### 技术特性
- **异步处理**: 基于aiohttp的异步HTTP请求
- **数据持久化**: 记账记录存储到SQLite数据库
- **Web管理**: 通过Web界面管理记账平台配置
- **API接口**: 提供完整的REST API接口

## 安装和配置

### 1. 数据库初始化

首先运行数据库初始化脚本：

```bash
python wxauto_mgt/scripts/add_accounting_tables.py
```

### 2. 创建记账平台

通过Web API创建只为记账平台：

```bash
curl -X POST "http://localhost:8000/api/platforms/zhiweijz" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "我的记账平台",
    "server_url": "https://app.zhiweijz.com",
    "username": "your_email@example.com",
    "password": "your_password",
    "account_book_id": "your_account_book_id",
    "account_book_name": "个人账本",
    "auto_login": true,
    "enabled": true
  }'
```

### 3. 配置消息投递规则

创建消息投递规则，将特定聊天的消息转发到记账平台：

```bash
curl -X POST "http://localhost:8000/api/rules" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "记账规则",
    "instance_id": "your_instance_id",
    "chat_pattern": "记账群",
    "platform_id": "zhiweijz_platform_id",
    "priority": 1,
    "enabled": true
  }'
```

## 使用方法

### 1. 基本记账

在配置的微信群聊中发送包含金额信息的消息：

```
午餐 麦当劳 35元
地铁费 5元
咖啡 星巴克 28元
```

系统会自动识别并调用只为记账API进行记账。

### 2. 查看记账记录

通过Web API查看记账记录：

```bash
# 获取所有记账记录
curl "http://localhost:8000/api/accounting/records"

# 获取特定平台的记账记录
curl "http://localhost:8000/api/accounting/records?platform_id=zhiweijz_platform_id"

# 获取成功的记账记录
curl "http://localhost:8000/api/accounting/records?success_only=true"
```

### 3. 查看统计信息

```bash
# 获取记账统计信息
curl "http://localhost:8000/api/accounting/stats"

# 获取特定平台的统计信息
curl "http://localhost:8000/api/accounting/stats?platform_id=zhiweijz_platform_id"
```

## API接口文档

### 平台管理

#### 创建只为记账平台
- **URL**: `POST /api/platforms/zhiweijz`
- **参数**:
  - `name`: 平台名称
  - `server_url`: 只为记账服务器地址
  - `username`: 用户名
  - `password`: 密码
  - `account_book_id`: 账本ID（可选）
  - `account_book_name`: 账本名称（可选）
  - `auto_login`: 是否自动登录（默认true）
  - `enabled`: 是否启用（默认true）

#### 测试连接
- **URL**: `POST /api/accounting/test`
- **参数**:
  - `server_url`: 服务器地址
  - `username`: 用户名
  - `password`: 密码
  - `account_book_id`: 账本ID（可选）

### 记账记录

#### 获取记账记录
- **URL**: `GET /api/accounting/records`
- **参数**:
  - `platform_id`: 平台ID（可选）
  - `instance_id`: 实例ID（可选）
  - `limit`: 返回数量限制（默认50）
  - `offset`: 偏移量（默认0）
  - `success_only`: 仅成功记录（可选）

#### 获取统计信息
- **URL**: `GET /api/accounting/stats`
- **参数**:
  - `platform_id`: 平台ID（可选）

## 数据库结构

### accounting_records 表

记账记录表，存储所有的记账操作记录：

```sql
CREATE TABLE accounting_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform_id TEXT NOT NULL,
    message_id TEXT,
    instance_id TEXT,
    chat_name TEXT,
    sender_name TEXT,
    description TEXT NOT NULL,
    amount REAL,
    category TEXT,
    account_book_id TEXT,
    account_book_name TEXT,
    success INTEGER NOT NULL,
    error_message TEXT,
    api_response TEXT,
    processing_time REAL,
    create_time INTEGER NOT NULL
);
```

### accounting_stats 视图

记账统计视图，提供汇总统计信息：

```sql
CREATE VIEW accounting_stats AS
SELECT 
    platform_id,
    COUNT(*) as total_records,
    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful_records,
    SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failed_records,
    ROUND(AVG(CASE WHEN success = 1 THEN processing_time END), 3) as avg_processing_time,
    SUM(CASE WHEN success = 1 AND amount IS NOT NULL THEN amount ELSE 0 END) as total_amount,
    MIN(create_time) as first_record_time,
    MAX(create_time) as last_record_time
FROM accounting_records
GROUP BY platform_id;
```

## 配置说明

### 平台配置参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| server_url | string | 是 | - | 只为记账服务器地址 |
| username | string | 是 | - | 登录用户名 |
| password | string | 是 | - | 登录密码 |
| account_book_id | string | 否 | "" | 账本ID |
| account_book_name | string | 否 | "" | 账本名称 |
| auto_login | boolean | 否 | true | 是否自动登录 |
| token_refresh_interval | integer | 否 | 300 | Token刷新间隔（秒） |
| request_timeout | integer | 否 | 30 | 请求超时时间（秒） |
| max_retries | integer | 否 | 3 | 最大重试次数 |

## 故障排除

### 常见问题

#### 1. 登录失败
- 检查服务器地址是否正确
- 验证用户名和密码
- 确认网络连接正常

#### 2. 记账失败
- 检查账本ID是否正确
- 验证消息格式是否符合要求
- 查看错误日志获取详细信息

#### 3. Token过期
- 系统会自动刷新Token
- 如果自动刷新失败，检查登录凭据

### 日志查看

查看系统日志获取详细的错误信息：

```bash
# 查看最近的日志
curl "http://localhost:8000/api/logs?limit=100"

# 查看特定时间后的日志
curl "http://localhost:8000/api/logs?since=1640995200"
```

## 开发指南

### 扩展记账平台

如果需要支持其他记账平台，可以参考只为记账平台的实现：

1. 创建新的异步管理器类（继承或参考`AsyncAccountingManager`）
2. 创建新的平台类（继承`ServicePlatform`）
3. 在`create_platform`函数中添加新平台类型
4. 添加相应的API接口

### 自定义记账逻辑

可以通过修改`ZhiWeiJZPlatform.process_message`方法来自定义记账逻辑：

```python
async def process_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
    # 自定义消息预处理
    content = self.preprocess_message(message.get('content', ''))
    
    # 调用记账API
    success, result = await self.accounting_manager.smart_accounting(
        description=content,
        sender_name=message.get('sender', '')
    )
    
    # 自定义响应处理
    return self.format_response(success, result)
```

## 安全注意事项

1. **密码保护**: 密码在数据库中应该加密存储
2. **API安全**: 确保API接口有适当的认证和授权
3. **网络安全**: 使用HTTPS连接到只为记账服务器
4. **数据备份**: 定期备份记账记录数据

## 更新日志

### v1.0.0 (2024-06-24)
- 初始版本发布
- 支持只为记账平台集成
- 提供完整的Web API接口
- 实现记账记录存储和统计
