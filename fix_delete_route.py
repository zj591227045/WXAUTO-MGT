#!/usr/bin/env python3
"""
修复删除路由问题
"""

import sys
import os
import traceback

# 添加项目根目录到Python路径
sys.path.insert(0, '.')

def fix_delete_route():
    """修复删除路由问题"""
    try:
        print("=== 修复删除路由问题 ===")
        
        # 创建一个简化的测试API来验证问题
        from fastapi import FastAPI, HTTPException
        from fastapi.testclient import TestClient
        
        # 创建测试应用
        test_app = FastAPI()
        
        # 添加简单的DELETE路由
        @test_app.delete("/api/instances/{instance_id}")
        async def test_delete_instance(instance_id: str):
            return {"message": f"删除实例 {instance_id} 成功", "instance_id": instance_id}
        
        # 添加PUT路由作为对比
        @test_app.put("/api/instances/{instance_id}")
        async def test_update_instance(instance_id: str):
            return {"message": f"更新实例 {instance_id} 成功", "instance_id": instance_id}
        
        # 测试简化的应用
        client = TestClient(test_app)
        
        print("=== 测试简化应用 ===")
        
        # 测试DELETE
        response = client.delete("/api/instances/test123")
        print(f"简化DELETE: {response.status_code} - {response.json()}")
        
        # 测试PUT
        response = client.put("/api/instances/test123")
        print(f"简化PUT: {response.status_code} - {response.json()}")
        
        # 现在测试实际的应用
        print("\n=== 测试实际应用 ===")
        from wxauto_mgt.web.server import create_app
        
        app = create_app()
        client = TestClient(app)
        
        # 测试DELETE
        response = client.delete("/api/instances/test123")
        print(f"实际DELETE: {response.status_code} - {response.text}")
        
        # 测试PUT
        response = client.put("/api/instances/test123", json={"name": "test", "base_url": "http://test", "api_key": "test"})
        print(f"实际PUT: {response.status_code} - {response.text}")
        
        # 检查路由冲突
        print("\n=== 检查路由冲突 ===")
        
        # 查找所有可能冲突的路由
        conflicting_routes = []
        for route in app.routes:
            if hasattr(route, 'path') and hasattr(route, 'methods'):
                path = route.path
                methods = route.methods
                
                # 检查是否可能与 /api/instances/{instance_id} 冲突
                if '/api/instances' in path and 'DELETE' in methods:
                    conflicting_routes.append((path, methods))
        
        print("可能冲突的DELETE路由:")
        for path, methods in conflicting_routes:
            print(f"  {methods} {path}")
        
        # 尝试修复：重新注册DELETE路由
        print("\n=== 尝试修复 ===")
        
        # 检查当前的API路由器
        from wxauto_mgt.web.api import api_router
        
        print(f"API路由器中的路由数量: {len(api_router.routes)}")
        
        # 查找DELETE路由
        delete_routes = []
        for route in api_router.routes:
            if hasattr(route, 'path') and hasattr(route, 'methods'):
                if '/instances/{instance_id}' in route.path and 'DELETE' in route.methods:
                    delete_routes.append(route)
        
        print(f"找到的DELETE路由数量: {len(delete_routes)}")
        for route in delete_routes:
            print(f"  {route.methods} {route.path} -> {route.endpoint.__name__}")
        
    except Exception as e:
        print(f"❌ 修复失败: {e}")
        print(f"异常详情: {traceback.format_exc()}")

if __name__ == "__main__":
    fix_delete_route()
