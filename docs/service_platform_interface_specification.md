# 服务平台接口规范

## 概述

本文档定义了WXAUTO-MGT项目中服务平台的标准化接口规范，为代码解耦重构提供统一的设计指导。

## 设计原则

1. **单一职责**：每个平台负责自己的完整业务流程
2. **接口统一**：所有平台实现相同的标准接口
3. **配置独立**：每个平台管理自己的配置参数
4. **错误处理**：统一的错误处理和日志记录机制
5. **向后兼容**：保持现有API调用方式不变

## 核心接口定义

### 1. ServicePlatform 基类

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class ServicePlatform(ABC):
    """服务平台基类，定义所有平台必须实现的接口"""
    
    def __init__(self, platform_id: str, name: str, config: Dict[str, Any]):
        """
        初始化服务平台
        
        Args:
            platform_id: 平台唯一标识符
            name: 平台显示名称
            config: 平台配置字典
        """
        self.platform_id = platform_id
        self.name = name
        self.config = config
        self._initialized = False
        self.message_send_mode = config.get('message_send_mode', 'normal')
    
    @abstractmethod
    async def initialize(self) -> bool:
        """
        初始化平台，验证配置和建立连接
        
        Returns:
            bool: 初始化是否成功
        """
        pass
    
    @abstractmethod
    async def process_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理消息的核心方法
        
        Args:
            message: 消息数据，包含以下字段：
                - content: 消息内容
                - sender: 发送者
                - sender_remark: 发送者备注
                - chat_name: 聊天对象名称
                - instance_id: 实例ID
                - message_id: 消息ID
                - mtype: 消息类型
                
        Returns:
            Dict[str, Any]: 处理结果，包含：
                - success: bool, 是否处理成功
                - content: str, 回复内容
                - error: str, 错误信息（可选）
                - raw_response: Any, 原始响应数据（可选）
                - should_reply: bool, 是否应该发送回复（可选）
                - conversation_id: str, 会话ID（可选）
        """
        pass
    
    @abstractmethod
    async def test_connection(self) -> Dict[str, Any]:
        """
        测试平台连接状态
        
        Returns:
            Dict[str, Any]: 测试结果，包含：
                - success: bool, 测试是否成功
                - message: str, 测试结果描述
                - error: str, 错误信息（可选）
                - data: Any, 额外数据（可选）
        """
        pass
    
    @abstractmethod
    def get_type(self) -> str:
        """
        获取平台类型标识符
        
        Returns:
            str: 平台类型（如 'dify', 'openai', 'zhiweijz', 'keyword'）
        """
        pass
    
    def get_safe_config(self) -> Dict[str, Any]:
        """
        获取安全的配置（隐藏敏感信息）
        
        Returns:
            Dict[str, Any]: 隐藏敏感信息后的配置
        """
        safe_config = self.config.copy()
        # 隐藏敏感信息
        sensitive_keys = ['api_key', 'token', 'secret', 'password']
        for key in sensitive_keys:
            if key in safe_config:
                safe_config[key] = '******'
        return safe_config
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式
        
        Returns:
            Dict[str, Any]: 平台信息字典
        """
        return {
            'platform_id': self.platform_id,
            'name': self.name,
            'type': self.get_type(),
            'config': self.get_safe_config(),
            'initialized': self._initialized
        }
    
    async def cleanup(self):
        """
        清理资源（可选实现）
        """
        pass
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取平台统计信息（可选实现）
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        return {}
```

## 平台类型定义

### 支持的平台类型

1. **dify**: Dify AI平台
2. **openai**: OpenAI兼容平台
3. **zhiweijz**: 只为记账平台
4. **keyword**: 关键词匹配平台

### 平台配置规范

每个平台的配置参数应该包含以下通用字段：

```python
{
    "message_send_mode": "normal",  # 消息发送模式：normal/typing
    # 平台特定配置...
}
```

#### Dify平台配置
```python
{
    "api_base": "https://api.dify.ai/v1",
    "api_key": "your_api_key",
    "conversation_id": "",  # 可选
    "user_id": "default_user",
    "message_send_mode": "normal"
}
```

#### OpenAI平台配置
```python
{
    "api_base": "https://api.openai.com/v1",
    "api_key": "your_api_key",
    "model": "gpt-3.5-turbo",
    "temperature": 0.7,
    "max_tokens": 1000,
    "system_prompt": "你是一个有用的助手。",
    "message_send_mode": "normal"
}
```

#### zhiweijz平台配置
```python
{
    "server_url": "http://localhost:5000",
    "username": "your_username",
    "password": "your_password",
    "account_book_id": "",
    "account_book_name": "",
    "auto_login": true,
    "warn_on_irrelevant": false,
    "message_send_mode": "normal"
}
```

#### 关键词匹配平台配置
```python
{
    "rules": [
        {
            "keywords": ["关键词1", "关键词2"],
            "match_type": "contains",  # exact/contains/fuzzy
            "replies": ["回复1", "回复2"],
            "is_random_reply": true,
            "min_reply_time": 1,
            "max_reply_time": 3
        }
    ],
    "min_reply_time": 1,
    "max_reply_time": 3,
    "message_send_mode": "normal"
}
```

## 工厂模式

### create_platform 函数

```python
def create_platform(platform_type: str, platform_id: str, name: str, config: Dict[str, Any]) -> Optional[ServicePlatform]:
    """
    创建服务平台实例的工厂函数
    
    Args:
        platform_type: 平台类型
        platform_id: 平台ID
        name: 平台名称
        config: 平台配置
        
    Returns:
        Optional[ServicePlatform]: 平台实例或None
    """
    platform_map = {
        "dify": "wxauto_mgt.core.platforms.dify_platform.DifyPlatform",
        "openai": "wxauto_mgt.core.platforms.openai_platform.OpenAIPlatform",
        "zhiweijz": "wxauto_mgt.core.platforms.zhiweijz_platform.ZhiWeiJZPlatform",
        "keyword": "wxauto_mgt.core.platforms.keyword_platform.KeywordMatchPlatform"
    }
    
    if platform_type not in platform_map:
        logger.error(f"不支持的平台类型: {platform_type}")
        return None
    
    # 动态导入和创建实例
    module_path, class_name = platform_map[platform_type].rsplit('.', 1)
    module = importlib.import_module(module_path)
    platform_class = getattr(module, class_name)
    
    return platform_class(platform_id, name, config)
```

## 目录结构

重构后的目录结构：

```
wxauto_mgt/core/
├── platforms/                    # 平台实现目录
│   ├── __init__.py
│   ├── base_platform.py         # ServicePlatform基类
│   ├── dify_platform.py         # Dify平台实现
│   ├── openai_platform.py       # OpenAI平台实现
│   ├── zhiweijz_platform.py     # zhiweijz平台实现（已存在）
│   └── keyword_platform.py      # 关键词匹配平台实现
├── service_platform.py          # 保留工厂函数和导入
└── service_platform_manager.py  # 平台管理器
```

## 重构步骤

1. 创建platforms目录和base_platform.py
2. 将ServicePlatform基类移动到base_platform.py
3. 逐个提取平台实现到独立文件
4. 更新工厂函数的导入路径
5. 验证功能完整性

## 兼容性保证

- 保持现有的API调用接口不变
- 保持数据库结构不变
- 保持配置格式向后兼容
- 保持日志格式一致
