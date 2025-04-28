# 消息投递服务规划文档

## 1. 概述

消息投递服务是wxauto_Mgt项目的一个核心组件，负责从消息监听服务获取未处理的消息，并将其投递到指定的服务平台（如Dify或OpenAI API），然后将服务平台的回复发送回微信联系人。本文档详细说明了消息投递服务的设计、实现和集成方案。

## 2. 系统架构

### 2.1 整体架构

消息投递服务在整个系统中的位置如下：

```
微信客户端 <--> WxAuto HTTP API <--> 消息监听服务 <--> 消息投递服务 <--> 服务平台(Dify/OpenAI)
                                          |                 |
                                          v                 v
                                       数据库 <--------> 消息规则管理
```

### 2.2 核心组件

消息投递服务由以下核心组件组成：

1. **MessageDeliveryService**: 消息投递服务的主类，负责协调各组件工作
2. **ServicePlatformManager**: 服务平台管理器，负责管理不同的服务平台
3. **DeliveryRuleManager**: 投递规则管理器，负责管理消息投递规则
4. **ServicePlatform**: 服务平台接口，定义了服务平台的标准接口
   - DifyPlatform: Dify平台实现
   - OpenAIPlatform: OpenAI API平台实现

## 3. 功能详细设计

### 3.1 消息投递服务 (MessageDeliveryService)

#### 3.1.1 主要功能

- 定期从消息监听服务获取未处理的消息
- 根据投递规则确定消息应该投递到哪个服务平台
- 将消息投递到相应的服务平台并获取回复
- 将回复通过WxAuto HTTP API发送回微信联系人
- 将消息标记为已处理

#### 3.1.2 关键方法

```python
class MessageDeliveryService:
    def __init__(self, poll_interval=5):
        # 初始化服务
        
    async def start(self):
        # 启动服务
        
    async def stop(self):
        # 停止服务
        
    async def _message_poll_loop(self):
        # 消息轮询循环
        
    async def process_message(self, message):
        # 处理单条消息
        
    async def deliver_message(self, message, platform):
        # 投递消息到指定平台
        
    async def send_reply(self, message, reply):
        # 发送回复
        
    async def mark_as_processed(self, message_id):
        # 标记消息为已处理
```

### 3.2 服务平台管理器 (ServicePlatformManager)

#### 3.2.1 主要功能

- 管理多个服务平台实例
- 提供服务平台的注册、获取和删除功能
- 保存和加载服务平台配置

#### 3.2.2 关键方法

```python
class ServicePlatformManager:
    def __init__(self):
        # 初始化管理器
        
    async def initialize(self):
        # 初始化，从数据库加载平台配置
        
    async def register_platform(self, platform_config):
        # 注册新的服务平台
        
    async def get_platform(self, platform_id):
        # 获取指定ID的服务平台
        
    async def get_all_platforms(self):
        # 获取所有服务平台
        
    async def update_platform(self, platform_id, config):
        # 更新服务平台配置
        
    async def delete_platform(self, platform_id):
        # 删除服务平台
        
    async def save_config(self):
        # 保存配置到数据库
```

### 3.3 投递规则管理器 (DeliveryRuleManager)

#### 3.3.1 主要功能

- 管理消息投递规则
- 根据规则匹配消息应该投递到哪个服务平台
- 提供规则的添加、修改和删除功能

#### 3.3.2 关键方法

```python
class DeliveryRuleManager:
    def __init__(self):
        # 初始化管理器
        
    async def initialize(self):
        # 初始化，从数据库加载规则
        
    async def add_rule(self, rule):
        # 添加新规则
        
    async def update_rule(self, rule_id, rule):
        # 更新规则
        
    async def delete_rule(self, rule_id):
        # 删除规则
        
    async def get_rule(self, rule_id):
        # 获取指定规则
        
    async def get_all_rules(self):
        # 获取所有规则
        
    async def match_rule(self, message):
        # 匹配消息应该使用哪个规则
        
    async def save_rules(self):
        # 保存规则到数据库
```

### 3.4 服务平台接口 (ServicePlatform)

#### 3.4.1 基础接口

```python
class ServicePlatform(ABC):
    @abstractmethod
    async def process_message(self, message):
        # 处理消息并返回回复
        pass
        
    @abstractmethod
    async def initialize(self):
        # 初始化平台
        pass
        
    @abstractmethod
    async def test_connection(self):
        # 测试连接是否正常
        pass
```

#### 3.4.2 Dify平台实现

```python
class DifyPlatform(ServicePlatform):
    def __init__(self, config):
        # 初始化Dify平台
        
    async def process_message(self, message):
        # 处理消息并返回回复
        
    async def initialize(self):
        # 初始化平台
        
    async def test_connection(self):
        # 测试连接是否正常
```

#### 3.4.3 OpenAI API平台实现

```python
class OpenAIPlatform(ServicePlatform):
    def __init__(self, config):
        # 初始化OpenAI平台
        
    async def process_message(self, message):
        # 处理消息并返回回复
        
    async def initialize(self):
        # 初始化平台
        
    async def test_connection(self):
        # 测试连接是否正常
```

## 4. 数据库设计

### 4.1 服务平台表 (service_platforms)

| 字段名 | 类型 | 说明 |
|-------|------|------|
| id | INTEGER | 主键 |
| platform_id | TEXT | 平台唯一标识 |
| name | TEXT | 平台名称 |
| type | TEXT | 平台类型（dify/openai） |
| config | TEXT | 平台配置（JSON格式） |
| enabled | INTEGER | 是否启用 |
| create_time | INTEGER | 创建时间 |
| update_time | INTEGER | 更新时间 |

### 4.2 投递规则表 (delivery_rules)

| 字段名 | 类型 | 说明 |
|-------|------|------|
| id | INTEGER | 主键 |
| rule_id | TEXT | 规则唯一标识 |
| name | TEXT | 规则名称 |
| instance_id | TEXT | 微信实例ID |
| chat_pattern | TEXT | 聊天对象匹配模式 |
| platform_id | TEXT | 服务平台ID |
| priority | INTEGER | 规则优先级 |
| enabled | INTEGER | 是否启用 |
| create_time | INTEGER | 创建时间 |
| update_time | INTEGER | 更新时间 |

### 4.3 消息表扩展

在现有的messages表中添加以下字段：

| 字段名 | 类型 | 说明 |
|-------|------|------|
| delivery_status | INTEGER | 投递状态（0未投递，1已投递，2投递失败） |
| delivery_time | INTEGER | 投递时间 |
| platform_id | TEXT | 处理该消息的平台ID |
| reply_content | TEXT | 平台回复内容 |
| reply_status | INTEGER | 回复状态（0未回复，1已回复，2回复失败） |
| reply_time | INTEGER | 回复时间 |

## 5. 消息处理流程

### 5.1 基本流程

1. 消息投递服务定期从数据库获取未处理的消息
2. 对于每条消息，根据投递规则确定应该投递到哪个服务平台
3. 将消息投递到相应的服务平台并获取回复
4. 将回复通过WxAuto HTTP API发送回微信联系人
5. 将消息标记为已处理

### 5.2 消息合并处理

消息投递服务支持两种消息处理模式：

1. **逐条处理**：每条消息单独投递和处理
2. **合并处理**：将同一聊天对象的多条消息合并为一条投递

合并处理的实现方式：

```python
async def merge_messages(self, messages):
    # 按聊天对象分组
    grouped_messages = {}
    for msg in messages:
        chat_key = f"{msg['instance_id']}_{msg['chat_name']}"
        if chat_key not in grouped_messages:
            grouped_messages[chat_key] = []
        grouped_messages[chat_key].append(msg)
    
    # 合并消息
    merged_results = []
    for chat_key, msgs in grouped_messages.items():
        if len(msgs) == 1:
            merged_results.append(msgs[0])
        else:
            # 按时间排序
            sorted_msgs = sorted(msgs, key=lambda x: x['create_time'])
            
            # 合并内容
            merged_content = "\n".join([
                f"{msg['sender'] or '我'}: {msg['content']}" 
                for msg in sorted_msgs
            ])
            
            # 创建合并后的消息
            merged_msg = sorted_msgs[-1].copy()  # 使用最新消息作为基础
            merged_msg['content'] = merged_content
            merged_msg['merged'] = True
            merged_msg['merged_count'] = len(sorted_msgs)
            merged_msg['merged_ids'] = [msg['message_id'] for msg in sorted_msgs]
            
            merged_results.append(merged_msg)
    
    return merged_results
```

## 6. 服务平台接口实现

### 6.1 Dify平台接口

Dify平台接口通过HTTP API与Dify服务进行通信，主要包括以下功能：

1. 初始化连接并验证API密钥
2. 将消息转换为Dify支持的格式
3. 发送消息并获取回复
4. 处理错误和异常情况

```python
async def process_message(self, message):
    try:
        # 构建请求数据
        request_data = {
            "inputs": {},
            "query": message['content'],
            "response_mode": "blocking",
            "user": message['sender'] or "user"
        }
        
        # 发送请求
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.api_base}/chat-messages",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json=request_data
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Dify API错误: {response.status}, {error_text}")
                    return {"error": f"API错误: {response.status}"}
                
                result = await response.json()
                return {
                    "content": result.get("answer", ""),
                    "raw_response": result
                }
    except Exception as e:
        logger.error(f"处理消息时出错: {e}")
        return {"error": str(e)}
```

### 6.2 OpenAI API平台接口

OpenAI API平台接口通过HTTP API与OpenAI服务进行通信，主要包括以下功能：

1. 初始化连接并验证API密钥
2. 将消息转换为OpenAI支持的格式
3. 发送消息并获取回复
4. 处理错误和异常情况

```python
async def process_message(self, message):
    try:
        # 构建消息历史
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": message['content']}
        ]
        
        # 发送请求
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": self.temperature
                }
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"OpenAI API错误: {response.status}, {error_text}")
                    return {"error": f"API错误: {response.status}"}
                
                result = await response.json()
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                return {
                    "content": content,
                    "raw_response": result
                }
    except Exception as e:
        logger.error(f"处理消息时出错: {e}")
        return {"error": str(e)}
```

## 7. 集成与部署

### 7.1 与现有系统的集成

消息投递服务将作为wxauto_Mgt项目的一个模块进行集成，主要涉及以下方面：

1. 在项目启动时初始化并启动消息投递服务
2. 在UI界面中添加服务平台和投递规则的管理功能
3. 在消息监听服务中添加对消息投递服务的支持

### 7.2 配置项

消息投递服务的配置项包括：

1. 轮询间隔：从数据库获取未处理消息的时间间隔
2. 批处理大小：每次处理的最大消息数量
3. 消息合并设置：是否启用消息合并，合并的时间窗口等
4. 重试设置：投递失败时的重试次数和间隔
5. 日志级别：日志记录的详细程度

### 7.3 部署步骤

1. 创建数据库表：service_platforms和delivery_rules
2. 修改现有的messages表，添加投递相关字段
3. 实现消息投递服务的各个组件
4. 在项目启动流程中添加消息投递服务的初始化和启动
5. 在UI界面中添加服务平台和投递规则的管理功能

## 8. 测试计划

### 8.1 单元测试

1. 服务平台接口测试：测试Dify和OpenAI API接口的功能
2. 投递规则匹配测试：测试规则匹配逻辑的正确性
3. 消息合并测试：测试消息合并功能的正确性

### 8.2 集成测试

1. 消息投递流程测试：测试从获取消息到发送回复的完整流程
2. 多平台并行处理测试：测试多个服务平台同时处理消息的情况
3. 错误处理和恢复测试：测试各种错误情况下的处理和恢复机制

### 8.3 性能测试

1. 高并发测试：测试系统在高并发情况下的性能
2. 长时间运行测试：测试系统在长时间运行情况下的稳定性
3. 资源占用测试：测试系统在不同负载下的资源占用情况

## 9. 安全考虑

1. API密钥保护：服务平台的API密钥应该加密存储
2. 消息内容保护：敏感消息内容应该加密存储
3. 访问控制：对服务平台和投递规则的管理应该有适当的访问控制
4. 错误处理：系统应该能够优雅地处理各种错误情况，避免敏感信息泄露

## 10. 未来扩展

1. 支持更多服务平台：如Azure OpenAI、Claude等
2. 支持更复杂的投递规则：如基于消息内容的规则匹配
3. 支持消息历史记录：在处理消息时考虑历史消息上下文
4. 支持多轮对话：实现基于会话的多轮对话处理
5. 支持消息队列：使用专业的消息队列系统提高可靠性和性能
