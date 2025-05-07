#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
创建用户会话表

这个脚本用于创建新的用户会话表，用于存储用户ID与会话ID的映射关系。
"""

import os
import sys
import asyncio
import logging
import sqlite3
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.append(str(project_root))

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 数据库路径
DB_PATH = os.path.join(project_root, 'data', 'wxauto_mgt.db')

async def create_user_conversations_table():
    """创建用户会话表"""
    try:
        # 导入数据库管理器
        from wxauto_mgt.data.db_manager import db_manager
        
        # 初始化数据库
        await db_manager.initialize(DB_PATH)
        
        # 检查表是否存在
        result = await db_manager.fetchone(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='user_conversations'"
        )
        
        if not result:
            # 创建表
            await db_manager.execute("""
            CREATE TABLE IF NOT EXISTS user_conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                instance_id TEXT NOT NULL,
                chat_name TEXT NOT NULL,
                user_id TEXT NOT NULL,
                conversation_id TEXT NOT NULL,
                platform_id TEXT NOT NULL,
                last_active INTEGER NOT NULL,
                create_time INTEGER NOT NULL,
                UNIQUE(instance_id, chat_name, user_id, platform_id)
            )
            """)
            
            # 创建索引
            await db_manager.execute(
                "CREATE INDEX IF NOT EXISTS idx_user_conversations_instance_id ON user_conversations(instance_id)"
            )
            await db_manager.execute(
                "CREATE INDEX IF NOT EXISTS idx_user_conversations_user_id ON user_conversations(user_id)"
            )
            await db_manager.execute(
                "CREATE INDEX IF NOT EXISTS idx_user_conversations_conversation_id ON user_conversations(conversation_id)"
            )
            
            logger.info("创建user_conversations表成功")
            print("创建user_conversations表成功")
        else:
            logger.info("user_conversations表已存在")
            print("user_conversations表已存在")
            
            # 检查表结构
            columns = await db_manager.fetchall("PRAGMA table_info(user_conversations)")
            column_names = [col['name'] for col in columns]
            
            # 检查是否有所有必要的列
            required_columns = [
                'id', 'instance_id', 'chat_name', 'user_id', 'conversation_id', 
                'platform_id', 'last_active', 'create_time'
            ]
            
            missing_columns = [col for col in required_columns if col not in column_names]
            if missing_columns:
                logger.warning(f"user_conversations表缺少以下列: {missing_columns}")
                print(f"user_conversations表缺少以下列: {missing_columns}")
                
                # 添加缺失的列
                for col in missing_columns:
                    if col == 'id':
                        continue  # 主键不能添加
                    elif col == 'instance_id':
                        await db_manager.execute("ALTER TABLE user_conversations ADD COLUMN instance_id TEXT NOT NULL DEFAULT ''")
                    elif col == 'chat_name':
                        await db_manager.execute("ALTER TABLE user_conversations ADD COLUMN chat_name TEXT NOT NULL DEFAULT ''")
                    elif col == 'user_id':
                        await db_manager.execute("ALTER TABLE user_conversations ADD COLUMN user_id TEXT NOT NULL DEFAULT ''")
                    elif col == 'conversation_id':
                        await db_manager.execute("ALTER TABLE user_conversations ADD COLUMN conversation_id TEXT NOT NULL DEFAULT ''")
                    elif col == 'platform_id':
                        await db_manager.execute("ALTER TABLE user_conversations ADD COLUMN platform_id TEXT NOT NULL DEFAULT ''")
                    elif col == 'last_active':
                        await db_manager.execute("ALTER TABLE user_conversations ADD COLUMN last_active INTEGER NOT NULL DEFAULT 0")
                    elif col == 'create_time':
                        await db_manager.execute("ALTER TABLE user_conversations ADD COLUMN create_time INTEGER NOT NULL DEFAULT 0")
                
                logger.info("已添加缺失的列")
                print("已添加缺失的列")
        
        return True
    except Exception as e:
        logger.error(f"创建user_conversations表时出错: {e}")
        print(f"创建user_conversations表时出错: {e}")
        return False

async def main():
    """主函数"""
    await create_user_conversations_table()

if __name__ == "__main__":
    asyncio.run(main())
