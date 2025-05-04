# wxauto_Mgt Web管理界面

wxauto_Mgt Web管理界面是一个基于FastAPI和Vue.js的Web应用，提供对wxauto_Mgt系统的远程管理能力。通过Web界面，用户可以远程监控和管理wxauto实例、服务平台和消息转发规则，查看实时消息流和系统状态。

## 功能特点

- **实例管理**：查看、添加、编辑和删除wxauto实例
- **服务平台管理**：配置Dify、OpenAI等服务平台
- **规则管理**：设置消息转发规则和优先级
- **消息监控**：查看实时消息流和处理状态
- **系统监控**：查看系统状态和性能指标
- **用户管理**：管理用户账号和权限

## 安装依赖

Web服务需要以下依赖：

```bash
pip install fastapi uvicorn pydantic python-jose[cryptography] passlib[bcrypt]
```

## 使用方法

### 在wxauto_Mgt中启动Web服务

```python
from wxauto_mgt.web import start_web_service

# 配置Web服务
config = {
    "port": 8443,
    "host": "0.0.0.0",
    "debug": False,
    "reload": False,
    "workers": 1,
    "ssl_certfile": None,
    "ssl_keyfile": None,
}

# 启动Web服务
await start_web_service(config)
```

### 停止Web服务

```python
from wxauto_mgt.web import stop_web_service

# 停止Web服务
await stop_web_service()
```

### 检查Web服务状态

```python
from wxauto_mgt.web import is_web_service_running

# 检查Web服务是否运行
if is_web_service_running():
    print("Web服务正在运行")
else:
    print("Web服务未运行")
```

### 获取和设置Web服务配置

```python
from wxauto_mgt.web import get_web_service_config, set_web_service_config

# 获取当前配置
config = get_web_service_config()
print(f"当前端口: {config['port']}")

# 更新配置
set_web_service_config({"port": 8080})
```

## API文档

启动Web服务后，可以通过以下URL访问API文档：

- Swagger UI: `http://localhost:8443/api/docs`
- ReDoc: `http://localhost:8443/api/redoc`

## WebSocket接口

Web服务提供以下WebSocket接口：

- 消息实时流: `ws://localhost:8443/ws/messages?token=<token>`
- 状态实时更新: `ws://localhost:8443/ws/status?token=<token>`

## 前端开发

前端代码位于`wxauto_mgt/web/frontend`目录下，基于Vue.js 3和Element Plus开发。

### 开发环境

```bash
# 进入前端目录
cd wxauto_mgt/web/frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

### 构建生产版本

```bash
# 构建生产版本
npm run build
```

构建后的文件将位于`dist`目录，FastAPI将自动提供这些静态文件。

## 安全注意事项

1. **生产环境配置**：
   - 使用HTTPS（配置SSL证书）
   - 更改默认密钥
   - 限制CORS域名

2. **认证**：
   - 默认用户名/密码：admin/admin
   - 生产环境中应更改默认密码
   - 考虑集成更强大的认证系统

## 故障排除

1. **Web服务无法启动**：
   - 检查端口是否被占用
   - 确保已安装所有依赖
   - 查看日志获取详细错误信息

2. **无法连接到Web服务**：
   - 确认主机和端口配置正确
   - 检查防火墙设置
   - 验证网络连接

3. **认证失败**：
   - 确认用户名和密码正确
   - 检查令牌是否过期
   - 验证认证头格式是否正确

## 示例代码

查看`wxauto_mgt/web/integration_example.py`获取完整的集成示例。
