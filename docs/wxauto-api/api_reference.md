# wxauto_http_api API 参考文档

## API 概述

wxauto_http_api 提供了一系列 HTTP API 接口，用于控制微信客户端，实现消息发送、接收、文件传输等功能。所有 API 都需要通过 API 密钥进行认证。

### 基本信息

- **基础 URL**: `http://localhost:5000/api`
- **认证方式**: 通过请求头 `X-API-Key` 传递 API 密钥
- **响应格式**: JSON
- **响应结构**:
  ```json
  {
    "code": 0,         // 状态码，0 表示成功，非 0 表示失败
    "message": "成功",  // 状态消息
    "data": {}         // 响应数据，可能为 null
  }
  ```

## API 端点

### 认证相关

#### 验证 API 密钥

```
POST /api/auth/verify
```

**请求头**:
- `X-API-Key`: API 密钥

**响应**:
```json
{
  "code": 0,
  "message": "验证成功",
  "data": {
    "valid": true
  }
}
```

### 微信相关

#### 初始化微信

```
POST /api/wechat/initialize
```

**请求头**:
- `X-API-Key`: API 密钥

**响应**:
```json
{
  "code": 0,
  "message": "初始化成功",
  "data": {
    "window_name": "微信"
  }
}
```

#### 获取微信状态

```
GET /api/health
```

**响应**:
```json
{
  "code": 0,
  "message": "服务正常",
  "data": {
    "status": "ok",
    "wechat_status": "connected",
    "uptime": 3600,
    "wx_lib": "wxauto"
  }
}
```

### 消息相关

#### 发送消息

```
POST /api/message/send
```

**请求头**:
- `X-API-Key`: API 密钥

**请求体**:
```json
{
  "receiver": "接收者名称",
  "message": "消息内容",
  "at_list": ["@的人1", "@的人2"],  // 可选
  "clear": true                    // 可选，是否清空输入框
}
```

**响应**:
```json
{
  "code": 0,
  "message": "发送成功",
  "data": {
    "message_id": "success"
  }
}
```

#### 发送打字消息

```
POST /api/message/send-typing
```

**请求头**:
- `X-API-Key`: API 密钥

**请求体**:
```json
{
  "receiver": "接收者名称",
  "message": "消息内容",
  "at_list": ["@的人1", "@的人2"],  // 可选
  "clear": true                    // 可选，是否清空输入框
}
```

**响应**:
```json
{
  "code": 0,
  "message": "发送成功",
  "data": {
    "message_id": "success"
  }
}
```

#### 发送文件

```
POST /api/message/send-file
```

**请求头**:
- `X-API-Key`: API 密钥

**请求体**:
```json
{
  "receiver": "接收者名称",
  "file_paths": [
    "C:\\path\\to\\file1.jpg",
    "C:\\path\\to\\file2.pdf"
  ]
}
```

**响应**:
```json
{
  "code": 0,
  "message": "发送完成",
  "data": {
    "success_count": 2,
    "failed_files": []
  }
}
```

#### 获取下一条新消息

```
GET /api/message/get-next-new
```

**请求头**:
- `X-API-Key`: API 密钥

**查询参数**:
- `savepic` (可选): 是否保存图片，默认 false
- `savefile` (可选): 是否保存文件，默认 false
- `savevoice` (可选): 是否保存语音，默认 false
- `parseurl` (可选): 是否解析 URL，默认 false（仅 wxautox 支持）

**响应**:
```json
{
  "code": 0,
  "message": "获取成功",
  "data": {
    "messages": {
      "张三": [
        {
          "id": "msg_123",
          "type": "text",
          "sender": "张三",
          "content": "你好",
          "file_path": null,
          "mtype": null
        }
      ],
      "李四": [
        {
          "id": "msg_456",
          "type": "image",
          "sender": "李四",
          "content": "C:\\path\\to\\image.jpg",
          "file_path": "C:\\path\\to\\image.jpg",
          "mtype": "image"
        }
      ]
    }
  }
}
```

#### 获取监听消息

```
GET /api/message/listen/get
```

**请求头**:
- `X-API-Key`: API 密钥

**查询参数**:
- `who` (可选): 指定聊天对象，不指定则获取所有监听窗口的消息
- `savepic` (可选): 是否保存图片，默认 false
- `savefile` (可选): 是否保存文件，默认 false
- `savevoice` (可选): 是否保存语音，默认 false
- `savevideo` (可选): 是否保存视频，默认 false（仅 wxautox 支持）
- `parseurl` (可选): 是否解析 URL，默认 false（仅 wxautox 支持）

**响应**:
```json
{
  "code": 0,
  "message": "获取成功",
  "data": {
    "messages": {
      "张三": [
        {
          "id": "msg_123",
          "type": "text",
          "sender": "张三",
          "content": "你好",
          "file_path": null,
          "mtype": null
        }
      ]
    }
  }
}
```

#### 添加监听聊天

```
POST /api/message/listen/add
```

**请求头**:
- `X-API-Key`: API 密钥

**请求体**:
```json
{
  "nickname": "聊天对象名称"
}
```

**响应**:
```json
{
  "code": 0,
  "message": "添加成功",
  "data": {
    "who": "聊天对象名称"
  }
}
```

#### 添加当前聊天到监听

```
POST /api/message/listen/add-current
```

**请求头**:
- `X-API-Key`: API 密钥

**响应**:
```json
{
  "code": 0,
  "message": "添加成功",
  "data": {
    "who": "当前聊天对象名称"
  }
}
```

#### 移除监听聊天

```
POST /api/message/listen/remove
```

**请求头**:
- `X-API-Key`: API 密钥

**请求体**:
```json
{
  "nickname": "聊天对象名称"
}
```

**响应**:
```json
{
  "code": 0,
  "message": "移除成功",
  "data": {
    "who": "聊天对象名称"
  }
}
```

#### 获取监听列表

```
GET /api/message/listen/list
```

**请求头**:
- `X-API-Key`: API 密钥

**响应**:
```json
{
  "code": 0,
  "message": "获取成功",
  "data": {
    "listen_list": ["张三", "李四", "文件传输助手"]
  }
}
```

### 聊天窗口相关

#### 发送消息到聊天窗口

```
POST /api/chat-window/message/send
```

**请求头**:
- `X-API-Key`: API 密钥

**请求体**:
```json
{
  "who": "聊天对象名称",
  "message": "消息内容",
  "at_list": ["@的人1", "@的人2"],  // 可选
  "clear": true                    // 可选，是否清空输入框
}
```

**响应**:
```json
{
  "code": 0,
  "message": "发送成功",
  "data": {
    "message_id": "success"
  }
}
```

#### 发送打字消息到聊天窗口

```
POST /api/chat-window/message/send-typing
```

**请求头**:
- `X-API-Key`: API 密钥

**请求体**:
```json
{
  "who": "聊天对象名称",
  "message": "消息内容",
  "at_list": ["@的人1", "@的人2"],  // 可选
  "clear": true                    // 可选，是否清空输入框
}
```

**响应**:
```json
{
  "code": 0,
  "message": "发送成功",
  "data": {
    "message_id": "success"
  }
}
```

#### 发送文件到聊天窗口

```
POST /api/chat-window/message/send-file
```

**请求头**:
- `X-API-Key`: API 密钥

**请求体**:
```json
{
  "who": "聊天对象名称",
  "file_paths": [
    "C:\\path\\to\\file1.jpg",
    "C:\\path\\to\\file2.pdf"
  ]
}
```

**响应**:
```json
{
  "code": 0,
  "message": "发送完成",
  "data": {
    "success_count": 2,
    "failed_files": []
  }
}
```

#### @所有人

```
POST /api/chat-window/message/at-all
```

**请求头**:
- `X-API-Key`: API 密钥

**请求体**:
```json
{
  "who": "群聊名称",
  "message": "消息内容"  // 可选
}
```

**响应**:
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

```
GET /api/chat-window/info
```

**请求头**:
- `X-API-Key`: API 密钥

**查询参数**:
- `who`: 聊天对象名称

**响应**:
```json
{
  "code": 0,
  "message": "获取成功",
  "data": {
    "name": "群聊名称",
    "members": ["张三", "李四", "王五"],
    "is_group": true
  }
}
```

### 联系人相关

#### 获取好友列表

```
GET /api/contact/list
```

**请求头**:
- `X-API-Key`: API 密钥

**响应**:
```json
{
  "code": 0,
  "message": "获取成功",
  "data": {
    "friends": [
      {"nickname": "张三"},
      {"nickname": "李四"},
      {"nickname": "王五"}
    ]
  }
}
```

### 系统相关

#### 获取系统资源使用情况

```
GET /api/system/resources
```

**请求头**:
- `X-API-Key`: API 密钥

**响应**:
```json
{
  "code": 0,
  "message": "获取成功",
  "data": {
    "cpu_percent": 10.5,
    "memory_percent": 45.2,
    "memory_used": 4.5,
    "memory_total": 16.0
  }
}
```

### 管理员相关

#### 重新加载配置

```
POST /api/admin/reload-config
```

**请求头**:
- `X-API-Key`: API 密钥

**响应**:
```json
{
  "code": 0,
  "message": "配置已重新加载",
  "data": null
}
```

## 错误码

- `0`: 成功
- `1xxx`: 请求错误
  - `1001`: 无效的 API 密钥
  - `1002`: 缺少必要参数
- `2xxx`: 微信错误
  - `2001`: 微信未初始化
  - `2002`: 微信连接失败
- `3xxx`: 操作错误
  - `3001`: 发送失败
  - `3002`: 获取消息失败
- `4xxx`: 资源错误
  - `4001`: 文件不存在
  - `4002`: 文件读取失败
- `5xxx`: 服务器错误
  - `5000`: 服务器内部错误
  - `5001`: 配置错误

## 库差异

wxauto_http_api 支持两种微信自动化库：wxauto（开源）和 wxautox（付费）。两种库在功能上有一些差异：

| 功能 | wxauto | wxautox |
|-----|--------|---------|
| 发送消息 | ✓ | ✓ |
| 接收消息 | ✓ | ✓ |
| 发送文件 | ✓ | ✓ |
| 保存图片 | ✓ | ✓ |
| 保存视频 | ✗ | ✓ |
| 解析 URL | ✗ | ✓ |
| 清空输入框 | ✓ (模拟) | ✓ (原生) |
| 打字消息 | ✗ (使用普通消息代替) | ✓ |
| @所有人 | ✓ | ✓ |

注意：当使用 wxauto 库时，不支持的功能会被忽略或使用替代方法实现。
