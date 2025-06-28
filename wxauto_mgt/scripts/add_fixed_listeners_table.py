#!/usr/bin/env python3
"""
添加固定监听配置表的数据库升级脚本

该脚本用于创建固定监听配置相关的数据库表，支持：
- 固定监听会话配置存储
- 会话状态管理
- 创建和更新时间记录
"""

import os
import sys
import asyncio
import logging

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from wxauto_mgt.data.db_manager import db_manager
from wxauto_mgt.utils.logging import setup_logging

# 设置日志
logger = logging.getLogger('wxauto_mgt')


async def add_fixed_listeners_table():
    """添加固定监听配置相关的数据库表"""
    try:
        # 初始化数据库
        db_path = os.path.join(project_root, 'data', 'wxauto_mgt.db')
        await db_manager.initialize(db_path)
        
        logger.info(f"数据库路径: {db_path}")
        
        # 检查固定监听配置表是否存在
        logger.info("\n=== 检查固定监听配置表 ===")
        
        table_exists = await db_manager.fetchone(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='fixed_listeners'"
        )
        
        if not table_exists:
            logger.info("创建固定监听配置表...")
            
            # 创建固定监听配置表
            await db_manager.execute("""
            CREATE TABLE IF NOT EXISTS fixed_listeners (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_name TEXT NOT NULL UNIQUE,
                enabled INTEGER NOT NULL DEFAULT 1,
                description TEXT,
                create_time INTEGER NOT NULL,
                update_time INTEGER NOT NULL
            )
            """)
            
            # 创建索引
            await db_manager.execute(
                "CREATE INDEX IF NOT EXISTS idx_fixed_listeners_session_name ON fixed_listeners(session_name)"
            )
            await db_manager.execute(
                "CREATE INDEX IF NOT EXISTS idx_fixed_listeners_enabled ON fixed_listeners(enabled)"
            )
            
            logger.info("✅ 已创建固定监听配置表")
        else:
            logger.info("✅ 固定监听配置表已存在")
        
        # 检查表结构
        logger.info("\n=== 检查表结构 ===")
        
        # 获取表结构信息
        columns = await db_manager.fetchall("PRAGMA table_info(fixed_listeners)")
        column_names = [col['name'] for col in columns]
        
        logger.info(f"当前表字段: {column_names}")
        
        # 检查是否需要添加description字段
        if 'description' not in column_names:
            logger.info("\n=== 添加description字段 ===")
            
            # 添加description字段
            await db_manager.execute(
                "ALTER TABLE fixed_listeners ADD COLUMN description TEXT"
            )
            logger.info("✅ 已添加description字段")
        else:
            logger.info("✅ description字段已存在")
        
        # 创建索引
        logger.info("\n=== 创建索引 ===")
        
        # 为session_name字段创建唯一索引
        await db_manager.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_fixed_listeners_session_name_unique ON fixed_listeners(session_name)"
        )
        logger.info("✅ 已创建session_name唯一索引")
        
        # 为enabled字段创建索引
        await db_manager.execute(
            "CREATE INDEX IF NOT EXISTS idx_fixed_listeners_enabled ON fixed_listeners(enabled)"
        )
        logger.info("✅ 已创建enabled字段索引")
        
        # 检查现有数据
        logger.info("\n=== 检查现有数据 ===")
        
        fixed_listeners_count = await db_manager.fetchone("SELECT COUNT(*) as count FROM fixed_listeners")
        logger.info(f"\n固定监听配置总数: {fixed_listeners_count['count']}")
        
        if fixed_listeners_count['count'] > 0:
            # 按状态统计
            status_stats = await db_manager.fetchall(
                "SELECT enabled, COUNT(*) as count FROM fixed_listeners GROUP BY enabled"
            )
            logger.info("按状态统计:")
            for stat in status_stats:
                status_name = "启用" if stat['enabled'] == 1 else "禁用"
                logger.info(f"  {status_name}: {stat['count']}")
        
        logger.info("\n✅ 固定监听配置表升级完成")
        return True
        
    except Exception as e:
        logger.error(f"升级固定监听配置表失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
    finally:
        # 关闭数据库连接
        await db_manager.close()


async def main():
    """主函数"""
    # 设置日志
    log_dir = os.path.join(project_root, 'data', 'logs')
    os.makedirs(log_dir, exist_ok=True)
    setup_logging(log_dir)

    logger.info("开始升级固定监听配置表...")

    success = await add_fixed_listeners_table()

    if success:
        logger.info("✅ 固定监听配置表升级成功")
    else:
        logger.error("❌ 固定监听配置表升级失败")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
