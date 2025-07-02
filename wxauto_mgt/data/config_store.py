"""
配置存储模块

负责管理系统配置信息，支持加密存储敏感信息。
支持多实例配置管理。
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Any, Union
from cryptography.fernet import Fernet

from ..data.db_manager import db_manager

logger = logging.getLogger(__name__)

class ConfigStore:
    """配置存储管理器，负责管理系统配置"""

    def __init__(self):
        """初始化配置存储管理器"""
        self._lock = asyncio.Lock()
        self._config_cache = {}
        self._crypto = None

    def init_encryption(self, key: bytes):
        """
        初始化加密功能

        Args:
            key: 加密密钥
        """
        self._crypto = Fernet(key)

    async def set_config(self, section: str, key: str, value: Any, encrypted: bool = False) -> bool:
        """
        设置配置项

        Args:
            section: 配置分区
            key: 配置键
            value: 配置值
            encrypted: 是否加密存储

        Returns:
            bool: 是否成功设置
        """
        try:
            # 序列化值
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            else:
                value = str(value)

            # 加密处理
            if encrypted:
                if not self._crypto:
                    raise RuntimeError("未初始化加密功能")
                value = self._crypto.encrypt(value.encode()).decode()

            # 准备数据
            config_key = f"{section}.{key}"
            data = {
                'key': config_key,
                'value': value,
                'encrypted': int(encrypted),
                'create_time': int(time.time()),
                'last_update': int(time.time())
            }

            # 更新或插入
            existing = await db_manager.fetchone(
                "SELECT key FROM configs WHERE key = ?",
                (config_key,)
            )

            if existing:
                await db_manager.update('configs', data, {'key': config_key})
            else:
                await db_manager.insert('configs', data)

            # 更新缓存
            self._config_cache[config_key] = value

            logger.debug(f"配置已保存: {config_key}")
            return True
        except Exception as e:
            logger.error(f"保存配置失败: {str(e)}")
            return False

    async def get_config(self, section: str, key: str, default: Any = None) -> Any:
        """
        获取配置项

        Args:
            section: 配置分区
            key: 配置键
            default: 默认值

        Returns:
            Any: 配置值
        """
        try:
            # 先从缓存获取
            config_key = f"{section}.{key}"
            if config_key in self._config_cache:
                return self._config_cache[config_key]

            # 从数据库获取
            sql = "SELECT * FROM configs WHERE key = ?"
            config = await db_manager.fetchone(sql, (config_key,))

            if not config:
                return default

            value = config['value']

            # 解密处理
            if config['encrypted']:
                if not self._crypto:
                    raise RuntimeError("未初始化加密功能")
                value = self._crypto.decrypt(value.encode()).decode()

            # 反序列化
            try:
                value = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                pass

            # 更新缓存
            self._config_cache[config_key] = value
            return value
        except Exception as e:
            logger.error(f"获取配置失败: {str(e)}")
            return default

    async def delete_config(self, section: str, key: str) -> bool:
        """
        删除配置项

        Args:
            section: 配置分区
            key: 配置键

        Returns:
            bool: 是否成功删除
        """
        try:
            config_key = f"{section}.{key}"
            await db_manager.delete('configs', {'key': config_key})

            # 清除缓存
            self._config_cache.pop(config_key, None)

            logger.debug(f"配置已删除: {config_key}")
            return True
        except Exception as e:
            logger.error(f"删除配置失败: {str(e)}")
            return False

    def get_config_sync(self, section: str, key: str, default: Any = None) -> Any:
        """
        同步获取配置项（用于非异步环境）

        Args:
            section: 配置分区
            key: 配置键
            default: 默认值

        Returns:
            Any: 配置值
        """
        try:
            # 先从缓存获取
            config_key = f"{section}.{key}"
            if config_key in self._config_cache:
                return self._config_cache[config_key]

            # 从数据库获取（同步方式）
            conn = db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM configs WHERE key = ?", (config_key,))
            config = cursor.fetchone()

            if not config:
                cursor.close()
                conn.close()
                return default

            # 将结果转换为字典（在cursor关闭前）
            column_names = [desc[0] for desc in cursor.description]
            config = dict(zip(column_names, config))
            cursor.close()
            conn.close()

            value = config['value']

            # 解密处理
            if config['encrypted']:
                if not self._crypto:
                    raise RuntimeError("未初始化加密功能")
                value = self._crypto.decrypt(value.encode()).decode()

            # 反序列化
            try:
                value = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                pass

            # 更新缓存
            self._config_cache[config_key] = value
            return value
        except Exception as e:
            logger.error(f"同步获取配置失败: {str(e)}")
            import traceback
            logger.error(f"同步获取配置异常详情: {traceback.format_exc()}")
            return default

    async def get_section_configs(self, section: str) -> Dict[str, Any]:
        """
        获取分区的所有配置

        Args:
            section: 配置分区

        Returns:
            Dict[str, Any]: 配置字典
        """
        try:
            sql = "SELECT * FROM configs WHERE key LIKE ?"
            configs = await db_manager.fetchall(sql, (f"{section}:%",))

            result = {}
            for config in configs:
                key = config['key'].split(':', 1)[1]
                value = config['value']

                # 解密处理
                if config['encrypted']:
                    if not self._crypto:
                        raise RuntimeError("未初始化加密功能")
                    value = self._crypto.decrypt(value.encode()).decode()

                # 反序列化
                try:
                    value = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    pass

                result[key] = value

            return result
        except Exception as e:
            logger.error(f"获取分区配置失败: {str(e)}")
            return {}

    async def clear_configs(self, section: str) -> bool:
        """
        清除分区的所有配置

        Args:
            section: 配置分区

        Returns:
            bool: 是否成功清除
        """
        try:
            # 删除数据库中的配置
            await db_manager.execute(
                "DELETE FROM configs WHERE key LIKE ?",
                (f"{section}.%",)
            )

            # 清除缓存
            keys_to_remove = [k for k in self._config_cache if k.startswith(f"{section}.")]
            for key in keys_to_remove:
                self._config_cache.pop(key, None)

            logger.debug(f"分区配置已清除: {section}")
            return True
        except Exception as e:
            logger.error(f"清除分区配置失败: {str(e)}")
            return False

# 创建全局实例
config_store = ConfigStore()