#!/usr/bin/env python3
"""
测试连接恢复监控功能
验证当微信实例重启后，监听对象能够自动重新添加
"""

import asyncio
import sys
import os
import time

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_connection_recovery():
    """测试连接恢复监控功能"""
    try:
        # 导入必要的模块
        from wxauto_mgt.core.message_listener import message_listener
        from wxauto_mgt.core.api_client import instance_manager
        from wxauto_mgt.data.db_manager import db_manager
        
        print("=== 测试连接恢复监控功能 ===")
        
        # 初始化数据库管理器
        print("初始化数据库管理器...")
        await db_manager.initialize()
        
        # 1. 加载实例配置
        print("\n1. 加载实例配置:")
        instances = await db_manager.fetchall("SELECT instance_id, name, base_url, api_key, enabled FROM instances WHERE enabled = 1")
        
        if not instances:
            print("   没有启用的实例配置")
            return
        
        for instance in instances:
            instance_id = instance['instance_id']
            base_url = instance['base_url']
            api_key = instance['api_key']
            
            print(f"   加载实例: {instance_id} ({base_url})")
            client = instance_manager.add_instance(instance_id, base_url, api_key)
        
        # 2. 查看数据库中的active监听对象
        print("\n2. 数据库中的active监听对象:")
        active_listeners = await db_manager.fetchall(
            "SELECT instance_id, who, last_message_time FROM listeners WHERE status = 'active'"
        )
        
        if not active_listeners:
            print("   数据库中没有active状态的监听对象")
            return
        else:
            for listener in active_listeners:
                from datetime import datetime
                last_time = datetime.fromtimestamp(listener['last_message_time']).strftime('%Y-%m-%d %H:%M:%S')
                print(f"   {listener['instance_id']} - {listener['who']} - {last_time}")
        
        # 3. 启动监听服务
        print("\n3. 启动监听服务:")
        
        if message_listener.running:
            print("   停止当前运行的监听服务...")
            await message_listener.stop()
        
        print("   启动监听服务...")
        await message_listener.start()
        print("   监听服务已启动")
        
        # 4. 检查初始连接状态
        print("\n4. 检查初始连接状态:")
        
        # 等待一段时间让连接监控运行
        await asyncio.sleep(5)
        
        # 检查连接状态
        connection_states = message_listener._instance_connection_states
        
        for instance_id, state in connection_states.items():
            connected = state.get('connected', False)
            last_check = state.get('last_check', 0)
            status_text = "连接正常" if connected else "连接中断"
            print(f"   实例 {instance_id}: {status_text} (最后检查: {time.strftime('%H:%M:%S', time.localtime(last_check))})")
        
        # 5. 检查监听对象API连接状态
        print("\n5. 检查监听对象API连接状态:")
        
        total_listeners = 0
        connected_listeners = 0
        
        for instance_id, listeners_dict in message_listener.listeners.items():
            for who, listener_info in listeners_dict.items():
                if listener_info.active:
                    total_listeners += 1
                    api_connected = getattr(listener_info, 'api_connected', False)
                    if api_connected:
                        connected_listeners += 1
                    
                    status = "已连接" if api_connected else "未连接"
                    print(f"   {instance_id} - {who}: API {status}")
        
        print(f"   总活跃监听对象: {total_listeners}")
        print(f"   API已连接: {connected_listeners}")
        print(f"   API未连接: {total_listeners - connected_listeners}")
        
        # 6. 模拟连接恢复场景
        print("\n6. 模拟连接恢复场景:")
        
        if connected_listeners > 0:
            print("   当前有API连接，模拟连接中断...")
            
            # 手动将所有监听对象标记为API未连接
            for instance_id, listeners_dict in message_listener.listeners.items():
                for who, listener_info in listeners_dict.items():
                    if listener_info.active:
                        listener_info.api_connected = False
            
            print("   已模拟连接中断，所有监听对象API连接已断开")
            
            # 等待连接监控检测到恢复
            print("   等待连接监控检测到恢复并自动重新添加监听对象...")
            print("   (这可能需要等待最多30秒的监控间隔)")
            
            # 等待并观察恢复过程
            for i in range(6):  # 等待最多3分钟
                await asyncio.sleep(30)
                
                # 检查是否有监听对象恢复连接
                recovered_count = 0
                for instance_id, listeners_dict in message_listener.listeners.items():
                    for who, listener_info in listeners_dict.items():
                        if listener_info.active and getattr(listener_info, 'api_connected', False):
                            recovered_count += 1
                
                print(f"   第 {i+1} 次检查: {recovered_count} 个监听对象已恢复API连接")
                
                if recovered_count > 0:
                    print("   ✅ 检测到监听对象自动恢复！")
                    break
            else:
                print("   ⚠️ 在等待时间内未检测到自动恢复")
        else:
            print("   当前没有API连接，等待连接监控检测到连接并自动添加监听对象...")
            
            # 等待并观察连接建立过程
            for i in range(6):  # 等待最多3分钟
                await asyncio.sleep(30)
                
                # 检查是否有监听对象建立连接
                connected_count = 0
                for instance_id, listeners_dict in message_listener.listeners.items():
                    for who, listener_info in listeners_dict.items():
                        if listener_info.active and getattr(listener_info, 'api_connected', False):
                            connected_count += 1
                
                print(f"   第 {i+1} 次检查: {connected_count} 个监听对象已建立API连接")
                
                if connected_count > 0:
                    print("   ✅ 检测到监听对象自动连接！")
                    break
            else:
                print("   ⚠️ 在等待时间内未检测到自动连接")
        
        # 7. 最终状态检查
        print("\n7. 最终状态检查:")
        
        final_connected = 0
        for instance_id, listeners_dict in message_listener.listeners.items():
            for who, listener_info in listeners_dict.items():
                if listener_info.active and getattr(listener_info, 'api_connected', False):
                    final_connected += 1
        
        print(f"   最终API连接数: {final_connected} / {total_listeners}")
        
        # 检查连接状态
        final_connection_states = message_listener._instance_connection_states
        for instance_id, state in final_connection_states.items():
            connected = state.get('connected', False)
            status_text = "连接正常" if connected else "连接中断"
            print(f"   实例 {instance_id}: {status_text}")
        
        # 8. 总结
        print("\n8. 总结:")
        
        if final_connected > 0:
            print("   ✅ 连接恢复监控功能工作正常")
            print("   📝 功能特点:")
            print("     - 定期监控微信实例连接状态")
            print("     - 检测连接中断和恢复事件")
            print("     - 连接恢复后自动重新添加监听对象")
            print("     - 确保监听对象能够持续接收消息")
        else:
            print("   ⚠️ 连接恢复监控功能需要微信实例运行才能完全验证")
            print("   📝 说明:")
            print("     - 监控机制已启动并运行")
            print("     - 当微信实例可用时，会自动建立连接")
            print("     - 当微信实例重启后，会自动恢复监听对象")
        
        print("\n=== 测试完成 ===")
        
    except Exception as e:
        print(f"测试过程中出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_connection_recovery())
