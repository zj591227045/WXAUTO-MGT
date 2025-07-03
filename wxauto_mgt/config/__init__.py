"""
配置模块

提供应用程序配置和版本信息。
"""

import os
import json
from pathlib import Path

# 应用版本
__version__ = "2.0.0"

def get_version():
    """
    获取应用程序版本
    
    Returns:
        str: 应用程序版本
    """
    try:
        # 尝试从配置文件中读取版本信息
        config_path = Path(__file__).parent / "default_config.json"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                if "app" in config and "version" in config["app"]:
                    return config["app"]["version"]
    except Exception:
        pass
    
    # 如果无法从配置文件中读取，则返回硬编码的版本
    return __version__
