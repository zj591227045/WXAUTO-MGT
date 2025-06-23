#!/usr/bin/env python3
"""
清理数据库中的模拟数据脚本

该脚本用于清理数据库中的模拟数据，包括：
- 包含 "示例群组" 的消息
- 包含 "用户A", "用户B" 等的消息
- 包含 "msg_0", "msg_1" 等的消息
- 包含 "这是一条示例消息" 的消息
"""

import os
import sys
import sqlite3
import json
import logging

# 添加项目根目录到Python路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 数据库路径
DB_PATH = os.path.join(project_root, 'data', 'wxauto_mgt.db')

def find_mock_messages(conn):
    """查找模拟消息"""
    try:
        cursor = conn.cursor()
        
        # 查询所有消息
        cursor.execute("SELECT * FROM messages ORDER BY create_time DESC")
        all_messages = cursor.fetchall()
        logger.info(f"数据库中共有 {len(all_messages)} 条消息")
        print(f"数据库中共有 {len(all_messages)} 条消息")
        
        # 查找模拟消息
        mock_messages = []
        mock_patterns = [
            "示例群组",
            "示例消息",
            "用户A", "用户B", "用户C", "用户D", "用户E", 
            "用户F", "用户G", "用户H", "用户I", "用户J",
            "msg_0", "msg_1", "msg_2", "msg_3", "msg_4",
            "msg_5", "msg_6", "msg_7", "msg_8", "msg_9",
            "inst_001"
        ]
        
        for msg in all_messages:
            # 将数据库记录转换为字典
            msg_dict = dict(msg)
            
            # 检查各个字段是否包含模拟数据
            is_mock = False
            for pattern in mock_patterns:
                if (pattern in str(msg_dict.get('message_id', '')) or
                    pattern in str(msg_dict.get('chat_name', '')) or
                    pattern in str(msg_dict.get('sender', '')) or
                    pattern in str(msg_dict.get('content', '')) or
                    pattern in str(msg_dict.get('instance_id', ''))):
                    is_mock = True
                    break
            
            if is_mock:
                mock_messages.append(msg_dict)
                logger.info(f"发现模拟消息: ID={msg_dict.get('message_id')}, "
                           f"聊天={msg_dict.get('chat_name')}, "
                           f"发送者={msg_dict.get('sender')}, "
                           f"内容={str(msg_dict.get('content', ''))[:50]}...")
        
        logger.info(f"共发现 {len(mock_messages)} 条模拟消息")
        print(f"共发现 {len(mock_messages)} 条模拟消息")
        
        return mock_messages
    except Exception as e:
        logger.error(f"查找模拟消息时出错: {str(e)}")
        return []

def delete_mock_messages(conn, mock_messages):
    """删除模拟消息"""
    try:
        cursor = conn.cursor()
        
        deleted_count = 0
        for msg in mock_messages:
            message_id = msg.get('message_id')
            if message_id:
                cursor.execute("DELETE FROM messages WHERE message_id = ?", (message_id,))
                deleted_count += 1
                logger.debug(f"删除模拟消息: {message_id}")
        
        # 提交事务
        conn.commit()
        
        logger.info(f"成功删除 {deleted_count} 条模拟消息")
        print(f"成功删除 {deleted_count} 条模拟消息")
        
        return deleted_count
    except Exception as e:
        logger.error(f"删除模拟消息时出错: {str(e)}")
        return 0

def find_mock_instances(conn):
    """查找模拟实例"""
    try:
        cursor = conn.cursor()
        
        # 查询所有实例
        cursor.execute("SELECT * FROM instances")
        all_instances = cursor.fetchall()
        logger.info(f"数据库中共有 {len(all_instances)} 个实例")
        print(f"数据库中共有 {len(all_instances)} 个实例")
        
        # 查找模拟实例
        mock_instances = []
        mock_patterns = [
            "inst_001", "主实例", "测试实例", "示例实例"
        ]
        
        for instance in all_instances:
            # 将数据库记录转换为字典
            instance_dict = dict(instance)
            
            # 检查各个字段是否包含模拟数据
            is_mock = False
            for pattern in mock_patterns:
                if (pattern in str(instance_dict.get('instance_id', '')) or
                    pattern in str(instance_dict.get('name', ''))):
                    is_mock = True
                    break
            
            if is_mock:
                mock_instances.append(instance_dict)
                logger.info(f"发现模拟实例: ID={instance_dict.get('instance_id')}, "
                           f"名称={instance_dict.get('name')}")
        
        logger.info(f"共发现 {len(mock_instances)} 个模拟实例")
        print(f"共发现 {len(mock_instances)} 个模拟实例")
        
        return mock_instances
    except Exception as e:
        logger.error(f"查找模拟实例时出错: {str(e)}")
        return []

def delete_mock_instances(conn, mock_instances):
    """删除模拟实例"""
    try:
        cursor = conn.cursor()
        
        deleted_count = 0
        for instance in mock_instances:
            instance_id = instance.get('instance_id')
            if instance_id:
                cursor.execute("DELETE FROM instances WHERE instance_id = ?", (instance_id,))
                deleted_count += 1
                logger.debug(f"删除模拟实例: {instance_id}")
        
        # 提交事务
        conn.commit()
        
        logger.info(f"成功删除 {deleted_count} 个模拟实例")
        print(f"成功删除 {deleted_count} 个模拟实例")
        
        return deleted_count
    except Exception as e:
        logger.error(f"删除模拟实例时出错: {str(e)}")
        return 0

def main():
    """主函数"""
    logger.info("开始清理数据库中的模拟数据")
    print("开始清理数据库中的模拟数据")
    
    if not os.path.exists(DB_PATH):
        logger.error(f"数据库文件不存在: {DB_PATH}")
        print(f"数据库文件不存在: {DB_PATH}")
        return
    
    try:
        # 连接数据库
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row  # 使结果可以像字典一样访问
        
        # 查找并删除模拟消息
        logger.info("=== 处理模拟消息 ===")
        print("=== 处理模拟消息 ===")
        mock_messages = find_mock_messages(conn)
        if mock_messages:
            delete_mock_messages(conn, mock_messages)
        else:
            logger.info("没有发现模拟消息")
            print("没有发现模拟消息")
        
        # 查找并删除模拟实例
        logger.info("=== 处理模拟实例 ===")
        print("=== 处理模拟实例 ===")
        mock_instances = find_mock_instances(conn)
        if mock_instances:
            delete_mock_instances(conn, mock_instances)
        else:
            logger.info("没有发现模拟实例")
            print("没有发现模拟实例")
        
        # 关闭数据库连接
        conn.close()
        
        logger.info("模拟数据清理完成")
        print("模拟数据清理完成")
        
    except Exception as e:
        logger.error(f"清理过程中出错: {str(e)}")
        print(f"清理过程中出错: {str(e)}")

if __name__ == "__main__":
    main()
