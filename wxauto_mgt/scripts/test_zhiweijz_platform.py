#!/usr/bin/env python3
"""
测试只为记账平台功能的脚本

该脚本用于测试只为记账平台的各项功能，包括：
- 平台创建和初始化
- 登录和token管理
- 智能记账功能
- 账本管理
- 错误处理
"""

import asyncio
import os
import sys
import logging
import time

# 添加项目根目录到Python路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from wxauto_mgt.data.db_manager import db_manager
from wxauto_mgt.core.service_platform_manager import platform_manager
from wxauto_mgt.core.async_accounting_manager import AsyncAccountingManager
from wxauto_mgt.core.zhiweijz_platform import ZhiWeiJZPlatform

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_async_accounting_manager():
    """测试异步记账管理器"""
    logger.info("\n=== 测试异步记账管理器 ===")
    
    # 测试配置（请根据实际情况修改）
    test_config = {
        'server_url': 'https://app.zhiweijz.com',  # 请替换为实际的服务器地址
        'username': 'test@example.com',  # 请替换为实际的用户名
        'password': 'test_password',  # 请替换为实际的密码
        'account_book_id': '',  # 可以为空，会自动获取
        'auto_login': True,
        'request_timeout': 30
    }
    
    try:
        async with AsyncAccountingManager(test_config) as manager:
            # 测试登录
            logger.info("测试登录...")
            success, message = await manager.login()
            logger.info(f"登录结果: {success}, 消息: {message}")
            
            if success:
                # 测试获取账本列表
                logger.info("测试获取账本列表...")
                books_success, books_message, books = await manager.get_account_books()
                logger.info(f"获取账本结果: {books_success}, 消息: {books_message}")
                
                if books_success and books:
                    logger.info(f"找到 {len(books)} 个账本:")
                    for book in books[:3]:  # 只显示前3个
                        logger.info(f"  - {book.get('name', 'Unknown')} (ID: {book.get('id', 'Unknown')})")
                    
                    # 如果配置中没有账本ID，使用第一个账本
                    if not test_config['account_book_id'] and books:
                        test_config['account_book_id'] = books[0].get('id', '')
                        logger.info(f"使用第一个账本进行测试: {books[0].get('name', 'Unknown')}")
                
                # 测试智能记账（使用模拟数据）
                if test_config['account_book_id']:
                    logger.info("测试智能记账...")
                    test_descriptions = [
                        "午餐 麦当劳 35元",
                        "地铁费 5元",
                        "咖啡 星巴克 28元"
                    ]
                    
                    for desc in test_descriptions:
                        logger.info(f"测试记账: {desc}")
                        accounting_success, accounting_message = await manager.smart_accounting(
                            description=desc,
                            sender_name="测试用户"
                        )
                        logger.info(f"记账结果: {accounting_success}, 消息: {accounting_message}")
                        
                        # 等待一下避免请求过快
                        await asyncio.sleep(1)
                else:
                    logger.warning("没有可用的账本ID，跳过智能记账测试")
                
                # 测试获取统计信息
                stats = manager.get_stats()
                logger.info(f"管理器统计信息: {stats}")
            else:
                logger.error("登录失败，跳过后续测试")
        
        return True
        
    except Exception as e:
        logger.error(f"测试异步记账管理器失败: {e}")
        import traceback
        logger.error(f"错误详情: {traceback.format_exc()}")
        return False


async def test_zhiweijz_platform():
    """测试只为记账平台"""
    logger.info("\n=== 测试只为记账平台 ===")
    
    # 测试配置（请根据实际情况修改）
    test_config = {
        'server_url': 'https://app.zhiweijz.com',  # 请替换为实际的服务器地址
        'username': 'test@example.com',  # 请替换为实际的用户名
        'password': 'test_password',  # 请替换为实际的密码
        'account_book_id': '',  # 可以为空，会自动获取
        'account_book_name': '测试账本',
        'auto_login': True,
        'request_timeout': 30
    }
    
    try:
        # 创建平台实例
        platform = ZhiWeiJZPlatform(
            platform_id="test_zhiweijz_001",
            name="测试只为记账平台",
            config=test_config
        )
        
        # 测试初始化
        logger.info("测试平台初始化...")
        init_success = await platform.initialize()
        logger.info(f"初始化结果: {init_success}")
        
        if init_success:
            # 测试连接
            logger.info("测试平台连接...")
            connection_result = await platform.test_connection()
            logger.info(f"连接测试结果: {connection_result}")
            
            # 测试消息处理
            logger.info("测试消息处理...")
            test_messages = [
                {
                    'content': '早餐 包子 8元',
                    'sender': '张三',
                    'chat_name': '测试群聊',
                    'instance_id': 'test_instance'
                },
                {
                    'content': '打车费 滴滴 25元',
                    'sender': '李四',
                    'chat_name': '测试群聊',
                    'instance_id': 'test_instance'
                }
            ]
            
            for msg in test_messages:
                logger.info(f"处理消息: {msg['content']}")
                result = await platform.process_message(msg)
                logger.info(f"处理结果: {result}")
                
                # 等待一下避免请求过快
                await asyncio.sleep(1)
            
            # 获取平台统计信息
            stats = platform.get_stats()
            logger.info(f"平台统计信息: {stats}")
        else:
            logger.error("平台初始化失败，跳过后续测试")
        
        # 清理资源
        await platform.cleanup()
        
        return True
        
    except Exception as e:
        logger.error(f"测试只为记账平台失败: {e}")
        import traceback
        logger.error(f"错误详情: {traceback.format_exc()}")
        return False


async def test_platform_manager_integration():
    """测试平台管理器集成"""
    logger.info("\n=== 测试平台管理器集成 ===")
    
    try:
        # 初始化数据库
        db_path = os.path.join(project_root, 'data', 'wxauto_mgt.db')
        await db_manager.initialize(db_path)
        
        # 初始化平台管理器
        await platform_manager.initialize()
        
        # 测试配置（请根据实际情况修改）
        test_config = {
            'server_url': 'https://app.zhiweijz.com',  # 请替换为实际的服务器地址
            'username': 'test@example.com',  # 请替换为实际的用户名
            'password': 'test_password',  # 请替换为实际的密码
            'account_book_id': '',
            'account_book_name': '测试账本',
            'auto_login': True,
            'request_timeout': 30
        }
        
        # 注册只为记账平台
        logger.info("注册只为记账平台...")
        platform_id = await platform_manager.register_platform(
            platform_type="zhiweijz",
            name="测试只为记账平台",
            config=test_config,
            enabled=True
        )
        
        if platform_id:
            logger.info(f"平台注册成功，ID: {platform_id}")
            
            # 获取平台实例
            platform = await platform_manager.get_platform(platform_id)
            if platform:
                logger.info("获取平台实例成功")
                
                # 测试平台功能
                test_result = await platform.test_connection()
                logger.info(f"平台测试结果: {test_result}")
            else:
                logger.error("获取平台实例失败")
            
            # 清理测试平台
            logger.info("清理测试平台...")
            delete_success = await platform_manager.delete_platform(platform_id)
            logger.info(f"删除平台结果: {delete_success}")
        else:
            logger.error("平台注册失败")
        
        return True
        
    except Exception as e:
        logger.error(f"测试平台管理器集成失败: {e}")
        import traceback
        logger.error(f"错误详情: {traceback.format_exc()}")
        return False


async def main():
    """主函数"""
    logger.info("开始测试只为记账平台功能...")
    
    # 注意：这些测试需要真实的只为记账服务器配置
    # 请在运行前修改测试配置中的服务器地址、用户名和密码
    
    logger.warning("注意：这些测试需要真实的只为记账服务器配置")
    logger.warning("请在运行前修改测试配置中的服务器地址、用户名和密码")
    
    # 测试1: 异步记账管理器
    success1 = await test_async_accounting_manager()
    
    # 测试2: 只为记账平台
    success2 = await test_zhiweijz_platform()
    
    # 测试3: 平台管理器集成
    success3 = await test_platform_manager_integration()
    
    # 总结
    logger.info("\n=== 测试总结 ===")
    logger.info(f"异步记账管理器测试: {'✅ 通过' if success1 else '❌ 失败'}")
    logger.info(f"只为记账平台测试: {'✅ 通过' if success2 else '❌ 失败'}")
    logger.info(f"平台管理器集成测试: {'✅ 通过' if success3 else '❌ 失败'}")
    
    if all([success1, success2, success3]):
        logger.info("🎉 所有测试通过！")
        return True
    else:
        logger.error("❌ 部分测试失败")
        return False


if __name__ == "__main__":
    asyncio.run(main())
