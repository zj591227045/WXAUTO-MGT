#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
更新数据库结构

这个脚本会连接到数据库，检查并更新表结构，确保所有必要的列都存在。
"""

import os
import sys
import logging
import sqlite3
import asyncio
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 数据库路径
DB_PATH = os.path.join(project_root, 'data', 'wxauto_mgt.db')

def update_delivery_rules_table():
    """更新delivery_rules表结构"""
    try:
        # 连接数据库
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 检查表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='delivery_rules'")
        if not cursor.fetchone():
            logger.info("delivery_rules表不存在，无需更新")
            conn.close()
            return True
        
        # 获取表结构
        cursor.execute("PRAGMA table_info(delivery_rules)")
        columns = cursor.fetchall()
        column_names = [col['name'] for col in columns]
        
        # 检查并添加缺失的列
        changes_made = False
        
        if 'only_at_messages' not in column_names:
            logger.info("添加only_at_messages列到delivery_rules表")
            cursor.execute("ALTER TABLE delivery_rules ADD COLUMN only_at_messages INTEGER DEFAULT 0")
            changes_made = True
        
        if 'at_name' not in column_names:
            logger.info("添加at_name列到delivery_rules表")
            cursor.execute("ALTER TABLE delivery_rules ADD COLUMN at_name TEXT DEFAULT ''")
            changes_made = True
        
        # 提交事务
        conn.commit()
        
        # 关闭数据库连接
        conn.close()
        
        if changes_made:
            logger.info("delivery_rules表结构更新成功")
        else:
            logger.info("delivery_rules表结构已是最新，无需更新")
        
        return True
    except Exception as e:
        logger.error(f"更新delivery_rules表结构时出错: {str(e)}")
        return False

def update_database_schema():
    """更新数据库结构"""
    logger.info("开始更新数据库结构")
    
    # 检查数据库文件是否存在
    if not os.path.exists(DB_PATH):
        logger.error(f"数据库文件不存在: {DB_PATH}")
        return False
    
    # 更新delivery_rules表
    if not update_delivery_rules_table():
        return False
    
    logger.info("数据库结构更新完成")
    return True

if __name__ == "__main__":
    success = update_database_schema()
    sys.exit(0 if success else 1)
