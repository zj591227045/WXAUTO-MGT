"""
Web服务配置模块

定义Web服务的配置项和默认值。
"""

import os
from typing import Dict, Any

# 默认配置
DEFAULT_CONFIG: Dict[str, Any] = {
    # 服务器配置
    "port": 8443,
    "host": "0.0.0.0",
    "debug": False,
    "reload": False,
    "workers": 1,
    "ssl_certfile": None,
    "ssl_keyfile": None,
    
    # 认证配置
    "auth_enabled": True,
    "token_expire_minutes": 1440,  # 24小时
    "secret_key": "wxauto_mgt_web_service_secret_key",  # 应该在生产环境中更改
    
    # CORS配置
    "cors_origins": ["*"],  # 在生产环境中应该限制为特定域名
    "cors_allow_credentials": True,
    "cors_allow_methods": ["*"],
    "cors_allow_headers": ["*"],
    
    # 日志配置
    "log_level": "info",
    
    # 静态文件配置
    "static_dir": os.path.join(os.path.dirname(__file__), "frontend", "dist"),
    
    # 数据库配置
    "db_path": None,  # 使用主程序的数据库路径
}

# 当前配置
current_config = DEFAULT_CONFIG.copy()

def get_config() -> Dict[str, Any]:
    """
    获取当前配置
    
    Returns:
        Dict[str, Any]: 当前配置
    """
    global current_config
    return current_config.copy()

def update_config(config: Dict[str, Any]) -> None:
    """
    更新配置
    
    Args:
        config: 新配置
    """
    global current_config
    current_config.update(config)

def reset_config() -> None:
    """重置为默认配置"""
    global current_config
    current_config = DEFAULT_CONFIG.copy()
