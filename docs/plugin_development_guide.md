# WXAUTO-MGT 插件开发指南

## 概述

WXAUTO-MGT 提供了一个强大的插件系统，允许开发者创建自定义的服务平台插件来扩展系统功能。本指南将帮助您了解如何开发、测试和发布插件。

## 插件系统架构

### 核心组件

1. **插件管理器 (PluginManager)**: 负责插件的生命周期管理
2. **插件注册表 (PluginRegistry)**: 管理已注册的插件
3. **插件加载器 (PluginLoader)**: 动态加载插件模块
4. **配置管理器 (PluginConfigManager)**: 管理插件配置
5. **安全管理器 (PluginSecurityManager)**: 控制插件权限和安全

### 插件类型

- **服务平台插件**: 实现与外部服务的集成（如AI平台、记账服务等）
- **消息处理插件**: 处理特定类型的消息
- **工具插件**: 提供辅助功能

## 快速开始

### 1. 创建插件目录结构

```
my_plugin/
├── plugin.json          # 插件清单文件
├── main.py             # 插件主文件
├── config.py           # 配置相关（可选）
├── utils.py            # 工具函数（可选）
└── README.md           # 插件说明（可选）
```

### 2. 编写插件清单 (plugin.json)

```json
{
  "plugin_id": "my_awesome_plugin",
  "name": "我的超棒插件",
  "version": "1.0.0",
  "description": "这是一个示例插件，展示如何开发WXAUTO-MGT插件",
  "author": "您的名字",
  "homepage": "https://github.com/yourname/my-awesome-plugin",
  "license": "MIT",
  "entry_point": "main.py",
  "class_name": "MyAwesomePlugin",
  "dependencies": [
    "aiohttp>=3.8.0",
    "requests>=2.28.0"
  ],
  "min_wxauto_version": "1.0.0",
  "python_version": "3.8",
  "supported_os": ["Windows", "Linux", "Darwin"],
  "permissions": [
    "network.http",
    "config.read",
    "config.write",
    "message.process"
  ],
  "tags": ["ai", "chat", "demo"],
  "config_schema": {
    "type": "object",
    "properties": {
      "api_key": {
        "type": "string",
        "title": "API密钥",
        "description": "服务API密钥",
        "format": "password"
      },
      "api_base": {
        "type": "string",
        "title": "API基础URL",
        "description": "服务API的基础URL",
        "default": "https://api.example.com"
      },
      "timeout": {
        "type": "integer",
        "title": "请求超时时间",
        "description": "API请求超时时间（秒）",
        "default": 30,
        "minimum": 5,
        "maximum": 300
      },
      "enabled": {
        "type": "boolean",
        "title": "启用插件",
        "default": true
      }
    },
    "required": ["api_key"]
  }
}
```

### 3. 实现插件主类 (main.py)

```python
"""
我的超棒插件实现
"""

import logging
import aiohttp
from typing import Dict, Any

from wxauto_mgt.core.plugin_system import (
    BaseServicePlatform, PluginInfo, MessageContext, ProcessResult, MessageType
)

logger = logging.getLogger(__name__)


class MyAwesomePlugin(BaseServicePlatform):
    """我的超棒插件"""
    
    def __init__(self, plugin_info: PluginInfo):
        """初始化插件"""
        super().__init__(plugin_info)
        
        # 设置支持的消息类型
        self._supported_message_types = [MessageType.TEXT]
        self._platform_type = "my_awesome"
        
        # 插件特定配置
        self.api_key = ""
        self.api_base = ""
        self.timeout = 30
    
    def get_config_schema(self) -> Dict[str, Any]:
        """获取配置模式定义"""
        return {
            "type": "object",
            "properties": {
                "api_key": {
                    "type": "string",
                    "title": "API密钥",
                    "format": "password"
                },
                "api_base": {
                    "type": "string",
                    "title": "API基础URL",
                    "default": "https://api.example.com"
                },
                "timeout": {
                    "type": "integer",
                    "title": "请求超时时间",
                    "default": 30,
                    "minimum": 5,
                    "maximum": 300
                }
            },
            "required": ["api_key"]
        }
    
    def validate_config(self, config: Dict[str, Any]) -> tuple[bool, str]:
        """验证配置"""
        if not config.get('api_key'):
            return False, "API密钥不能为空"
        
        if not config.get('api_base'):
            return False, "API基础URL不能为空"
        
        return True, None
    
    async def _do_initialize(self):
        """执行自定义初始化逻辑"""
        self.api_key = self._config.get('api_key', '')
        self.api_base = self._config.get('api_base', '').rstrip('/')
        self.timeout = self._config.get('timeout', 30)
        
        logger.info(f"我的超棒插件初始化完成: {self.api_base}")
    
    async def _do_process_message(self, context: MessageContext) -> ProcessResult:
        """处理消息"""
        try:
            # 构建请求数据
            request_data = {
                "message": context.content,
                "sender": context.sender_remark or context.sender
            }
            
            # 发送API请求
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.post(
                    f"{self.api_base}/chat",
                    headers=headers,
                    json=request_data
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        return ProcessResult(
                            success=False,
                            error=f"API错误: {response.status}",
                            should_reply=False
                        )
                    
                    result = await response.json()
                    reply_content = result.get("reply", "")
                    
                    return ProcessResult(
                        success=True,
                        response=reply_content,
                        should_reply=bool(reply_content),
                        metadata=result.get("metadata", {})
                    )
        
        except Exception as e:
            logger.error(f"处理消息失败: {e}")
            return ProcessResult(
                success=False,
                error=str(e),
                should_reply=False
            )
    
    async def _do_test_connection(self) -> Dict[str, Any]:
        """测试连接"""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get(
                    f"{self.api_base}/health",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        return {
                            "success": True,
                            "message": "连接测试成功"
                        }
                    else:
                        error_text = await response.text()
                        return {
                            "success": False,
                            "error": f"HTTP {response.status}: {error_text}"
                        }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
```

## 配置模式 (JSON Schema)

插件使用JSON Schema定义配置参数，支持以下类型：

### 基本类型

```json
{
  "type": "object",
  "properties": {
    "string_field": {
      "type": "string",
      "title": "字符串字段",
      "description": "这是一个字符串字段",
      "default": "默认值"
    },
    "password_field": {
      "type": "string",
      "title": "密码字段",
      "format": "password"
    },
    "integer_field": {
      "type": "integer",
      "title": "整数字段",
      "default": 100,
      "minimum": 1,
      "maximum": 1000
    },
    "number_field": {
      "type": "number",
      "title": "数字字段",
      "default": 1.5,
      "minimum": 0.0,
      "maximum": 10.0
    },
    "boolean_field": {
      "type": "boolean",
      "title": "布尔字段",
      "default": true
    },
    "enum_field": {
      "type": "string",
      "title": "枚举字段",
      "enum": ["选项1", "选项2", "选项3"],
      "default": "选项1"
    }
  },
  "required": ["string_field", "password_field"]
}
```

## 权限系统

插件需要声明所需的权限：

### 可用权限

- `network.http`: HTTP网络访问
- `network.https`: HTTPS网络访问
- `file.read`: 文件读取
- `file.write`: 文件写入
- `config.read`: 配置读取
- `config.write`: 配置写入
- `database.read`: 数据库读取
- `database.write`: 数据库写入
- `message.process`: 消息处理
- `message.send`: 消息发送

### 权限检查

```python
from wxauto_mgt.core.plugin_system.plugin_security import plugin_security_manager, Permission

# 检查权限
if plugin_security_manager.check_permission(self._info.plugin_id, Permission.NETWORK_HTTP):
    # 执行网络请求
    pass
else:
    # 权限不足
    pass
```

## 消息处理

### 消息上下文 (MessageContext)

```python
@dataclass
class MessageContext:
    message_id: str          # 消息ID
    instance_id: str         # 实例ID
    chat_name: str          # 聊天对象名称
    sender: str             # 发送者
    sender_remark: str      # 发送者备注
    message_type: MessageType # 消息类型
    content: str            # 消息内容
    file_path: str          # 文件路径（文件消息）
    file_size: int          # 文件大小
    timestamp: datetime     # 时间戳
    metadata: Dict[str, Any] # 元数据
```

### 处理结果 (ProcessResult)

```python
@dataclass
class ProcessResult:
    success: bool           # 是否成功
    response: str          # 回复内容
    error: str             # 错误信息
    should_reply: bool     # 是否应该回复
    metadata: Dict[str, Any] # 元数据
    next_action: str       # 下一步操作
```

## 测试插件

### 1. 本地测试

```python
import asyncio
from wxauto_mgt.core.plugin_system import plugin_manager

async def test_plugin():
    # 初始化插件管理器
    await plugin_manager.initialize()
    
    # 加载插件
    manifest = {...}  # 插件清单
    success = await plugin_manager.install_plugin(manifest)
    
    if success:
        # 测试插件
        plugin = plugin_manager.get_plugin("my_awesome_plugin")
        if plugin:
            result = await plugin.test_connection()
            print(f"测试结果: {result}")

# 运行测试
asyncio.run(test_plugin())
```

### 2. 单元测试

```python
import unittest
from unittest.mock import AsyncMock, patch
from wxauto_mgt.core.plugin_system import MessageContext, MessageType

class TestMyAwesomePlugin(unittest.TestCase):
    
    def setUp(self):
        from main import MyAwesomePlugin
        from wxauto_mgt.core.plugin_system import PluginInfo
        
        plugin_info = PluginInfo(
            plugin_id="test_plugin",
            name="测试插件",
            version="1.0.0",
            description="测试用插件",
            author="测试者"
        )
        
        self.plugin = MyAwesomePlugin(plugin_info)
    
    async def test_process_message(self):
        # 配置插件
        config = {
            "api_key": "test_key",
            "api_base": "https://api.test.com",
            "timeout": 30
        }
        await self.plugin.initialize(config)
        
        # 创建测试消息
        context = MessageContext(
            message_id="test_msg",
            instance_id="test_instance",
            chat_name="测试群",
            sender="测试用户",
            message_type=MessageType.TEXT,
            content="你好"
        )
        
        # 模拟API响应
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = {"reply": "你好！"}
            mock_post.return_value.__aenter__.return_value = mock_response
            
            # 测试消息处理
            result = await self.plugin.process_message(context)
            
            self.assertTrue(result.success)
            self.assertEqual(result.response, "你好！")
            self.assertTrue(result.should_reply)

if __name__ == '__main__':
    unittest.main()
```

## 打包和分发

### 1. 创建插件包

```bash
# 创建插件包目录
mkdir my_awesome_plugin_package
cd my_awesome_plugin_package

# 复制插件文件
cp -r ../my_plugin/* .

# 创建压缩包
zip -r my_awesome_plugin_v1.0.0.zip .
```

### 2. 插件市场发布

1. 访问插件市场网站
2. 注册开发者账号
3. 上传插件包
4. 填写插件信息
5. 等待审核

### 3. 本地安装

```python
from wxauto_mgt.core.plugin_system import plugin_marketplace

# 从文件安装
success, error = await plugin_marketplace.install_plugin_from_file("my_plugin.zip")

# 从市场安装
success, error = await plugin_marketplace.install_plugin_from_marketplace("my_awesome_plugin")
```

## 最佳实践

### 1. 错误处理

- 使用try-catch包装所有异步操作
- 提供有意义的错误信息
- 记录详细的日志

### 2. 性能优化

- 使用连接池复用HTTP连接
- 实现适当的缓存机制
- 避免阻塞操作

### 3. 安全考虑

- 验证所有输入参数
- 使用HTTPS进行网络通信
- 不在日志中记录敏感信息

### 4. 配置管理

- 提供合理的默认值
- 验证配置参数
- 支持配置热更新

## 常见问题

### Q: 如何处理插件依赖？

A: 在plugin.json中声明依赖，插件管理器会自动安装。

### Q: 如何调试插件？

A: 使用Python的logging模块记录日志，在开发环境中可以看到详细日志。

### Q: 插件如何访问数据库？

A: 需要申请database.read和database.write权限，然后使用db_manager。

### Q: 如何实现插件间通信？

A: 可以通过插件管理器获取其他插件实例，或使用事件系统。

## 示例插件

查看以下示例插件了解更多实现细节：

- `plugins/dify_platform/`: Dify平台集成
- `plugins/openai_platform/`: OpenAI API集成
- `plugins/keyword_platform/`: 关键词匹配
- `plugins/accounting_platform/`: 记账服务集成

## 支持和反馈

- GitHub Issues: https://github.com/zj591227045/WXAUTO-MGT/issues
- 开发者文档: https://docs.wxauto-mgt.com
- 社区论坛: https://community.wxauto-mgt.com
