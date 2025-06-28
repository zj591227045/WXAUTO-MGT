
"""
数据库管理模块

负责管理SQLite数据库连接、查询执行和事务管理。提供异步接口用于数据库交互。
支持多实例管理。
"""

import asyncio
import os
import sqlite3
import time
import traceback
import platform
import aiosqlite
import logging
from typing import Dict, List, Optional, Any, Union

logger = logging.getLogger(__name__)

class DBManager:
    """数据库管理器，负责管理数据库连接和操作"""

    def __init__(self):
        """初始化数据库管理器"""
        self._db_path = None
        self._initialized = False
        self._lock = asyncio.Lock()
        self._connection = None

    async def initialize(self, db_path: str = None) -> None:
        """
        初始化数据库

        Args:
            db_path: 数据库文件路径，如果为None则使用默认路径
        """
        if self._initialized:
            logger.warning("数据库管理器已经初始化")
            return

        # 如果未指定路径，使用默认路径
        if db_path is None:
            # 使用项目相对路径
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
            db_path = os.path.join(project_root, 'data', 'wxauto_mgt.db')

        self._db_path = db_path

        # 确保数据库目录存在
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        # 初始化数据库
        await self._init_db()

        # 标记为已初始化
        self._initialized = True

        # 检查并确保触发器存在
        try:
            await self._ensure_triggers()
        except Exception as e:
            logger.error(f"确保触发器存在时出错: {e}")
            # 不要因为触发器问题而阻止应用程序启动

        # 检查并更新表结构
        try:
            await self._check_and_update_tables()
        except Exception as e:
            logger.error(f"检查并更新表结构时出错: {e}")
            # 不要因为表结构问题而阻止应用程序启动

        logger.info(f"数据库初始化完成: {db_path}")

    async def _init_db(self) -> None:
        """初始化数据库结构"""
        # 同步创建数据库文件和表
        conn = sqlite3.connect(self._db_path)
        try:
            # 设置数据库配置
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA temp_store=MEMORY")
            conn.execute("PRAGMA mmap_size=30000000000")
            conn.execute("PRAGMA page_size=4096")

            # 创建表
            await self._create_tables_sync(conn)
            conn.commit()
        finally:
            conn.close()

    async def _ensure_triggers(self) -> None:
        """确保所有必要的触发器存在"""
        try:
            # 检查触发器是否存在
            trigger_exists = await self.fetchone(
                "SELECT name FROM sqlite_master WHERE type='trigger' AND name='delete_self_time_messages'"
            )

            if not trigger_exists:
                logger.info("消息过滤触发器不存在，正在创建...")

                # 创建触发器
                await self.execute("""
                CREATE TRIGGER IF NOT EXISTS delete_self_time_messages
                AFTER INSERT ON messages
                FOR EACH ROW
                WHEN LOWER(NEW.sender) = 'self' OR
                     LOWER(NEW.message_type) = 'self' OR
                     LOWER(NEW.message_type) = 'time' OR
                     LOWER(NEW.mtype) = '10000' OR
                     LOWER(NEW.mtype) = '10002'
                BEGIN
                    DELETE FROM messages WHERE message_id = NEW.message_id;
                END
                """)

                logger.info("消息过滤触发器创建成功")
            else:
                logger.debug("消息过滤触发器已存在")
        except Exception as e:
            logger.error(f"确保触发器存在时出错: {str(e)}")

    async def _check_and_update_tables(self) -> None:
        """检查并更新表结构，添加缺少的字段"""
        try:
            # 检查listeners表是否有conversation_id字段
            listeners_table_info = await self._get_table_structure('listeners')
            listeners_columns = {col["name"] for col in listeners_table_info}

            if 'conversation_id' not in listeners_columns:
                logger.info("listeners表缺少conversation_id字段，正在添加...")

                # 添加conversation_id字段
                await self.execute("""
                ALTER TABLE listeners ADD COLUMN conversation_id TEXT
                """)

                logger.info("成功添加conversation_id字段到listeners表")
            else:
                logger.debug("listeners表已有conversation_id字段")

        except Exception as e:
            logger.error(f"检查并更新表结构时出错: {str(e)}")
            logger.error(traceback.format_exc())

    async def _create_tables_sync(self, conn: sqlite3.Connection) -> None:
        """创建数据库表"""
        # 配置表
        conn.execute("""
        CREATE TABLE IF NOT EXISTS configs (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            encrypted INTEGER NOT NULL DEFAULT 0,
            create_time INTEGER NOT NULL,
            last_update INTEGER NOT NULL
        )
        """)
        logger.debug("创建configs表")

        # 实例表
        conn.execute("""
        CREATE TABLE IF NOT EXISTS instances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            instance_id TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            base_url TEXT NOT NULL,
            api_key TEXT,
            status TEXT NOT NULL DEFAULT 'inactive',
            enabled INTEGER NOT NULL DEFAULT 1,
            last_active INTEGER,
            created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
            updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
            config TEXT
        )
        """)
        logger.debug("创建instances表")

        # 状态日志表
        conn.execute("""
        CREATE TABLE IF NOT EXISTS status_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            instance_id TEXT NOT NULL,
            status TEXT NOT NULL,
            details TEXT,
            create_time INTEGER NOT NULL
        )
        """)
        logger.debug("创建status_logs表")

        # 性能指标表
        conn.execute("""
        CREATE TABLE IF NOT EXISTS performance_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            instance_id TEXT NOT NULL,
            metric_type TEXT NOT NULL,
            value REAL NOT NULL,
            create_time INTEGER NOT NULL
        )
        """)
        logger.debug("创建performance_metrics表")

        # 警报规则表
        conn.execute("""
        CREATE TABLE IF NOT EXISTS alert_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            instance_id TEXT NOT NULL,
            metric_type TEXT NOT NULL,
            threshold REAL NOT NULL,
            threshold_type TEXT NOT NULL,
            notify_methods TEXT NOT NULL,
            alert_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            create_time INTEGER NOT NULL,
            last_update INTEGER NOT NULL
        )
        """)
        logger.debug("创建alert_rules表")

        # 警报历史表
        conn.execute("""
        CREATE TABLE IF NOT EXISTS alert_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_id INTEGER NOT NULL,
            instance_id TEXT NOT NULL,
            metric_type TEXT NOT NULL,
            metric_value REAL NOT NULL,
            threshold REAL NOT NULL,
            threshold_type TEXT NOT NULL,
            status TEXT NOT NULL,
            create_time INTEGER NOT NULL,
            FOREIGN KEY (rule_id) REFERENCES alert_rules (id)
        )
        """)
        logger.debug("创建alert_history表")

        # 监听器表
        conn.execute("""
        CREATE TABLE IF NOT EXISTS listeners (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            instance_id TEXT NOT NULL,
            who TEXT NOT NULL,
            last_message_time INTEGER,
            create_time INTEGER NOT NULL,
            conversation_id TEXT,
            manual_added INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            UNIQUE(instance_id, who)
        )
        """)
        logger.debug("创建listeners表")

        # 创建listeners表索引
        conn.execute("CREATE INDEX IF NOT EXISTS idx_listeners_status ON listeners(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_listeners_manual_added ON listeners(manual_added)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_listeners_last_message_time ON listeners(last_message_time)")
        logger.debug("创建listeners表索引")

        # 消息表
        conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            instance_id TEXT NOT NULL,
            message_id TEXT NOT NULL,
            chat_name TEXT NOT NULL,
            message_type TEXT NOT NULL,
            content TEXT,
            sender TEXT,
            sender_remark TEXT,
            mtype TEXT,
            processed INTEGER NOT NULL DEFAULT 0,
            create_time INTEGER NOT NULL,
            delivery_status INTEGER DEFAULT 0,
            delivery_time INTEGER,
            platform_id TEXT,
            reply_content TEXT,
            reply_status INTEGER DEFAULT 0,
            reply_time INTEGER,
            merged INTEGER DEFAULT 0,
            merged_count INTEGER DEFAULT 0,
            merged_ids TEXT,
            local_file_path TEXT,
            file_size INTEGER,
            original_file_path TEXT,
            UNIQUE(instance_id, message_id)
        )
        """)
        logger.debug("创建messages表")

        # 创建消息相关索引
        conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_delivery_status ON messages(delivery_status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_platform_id ON messages(platform_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_reply_status ON messages(reply_status)")
        logger.debug("创建messages表索引")

        # 服务平台表
        conn.execute("""
        CREATE TABLE IF NOT EXISTS service_platforms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform_id TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            config TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            create_time INTEGER NOT NULL,
            update_time INTEGER NOT NULL
        )
        """)
        logger.debug("创建service_platforms表")

        # 投递规则表
        conn.execute("""
        CREATE TABLE IF NOT EXISTS delivery_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_id TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            instance_id TEXT NOT NULL,
            chat_pattern TEXT NOT NULL,
            platform_id TEXT NOT NULL,
            priority INTEGER NOT NULL DEFAULT 0,
            enabled INTEGER NOT NULL DEFAULT 1,
            create_time INTEGER NOT NULL,
            update_time INTEGER NOT NULL,
            FOREIGN KEY (platform_id) REFERENCES service_platforms (platform_id)
        )
        """)
        logger.debug("创建delivery_rules表")

        # 创建投递规则相关索引
        conn.execute("CREATE INDEX IF NOT EXISTS idx_delivery_rules_instance_id ON delivery_rules(instance_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_delivery_rules_platform_id ON delivery_rules(platform_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_delivery_rules_priority ON delivery_rules(priority)")
        logger.debug("创建delivery_rules表索引")

        # 创建触发器，自动删除Self和Time类型的消息
        logger.info("创建消息过滤触发器...")

        # 先删除旧的触发器（如果存在）
        conn.execute("DROP TRIGGER IF EXISTS delete_self_time_messages")

        # 创建新的触发器
        conn.execute("""
        CREATE TRIGGER IF NOT EXISTS delete_self_time_messages
        AFTER INSERT ON messages
        FOR EACH ROW
        WHEN LOWER(NEW.sender) = 'self' OR
             LOWER(NEW.message_type) = 'self' OR
             LOWER(NEW.message_type) = 'time' OR
             LOWER(NEW.mtype) = '10000' OR
             LOWER(NEW.mtype) = '10002'
        BEGIN
            DELETE FROM messages WHERE message_id = NEW.message_id;
        END
        """)
        logger.debug("创建消息过滤触发器完成")

        # 升级现有表结构
        await self._upgrade_table_structure(conn)

    async def _upgrade_table_structure(self, conn):
        """升级现有表结构，添加缺失的字段"""
        try:
            # 检查listeners表是否需要升级
            cursor = conn.execute("PRAGMA table_info(listeners)")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]

            # 检查并添加manual_added字段
            if 'manual_added' not in column_names:
                logger.info("添加manual_added字段到listeners表")
                conn.execute("ALTER TABLE listeners ADD COLUMN manual_added INTEGER DEFAULT 0")
                conn.execute("UPDATE listeners SET manual_added = 0 WHERE manual_added IS NULL")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_listeners_manual_added ON listeners(manual_added)")

            # 检查并添加status字段
            if 'status' not in column_names:
                logger.info("添加status字段到listeners表")
                conn.execute("ALTER TABLE listeners ADD COLUMN status TEXT DEFAULT 'active'")
                conn.execute("UPDATE listeners SET status = 'active' WHERE status IS NULL")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_listeners_status ON listeners(status)")

            # 检查并创建fixed_listeners表
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='fixed_listeners'")
            if not cursor.fetchone():
                logger.info("创建fixed_listeners表")
                conn.execute("""
                CREATE TABLE fixed_listeners (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_name TEXT NOT NULL UNIQUE,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    description TEXT DEFAULT '',
                    create_time INTEGER NOT NULL,
                    update_time INTEGER NOT NULL
                )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_fixed_listeners_enabled ON fixed_listeners(enabled)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_fixed_listeners_session_name ON fixed_listeners(session_name)")

            logger.debug("表结构升级完成")
        except Exception as e:
            logger.error(f"升级表结构时出错: {e}")

    async def execute(self, sql: str, params: tuple = None) -> None:
        """
        执行SQL命令

        Args:
            sql: SQL命令
            params: SQL参数
        """
        if not self._initialized:
            raise RuntimeError("数据库管理器未初始化")

        async with self._lock:
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute(sql, params or ())
                await db.commit()

    async def executemany(self, sql: str, params_list: List[tuple]) -> None:
        """
        执行多条SQL命令

        Args:
            sql: SQL命令
            params_list: SQL参数列表
        """
        if not self._initialized:
            raise RuntimeError("数据库管理器未初始化")

        async with self._lock:
            async with aiosqlite.connect(self._db_path) as db:
                await db.executemany(sql, params_list)
                await db.commit()

    async def fetchone(self, sql: str, params: tuple = None) -> Optional[Dict]:
        """
        获取单条记录

        Args:
            sql: SQL查询
            params: SQL参数

        Returns:
            Optional[Dict]: 查询结果
        """
        if not self._initialized:
            raise RuntimeError("数据库管理器未初始化")

        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(sql, params or ()) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def fetchall(self, sql: str, params: tuple = None) -> List[Dict]:
        """
        获取多条记录

        Args:
            sql: SQL查询
            params: SQL参数

        Returns:
            List[Dict]: 查询结果列表
        """
        if not self._initialized:
            raise RuntimeError("数据库管理器未初始化")

        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(sql, params or ()) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def insert(self, table: str, data: Dict) -> int:
        """
        插入数据

        Args:
            table: 表名
            data: 数据字典

        Returns:
            int: 新插入记录的ID
        """
        if not self._initialized:
            logger.error("数据库管理器未初始化，无法执行插入操作")
            try:
                logger.info("尝试初始化数据库管理器...")
                await self.initialize()
                logger.info("数据库管理器初始化成功")
            except Exception as init_error:
                logger.error(f"初始化数据库管理器失败: {init_error}")
                raise RuntimeError(f"数据库管理器未初始化且无法自动初始化: {init_error}")

        try:
            logger.debug(f"准备向表 {table} 插入数据: {data}")

            # 验证表名
            try:
                valid_tables = await self._get_table_names()
                if table not in valid_tables:
                    error_msg = f"表 {table} 不存在，可用的表: {valid_tables}"
                    logger.error(error_msg)
                    raise ValueError(error_msg)
            except Exception as table_error:
                logger.error(f"获取表名时出错: {table_error}")
                # 继续执行，假设表存在

            # 获取表结构，验证字段
            try:
                table_info = await self._get_table_structure(table)
                table_columns = {col["name"] for col in table_info}

                # 检查数据字段是否在表中存在
                invalid_fields = set(data.keys()) - table_columns
                if invalid_fields:
                    logger.warning(f"字段 {invalid_fields} 在表 {table} 中不存在，将被忽略")
                    # 移除无效字段
                    for field in invalid_fields:
                        data.pop(field, None)
            except Exception as struct_error:
                logger.error(f"获取表结构时出错: {struct_error}")
                # 继续执行，不验证字段

            if not data:
                logger.error("没有有效的数据可以插入")
                return 0

            keys = list(data.keys())
            values = list(data.values())
            placeholders = ','.join(['?' for _ in keys])

            sql = f"INSERT INTO {table} ({','.join(keys)}) VALUES ({placeholders})"
            logger.debug(f"执行SQL: {sql}, 参数: {values}")

            async with self._lock:
                async with aiosqlite.connect(self._db_path) as db:
                    try:
                        cursor = await db.execute(sql, values)
                        await db.commit()
                        last_rowid = cursor.lastrowid
                        logger.debug(f"插入记录成功，ID: {last_rowid}")
                        return last_rowid
                    except Exception as db_error:
                        import traceback
                        error_msg = f"执行SQL时发生错误: {db_error}"
                        logger.error(error_msg)
                        logger.error(f"异常堆栈: {traceback.format_exc()}")

                        # 尝试使用另一种方式插入
                        try:
                            logger.info("尝试使用直接SQL语句插入...")
                            # 构建SQL语句
                            fields = ", ".join(keys)
                            placeholders = ", ".join(["?" for _ in keys])

                            insert_sql = f"INSERT INTO {table} ({fields}) VALUES ({placeholders})"
                            logger.debug(f"执行SQL: {insert_sql}")
                            logger.debug(f"参数值: {values}")

                            await db.execute(insert_sql, values)
                            await db.commit()

                            # 获取最后插入的ID
                            cursor = await db.execute("SELECT last_insert_rowid()")
                            row = await cursor.fetchone()
                            last_id = row[0] if row else 0

                            logger.info(f"使用直接SQL语句插入成功，ID: {last_id}")
                            return last_id
                        except Exception as direct_error:
                            logger.error(f"直接SQL插入也失败: {direct_error}")
                            logger.error(f"异常堆栈: {traceback.format_exc()}")
                            raise ValueError(f"数据库插入失败: {str(db_error)}, 直接SQL插入也失败: {str(direct_error)}")

        except Exception as e:
            import traceback
            logger.error(f"insert 方法异常: {e}")
            logger.error(f"异常堆栈: {traceback.format_exc()}")
            raise

    async def _get_table_names(self) -> List[str]:
        """获取所有表名"""
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table'")
            rows = await cursor.fetchall()
            return [row['name'] for row in rows]

    async def _get_table_structure(self, table: str) -> List[Dict]:
        """获取表结构"""
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(f"PRAGMA table_info({table})")
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def update(self, table: str, data: Dict, conditions: Dict) -> int:
        """
        更新数据

        Args:
            table: 表名
            data: 更新的数据字典
            conditions: 更新条件

        Returns:
            int: 受影响的行数
        """
        if not self._initialized:
            raise RuntimeError("数据库管理器未初始化")

        set_clause = ','.join([f"{k}=?" for k in data.keys()])
        where_clause = ' AND '.join([f"{k}=?" for k in conditions.keys()])

        sql = f"UPDATE {table} SET {set_clause} WHERE {where_clause}"
        params = list(data.values()) + list(conditions.values())

        async with self._lock:
            async with aiosqlite.connect(self._db_path) as db:
                cursor = await db.execute(sql, params)
                await db.commit()
                return cursor.rowcount

    async def delete(self, table: str, conditions: Dict) -> int:
        """
        删除数据

        Args:
            table: 表名
            conditions: 删除条件

        Returns:
            int: 受影响的行数
        """
        if not self._initialized:
            raise RuntimeError("数据库管理器未初始化")

        where_clause = ' AND '.join([f"{k}=?" for k in conditions.keys()])
        sql = f"DELETE FROM {table} WHERE {where_clause}"

        async with self._lock:
            async with aiosqlite.connect(self._db_path) as db:
                cursor = await db.execute(sql, list(conditions.values()))
                await db.commit()
                return cursor.rowcount

    def get_connection(self):
        """
        获取数据库连接（同步方法）

        Returns:
            sqlite3.Connection: 数据库连接
        """
        if not self._initialized:
            raise RuntimeError("数据库管理器未初始化")

        # 创建新的连接
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    async def close(self) -> None:
        """关闭数据库连接"""
        if not self._initialized:
            return

        self._initialized = False
        logger.info("数据库连接已关闭")

# 创建全局实例
db_manager = DBManager()
