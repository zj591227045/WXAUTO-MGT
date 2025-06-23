#!/usr/bin/env python3
"""
测试平台状态功能

验证平台的启用/禁用状态是否正确处理
"""

import requests
import json
import time

def test_platform_status():
    """测试平台状态功能"""
    base_url = "http://10.255.0.10:8080"
    
    print("=== 测试平台状态功能 ===")
    
    # 1. 创建启用的平台
    print("\n1. 创建启用的平台")
    enabled_platform_data = {
        "name": "测试启用平台",
        "type": "openai",
        "enabled": True,
        "config": {
            "api_key": "test_enabled_key",
            "api_base": "https://api.openai.com/v1",
            "model": "gpt-3.5-turbo",
            "temperature": 0.7,
            "system_prompt": "你是一个有用的助手。",
            "max_tokens": 1000
        }
    }
    
    enabled_platform_id = None
    try:
        response = requests.post(
            f"{base_url}/api/platforms",
            json=enabled_platform_data,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            enabled_platform_id = data.get('data', {}).get('platform_id')
            print(f"✅ 成功创建启用平台: {enabled_platform_id}")
        else:
            print(f"❌ 创建启用平台失败: {response.text}")
    except Exception as e:
        print(f"❌ 创建启用平台请求失败: {e}")
    
    # 2. 创建禁用的平台
    print("\n2. 创建禁用的平台")
    disabled_platform_data = {
        "name": "测试禁用平台",
        "type": "openai",
        "enabled": False,
        "config": {
            "api_key": "test_disabled_key",
            "api_base": "https://api.openai.com/v1",
            "model": "gpt-3.5-turbo",
            "temperature": 0.7,
            "system_prompt": "你是一个有用的助手。",
            "max_tokens": 1000
        }
    }
    
    disabled_platform_id = None
    try:
        response = requests.post(
            f"{base_url}/api/platforms",
            json=disabled_platform_data,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            disabled_platform_id = data.get('data', {}).get('platform_id')
            print(f"✅ 成功创建禁用平台: {disabled_platform_id}")
        else:
            print(f"❌ 创建禁用平台失败: {response.text}")
    except Exception as e:
        print(f"❌ 创建禁用平台请求失败: {e}")
    
    # 3. 验证平台状态
    print("\n3. 验证平台状态")
    try:
        response = requests.get(f"{base_url}/api/platforms", timeout=10)
        if response.status_code == 200:
            platforms = response.json()
            print(f"获取到 {len(platforms)} 个平台")
            
            for platform in platforms:
                platform_id = platform.get('platform_id')
                name = platform.get('name')
                enabled = platform.get('enabled')
                
                if platform_id == enabled_platform_id:
                    if enabled:
                        print(f"✅ 启用平台状态正确: {name} (enabled={enabled})")
                    else:
                        print(f"❌ 启用平台状态错误: {name} (enabled={enabled})")
                elif platform_id == disabled_platform_id:
                    if not enabled:
                        print(f"✅ 禁用平台状态正确: {name} (enabled={enabled})")
                    else:
                        print(f"❌ 禁用平台状态错误: {name} (enabled={enabled})")
                else:
                    print(f"ℹ️  其他平台: {name} (enabled={enabled})")
        else:
            print(f"❌ 获取平台列表失败: {response.text}")
    except Exception as e:
        print(f"❌ 获取平台列表请求失败: {e}")
    
    # 4. 测试更新平台状态
    if enabled_platform_id:
        print(f"\n4. 测试更新平台状态 - 禁用启用的平台")
        update_data = {
            "name": "测试启用平台（已更新）",
            "enabled": False,
            "config": {
                "api_key": "test_enabled_key_updated",
                "api_base": "https://api.openai.com/v1",
                "model": "gpt-3.5-turbo",
                "temperature": 0.8,
                "system_prompt": "你是一个有用的助手。",
                "max_tokens": 1500
            }
        }
        
        try:
            response = requests.put(
                f"{base_url}/api/platforms/{enabled_platform_id}",
                json=update_data,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            if response.status_code == 200:
                print(f"✅ 成功更新平台状态")
                
                # 验证更新后的状态
                time.sleep(1)  # 等待一秒确保更新完成
                response = requests.get(f"{base_url}/api/platforms", timeout=10)
                if response.status_code == 200:
                    platforms = response.json()
                    for platform in platforms:
                        if platform.get('platform_id') == enabled_platform_id:
                            if not platform.get('enabled'):
                                print(f"✅ 平台状态更新成功: {platform.get('name')} (enabled={platform.get('enabled')})")
                            else:
                                print(f"❌ 平台状态更新失败: {platform.get('name')} (enabled={platform.get('enabled')})")
                            break
            else:
                print(f"❌ 更新平台状态失败: {response.text}")
        except Exception as e:
            print(f"❌ 更新平台状态请求失败: {e}")
    
    # 5. 清理测试数据
    print("\n5. 清理测试数据")
    for platform_id, name in [(enabled_platform_id, "启用平台"), (disabled_platform_id, "禁用平台")]:
        if platform_id:
            try:
                response = requests.delete(f"{base_url}/api/platforms/{platform_id}", timeout=10)
                if response.status_code == 200:
                    print(f"✅ 成功删除{name}: {platform_id}")
                else:
                    print(f"❌ 删除{name}失败: {response.text}")
            except Exception as e:
                print(f"❌ 删除{name}请求失败: {e}")

if __name__ == "__main__":
    test_platform_status()
