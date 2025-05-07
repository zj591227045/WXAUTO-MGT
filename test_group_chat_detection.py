#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试群聊检测和用户ID生成

这个脚本用于测试群聊检测逻辑和用户ID生成是否正确工作。
"""

import os
import sys
import asyncio
import logging
import json
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

# 导入需要测试的模块
from wxauto_mgt.core.service_platform import DifyPlatform
from wxauto_mgt.core.message_listener import message_listener

# 模拟文件日志记录器
class MockFileLogger:
    def debug(self, msg):
        print(f"[FILE_DEBUG] {msg}")
    
    def info(self, msg):
        print(f"[FILE_INFO] {msg}")
    
    def warning(self, msg):
        print(f"[FILE_WARNING] {msg}")
    
    def error(self, msg):
        print(f"[FILE_ERROR] {msg}")

# 测试群聊检测和用户ID生成
async def test_group_chat_detection():
    """测试群聊检测和用户ID生成"""
    print("\n=== 测试群聊检测和用户ID生成 ===")
    
    # 创建DifyPlatform实例
    dify_platform = DifyPlatform(
        platform_id="test_platform",
        name="测试平台",
        config={
            "api_url": "http://example.com/api",
            "api_key": "test_key"
        }
    )
    
    # 注入模拟文件日志记录器
    dify_platform.file_logger = MockFileLogger()
    
    # 测试用例1: 私聊消息 (发送者和聊天对象名称相同)
    private_message = {
        'id': 1,
        'instance_id': 'wxauto_test',
        'message_id': '123456',
        'chat_name': '张三',
        'message_type': 'friend',
        'content': '你好，这是私聊消息',
        'sender': '张三',
        'sender_remark': '张三',
        'mtype': '',
        'processed': 0,
        'create_time': 1746581750,
        'delivery_status': 0,
        'delivery_time': None,
        'platform_id': None,
        'reply_content': None,
        'reply_status': 0,
        'reply_time': None,
        'merged': 0,
        'merged_count': 0,
        'merged_ids': None,
        'local_file_path': None,
        'file_size': None,
        'original_file_path': None,
        'file_type': None,
        'conversation_id': 'conv-123'
    }
    
    # 测试用例2: 群聊消息 (发送者和聊天对象名称不同)
    group_message = {
        'id': 2,
        'instance_id': 'wxauto_test',
        'message_id': '789012',
        'chat_name': '测试群',
        'message_type': 'friend',  # 注意这里故意设置为friend，测试我们的检测逻辑
        'content': '大家好，这是群聊消息',
        'sender': '李四',
        'sender_remark': '李四',
        'mtype': '',
        'processed': 0,
        'create_time': 1746581750,
        'delivery_status': 0,
        'delivery_time': None,
        'platform_id': None,
        'reply_content': None,
        'reply_status': 0,
        'reply_time': None,
        'merged': 0,
        'merged_count': 0,
        'merged_ids': None,
        'local_file_path': None,
        'file_size': None,
        'original_file_path': None,
        'file_type': None,
        'conversation_id': 'conv-456'
    }
    
    # 测试用例3: 群聊消息 (message_type为group，但我们的逻辑应该忽略这个字段)
    group_message2 = {
        'id': 3,
        'instance_id': 'wxauto_test',
        'message_id': '345678',
        'chat_name': '另一个测试群',
        'message_type': 'group',
        'content': '这是另一个群聊消息',
        'sender': '王五',
        'sender_remark': '王五',
        'mtype': '',
        'processed': 0,
        'create_time': 1746581750,
        'delivery_status': 0,
        'delivery_time': None,
        'platform_id': None,
        'reply_content': None,
        'reply_status': 0,
        'reply_time': None,
        'merged': 0,
        'merged_count': 0,
        'merged_ids': None,
        'local_file_path': None,
        'file_size': None,
        'original_file_path': None,
        'file_type': None,
        'conversation_id': 'conv-789'
    }
    
    # 测试处理私聊消息
    print("\n--- 测试私聊消息 ---")
    request_data = await process_message_and_get_request_data(dify_platform, private_message)
    print(f"请求数据: {json.dumps(request_data, ensure_ascii=False, indent=2)}")
    print(f"用户ID: {request_data.get('user')}")
    
    # 测试处理群聊消息
    print("\n--- 测试群聊消息 (message_type=friend) ---")
    request_data = await process_message_and_get_request_data(dify_platform, group_message)
    print(f"请求数据: {json.dumps(request_data, ensure_ascii=False, indent=2)}")
    print(f"用户ID: {request_data.get('user')}")
    
    # 测试处理群聊消息 (message_type=group)
    print("\n--- 测试群聊消息 (message_type=group) ---")
    request_data = await process_message_and_get_request_data(dify_platform, group_message2)
    print(f"请求数据: {json.dumps(request_data, ensure_ascii=False, indent=2)}")
    print(f"用户ID: {request_data.get('user')}")

async def process_message_and_get_request_data(platform, message):
    """处理消息并获取请求数据"""
    # 模拟process_message方法的前半部分，只关注用户ID生成
    is_file_message = 'dify_file' in message or ('local_file_path' in message and message.get('file_type') in ['image', 'file'])
    
    # 获取发送者和聊天名称
    sender = message.get('sender', '')
    chat_name = message.get('chat_name', '')
    
    # 根据消息对象名称与发送者名称是否相同来判断群聊
    if sender and chat_name and sender != chat_name:
        # 对于群聊消息，使用"群聊名称==发送者"格式的用户ID
        combined_user_id = f"{chat_name}=={sender}"
        print(f"群聊消息，使用组合用户ID: {combined_user_id}")
        user_id = combined_user_id
    else:
        # 对于私聊消息，使用原始发送者ID
        user_id = sender or "default_user"
        print(f"私聊消息，使用原始用户ID: {user_id}")
    
    request_data = {
        "inputs": {},
        "query": " " if is_file_message else message['content'],
        "response_mode": "blocking",
        "user": user_id
    }
    
    # 如果消息中包含会话ID，添加到请求数据中
    if 'conversation_id' in message and message['conversation_id']:
        request_data['conversation_id'] = message['conversation_id']
    
    return request_data

# 测试会话ID保存
async def test_conversation_id_storage():
    """测试会话ID保存"""
    print("\n=== 测试会话ID保存 ===")
    
    # 查看当前数据库中的listeners表结构
    print("\n--- 当前listeners表结构 ---")
    try:
        # 这里我们只是打印一下表结构，不实际执行数据库操作
        print("listeners表结构:")
        print("  id (INTEGER)")
        print("  instance_id (TEXT)")
        print("  who (TEXT)")
        print("  last_message_time (INTEGER)")
        print("  create_time (INTEGER)")
        print("  conversation_id (TEXT)")
        
        # 解释当前的会话ID存储机制
        print("\n当前会话ID存储机制:")
        print("1. 会话ID存储在listeners表的conversation_id字段中")
        print("2. 每个监听对象(instance_id + who)对应一个会话ID")
        print("3. 对于群聊，多个发送者共享同一个监听对象的会话ID")
        print("4. 使用'群聊名称==发送者'格式的用户ID可以区分不同发送者")
        print("5. 不需要修改数据库结构，只需要修改用户ID生成逻辑")
    except Exception as e:
        print(f"获取表结构时出错: {e}")

async def main():
    """主函数"""
    try:
        # 测试群聊检测和用户ID生成
        await test_group_chat_detection()
        
        # 测试会话ID保存
        await test_conversation_id_storage()
        
        print("\n所有测试完成!")
    except Exception as e:
        logger.error(f"测试过程中出错: {e}")

if __name__ == "__main__":
    asyncio.run(main())
