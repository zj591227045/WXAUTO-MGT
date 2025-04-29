"""
配置管理器模块

负责管理应用程序配置，包括加载、保存和加密存储配置数据。支持从默认配置文件、
数据库和环境变量加载配置，并提供配置项的验证功能。支持多实例管理。
"""

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import logging

from ..data.db_manager import db_manager

logger = logging.getLogger(__name__)

class ConfigError(Exception):
    """配置错误异常"""
    pass

class ConfigManager:
    """配置管理器，负责管理应用程序配置"""

    def __init__(self):
        """初始化配置管理器"""
        self._config = {}  # 当前配置
        self._initialized = False
        self._default_config_path = None
        self._cipher = None  # 加密工具
        self._salt = b'wxauto_mgt_salt'  # 盐值，用于生成加密密钥
        self._encryption_key = None  # 加密密钥
        self._encryption_key_id = 1  # 加密密钥ID
        self._legacy_ciphers = {}  # 旧密钥字典，用于解密历史数据
        self._lock = asyncio.Lock()

        logger.debug("初始化配置管理器")

    async def initialize(self, default_config_path: Optional[str] = None,
                        encryption_key: Optional[str] = None,
                        encryption_key_id: int = 1) -> None:
        """
        初始化配置管理器

        Args:
            default_config_path: 默认配置文件路径，默认为None（使用应用目录下的config/default_config.json）
            encryption_key: 加密密钥，默认为None（使用默认密钥）
            encryption_key_id: 加密密钥ID，用于密钥轮换
        """
        if self._initialized:
            logger.warning("配置管理器已经初始化")
            return

        # 设置默认配置文件路径
        if default_config_path is None:
            app_dir = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            self._default_config_path = app_dir / "config" / "default_config.json"
        else:
            self._default_config_path = Path(default_config_path)

        # 初始化加密工具
        self._encryption_key_id = encryption_key_id
        await self._init_encryption(encryption_key)

        # 加载配置
        await self.load_config()

        self._initialized = True
        logger.info("配置管理器初始化完成")

    async def _init_encryption(self, encryption_key: Optional[str] = None) -> None:
        """
        初始化加密工具

        Args:
            encryption_key: 加密密钥，如果为None则使用默认密钥
        """
        # 如果未提供密钥，使用默认密钥
        if encryption_key is None:
            encryption_key = "wxauto_mgt_default_key"

        self._encryption_key = encryption_key

        # 使用PBKDF2生成加密密钥
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self._salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(encryption_key.encode()))

        # 创建Fernet对象
        self._cipher = Fernet(key)
        logger.debug("加密工具初始化完成")

    async def add_legacy_key(self, key_id: int, encryption_key: str) -> None:
        """
        添加旧密钥，用于解密历史数据

        Args:
            key_id: 密钥ID
            encryption_key: 加密密钥
        """
        if key_id == self._encryption_key_id:
            logger.warning(f"密钥ID {key_id} 是当前正在使用的密钥，不需要添加为旧密钥")
            return

        # 生成密钥
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self._salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(encryption_key.encode()))

        # 创建Fernet对象并保存
        self._legacy_ciphers[key_id] = Fernet(key)
        logger.info(f"已添加旧密钥: ID={key_id}")

    def encrypt(self, data: str) -> str:
        """
        加密数据

        Args:
            data: 要加密的数据

        Returns:
            str: 加密后的数据（Base64编码）
        """
        if self._cipher is None:
            raise ConfigError("加密工具未初始化")

        encrypted = self._cipher.encrypt(data.encode())
        return base64.urlsafe_b64encode(encrypted).decode()

    def decrypt(self, encrypted_data: str) -> str:
        """
        解密数据，支持多密钥解密

        Args:
            encrypted_data: 加密的数据（Base64编码）

        Returns:
            str: 解密后的数据
        """
        if self._cipher is None:
            raise ConfigError("加密工具未初始化")

        try:
            decoded = base64.urlsafe_b64decode(encrypted_data.encode())

            # 首先尝试使用当前密钥解密
            try:
                decrypted = self._cipher.decrypt(decoded)
                return decrypted.decode()
            except Exception:
                # 如果当前密钥解密失败，尝试使用旧密钥
                for key_id, cipher in self._legacy_ciphers.items():
                    try:
                        decrypted = cipher.decrypt(decoded)
                        logger.debug(f"使用旧密钥 (ID={key_id}) 成功解密数据")
                        return decrypted.decode()
                    except Exception:
                        continue

                raise ConfigError("无法使用任何密钥解密数据")
        except Exception as e:
            logger.error(f"解密数据失败: {e}")
            raise ConfigError(f"解密数据失败: {e}")

    async def load_config(self) -> Dict:
        """
        加载配置

        Returns:
            Dict: 加载的配置
        """
        try:
            # 加载默认配置
            default_config = await self._load_default_config()

            # 加载数据库配置
            db_config = await self._load_db_config()

            # 合并配置
            self._config = self._merge_configs(default_config, db_config)

            logger.info("配置加载完成")
            return self._config
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            raise

    async def _load_default_config(self) -> Dict:
        """
        加载默认配置

        Returns:
            Dict: 默认配置
        """
        try:
            if not self._default_config_path.exists():
                logger.warning(f"默认配置文件不存在: {self._default_config_path}")
                return {}

            with open(self._default_config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            logger.debug(f"已加载默认配置: {self._default_config_path}")
            return config
        except Exception as e:
            logger.error(f"加载默认配置失败: {e}")
            return {}

    async def _load_db_config(self) -> Dict:
        """
        从数据库加载配置

        Returns:
            Dict: 数据库配置
        """
        try:
            rows = await db_manager.fetchall("SELECT * FROM configs")

            config = {}
            for row in rows:
                key = row['key']
                value = row['value']
                encrypted = row['encrypted']

                if encrypted:
                    try:
                        value = self.decrypt(value)
                    except Exception as e:
                        logger.error(f"解密配置项 {key} 失败: {e}")
                        continue

                try:
                    # 尝试解析JSON值
                    value = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    pass

                self._set_nested_key(config, key, value)

            logger.debug("已加载数据库配置")
            return config
        except Exception as e:
            logger.error(f"加载数据库配置失败: {e}")
            return {}

    def _set_nested_key(self, config: Dict, key: str, value: Any) -> None:
        """
        设置嵌套键值

        Args:
            config: 配置字典
            key: 键路径（使用.分隔）
            value: 值
        """
        keys = key.split('.')
        current = config

        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]

        current[keys[-1]] = value

    def _merge_configs(self, default_config: Dict, override_config: Dict) -> Dict:
        """
        合并配置

        Args:
            default_config: 默认配置
            override_config: 覆盖配置

        Returns:
            Dict: 合并后的配置
        """
        result = default_config.copy()

        def merge_dict(target, source):
            for key, value in source.items():
                if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                    merge_dict(target[key], value)
                else:
                    target[key] = value

        merge_dict(result, override_config)
        return result

    async def save_config(self) -> bool:
        """
        保存配置到数据库

        Returns:
            bool: 是否成功保存
        """
        try:
            # 展平配置
            flat_config = self._flatten_config(self._config)

            async with self._lock:
                # 获取现有配置
                existing_keys = set()
                rows = await db_manager.fetchall("SELECT key FROM configs")
                for row in rows:
                    existing_keys.add(row['key'])

                # 更新或插入配置
                now = int(time.time())
                for key, value in flat_config.items():
                    # 确定是否需要加密
                    should_encrypt = self._should_encrypt(key)

                    # 准备值
                    if isinstance(value, (dict, list)):
                        value = json.dumps(value)
                    else:
                        value = str(value)

                    if should_encrypt:
                        value = self.encrypt(value)

                    if key in existing_keys:
                        # 更新现有配置
                        await db_manager.execute(
                            """UPDATE configs
                               SET value = ?, encrypted = ?, last_update = ?
                               WHERE key = ?""",
                            (value, should_encrypt, now, key)
                        )
                    else:
                        # 插入新配置
                        await db_manager.execute(
                            """INSERT INTO configs
                               (key, value, encrypted, create_time, last_update)
                               VALUES (?, ?, ?, ?, ?)""",
                            (key, value, should_encrypt, now, now)
                        )

                logger.info("配置已保存到数据库")
                return True
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            return False

    def _should_encrypt(self, key: str) -> bool:
        """
        判断配置项是否需要加密

        Args:
            key: 配置项键

        Returns:
            bool: 是否需要加密
        """
        # 需要加密的配置项模式
        patterns = [
            "*.password",
            "*.secret",
            "*.key",
            "*.token",
            "*.api_key",
            "*.access_token",
            "*.refresh_token"
        ]

        return any(self._match_pattern(key, pattern) for pattern in patterns)

    def _match_pattern(self, key: str, pattern: str) -> bool:
        """
        匹配配置项键是否符合模式

        Args:
            key: 配置项键
            pattern: 匹配模式

        Returns:
            bool: 是否匹配
        """
        if pattern == key:
            return True

        if pattern.startswith("*."):
            return key.endswith(pattern[2:])

        return False

    def _flatten_config(self, config: Dict, prefix: str = "") -> Dict:
        """
        展平配置字典

        Args:
            config: 配置字典
            prefix: 键前缀

        Returns:
            Dict: 展平后的配置字典
        """
        result = {}

        for key, value in config.items():
            new_key = f"{prefix}.{key}" if prefix else key

            if isinstance(value, dict) and not self._is_special_dict(value):
                # 递归展平嵌套字典
                result.update(self._flatten_config(value, new_key))
            else:
                result[new_key] = value

        return result

    def _is_special_dict(self, value: Dict) -> bool:
        """
        判断是否为特殊字典（不需要展平）

        Args:
            value: 字典值

        Returns:
            bool: 是否为特殊字典
        """
        # 特殊字典的特征
        special_keys = {
            "type", "value", "description", "default",  # 配置项元数据
            "host", "port", "username", "password",  # 连接配置
            "id", "name", "enabled", "config"  # 实例配置
        }

        return bool(value.keys() & special_keys)

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项值"""
        try:
            value = self._get_nested_key(self._config, key)
            return value if value is not None else default
        except Exception:
            return default

    def set(self, key: str, value: Any, save: bool = False) -> None:
        """设置配置项值"""
        self._set_nested_key(self._config, key, value)
        if save:
            asyncio.create_task(self.save_config())

    def get_all(self) -> Dict:
        """获取所有配置"""
        return self._config.copy()

    async def reset_to_default(self) -> bool:
        """重置为默认配置"""
        try:
            default_config = await self._load_default_config()
            self._config = default_config.copy()
            await self.save_config()
            logger.info("配置已重置为默认值")
            return True
        except Exception as e:
            logger.error(f"重置配置失败: {e}")
            return False

    async def validate_config(self) -> Tuple[bool, List[str]]:
        """
        验证配置

        Returns:
            Tuple[bool, List[str]]: (是否有效, 错误消息列表)
        """
        errors = []

        # 验证必需的配置项
        required_keys = [
            "database.path",
            "api.host",
            "api.port",
            "logging.level"
        ]

        for key in required_keys:
            if not self.get(key):
                errors.append(f"缺少必需的配置项: {key}")

        # 验证端口号
        api_port = self.get("api.port")
        if api_port is not None:
            try:
                port = int(api_port)
                if not (1 <= port <= 65535):
                    errors.append(f"无效的端口号: {port}")
            except ValueError:
                errors.append(f"端口号必须是整数: {api_port}")

        # 验证日志级别
        log_level = self.get("logging.level", "").upper()
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if log_level and log_level not in valid_levels:
            errors.append(f"无效的日志级别: {log_level}")

        # 验证实例配置
        instances = self.get("instances", {})
        for instance_id, instance in instances.items():
            if not isinstance(instance, dict):
                errors.append(f"无效的实例配置: {instance_id}")
                continue

            # 验证必需的实例配置项
            required_instance_keys = ["name", "base_url", "api_key"]
            for key in required_instance_keys:
                if key not in instance:
                    errors.append(f"实例 {instance_id} 缺少必需的配置项: {key}")

        return len(errors) == 0, errors

    async def add_instance(self, instance_id: str, name: str, base_url: str,
                         api_key: str, enabled: bool = True, **kwargs) -> bool:
        """
        添加实例配置

        Args:
            instance_id: 实例ID
            name: 实例名称
            base_url: API基础URL
            api_key: API密钥
            enabled: 是否启用
            **kwargs: 其他配置参数

        Returns:
            bool: 是否成功添加
        """
        try:
            logger.info(f"正在添加实例: {instance_id}, 名称: {name}")

            # 检查实例是否已存在
            query = "SELECT id FROM instances WHERE instance_id = ?"
            params = (instance_id,)
            logger.debug(f"执行查询: {query}, 参数: {params}")

            existing = await db_manager.fetchone(query, params)

            if existing:
                logger.error(f"实例 {instance_id} 已存在")
                return False

            # 检查数据库表结构
            table_info = await db_manager._get_table_structure("instances")
            column_names = {col["name"] for col in table_info}
            logger.debug(f"实例表字段: {column_names}")

            # 准备实例数据 - 适配数据库表结构
            current_time = int(time.time())
            instance_data = {}

            # 添加基本字段
            instance_data["instance_id"] = instance_id
            instance_data["name"] = name
            instance_data["base_url"] = base_url
            instance_data["api_key"] = api_key
            instance_data["status"] = "UNKNOWN"
            instance_data["enabled"] = 1 if enabled else 0

            # 根据表结构选择正确的时间字段名
            if "last_active" in column_names:
                instance_data["last_active"] = 0
            elif "last_active_time" in column_names:
                instance_data["last_active_time"] = 0

            if "created_at" in column_names:
                instance_data["created_at"] = current_time
            elif "create_time" in column_names:
                instance_data["create_time"] = current_time

            if "updated_at" in column_names:
                instance_data["updated_at"] = current_time
            elif "update_time" in column_names:
                instance_data["update_time"] = current_time

            # 准备配置字段
            if "config" in column_names:
                instance_data["config"] = json.dumps(kwargs) if kwargs else "{}"

            logger.debug(f"准备插入数据: {instance_data}")

            # 插入数据库
            try:
                result = await db_manager.insert("instances", instance_data)
                if not result:
                    logger.error(f"数据库插入实例失败: {instance_id}, 返回 ID: {result}")
                    return False
                logger.debug(f"数据库插入成功, ID: {result}")
            except Exception as db_error:
                import traceback
                logger.error(f"数据库插入异常: {str(db_error)}")
                logger.error(f"异常详情: {traceback.format_exc()}")
                raise

            # 更新内存中的配置
            instances = self.get("instances", {})
            instances[instance_id] = instance_data
            self.set("instances", instances)

            logger.info(f"已添加实例配置: {instance_id}")
            return True

        except Exception as e:
            import traceback
            logger.error(f"添加实例配置失败: {e}")
            logger.error(f"异常详情: {traceback.format_exc()}")
            return False

    async def update_instance(self, instance_id: str, updated_data: dict) -> bool:
        """
        更新实例配置

        Args:
            instance_id: 实例ID
            updated_data: 更新的配置数据

        Returns:
            bool: 是否成功更新
        """
        try:
            # 检查实例是否存在
            from ..data.db_manager import db_manager

            instance = await db_manager.fetchone(
                "SELECT * FROM instances WHERE instance_id = ?",
                (instance_id,)
            )

            if not instance:
                logger.error(f"实例 {instance_id} 不存在")
                return False

            # 准备更新数据
            update_data = {}

            # 基本字段
            if "name" in updated_data:
                update_data["name"] = updated_data["name"]
            if "base_url" in updated_data:
                update_data["base_url"] = updated_data["base_url"]
            if "api_key" in updated_data:
                update_data["api_key"] = updated_data["api_key"]
            if "enabled" in updated_data:
                update_data["enabled"] = 1 if updated_data["enabled"] else 0

            # 更新时间
            update_data["updated_at"] = int(time.time())

            # 配置字段 - 合并现有配置和新配置
            if "config" in updated_data or any(k in updated_data for k in ["timeout", "retry_limit", "poll_interval", "timeout_minutes"]):
                # 获取现有配置
                current_config = {}
                if instance.get("config"):
                    try:
                        if isinstance(instance["config"], str):
                            current_config = json.loads(instance["config"])
                        else:
                            current_config = instance["config"]
                    except Exception as e:
                        logger.error(f"解析配置失败: {e}")

                # 更新配置
                if "config" in updated_data and isinstance(updated_data["config"], dict):
                    current_config.update(updated_data["config"])

                # 单独的配置项
                for key in ["timeout", "retry_limit", "poll_interval", "timeout_minutes"]:
                    if key in updated_data:
                        current_config[key] = updated_data[key]

                # 保存配置
                update_data["config"] = json.dumps(current_config)

            # 更新数据库
            if update_data:
                result = await db_manager.update(
                    "instances",
                    update_data,
                    {"instance_id": instance_id}
                )

                logger.info(f"已更新实例配置: {instance_id}, 影响行数: {result}")

                # 更新内存中的配置
                instances = self.get("instances", {})
                if instance_id in instances:
                    instance_config = instances[instance_id]
                    instance_config.update(updated_data)
                    instance_config["last_update"] = int(time.time())
                    instances[instance_id] = instance_config
                    self.set("instances", instances)

                return True
            else:
                logger.warning(f"没有需要更新的数据: {instance_id}")
                return False

        except Exception as e:
            logger.error(f"更新实例配置失败: {e}")
            import traceback
            logger.error(f"异常堆栈: {traceback.format_exc()}")
            return False

    async def remove_instance(self, instance_id: str) -> bool:
        """
        移除实例配置

        Args:
            instance_id: 实例ID

        Returns:
            bool: 是否成功移除
        """
        try:
            instances = self.get("instances", {})

            if instance_id not in instances:
                logger.error(f"实例 {instance_id} 不存在")
                return False

            # 移除配置
            del instances[instance_id]
            self.set("instances", instances, save=True)

            logger.info(f"已移除实例配置: {instance_id}")
            return True
        except Exception as e:
            logger.error(f"移除实例配置失败: {e}")
            return False

    def get_instance_config(self, instance_id: str) -> Optional[Dict]:
        """获取实例配置"""
        instances = self.get("instances", {})
        return instances.get(instance_id)

    def get_enabled_instances(self) -> List[Dict]:
        """获取已启用的实例列表（同步方法）"""
        # 注意：这是一个同步方法，但需要访问数据库
        # 为避免异步/同步混合带来的复杂性，此处使用直接查询
        try:
            # 直接执行SQL查询（同步方式）
            conn = db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM instances WHERE enabled = 1")
            result = cursor.fetchall()
            cursor.close()

            # 将结果转换为字典列表
            instances = []
            if result:
                column_names = [desc[0] for desc in cursor.description]
                for row in result:
                    instance = dict(zip(column_names, row))
                    instances.append(instance)

            return instances
        except Exception as e:
            logger.error(f"获取已启用实例列表时出错: {e}")
            return []

    async def disable_instance(self, instance_id: str) -> bool:
        """禁用实例"""
        return await self.update_instance(instance_id, {"enabled": False})

    async def enable_instance(self, instance_id: str) -> bool:
        """启用实例"""
        return await self.update_instance(instance_id, {"enabled": True})

# 创建全局实例
config_manager = ConfigManager()