"""
配置管理器环境变量加载补丁

修复环境变量嵌套键加载功能
"""

def patch_load_from_env(self, prefix: str = "WXAUTO_") -> Dict:
    """
    从环境变量加载配置
    
    Args:
        prefix: 环境变量前缀
        
    Returns:
        Dict: 从环境变量加载的配置
    """
    config = {}
    count = 0
    
    for key, value in os.environ.items():
        # 检查前缀
        if not key.startswith(prefix):
            continue
        
        # 移除前缀并转换为小写
        config_key = key[len(prefix):].lower()
        
        # 将下划线分隔转换为点分隔的嵌套键
        config_key = config_key.replace("_", ".")
        
        # 解析值
        if value.lower() == "true":
            parsed_value = True
        elif value.lower() == "false":
            parsed_value = False
        elif value.isdigit():
            parsed_value = int(value)
        elif value.replace(".", "", 1).isdigit() and value.count(".") == 1:
            parsed_value = float(value)
        else:
            parsed_value = value
        
        # 设置配置
        self._set_nested_key(config, config_key, parsed_value)
        count += 1
    
    logger.info(f"已从环境变量加载 {count} 个配置项")
    return config 