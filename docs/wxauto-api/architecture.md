# wxauto_http_api 项目架构文档

## 项目概述

wxauto_http_api 是一个基于 wxauto/wxautox 的微信自动化 HTTP API 服务，提供了完整的 HTTP 接口，使开发者能够通过 HTTP 请求控制微信客户端，实现消息发送、接收、文件传输等功能。

## 目录结构

```
wxauto_http_api/
├── app/                    # 应用核心代码
│   ├── __init__.py         # 应用初始化
│   ├── api/                # API 路由
│   │   ├── __init__.py
│   │   ├── routes.py       # 主要 API 路由
│   │   └── admin_routes.py # 管理员 API 路由
│   ├── config.py           # 配置管理
│   ├── logs.py             # 日志管理
│   ├── wechat.py           # 微信管理器
│   ├── wechat_adapter.py   # 微信适配器
│   ├── wechat_init.py      # 微信初始化
│   ├── api_queue.py        # API 队列处理
│   ├── auth.py             # 认证管理
│   ├── system_monitor.py   # 系统监控
│   └── utils/              # 工具函数
│       ├── __init__.py
│       ├── image_utils.py  # 图片处理工具
│       └── file_utils.py   # 文件处理工具
├── data/                   # 数据目录
│   └── api/
│       ├── config/         # 配置文件
│       │   ├── app_config.json     # 应用配置
│       │   └── log_filter.json     # 日志过滤配置
│       ├── logs/           # 日志文件
│       └── temp/           # 临时文件
├── wxauto/                 # wxauto 库
├── app_ui.py               # UI 界面
├── config_manager.py       # 配置管理器
├── run.py                  # 服务启动脚本
├── start_ui.py             # UI 启动脚本
├── requirements.txt        # 依赖列表
└── .env                    # 环境变量配置
```

## 核心模块

### 1. 应用初始化 (app/\_\_init\_\_.py)

负责创建 Flask 应用实例，注册蓝图，初始化微信相关配置。

```python
def create_app():
    # 初始化微信相关配置
    from app.wechat_init import initialize as init_wechat
    init_wechat()

    # 创建 Flask 应用
    app = Flask(__name__)
    app.config.from_object(Config)

    # 注册蓝图
    from app.api.routes import api_bp
    from app.api.admin_routes import admin_bp
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')

    return app
```

### 2. 配置管理 (app/config.py)

负责加载和管理应用配置，支持从配置文件和环境变量加载配置。

```python
class Config:
    # 从配置文件或环境变量加载配置
    if config_manager:
        # 确保目录存在
        config_manager.ensure_dirs()

        # 加载应用配置
        app_config = config_manager.load_app_config()

        # API配置
        API_KEYS = app_config.get('api_keys', ['test-key-2'])

        # Flask配置
        PORT = app_config.get('port', 5000)

        # 微信库选择配置
        WECHAT_LIB = app_config.get('wechat_lib', 'wxauto').lower()
    else:
        # 如果无法导入config_manager，则使用环境变量
        API_KEYS = os.getenv('API_KEYS', 'test-key-2').split(',')
        PORT = int(os.getenv('PORT', 5000))
        WECHAT_LIB = os.getenv('WECHAT_LIB', 'wxauto').lower()
```

### 3. 微信管理器 (app/wechat.py)

负责管理微信实例，提供初始化、获取实例、检查连接状态等功能。

```python
class WeChatManager:
    def __init__(self):
        self._instance = None
        self._lock = threading.Lock()
        self._last_check = 0
        self._check_interval = Config.WECHAT_CHECK_INTERVAL
        self._reconnect_delay = Config.WECHAT_RECONNECT_DELAY
        self._max_retry = Config.WECHAT_MAX_RETRY
        self._monitor_thread = None
        self._running = False
        self._retry_count = 0
        self._adapter = wechat_adapter

    def initialize(self):
        """初始化微信实例"""
        with self._lock:
            success = self._adapter.initialize()
            if success:
                self._instance = self._adapter.get_instance()
                if Config.WECHAT_AUTO_RECONNECT:
                    self._start_monitor()
                self._retry_count = 0
                logger.info(f"微信初始化成功，使用库: {self._adapter.get_lib_name()}")
            return success

    def get_instance(self):
        """获取微信实例"""
        return self._adapter
```

### 4. 微信适配器 (app/wechat_adapter.py)

负责适配 wxauto 和 wxautox 两种库，提供统一的接口，处理两种库之间的差异。

```python
class WeChatAdapter:
    """微信自动化库适配器，支持wxauto和wxautox"""

    def __init__(self, lib_name: str = 'wxauto'):
        """
        初始化适配器

        Args:
            lib_name: 指定使用的库名称，可选值: 'wxauto', 'wxautox'，默认为'wxauto'
        """
        self._instance = None
        self._lib_name = None
        self._lock = threading.Lock()
        self._listen = {}  # 添加listen属性

        # 根据指定的库名称导入相应的库
        if lib_name.lower() == 'wxautox':
            if not self._try_import_wxautox():
                logger.error("无法导入wxautox库")
                raise ImportError("无法导入wxautox库，请确保已正确安装")
        else:  # 默认使用wxauto
            if not self._try_import_wxauto():
                logger.error("无法导入wxauto库")
                raise ImportError("无法导入wxauto库，请确保已正确安装")
```

### 5. API 路由 (app/api/routes.py)

负责定义 API 路由，处理 HTTP 请求，调用微信功能。

```python
@api_bp.route('/message/send', methods=['POST'])
@require_api_key
def send_message():
    # 在队列处理前获取所有请求数据
    try:
        data = request.get_json()
        receiver = data.get('receiver')
        message = data.get('message')
        at_list = data.get('at_list', [])
        clear = "1" if data.get('clear', True) else "0"

        if not receiver or not message:
            return jsonify({
                'code': 1002,
                'message': '缺少必要参数',
                'data': None
            }), 400

        # 将任务加入队列处理
        result = _send_message_task(receiver, message, at_list, clear)

        # 处理队列任务返回的结果
        if isinstance(result, dict) and 'response' in result and 'status_code' in result:
            return jsonify(result['response']), result['status_code']
```

### 6. 认证管理 (app/auth.py)

负责 API 认证，验证 API 密钥。

```python
def require_api_key(f):
    """API密钥认证装饰器"""
    @wraps(f)
    def decorated(*args, **kwargs):
        # 获取API密钥
        api_key = request.headers.get('X-API-Key')
        
        # 检查API密钥是否有效
        if not api_key or api_key not in Config.API_KEYS:
            return jsonify({
                'code': 1001,
                'message': '无效的API密钥',
                'data': None
            }), 401
            
        # 将API密钥存储在g对象中，以便在视图函数中使用
        g.api_key = api_key
        
        return f(*args, **kwargs)
    return decorated
```

### 7. 日志管理 (app/logs.py)

负责日志记录和管理，支持日志过滤和格式化。

```python
class WeChatLibAdapter(logging.LoggerAdapter):
    """
    日志适配器，添加当前使用的库信息
    """
    _lib_name = "wxauto"  # 默认库名称
    
    def __init__(self, logger, lib_name="wxauto"):
        """
        初始化适配器
        
        Args:
            logger: 原始logger
            lib_name: 库名称
        """
        super().__init__(logger, {})
        self._lib_name = lib_name
        
    def process(self, msg, kwargs):
        """
        处理日志消息，添加库名称
        """
        kwargs["extra"] = kwargs.get("extra", {})
        kwargs["extra"]["wechat_lib"] = self._lib_name
        return msg, kwargs
```

### 8. API 队列处理 (app/api_queue.py)

负责处理 API 请求队列，避免并发问题。

```python
def queue_task(func, *args, **kwargs):
    """
    将任务加入队列处理
    
    Args:
        func: 要执行的函数
        *args: 函数参数
        **kwargs: 函数关键字参数
        
    Returns:
        任务结果
    """
    # 创建任务
    task = {
        'id': str(uuid.uuid4()),
        'func': func,
        'args': args,
        'kwargs': kwargs,
        'result': None,
        'status': 'pending',
        'error': None
    }
    
    # 将任务加入队列
    with queue_lock:
        task_queue.put(task)
        task_map[task['id']] = task
    
    # 等待任务完成
    while True:
        with queue_lock:
            if task['status'] != 'pending':
                # 从任务映射中移除任务
                task_map.pop(task['id'], None)
                break
        time.sleep(0.01)
    
    # 返回任务结果
    if task['status'] == 'error':
        raise Exception(task['error'])
    return task['result']
```

### 9. 配置管理器 (config_manager.py)

负责管理配置文件，提供配置的读写功能。

```python
def load_app_config():
    """
    加载应用配置，如果配置文件不存在，则从.env文件读取默认配置并创建配置文件

    Returns:
        dict: 应用配置
    """
    ensure_dirs()

    # 如果配置文件不存在，从.env文件读取默认配置
    if not APP_CONFIG_FILE.exists():
        # 加载.env文件
        env_file = Path(".env")
        if env_file.exists():
            load_dotenv(env_file)

            # 从环境变量读取配置
            api_keys = os.getenv('API_KEYS', 'test-key-2').split(',')
            port = int(os.getenv('PORT', 5000))
            wechat_lib = os.getenv('WECHAT_LIB', 'wxauto').lower()

            # 创建配置
            config = {
                "api_keys": api_keys,
                "port": port,
                "wechat_lib": wechat_lib
            }
        else:
            # 如果.env文件不存在，使用默认配置
            config = DEFAULT_APP_CONFIG.copy()

        # 保存配置
        save_app_config(config)
        return config
```

### 10. UI 界面 (app_ui.py)

负责提供图形用户界面，方便用户操作。

```python
class WxAutoHttpUI:
    def __init__(self, root):
        self.root = root
        self.root.title("微信自动化HTTP API")
        self.root.geometry("800x600")
        
        # 创建主框架
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建控制面板
        self.create_control_panel()
        
        # 创建日志显示区域
        self.create_log_area()
        
        # 创建选项卡
        self.create_tabs()
        
        # 初始化状态
        self.api_running = False
        self.current_lib = "wxauto"  # 默认使用wxauto
        self.current_port = 5000     # 默认端口号
```

## 数据流

1. **HTTP 请求流程**:
   - 客户端发送 HTTP 请求到 API 端点
   - Flask 路由处理请求，验证 API 密钥
   - 请求参数被解析并验证
   - 请求被加入队列处理
   - 队列处理器执行请求，调用微信功能
   - 结果被返回给客户端

2. **微信消息接收流程**:
   - 客户端发送请求获取新消息
   - API 调用微信适配器的 GetNextNewMessage 方法
   - 微信适配器处理库差异，调用实际的微信实例方法
   - 消息被处理并格式化
   - 结果被返回给客户端

3. **微信消息发送流程**:
   - 客户端发送请求发送消息
   - API 解析请求参数
   - 请求被加入队列处理
   - 队列处理器调用微信适配器的 SendMsg 方法
   - 微信适配器处理库差异，调用实际的微信实例方法
   - 结果被返回给客户端

## 扩展点

1. **微信库适配**:
   - 通过 WeChatAdapter 类适配不同的微信自动化库
   - 可以通过添加新的适配方法支持更多的库

2. **API 端点**:
   - 可以在 app/api/routes.py 中添加新的 API 端点
   - 可以创建新的蓝图添加更多功能

3. **配置选项**:
   - 可以在 app/config.py 中添加新的配置选项
   - 可以在 config_manager.py 中添加新的配置文件处理逻辑

4. **UI 界面**:
   - 可以在 app_ui.py 中添加新的 UI 元素和功能
   - 可以创建新的选项卡添加更多功能

## 依赖关系

1. **核心依赖**:
   - Flask: Web 框架
   - wxauto/wxautox: 微信自动化库
   - python-dotenv: 环境变量加载
   - requests: HTTP 请求
   - Pillow: 图片处理

2. **模块依赖**:
   - app/\_\_init\_\_.py 依赖 app/wechat_init.py, app/config.py, app/api/routes.py
   - app/wechat.py 依赖 app/wechat_adapter.py, app/config.py, app/logs.py
   - app/api/routes.py 依赖 app/wechat.py, app/auth.py, app/api_queue.py
   - app_ui.py 依赖 config_manager.py, app/config.py, app/logs.py

## 配置项

1. **API 配置**:
   - API_KEYS: API 密钥列表
   - SECRET_KEY: 密钥
   - PORT: 监听端口
   - HOST: 监听地址

2. **微信配置**:
   - WECHAT_LIB: 使用的微信库，可选值: 'wxauto', 'wxautox'
   - WECHAT_CHECK_INTERVAL: 连接检查间隔（秒）
   - WECHAT_AUTO_RECONNECT: 是否自动重连
   - WECHAT_RECONNECT_DELAY: 重连延迟（秒）
   - WECHAT_MAX_RETRY: 最大重试次数

3. **日志配置**:
   - LOG_LEVEL: 日志级别
   - LOG_FORMAT: 日志格式
   - LOG_DATE_FORMAT: 日志日期格式
   - LOG_FILENAME: 日志文件名

## 注意事项

1. **线程安全**:
   - 使用线程锁保护共享资源
   - 使用队列处理并发请求
   - 在多线程环境中使用 COM 对象时初始化 COM 环境

2. **错误处理**:
   - 捕获并记录所有异常
   - 返回统一的错误响应格式
   - 使用错误码标识不同类型的错误

3. **资源管理**:
   - 正确释放 COM 资源
   - 清理临时文件
   - 停止服务时关闭所有线程

4. **配置管理**:
   - 优先使用配置文件
   - 如果配置文件不存在，使用环境变量
   - 如果环境变量不存在，使用默认值

5. **库差异处理**:
   - 处理 wxauto 和 wxautox 之间的差异
   - 对不支持的功能提供替代实现或忽略
   - 记录库差异相关的警告日志
