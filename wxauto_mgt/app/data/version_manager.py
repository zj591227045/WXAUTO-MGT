"""
版本管理模块

负责管理应用版本信息、版本检查和数据库迁移。
提供版本比较、检查更新和迁移功能。
"""

import asyncio
import json
import os
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union
import aiohttp
import semver
from packaging import version

from app.data.db_manager import db_manager
from app.data.config_store import config_store
from app.utils.logging import get_logger

logger = get_logger()


class VersionManager:
    """
    版本管理类，负责管理应用版本信息、检查更新和执行迁移
    """
    
    # 当前应用版本
    CURRENT_VERSION = "0.1.0"
    
    # 版本检查URL
    DEFAULT_VERSION_CHECK_URL = "https://api.github.com/repos/user/wxauto_mgt/releases/latest"
    
    def __init__(self):
        """初始化版本管理器"""
        self._lock = asyncio.Lock()
        self._initialized = False
        self._db_version = None
        logger.debug("初始化版本管理器")
    
    async def initialize(self) -> None:
        """
        初始化版本管理器
        
        确保版本表已创建，并加载当前数据库版本
        """
        if self._initialized:
            logger.debug("版本管理器已初始化")
            return
        
        # 确保数据库已初始化
        await db_manager.initialize()
        
        # 确保配置存储已初始化
        await config_store.initialize()
        
        # 检查并创建版本表
        async with self._lock:
            try:
                # 获取当前数据库版本
                self._db_version = await self._get_db_version()
                
                # 如果版本不存在，则初始化为当前版本
                if not self._db_version:
                    await self._set_db_version(self.CURRENT_VERSION)
                    self._db_version = self.CURRENT_VERSION
                
                # 检查是否需要迁移
                if self._db_version != self.CURRENT_VERSION:
                    logger.info(f"检测到版本差异: 数据库版本 {self._db_version}, 应用版本 {self.CURRENT_VERSION}")
                    await self._run_migrations()
            except Exception as e:
                logger.error(f"初始化版本管理器失败: {e}")
                raise
        
        self._initialized = True
        logger.info("版本管理器初始化完成")
    
    async def _get_db_version(self) -> Optional[str]:
        """
        获取当前数据库版本
        
        Returns:
            Optional[str]: 数据库版本号，如果不存在则返回None
        """
        try:
            # 从配置中获取版本
            version = await config_store.get_config("app_version")
            return version
        except Exception as e:
            logger.error(f"获取数据库版本失败: {e}")
            return None
    
    async def _set_db_version(self, version: str) -> bool:
        """
        设置数据库版本
        
        Args:
            version: 版本号
            
        Returns:
            bool: 是否成功设置
        """
        try:
            # 存储版本到配置
            result = await config_store.save_config("app_version", version)
            
            if result:
                # 同时记录版本更新时间
                await config_store.save_config("app_version_updated", int(time.time()))
                logger.info(f"已设置数据库版本为 {version}")
                return True
            return False
        except Exception as e:
            logger.error(f"设置数据库版本失败: {e}")
            return False
    
    async def _run_migrations(self) -> bool:
        """
        执行数据库迁移
        
        从当前数据库版本迁移到应用版本
        
        Returns:
            bool: 是否成功迁移
        """
        if not self._db_version:
            logger.warning("数据库版本未知，无法执行迁移")
            return False
        
        # 解析版本
        try:
            current_ver = version.parse(self._db_version)
            target_ver = version.parse(self.CURRENT_VERSION)
            
            if current_ver > target_ver:
                logger.warning(f"数据库版本 ({self._db_version}) 高于应用版本 ({self.CURRENT_VERSION})，跳过迁移")
                return False
            
            if current_ver == target_ver:
                logger.debug("数据库版本已是最新，无需迁移")
                return True
            
            # 执行迁移
            logger.info(f"开始数据库迁移: {self._db_version} -> {self.CURRENT_VERSION}")
            
            # 迁移记录：版本号 -> 迁移函数
            migrations = {
                # 示例迁移
                "0.1.0": self._migrate_to_0_1_0,
                "0.2.0": self._migrate_to_0_2_0,
            }
            
            # 获取所有版本并排序
            versions = sorted(
                [version.parse(v) for v in migrations.keys()],
                key=lambda v: v
            )
            
            # 找到需要执行的迁移
            to_run = [str(v) for v in versions if current_ver < v <= target_ver]
            
            if not to_run:
                logger.warning(f"未找到从 {self._db_version} 到 {self.CURRENT_VERSION} 的迁移路径")
                return False
            
            # 执行迁移
            for ver in to_run:
                if ver in migrations:
                    logger.info(f"执行迁移到版本 {ver}")
                    success = await migrations[ver]()
                    
                    if not success:
                        logger.error(f"迁移到版本 {ver} 失败")
                        return False
                    
                    # 更新数据库版本
                    await self._set_db_version(ver)
            
            # 最终更新到目标版本
            if self.CURRENT_VERSION not in to_run:
                await self._set_db_version(self.CURRENT_VERSION)
            
            logger.info(f"数据库迁移完成: {self._db_version} -> {self.CURRENT_VERSION}")
            return True
            
        except Exception as e:
            logger.error(f"执行数据库迁移失败: {e}")
            return False
    
    async def _migrate_to_0_1_0(self) -> bool:
        """
        迁移到版本 0.1.0
        
        创建初始数据库表结构
        
        Returns:
            bool: 是否成功迁移
        """
        try:
            # 创建配置表
            await db_manager.execute("""
                CREATE TABLE IF NOT EXISTS configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT NOT NULL UNIQUE,
                    value TEXT NOT NULL,
                    encrypted INTEGER NOT NULL DEFAULT 0,
                    updated_at INTEGER NOT NULL
                )
            """)
            
            # 创建配置版本表
            await db_manager.execute("""
                CREATE TABLE IF NOT EXISTS config_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    config_key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    encrypted INTEGER NOT NULL DEFAULT 0,
                    timestamp INTEGER NOT NULL
                )
            """)
            
            # 创建消息队列表
            await db_manager.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id TEXT NOT NULL UNIQUE,
                    instance_id TEXT NOT NULL,
                    message_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    retry_count INTEGER NOT NULL DEFAULT 0
                )
            """)
            
            # 创建索引
            await db_manager.execute("CREATE INDEX IF NOT EXISTS idx_messages_status ON messages(status)")
            await db_manager.execute("CREATE INDEX IF NOT EXISTS idx_messages_instance ON messages(instance_id)")
            await db_manager.execute("CREATE INDEX IF NOT EXISTS idx_configs_key ON configs(key)")
            await db_manager.execute("CREATE INDEX IF NOT EXISTS idx_config_versions_timestamp ON config_versions(timestamp)")
            
            return True
        
        except Exception as e:
            logger.error(f"迁移到版本 0.1.0 失败: {e}")
            return False
    
    async def _migrate_to_0_2_0(self) -> bool:
        """
        迁移到版本 0.2.0
        
        添加实例管理和日志表
        
        Returns:
            bool: 是否成功迁移
        """
        try:
            # 创建实例表
            await db_manager.execute("""
                CREATE TABLE IF NOT EXISTS instances (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    instance_id TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    api_url TEXT NOT NULL,
                    api_key TEXT,
                    status TEXT NOT NULL DEFAULT 'inactive',
                    last_active INTEGER,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    config TEXT
                )
            """)
            
            # 创建日志表
            await db_manager.execute("""
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    level TEXT NOT NULL,
                    module TEXT NOT NULL,
                    message TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    details TEXT
                )
            """)
            
            # 创建索引
            await db_manager.execute("CREATE INDEX IF NOT EXISTS idx_instances_status ON instances(status)")
            await db_manager.execute("CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs(timestamp)")
            await db_manager.execute("CREATE INDEX IF NOT EXISTS idx_logs_level ON logs(level)")
            
            return True
        
        except Exception as e:
            logger.error(f"迁移到版本 0.2.0 失败: {e}")
            return False
    
    async def get_version_info(self) -> Dict:
        """
        获取版本信息
        
        返回当前应用版本和数据库版本
        
        Returns:
            Dict: 版本信息字典
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            # 获取当前数据库版本
            db_version = await self._get_db_version()
            
            # 获取版本更新时间
            updated_at = await config_store.get_config("app_version_updated")
            
            updated_time = None
            if updated_at:
                try:
                    updated_time = datetime.fromtimestamp(int(updated_at)).strftime("%Y-%m-%d %H:%M:%S")
                except (ValueError, TypeError):
                    pass
            
            return {
                "app_version": self.CURRENT_VERSION,
                "db_version": db_version,
                "db_updated_at": updated_time,
                "is_latest": db_version == self.CURRENT_VERSION
            }
        
        except Exception as e:
            logger.error(f"获取版本信息失败: {e}")
            return {
                "app_version": self.CURRENT_VERSION,
                "db_version": "unknown",
                "db_updated_at": None,
                "is_latest": False,
                "error": str(e)
            }
    
    async def check_for_updates(self, force: bool = False) -> Dict:
        """
        检查更新
        
        连接到更新服务器检查是否有新版本
        
        Args:
            force: 是否强制检查，忽略缓存
            
        Returns:
            Dict: 更新信息字典
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            # 获取上次检查时间
            last_check = await config_store.get_config("update_last_check")
            last_check_time = int(last_check) if last_check else 0
            current_time = int(time.time())
            
            # 默认间隔为24小时
            check_interval = int(await config_store.get_config("update_check_interval", 86400))
            
            # 检查是否需要更新
            if not force and last_check_time > 0 and (current_time - last_check_time) < check_interval:
                # 返回缓存的更新信息
                update_info = await config_store.get_config("update_info", {})
                if update_info:
                    update_info["from_cache"] = True
                    return update_info
            
            # 获取版本检查URL
            version_url = await config_store.get_config(
                "update_check_url", 
                self.DEFAULT_VERSION_CHECK_URL
            )
            
            # 执行HTTP请求检查更新
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(version_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # 解析返回数据
                        latest_version = data.get("tag_name", "").lstrip("v")
                        
                        # 比较版本
                        has_update = False
                        try:
                            has_update = version.parse(latest_version) > version.parse(self.CURRENT_VERSION)
                        except Exception:
                            pass
                        
                        update_info = {
                            "current_version": self.CURRENT_VERSION,
                            "latest_version": latest_version,
                            "has_update": has_update,
                            "release_notes": data.get("body", ""),
                            "release_url": data.get("html_url", ""),
                            "assets": [
                                {
                                    "name": asset.get("name", ""),
                                    "size": asset.get("size", 0),
                                    "download_url": asset.get("browser_download_url", "")
                                }
                                for asset in data.get("assets", [])
                            ],
                            "last_checked": current_time,
                            "from_cache": False
                        }
                        
                        # 保存更新信息和检查时间
                        await config_store.save_config("update_info", update_info)
                        await config_store.save_config("update_last_check", current_time)
                        
                        return update_info
                    else:
                        # 检查失败
                        logger.warning(f"检查更新失败，HTTP状态码: {response.status}")
                        return {
                            "error": f"检查更新失败: HTTP {response.status}",
                            "current_version": self.CURRENT_VERSION,
                            "has_update": False,
                            "last_checked": current_time,
                            "from_cache": False
                        }
        
        except asyncio.TimeoutError:
            logger.warning("检查更新超时")
            return {
                "error": "检查更新超时",
                "current_version": self.CURRENT_VERSION,
                "has_update": False,
                "from_cache": False
            }
        
        except Exception as e:
            logger.error(f"检查更新失败: {e}")
            return {
                "error": f"检查更新失败: {str(e)}",
                "current_version": self.CURRENT_VERSION,
                "has_update": False,
                "from_cache": False
            }
    
    @staticmethod
    def compare_versions(version1: str, version2: str) -> int:
        """
        比较两个版本号
        
        Args:
            version1: 第一个版本号
            version2: 第二个版本号
            
        Returns:
            int: 如果version1 > version2返回1，如果version1 < version2返回-1，如果相等返回0
        """
        try:
            v1 = version.parse(version1)
            v2 = version.parse(version2)
            
            if v1 > v2:
                return 1
            elif v1 < v2:
                return -1
            else:
                return 0
        except Exception as e:
            logger.error(f"比较版本失败: {e}")
            # 如果解析失败，使用字符串比较
            if version1 > version2:
                return 1
            elif version1 < version2:
                return -1
            else:
                return 0
    
    @staticmethod
    def is_compatible_version(version_str: str, min_version: str, max_version: Optional[str] = None) -> bool:
        """
        检查版本兼容性
        
        Args:
            version_str: 待检查的版本
            min_version: 最小兼容版本
            max_version: 最大兼容版本，如果为None则不检查上限
            
        Returns:
            bool: 是否兼容
        """
        try:
            v = version.parse(version_str)
            min_v = version.parse(min_version)
            
            if v < min_v:
                return False
            
            if max_version is not None:
                max_v = version.parse(max_version)
                if v > max_v:
                    return False
            
            return True
        except Exception as e:
            logger.error(f"检查版本兼容性失败: {e}")
            return False


# 创建全局版本管理器实例
version_manager = VersionManager() 