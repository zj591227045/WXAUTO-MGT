# 简单回声插件

这是一个WXAUTO-MGT的示例插件，用于演示插件开发的基本流程。该插件将收到的消息原样返回，并可以添加自定义的前缀和后缀。

## 功能特性

- ✅ 消息回声：将收到的消息原样返回
- ✅ 可配置前缀和后缀
- ✅ 消息长度限制和截断
- ✅ 可配置回复延迟
- ✅ 启用/禁用开关
- ✅ 统计功能
- ✅ 健康检查和自我诊断

## 配置参数

| 参数名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| prefix | string | "回声: " | 回复消息的前缀 |
| suffix | string | "" | 回复消息的后缀 |
| enabled | boolean | true | 是否启用插件 |
| delay_seconds | number | 0.5 | 回复前的延迟时间（秒） |
| max_length | integer | 200 | 回复消息的最大长度 |

## 安装方法

### 方法1：从插件市场安装

1. 打开WXAUTO-MGT应用
2. 进入"插件管理"页面
3. 搜索"简单回声插件"
4. 点击"安装"按钮

### 方法2：手动安装

1. 下载插件文件
2. 解压到WXAUTO-MGT的plugins目录
3. 重启应用或重新加载插件

### 方法3：开发者安装

```bash
# 克隆项目
git clone https://github.com/zj591227045/WXAUTO-MGT.git
cd WXAUTO-MGT

# 复制示例插件
cp -r examples/simple_echo_plugin plugins/

# 重启应用
python main.py
```

## 使用方法

1. **启用插件**：
   - 进入"插件管理" -> "插件列表"
   - 找到"简单回声插件"
   - 勾选"启用"复选框

2. **配置插件**：
   - 点击"配置"按钮
   - 设置前缀、后缀等参数
   - 点击"保存"

3. **创建转发规则**：
   - 进入"消息转发规则"页面
   - 添加新规则，选择此插件作为目标平台
   - 设置匹配的聊天对象

4. **测试功能**：
   - 在配置的聊天中发送消息
   - 插件会自动回复带有前缀的相同消息

## 配置示例

### 基础配置
```json
{
  "prefix": "回声: ",
  "suffix": "",
  "enabled": true,
  "delay_seconds": 0.5,
  "max_length": 200
}
```

### 自定义配置
```json
{
  "prefix": "🔊 ",
  "suffix": " (来自回声插件)",
  "enabled": true,
  "delay_seconds": 1.0,
  "max_length": 150
}
```

## 开发说明

这个插件展示了WXAUTO-MGT插件开发的核心概念：

### 1. 插件类结构
```python
class SimpleEchoPlugin(BaseServicePlatform):
    def __init__(self, plugin_info: PluginInfo):
        # 初始化插件
    
    def get_config_schema(self) -> Dict[str, Any]:
        # 定义配置模式
    
    def validate_config(self, config: Dict[str, Any]) -> tuple[bool, str]:
        # 验证配置
    
    async def _do_process_message(self, context: MessageContext) -> ProcessResult:
        # 处理消息的核心逻辑
```

### 2. 配置管理
- 使用JSON Schema定义配置参数
- 实现配置验证逻辑
- 支持动态配置更新

### 3. 消息处理
- 接收MessageContext对象
- 返回ProcessResult对象
- 支持异步处理

### 4. 健康检查
- 实现健康检查接口
- 提供性能指标
- 支持自我诊断

## 测试用例

### 基本功能测试
```python
import unittest
from wxauto_mgt.core.plugin_system import MessageContext, MessageType

class TestSimpleEchoPlugin(unittest.TestCase):
    
    def setUp(self):
        # 初始化插件
        pass
    
    async def test_echo_message(self):
        # 测试消息回声功能
        context = MessageContext(
            message_id="test_001",
            instance_id="test_instance",
            chat_name="测试群",
            sender="测试用户",
            message_type=MessageType.TEXT,
            content="Hello World"
        )
        
        result = await self.plugin.process_message(context)
        
        self.assertTrue(result.success)
        self.assertEqual(result.response, "回声: Hello World")
        self.assertTrue(result.should_reply)
    
    async def test_length_limit(self):
        # 测试长度限制功能
        long_message = "A" * 300
        context = MessageContext(
            message_id="test_002",
            content=long_message
        )
        
        result = await self.plugin.process_message(context)
        
        self.assertTrue(result.success)
        self.assertLessEqual(len(result.response), 200)
        self.assertIn("...", result.response)
```

### 配置测试
```python
def test_config_validation(self):
    # 测试有效配置
    valid_config = {
        "prefix": "Test: ",
        "suffix": " [End]",
        "enabled": True,
        "delay_seconds": 1.0,
        "max_length": 100
    }
    
    is_valid, error = self.plugin.validate_config(valid_config)
    self.assertTrue(is_valid)
    self.assertEqual(error, "")
    
    # 测试无效配置
    invalid_config = {
        "delay_seconds": -1,  # 无效的延迟时间
        "max_length": 5       # 过小的最大长度
    }
    
    is_valid, error = self.plugin.validate_config(invalid_config)
    self.assertFalse(is_valid)
    self.assertIsNotNone(error)
```

## 扩展建议

基于这个示例插件，你可以开发更复杂的功能：

1. **智能回复**：集成AI服务，提供智能回复
2. **消息过滤**：添加关键词过滤和内容审核
3. **多语言支持**：支持多种语言的消息处理
4. **数据存储**：保存消息历史和用户偏好
5. **外部API**：集成第三方服务和API

## 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

## 贡献

欢迎提交Issue和Pull Request来改进这个示例插件！

## 支持

如果你在使用过程中遇到问题，可以：

1. 查看[插件开发指南](../../docs/plugin_development_guide.md)
2. 在GitHub上提交Issue
3. 加入开发者社区讨论
