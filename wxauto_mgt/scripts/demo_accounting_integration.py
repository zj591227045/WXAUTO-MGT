#!/usr/bin/env python3
"""
只为记账平台集成演示脚本

该脚本演示如何使用WXAUTO-MGT的只为记账平台集成功能，包括：
- 创建记账平台
- 配置消息投递规则
- 模拟消息处理
- 查看记账记录和统计
"""

import asyncio
import os
import sys
import logging
import time
import json

# 添加项目根目录到Python路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from wxauto_mgt.data.db_manager import db_manager
from wxauto_mgt.core.service_platform_manager import platform_manager, rule_manager

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def initialize_system():
    """初始化系统"""
    logger.info("初始化系统...")
    
    # 初始化数据库
    db_path = os.path.join(project_root, 'data', 'wxauto_mgt.db')
    await db_manager.initialize(db_path)
    logger.info("数据库初始化完成")
    
    # 初始化平台管理器
    await platform_manager.initialize()
    logger.info("平台管理器初始化完成")
    
    # 初始化规则管理器
    await rule_manager.initialize()
    logger.info("规则管理器初始化完成")


async def create_demo_accounting_platform():
    """创建演示用的记账平台"""
    logger.info("\n=== 创建演示记账平台 ===")
    
    # 演示配置（请根据实际情况修改）
    demo_config = {
        'server_url': 'https://demo.zhiweijz.com',  # 演示服务器地址
        'username': 'demo@example.com',  # 演示用户名
        'password': 'demo_password',  # 演示密码
        'account_book_id': 'demo_book_001',  # 演示账本ID
        'account_book_name': '演示账本',
        'auto_login': True,
        'token_refresh_interval': 300,
        'request_timeout': 30,
        'max_retries': 3
    }
    
    try:
        # 注册记账平台
        platform_id = await platform_manager.register_platform(
            platform_type="zhiweijz",
            name="演示记账平台",
            config=demo_config,
            enabled=True
        )
        
        if platform_id:
            logger.info(f"✅ 记账平台创建成功，ID: {platform_id}")
            return platform_id
        else:
            logger.error("❌ 记账平台创建失败")
            return None
            
    except Exception as e:
        logger.error(f"创建记账平台时出错: {e}")
        return None


async def create_demo_delivery_rule(platform_id: str):
    """创建演示用的消息投递规则"""
    logger.info("\n=== 创建消息投递规则 ===")
    
    try:
        # 创建投递规则
        rule_id = await rule_manager.add_rule(
            name="记账演示规则",
            instance_id="demo_instance",
            chat_pattern="记账群|账单群|消费群",  # 匹配包含这些关键词的群聊
            platform_id=platform_id,
            priority=1,
            only_at_messages=0,  # 不仅限于@消息
            at_name="",
            reply_at_sender=1  # 回复时@发送者
        )
        
        if rule_id:
            logger.info(f"✅ 投递规则创建成功，ID: {rule_id}")
            return rule_id
        else:
            logger.error("❌ 投递规则创建失败")
            return None
            
    except Exception as e:
        logger.error(f"创建投递规则时出错: {e}")
        return None


async def simulate_message_processing(platform_id: str):
    """模拟消息处理"""
    logger.info("\n=== 模拟消息处理 ===")
    
    # 模拟消息数据
    demo_messages = [
        {
            'content': '早餐 包子豆浆 12元',
            'sender': '张三',
            'chat_name': '记账群',
            'instance_id': 'demo_instance',
            'message_id': 'msg_001',
            'create_time': int(time.time())
        },
        {
            'content': '午餐 麦当劳 35元',
            'sender': '李四',
            'chat_name': '记账群',
            'instance_id': 'demo_instance',
            'message_id': 'msg_002',
            'create_time': int(time.time()) + 1
        },
        {
            'content': '地铁费 5元',
            'sender': '王五',
            'chat_name': '记账群',
            'instance_id': 'demo_instance',
            'message_id': 'msg_003',
            'create_time': int(time.time()) + 2
        },
        {
            'content': '咖啡 星巴克 28元',
            'sender': '赵六',
            'chat_name': '记账群',
            'instance_id': 'demo_instance',
            'message_id': 'msg_004',
            'create_time': int(time.time()) + 3
        }
    ]
    
    try:
        # 获取平台实例
        platform = await platform_manager.get_platform(platform_id)
        if not platform:
            logger.error("无法获取平台实例")
            return False
        
        # 处理每条消息
        for i, message in enumerate(demo_messages, 1):
            logger.info(f"处理消息 {i}/{len(demo_messages)}: {message['content']}")
            
            # 模拟记账处理（由于没有真实服务器，这里会失败，但会记录到数据库）
            try:
                result = await platform.process_message(message)
                logger.info(f"处理结果: {result}")
                
                # 将记录插入数据库（模拟记账记录）
                await insert_demo_accounting_record(
                    platform_id=platform_id,
                    message=message,
                    success=False,  # 由于是演示，标记为失败
                    error_message="演示模式：无真实服务器连接",
                    processing_time=0.5
                )
                
            except Exception as e:
                logger.warning(f"消息处理失败: {e}")
                
                # 记录失败的记账记录
                await insert_demo_accounting_record(
                    platform_id=platform_id,
                    message=message,
                    success=False,
                    error_message=str(e),
                    processing_time=0.1
                )
            
            # 等待一下模拟真实处理间隔
            await asyncio.sleep(0.5)
        
        logger.info("✅ 消息处理演示完成")
        return True
        
    except Exception as e:
        logger.error(f"模拟消息处理时出错: {e}")
        return False


async def insert_demo_accounting_record(platform_id: str, message: dict, success: bool, error_message: str = None, processing_time: float = 0.0):
    """插入演示记账记录"""
    try:
        # 模拟从消息中提取金额
        content = message['content']
        amount = None
        if '元' in content:
            # 简单的金额提取逻辑
            import re
            amount_match = re.search(r'(\d+(?:\.\d+)?)元', content)
            if amount_match:
                amount = float(amount_match.group(1))
        
        # 插入记录
        await db_manager.execute("""
        INSERT INTO accounting_records (
            platform_id, message_id, instance_id, chat_name, sender_name,
            description, amount, category, account_book_id, account_book_name,
            success, error_message, api_response, processing_time, create_time
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            platform_id, message['message_id'], message['instance_id'],
            message['chat_name'], message['sender'], message['content'],
            amount, '餐饮' if '餐' in content or '咖啡' in content else '交通' if '地铁' in content else '其他',
            'demo_book_001', '演示账本', 1 if success else 0, error_message,
            json.dumps({"demo": True, "success": success}), processing_time, message['create_time']
        ))
        
    except Exception as e:
        logger.error(f"插入演示记账记录失败: {e}")


async def show_accounting_records(platform_id: str):
    """显示记账记录"""
    logger.info("\n=== 记账记录 ===")
    
    try:
        # 查询记账记录
        records = await db_manager.fetchall(
            "SELECT * FROM accounting_records WHERE platform_id = ? ORDER BY create_time DESC",
            (platform_id,)
        )
        
        if records:
            logger.info(f"找到 {len(records)} 条记账记录:")
            for i, record in enumerate(records, 1):
                status = "✅ 成功" if record['success'] else "❌ 失败"
                amount_str = f"{record['amount']}元" if record['amount'] else "未知金额"
                logger.info(f"  {i}. {record['description']} - {amount_str} - {status}")
                if not record['success'] and record['error_message']:
                    logger.info(f"     错误: {record['error_message']}")
        else:
            logger.info("没有找到记账记录")
            
    except Exception as e:
        logger.error(f"查询记账记录失败: {e}")


async def show_accounting_stats(platform_id: str):
    """显示记账统计"""
    logger.info("\n=== 记账统计 ===")
    
    try:
        # 查询统计信息
        stats = await db_manager.fetchone(
            "SELECT * FROM accounting_stats WHERE platform_id = ?",
            (platform_id,)
        )
        
        if stats:
            logger.info("统计信息:")
            logger.info(f"  总记录数: {stats['total_records']}")
            logger.info(f"  成功记录数: {stats['successful_records']}")
            logger.info(f"  失败记录数: {stats['failed_records']}")
            logger.info(f"  成功率: {stats['successful_records']/stats['total_records']*100:.1f}%")
            logger.info(f"  总金额: {stats['total_amount']}元")
            if stats['avg_processing_time']:
                logger.info(f"  平均处理时间: {stats['avg_processing_time']}秒")
        else:
            logger.info("没有找到统计信息")
            
    except Exception as e:
        logger.error(f"查询统计信息失败: {e}")


async def cleanup_demo_data(platform_id: str, rule_id: str):
    """清理演示数据"""
    logger.info("\n=== 清理演示数据 ===")
    
    try:
        # 删除记账记录
        await db_manager.execute(
            "DELETE FROM accounting_records WHERE platform_id = ?",
            (platform_id,)
        )
        logger.info("✅ 记账记录已清理")
        
        # 删除投递规则
        if rule_id:
            await rule_manager.delete_rule(rule_id)
            logger.info("✅ 投递规则已删除")
        
        # 删除平台
        if platform_id:
            await platform_manager.delete_platform(platform_id)
            logger.info("✅ 记账平台已删除")
            
    except Exception as e:
        logger.error(f"清理演示数据失败: {e}")


async def main():
    """主函数"""
    logger.info("🚀 开始只为记账平台集成演示...")
    
    try:
        # 1. 初始化系统
        await initialize_system()
        
        # 2. 创建演示记账平台
        platform_id = await create_demo_accounting_platform()
        if not platform_id:
            logger.error("无法创建记账平台，演示终止")
            return
        
        # 3. 创建消息投递规则
        rule_id = await create_demo_delivery_rule(platform_id)
        
        # 4. 模拟消息处理
        await simulate_message_processing(platform_id)
        
        # 5. 显示记账记录
        await show_accounting_records(platform_id)
        
        # 6. 显示统计信息
        await show_accounting_stats(platform_id)
        
        # 7. 询问是否清理数据
        logger.info("\n演示完成！")
        
        # 在实际使用中，可以选择是否清理演示数据
        # 这里为了演示目的，我们保留数据
        logger.info("演示数据已保留，您可以通过Web界面查看")
        logger.info("如需清理演示数据，请手动调用cleanup_demo_data函数")
        
        logger.info("🎉 演示成功完成！")
        
    except Exception as e:
        logger.error(f"演示过程中出错: {e}")
        import traceback
        logger.error(f"错误详情: {traceback.format_exc()}")


if __name__ == "__main__":
    asyncio.run(main())
