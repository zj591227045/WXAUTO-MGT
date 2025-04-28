# 消息投递服务集成指南

## 1. 概述

本文档详细说明了如何将消息投递服务集成到现有的wxauto_Mgt项目中。消息投递服务负责从消息监听服务获取未处理的消息，并将其投递到指定的服务平台（如Dify或OpenAI API），然后将服务平台的回复发送回微信联系人。

## 2. 文件结构

消息投递服务由以下文件组成：

1. `wxauto_mgt/core/message_delivery_service.py` - 消息投递服务的主类
2. `wxauto_mgt/core/service_platform.py` - 服务平台接口和实现
3. `wxauto_mgt/core/service_platform_manager.py` - 服务平台管理器和投递规则管理器

## 3. 数据库表结构

消息投递服务需要以下数据库表：

1. `service_platforms` - 存储服务平台配置
2. `delivery_rules` - 存储消息投递规则
3. 在现有的 `messages` 表中添加投递相关字段

可以使用 `docs/message_delivery_service_schema.sql` 中的SQL语句创建这些表。

## 4. 集成步骤

### 4.1 复制文件

将以下文件复制到项目中：

1. 将 `docs/service_platform_interface.py` 复制到 `wxauto_mgt/core/service_platform.py`
2. 将 `docs/service_platform_manager.py` 复制到 `wxauto_mgt/core/service_platform_manager.py`
3. 将 `docs/message_delivery_service.py` 复制到 `wxauto_mgt/core/message_delivery_service.py`

### 4.2 创建数据库表

执行 `docs/message_delivery_service_schema.sql` 中的SQL语句，创建必要的数据库表和字段。

### 4.3 修改项目启动流程

在项目启动流程中添加消息投递服务的初始化和启动代码。修改 `wxauto_mgt/main.py` 文件：

```python
# 导入消息投递服务
from wxauto_mgt.core.message_delivery_service import message_delivery_service

async def init_services():
    """初始化服务"""
    # 初始化数据库
    await db_manager.initialize()
    
    # 初始化实例管理器
    await instance_manager.initialize()
    
    # 初始化消息监听服务
    await message_listener.initialize()
    
    # 初始化消息投递服务
    await message_delivery_service.initialize()
    
    # 启动消息监听服务
    await message_listener.start()
    
    # 启动消息投递服务
    await message_delivery_service.start()
    
    return True

async def cleanup_services():
    """清理服务"""
    # 停止消息监听服务
    await message_listener.stop()
    
    # 停止消息投递服务
    await message_delivery_service.stop()
    
    # 关闭数据库连接
    await db_manager.close()
```

### 4.4 添加UI界面

在UI界面中添加服务平台和投递规则的管理功能。可以创建以下文件：

1. `wxauto_mgt/ui/components/platform_panel.py` - 服务平台管理面板
2. `wxauto_mgt/ui/components/rule_panel.py` - 投递规则管理面板
3. `wxauto_mgt/ui/dialogs/platform_dialog.py` - 服务平台编辑对话框
4. `wxauto_mgt/ui/dialogs/rule_dialog.py` - 投递规则编辑对话框

然后在主界面中添加这些面板的入口。

## 5. 配置说明

消息投递服务的配置项包括：

1. `poll_interval` - 轮询间隔（秒）
2. `batch_size` - 每次处理的消息数量
3. `merge_messages` - 是否合并消息
4. `merge_window` - 消息合并时间窗口（秒）

可以在初始化消息投递服务时设置这些配置项：

```python
# 创建消息投递服务实例
message_delivery_service = MessageDeliveryService(
    poll_interval=5,
    batch_size=10,
    merge_messages=True,
    merge_window=60
)
```

## 6. 服务平台配置

### 6.1 Dify平台

Dify平台需要以下配置项：

1. `api_base` - API基础URL，例如 `https://api.dify.ai/v1`
2. `api_key` - API密钥
3. `conversation_id` - 会话ID（可选）
4. `user_id` - 用户ID（可选）

### 6.2 OpenAI API平台

OpenAI API平台需要以下配置项：

1. `api_base` - API基础URL，默认为 `https://api.openai.com/v1`
2. `api_key` - API密钥
3. `model` - 模型名称，默认为 `gpt-3.5-turbo`
4. `temperature` - 温度参数，默认为 0.7
5. `system_prompt` - 系统提示词，默认为 `你是一个有用的助手。`
6. `max_tokens` - 最大生成令牌数，默认为 1000

## 7. 投递规则配置

投递规则包括以下配置项：

1. `name` - 规则名称
2. `instance_id` - 实例ID，可以是具体的实例ID或者 `*` 表示所有实例
3. `chat_pattern` - 聊天对象匹配模式，支持以下格式：
   - 精确匹配：直接填写聊天对象名称
   - 通配符匹配：使用 `*` 表示匹配所有聊天对象
   - 正则表达式匹配：使用 `regex:` 前缀，例如 `regex:^群聊.*`
4. `platform_id` - 服务平台ID
5. `priority` - 规则优先级，数字越大优先级越高

## 8. 测试方法

### 8.1 测试服务平台连接

可以使用以下代码测试服务平台连接：

```python
# 测试Dify平台
dify_platform = DifyPlatform(
    platform_id="dify_test",
    name="Dify测试",
    config={
        "api_base": "https://api.dify.ai/v1",
        "api_key": "your_api_key"
    }
)
result = await dify_platform.test_connection()
print(result)

# 测试OpenAI API平台
openai_platform = OpenAIPlatform(
    platform_id="openai_test",
    name="OpenAI测试",
    config={
        "api_key": "your_api_key"
    }
)
result = await openai_platform.test_connection()
print(result)
```

### 8.2 测试消息投递

可以使用以下代码测试消息投递：

```python
# 创建测试消息
test_message = {
    "message_id": "test_message_id",
    "instance_id": "test_instance_id",
    "chat_name": "测试聊天",
    "content": "你好，这是一条测试消息",
    "sender": "测试用户",
    "create_time": int(time.time())
}

# 测试消息投递
result = await message_delivery_service.process_message(test_message)
print(result)
```

## 9. 常见问题

### 9.1 消息投递失败

如果消息投递失败，可能有以下原因：

1. 服务平台配置错误，例如API密钥不正确
2. 网络连接问题
3. 服务平台API限制或错误

可以查看日志了解具体错误信息。

### 9.2 消息回复失败

如果消息回复失败，可能有以下原因：

1. 微信API客户端连接问题
2. 微信实例不在线
3. 聊天对象不存在或无法发送消息

可以查看日志了解具体错误信息。

### 9.3 规则匹配问题

如果规则匹配不正确，可以检查以下方面：

1. 规则优先级设置是否合理
2. 聊天对象匹配模式是否正确
3. 实例ID是否匹配

## 10. 扩展开发

### 10.1 添加新的服务平台

要添加新的服务平台，需要执行以下步骤：

1. 在 `wxauto_mgt/core/service_platform.py` 中创建新的服务平台类，继承自 `ServicePlatform` 基类
2. 实现必要的方法：`initialize`、`process_message`、`test_connection` 和 `get_type`
3. 在 `create_platform` 函数中添加对新平台类型的支持

例如，添加对Claude API的支持：

```python
class ClaudeAPIPlatform(ServicePlatform):
    """Claude API平台实现"""
    
    def __init__(self, platform_id: str, name: str, config: Dict[str, Any]):
        super().__init__(platform_id, name, config)
        self.api_base = config.get('api_base', 'https://api.anthropic.com')
        self.api_key = config.get('api_key', '')
        self.model = config.get('model', 'claude-2')
        # 其他配置...
    
    async def initialize(self) -> bool:
        # 实现初始化逻辑
        pass
    
    async def process_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        # 实现消息处理逻辑
        pass
    
    async def test_connection(self) -> Dict[str, Any]:
        # 实现连接测试逻辑
        pass
    
    def get_type(self) -> str:
        return "claude"

# 在create_platform函数中添加支持
def create_platform(platform_type: str, platform_id: str, name: str, config: Dict[str, Any]) -> Optional[ServicePlatform]:
    if platform_type == "dify":
        return DifyPlatform(platform_id, name, config)
    elif platform_type == "openai":
        return OpenAIPlatform(platform_id, name, config)
    elif platform_type == "claude":  # 添加新平台支持
        return ClaudeAPIPlatform(platform_id, name, config)
    else:
        logger.error(f"不支持的平台类型: {platform_type}")
        return None
```

### 10.2 增强消息处理功能

可以通过以下方式增强消息处理功能：

1. 添加消息过滤功能，例如根据消息内容或发送者过滤消息
2. 添加消息转换功能，例如将图片消息转换为文本描述
3. 添加消息历史记录功能，在处理消息时考虑历史消息上下文
4. 添加多轮对话功能，实现基于会话的多轮对话处理

## 11. 日志和监控

消息投递服务使用Python标准库的logging模块记录日志。可以通过以下方式配置日志：

```python
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('message_delivery.log'),
        logging.StreamHandler()
    ]
)

# 设置消息投递服务的日志级别
logging.getLogger('wxauto_mgt.core.message_delivery_service').setLevel(logging.DEBUG)
logging.getLogger('wxauto_mgt.core.service_platform').setLevel(logging.DEBUG)
logging.getLogger('wxauto_mgt.core.service_platform_manager').setLevel(logging.DEBUG)
```

可以通过监控以下指标来评估服务的性能和健康状况：

1. 消息处理速率：每秒处理的消息数量
2. 消息处理延迟：从消息创建到处理完成的时间
3. 投递成功率：成功投递的消息比例
4. 回复成功率：成功回复的消息比例
5. 错误率：处理过程中出现错误的消息比例
