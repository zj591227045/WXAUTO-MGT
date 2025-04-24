# WxAuto HTTP API 接口文档

## API 概述

本文档详细说明了WxAuto HTTP API的使用方法、请求格式和响应格式。所有接口都需要通过API密钥认证。

## 认证方式

所有API请求都需要在HTTP Header中包含API密钥：

```http
X-API-Key: your_api_key_here
```

## 通用响应格式

```json
{
    "code": 0,       // 状态码：0成功，非0失败
    "message": "",   // 响应消息
    "data": {}       // 响应数据
}
```

## 错误码说明

- 0: 成功
- 1001: 认证失败
- 1002: 参数错误
- 2001: 微信未初始化
- 2002: 微信已掉线
- 3001: 发送消息失败
- 3002: 获取消息失败
- 4001: 群操作失败
- 5001: 好友操作失败

## API 端点详细说明

### 1. 认证相关

#### 验证API密钥
```http
POST /api/auth/verify
```

CURL 示例:
```bash
curl -X POST http://10.255.0.90:5000/api/auth/verify \
  -H "X-API-Key: test-key-2"
```

请求头：
```http
X-API-Key: your_api_key_here
```

响应示例：
```json
{
    "code": 0,
    "message": "验证成功",
    "data": {
        "valid": true
    }
}
```

### 2. 微信基础功能

#### 初始化微信实例
```http
POST /api/wechat/initialize
```

CURL 示例:
```bash
curl -X POST http://10.255.0.90:5000/api/wechat/initialize \
  -H "X-API-Key: test-key-2"
```

响应示例：
```json
{
    "code": 0,
    "message": "初始化成功",
    "data": {
        "status": "connected"
    }
}
```

#### 获取微信状态
```http
GET /api/wechat/status
```

CURL 示例:
```bash
curl -X GET http://10.255.0.90:5000/api/wechat/status \
  -H "X-API-Key: test-key-2"
```

响应示例：
```json
{
    "code": 0,
    "message": "获取成功",
    "data": {
        "status": "online",
        "last_active": "2025-04-23 10:30:00"
    }
}
```

### 3. 消息相关接口

#### 发送普通文本消息
```http
POST /api/message/send
```

CURL 示例:
```bash
curl -X POST http://10.255.0.90:5000/api/message/send \
  -H "X-API-Key: test-key-2" \
  -H "Content-Type: application/json" \
  -d '{
    "receiver": "文件传输助手",
    "message": "这是一条测试消息",
    "at_list": ["张三", "李四"],
    "clear": true
  }'
```

请求体：
```json
{
    "receiver": "文件传输助手",
    "message": "这是一条测试消息",
    "at_list": ["张三", "李四"],  // 可选
    "clear": true  // 可选，是否清除输入框
}
```

响应示例：
```json
{
    "code": 0,
    "message": "发送成功",
    "data": {
        "message_id": "xxxxx"
    }
}
```

#### 发送打字机模式消息
```http
POST /api/message/send-typing
```

CURL 示例:
```bash
curl -X POST http://10.255.0.90:5000/api/message/send-typing \
  -H "X-API-Key: test-key-2" \
  -H "Content-Type: application/json" \
  -d '{
    "receiver": "文件传输助手",
    "message": "这是打字机模式消息\n这是第二行",
    "at_list": ["张三", "李四"],
    "clear": true
  }'
```

请求体：
```json
{
    "receiver": "文件传输助手",
    "message": "这是打字机模式消息\n这是第二行",
    "at_list": ["张三", "李四"],  // 可选
    "clear": true  // 可选
}
```

响应示例：
```json
{
    "code": 0,
    "message": "发送成功",
    "data": {
        "message_id": "xxxxx"
    }
}
```

#### 发送文件消息
```http
POST /api/message/send-file
```

CURL 示例:
```bash
curl -X POST http://10.255.0.90:5000/api/message/send-file \
  -H "X-API-Key: test-key-2" \
  -H "Content-Type: application/json" \
  -d '{
    "receiver": "文件传输助手",
    "file_paths": [
        "D:/test/test1.txt",
        "D:/test/test2.txt"
    ]
  }'
```

请求体：
```json
{
    "receiver": "文件传输助手",
    "file_paths": [
        "D:/test/test1.txt",
        "D:/test/test2.txt"
    ]
}
```

响应示例：
```json
{
    "code": 0,
    "message": "发送成功",
    "data": {
        "success_count": 2,
        "failed_files": []
    }
}
```

#### 获取聊天记录
```http
POST /api/message/get-history
```

请求体：
```json
{
    "chat_name": "文件传输助手",
    "save_pic": false,    // 可选，是否保存图片
    "save_video": false,  // 可选，是否保存视频
    "save_file": false,   // 可选，是否保存文件
    "save_voice": false   // 可选，是否保存语音
}
```

响应示例：
```json
{
    "code": 0,
    "message": "获取成功",
    "data": {
        "messages": [
            {
                "type": "text",
                "sender": "张三",
                "content": "测试消息",
                "time": "2025-04-23 10:30:00"
            }
        ]
    }
}
```

#### 获取主窗口未读消息
```http
GET /api/message/get-next-new?savepic=false&savevideo=false&savefile=false&savevoice=false&parseurl=false
```

CURL 示例:
```bash
curl -X GET "http://10.255.0.90:5000/api/message/get-next-new?savepic=false&savevideo=false&savefile=false&savevoice=false&parseurl=false" \
  -H "X-API-Key: test-key-2"
```

查询参数：
- savepic: bool，是否保存图片（可选，默认false）
- savevideo: bool，是否保存视频（可选，默认false）
- savefile: bool，是否保存文件（可选，默认false）
- savevoice: bool，是否保存语音（可选，默认false）
- parseurl: bool，是否解析链接（可选，默认false）

响应示例：
```json
{
    "code": 0,
    "message": "获取成功",
    "data": {
        "messages": {
            "张三": [
                {
                    "type": "text",
                    "content": "你好",
                    "sender": "张三",
                    "id": "123456",
                    "mtype": 1,
                    "sender_remark": "老张"
                }
            ]
        }
    }
}
```

### 4. 消息监听相关接口

#### 添加监听对象
```http
POST /api/message/listen/add
```

CURL 示例:
```bash
curl -X POST http://10.255.0.90:5000/api/message/listen/add \
  -H "X-API-Key: test-key-2" \
  -H "Content-Type: application/json" \
  -d '{
    "who": "测试群",
    "savepic": false,
    "savevideo": false,
    "savefile": false,
    "savevoice": false,
    "parseurl": false,
    "exact": false
  }'
```

请求体：
```json
{
    "who": "测试群",
    "savepic": false,      // 可选，是否保存图片
    "savevideo": false,    // 可选，是否保存视频 
    "savefile": false,     // 可选，是否保存文件
    "savevoice": false,    // 可选，是否保存语音
    "parseurl": false,     // 可选，是否解析URL
    "exact": false         // 可选，是否精确匹配名称
}
```

响应示例：
```json
{
    "code": 0,
    "message": "添加监听成功",
    "data": {
        "who": "测试群"
    }
}
```

#### 获取监听消息
```http
GET /api/message/listen/get?who=测试群
```

CURL 示例:
```bash
curl -X GET "http://10.255.0.90:5000/api/message/listen/get?who=测试群" \
  -H "X-API-Key: test-key-2"
```

查询参数：
- who: string，要获取消息的对象（可选，不传则获取所有监听对象的消息）

响应示例：
```json
{
    "code": 0,
    "message": "获取成功",
    "data": {
        "messages": {
            "测试群": [
                {
                    "type": "text",
                    "content": "新消息",
                    "sender": "张三",
                    "id": "123456",
                    "mtype": 1,
                    "sender_remark": "老张"
                }
            ]
        }
    }
}
```

#### 移除监听对象
```http
POST /api/message/listen/remove
```

CURL 示例:
```bash
curl -X POST http://10.255.0.90:5000/api/message/listen/remove \
  -H "X-API-Key: test-key-2" \
  -H "Content-Type: application/json" \
  -d '{
    "who": "测试群"
  }'
```

请求体：
```json
{
    "who": "测试群"
}
```

响应示例：
```json
{
    "code": 0,
    "message": "移除监听成功",
    "data": {
        "who": "测试群"
    }
}
```

### 5. 聊天窗口操作接口

注意：以下接口需要先通过 `/api/message/listen/add` 将目标添加到监听列表。

#### 发送普通消息
```http
POST /api/chat-window/message/send
```

CURL 示例:
```bash
curl -X POST http://10.255.0.90:5000/api/chat-window/message/send \
  -H "X-API-Key: test-key-2" \
  -H "Content-Type: application/json" \
  -d '{
    "who": "测试群",
    "message": "测试消息",
    "at_list": ["张三", "李四"],
    "clear": true
  }'
```

请求体：
```json
{
    "who": "测试群",
    "message": "测试消息",
    "at_list": ["张三", "李四"],  // 可选
    "clear": true                // 可选，是否清除输入框
}
```

响应示例：
```json
{
    "code": 0,
    "message": "发送成功",
    "data": {
        "message_id": "success"
    }
}
```

#### 发送打字机模式消息
```http
POST /api/chat-window/message/send-typing
```

CURL 示例:
```bash
curl -X POST http://10.255.0.90:5000/api/chat-window/message/send-typing \
  -H "X-API-Key: test-key-2" \
  -H "Content-Type: application/json" \
  -d '{
    "who": "测试群",
    "message": "测试消息",
    "at_list": ["张三", "李四"],
    "clear": true
  }'
```

请求体和响应格式同上。

#### 发送文件
```http
POST /api/chat-window/message/send-file
```

CURL 示例:
```bash
curl -X POST http://10.255.0.90:5000/api/chat-window/message/send-file \
  -H "X-API-Key: test-key-2" \
  -H "Content-Type: application/json" \
  -d '{
    "who": "测试群",
    "file_paths": [
        "D:/test/test1.txt",
        "D:/test/test2.txt"
    ]
  }'
```

请求体：
```json
{
    "who": "测试群",
    "file_paths": [
        "D:/test/test1.txt",
        "D:/test/test2.txt"
    ]
}
```

响应示例：
```json
{
    "code": 0,
    "message": "发送成功",
    "data": {
        "success_count": 2,
        "failed_files": []
    }
}
```

#### @所有人
```http
POST /api/chat-window/message/at-all
```

CURL 示例:
```bash
curl -X POST http://10.255.0.90:5000/api/chat-window/message/at-all \
  -H "X-API-Key: test-key-2" \
  -H "Content-Type: application/json" \
  -d '{
    "who": "测试群",
    "message": "请大家注意"
  }'
```

请求体：
```json
{
    "who": "测试群",
    "message": "请大家注意"  // 可选
}
```

响应示例：
```json
{
    "code": 0,
    "message": "发送成功",
    "data": {
        "message_id": "success"
    }
}
```

#### 获取聊天窗口信息
```http
GET /api/chat-window/info?who=测试群
```

CURL 示例:
```bash
curl -X GET "http://10.255.0.90:5000/api/chat-window/info?who=测试群" \
  -H "X-API-Key: test-key-2"
```

响应示例：
```json
{
    "code": 0,
    "message": "获取成功",
    "data": {
        "member_count": 100,
        "name": "测试群",
        "members": ["张三", "李四"]
    }
}
```

### 6. 群组相关接口

#### 获取群列表
```http
GET /api/group/list
```

CURL 示例:
```bash
curl -X GET http://10.255.0.90:5000/api/group/list \
  -H "X-API-Key: test-key-2"
```

响应示例：
```json
{
    "code": 0,
    "message": "获取成功",
    "data": {
        "groups": [
            {
                "name": "测试群",
                "member_count": 100
            }
        ]
    }
}
```

#### 群管理操作
```http
POST /api/group/manage
```

CURL 示例:
```bash
# 重命名群
curl -X POST http://10.255.0.90:5000/api/group/manage \
  -H "X-API-Key: test-key-2" \
  -H "Content-Type: application/json" \
  -d '{
    "group_name": "测试群",
    "action": "rename",
    "params": {
        "new_name": "新群名"
    }
  }'

# 退出群
curl -X POST http://10.255.0.90:5000/api/group/manage \
  -H "X-API-Key: test-key-2" \
  -H "Content-Type: application/json" \
  -d '{
    "group_name": "测试群",
    "action": "quit"
  }'
```

请求体：
```json
{
    "group_name": "测试群",
    "action": "rename",  // rename/set_announcement/quit
    "params": {
        "new_name": "新群名"  // 根据action不同，参数不同
    }
}
```

响应示例：
```json
{
    "code": 0,
    "message": "操作成功",
    "data": {
        "success": true
    }
}
```

### 7. 好友相关接口

#### 获取好友列表
```http
GET /api/contact/list
```

CURL 示例:
```bash
curl -X GET http://10.255.0.90:5000/api/contact/list \
  -H "X-API-Key: test-key-2"
```

响应示例：
```json
{
    "code": 0,
    "message": "获取成功",
    "data": {
        "friends": [
            {
                "nickname": "张三",
                "remark": "张总",
                "tags": ["同事"]
            }
        ]
    }
}
```

#### 添加好友
```http
POST /api/contact/add
```

CURL 示例:
```bash
curl -X POST http://10.255.0.90:5000/api/contact/add \
  -H "X-API-Key: test-key-2" \
  -H "Content-Type: application/json" \
  -d '{
    "keywords": "wxid_xxxxx",
    "message": "你好，我是...",
    "remark": "备注名",
    "tags": ["同事", "朋友"]
  }'
```

请求体：
```json
{
    "keywords": "wxid_xxxxx",  // 微信号/手机号/QQ号
    "message": "你好，我是...",
    "remark": "备注名",        // 可选
    "tags": ["同事", "朋友"]   // 可选
}
```

响应示例：
```json
{
    "code": 0,
    "message": "发送请求成功",
    "data": {
        "status": 1,  // 0:失败 1:成功 2:已是好友 3:被拉黑 4:未找到账号
        "message": "发送请求成功"
    }
}
```

### 8. 健康检查接口

获取服务和微信连接状态。

```http
GET /api/health
```

CURL 示例:
```bash
curl -X GET http://10.255.0.90:5000/api/health \
  -H "X-API-Key: test-key-2"
```

响应示例：
```json
{
    "code": 0,
    "message": "服务正常",
    "data": {
        "status": "ok",
        "wechat_status": "connected",
        "uptime": 3600
    }
}
```

## 注意事项

1. 所有接口调用都需要先调用初始化接口
2. 注意处理接口调用频率，避免触发微信限制
3. 文件相关操作需要确保文件路径正确且有访问权限
4. 建议在调用接口前先检查微信在线状态

## 使用注意事项

1. 所有接口调用前请确保：
   - 已通过API密钥验证
   - 已调用初始化接口
   - 微信处于登录状态

2. 使用监听相关功能时：
   - 添加监听前请确认对象存在
   - 及时处理监听消息避免内存占用过大
   - 不再需要时记得移除监听

3. 发送消息时：
   - 注意消息频率，避免触发微信限制
   - 文件发送前确认路径正确且有访问权限
   - 使用打字机模式时预留合适的打字间隔

4. 异常处理：
   - 妥善处理各类错误码
   - 实现合适的重试机制
   - 保持日志记录便于问题排查

## 开发建议

1. 使用合适的HTTP客户端库
2. 实现请求重试和超时处理
3. 做好异常捕获和日志记录
4. 合理设置并发和队列处理
5. 定期检查微信状态保持连接

## 示例代码

### Python示例

```python
import requests

class WxAutoAPI:
    def __init__(self, base_url, api_key):
        self.base_url = base_url
        self.headers = {
            'X-API-Key': api_key,
            'Content-Type': 'application/json'
        }
    
    def initialize(self):
        response = requests.post(
            f"{self.base_url}/api/wechat/initialize",
            headers=self.headers
        )
        return response.json()
    
    def send_message(self, receiver, message, at_list=None):
        data = {
            'receiver': receiver,
            'message': message,
            'at_list': at_list or []
        }
        response = requests.post(
            f"{self.base_url}/api/message/send",
            headers=self.headers,
            json=data
        )
        return response.json()
    
    def add_listen(self, who, **kwargs):
        data = {'who': who, **kwargs}
        response = requests.post(
            f"{self.base_url}/api/message/listen/add",
            headers=self.headers,
            json=data
        )
        return response.json()
    
    def get_messages(self, who=None):
        params = {'who': who} if who else {}
        response = requests.get(
            f"{self.base_url}/api/message/listen/get",
            headers=self.headers,
            params=params
        )
        return response.json()

# 使用示例
api = WxAutoAPI('http://10.255.0.90:5000', 'your-api-key')

# 初始化
api.initialize()

# 发送消息
api.send_message('文件传输助手', '测试消息')

# 添加监听
api.add_listen('测试群', savepic=True)

# 获取消息
messages = api.get_messages('测试群')
print(messages)
```

### JavaScript示例

```javascript
class WxAutoAPI {
    constructor(baseUrl, apiKey) {
        this.baseUrl = baseUrl;
        this.headers = {
            'X-API-Key': apiKey,
            'Content-Type': 'application/json'
        };
    }

    async initialize() {
        const response = await fetch(`${this.baseUrl}/api/wechat/initialize`, {
            method: 'POST',
            headers: this.headers
        });
        return response.json();
    }

    async sendMessage(receiver, message, atList = []) {
        const response = await fetch(`${this.baseUrl}/api/message/send`, {
            method: 'POST',
            headers: this.headers,
            body: JSON.stringify({
                receiver,
                message,
                at_list: atList
            })
        });
        return response.json();
    }

    async addListen(who, options = {}) {
        const response = await fetch(`${this.baseUrl}/api/message/listen/add`, {
            method: 'POST',
            headers: this.headers,
            body: JSON.stringify({
                who,
                ...options
            })
        });
        return response.json();
    }

    async getMessages(who = null) {
        const url = new URL(`${this.baseUrl}/api/message/listen/get`);
        if (who) url.searchParams.set('who', who);
        
        const response = await fetch(url, {
            headers: this.headers
        });
        return response.json();
    }
}

// 使用示例
const api = new WxAutoAPI('http://10.255.0.90:5000', 'your-api-key');

async function demo() {
    // 初始化
    await api.initialize();

    // 发送消息
    await api.sendMessage('文件传输助手', '测试消息');

    // 添加监听
    await api.addListen('测试群', { savepic: true });

    // 获取消息
    const messages = await api.getMessages('测试群');
    console.log(messages);
}

demo().catch(console.error);
```