#!/usr/bin/env python3
"""
测试UI对话框功能
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

async def test_ui_dialog_logic():
    """测试UI对话框逻辑"""
    try:
        # 初始化数据库
        await db_manager.initialize('./data/wxauto_mgt.db')
        
        # 初始化平台管理器
        await platform_manager.initialize()
        
        # 测试平台ID
        platform_id = 'openai_webtest01'
        
        print(f"=== 测试UI对话框逻辑: {platform_id} ===")
        
        # 模拟UI组件的编辑平台逻辑
        print("步骤1: 模拟UI组件获取平台数据")
        
        # 首先尝试从内存中获取平台
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
        else:
            print("❌ 内存中未找到平台，从数据库获取")
            platform_db_data = await db_manager.fetchone(
                "SELECT * FROM service_platforms WHERE platform_id = ?",
                (platform_id,)
            )
            
            if not platform_db_data:
                print("❌ 数据库中未找到平台")
                return
            
            config = json.loads(platform_db_data['config'])
            platform_data = {
                'platform_id': platform_db_data['platform_id'],
                'name': platform_db_data['name'],
                'type': platform_db_data['type'],
                'config': config,
                'initialized': False
            }
        
        print(f"平台数据: {json.dumps(platform_data, ensure_ascii=False, indent=2)}")
        
        # 步骤2: 模拟对话框加载数据
        print("\n步骤2: 模拟对话框加载数据")
        
        config = platform_data.get("config", {})
        
        # 模拟处理temperature字段（这是之前的问题所在）
        temperature = config.get("temperature", 0.7)
        if isinstance(temperature, str):
            try:
                temperature = float(temperature)
                print(f"✅ 成功转换temperature字符串 '{config.get('temperature')}' 为浮点数 {temperature}")
            except (ValueError, TypeError):
                temperature = 0.7
                print(f"❌ 转换temperature失败，使用默认值 {temperature}")
        else:
            print(f"✅ temperature已经是数字类型: {temperature}")
        
        # 模拟处理max_tokens字段
        max_tokens = config.get("max_tokens", 1000)
        if isinstance(max_tokens, str):
            try:
                max_tokens = int(max_tokens)
                print(f"✅ 成功转换max_tokens字符串 '{config.get('max_tokens')}' 为整数 {max_tokens}")
            except (ValueError, TypeError):
                max_tokens = 1000
                print(f"❌ 转换max_tokens失败，使用默认值 {max_tokens}")
        else:
            print(f"✅ max_tokens已经是数字类型: {max_tokens}")
        
        # 步骤3: 模拟对话框保存数据
        print("\n步骤3: 模拟对话框保存数据")
        
        # 模拟用户修改了一些配置
        new_config = config.copy()
        new_config['system_prompt'] = '你是一个经过UI测试的助手。'
        new_config['temperature'] = temperature  # 确保是数字类型
        new_config['max_tokens'] = max_tokens    # 确保是数字类型
        new_name = platform_data['name'] + ' (UI测试)'
        
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
                
                # 验证数据类型
                updated_config = p['config']
                print(f"\n数据类型验证:")
                print(f"  temperature: {updated_config.get('temperature')} (类型: {type(updated_config.get('temperature'))})")
                print(f"  max_tokens: {updated_config.get('max_tokens')} (类型: {type(updated_config.get('max_tokens'))})")
                break
        
    except Exception as e:
        print(f"❌ 测试过程中出错: {e}")
        print(f"异常详情: {traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(test_ui_dialog_logic())
