#!/usr/bin/env python3
"""
调试 API 端点脚本

检查具体的 API 端点是否正常工作
"""

import requests
import json

def test_specific_endpoints():
    """测试具体的 API 端点"""
    base_url = "http://10.255.0.10:8080"
    
    # 测试所有可能的实例相关端点
    instance_endpoints = [
        ("GET", "/api/instances"),
        ("POST", "/api/instances"),
        ("PUT", "/api/instances/test_id"),
        ("DELETE", "/api/instances/test_id"),
    ]
    
    print("=== 测试实例相关端点 ===")
    for method, endpoint in instance_endpoints:
        try:
            if method == "GET":
                response = requests.get(f"{base_url}{endpoint}", timeout=5)
            elif method == "POST":
                test_data = {
                    "name": "测试实例",
                    "base_url": "http://localhost:5001",
                    "api_key": "test_key"
                }
                response = requests.post(
                    f"{base_url}{endpoint}",
                    json=test_data,
                    headers={'Content-Type': 'application/json'},
                    timeout=5
                )
            elif method == "PUT":
                test_data = {
                    "name": "更新测试实例",
                    "base_url": "http://localhost:5001",
                    "api_key": "test_key"
                }
                response = requests.put(
                    f"{base_url}{endpoint}",
                    json=test_data,
                    headers={'Content-Type': 'application/json'},
                    timeout=5
                )
            elif method == "DELETE":
                response = requests.delete(f"{base_url}{endpoint}", timeout=5)
            
            print(f"{method} {endpoint}: {response.status_code}")
            if response.status_code != 200:
                print(f"  错误: {response.text}")
        except Exception as e:
            print(f"{method} {endpoint}: 请求失败 - {e}")
    
    # 测试平台相关端点
    platform_endpoints = [
        ("GET", "/api/platforms"),
        ("POST", "/api/platforms"),
        ("PUT", "/api/platforms/test_id"),
        ("DELETE", "/api/platforms/test_id"),
    ]
    
    print("\n=== 测试平台相关端点 ===")
    for method, endpoint in platform_endpoints:
        try:
            if method == "GET":
                response = requests.get(f"{base_url}{endpoint}", timeout=5)
            elif method == "POST":
                test_data = {
                    "name": "测试平台",
                    "type": "openai",
                    "config": {
                        "api_key": "test_key",
                        "model": "gpt-3.5-turbo"
                    }
                }
                response = requests.post(
                    f"{base_url}{endpoint}",
                    json=test_data,
                    headers={'Content-Type': 'application/json'},
                    timeout=5
                )
            elif method == "PUT":
                test_data = {
                    "name": "更新测试平台",
                    "config": {
                        "api_key": "test_key",
                        "model": "gpt-3.5-turbo"
                    }
                }
                response = requests.put(
                    f"{base_url}{endpoint}",
                    json=test_data,
                    headers={'Content-Type': 'application/json'},
                    timeout=5
                )
            elif method == "DELETE":
                response = requests.delete(f"{base_url}{endpoint}", timeout=5)
            
            print(f"{method} {endpoint}: {response.status_code}")
            if response.status_code != 200:
                print(f"  错误: {response.text}")
        except Exception as e:
            print(f"{method} {endpoint}: 请求失败 - {e}")
    
    # 测试规则相关端点
    rule_endpoints = [
        ("GET", "/api/rules"),
        ("POST", "/api/rules"),
        ("PUT", "/api/rules/test_id"),
        ("DELETE", "/api/rules/test_id"),
    ]
    
    print("\n=== 测试规则相关端点 ===")
    for method, endpoint in rule_endpoints:
        try:
            if method == "GET":
                response = requests.get(f"{base_url}{endpoint}", timeout=5)
            elif method == "POST":
                test_data = {
                    "name": "测试规则",
                    "instance_id": "*",
                    "chat_pattern": "*",
                    "platform_id": "test_platform"
                }
                response = requests.post(
                    f"{base_url}{endpoint}",
                    json=test_data,
                    headers={'Content-Type': 'application/json'},
                    timeout=5
                )
            elif method == "PUT":
                test_data = {
                    "name": "更新测试规则",
                    "instance_id": "*",
                    "chat_pattern": "*",
                    "platform_id": "test_platform"
                }
                response = requests.put(
                    f"{base_url}{endpoint}",
                    json=test_data,
                    headers={'Content-Type': 'application/json'},
                    timeout=5
                )
            elif method == "DELETE":
                response = requests.delete(f"{base_url}{endpoint}", timeout=5)
            
            print(f"{method} {endpoint}: {response.status_code}")
            if response.status_code != 200:
                print(f"  错误: {response.text}")
        except Exception as e:
            print(f"{method} {endpoint}: 请求失败 - {e}")

if __name__ == "__main__":
    test_specific_endpoints()
