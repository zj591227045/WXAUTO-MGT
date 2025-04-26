"""
配置存储模块

提供应用配置的持久化、加载、加密和版本控制功能。
使用SQLite作为存储介质，支持配置的自动备份和恢复。
"""

import asyncio
import base64
import json
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app1.data.db_manager import db_manager
from app.utils.logging import get_logger

logger = get_logger()


class ConfigStore:
    """
    配置存储类，负责管理应用配置的存储、加载和版本控制
    """
    
    def __init__(self):
        """初始化配置存储"""
        self._lock = asyncio.Lock()
        self._initialized = False
        self._encryption_key = None
        self._env_loaded = False
        logger.debug("初始化配置存储")
    
    async def initialize(self) -> None:
        """
        初始化配置存储
        
        确保数据库表已经创建并且索引已建立
        """
        if self._initialized:
            logger.debug("配置存储已初始化")
            return
        
        # 确保数据库已初始化
        await db_manager.initialize()
        
        # 创建额外的索引（如果需要）
        async with self._lock:
            try:
                # 为配置表创建索引
                await db_manager.execute(
                    "CREATE INDEX IF NOT EXISTS idx_configs_key ON configs(key)"
                )
                
                # 为配置版本表创建索引
                await db_manager.execute(
                    "CREATE INDEX IF NOT EXISTS idx_config_versions_timestamp ON config_versions(timestamp)"
                )
            except Exception as e:
                logger.error(f"创建配置索引失败: {e}")
                raise
        
        self._initialized = True
        logger.info("配置存储初始化完成")
    
    def _generate_key(self, password: str, salt: Optional[bytes] = None) -> Tuple[bytes, bytes]:
        """
        根据密码生成加密密钥
        
        Args:
            password: 密码字符串
            salt: 盐值，如果未提供则生成新的盐值
            
        Returns:
            Tuple[bytes, bytes]: 密钥和盐值的元组
        """
        if salt is None:
            salt = os.urandom(16)
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key, salt
    
    async def set_encryption_password(self, password: str) -> bool:
        """
        设置加密密码
        
        Args:
            password: 加密密码
            
        Returns:
            bool: 是否成功设置
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            # 生成密钥和盐值
            key, salt = self._generate_key(password)
            
            # 将盐值存储到数据库中
            await self.save_config("_encryption_salt", base64.b64encode(salt).decode(), False)
            
            # 设置加密密钥
            self._encryption_key = key
            
            logger.info("已设置加密密码")
            return True
        
        except Exception as e:
            logger.error(f"设置加密密码失败: {e}")
            return False
    
    async def load_encryption_key(self) -> bool:
        """
        加载加密密钥
        
        Returns:
            bool: 是否成功加载
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            # 尝试从环境变量获取密码
            password = os.environ.get("WXAUTO_MGT_ENCRYPTION_PASSWORD")
            
            if not password:
                # 如果环境变量不存在，尝试从配置文件获取
                password = await self.get_config("encryption_password", None, False)
            
            if not password:
                logger.warning("未找到加密密码，配置加密功能将不可用")
                return False
            
            # 获取存储的盐值
            salt_base64 = await self.get_config("_encryption_salt", None, False)
            if not salt_base64:
                logger.warning("未找到加密盐值，配置加密功能将不可用")
                return False
            
            salt = base64.b64decode(salt_base64)
            
            # 生成密钥
            key, _ = self._generate_key(password, salt)
            self._encryption_key = key
            
            logger.info("已加载加密密钥")
            return True
        
        except Exception as e:
            logger.error(f"加载加密密钥失败: {e}")
            return False
    
    def _encrypt_value(self, value: str) -> str:
        """
        加密值
        
        Args:
            value: 待加密的值
            
        Returns:
            str: 加密后的值
            
        Raises:
            ValueError: 如果加密密钥未设置
        """
        if not self._encryption_key:
            raise ValueError("加密密钥未设置")
        
        fernet = Fernet(self._encryption_key)
        encrypted = fernet.encrypt(value.encode())
        return base64.b64encode(encrypted).decode()
    
    def _decrypt_value(self, encrypted_value: str) -> str:
        """
        解密值
        
        Args:
            encrypted_value: 加密的值
            
        Returns:
            str: 解密后的值
            
        Raises:
            ValueError: 如果加密密钥未设置
        """
        if not self._encryption_key:
            raise ValueError("加密密钥未设置")
        
        try:
            fernet = Fernet(self._encryption_key)
            decrypted = fernet.decrypt(base64.b64decode(encrypted_value))
            return decrypted.decode()
        except Exception as e:
            logger.error(f"解密失败: {e}")
            raise ValueError(f"解密失败: {e}")
    
    async def save_config(self, key: str, value: Any, encrypt: bool = False, create_version: bool = True) -> bool:
        """
        保存配置
        
        Args:
            key: 配置键
            value: 配置值，如果是复杂类型将被转换为JSON
            encrypt: 是否加密
            create_version: 是否创建版本记录
            
        Returns:
            bool: 是否成功保存
        """
        if not self._initialized:
            await self.initialize()
        
        # 将值转换为字符串
        if isinstance(value, (dict, list)):
            value_str = json.dumps(value, ensure_ascii=False)
        else:
            value_str = str(value)
        
        # 如果需要加密
        if encrypt:
            try:
                if not self._encryption_key:
                    await self.load_encryption_key()
                if not self._encryption_key:
                    logger.error("保存配置失败: 加密密钥未设置")
                    return False
                value_str = self._encrypt_value(value_str)
            except Exception as e:
                logger.error(f"加密配置值失败: {e}")
                return False
        
        # 准备配置数据
        config_data = {
            "key": key,
            "value": value_str,
            "encrypted": encrypt,
            "updated_at": int(time.time())
        }
        
        try:
            # 检查配置是否已存在
            row = await db_manager.fetch_one(
                "SELECT id FROM configs WHERE key = ?", 
                [key]
            )
            
            if row:
                # 如果需要创建版本记录
                if create_version:
                    # 获取当前值以创建版本记录
                    current = await db_manager.fetch_one(
                        "SELECT * FROM configs WHERE key = ?", 
                        [key]
                    )
                    
                    if current:
                        version_data = {
                            "config_key": key,
                            "value": current["value"],
                            "encrypted": current["encrypted"],
                            "timestamp": int(time.time())
                        }
                        
                        await db_manager.insert("config_versions", version_data)
                        logger.debug(f"已为配置 {key} 创建版本记录")
                
                # 更新配置
                await db_manager.update(
                    "configs",
                    config_data,
                    "key = ?",
                    [key]
                )
                logger.debug(f"已更新配置: {key}")
            else:
                # 插入新配置
                await db_manager.insert("configs", config_data)
                logger.debug(f"已添加配置: {key}")
            
            return True
        
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            return False
    
    async def save_configs(self, configs: Dict[str, Any], encrypt: bool = False, create_version: bool = True) -> bool:
        """
        批量保存配置
        
        Args:
            configs: 配置字典
            encrypt: 是否加密
            create_version: 是否创建版本记录
            
        Returns:
            bool: 是否全部成功保存
        """
        if not self._initialized:
            await self.initialize()
        
        success = True
        
        # 使用事务确保原子性
        async with db_manager.transaction():
            for key, value in configs.items():
                result = await self.save_config(key, value, encrypt, create_version)
                if not result:
                    success = False
                    logger.warning(f"保存配置 {key} 失败")
        
        return success
    
    async def get_config(self, key: str, default: Any = None, decrypt: bool = False) -> Any:
        """
        获取配置
        
        Args:
            key: 配置键
            default: 默认值
            decrypt: 是否解密
            
        Returns:
            Any: 配置值
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            row = await db_manager.fetch_one(
                "SELECT * FROM configs WHERE key = ?", 
                [key]
            )
            
            if not row:
                return default
            
            value = row["value"]
            
            # 如果需要解密
            if row["encrypted"] or decrypt:
                try:
                    if not self._encryption_key:
                        await self.load_encryption_key()
                    if not self._encryption_key:
                        logger.error("获取配置失败: 配置已加密但加密密钥未设置")
                        return default
                    value = self._decrypt_value(value)
                except Exception as e:
                    logger.error(f"解密配置值失败: {e}")
                    return default
            
            # 尝试解析JSON
            try:
                if value.startswith('{') or value.startswith('['):
                    return json.loads(value)
            except (json.JSONDecodeError, TypeError, AttributeError):
                pass
            
            return value
        
        except Exception as e:
            logger.error(f"获取配置失败: {e}")
            return default
    
    async def get_configs(self, keys: List[str], decrypt: bool = False) -> Dict[str, Any]:
        """
        批量获取配置
        
        Args:
            keys: 配置键列表
            decrypt: 是否解密
            
        Returns:
            Dict[str, Any]: 配置字典
        """
        if not self._initialized:
            await self.initialize()
        
        result = {}
        
        for key in keys:
            value = await self.get_config(key, None, decrypt)
            result[key] = value
        
        return result
    
    async def delete_config(self, key: str, create_version: bool = True) -> bool:
        """
        删除配置
        
        Args:
            key: 配置键
            create_version: 是否创建版本记录
            
        Returns:
            bool: 是否成功删除
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            # 如果需要创建版本记录
            if create_version:
                # 获取当前值以创建版本记录
                current = await db_manager.fetch_one(
                    "SELECT * FROM configs WHERE key = ?", 
                    [key]
                )
                
                if current:
                    version_data = {
                        "config_key": key,
                        "value": current["value"],
                        "encrypted": current["encrypted"],
                        "timestamp": int(time.time())
                    }
                    
                    await db_manager.insert("config_versions", version_data)
                    logger.debug(f"已为配置 {key} 创建删除前版本记录")
            
            # 删除配置
            deleted = await db_manager.delete(
                "configs",
                "key = ?",
                [key]
            )
            
            if deleted > 0:
                logger.debug(f"已删除配置: {key}")
                return True
            else:
                logger.warning(f"配置 {key} 不存在")
                return False
        
        except Exception as e:
            logger.error(f"删除配置失败: {e}")
            return False
    
    async def get_config_history(self, key: str, limit: int = 10) -> List[Dict]:
        """
        获取配置历史版本
        
        Args:
            key: 配置键
            limit: 历史记录数量限制
            
        Returns:
            List[Dict]: 历史版本列表
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            rows = await db_manager.fetch_all(
                """
                SELECT * FROM config_versions 
                WHERE config_key = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
                """, 
                [key, limit]
            )
            
            history = []
            for row in rows:
                version = dict(row)
                version["timestamp_readable"] = datetime.fromtimestamp(version["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
                history.append(version)
            
            return history
        
        except Exception as e:
            logger.error(f"获取配置历史失败: {e}")
            return []
    
    async def restore_config_version(self, version_id: int) -> bool:
        """
        恢复配置到指定版本
        
        Args:
            version_id: 版本ID
            
        Returns:
            bool: 是否成功恢复
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            # 获取版本记录
            version = await db_manager.fetch_one(
                "SELECT * FROM config_versions WHERE id = ?", 
                [version_id]
            )
            
            if not version:
                logger.warning(f"配置版本 {version_id} 不存在")
                return False
            
            # 更新当前配置
            config_data = {
                "key": version["config_key"],
                "value": version["value"],
                "encrypted": version["encrypted"],
                "updated_at": int(time.time())
            }
            
            # 检查配置是否存在
            row = await db_manager.fetch_one(
                "SELECT id FROM configs WHERE key = ?", 
                [version["config_key"]]
            )
            
            if row:
                # 创建版本记录（当前值）
                current = await db_manager.fetch_one(
                    "SELECT * FROM configs WHERE key = ?", 
                    [version["config_key"]]
                )
                
                version_data = {
                    "config_key": version["config_key"],
                    "value": current["value"],
                    "encrypted": current["encrypted"],
                    "timestamp": int(time.time())
                }
                
                await db_manager.insert("config_versions", version_data)
                
                # 更新配置
                await db_manager.update(
                    "configs",
                    config_data,
                    "key = ?",
                    [version["config_key"]]
                )
            else:
                # 插入新配置
                await db_manager.insert("configs", config_data)
            
            logger.info(f"已恢复配置 {version['config_key']} 到指定版本")
            return True
        
        except Exception as e:
            logger.error(f"恢复配置版本失败: {e}")
            return False
    
    async def export_configs(self, include_encrypted: bool = False, pretty: bool = True) -> str:
        """
        导出所有配置
        
        Args:
            include_encrypted: 是否包含加密配置
            pretty: 是否美化输出
            
        Returns:
            str: 配置JSON字符串
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            # 构建查询条件
            query = "SELECT * FROM configs"
            params = []
            
            if not include_encrypted:
                query += " WHERE encrypted = 0"
            
            # 获取所有配置
            rows = await db_manager.fetch_all(query, params)
            
            configs = {}
            for row in rows:
                key = row["key"]
                value = row["value"]
                encrypted = row["encrypted"]
                
                # 跳过内部配置
                if key.startswith('_'):
                    continue
                
                # 解密值（如果需要）
                if encrypted and include_encrypted:
                    try:
                        if not self._encryption_key:
                            await self.load_encryption_key()
                        if self._encryption_key:
                            value = self._decrypt_value(value)
                    except Exception as e:
                        logger.warning(f"导出时解密配置 {key} 失败: {e}")
                        continue
                
                # 尝试解析JSON
                try:
                    if value.startswith('{') or value.startswith('['):
                        configs[key] = json.loads(value)
                        continue
                except (json.JSONDecodeError, TypeError, AttributeError):
                    pass
                
                configs[key] = value
            
            # 导出为JSON
            indent = 2 if pretty else None
            return json.dumps(configs, indent=indent, ensure_ascii=False)
        
        except Exception as e:
            logger.error(f"导出配置失败: {e}")
            return "{}"
    
    async def import_configs(self, config_json: str, overwrite: bool = False, encrypt_sensitive: bool = True) -> int:
        """
        从JSON导入配置
        
        Args:
            config_json: 配置JSON字符串
            overwrite: 是否覆盖现有配置
            encrypt_sensitive: 是否加密敏感配置
            
        Returns:
            int: 导入的配置数量
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            configs = json.loads(config_json)
            
            if not isinstance(configs, dict):
                raise ValueError("配置必须是有效的JSON对象")
            
            # 敏感配置键列表
            sensitive_keys = [
                "password", "token", "secret", "key", "credential", "api_key",
                "access_token", "refresh_token"
            ]
            
            # 判断是否为敏感配置
            def is_sensitive(key: str) -> bool:
                return any(sk in key.lower() for sk in sensitive_keys)
            
            imported_count = 0
            
            # 导入配置
            for key, value in configs.items():
                # 跳过内部配置
                if key.startswith('_'):
                    continue
                
                # 检查是否已存在
                if not overwrite:
                    exists = await db_manager.fetch_one(
                        "SELECT id FROM configs WHERE key = ?", 
                        [key]
                    )
                    
                    if exists:
                        logger.debug(f"配置 {key} 已存在，跳过导入")
                        continue
                
                # 确定是否加密
                should_encrypt = encrypt_sensitive and is_sensitive(key)
                
                # 保存配置
                result = await self.save_config(key, value, should_encrypt)
                
                if result:
                    imported_count += 1
            
            logger.info(f"导入配置完成，成功导入 {imported_count} 项")
            return imported_count
        
        except Exception as e:
            logger.error(f"导入配置失败: {e}")
            return 0
    
    async def load_env_variables(self, prefix: str = "WXAUTO_MGT_") -> int:
        """
        从环境变量加载配置
        
        Args:
            prefix: 环境变量前缀
            
        Returns:
            int: 加载的配置数量
        """
        if self._env_loaded:
            return 0
        
        if not self._initialized:
            await self.initialize()
        
        try:
            loaded_count = 0
            
            for key, value in os.environ.items():
                if key.startswith(prefix):
                    # 移除前缀并转换为小写
                    config_key = key[len(prefix):].lower()
                    
                    # 处理多层级键，使用点分隔
                    config_key = config_key.replace("__", ".")
                    
                    # 保存配置，不覆盖现有配置
                    exists = await db_manager.fetch_one(
                        "SELECT id FROM configs WHERE key = ?", 
                        [config_key]
                    )
                    
                    if not exists:
                        result = await self.save_config(config_key, value, False)
                        
                        if result:
                            loaded_count += 1
            
            self._env_loaded = True
            
            if loaded_count > 0:
                logger.info(f"已从环境变量加载 {loaded_count} 项配置")
            
            return loaded_count
        
        except Exception as e:
            logger.error(f"从环境变量加载配置失败: {e}")
            return 0
    
    async def get_all_configs(self, include_encrypted: bool = False, decrypt: bool = False) -> Dict[str, Any]:
        """
        获取所有配置
        
        Args:
            include_encrypted: 是否包含加密配置
            decrypt: 是否解密加密配置
            
        Returns:
            Dict[str, Any]: 配置字典
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            # 构建查询条件
            query = "SELECT * FROM configs"
            params = []
            
            if not include_encrypted:
                query += " WHERE encrypted = 0"
            
            # 获取所有配置
            rows = await db_manager.fetch_all(query, params)
            
            configs = {}
            for row in rows:
                key = row["key"]
                value = row["value"]
                encrypted = row["encrypted"]
                
                # 跳过内部配置
                if key.startswith('_'):
                    continue
                
                # 解密值（如果需要）
                if encrypted and decrypt:
                    try:
                        if not self._encryption_key:
                            await self.load_encryption_key()
                        if self._encryption_key:
                            value = self._decrypt_value(value)
                    except Exception as e:
                        logger.warning(f"获取配置 {key} 时解密失败: {e}")
                        continue
                
                # 尝试解析JSON
                try:
                    if value.startswith('{') or value.startswith('['):
                        configs[key] = json.loads(value)
                        continue
                except (json.JSONDecodeError, TypeError, AttributeError):
                    pass
                
                configs[key] = value
            
            return configs
        
        except Exception as e:
            logger.error(f"获取所有配置失败: {e}")
            return {}


# 创建全局配置存储实例
config_store = ConfigStore() 