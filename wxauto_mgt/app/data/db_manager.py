"""
数据库管理模块

负责应用程序的SQLite数据库连接、查询执行和事务管理。
提供异步接口与SQLite数据库交互。
"""

import asyncio
import os
import sqlite3
import time
import traceback
import platform
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import aiosqlite
from app.utils.logging import get_logger

logger = get_logger()


class DBManager:
    """
    数据库管理类，负责与SQLite数据库的交互。
    提供异步接口执行SQL查询，管理连接池和事务。
    """

    def __init__(self, db_path: str = None):
        """
        初始化数据库管理器
        
        Args:
            db_path: 数据库文件路径，如果为None则使用默认路径
        """
        self._db_path = db_path
        self._initialized = False
        self._connection = None
        self._lock = asyncio.Lock()
        self._transaction_lock = asyncio.Lock()
        self._active_connections = 0
        self._max_connections = 5
        logger.debug(f"初始化数据库管理器, 数据库路径: {db_path}")
    
    async def initialize(self, recreate_db: bool = False) -> bool:
        """
        初始化数据库，创建必要的目录和连接
        
        Args:
            recreate_db: 是否重新创建数据库文件，默认为False
        
        Returns:
            bool: 是否成功初始化
        """
        if self._initialized:
            logger.info("数据库已初始化，跳过")
            return True
        
        # 获取应用数据目录
        if not self._db_path:
            # 使用项目data目录而非用户目录
            app_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            app_data_dir = os.path.join(app_dir, "data")
            os.makedirs(app_data_dir, exist_ok=True)
            self._db_path = os.path.join(app_data_dir, "wxauto_mgt.db")
            logger.info(f"使用项目数据库路径: {self._db_path}")
        
        # 确保数据库目录存在
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        
        # 检查文件权限
        self._check_file_permissions()
        
        try:
            # 改用同步SQLite3初始化数据库
            logger.info(f"使用同步方式初始化SQLite数据库: {self._db_path}")
            
            # 如果指定了重新创建并且文件存在，则备份并删除旧文件
            if recreate_db and os.path.exists(self._db_path):
                logger.info(f"检测到现有数据库文件，备份并重新创建: {self._db_path}")
                backup_dir = os.path.join(os.path.dirname(self._db_path), "backup")
                os.makedirs(backup_dir, exist_ok=True)
                backup_file = os.path.join(backup_dir, f"wxauto_mgt.db.bak.{int(time.time())}")
                
                try:
                    import shutil
                    shutil.copy2(self._db_path, backup_file)
                    logger.info(f"已备份数据库文件: {backup_file}")
                    os.remove(self._db_path)
                    logger.info(f"已删除旧数据库文件: {self._db_path}")
                except Exception as e:
                    logger.warning(f"备份/删除旧数据库文件失败: {str(e)}")
            elif os.path.exists(self._db_path):
                logger.info(f"使用现有数据库文件: {self._db_path}")
            
            # 创建新的数据库连接
            conn = None
            try:
                logger.info("创建数据库连接...")
                conn = sqlite3.connect(self._db_path, timeout=10.0)
                
                # 设置数据库参数
                logger.info("设置数据库PRAGMA参数...")
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
                conn.execute("PRAGMA foreign_keys=ON")
                conn.commit()
            
                # 创建表（如果不存在）
                logger.info("确保数据库表存在...")
                self._create_tables_sync(conn)
                
                logger.info("数据库初始化成功")
                self._initialized = True
                
                # 关闭连接
                conn.close()
                logger.info("初始化连接已关闭")
                
                return True
            except Exception as e:
                if conn:
                    try:
                        conn.close()
                    except:
                        pass
                logger.error(f"同步初始化数据库失败: {str(e)}")
                traceback.print_exc()
                return False
        except Exception as e:
            logger.error(f"数据库初始化失败: {str(e)}")
            traceback.print_exc()
            return False
    
    def _create_tables_sync(self, conn: sqlite3.Connection) -> bool:
        """
        使用同步方式创建数据库表
        
        Args:
            conn: SQLite连接
            
        Returns:
            bool: 是否成功创建表
        """
        try:
            # 配置表
            logger.info("创建配置表...")
            configs_schema = """
            CREATE TABLE IF NOT EXISTS configs (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                encrypted INTEGER DEFAULT 0,
                version INTEGER DEFAULT 1,
                create_time INTEGER DEFAULT (strftime('%s', 'now')),
                last_update INTEGER DEFAULT (strftime('%s', 'now'))
            )
            """
            conn.execute(configs_schema)
            
            # 状态日志表
            logger.info("创建状态日志表...")
            status_logs_schema = """
            CREATE TABLE IF NOT EXISTS status_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                instance_id TEXT NOT NULL,
                status TEXT NOT NULL,
                message TEXT,
                details TEXT,
                create_time INTEGER DEFAULT (strftime('%s', 'now'))
            )
            """
            conn.execute(status_logs_schema)
            
            # 性能指标表
            logger.info("创建性能指标表...")
            performance_metrics_schema = """
            CREATE TABLE IF NOT EXISTS performance_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                instance_id TEXT NOT NULL,
                metric_type TEXT NOT NULL,
                value REAL NOT NULL,
                details TEXT,
                create_time INTEGER DEFAULT (strftime('%s', 'now'))
            )
            """
            conn.execute(performance_metrics_schema)
            
            # 监听对象表
            logger.info("创建监听对象表...")
            listeners_schema = """
            CREATE TABLE IF NOT EXISTS listeners (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                instance_id TEXT NOT NULL,
                who TEXT NOT NULL,
                last_message_time INTEGER DEFAULT 0,
                create_time INTEGER DEFAULT (strftime('%s', 'now')),
                UNIQUE(instance_id, who)
            )
            """
            conn.execute(listeners_schema)
            
            # 提交事务
            conn.commit()
            logger.info("所有表创建成功")
            
            return True
        except Exception as e:
            logger.error(f"同步创建表失败: {str(e)}")
            traceback.print_exc()
            return False
    
    def _check_file_permissions(self):
        """检查并修复数据库文件权限"""
        db_dir = os.path.dirname(self._db_path)
        logger.info(f"检查数据库目录权限: {db_dir}")
        
        try:
            # 确保目录存在且有写权限
            if not os.path.exists(db_dir):
                logger.info(f"创建数据库目录: {db_dir}")
                os.makedirs(db_dir, exist_ok=True)
            
            # 检查目录权限
            if not os.access(db_dir, os.W_OK | os.R_OK):
                logger.warning(f"数据库目录权限不足: {db_dir}")
                try:
                    # 尝试修改权限
                    import stat
                    current_mode = os.stat(db_dir).st_mode
                    new_mode = current_mode | stat.S_IRUSR | stat.S_IWUSR
                    os.chmod(db_dir, new_mode)
                    logger.info(f"已修改目录权限: {db_dir}")
                except Exception as e:
                    logger.error(f"无法修改目录权限: {str(e)}")
            
            # 如果数据库文件已存在，检查文件权限
            if os.path.exists(self._db_path):
                if not os.access(self._db_path, os.W_OK | os.R_OK):
                    logger.warning(f"数据库文件权限不足: {self._db_path}")
                    try:
                        # 尝试修改权限
                        import stat
                        current_mode = os.stat(self._db_path).st_mode
                        new_mode = current_mode | stat.S_IRUSR | stat.S_IWUSR
                        os.chmod(self._db_path, new_mode)
                        logger.info(f"已修改文件权限: {self._db_path}")
                    except Exception as e:
                        logger.error(f"无法修改文件权限: {str(e)}")
            
            # 测试能否写入目录
            test_file = os.path.join(db_dir, ".write_test")
            try:
                with open(test_file, "w") as f:
                    f.write("test")
                os.remove(test_file)
                logger.debug(f"目录写入测试成功: {db_dir}")
            except Exception as e:
                logger.error(f"目录写入测试失败: {str(e)}")
        
        except Exception as e:
            logger.error(f"检查文件权限出错: {str(e)}")
    
    async def get_connection(self) -> aiosqlite.Connection:
        """
        获取数据库连接
        
        Returns:
            aiosqlite.Connection: 数据库连接对象
        
        Raises:
            Exception: 获取连接失败
        """
        if not self._initialized:
            logger.warning("数据库未初始化，尝试初始化")
            if not await self.initialize():
                raise Exception("数据库初始化失败")
        
        async with self._lock:
            if self._connection is None:
                logger.debug("创建新的数据库连接")
                self._connection = await aiosqlite.connect(self._db_path)
                await self._connection.execute("PRAGMA journal_mode=WAL")
                await self._connection.execute("PRAGMA synchronous=NORMAL")
                await self._connection.execute("PRAGMA foreign_keys=ON")
                self._connection.row_factory = aiosqlite.Row
                self._active_connections = 1
            else:
                # 检查连接是否有效
                try:
                    # 简单查询测试连接是否有效
                    async with self._connection.execute("SELECT 1") as cursor:
                        await cursor.fetchone()
                except Exception as e:
                    logger.warning(f"数据库连接无效，重新连接: {e}")
                    try:
                        await self._connection.close()
                    except:
                        pass
                    self._connection = await aiosqlite.connect(self._db_path)
                    await self._connection.execute("PRAGMA journal_mode=WAL")
                    await self._connection.execute("PRAGMA synchronous=NORMAL")
                    await self._connection.execute("PRAGMA foreign_keys=ON")
                    self._connection.row_factory = aiosqlite.Row
                    self._active_connections = 1
            
            # 我们使用单一连接，不要增加计数
            return self._connection
    
    async def close(self) -> None:
        """关闭数据库连接"""
        if self._connection:
            try:
                logger.info("关闭数据库连接")
                await self._connection.close()
                self._connection = None
                logger.info("数据库连接已关闭")
            except Exception as e:
                logger.error(f"关闭数据库连接失败: {e}")
                # 确保连接被标记为关闭
                self._connection = None

    async def execute(self, sql: str, params: tuple = None) -> int:
        """
        执行SQL语句
        
        Args:
            sql: SQL语句
            params: 参数元组或列表
            
        Returns:
            int: 受影响的行数或插入的ID
        """
        conn = await self.get_connection()
        try:
            async with conn.cursor() as cursor:
                await cursor.execute(sql, params or ())
                await conn.commit()
                return cursor.lastrowid or cursor.rowcount
        except Exception as e:
            logger.error(f"执行SQL失败: {e}, SQL: {sql}")
            raise

    async def fetchall(self, sql: str, params: tuple = None) -> List[Dict]:
        """
        执行查询并返回所有结果
        
        Args:
            sql: SQL查询语句
            params: 参数元组或列表
            
        Returns:
            List[Dict]: 结果集
        """
        conn = await self.get_connection()
        try:
            async with conn.execute(sql, params or ()) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"查询失败: {e}, SQL: {sql}")
            raise

    async def fetch_one(self, sql: str, params: tuple = None) -> Optional[Dict]:
        """
        执行查询并返回第一条结果
        
        Args:
            sql: SQL查询语句
            params: 参数元组或列表
            
        Returns:
            Optional[Dict]: 结果字典或None
        """
        conn = await self.get_connection()
        try:
            async with conn.execute(sql, params or ()) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"查询单行失败: {e}, SQL: {sql}")
            raise

    async def fetch_all(self, sql: str, params: tuple = None) -> List[Dict]:
        """
        执行查询并返回所有结果（别名，同fetchall）
        
        Args:
            sql: SQL查询语句
            params: 参数元组或列表
            
        Returns:
            List[Dict]: 结果集
        """
        return await self.fetchall(sql, params)

    async def insert(self, table: str, data: Dict) -> int:
        """
        插入数据
        
        Args:
            table: 表名
            data: 数据字典
            
        Returns:
            int: 插入的记录ID
        """
        keys = list(data.keys())
        values = list(data.values())
        placeholders = ', '.join(['?' for _ in keys])
        columns = ', '.join(keys)
        
        sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        
        return await self.execute(sql, values)

# 创建全局数据库管理器实例
db_manager = DBManager() 