#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试规则对话框

这个脚本会运行数据库升级，然后测试规则对话框的保存功能。
"""

import os
import sys
import logging
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

# 导入更新数据库结构的函数
from wxauto_mgt.scripts.update_db_schema import update_database_schema

# 导入数据库管理器
from wxauto_mgt.data.db_manager import db_manager

async def test_rule_dialog():
    """测试规则对话框"""
    try:
        # 更新数据库结构
        logger.info("更新数据库结构...")
        if not update_database_schema():
            logger.error("更新数据库结构失败")
            return False
        
        # 初始化数据库
        logger.info("初始化数据库...")
        db_path = os.path.join(project_root, 'data', 'wxauto_mgt.db')
        await db_manager.initialize(db_path)
        
        # 检查delivery_rules表结构
        logger.info("检查delivery_rules表结构...")
        columns = await db_manager.fetchall(
            "PRAGMA table_info(delivery_rules)"
        )
        
        column_names = [col['name'] for col in columns]
        logger.info(f"delivery_rules表列: {column_names}")
        
        # 检查是否包含必要的列
        required_columns = ['only_at_messages', 'at_name']
        missing_columns = [col for col in required_columns if col not in column_names]
        
        if missing_columns:
            logger.error(f"缺少必要的列: {missing_columns}")
            return False
        else:
            logger.info("所有必要的列都存在")
        
        # 测试添加规则
        logger.info("测试添加规则...")
        from wxauto_mgt.core.service_platform_manager import rule_manager
        
        # 初始化规则管理器
        await rule_manager.initialize()
        
        # 添加测试规则
        rule_id = await rule_manager.add_rule(
            name="测试规则",
            instance_id="test_instance",
            chat_pattern="测试聊天",
            platform_id="test_platform",
            priority=5,
            only_at_messages=1,
            at_name="测试用户"
        )
        
        if not rule_id:
            logger.error("添加规则失败")
            return False
        
        logger.info(f"添加规则成功: {rule_id}")
        
        # 获取规则并检查字段
        rule = await rule_manager.get_rule(rule_id)
        if not rule:
            logger.error("获取规则失败")
            return False
        
        logger.info(f"获取规则成功: {rule}")
        
        # 检查字段值
        if rule['only_at_messages'] != 1:
            logger.error(f"only_at_messages字段值错误: {rule['only_at_messages']}")
            return False
        
        if rule['at_name'] != "测试用户":
            logger.error(f"at_name字段值错误: {rule['at_name']}")
            return False
        
        logger.info("字段值正确")
        
        # 删除测试规则
        logger.info("删除测试规则...")
        if not await rule_manager.delete_rule(rule_id):
            logger.error("删除规则失败")
            return False
        
        logger.info("删除规则成功")
        
        logger.info("测试完成")
        return True
    except Exception as e:
        logger.error(f"测试过程中出错: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False
    finally:
        # 关闭数据库连接
        await db_manager.close()

async def main():
    """主函数"""
    success = await test_rule_dialog()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())
