#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
清理数据库中的Self和Time类型消息

这个脚本会连接到数据库，查找并删除所有Self和Time类型的消息。
"""

import os
import sys
import logging
import sqlite3
import json
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

def log_dict(logger, data, prefix=""):
    """格式化输出字典数据"""
    if not data:
        logger.info(f"{prefix} 空数据")
        return
    
    try:
        formatted_json = json.dumps(data, ensure_ascii=False, indent=2)
        logger.info(f"{prefix}\n{formatted_json}")
    except Exception as e:
        logger.info(f"{prefix} {str(data)}")

def find_self_messages(conn):
    """查找Self和Time消息"""
    try:
        cursor = conn.cursor()
        
        # 查询所有消息
        cursor.execute("SELECT * FROM messages ORDER BY create_time DESC")
        all_messages = cursor.fetchall()
        logger.info(f"数据库中共有 {len(all_messages)} 条消息")
        print(f"数据库中共有 {len(all_messages)} 条消息")
        
        # 查找Self和Time消息
        self_time_messages = []
        for msg in all_messages:
            # 将数据库记录转换为字典
            msg_dict = dict(msg)
            
            # 获取发送者和类型
            original_sender = msg_dict.get('sender', '')
            original_type = msg_dict.get('message_type', '')
            sender = original_sender.lower() if original_sender else ''
            msg_type = original_type.lower() if original_type else ''
            
            # 检查是否是Self或Time消息
            is_self_sender = sender == 'self' or original_sender == 'Self'
            is_filtered_type = msg_type in ['self', 'time'] or original_type in ['self', 'Self', 'time', 'Time']
            
            if is_self_sender or is_filtered_type:
                self_time_messages.append(msg_dict)
                logger.info(f"发现Self/Time消息: ID={msg_dict.get('message_id')}, 发送者={original_sender}, 类型={original_type}")
        
        logger.info(f"共找到 {len(self_time_messages)} 条Self/Time消息")
        print(f"共找到 {len(self_time_messages)} 条Self/Time消息")
        return self_time_messages
    except Exception as e:
        logger.error(f"查找Self/Time消息时出错: {str(e)}")
        return []

def delete_self_messages(conn, messages):
    """删除Self和Time消息"""
    if not messages:
        logger.info("没有需要删除的Self/Time消息")
        return 0
    
    try:
        cursor = conn.cursor()
        deleted_count = 0
        
        for msg in messages:
            message_id = msg.get('message_id')
            if not message_id:
                continue
            
            # 删除消息
            cursor.execute("DELETE FROM messages WHERE message_id = ?", (message_id,))
            deleted_count += cursor.rowcount
        
        # 提交事务
        conn.commit()
        
        logger.info(f"成功删除 {deleted_count} 条Self/Time消息")
        print(f"成功删除 {deleted_count} 条Self/Time消息")
        return deleted_count
    except Exception as e:
        logger.error(f"删除Self/Time消息时出错: {str(e)}")
        conn.rollback()
        return 0

def clean_database():
    """清理数据库中的Self和Time消息"""
    logger.info("开始清理数据库中的Self和Time消息")
    print("开始清理数据库中的Self和Time消息")
    
    # 检查数据库文件是否存在
    if not os.path.exists(DB_PATH):
        logger.error(f"数据库文件不存在: {DB_PATH}")
        print(f"数据库文件不存在: {DB_PATH}")
        return
    
    try:
        # 连接数据库
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        
        # 查找Self和Time消息
        self_time_messages = find_self_messages(conn)
        
        # 删除Self和Time消息
        deleted_count = delete_self_messages(conn, self_time_messages)
        
        # 关闭数据库连接
        conn.close()
        
        logger.info("数据库清理完成")
        print("数据库清理完成")
        return deleted_count
    except Exception as e:
        logger.error(f"清理数据库时出错: {str(e)}")
        print(f"清理数据库时出错: {str(e)}")
        return 0

def main():
    """主函数"""
    try:
        # 清理数据库
        deleted_count = clean_database()
        
        logger.info(f"脚本执行完成，共删除 {deleted_count} 条Self/Time消息")
        print(f"脚本执行完成，共删除 {deleted_count} 条Self/Time消息")
    except Exception as e:
        logger.error(f"脚本执行出错: {str(e)}")
        print(f"脚本执行出错: {str(e)}")

if __name__ == "__main__":
    main()
