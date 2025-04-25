"""
配置管理器模块

负责管理应用程序配置，包括加载、保存和加密存储配置数据。支持从默认配置文件、
数据库和环境变量加载配置，并提供配置项的验证功能。
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

from app.data.db_manager import db_manager
from app.utils.logging import get_logger

logger = get_logger()


class ConfigError(Exception):
    """配置错误异常"""
    pass


class ConfigManager:
    """
    配置管理器，负责管理应用程序配置
    """
    
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
    
    async def rotate_encryption_key(self, new_encryption_key: str, new_key_id: int) -> bool:
        """
        轮换加密密钥，重新加密所有敏感数据
        
        Args:
            new_encryption_key: 新加密密钥
            new_key_id: 新密钥ID
            
        Returns:
            bool: 是否成功轮换密钥
        """
        if not self._initialized:
            logger.error("配置管理器未初始化")
            return False
        
        # 保存当前密钥作为旧密钥
        old_key_id = self._encryption_key_id
        old_cipher = self._cipher
        
        try:
            # 初始化新密钥
            await self._init_encryption(new_encryption_key)
            self._encryption_key_id = new_key_id
            
            # 将当前密钥添加到旧密钥列表
            self._legacy_ciphers[old_key_id] = old_cipher
            
            # 重新加密数据库中的敏感信息
            await self._reencrypt_sensitive_data()
            
            logger.info(f"已轮换加密密钥: 旧ID={old_key_id}, 新ID={new_key_id}")
            return True
        except Exception as e:
            # 恢复旧密钥
            self._cipher = old_cipher
            self._encryption_key_id = old_key_id
            if new_key_id in self._legacy_ciphers:
                del self._legacy_ciphers[new_key_id]
            
            logger.error(f"轮换加密密钥失败: {e}")
            return False
    
    async def _reencrypt_sensitive_data(self) -> None:
        """重新加密数据库中的敏感信息"""
        # 从数据库获取所有加密的配置项
        rows = await db_manager.fetchall(
            "SELECT key, value, encrypted FROM configs WHERE encrypted = 1"
        )
        
        for row in rows:
            key = row['key']
            encrypted_value = row['value']
            
            try:
                # 使用旧密钥解密
                decrypted = self.decrypt(encrypted_value)
                
                # 使用新密钥加密
                new_encrypted = self.encrypt(decrypted)
                
                # 更新数据库
                await db_manager.update(
                    "configs",
                    {
                        "value": new_encrypted,
                        "encrypted": 1,
                        "version": self._encryption_key_id,
                        "last_update": int(time.time())
                    },
                    "key = ?",
                    [key]
                )
            except Exception as e:
                logger.error(f"重新加密配置项 {key} 失败: {e}")
    
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
                
                # 所有密钥都解密失败
                raise ConfigError("无法解密数据，所有密钥都失败")
        except Exception as e:
            logger.error(f"解密数据失败: {e}")
            raise ConfigError(f"解密数据失败: {e}")
    
    def get_encryption_key_id(self) -> int:
        """
        获取当前加密密钥ID
        
        Returns:
            int: 密钥ID
        """
        return self._encryption_key_id
    
    def get_legacy_key_ids(self) -> List[int]:
        """
        获取所有旧密钥ID
        
        Returns:
            List[int]: 旧密钥ID列表
        """
        return list(self._legacy_ciphers.keys())
    
    async def remove_legacy_key(self, key_id: int) -> bool:
        """
        移除旧密钥
        
        Args:
            key_id: 密钥ID
            
        Returns:
            bool: 是否成功移除
        """
        if key_id not in self._legacy_ciphers:
            logger.warning(f"旧密钥 ID={key_id} 不存在")
            return False
        
        # 检查是否有使用该密钥加密的数据
        row = await db_manager.fetchone(
            "SELECT COUNT(*) as count FROM configs WHERE encrypted = 1 AND version = ?",
            [key_id]
        )
        
        if row and row['count'] > 0:
            logger.warning(f"旧密钥 ID={key_id} 仍有数据使用，无法移除")
            return False
        
        # 移除密钥
        del self._legacy_ciphers[key_id]
        logger.info(f"已移除旧密钥: ID={key_id}")
        return True
    
    def _should_encrypt(self, key: str) -> bool:
        """
        判断指定键是否需要加密
        
        Args:
            key: 配置键名
            
        Returns:
            bool: 是否需要加密
        """
        # 需要加密的键列表或模式
        sensitive_patterns = [
            'instances.*.api_key',     # 实例API密钥
            'api.secret',              # API密钥
            'api.*.token',             # API令牌
            'auth.password',           # 认证密码
            'auth.*.token',            # 认证令牌
            'database.password',       # 数据库密码
            'security.*.key',          # 安全密钥
            '*.password',              # 任何密码字段
            '*.secret',                # 任何密钥字段
            '*.token',                 # 任何令牌字段
            '*.api_key'                # 任何API密钥字段
        ]
        
        # 检查键是否匹配任何敏感模式
        for pattern in sensitive_patterns:
            if self._match_pattern(key, pattern):
                return True
        
        return False
    
    def _match_pattern(self, key: str, pattern: str) -> bool:
        """
        检查键是否匹配指定的模式
        
        Args:
            key: 配置键名
            pattern: 匹配模式，可包含*通配符
            
        Returns:
            bool: 是否匹配
        """
        # 如果模式中不包含通配符，直接比较
        if '*' not in pattern:
            return key == pattern
        
        # 将模式转换为正则表达式
        pattern_regex = pattern.replace('.', '\\.').replace('*', '.*')
        import re
        return bool(re.match(f"^{pattern_regex}$", key))
    
    async def load_config(self) -> Dict:
        """
        加载配置
        
        Returns:
            Dict: 加载的配置
        """
        # 首先加载默认配置
        default_config = await self._load_default_config()
        
        # 然后加载数据库中的配置
        db_config = await self._load_db_config()
        
        # 合并配置
        self._config = self._merge_configs(default_config, db_config)
        
        # 记录加载了多少实例
        instances = self.get('instances', [])
        logger.info(f"配置加载完成，共加载了 {len(instances)} 个实例配置")
        for instance in instances:
            logger.debug(f"已加载实例配置: {instance.get('instance_id')} - {instance.get('name')}")
        
        return self._config.copy()
    
    async def _load_default_config(self) -> Dict:
        """
        加载默认配置文件
        
        Returns:
            Dict: 默认配置
        """
        try:
            if not os.path.exists(self._default_config_path):
                logger.warning(f"默认配置文件不存在: {self._default_config_path}")
                return {}
            
            with open(self._default_config_path, 'r', encoding='utf-8') as file:
                config = json.load(file)
            
            logger.debug(f"已加载默认配置文件: {self._default_config_path}")
            return config
        except Exception as e:
            logger.error(f"加载默认配置文件失败: {e}")
            return {}
    
    async def _load_db_config(self) -> Dict:
        """
        从数据库加载配置
        
        Returns:
            Dict: 数据库配置
        """
        config = {}
        
        try:
            rows = await db_manager.fetchall("SELECT key, value, encrypted FROM configs")
            
            logger.info(f"从数据库加载了 {len(rows)} 个配置项")
            
            for row in rows:
                key = row['key']
                value = row['value']
                encrypted = bool(row['encrypted'])
                
                logger.debug(f"加载配置项: {key} (加密: {encrypted})")
                
                # 如果是加密的值，先解密
                if encrypted:
                    try:
                        value = self.decrypt(value)
                    except Exception as e:
                        logger.error(f"解密配置项 {key} 失败: {e}")
                        continue
                
                # 尝试将值解析为JSON
                try:
                    value = json.loads(value)
                    if key == 'instances':
                        logger.info(f"从数据库加载了 {len(value)} 个实例配置")
                except Exception as e:
                    logger.debug(f"配置项 {key} 不是JSON格式: {e}")
                    pass  # 如果不是JSON，保持原样
                
                # 将键设置为嵌套结构
                self._set_nested_key(config, key, value)
            
            logger.debug(f"从数据库加载配置完成")
            return config
        except Exception as e:
            logger.error(f"从数据库加载配置失败: {e}")
            return {}
    
    def _set_nested_key(self, config: Dict, key: str, value: Any) -> None:
        """
        设置嵌套键的值
        
        Args:
            config: 配置字典
            key: 键名，可以是点分隔的嵌套键
            value: 值
        """
        if '.' not in key:
            config[key] = value
            return
        
        parts = key.split('.')
        current = config
        
        # 遍历键的各个部分
        for i, part in enumerate(parts):
            # 如果是最后一个部分，直接设置值
            if i == len(parts) - 1:
                current[part] = value
            else:
                # 如果中间部分不存在，创建一个空字典
                if part not in current:
                    current[part] = {}
                # 更新当前引用
                current = current[part]
    
    def _get_nested_key(self, config: Dict, key: str) -> Any:
        """
        获取嵌套键的值
        
        Args:
            config: 配置字典
            key: 键名，可以是点分隔的嵌套键
            
        Returns:
            Any: 键对应的值，如果不存在则返回None
        """
        if '.' not in key:
            return config.get(key)
        
        parts = key.split('.')
        current = config
        
        # 遍历键的各个部分
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        
        return current
    
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
            # 获取所有配置项
            flat_config = self._flatten_config(self._config)
            
            # 获取数据库中的现有配置项
            existing_configs = {}
            try:
                rows = await db_manager.fetchall("SELECT key, encrypted FROM configs")
                for row in rows:
                    existing_configs[row['key']] = bool(row['encrypted'])
                logger.debug(f"数据库中已有 {len(existing_configs)} 个配置项")
            except Exception as e:
                logger.error(f"获取数据库现有配置失败: {e}")
            
            # 对每个配置项进行处理
            async with self._lock:
                for key, value in flat_config.items():
                    # 检查值是否需要加密
                    encrypted = False
                    
                    # 对于敏感配置项进行加密，例如API密钥、密码等
                    if any(sensitive in key.lower() for sensitive in [
                        'password', 'secret', 'key', 'token', 'credential'
                    ]):
                        encrypted = True
                    
                    # 如果值是字典或列表，转换为JSON字符串
                    if isinstance(value, (dict, list)):
                        value = json.dumps(value, ensure_ascii=False)
                    
                    # 加密敏感数据
                    if encrypted:
                        value = self.encrypt(str(value))
                    else:
                        value = str(value)
                    
                    # 检查配置项是否已存在
                    exists = key in existing_configs
                    logger.debug(f"保存配置项: {key} (加密: {encrypted}, 存在: {exists})")
                    
                    if exists:
                        # 更新现有配置
                        try:
                            await db_manager.execute(
                                "UPDATE configs SET value = ?, encrypted = ?, version = ?, last_update = ? WHERE key = ?",
                                (value, 1 if encrypted else 0, self._encryption_key_id if encrypted else 1, int(time.time()), key)
                            )
                            logger.debug(f"已更新配置项: {key}")
                        except Exception as e:
                            logger.error(f"更新配置项 {key} 失败: {e}")
                    else:
                        # 插入新配置
                        try:
                            await db_manager.execute(
                                "INSERT INTO configs (key, value, encrypted, version, last_update) VALUES (?, ?, ?, ?, ?)",
                                (key, value, 1 if encrypted else 0, self._encryption_key_id if encrypted else 1, int(time.time()))
                            )
                            logger.debug(f"已插入新配置项: {key}")
                        except Exception as e:
                            logger.error(f"插入配置项 {key} 失败: {e}")
                
                logger.info(f"已保存 {len(flat_config)} 个配置项到数据库")
                return True
        except Exception as e:
            logger.error(f"保存配置到数据库失败: {e}")
            return False
    
    def _flatten_config(self, config: Dict, prefix: str = "") -> Dict:
        """
        将嵌套配置扁平化为键值对
        
        Args:
            config: 嵌套配置
            prefix: 键前缀
            
        Returns:
            Dict: 扁平化的配置
        """
        result = {}
        
        for key, value in config.items():
            full_key = f"{prefix}.{key}" if prefix else key
            
            # 处理嵌套字典
            if isinstance(value, dict):
                nested = self._flatten_config(value, full_key)
                result.update(nested)
            else:
                # 确定是否需要加密
                encrypted = False
                if any(sensitive in full_key.lower() for sensitive in [
                    'password', 'secret', 'key', 'token', 'credential'
                ]):
                    encrypted = True
                
                result[full_key] = value
        
        return result
    
    def _is_special_dict(self, value: Dict) -> bool:
        """
        判断是否为特殊字典，不需要扁平化处理
        
        Args:
            value: 要判断的字典
            
        Returns:
            bool: 是否为特殊字典
        """
        # 这里可以添加一些判断逻辑，例如包含特定键的字典
        return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值
        
        Args:
            key: 配置键名，可以是点分隔的嵌套键
            default: 默认值，如果键不存在则返回此值
            
        Returns:
            Any: 配置值
        """
        value = self._get_nested_key(self._config, key)
        return default if value is None else value
    
    def set(self, key: str, value: Any, save: bool = False) -> None:
        """
        设置配置值
        
        Args:
            key: 配置键名，可以是点分隔的嵌套键
            value: 配置值
            save: 是否立即保存到数据库
        """
        self._set_nested_key(self._config, key, value)
        
        if save:
            asyncio.create_task(self.save_config())
    
    def get_all(self) -> Dict:
        """
        获取所有配置
        
        Returns:
            Dict: 配置字典副本
        """
        return self._config.copy()
    
    async def reset_to_default(self) -> bool:
        """
        重置配置为默认值
        
        Returns:
            bool: 是否成功重置
        """
        try:
            # 清空数据库中的配置
            await db_manager.execute("DELETE FROM configs")
            
            # 重新加载默认配置
            self._config = await self._load_default_config()
            
            # 保存到数据库
            await self.save_config()
            
            logger.info("已重置配置为默认值")
            return True
        except Exception as e:
            logger.error(f"重置配置失败: {e}")
            return False
    
    async def validate_config(self) -> Tuple[bool, List[str]]:
        """
        验证配置合法性
        
        Returns:
            Tuple[bool, List[str]]: 是否有效和错误消息列表
        """
        errors = []
        
        # 检查必需的配置项
        required_fields = [
            'app.name',
            'app.version',
            'message_listener.poll_interval',
            'message_listener.max_listeners',
            'status_monitor.check_interval',
            'db.path'
        ]
        
        for field in required_fields:
            if self.get(field) is None:
                errors.append(f"缺少必需的配置项: {field}")
        
        # 检查类型和值范围
        if isinstance(self.get('message_listener.poll_interval'), (int, float)):
            if self.get('message_listener.poll_interval') < 1:
                errors.append("消息监听轮询间隔必须大于0")
        else:
            errors.append("消息监听轮询间隔必须是数字")
        
        if isinstance(self.get('message_listener.max_listeners'), int):
            if self.get('message_listener.max_listeners') < 1:
                errors.append("最大监听数量必须大于0")
        else:
            errors.append("最大监听数量必须是整数")
        
        if isinstance(self.get('status_monitor.check_interval'), (int, float)):
            if self.get('status_monitor.check_interval') < 1:
                errors.append("状态检查间隔必须大于0")
        else:
            errors.append("状态检查间隔必须是数字")
        
        # 检查实例配置
        instances = self.get('instances', [])
        if not isinstance(instances, list):
            errors.append("实例配置必须是列表")
        else:
            for i, instance in enumerate(instances):
                if not isinstance(instance, dict):
                    errors.append(f"实例 #{i+1} 配置必须是字典")
                    continue
                
                if 'instance_id' not in instance:
                    errors.append(f"实例 #{i+1} 缺少实例ID")
                
                if 'base_url' not in instance:
                    errors.append(f"实例 #{i+1} 缺少基础URL")
                
                if 'api_key' not in instance:
                    errors.append(f"实例 #{i+1} 缺少API密钥")
        
        return len(errors) == 0, errors
    
    async def export_config(self, file_path: str, include_secrets: bool = False) -> bool:
        """
        导出配置到文件
        
        Args:
            file_path: 导出文件路径
            include_secrets: 是否包含敏感信息，默认为False
            
        Returns:
            bool: 是否成功导出
        """
        try:
            # 复制配置
            config_to_export = self.get_all()
            
            # 如果不包含敏感信息，移除敏感字段
            if not include_secrets:
                self._remove_secrets(config_to_export)
            
            # 确保目录存在
            os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
            
            # 写入文件
            with open(file_path, 'w', encoding='utf-8') as file:
                json.dump(config_to_export, file, indent=2, ensure_ascii=False)
            
            logger.info(f"已导出配置到: {file_path}")
            return True
        except Exception as e:
            logger.error(f"导出配置失败: {e}")
            return False
    
    def _remove_secrets(self, config: Dict) -> None:
        """
        从配置中移除敏感信息
        
        Args:
            config: 配置字典
        """
        # 将配置扁平化
        flat_config = self._flatten_config(config)
        
        # 找出需要移除的敏感键
        keys_to_remove = []
        for key, item in flat_config.items():
            if item.get('encrypted', False):
                keys_to_remove.append(key)
        
        # 从原始配置中移除敏感键
        for key in keys_to_remove:
            parts = key.split('.')
            current = config
            
            # 遍历到倒数第二级
            for i in range(len(parts) - 1):
                part = parts[i]
                if part in current:
                    current = current[part]
                else:
                    break
            
            # 移除最后一级
            if isinstance(current, dict) and parts[-1] in current:
                current[parts[-1]] = "******"  # 用星号替换敏感值
    
    async def import_config(self, file_path: str, merge: bool = True) -> bool:
        """
        从文件导入配置
        
        Args:
            file_path: 导入文件路径
            merge: 是否合并到现有配置，默认为True
            
        Returns:
            bool: 是否成功导入
        """
        try:
            # 读取文件
            with open(file_path, 'r', encoding='utf-8') as file:
                imported_config = json.load(file)
            
            if not merge:
                # 如果不合并，直接替换配置
                self._config = imported_config
            else:
                # 合并到现有配置
                self._config = self._merge_configs(self._config, imported_config)
            
            # 保存到数据库
            await self.save_config()
            
            logger.info(f"已从 {file_path} 导入配置")
            return True
        except Exception as e:
            logger.error(f"导入配置失败: {e}")
            return False
    
    def load_from_env(self, prefix: str = "WXAUTO_") -> Dict:
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
    
    async def add_instance(self, instance_id: str, name: str, base_url: str, 
                         api_key: str, enabled: bool = True) -> bool:
        """
        添加WxAuto实例配置
        
        Args:
            instance_id: 实例ID
            name: 实例名称
            base_url: API基础URL
            api_key: API密钥
            enabled: 是否启用
            
        Returns:
            bool: 是否成功添加
        """
        try:
            # 获取当前实例列表
            instances = self.get('instances', [])
            
            # 检查实例ID是否已存在
            for i, instance in enumerate(instances):
                if instance.get('instance_id') == instance_id:
                    # 更新现有实例
                    instances[i] = {
                        'instance_id': instance_id,
                        'name': name,
                        'base_url': base_url,
                        'api_key': api_key,
                        'enabled': enabled
                    }
                    break
            else:
                # 添加新实例
                instances.append({
                    'instance_id': instance_id,
                    'name': name,
                    'base_url': base_url,
                    'api_key': api_key,
                    'enabled': enabled
                })
            
            # 更新配置
            self.set('instances', instances)
            
            # 保存到数据库
            await self.save_config()
            
            logger.info(f"已添加/更新实例配置: {instance_id}")
            return True
        except Exception as e:
            logger.error(f"添加实例配置失败: {e}")
            return False
    
    async def update_instance(self, instance_id: str, updated_data: dict) -> bool:
        """
        更新WxAuto实例配置
        
        Args:
            instance_id: 实例ID
            updated_data: 更新的实例数据字典，包含name、base_url、api_key、enabled等字段
            
        Returns:
            bool: 是否成功更新
        """
        try:
            # 获取当前实例列表
            instances = self.get('instances', [])
            
            # 查找并更新实例
            for i, instance in enumerate(instances):
                if instance.get('instance_id') == instance_id:
                    # 更新实例数据，保留原有字段
                    for key, value in updated_data.items():
                        instances[i][key] = value
                    
                    # 确保实例ID不会被修改
                    instances[i]['instance_id'] = instance_id
                    
                    # 更新配置
                    self.set('instances', instances)
                    
                    # 保存到数据库
                    await self.save_config()
                    
                    logger.info(f"已更新实例配置: {instance_id}")
                    return True
            
            logger.warning(f"未找到待更新的实例: {instance_id}")
            return False
        except Exception as e:
            logger.error(f"更新实例配置失败: {e}")
            return False
    
    async def remove_instance(self, instance_id: str) -> bool:
        """
        移除WxAuto实例配置
        
        Args:
            instance_id: 实例ID
            
        Returns:
            bool: 是否成功移除
        """
        try:
            # 获取当前实例列表
            instances = self.get('instances', [])
            
            # 过滤实例列表
            new_instances = [inst for inst in instances if inst.get('instance_id') != instance_id]
            
            # 如果长度相同，说明没有找到实例
            if len(instances) == len(new_instances):
                logger.warning(f"未找到实例配置: {instance_id}")
                return False
            
            # 更新配置
            self.set('instances', new_instances)
            
            # 保存到数据库
            await self.save_config()
            
            logger.info(f"已移除实例配置: {instance_id}")
            return True
        except Exception as e:
            logger.error(f"移除实例配置失败: {e}")
            return False
    
    def get_instance_config(self, instance_id: str) -> Optional[Dict]:
        """
        获取指定实例的配置
        
        Args:
            instance_id: 实例ID
            
        Returns:
            Optional[Dict]: 实例配置，如果不存在则返回None
        """
        instances = self.get('instances', [])
        
        for instance in instances:
            if instance.get('instance_id') == instance_id:
                return instance.copy()
        
        return None
    
    def get_enabled_instances(self) -> List[Dict]:
        """
        获取所有已启用的实例配置
        
        Returns:
            List[Dict]: 已启用的实例配置列表
        """
        instances = self.get('instances', [])
        logger.debug(f"获取已启用实例: 实例列表中有 {len(instances)} 个实例")
        
        # 确保instances是列表
        if not isinstance(instances, list):
            logger.error(f"实例配置格式错误，应为列表但实际为: {type(instances)}")
            try:
                # 尝试解析为列表
                if isinstance(instances, str):
                    try:
                        instances = json.loads(instances)
                        logger.info(f"尝试将字符串解析为列表: {instances}")
                    except:
                        logger.error(f"无法将实例配置字符串解析为JSON: {instances}")
                        return []
                else:
                    logger.error(f"实例配置格式无法处理: {instances}")
                    return []
            except Exception as e:
                logger.error(f"处理实例配置时出错: {e}")
                return []
        
        enabled_instances = []
        for inst in instances:
            if not isinstance(inst, dict):
                logger.error(f"实例配置项不是字典: {inst}")
                continue
                
            enabled = inst.get('enabled')
            if enabled is None:  # 如果没有enabled字段，默认为启用
                enabled = True
                
            if enabled:
                logger.debug(f"找到已启用的实例: {inst.get('instance_id')} - {inst.get('name')}")
                enabled_instances.append(inst.copy())
            else:
                logger.debug(f"跳过未启用的实例: {inst.get('instance_id')} - {inst.get('name')}")
                
        logger.info(f"找到 {len(enabled_instances)}/{len(instances)} 个已启用的实例")
        return enabled_instances
    
    async def disable_instance(self, instance_id: str) -> bool:
        """
        禁用指定实例
        
        Args:
            instance_id: 实例ID
            
        Returns:
            bool: 是否成功禁用
        """
        try:
            instances = self.get('instances', [])
            
            for i, instance in enumerate(instances):
                if instance.get('instance_id') == instance_id:
                    # 更新启用状态
                    instances[i]['enabled'] = False
                    
                    # 更新配置
                    self.set('instances', instances)
                    
                    # 保存到数据库
                    await self.save_config()
                    
                    logger.info(f"已禁用实例: {instance_id}")
                    return True
            
            logger.warning(f"未找到实例配置: {instance_id}")
            return False
        except Exception as e:
            logger.error(f"禁用实例失败: {e}")
            return False
    
    async def enable_instance(self, instance_id: str) -> bool:
        """
        启用指定实例
        
        Args:
            instance_id: 实例ID
            
        Returns:
            bool: 是否成功启用
        """
        try:
            instances = self.get('instances', [])
            
            for i, instance in enumerate(instances):
                if instance.get('instance_id') == instance_id:
                    # 更新启用状态
                    instances[i]['enabled'] = True
                    
                    # 更新配置
                    self.set('instances', instances)
                    
                    # 保存到数据库
                    await self.save_config()
                    
                    logger.info(f"已启用实例: {instance_id}")
                    return True
            
            logger.warning(f"未找到实例配置: {instance_id}")
            return False
        except Exception as e:
            logger.error(f"启用实例失败: {e}")
            return False
    
    def get_message_listener_config(self) -> Dict:
        """
        获取消息监听器配置
        
        Returns:
            Dict: 消息监听器配置
        """
        return {
            'poll_interval': self.get('message_listener.poll_interval', 5),
            'max_listeners': self.get('message_listener.max_listeners', 30),
            'listener_timeout_minutes': self.get('message_listener.listener_timeout_minutes', 30)
        }
    
    def get_status_monitor_config(self) -> Dict:
        """
        获取状态监控器配置
        
        Returns:
            Dict: 状态监控器配置
        """
        return {
            'check_interval': self.get('status_monitor.check_interval', 60)
        }
    
    def get_db_config(self) -> Dict:
        """
        获取数据库配置
        
        Returns:
            Dict: 数据库配置
        """
        # 使用项目的data目录
        default_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "data",
            "wxauto_mgt.db"
        )
        return {
            'path': self.get('db.path', default_path)
        }


# 创建全局配置管理器实例
config_manager = ConfigManager() 