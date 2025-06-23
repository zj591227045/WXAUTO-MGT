#!/usr/bin/env python3
"""
测试 Web API 脚本

直接测试运行中的 HTTP 服务器 API 接口
"""

import requests
import json

def test_live_api():
    """测试运行中的 API 服务器"""
    base_url = "http://10.255.0.10:8080"

    # 测试添加实例 API
    print("\n=== 测试添加实例 API ===")
    import time

    # 创建测试实例数据
    test_instance_data = {
        "name": "测试实例",
        "base_url": "http://localhost:5001",
        "api_key": "test_api_key_123",
        "enabled": True,
        "config": {
            "timeout": 30,
            "retry_limit": 3,
            "poll_interval": 5,
            "timeout_minutes": 30
        }
    }

    try:
        start_time = time.time()
        response = requests.post(
            f"{base_url}/api/instances",
            json=test_instance_data,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        end_time = time.time()

        print(f"添加实例请求:")
        print(f"  状态码: {response.status_code}")
        print(f"  响应时间: {end_time - start_time:.2f} 秒")

        if response.status_code == 200:
            data = response.json()
            print(f"  响应数据: {json.dumps(data, ensure_ascii=False, indent=2)}")
            created_instance_id = data.get('data', {}).get('instance_id')

            if created_instance_id:
                print(f"  成功创建实例: {created_instance_id}")

                # 测试获取实例列表，验证实例是否被创建
                print("\n=== 验证实例是否被创建 ===")
                list_response = requests.get(f"{base_url}/api/instances", timeout=10)
                if list_response.status_code == 200:
                    instances = list_response.json()
                    found_instance = None
                    for instance in instances:
                        if instance.get('instance_id') == created_instance_id:
                            found_instance = instance
                            break

                    if found_instance:
                        print(f"  ✅ 实例已成功创建并出现在列表中")
                        print(f"  实例名称: {found_instance.get('name')}")
                        print(f"  实例状态: {found_instance.get('status')}")
                    else:
                        print(f"  ❌ 实例未在列表中找到")

                # 测试删除实例
                print(f"\n=== 测试删除实例 {created_instance_id} ===")
                delete_response = requests.delete(f"{base_url}/api/instances/{created_instance_id}", timeout=10)
                print(f"  删除状态码: {delete_response.status_code}")
                if delete_response.status_code == 200:
                    delete_data = delete_response.json()
                    print(f"  删除响应: {json.dumps(delete_data, ensure_ascii=False, indent=2)}")
                    print(f"  ✅ 实例删除成功")
                else:
                    print(f"  ❌ 删除失败: {delete_response.text}")
        else:
            print(f"  ❌ 添加失败: {response.text}")
    except Exception as e:
        print(f"  ❌ 请求失败: {e}")

    # 测试实例 API 的性能
    print("\n=== 性能测试实例 API ===")

    for i in range(2):
        try:
            start_time = time.time()
            response = requests.get(f"{base_url}/api/instances", timeout=30)
            end_time = time.time()

            print(f"第 {i+1} 次请求:")
            print(f"  状态码: {response.status_code}")
            print(f"  响应时间: {end_time - start_time:.2f} 秒")

            if response.status_code == 200:
                data = response.json()
                print(f"  实例数量: {len(data)}")
                if data:
                    instance = data[0]
                    print(f"  第一个实例状态: {instance.get('status')}")
                    print(f"  运行时间: {instance.get('runtime')}")
                    print(f"  CPU使用率: {instance.get('cpu_percent')}%")
            else:
                print(f"  请求失败: {response.text}")
        except Exception as e:
            print(f"  请求失败: {e}")

        if i < 1:
            print("  等待 2 秒...")
            time.sleep(2)

    # 测试添加平台和规则功能
    print("\n=== 测试添加平台功能 ===")

    # 创建测试平台数据
    test_platform_data = {
        "name": "测试OpenAI平台",
        "type": "openai",
        "enabled": True,
        "config": {
            "api_key": "test_openai_key_123",
            "api_base": "https://api.openai.com/v1",
            "model": "gpt-3.5-turbo",
            "temperature": 0.7,
            "system_prompt": "你是一个有用的助手。",
            "max_tokens": 1000
        }
    }

    created_platform_id = None
    try:
        response = requests.post(
            f"{base_url}/api/platforms",
            json=test_platform_data,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            created_platform_id = data.get('data', {}).get('platform_id')
            print(f"✅ 成功创建测试平台: {created_platform_id}")
        else:
            print(f"❌ 创建平台失败: {response.text}")
    except Exception as e:
        print(f"❌ 创建平台请求失败: {e}")

    # 测试添加规则功能
    if created_platform_id:
        print("\n=== 测试添加规则功能 ===")

        test_rule_data = {
            "name": "测试@消息规则",
            "instance_id": "*",
            "chat_pattern": "测试群*",
            "platform_id": created_platform_id,
            "priority": 10,
            "only_at_messages": 1,
            "at_name": "小助手,AI助手",
            "reply_at_sender": 1
        }

        created_rule_id = None
        try:
            response = requests.post(
                f"{base_url}/api/rules",
                json=test_rule_data,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                created_rule_id = data.get('data', {}).get('rule_id')
                print(f"✅ 成功创建测试规则: {created_rule_id}")
            else:
                print(f"❌ 创建规则失败: {response.text}")
        except Exception as e:
            print(f"❌ 创建规则请求失败: {e}")

        # 清理测试数据
        if created_rule_id:
            print(f"\n=== 清理测试规则 {created_rule_id} ===")
            try:
                response = requests.delete(f"{base_url}/api/rules/{created_rule_id}", timeout=10)
                if response.status_code == 200:
                    print("✅ 测试规则删除成功")
                else:
                    print(f"❌ 删除规则失败: {response.text}")
            except Exception as e:
                print(f"❌ 删除规则请求失败: {e}")

    # 清理测试平台
    if created_platform_id:
        print(f"\n=== 清理测试平台 {created_platform_id} ===")
        try:
            response = requests.delete(f"{base_url}/api/platforms/{created_platform_id}", timeout=10)
            if response.status_code == 200:
                print("✅ 测试平台删除成功")
            else:
                print(f"❌ 删除平台失败: {response.text}")
        except Exception as e:
            print(f"❌ 删除平台请求失败: {e}")

    # 测试其他 API 端点
    endpoints = [
        "/api/test",
        "/api/platforms",
        "/api/rules",
        "/api/messages",
        "/api/listeners"
    ]

    for endpoint in endpoints:
        try:
            print(f"\n=== 测试 {endpoint} ===")
            start_time = time.time()
            response = requests.get(f"{base_url}{endpoint}", timeout=10)
            end_time = time.time()

            print(f"状态码: {response.status_code}")
            print(f"响应时间: {end_time - start_time:.2f} 秒")

            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"响应数据类型: {type(data)}")
                    if isinstance(data, list):
                        print(f"数据长度: {len(data)}")
                        if len(data) > 0:
                            print(f"第一条数据: {json.dumps(data[0], ensure_ascii=False, indent=2)}")
                        else:
                            print("数据为空列表")
                    elif isinstance(data, dict):
                        print(f"数据内容: {json.dumps(data, ensure_ascii=False, indent=2)}")
                    else:
                        print(f"数据内容: {data}")
                except Exception as e:
                    print(f"解析 JSON 失败: {e}")
                    print(f"原始响应: {response.text[:500]}")
            else:
                print(f"请求失败: {response.text}")

        except Exception as e:
            print(f"请求 {endpoint} 失败: {e}")

def main():
    """主函数"""
    print("测试运行中的 Web API 服务器: http://10.255.0.10:8080")
    test_live_api()
    print("\n测试完成")

if __name__ == "__main__":
    main()
