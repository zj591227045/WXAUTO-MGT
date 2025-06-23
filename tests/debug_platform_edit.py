#!/usr/bin/env python3
"""
调试平台编辑问题
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

async def debug_platform_edit():
    """调试平台编辑问题"""
    try:
        # 初始化数据库
        await db_manager.initialize('./data/wxauto_mgt.db')
        
        # 初始化平台管理器
        await platform_manager.initialize()
        
        print("=== 获取所有平台 ===")
        platforms = await platform_manager.get_all_platforms()
        
        for platform in platforms:
            print(f"平台ID: {platform['platform_id']}")
            print(f"名称: {platform['name']}")
            print(f"类型: {platform['type']}")
            print(f"启用: {platform['enabled']}")
            print(f"初始化: {platform.get('initialized', 'N/A')}")
            print(f"配置: {json.dumps(platform['config'], ensure_ascii=False, indent=2)}")
            print("-" * 50)
            
            # 尝试从内存获取平台
            memory_platform = await platform_manager.get_platform(platform['platform_id'])
            if memory_platform:
                print(f"内存中存在: {memory_platform.name}")
            else:
                print("内存中不存在，尝试从数据库获取...")
                
                # 模拟编辑平台的逻辑
                try:
                    platform_db_data = await db_manager.fetchone(
                        "SELECT * FROM service_platforms WHERE platform_id = ?",
                        (platform['platform_id'],)
                    )
                    
                    if platform_db_data:
                        print("数据库中找到平台数据:")
                        print(f"  platform_id: {platform_db_data['platform_id']}")
                        print(f"  name: {platform_db_data['name']}")
                        print(f"  type: {platform_db_data['type']}")
                        print(f"  enabled: {platform_db_data['enabled']}")
                        print(f"  config: {platform_db_data['config'][:100]}...")
                        
                        # 尝试解析配置
                        try:
                            config = json.loads(platform_db_data['config'])
                            print(f"  配置解析成功，包含 {len(config)} 个字段")
                            
                            # 构建平台数据
                            platform_data = {
                                'platform_id': platform_db_data['platform_id'],
                                'name': platform_db_data['name'],
                                'type': platform_db_data['type'],
                                'config': config,
                                'initialized': False
                            }
                            print("  平台数据构建成功")
                            
                        except json.JSONDecodeError as e:
                            print(f"  ❌ 配置解析失败: {e}")
                        except Exception as e:
                            print(f"  ❌ 构建平台数据失败: {e}")
                            print(f"  异常详情: {traceback.format_exc()}")
                    else:
                        print("❌ 数据库中未找到平台数据")
                        
                except Exception as e:
                    print(f"❌ 从数据库获取平台数据失败: {e}")
                    print(f"异常详情: {traceback.format_exc()}")
            
            print("=" * 50)
            
    except Exception as e:
        print(f"❌ 调试过程中出错: {e}")
        print(f"异常详情: {traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(debug_platform_edit())
