# 实例卡片登录功能说明

## 功能概述

为程序端和web端的实例卡片添加了自动登录和获取登录二维码的功能，支持微信自动登录和二维码扫码登录。

## 新增功能

### 1. 自动登录按钮
- **位置**: 实例卡片的操作按钮区域
- **功能**: 调用微信自动登录API，尝试自动登录微信
- **流程**: 
  1. 点击"自动登录"按钮
  2. 调用 `/api/auxiliary/login/auto` 接口
  3. 如果登录成功，自动开始微信初始化循环
  4. 初始化成功后重新启动消息监听

### 2. 登录二维码按钮
- **位置**: 实例卡片的操作按钮区域
- **功能**: 获取微信登录二维码，支持扫码登录
- **流程**:
  1. 点击"登录码"按钮
  2. 调用 `/api/auxiliary/login/qrcode` 接口
  3. 显示二维码对话框/模态框
  4. 用户扫码登录后点击"登录成功"
  5. 自动开始微信初始化循环
  6. 初始化成功后重新启动消息监听

## 技术实现

### 程序端 (Qt/PySide6)

#### 实例卡片 (InstanceCard)
- 新增信号: `auto_login_requested`, `qrcode_requested`
- 新增按钮: 自动登录按钮、获取登录二维码按钮
- 按钮布局: 多行布局设计，避免按钮遮挡
  - 第一行: 编辑、删除按钮（并排显示）
  - 第二行: 自动登录按钮（占满整行）
  - 第三行: 获取登录二维码按钮（占满整行）
- 按钮样式: 绿色自动登录按钮、紫色二维码按钮
- 卡片高度: 自适应调整，最小高度160px

#### 实例管理面板 (InstanceManagerPanel)
- 新增方法:
  - `_auto_login_instance()`: 处理自动登录请求
  - `_qrcode_instance()`: 处理二维码登录请求
  - `_show_qrcode_dialog()`: 显示二维码对话框
  - `_start_wechat_initialization_loop()`: 微信初始化循环
  - `_restart_message_listening()`: 重启消息监听

### Web端 (JavaScript)

#### 实例卡片
- 新增按钮: 自动登录按钮、登录码按钮
- 使用Bootstrap样式

#### JavaScript函数
- `autoLogin(instanceId)`: 自动登录功能
- `showQRCodeLogin(instanceId)`: 显示二维码登录
- `showQRCodeModal()`: 显示二维码模态框
- `startWeChatInitializationLoop()`: 微信初始化循环

## API接口

### 自动登录接口
```
POST /api/auxiliary/login/auto
Content-Type: application/json
X-API-Key: your-api-key

{
  "timeout": 10
}
```

**响应示例**:
```json
{
  "code": 0,
  "message": "自动登录执行完成",
  "data": {
    "login_result": true,
    "success": true
  }
}
```

### 获取登录二维码接口
```
POST /api/auxiliary/login/qrcode
Content-Type: application/json
X-API-Key: your-api-key

{}
```

**响应示例**:
```json
{
  "code": 0,
  "message": "获取登录二维码成功",
  "data": {
    "qrcode_data_url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...",
    "mime_type": "image/png"
  }
}
```

## 微信初始化循环

登录成功后，系统会自动执行以下流程：

1. **循环调用微信初始化接口** (`/api/wechat/initialize`)
2. **检查连接状态**: 直到返回 `status: "connected"`
3. **重启消息监听**: 停止当前监听并重新启动
4. **最大尝试次数**: 30次，每次间隔2秒

## 错误处理

- **网络错误**: 显示网络连接失败提示
- **API错误**: 显示具体的错误信息
- **超时处理**: 达到最大尝试次数后显示超时提示
- **用户取消**: 支持用户随时取消操作

## 用户界面

### 程序端
- 按钮布局: 多行布局设计
  - 第一行: 编辑、删除按钮（右对齐）
  - 第二行: 自动登录按钮（占满整行）
  - 第三行: 获取登录二维码按钮（占满整行）
- 按钮样式: 现代化扁平设计，带悬停效果
- 卡片尺寸: 自适应高度，最小160px
- 对话框: 原生Qt对话框，支持二维码图片显示

### Web端
- 按钮位置: 实例卡片操作区域
- 按钮样式: Bootstrap按钮样式
- 模态框: Bootstrap模态框，响应式设计

## 注意事项

1. **API密钥**: 确保实例配置了正确的API密钥
2. **网络连接**: 确保能够访问实例的API地址
3. **微信状态**: 登录前确保微信客户端处于可登录状态
4. **权限要求**: 某些操作可能需要管理员权限

## 兼容性

- **程序端**: 支持Windows、Linux、macOS
- **Web端**: 支持现代浏览器 (Chrome, Firefox, Safari, Edge)
- **向后兼容**: 不影响现有功能，完全向后兼容
