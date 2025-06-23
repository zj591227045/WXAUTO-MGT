#!/usr/bin/env python3
"""
升级listeners表，添加status字段支持活跃状态管理
"""

import os
import sys
import asyncio
import sqlite3
import logging
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from wxauto_mgt.data.db_manager import db_manager

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 数据库路径
DB_PATH = os.path.join(project_root, 'data', 'wxauto_mgt.db')

async def upgrade_listeners_table():
    """升级listeners表结构"""
    try:
        # 初始化数据库
        await db_manager.initialize(DB_PATH)
        
        print(f"数据库路径: {DB_PATH}")
        
        # 检查listeners表结构
        print("\n=== 检查listeners表结构 ===")
        
        # 获取表结构
        columns_result = await db_manager.fetchall("PRAGMA table_info(listeners)")
        
        if not columns_result:
            print("❌ listeners表不存在")
            return False
        
        print("当前表结构:")
        column_names = []
        for col in columns_result:
            column_names.append(col['name'])
            print(f"  {col['name']} - {col['type']} - {'NOT NULL' if col['notnull'] else 'NULL'} - 默认值: {col['dflt_value']}")
        
        # 检查是否需要添加status字段
        if 'status' not in column_names:
            print("\n=== 添加status字段 ===")
            
            # 添加status字段，默认值为'active'
            await db_manager.execute(
                "ALTER TABLE listeners ADD COLUMN status TEXT DEFAULT 'active'"
            )
            print("✅ 已添加status字段")
            
            # 更新现有记录的状态为'active'
            await db_manager.execute(
                "UPDATE listeners SET status = 'active' WHERE status IS NULL"
            )
            print("✅ 已更新现有记录状态为'active'")
        else:
            print("✅ status字段已存在")
        
        # 检查是否需要添加manual_added字段
        if 'manual_added' not in column_names:
            print("\n=== 添加manual_added字段 ===")
            
            # 添加manual_added字段，默认值为0
            await db_manager.execute(
                "ALTER TABLE listeners ADD COLUMN manual_added INTEGER DEFAULT 0"
            )
            print("✅ 已添加manual_added字段")
            
            # 更新现有记录的manual_added为0
            await db_manager.execute(
                "UPDATE listeners SET manual_added = 0 WHERE manual_added IS NULL"
            )
            print("✅ 已更新现有记录manual_added为0")
        else:
            print("✅ manual_added字段已存在")
        
        # 创建索引
        print("\n=== 创建索引 ===")
        
        # 为status字段创建索引
        await db_manager.execute(
            "CREATE INDEX IF NOT EXISTS idx_listeners_status ON listeners(status)"
        )
        print("✅ 已创建status字段索引")
        
        # 为manual_added字段创建索引
        await db_manager.execute(
            "CREATE INDEX IF NOT EXISTS idx_listeners_manual_added ON listeners(manual_added)"
        )
        print("✅ 已创建manual_added字段索引")
        
        # 验证升级结果
        print("\n=== 验证升级结果 ===")
        
        # 重新获取表结构
        updated_columns = await db_manager.fetchall("PRAGMA table_info(listeners)")
        print("升级后的表结构:")
        for col in updated_columns:
            print(f"  {col['name']} - {col['type']} - {'NOT NULL' if col['notnull'] else 'NULL'} - 默认值: {col['dflt_value']}")
        
        # 检查现有数据
        listeners_count = await db_manager.fetchone("SELECT COUNT(*) as count FROM listeners")
        print(f"\n监听对象总数: {listeners_count['count']}")
        
        if listeners_count['count'] > 0:
            # 按状态统计
            status_stats = await db_manager.fetchall(
                "SELECT status, COUNT(*) as count FROM listeners GROUP BY status"
            )
            print("按状态统计:")
            for stat in status_stats:
                print(f"  {stat['status']}: {stat['count']}")
            
            # 按manual_added统计
            manual_stats = await db_manager.fetchall(
                "SELECT manual_added, COUNT(*) as count FROM listeners GROUP BY manual_added"
            )
            print("按手动添加统计:")
            for stat in manual_stats:
                manual_type = "手动添加" if stat['manual_added'] == 1 else "自动添加"
                print(f"  {manual_type}: {stat['count']}")
        
        print("\n✅ listeners表升级完成")
        return True
        
    except Exception as e:
        logger.error(f"升级listeners表时出错: {e}")
        print(f"❌ 升级失败: {e}")
        return False

async def main():
    """主函数"""
    print("开始升级listeners表...")
    
    success = await upgrade_listeners_table()
    
    if success:
        print("\n🎉 升级成功完成！")
    else:
        print("\n❌ 升级失败！")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
