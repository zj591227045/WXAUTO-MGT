#!/usr/bin/env python3
"""
添加记账相关数据库表的脚本

该脚本用于在现有数据库中添加记账平台相关的表结构，包括：
- accounting_records: 记账记录表
- zhiweijz_platforms: 只为记账平台配置表（可选，如果需要独立存储）
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

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def add_accounting_tables():
    """添加记账相关的数据库表"""
    try:
        # 初始化数据库
        db_path = os.path.join(project_root, 'data', 'wxauto_mgt.db')
        await db_manager.initialize(db_path)
        
        logger.info(f"数据库路径: {db_path}")
        
        # 检查记账记录表是否存在
        logger.info("\n=== 检查记账记录表 ===")
        
        table_exists = await db_manager.fetchone(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='accounting_records'"
        )
        
        if not table_exists:
            logger.info("创建记账记录表...")
            
            # 创建记账记录表
            await db_manager.execute("""
            CREATE TABLE IF NOT EXISTS accounting_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform_id TEXT NOT NULL,
                message_id TEXT,
                instance_id TEXT,
                chat_name TEXT,
                sender_name TEXT,
                description TEXT NOT NULL,
                amount REAL,
                category TEXT,
                account_book_id TEXT,
                account_book_name TEXT,
                success INTEGER NOT NULL,
                error_message TEXT,
                api_response TEXT,
                processing_time REAL,
                create_time INTEGER NOT NULL,
                FOREIGN KEY (platform_id) REFERENCES service_platforms(platform_id)
            )
            """)
            
            # 创建索引
            await db_manager.execute(
                "CREATE INDEX IF NOT EXISTS idx_accounting_records_platform_id ON accounting_records(platform_id)"
            )
            await db_manager.execute(
                "CREATE INDEX IF NOT EXISTS idx_accounting_records_success ON accounting_records(success)"
            )
            await db_manager.execute(
                "CREATE INDEX IF NOT EXISTS idx_accounting_records_create_time ON accounting_records(create_time)"
            )
            await db_manager.execute(
                "CREATE INDEX IF NOT EXISTS idx_accounting_records_instance_id ON accounting_records(instance_id)"
            )
            
            logger.info("✅ 记账记录表创建成功")
        else:
            logger.info("✅ 记账记录表已存在")
            
            # 检查表结构是否需要更新
            columns_result = await db_manager.fetchall("PRAGMA table_info(accounting_records)")
            column_names = [col['name'] for col in columns_result]
            
            # 需要添加的新字段
            new_columns = {
                'account_book_name': 'TEXT',
                'processing_time': 'REAL',
                'instance_id': 'TEXT'
            }
            
            for column_name, column_type in new_columns.items():
                if column_name not in column_names:
                    logger.info(f"添加字段 {column_name} 到记账记录表...")
                    await db_manager.execute(f"ALTER TABLE accounting_records ADD COLUMN {column_name} {column_type}")
                    logger.info(f"✅ 字段 {column_name} 添加成功")
        
        # 检查是否需要创建记账统计视图
        logger.info("\n=== 创建记账统计视图 ===")
        
        view_exists = await db_manager.fetchone(
            "SELECT name FROM sqlite_master WHERE type='view' AND name='accounting_stats'"
        )
        
        if not view_exists:
            logger.info("创建记账统计视图...")
            
            await db_manager.execute("""
            CREATE VIEW IF NOT EXISTS accounting_stats AS
            SELECT 
                platform_id,
                COUNT(*) as total_records,
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful_records,
                SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failed_records,
                ROUND(AVG(CASE WHEN success = 1 THEN processing_time END), 3) as avg_processing_time,
                SUM(CASE WHEN success = 1 AND amount IS NOT NULL THEN amount ELSE 0 END) as total_amount,
                MIN(create_time) as first_record_time,
                MAX(create_time) as last_record_time
            FROM accounting_records
            GROUP BY platform_id
            """)
            
            logger.info("✅ 记账统计视图创建成功")
        else:
            logger.info("✅ 记账统计视图已存在")
        
        # 验证表结构
        logger.info("\n=== 验证表结构 ===")
        
        # 检查记账记录表结构
        columns_result = await db_manager.fetchall("PRAGMA table_info(accounting_records)")
        logger.info("记账记录表结构:")
        for col in columns_result:
            logger.info(f"  {col['name']} - {col['type']} - {'NOT NULL' if col['notnull'] else 'NULL'}")
        
        # 检查索引
        indexes_result = await db_manager.fetchall(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='accounting_records'"
        )
        logger.info("记账记录表索引:")
        for idx in indexes_result:
            logger.info(f"  {idx['name']}")
        
        logger.info("\n✅ 记账相关数据库表添加完成")
        return True
        
    except Exception as e:
        logger.error(f"添加记账数据库表失败: {e}")
        import traceback
        logger.error(f"错误详情: {traceback.format_exc()}")
        return False


async def test_accounting_tables():
    """测试记账表的基本操作"""
    try:
        logger.info("\n=== 测试记账表操作 ===")
        
        # 测试插入记录
        test_record = {
            'platform_id': 'test_platform',
            'message_id': 'test_msg_001',
            'instance_id': 'test_instance',
            'chat_name': '测试群聊',
            'sender_name': '测试用户',
            'description': '午餐 麦当劳 35元',
            'amount': 35.0,
            'category': '餐饮',
            'account_book_id': 'book_123',
            'account_book_name': '个人账本',
            'success': 1,
            'error_message': None,
            'api_response': '{"success": true, "message": "记账成功"}',
            'processing_time': 1.23,
            'create_time': int(time.time())
        }
        
        # 插入测试记录
        test_record['create_time'] = int(time.time())
        
        await db_manager.execute("""
        INSERT INTO accounting_records (
            platform_id, message_id, instance_id, chat_name, sender_name,
            description, amount, category, account_book_id, account_book_name,
            success, error_message, api_response, processing_time, create_time
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            test_record['platform_id'], test_record['message_id'], test_record['instance_id'],
            test_record['chat_name'], test_record['sender_name'], test_record['description'],
            test_record['amount'], test_record['category'], test_record['account_book_id'],
            test_record['account_book_name'], test_record['success'], test_record['error_message'],
            test_record['api_response'], test_record['processing_time'], test_record['create_time']
        ))
        
        logger.info("✅ 测试记录插入成功")
        
        # 查询测试记录
        result = await db_manager.fetchone(
            "SELECT * FROM accounting_records WHERE platform_id = ?",
            (test_record['platform_id'],)
        )
        
        if result:
            logger.info("✅ 测试记录查询成功")
            logger.info(f"记录ID: {result['id']}, 描述: {result['description']}")
        else:
            logger.error("❌ 测试记录查询失败")
        
        # 测试统计视图
        stats = await db_manager.fetchone(
            "SELECT * FROM accounting_stats WHERE platform_id = ?",
            (test_record['platform_id'],)
        )
        
        if stats:
            logger.info("✅ 统计视图查询成功")
            logger.info(f"总记录数: {stats['total_records']}, 成功记录数: {stats['successful_records']}")
        else:
            logger.error("❌ 统计视图查询失败")
        
        # 清理测试数据
        await db_manager.execute(
            "DELETE FROM accounting_records WHERE platform_id = ?",
            (test_record['platform_id'],)
        )
        logger.info("✅ 测试数据清理完成")
        
        return True
        
    except Exception as e:
        logger.error(f"测试记账表操作失败: {e}")
        import traceback
        logger.error(f"错误详情: {traceback.format_exc()}")
        return False


async def main():
    """主函数"""
    logger.info("开始添加记账相关数据库表...")
    
    # 添加表
    if not await add_accounting_tables():
        logger.error("添加记账数据库表失败")
        return False
    
    # 测试表操作
    if not await test_accounting_tables():
        logger.error("测试记账表操作失败")
        return False
    
    logger.info("记账数据库表添加和测试完成")
    return True


if __name__ == "__main__":
    asyncio.run(main())
