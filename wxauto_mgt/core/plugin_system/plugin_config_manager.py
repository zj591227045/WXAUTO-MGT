"""
插件配置管理器

该模块负责插件配置的管理，包括：
- 配置的存储和加载
- 配置验证
- 配置模式管理
- 配置UI生成
"""

import logging
import json
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from wxauto_mgt.data.db_manager import db_manager
from .interfaces import IConfigurable

logger = logging.getLogger(__name__)


@dataclass
class PluginConfigInfo:
    """插件配置信息"""
    plugin_id: str
    config_data: Dict[str, Any]
    config_schema: Dict[str, Any]
    enabled: bool
    create_time: int
    update_time: int


class PluginConfigManager:
    """插件配置管理器"""
    
    def __init__(self):
        self._initialized = False
        self._config_cache: Dict[str, PluginConfigInfo] = {}
    
    async def initialize(self):
        """初始化配置管理器"""
        if self._initialized:
            return
        
        logger.info("初始化插件配置管理器")
        
        # 确保数据库表存在
        await self._ensure_tables()
        
        # 加载配置缓存
        await self._load_config_cache()
        
        self._initialized = True
        logger.info("插件配置管理器初始化完成")
    
    async def _ensure_tables(self):
        """确保数据库表存在"""
        try:
            # 创建插件配置表
            await db_manager.execute("""
                CREATE TABLE IF NOT EXISTS plugin_configs (
                    plugin_id TEXT PRIMARY KEY,
                    config_data TEXT NOT NULL,
                    config_schema TEXT,
                    enabled INTEGER DEFAULT 1,
                    create_time INTEGER NOT NULL,
                    update_time INTEGER NOT NULL
                )
            """)
            
            # 创建插件实例表（用于存储插件的多个实例配置）
            await db_manager.execute("""
                CREATE TABLE IF NOT EXISTS plugin_instances (
                    instance_id TEXT PRIMARY KEY,
                    plugin_id TEXT NOT NULL,
                    instance_name TEXT NOT NULL,
                    config_data TEXT NOT NULL,
                    enabled INTEGER DEFAULT 1,
                    create_time INTEGER NOT NULL,
                    update_time INTEGER NOT NULL,
                    FOREIGN KEY (plugin_id) REFERENCES plugin_configs (plugin_id)
                )
            """)
            
            logger.info("插件配置数据库表检查完成")
            
        except Exception as e:
            logger.error(f"创建插件配置数据库表失败: {e}")
            raise
    
    async def _load_config_cache(self):
        """加载配置缓存"""
        try:
            configs = await db_manager.fetchall(
                "SELECT * FROM plugin_configs"
            )
            
            for config_row in configs:
                config_info = PluginConfigInfo(
                    plugin_id=config_row['plugin_id'],
                    config_data=json.loads(config_row['config_data']),
                    config_schema=json.loads(config_row['config_schema'] or '{}'),
                    enabled=bool(config_row['enabled']),
                    create_time=config_row['create_time'],
                    update_time=config_row['update_time']
                )
                self._config_cache[config_row['plugin_id']] = config_info
            
            logger.info(f"加载了 {len(self._config_cache)} 个插件配置")
            
        except Exception as e:
            logger.error(f"加载插件配置缓存失败: {e}")
            raise
    
    async def save_plugin_config(self, plugin_id: str, config_data: Dict[str, Any], 
                                config_schema: Dict[str, Any] = None) -> bool:
        """
        保存插件配置
        
        Args:
            plugin_id: 插件ID
            config_data: 配置数据
            config_schema: 配置模式
            
        Returns:
            bool: 是否保存成功
        """
        try:
            if not self._initialized:
                await self.initialize()
            
            now = int(time.time())
            
            # 检查插件是否已存在
            existing = await db_manager.fetchone(
                "SELECT * FROM plugin_configs WHERE plugin_id = ?",
                (plugin_id,)
            )
            
            if existing:
                # 更新现有配置
                await db_manager.execute(
                    """UPDATE plugin_configs 
                       SET config_data = ?, config_schema = ?, update_time = ?
                       WHERE plugin_id = ?""",
                    (json.dumps(config_data), 
                     json.dumps(config_schema or {}), 
                     now, plugin_id)
                )
                
                # 更新缓存
                if plugin_id in self._config_cache:
                    self._config_cache[plugin_id].config_data = config_data
                    self._config_cache[plugin_id].config_schema = config_schema or {}
                    self._config_cache[plugin_id].update_time = now
            else:
                # 插入新配置
                await db_manager.execute(
                    """INSERT INTO plugin_configs 
                       (plugin_id, config_data, config_schema, enabled, create_time, update_time)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (plugin_id, json.dumps(config_data), 
                     json.dumps(config_schema or {}), 1, now, now)
                )
                
                # 添加到缓存
                self._config_cache[plugin_id] = PluginConfigInfo(
                    plugin_id=plugin_id,
                    config_data=config_data,
                    config_schema=config_schema or {},
                    enabled=True,
                    create_time=now,
                    update_time=now
                )
            
            logger.info(f"保存插件配置成功: {plugin_id}")
            return True
            
        except Exception as e:
            logger.error(f"保存插件配置失败: {plugin_id}, 错误: {e}")
            return False
    
    async def load_plugin_config(self, plugin_id: str) -> Optional[Dict[str, Any]]:
        """
        加载插件配置
        
        Args:
            plugin_id: 插件ID
            
        Returns:
            Optional[Dict[str, Any]]: 配置数据
        """
        try:
            if not self._initialized:
                await self.initialize()
            
            # 先从缓存获取
            if plugin_id in self._config_cache:
                return self._config_cache[plugin_id].config_data.copy()
            
            # 从数据库获取
            config_row = await db_manager.fetchone(
                "SELECT config_data FROM plugin_configs WHERE plugin_id = ?",
                (plugin_id,)
            )
            
            if config_row:
                return json.loads(config_row['config_data'])
            
            return None
            
        except Exception as e:
            logger.error(f"加载插件配置失败: {plugin_id}, 错误: {e}")
            return None
    
    async def get_plugin_config_schema(self, plugin_id: str) -> Optional[Dict[str, Any]]:
        """
        获取插件配置模式
        
        Args:
            plugin_id: 插件ID
            
        Returns:
            Optional[Dict[str, Any]]: 配置模式
        """
        try:
            if not self._initialized:
                await self.initialize()
            
            # 先从缓存获取
            if plugin_id in self._config_cache:
                return self._config_cache[plugin_id].config_schema.copy()
            
            # 从数据库获取
            config_row = await db_manager.fetchone(
                "SELECT config_schema FROM plugin_configs WHERE plugin_id = ?",
                (plugin_id,)
            )
            
            if config_row and config_row['config_schema']:
                return json.loads(config_row['config_schema'])
            
            return None
            
        except Exception as e:
            logger.error(f"获取插件配置模式失败: {plugin_id}, 错误: {e}")
            return None
    
    async def enable_plugin(self, plugin_id: str) -> bool:
        """
        启用插件
        
        Args:
            plugin_id: 插件ID
            
        Returns:
            bool: 是否成功
        """
        try:
            await db_manager.execute(
                "UPDATE plugin_configs SET enabled = 1, update_time = ? WHERE plugin_id = ?",
                (int(time.time()), plugin_id)
            )
            
            # 更新缓存
            if plugin_id in self._config_cache:
                self._config_cache[plugin_id].enabled = True
                self._config_cache[plugin_id].update_time = int(time.time())
            
            logger.info(f"启用插件: {plugin_id}")
            return True
            
        except Exception as e:
            logger.error(f"启用插件失败: {plugin_id}, 错误: {e}")
            return False
    
    async def disable_plugin(self, plugin_id: str) -> bool:
        """
        禁用插件
        
        Args:
            plugin_id: 插件ID
            
        Returns:
            bool: 是否成功
        """
        try:
            await db_manager.execute(
                "UPDATE plugin_configs SET enabled = 0, update_time = ? WHERE plugin_id = ?",
                (int(time.time()), plugin_id)
            )
            
            # 更新缓存
            if plugin_id in self._config_cache:
                self._config_cache[plugin_id].enabled = False
                self._config_cache[plugin_id].update_time = int(time.time())
            
            logger.info(f"禁用插件: {plugin_id}")
            return True
            
        except Exception as e:
            logger.error(f"禁用插件失败: {plugin_id}, 错误: {e}")
            return False
    
    async def is_plugin_enabled(self, plugin_id: str) -> bool:
        """
        检查插件是否启用
        
        Args:
            plugin_id: 插件ID
            
        Returns:
            bool: 是否启用
        """
        if plugin_id in self._config_cache:
            return self._config_cache[plugin_id].enabled
        
        try:
            config_row = await db_manager.fetchone(
                "SELECT enabled FROM plugin_configs WHERE plugin_id = ?",
                (plugin_id,)
            )
            
            return bool(config_row['enabled']) if config_row else False
            
        except Exception as e:
            logger.error(f"检查插件启用状态失败: {plugin_id}, 错误: {e}")
            return False
    
    async def get_all_plugin_configs(self) -> Dict[str, PluginConfigInfo]:
        """
        获取所有插件配置
        
        Returns:
            Dict[str, PluginConfigInfo]: 插件配置字典
        """
        if not self._initialized:
            await self.initialize()
        
        return self._config_cache.copy()
    
    async def delete_plugin_config(self, plugin_id: str) -> bool:
        """
        删除插件配置
        
        Args:
            plugin_id: 插件ID
            
        Returns:
            bool: 是否成功
        """
        try:
            # 删除数据库记录
            await db_manager.execute(
                "DELETE FROM plugin_configs WHERE plugin_id = ?",
                (plugin_id,)
            )
            
            # 删除插件实例
            await db_manager.execute(
                "DELETE FROM plugin_instances WHERE plugin_id = ?",
                (plugin_id,)
            )
            
            # 从缓存中删除
            if plugin_id in self._config_cache:
                del self._config_cache[plugin_id]
            
            logger.info(f"删除插件配置: {plugin_id}")
            return True
            
        except Exception as e:
            logger.error(f"删除插件配置失败: {plugin_id}, 错误: {e}")
            return False


# 全局插件配置管理器实例
plugin_config_manager = PluginConfigManager()
