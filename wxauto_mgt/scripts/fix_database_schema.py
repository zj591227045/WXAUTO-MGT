#!/usr/bin/env python3
"""
修复数据库表结构

检查并修复 service_platforms 表的 enabled 字段
"""

import asyncio
import sys
import os

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from wxauto_mgt.data.db_manager import db_manager
from wxauto_mgt.utils.logging import logger

async def check_and_fix_database():
    """检查并修复数据库表结构"""
    try:
        # 初始化数据库
        db_path = os.path.join(project_root, 'data', 'wxauto_mgt.db')
        await db_manager.initialize(db_path)
        
        print(f"数据库路径: {db_path}")
        
        # 检查 service_platforms 表结构
        print("\n=== 检查 service_platforms 表结构 ===")
        
        # 获取表结构
        columns_result = await db_manager.fetchall("PRAGMA table_info(service_platforms)")
        
        if not columns_result:
            print("❌ service_platforms 表不存在")
            return
        
        print("当前表结构:")
        column_names = []
        for col in columns_result:
            column_names.append(col['name'])
            print(f"  {col['name']} - {col['type']} - {'NOT NULL' if col['notnull'] else 'NULL'} - 默认值: {col['dflt_value']}")
        
        # 检查是否有 enabled 字段
        if 'enabled' not in column_names:
            print("\n❌ 缺少 enabled 字段，正在添加...")
            try:
                await db_manager.execute(
                    "ALTER TABLE service_platforms ADD COLUMN enabled INTEGER NOT NULL DEFAULT 1"
                )
                print("✅ 成功添加 enabled 字段")
            except Exception as e:
                print(f"❌ 添加 enabled 字段失败: {e}")
        else:
            print("\n✅ enabled 字段已存在")
        
        # 检查现有数据
        print("\n=== 检查现有平台数据 ===")
        platforms = await db_manager.fetchall("SELECT platform_id, name, type, enabled FROM service_platforms")
        
        if not platforms:
            print("没有现有平台数据")
        else:
            print(f"找到 {len(platforms)} 个平台:")
            for platform in platforms:
                enabled_status = "启用" if platform.get('enabled') == 1 else "禁用" if platform.get('enabled') == 0 else "未知"
                print(f"  {platform['name']} ({platform['type']}) - {enabled_status} (enabled={platform.get('enabled')})")
        
        # 修复 enabled 字段为 NULL 的记录
        null_enabled_count = await db_manager.fetchone(
            "SELECT COUNT(*) as count FROM service_platforms WHERE enabled IS NULL"
        )
        
        if null_enabled_count and null_enabled_count['count'] > 0:
            print(f"\n⚠️  发现 {null_enabled_count['count']} 个平台的 enabled 字段为 NULL，正在修复...")
            try:
                await db_manager.execute(
                    "UPDATE service_platforms SET enabled = 1 WHERE enabled IS NULL"
                )
                print("✅ 成功修复 enabled 字段")
            except Exception as e:
                print(f"❌ 修复 enabled 字段失败: {e}")
        
        # 再次检查数据
        print("\n=== 修复后的平台数据 ===")
        platforms = await db_manager.fetchall("SELECT platform_id, name, type, enabled FROM service_platforms")
        
        if platforms:
            for platform in platforms:
                enabled_status = "启用" if platform.get('enabled') == 1 else "禁用" if platform.get('enabled') == 0 else "未知"
                print(f"  {platform['name']} ({platform['type']}) - {enabled_status} (enabled={platform.get('enabled')})")
        
        # 检查 delivery_rules 表的新字段
        print("\n=== 检查 delivery_rules 表结构 ===")
        
        # 获取表结构
        rules_columns_result = await db_manager.fetchall("PRAGMA table_info(delivery_rules)")
        
        if not rules_columns_result:
            print("❌ delivery_rules 表不存在")
        else:
            print("当前表结构:")
            rules_column_names = []
            for col in rules_columns_result:
                rules_column_names.append(col['name'])
                print(f"  {col['name']} - {col['type']} - {'NOT NULL' if col['notnull'] else 'NULL'} - 默认值: {col['dflt_value']}")
            
            # 检查新字段
            missing_fields = []
            if 'only_at_messages' not in rules_column_names:
                missing_fields.append(('only_at_messages', 'INTEGER DEFAULT 0'))
            if 'at_name' not in rules_column_names:
                missing_fields.append(('at_name', 'TEXT DEFAULT ""'))
            if 'reply_at_sender' not in rules_column_names:
                missing_fields.append(('reply_at_sender', 'INTEGER DEFAULT 0'))
            
            if missing_fields:
                print(f"\n⚠️  发现缺少 {len(missing_fields)} 个字段，正在添加...")
                for field_name, field_def in missing_fields:
                    try:
                        await db_manager.execute(
                            f"ALTER TABLE delivery_rules ADD COLUMN {field_name} {field_def}"
                        )
                        print(f"✅ 成功添加 {field_name} 字段")
                    except Exception as e:
                        print(f"❌ 添加 {field_name} 字段失败: {e}")
            else:
                print("\n✅ 所有必需字段都已存在")
        
        print("\n=== 数据库检查和修复完成 ===")
        
    except Exception as e:
        print(f"❌ 数据库检查失败: {e}")
        import traceback
        print(traceback.format_exc())
    finally:
        await db_manager.close()

if __name__ == "__main__":
    asyncio.run(check_and_fix_database())
