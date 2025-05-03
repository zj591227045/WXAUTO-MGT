#!/usr/bin/env python
"""
测试主界面监听未读消息功能

该脚本用于测试主界面监听未读消息的功能，包括消息处理和添加监听对象。
"""

import asyncio
import os
import sys
import logging
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.append(str(project_root))

# 导入必要的模块
from wxauto_mgt.data.db_manager import DBManager
from wxauto_mgt.core.message_listener import MessageListener
from wxauto_mgt.core.message_delivery_service import MessageDeliveryService
from wxauto_mgt.core.api_client import instance_manager, WxAutoApiClient
from wxauto_mgt.utils.file_logger import file_logger

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 模拟未读消息
MOCK_UNREAD_MESSAGES = {
    "张杰": [
        {
            "id": "test_message_1",
            "type": "text",
            "mtype": "text",
            "sender": "张杰",
            "sender_remark": "张杰",
            "content": "这是一条测试消息",
            "chat_name": "张杰"
        },
        {
            "id": "test_message_2",
            "type": "image",
            "mtype": "image",
            "sender": "张杰",
            "sender_remark": "张杰",
            "content": "C:\\Code\\wxauto-ui\\wxauto文件\\微信图片_20250503084836312905.png",
            "chat_name": "张杰"
        }
    ]
}

class MockAPIClient(WxAutoApiClient):
    """模拟API客户端"""

    def __init__(self, instance_id, base_url, api_key, timeout=30):
        super().__init__(instance_id, base_url, api_key)
        self.listeners = {}

    async def get_unread_messages(self, **kwargs):
        """模拟获取未读消息"""
        messages = []
        for chat_name, chat_messages in MOCK_UNREAD_MESSAGES.items():
            for msg in chat_messages:
                messages.append(msg)
        return messages

    async def add_listener(self, who, **kwargs):
        """模拟添加监听对象"""
        self.listeners[who] = kwargs
        logger.info(f"添加监听对象: {who}, 参数: {kwargs}")
        return True

    async def get_listener_messages(self, who):
        """模拟获取监听对象消息"""
        if who in MOCK_UNREAD_MESSAGES:
            return MOCK_UNREAD_MESSAGES[who]
        return []

    async def send_message(self, who, message):
        """模拟发送消息"""
        logger.info(f"发送消息到 {who}: {message}")
        return {"success": True}

async def main():
    """主函数"""
    logger.info("开始测试主界面监听未读消息功能")

    # 初始化数据库连接
    # 使用项目根目录下的data目录
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
    db_path = os.path.join(project_root, 'data', 'wxauto_mgt.db')
    db_manager = DBManager()
    await db_manager.initialize(db_path)

    # 创建模拟API客户端
    mock_client = MockAPIClient("test_instance", "http://localhost:5000", "test_api_key")

    # 添加到实例管理器
    instance_manager._instances["test_instance"] = mock_client

    # 创建并启动消息监听服务
    message_listener = MessageListener()
    await message_listener.start()

    # 创建并启动消息投递服务
    message_delivery_service = MessageDeliveryService()
    await message_delivery_service.initialize()
    await message_delivery_service.start()

    # 等待一段时间，让服务启动
    logger.info("服务已启动，等待5秒...")
    await asyncio.sleep(5)

    # 手动调用主界面监听未读消息方法
    logger.info("手动调用主界面监听未读消息方法")
    await message_listener.check_main_window_messages("test_instance", mock_client)

    # 等待一段时间，让消息处理完成
    logger.info("等待10秒，让消息处理完成...")
    await asyncio.sleep(10)

    # 检查监听对象是否添加成功
    listeners = message_listener.get_active_listeners("test_instance")
    logger.info(f"当前监听对象: {listeners}")

    # 检查消息是否处理成功
    messages = await db_manager.fetchall("SELECT * FROM messages")
    logger.info(f"数据库中的消息数量: {len(messages)}")
    for msg in messages:
        logger.info(f"消息ID: {msg.get('message_id')}, 状态: {msg.get('processed')}, 投递状态: {msg.get('delivery_status')}")

    # 停止服务
    await message_delivery_service.stop()
    await message_listener.stop()

    # 关闭数据库连接
    await db_manager.close()

    logger.info("测试完成")

if __name__ == "__main__":
    asyncio.run(main())
