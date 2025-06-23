#!/usr/bin/env python3
"""
直接测试删除函数
"""

import asyncio
import sys
import os
import traceback

# 添加项目根目录到Python路径
sys.path.insert(0, '.')

async def test_delete_function():
    """直接测试删除函数"""
    try:
        print("=== 直接测试删除函数 ===")
        
        # 导入删除函数
        from wxauto_mgt.web.api import delete_instance
        
        print(f"删除函数: {delete_instance}")
        print(f"函数类型: {type(delete_instance)}")
        
        # 测试调用删除函数
        instance_id = "test_instance"
        
        print(f"\n=== 测试调用删除函数 ===")
        try:
            result = await delete_instance(instance_id)
            print(f"删除函数返回: {result}")
        except Exception as e:
            print(f"删除函数异常: {e}")
            print(f"异常类型: {type(e)}")
            print(f"异常详情: {traceback.format_exc()}")
        
        # 测试FastAPI路由匹配
        print(f"\n=== 测试FastAPI路由匹配 ===")
        from wxauto_mgt.web.server import create_app
        from fastapi.testclient import TestClient
        
        app = create_app()
        client = TestClient(app)
        
        # 测试DELETE请求
        response = client.delete("/api/instances/test_instance")
        print(f"DELETE响应状态码: {response.status_code}")
        print(f"DELETE响应内容: {response.text}")
        print(f"DELETE响应头: {dict(response.headers)}")
        
        # 测试PUT请求作为对比
        response = client.put("/api/instances/test_instance", 
                             json={"name": "test", "base_url": "http://test", "api_key": "test"})
        print(f"PUT响应状态码: {response.status_code}")
        print(f"PUT响应内容: {response.text}")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        print(f"异常详情: {traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(test_delete_function())
