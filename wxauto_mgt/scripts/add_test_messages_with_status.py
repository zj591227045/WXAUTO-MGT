#!/usr/bin/env python3
"""
添加带有状态的测试消息
用于验证首页消息状态图例显示功能
"""

import os
import sys
import asyncio
import time
import json

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from wxauto_mgt.utils.database import db_manager
from wxauto_mgt.utils.logging import setup_logging

# 设置日志
logger = setup_logging()

async def add_test_messages():
    """添加带有不同状态的测试消息"""
    try:
        # 初始化数据库
        db_path = os.path.join(project_root, 'data', 'wxauto_mgt.db')
        await db_manager.initialize(db_path)
        
        print(f"数据库路径: {db_path}")
        
        # 检查messages表结构
        print("\n=== 检查messages表结构 ===")
        columns_result = await db_manager.fetchall("PRAGMA table_info(messages)")
        
        if not columns_result:
            print("❌ messages表不存在")
            return False
        
        print("当前表结构:")
        column_names = []
        for col in columns_result:
            column_names.append(col['name'])
            print(f"  {col['name']} - {col['type']}")
        
        # 检查是否有状态字段
        status_fields = ['processed', 'delivery_status', 'reply_status']
        missing_fields = [field for field in status_fields if field not in column_names]
        
        if missing_fields:
            print(f"\n❌ 缺少状态字段: {missing_fields}")
            print("请先运行消息投递服务来添加这些字段")
            return False
        
        print("✅ 所有状态字段都存在")
        
        # 获取当前时间戳
        current_time = int(time.time())
        
        # 准备测试消息数据
        test_messages = [
            {
                'instance_id': 'test_instance',
                'message_id': f'test_msg_1_{current_time}',
                'chat_name': '测试用户1',
                'message_type': 'text',
                'content': '这是一条已处理但未投递的消息',
                'sender': '测试用户1',
                'sender_remark': '测试用户1',
                'mtype': 1,
                'processed': 1,
                'delivery_status': 0,
                'reply_status': 0,
                'create_time': current_time - 300
            },
            {
                'instance_id': 'test_instance',
                'message_id': f'test_msg_2_{current_time}',
                'chat_name': '测试用户2',
                'message_type': 'text',
                'content': '这是一条已处理且投递成功的消息',
                'sender': '测试用户2',
                'sender_remark': '测试用户2',
                'mtype': 1,
                'processed': 1,
                'delivery_status': 1,
                'reply_status': 0,
                'create_time': current_time - 240
            },
            {
                'instance_id': 'test_instance',
                'message_id': f'test_msg_3_{current_time}',
                'chat_name': '测试用户3',
                'message_type': 'text',
                'content': '这是一条已处理、投递成功且已回复的消息',
                'sender': '测试用户3',
                'sender_remark': '测试用户3',
                'mtype': 1,
                'processed': 1,
                'delivery_status': 1,
                'reply_status': 1,
                'reply_content': '这是AI的回复内容',
                'reply_time': current_time - 180,
                'create_time': current_time - 180
            },
            {
                'instance_id': 'test_instance',
                'message_id': f'test_msg_4_{current_time}',
                'chat_name': '测试用户4',
                'message_type': 'text',
                'content': '这是一条已处理但投递失败的消息',
                'sender': '测试用户4',
                'sender_remark': '测试用户4',
                'mtype': 1,
                'processed': 1,
                'delivery_status': 2,
                'reply_status': 0,
                'create_time': current_time - 120
            },
            {
                'instance_id': 'test_instance',
                'message_id': f'test_msg_5_{current_time}',
                'chat_name': '测试用户5',
                'message_type': 'text',
                'content': '这是一条未处理的新消息',
                'sender': '测试用户5',
                'sender_remark': '测试用户5',
                'mtype': 1,
                'processed': 0,
                'delivery_status': 0,
                'reply_status': 0,
                'create_time': current_time - 60
            }
        ]
        
        # 添加测试消息
        print(f"\n=== 添加 {len(test_messages)} 条测试消息 ===")
        
        for i, message in enumerate(test_messages, 1):
            try:
                await db_manager.insert('messages', message)
                print(f"✅ 已添加测试消息 {i}: {message['chat_name']} - {message['content'][:30]}...")
            except Exception as e:
                print(f"❌ 添加测试消息 {i} 失败: {e}")
        
        print("\n=== 验证添加的消息 ===")
        
        # 查询刚添加的消息
        recent_messages = await db_manager.fetchall(
            "SELECT * FROM messages WHERE instance_id = ? ORDER BY create_time DESC LIMIT 10",
            ('test_instance',)
        )
        
        print(f"查询到 {len(recent_messages)} 条消息:")
        for msg in recent_messages:
            status_info = f"处理:{msg.get('processed', 0)} 投递:{msg.get('delivery_status', 0)} 回复:{msg.get('reply_status', 0)}"
            print(f"  {msg['chat_name']}: {msg['content'][:30]}... [{status_info}]")
        
        print("\n✅ 测试消息添加完成！")
        print("现在可以刷新首页查看状态图例显示效果")
        
        return True
        
    except Exception as e:
        logger.error(f"添加测试消息失败: {e}")
        print(f"❌ 添加测试消息失败: {e}")
        return False
    finally:
        await db_manager.close()

if __name__ == "__main__":
    asyncio.run(add_test_messages())
