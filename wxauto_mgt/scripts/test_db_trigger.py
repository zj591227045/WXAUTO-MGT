#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试数据库触发器自动创建功能
"""

import os
import sys
import asyncio
import logging
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

# 导入数据库管理器
from wxauto_mgt.data.db_manager import db_manager

async def test_trigger():
    """测试触发器自动创建功能"""
    try:
        # 初始化数据库
        logger.info("初始化数据库...")
        # 使用项目相对路径
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        db_path = os.path.join(project_root, 'data', 'wxauto_mgt.db')
        await db_manager.initialize(db_path)

        # 检查触发器是否存在
        logger.info("检查触发器是否存在...")
        trigger = await db_manager.fetchone(
            "SELECT name, sql FROM sqlite_master WHERE type='trigger' AND name='delete_self_time_messages'"
        )

        if trigger:
            logger.info(f"触发器存在: {trigger['name']}")
            logger.info(f"触发器SQL: {trigger['sql']}")
        else:
            logger.error("触发器不存在!")

        # 测试触发器功能
        logger.info("测试触发器功能...")

        # 插入一条self类型的消息
        await db_manager.execute("""
        INSERT INTO messages
        (instance_id, message_id, chat_name, message_type, content, sender, create_time)
        VALUES
        ('test_instance', 'test_msg_id', 'test_chat', 'self', 'test content', 'Self', strftime('%s', 'now'))
        """)

        # 检查消息是否被自动删除
        message = await db_manager.fetchone(
            "SELECT * FROM messages WHERE message_id = 'test_msg_id'"
        )

        if message:
            logger.error("触发器未生效! Self类型的消息未被删除")
        else:
            logger.info("触发器生效! Self类型的消息已被自动删除")

        logger.info("测试完成")
    except Exception as e:
        logger.error(f"测试过程中出错: {str(e)}")
    finally:
        # 关闭数据库连接
        await db_manager.close()

async def main():
    """主函数"""
    await test_trigger()

if __name__ == "__main__":
    asyncio.run(main())
