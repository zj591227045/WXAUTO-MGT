"""
Web服务配置管理模块

使用统一的配置存储机制，避免全局变量和配置不一致问题
"""

from typing import Optional
from functools import lru_cache
from wxauto_mgt.utils.logging import logger


class WebServiceConfig:
    """Web服务配置类"""

    def __init__(self):
        self._host = '0.0.0.0'
        self._port = 8080
        self._auto_start = True
        self._password = None
        self._loaded = False
        self._config_cache = None
    
    @property
    def host(self) -> str:
        """获取主机地址"""
        if not self._loaded:
            self._load_from_store()
        return self._host
    
    @property
    def port(self) -> int:
        """获取端口"""
        if not self._loaded:
            self._load_from_store()
        return self._port
    
    @property
    def auto_start(self) -> bool:
        """获取自动启动设置"""
        if not self._loaded:
            self._load_from_store()
        return self._auto_start
    
    @property
    def password(self) -> Optional[str]:
        """获取密码哈希"""
        if not self._loaded:
            self._load_from_store()
        return self._password
    
    def _load_from_store(self):
        """从配置存储加载配置（同步版本）"""
        try:
            # 使用同步方式从配置存储加载配置
            from wxauto_mgt.core.config_store import config_store
            config = config_store.get_config_sync('system', 'web_service', {})

            if config and isinstance(config, dict):
                logger.debug(f"从配置存储加载Web服务配置: {config}")
                self._apply_config(config)
            else:
                logger.debug("使用默认Web服务配置")

            self._loaded = True

        except Exception as e:
            logger.error(f"加载Web服务配置失败: {e}")
            # 使用默认值
            self._loaded = True

    
    async def initialize(self):
        """异步初始化配置"""
        try:
            from wxauto_mgt.core.config_store import config_store

            logger.debug(f"Web服务配置初始化 - 数据库路径: {config_store.db_path}")

            # 检查数据库文件是否存在
            import os
            if os.path.exists(config_store.db_path):
                logger.debug(f"Web服务配置初始化 - 数据库文件存在")
            else:
                logger.warning(f"Web服务配置初始化 - 数据库文件不存在: {config_store.db_path}")

            # 使用与主窗口完全相同的方式读取配置
            config = await config_store.get_config('system', 'web_service', {})
            logger.debug(f"Web服务配置初始化 - 从配置存储读取: {config}")
            logger.debug(f"Web服务配置初始化 - 配置类型: {type(config)}")

            # 详细调试：检查配置中的字段
            if isinstance(config, dict):
                logger.debug(f"Web服务配置初始化 - 配置字段: {list(config.keys())}")
                logger.debug(f"Web服务配置初始化 - 是否包含密码: {'password' in config}")
                if 'password' in config:
                    logger.debug(f"Web服务配置初始化 - 密码长度: {len(config['password'])}")

            # 直接查询数据库验证
            try:
                import aiosqlite
                async with aiosqlite.connect(config_store.db_path) as db:
                    cursor = await db.execute("SELECT value FROM configs WHERE key = ?", ('system.web_service',))
                    db_result = await cursor.fetchone()
                    if db_result:
                        import json
                        db_config = json.loads(db_result[0])
                        logger.debug(f"Web服务配置初始化 - 数据库直接查询结果: {db_config}")
                        logger.debug(f"Web服务配置初始化 - 数据库中是否包含密码: {'password' in db_config}")
                    else:
                        logger.warning("Web服务配置初始化 - 数据库中未找到system.web_service配置")
            except Exception as db_e:
                logger.error(f"Web服务配置初始化 - 数据库直接查询失败: {db_e}")

            # 如果读取到空字典，尝试直接查询数据库
            if not config or config == {}:
                logger.warning("Web服务配置初始化 - 读取到空配置，尝试直接查询数据库")
                try:
                    import aiosqlite
                    async with aiosqlite.connect(config_store.db_path) as db:
                        cursor = await db.execute("SELECT key, value FROM configs WHERE key LIKE 'system.web_service%'")
                        rows = await cursor.fetchall()
                        logger.debug(f"Web服务配置初始化 - 数据库查询结果: {rows}")

                        # 查询所有配置项
                        cursor = await db.execute("SELECT key, value FROM configs")
                        all_rows = await cursor.fetchall()
                        logger.debug(f"Web服务配置初始化 - 所有配置项数量: {len(all_rows)}")
                        for row in all_rows[:5]:  # 只显示前5个
                            logger.debug(f"Web服务配置初始化 - 配置项: {row}")
                except Exception as db_e:
                    logger.error(f"Web服务配置初始化 - 直接查询数据库失败: {db_e}")

            # 缓存配置
            self._config_cache = config

            # 应用配置
            self._apply_config(config)

        except Exception as e:
            logger.error(f"异步初始化Web服务配置失败: {e}")
            import traceback
            traceback.print_exc()
            # 使用默认配置
            self._apply_config({
                'host': '0.0.0.0',
                'port': 8080,
                'auto_start': True
            })

    def _apply_config(self, config):
        """应用配置"""
        if isinstance(config, dict):
            self._host = config.get('host', '0.0.0.0')
            self._port = config.get('port', 8080)
            self._auto_start = config.get('auto_start', True)
            self._password = config.get('password')
            logger.debug(f"已加载Web服务配置: host={self._host}, port={self._port}, auto_start={self._auto_start}, has_password={bool(self._password)}")
        else:
            logger.warning(f"Web服务配置格式不正确: {type(config)}, 使用默认值")

        self._loaded = True
    
    async def save_config(self, host: str = None, port: int = None, 
                         auto_start: bool = None, password: str = None):
        """保存配置到存储"""
        try:
            from wxauto_mgt.core.config_store import config_store
            
            # 获取现有配置
            existing_config = await config_store.get_config('system', 'web_service', {})
            
            # 确保配置是字典格式
            if not isinstance(existing_config, dict):
                logger.warning("现有Web服务配置格式不正确，重新初始化")
                existing_config = {}
            
            # 更新配置
            new_config = existing_config.copy()
            if host is not None:
                new_config['host'] = host
                self._host = host
            if port is not None:
                new_config['port'] = port
                self._port = port
            if auto_start is not None:
                new_config['auto_start'] = auto_start
                self._auto_start = auto_start
            if password is not None:
                from wxauto_mgt.web.security import hash_password
                new_config['password'] = hash_password(password)
                self._password = new_config['password']
            
            # 保存到存储
            await config_store.set_config('system', 'web_service', new_config)
            self._loaded = True
            
            logger.info(f"Web服务配置已保存: host={self._host}, port={self._port}, auto_start={self._auto_start}")
            return True
            
        except Exception as e:
            logger.error(f"保存Web服务配置失败: {e}")
            return False
    
    def reload(self):
        """重新加载配置"""
        self._loaded = False
        self._load_from_store()
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'host': self.host,
            'port': self.port,
            'auto_start': self.auto_start,
            'password': self.password
        }


@lru_cache()
def get_web_service_config() -> WebServiceConfig:
    """获取Web服务配置实例（单例模式）"""
    return WebServiceConfig()


# 兼容性函数，保持向后兼容
def get_web_service_config_dict() -> dict:
    """获取Web服务配置字典（兼容性函数）"""
    return get_web_service_config().to_dict()


def set_web_service_config_dict(config: dict):
    """设置Web服务配置字典（兼容性函数）"""
    web_config = get_web_service_config()
    web_config._host = config.get('host', web_config._host)
    web_config._port = config.get('port', web_config._port)
    web_config._auto_start = config.get('auto_start', web_config._auto_start)
    web_config._password = config.get('password', web_config._password)
    web_config._loaded = True
