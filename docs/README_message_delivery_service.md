# 消息投递服务

## 概述

消息投递服务是wxauto_Mgt项目的一个核心组件，负责从消息监听服务获取未处理的消息，并将其投递到指定的服务平台（如Dify或OpenAI API），然后将服务平台的回复发送回微信联系人。

## 主要功能

1. **消息获取**：从数据库获取未处理的消息
2. **消息合并**：支持将同一聊天对象的多条消息合并为一条投递
3. **规则匹配**：根据投递规则确定消息应该投递到哪个服务平台
4. **消息投递**：将消息投递到相应的服务平台并获取回复
5. **回复发送**：将回复通过WxAuto HTTP API发送回微信联系人
6. **状态管理**：管理消息的投递状态和回复状态

## 支持的服务平台

1. **Dify**：支持Dify平台的消息处理
2. **OpenAI API**：支持OpenAI API的消息处理

## 文件结构

- `wxauto_mgt/core/message_delivery_service.py` - 消息投递服务的主类
- `wxauto_mgt/core/service_platform.py` - 服务平台接口和实现
- `wxauto_mgt/core/service_platform_manager.py` - 服务平台管理器和投递规则管理器
- `wxauto_mgt/ui/components/platform_panel.py` - 服务平台管理面板
- `wxauto_mgt/ui/components/rule_panel.py` - 投递规则管理面板

## 快速开始

### 1. 安装依赖

```bash
pip install aiohttp
```

### 2. 创建数据库表

执行 `docs/message_delivery_service_schema.sql` 中的SQL语句，创建必要的数据库表和字段。

### 3. 集成到项目

按照 `docs/message_delivery_service_integration_guide.md` 中的说明，将消息投递服务集成到项目中。

### 4. 配置服务平台

使用UI界面或API添加服务平台：

```python
# 添加Dify平台
platform_id = await platform_manager.register_platform(
    "dify",
    "Dify平台",
    {
        "api_base": "https://api.dify.ai/v1",
        "api_key": "your_dify_api_key"
    }
)

# 添加OpenAI平台
platform_id = await platform_manager.register_platform(
    "openai",
    "OpenAI平台",
    {
        "api_key": "your_openai_api_key",
        "model": "gpt-3.5-turbo"
    }
)
```

### 5. 配置投递规则

使用UI界面或API添加投递规则：

```python
# 添加投递规则
rule_id = await rule_manager.add_rule(
    name="默认规则",
    instance_id="*",  # 所有实例
    chat_pattern="*",  # 所有聊天对象
    platform_id=platform_id,
    priority=0
)
```

### 6. 启动服务

```python
# 初始化消息投递服务
await message_delivery_service.initialize()

# 启动消息投递服务
await message_delivery_service.start()
```

## 配置选项

### 消息投递服务配置

- `poll_interval` - 轮询间隔（秒）
- `batch_size` - 每次处理的消息数量
- `merge_messages` - 是否合并消息
- `merge_window` - 消息合并时间窗口（秒）

### Dify平台配置

- `api_base` - API基础URL
- `api_key` - API密钥
- `conversation_id` - 会话ID（可选）
- `user_id` - 用户ID（可选）

### OpenAI API平台配置

- `api_base` - API基础URL
- `api_key` - API密钥
- `model` - 模型名称
- `temperature` - 温度参数
- `system_prompt` - 系统提示词
- `max_tokens` - 最大生成令牌数

## 投递规则配置

- `name` - 规则名称
- `instance_id` - 实例ID，可以是具体的实例ID或者 `*` 表示所有实例
- `chat_pattern` - 聊天对象匹配模式
  - 精确匹配：直接填写聊天对象名称
  - 通配符匹配：使用 `*` 表示匹配所有聊天对象
  - 正则表达式匹配：使用 `regex:` 前缀，例如 `regex:^群聊.*`
- `platform_id` - 服务平台ID
- `priority` - 规则优先级，数字越大优先级越高

## 使用示例

### 基本使用

```python
# 初始化和启动服务
await message_delivery_service.initialize()
await message_delivery_service.start()

# 手动处理消息
message = {
    "message_id": "test_message_id",
    "instance_id": "test_instance",
    "chat_name": "测试聊天",
    "content": "你好，这是一条测试消息",
    "sender": "测试用户",
    "create_time": int(time.time())
}
await message_delivery_service.process_message(message)

# 停止服务
await message_delivery_service.stop()
```

### 服务平台管理

```python
# 注册平台
platform_id = await platform_manager.register_platform(
    "openai",
    "OpenAI平台",
    {
        "api_key": "your_openai_api_key",
        "model": "gpt-3.5-turbo"
    }
)

# 获取平台
platform = await platform_manager.get_platform(platform_id)

# 更新平台
await platform_manager.update_platform(
    platform_id,
    "OpenAI平台（更新）",
    {
        "api_key": "your_new_openai_api_key",
        "model": "gpt-4"
    }
)

# 删除平台
await platform_manager.delete_platform(platform_id)
```

### 投递规则管理

```python
# 添加规则
rule_id = await rule_manager.add_rule(
    name="测试规则",
    instance_id="test_instance",
    chat_pattern="测试聊天",
    platform_id=platform_id,
    priority=10
)

# 获取规则
rule = await rule_manager.get_rule(rule_id)

# 更新规则
await rule_manager.update_rule(
    rule_id,
    "测试规则（更新）",
    "test_instance",
    "测试聊天",
    platform_id,
    20
)

# 删除规则
await rule_manager.delete_rule(rule_id)
```

## 测试

使用 `docs/test_message_delivery.py` 脚本测试消息投递服务的功能：

```bash
python docs/test_message_delivery.py
```

## 扩展开发

### 添加新的服务平台

1. 在 `wxauto_mgt/core/service_platform.py` 中创建新的服务平台类，继承自 `ServicePlatform` 基类
2. 实现必要的方法：`initialize`、`process_message`、`test_connection` 和 `get_type`
3. 在 `create_platform` 函数中添加对新平台类型的支持

### 增强消息处理功能

可以通过以下方式增强消息处理功能：

1. 添加消息过滤功能
2. 添加消息转换功能
3. 添加消息历史记录功能
4. 添加多轮对话功能

## 常见问题

### 消息投递失败

如果消息投递失败，可能有以下原因：

1. 服务平台配置错误，例如API密钥不正确
2. 网络连接问题
3. 服务平台API限制或错误

### 消息回复失败

如果消息回复失败，可能有以下原因：

1. 微信API客户端连接问题
2. 微信实例不在线
3. 聊天对象不存在或无法发送消息

### 规则匹配问题

如果规则匹配不正确，可以检查以下方面：

1. 规则优先级设置是否合理
2. 聊天对象匹配模式是否正确
3. 实例ID是否匹配

## 更多信息

详细的集成指南和API文档，请参考：

- `docs/message_delivery_service_integration_guide.md` - 集成指南
- `docs/message_delivery_service_plan.md` - 设计文档
- `docs/message_delivery_service_schema.sql` - 数据库表结构
