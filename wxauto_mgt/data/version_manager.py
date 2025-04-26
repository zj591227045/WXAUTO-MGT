"""
版本管理模块

负责管理软件版本信息，包括版本检查、更新等功能。
支持多实例版本管理。
"""

import asyncio
import logging
import time
from typing import Dict, Optional, Tuple, List

from ..data.db_manager import db_manager

logger = logging.getLogger(__name__)

class VersionManager:
    """版本管理器，负责管理软件版本信息"""
    
    def __init__(self):
        """初始化版本管理器"""
        self._lock = asyncio.Lock()
        self._version_cache = {}
        
    async def save_version(self, instance_id: str, version_info: Dict) -> bool:
        """
        保存版本信息
        
        Args:
            instance_id: 实例ID
            version_info: 版本信息
            
        Returns:
            bool: 是否成功保存
        """
        try:
            data = {
                'instance_id': instance_id,
                'version': version_info.get('version'),
                'build_number': version_info.get('build_number'),
                'release_date': version_info.get('release_date'),
                'features': version_info.get('features'),
                'create_time': int(time.time())
            }
            
            await db_manager.insert('versions', data)
            self._version_cache[instance_id] = version_info
            logger.debug(f"版本信息已保存: {instance_id}")
            return True
        except Exception as e:
            logger.error(f"保存版本信息失败: {str(e)}")
            return False
            
    async def get_version(self, instance_id: str) -> Optional[Dict]:
        """
        获取版本信息
        
        Args:
            instance_id: 实例ID
            
        Returns:
            Optional[Dict]: 版本信息
        """
        try:
            # 先从缓存获取
            if instance_id in self._version_cache:
                return self._version_cache[instance_id]
                
            # 从数据库获取
            sql = "SELECT * FROM versions WHERE instance_id = ? ORDER BY create_time DESC LIMIT 1"
            version = await db_manager.fetchone(sql, (instance_id,))
            
            if version:
                self._version_cache[instance_id] = version
            return version
        except Exception as e:
            logger.error(f"获取版本信息失败: {str(e)}")
            return None
            
    async def check_update(self, instance_id: str, current_version: str) -> Tuple[bool, Optional[Dict]]:
        """
        检查更新
        
        Args:
            instance_id: 实例ID
            current_version: 当前版本号
            
        Returns:
            Tuple[bool, Optional[Dict]]: (是否有更新, 更新信息)
        """
        try:
            sql = """
            SELECT * FROM versions 
            WHERE instance_id = ? AND version > ? 
            ORDER BY version DESC 
            LIMIT 1
            """
            update = await db_manager.fetchone(sql, (instance_id, current_version))
            
            if update:
                return True, update
            return False, None
        except Exception as e:
            logger.error(f"检查更新失败: {str(e)}")
            return False, None
            
    async def get_version_history(self, instance_id: str, limit: int = 10) -> List[Dict]:
        """
        获取版本历史
        
        Args:
            instance_id: 实例ID
            limit: 返回记录数量限制
            
        Returns:
            List[Dict]: 版本历史记录
        """
        try:
            sql = """
            SELECT * FROM versions 
            WHERE instance_id = ? 
            ORDER BY create_time DESC 
            LIMIT ?
            """
            history = await db_manager.fetchall(sql, (instance_id, limit))
            return history
        except Exception as e:
            logger.error(f"获取版本历史失败: {str(e)}")
            return []
            
    async def cleanup_old_versions(self, keep_versions: int = 5) -> bool:
        """
        清理旧版本记录
        
        Args:
            keep_versions: 保留的版本数量
            
        Returns:
            bool: 是否成功清理
        """
        try:
            sql = """
            DELETE FROM versions 
            WHERE id NOT IN (
                SELECT id FROM (
                    SELECT id FROM versions 
                    ORDER BY create_time DESC 
                    LIMIT ?
                )
            )
            """
            await db_manager.execute(sql, (keep_versions,))
            logger.info(f"已清理旧版本记录，保留最新的{keep_versions}个版本")
            return True
        except Exception as e:
            logger.error(f"清理旧版本记录失败: {str(e)}")
            return False

# 创建全局实例
version_manager = VersionManager() 