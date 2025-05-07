#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试用户会话管理器

这个脚本用于测试用户会话管理器的功能，包括保存、获取和删除用户会话ID。
"""

import os
import sys
import asyncio
import logging
import json
import time
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
from wxauto_mgt.data.db_manager import db_manager
from wxauto_mgt.core.user_conversation_manager import user_conversation_manager

async def test_user_conversation_manager():
    """测试用户会话管理器"""
    try:
        # 初始化数据库
        logger.info("初始化数据库...")
        # 使用项目相对路径
        db_path = os.path.join(project_root, 'data', 'wxauto_mgt.db')
        await db_manager.initialize(db_path)
        
        # 初始化用户会话管理器
        logger.info("初始化用户会话管理器...")
        await user_conversation_manager.initialize()
        
        # 测试数据
        instance_id = "test_instance"
        chat_name = "测试群"
        user_id_1 = "测试群==张三"
        user_id_2 = "测试群==李四"
        platform_id = "dify_test"
        conversation_id_1 = f"conv-{int(time.time())}-1"
        conversation_id_2 = f"conv-{int(time.time())}-2"
        
        # 测试保存会话ID
        logger.info("测试保存会话ID...")
        result = await user_conversation_manager.save_conversation_id(
            instance_id, chat_name, user_id_1, platform_id, conversation_id_1
        )
        logger.info(f"保存会话ID结果: {result}")
        
        result = await user_conversation_manager.save_conversation_id(
            instance_id, chat_name, user_id_2, platform_id, conversation_id_2
        )
        logger.info(f"保存会话ID结果: {result}")
        
        # 测试获取会话ID
        logger.info("测试获取会话ID...")
        conv_id_1 = await user_conversation_manager.get_conversation_id(
            instance_id, chat_name, user_id_1, platform_id
        )
        logger.info(f"获取到的会话ID 1: {conv_id_1}")
        
        conv_id_2 = await user_conversation_manager.get_conversation_id(
            instance_id, chat_name, user_id_2, platform_id
        )
        logger.info(f"获取到的会话ID 2: {conv_id_2}")
        
        # 验证会话ID是否正确
        assert conv_id_1 == conversation_id_1, f"会话ID 1不匹配: {conv_id_1} != {conversation_id_1}"
        assert conv_id_2 == conversation_id_2, f"会话ID 2不匹配: {conv_id_2} != {conversation_id_2}"
        logger.info("会话ID验证通过")
        
        # 测试更新会话ID
        logger.info("测试更新会话ID...")
        new_conversation_id_1 = f"conv-{int(time.time())}-1-new"
        result = await user_conversation_manager.save_conversation_id(
            instance_id, chat_name, user_id_1, platform_id, new_conversation_id_1
        )
        logger.info(f"更新会话ID结果: {result}")
        
        # 验证更新后的会话ID
        conv_id_1_updated = await user_conversation_manager.get_conversation_id(
            instance_id, chat_name, user_id_1, platform_id
        )
        logger.info(f"更新后的会话ID 1: {conv_id_1_updated}")
        assert conv_id_1_updated == new_conversation_id_1, f"更新后的会话ID 1不匹配: {conv_id_1_updated} != {new_conversation_id_1}"
        logger.info("更新会话ID验证通过")
        
        # 测试删除会话ID
        logger.info("测试删除会话ID...")
        result = await user_conversation_manager.delete_conversation_id(
            instance_id, chat_name, user_id_1, platform_id
        )
        logger.info(f"删除会话ID结果: {result}")
        
        # 验证删除后的会话ID
        conv_id_1_deleted = await user_conversation_manager.get_conversation_id(
            instance_id, chat_name, user_id_1, platform_id
        )
        logger.info(f"删除后的会话ID 1: {conv_id_1_deleted}")
        assert conv_id_1_deleted is None, f"删除后的会话ID 1应为None，但实际为: {conv_id_1_deleted}"
        logger.info("删除会话ID验证通过")
        
        # 测试清理过期会话
        logger.info("测试清理过期会话...")
        # 先插入一个过期的会话
        expired_time = int(time.time()) - 31 * 24 * 60 * 60  # 31天前
        await db_manager.execute(
            """
            INSERT INTO user_conversations
            (instance_id, chat_name, user_id, platform_id, conversation_id, last_active, create_time)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("test_instance", "过期群", "过期群==过期用户", "dify_test", "conv-expired", expired_time, expired_time)
        )
        
        # 清理过期会话
        cleaned = await user_conversation_manager.clear_expired_conversations(30)  # 30天过期
        logger.info(f"清理过期会话结果: 清理了 {cleaned} 个过期会话")
        
        # 验证过期会话是否被清理
        expired_conv = await db_manager.fetchone(
            """
            SELECT * FROM user_conversations
            WHERE instance_id = ? AND chat_name = ? AND user_id = ? AND platform_id = ?
            """,
            ("test_instance", "过期群", "过期群==过期用户", "dify_test")
        )
        assert expired_conv is None, "过期会话应该被清理，但仍然存在"
        logger.info("清理过期会话验证通过")
        
        # 清理测试数据
        logger.info("清理测试数据...")
        await db_manager.execute(
            """
            DELETE FROM user_conversations
            WHERE instance_id = ? AND platform_id = ?
            """,
            (instance_id, platform_id)
        )
        
        logger.info("测试完成")
        return True
    except Exception as e:
        logger.error(f"测试过程中出错: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
    finally:
        # 关闭数据库连接
        await db_manager.close()

async def main():
    """主函数"""
    success = await test_user_conversation_manager()
    if success:
        print("测试成功")
    else:
        print("测试失败")

if __name__ == "__main__":
    asyncio.run(main())
