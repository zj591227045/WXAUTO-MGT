"""
配置存储模块

提供一个简单的配置存储和读取机制，用于保存和获取配置项。
"""

import logging
import aiosqlite
import json
import os
import asyncio
import time

# 获取日志记录器
logger = logging.getLogger(__name__)

class ConfigStore:
    """配置存储类，提供配置的保存和获取功能"""
    
    def __init__(self, db_path=None):
        """初始化配置存储
        
        Args:
            db_path: 数据库文件路径，为None则使用默认路径
        """
        # 如果未指定数据库路径，则使用默认路径
        if db_path is None:
            # 获取项目根目录
            root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            db_path = os.path.join(root_dir, 'data', 'wxauto_mgt.db')
        
        self.db_path = db_path
        logger.debug(f"配置存储使用数据库: {db_path}")
    
    async def get_config(self, section, key, default=None):
        """获取配置项
        
        Args:
            section: 配置区域名称
            key: 配置项键名
            default: 默认值，如果配置不存在则返回此值
            
        Returns:
            配置值，如果不存在则返回默认值
        """
        try:
            # 使用复合键，将section和key组合为一个键值
            composite_key = f"{section}.{key}"
            
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = lambda cursor, row: {
                    col[0]: row[idx] for idx, col in enumerate(cursor.description)
                }
                
                query = "SELECT value FROM configs WHERE key = ?"
                params = (composite_key,)
                
                cursor = await db.execute(query, params)
                result = await cursor.fetchone()
                
                if result:
                    value = result['value']
                    # 尝试解析JSON
                    try:
                        return json.loads(value)
                    except:
                        return value
                        
                logger.debug(f"配置项不存在: {section}.{key}，使用默认值: {default}")
                return default
                
        except Exception as e:
            logger.error(f"获取配置项时出错: {e}")
            return default

    def get_config_sync(self, section, key, default=None):
        """同步获取配置项

        Args:
            section: 配置区域名称
            key: 配置项键名
            default: 默认值，如果配置不存在则返回此值

        Returns:
            配置值，如果不存在则返回默认值
        """
        try:
            import sqlite3
            # 使用复合键，将section和key组合为一个键值
            composite_key = f"{section}.{key}"

            with sqlite3.connect(self.db_path) as db:
                db.row_factory = sqlite3.Row

                query = "SELECT value FROM configs WHERE key = ?"
                params = (composite_key,)

                cursor = db.execute(query, params)
                result = cursor.fetchone()

                if result:
                    value = result['value']
                    # 尝试解析JSON
                    try:
                        return json.loads(value)
                    except:
                        return value

                logger.debug(f"配置项不存在: {section}.{key}，使用默认值: {default}")
                return default

        except Exception as e:
            logger.error(f"同步获取配置项时出错: {e}")
            return default

    async def set_config(self, section, key, value):
        """设置配置项
        
        Args:
            section: 配置区域名称
            key: 配置项键名
            value: 配置值，会自动序列化为JSON
            
        Returns:
            bool: 是否设置成功
        """
        try:
            # 使用复合键，将section和key组合为一个键值
            composite_key = f"{section}.{key}"
            
            # 转换复杂对象为JSON字符串
            if not isinstance(value, (str, int, float, bool, type(None))):
                value = json.dumps(value)
            elif isinstance(value, (dict, list)):
                value = json.dumps(value)
            else:
                value = str(value)
            
            current_time = int(time.time())
            
            async with aiosqlite.connect(self.db_path) as db:
                # 检查键是否已存在
                cursor = await db.execute("SELECT key FROM configs WHERE key = ?", (composite_key,))
                exists = await cursor.fetchone()
                
                if exists:
                    # 已存在，执行更新
                    query = """
                    UPDATE configs 
                    SET value = ?, last_update = ? 
                    WHERE key = ?
                    """
                    await db.execute(query, (value, current_time, composite_key))
                else:
                    # 不存在，插入新记录
                    query = """
                    INSERT INTO configs (key, value, encrypted, create_time, last_update)
                    VALUES (?, ?, 0, ?, ?)
                    """
                    await db.execute(query, (composite_key, value, current_time, current_time))
                
                await db.commit()
                logger.debug(f"配置项已设置: {composite_key} = {value}")
                return True
                
        except Exception as e:
            logger.error(f"设置配置项时出错: {e}")
            return False
    
    async def delete_config(self, section, key=None):
        """删除配置项
        
        Args:
            section: 配置区域名称
            key: 配置项键名，为None则删除整个区域
            
        Returns:
            bool: 是否删除成功
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                if key is None:
                    # 删除整个区域的配置，使用LIKE进行匹配
                    pattern = f"{section}.%"
                    query = "DELETE FROM configs WHERE key LIKE ?"
                    await db.execute(query, (pattern,))
                else:
                    # 删除特定配置项
                    composite_key = f"{section}.{key}"
                    query = "DELETE FROM configs WHERE key = ?"
                    await db.execute(query, (composite_key,))
                
                await db.commit()
                logger.debug(f"配置项已删除: {section}.{key if key else '*'}")
                return True
                
        except Exception as e:
            logger.error(f"删除配置项时出错: {e}")
            return False

# 创建全局实例
config_store = ConfigStore() 