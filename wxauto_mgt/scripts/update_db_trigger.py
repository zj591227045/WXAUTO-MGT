#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
更新数据库触发器

这个脚本会连接到数据库，更新或创建触发器，确保自动删除Self和Time类型的消息。
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

def update_trigger():
    """更新数据库触发器"""
    logger.info("开始更新数据库触发器")
    print("开始更新数据库触发器")
    
    # 检查数据库文件是否存在
    if not os.path.exists(DB_PATH):
        logger.error(f"数据库文件不存在: {DB_PATH}")
        print(f"数据库文件不存在: {DB_PATH}")
        return False
    
    try:
        # 连接数据库
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 先删除旧的触发器（如果存在）
        drop_trigger_sql = """
        DROP TRIGGER IF EXISTS delete_self_time_messages;
        """
        cursor.execute(drop_trigger_sql)
        logger.info("已删除旧的触发器（如果存在）")
        
        # 创建新的触发器
        trigger_sql = """
        CREATE TRIGGER IF NOT EXISTS delete_self_time_messages
        AFTER INSERT ON messages
        FOR EACH ROW
        WHEN LOWER(NEW.sender) = 'self' OR 
             LOWER(NEW.message_type) = 'self' OR 
             LOWER(NEW.message_type) = 'time'
        BEGIN
            DELETE FROM messages WHERE message_id = NEW.message_id;
        END;
        """
        cursor.execute(trigger_sql)
        
        # 提交事务
        conn.commit()
        
        # 关闭数据库连接
        conn.close()
        
        logger.info("数据库触发器更新成功")
        print("数据库触发器更新成功")
        return True
    except Exception as e:
        logger.error(f"更新数据库触发器时出错: {str(e)}")
        print(f"更新数据库触发器时出错: {str(e)}")
        return False

def main():
    """主函数"""
    try:
        # 更新触发器
        success = update_trigger()
        
        if success:
            logger.info("脚本执行成功")
            print("脚本执行成功")
        else:
            logger.error("脚本执行失败")
            print("脚本执行失败")
    except Exception as e:
        logger.error(f"脚本执行出错: {str(e)}")
        print(f"脚本执行出错: {str(e)}")

if __name__ == "__main__":
    main()
