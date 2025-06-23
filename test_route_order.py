#!/usr/bin/env python3
"""
测试路由注册顺序
"""

import sys
import os
import traceback

# 添加项目根目录到Python路径
sys.path.insert(0, '.')

def test_route_order():
    """测试路由注册顺序"""
    try:
        print("=== 测试路由注册顺序 ===")
        
        from wxauto_mgt.web.server import create_app
        from fastapi.testclient import TestClient
        
        app = create_app()
        client = TestClient(app)
        
        print(f"FastAPI应用路由数量: {len(app.routes)}")
        
        # 列出所有路由，按注册顺序
        print("\n=== 所有路由（按注册顺序） ===")
        for i, route in enumerate(app.routes):
            if hasattr(route, 'path') and hasattr(route, 'methods'):
                print(f"{i:2d}. {route.methods} {route.path}")
            elif hasattr(route, 'path'):
                print(f"{i:2d}. [MOUNT] {route.path}")
            else:
                print(f"{i:2d}. [OTHER] {type(route)}")
        
        # 特别关注instances相关的路由
        print("\n=== instances相关路由 ===")
        instances_routes = []
        for i, route in enumerate(app.routes):
            if hasattr(route, 'path') and 'instances' in route.path:
                instances_routes.append((i, route))
                print(f"{i:2d}. {getattr(route, 'methods', ['UNKNOWN'])} {route.path}")
        
        # 测试路由匹配
        print("\n=== 测试路由匹配 ===")
        
        # 测试不同的路径
        test_paths = [
            "/api/instances",
            "/api/instances/",
            "/api/instances/test",
            "/api/instances/test/",
            "/api/instances/wxauto_test",
        ]
        
        for path in test_paths:
            print(f"\n路径: {path}")
            
            # GET
            try:
                response = client.get(path)
                print(f"  GET: {response.status_code}")
            except Exception as e:
                print(f"  GET: 异常 - {e}")
            
            # PUT
            try:
                response = client.put(path, json={"name": "test", "base_url": "http://test", "api_key": "test"})
                print(f"  PUT: {response.status_code}")
            except Exception as e:
                print(f"  PUT: 异常 - {e}")
            
            # DELETE
            try:
                response = client.delete(path)
                print(f"  DELETE: {response.status_code}")
            except Exception as e:
                print(f"  DELETE: 异常 - {e}")
        
        # 检查路由匹配器
        print("\n=== 检查路由匹配器 ===")
        from starlette.routing import Match
        
        # 手动测试路由匹配
        test_scope = {
            "type": "http",
            "method": "DELETE",
            "path": "/api/instances/test_instance",
            "query_string": b"",
            "headers": [],
        }
        
        for i, route in enumerate(app.routes):
            if hasattr(route, 'matches'):
                match, child_scope = route.matches(test_scope)
                if match == Match.FULL:
                    print(f"路由 {i} 完全匹配: {getattr(route, 'path', 'unknown')}")
                elif match == Match.PARTIAL:
                    print(f"路由 {i} 部分匹配: {getattr(route, 'path', 'unknown')}")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        print(f"异常详情: {traceback.format_exc()}")

if __name__ == "__main__":
    test_route_order()
