#!/usr/bin/env python3
"""
测试平台编辑功能
"""

import asyncio
import sys
import os
import json
import traceback

# 添加项目根目录到Python路径
sys.path.insert(0, '.')

from wxauto_mgt.data.db_manager import db_manager
from wxauto_mgt.core.service_platform_manager import platform_manager

async def test_edit_platform():
    """测试编辑平台功能"""
    try:
        # 初始化数据库
        await db_manager.initialize('./data/wxauto_mgt.db')
        
        # 初始化平台管理器
        await platform_manager.initialize()
        
        # 测试平台ID
        platform_id = 'openai_webtest01'
        
        print(f"=== 测试编辑平台: {platform_id} ===")
        
        # 步骤1: 尝试从内存获取平台
        print("步骤1: 从内存获取平台")
        platform = await platform_manager.get_platform(platform_id)
        
        if platform:
            print(f"✅ 内存中找到平台: {platform.name}")
            platform_data = {
                'platform_id': platform.platform_id,
                'name': platform.name,
                'type': platform.get_type(),
                'config': platform.config.copy(),
                'initialized': platform._initialized
            }
            print(f"平台数据: {json.dumps(platform_data, ensure_ascii=False, indent=2)}")
        else:
            print("❌ 内存中未找到平台")
            
            # 步骤2: 从数据库获取平台
            print("步骤2: 从数据库获取平台")
            platform_db_data = await db_manager.fetchone(
                "SELECT * FROM service_platforms WHERE platform_id = ?",
                (platform_id,)
            )
            
            if not platform_db_data:
                print("❌ 数据库中未找到平台")
                return
            
            print("✅ 数据库中找到平台")
            print(f"数据库数据: {dict(platform_db_data)}")
            
            # 解析配置
            config = json.loads(platform_db_data['config'])
            platform_data = {
                'platform_id': platform_db_data['platform_id'],
                'name': platform_db_data['name'],
                'type': platform_db_data['type'],
                'config': config,
                'initialized': False
            }
            print(f"构建的平台数据: {json.dumps(platform_data, ensure_ascii=False, indent=2)}")
        
        # 步骤3: 模拟编辑操作
        print("\n步骤3: 模拟编辑操作")
        
        # 修改配置
        new_config = platform_data['config'].copy()
        new_config['system_prompt'] = '你是一个更新后的助手。'
        new_name = platform_data['name'] + ' (已编辑)'
        
        print(f"新名称: {new_name}")
        print(f"新配置: {json.dumps(new_config, ensure_ascii=False, indent=2)}")
        
        # 步骤4: 更新平台
        print("\n步骤4: 更新平台")
        success = await platform_manager.update_platform_simple(
            platform_id,
            new_name,
            new_config
        )
        
        if success:
            print("✅ 平台更新成功")
        else:
            print("❌ 平台更新失败")
        
        # 步骤5: 验证更新
        print("\n步骤5: 验证更新")
        updated_platforms = await platform_manager.get_all_platforms()
        for p in updated_platforms:
            if p['platform_id'] == platform_id:
                print(f"更新后的平台: {json.dumps(p, ensure_ascii=False, indent=2)}")
                break
        
    except Exception as e:
        print(f"❌ 测试过程中出错: {e}")
        print(f"异常详情: {traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(test_edit_platform())
