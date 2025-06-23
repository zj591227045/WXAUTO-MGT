#!/usr/bin/env python3
"""
测试API路由注册
"""

import sys
import os
import traceback

# 添加项目根目录到Python路径
sys.path.insert(0, '.')

def test_api_routes():
    """测试API路由注册"""
    try:
        print("=== 测试API路由注册 ===")
        
        # 导入API路由器
        from wxauto_mgt.web.api import api_router
        
        print(f"API路由器类型: {type(api_router)}")
        print(f"API路由器路由数量: {len(api_router.routes)}")
        
        # 列出所有路由
        print("\n=== API路由器中的路由 ===")
        for route in api_router.routes:
            if hasattr(route, 'path') and hasattr(route, 'methods'):
                print(f"{route.methods} {route.path} -> {route.endpoint.__name__ if hasattr(route, 'endpoint') else 'unknown'}")
        
        # 检查删除实例路由
        delete_instance_routes = [r for r in api_router.routes 
                                 if hasattr(r, 'path') and '/instances/{instance_id}' in r.path 
                                 and hasattr(r, 'methods') and 'DELETE' in r.methods]
        
        print(f"\n=== 删除实例路由 ===")
        if delete_instance_routes:
            for route in delete_instance_routes:
                print(f"找到删除实例路由: {route.methods} {route.path}")
                print(f"  端点函数: {route.endpoint.__name__ if hasattr(route, 'endpoint') else 'unknown'}")
        else:
            print("❌ 未找到删除实例路由")
        
        # 测试创建FastAPI应用
        print("\n=== 测试创建FastAPI应用 ===")
        from wxauto_mgt.web.server import create_app
        
        app = create_app()
        print(f"FastAPI应用类型: {type(app)}")
        print(f"FastAPI应用路由数量: {len(app.routes)}")
        
        # 检查FastAPI应用中的删除实例路由
        delete_routes_in_app = []
        for route in app.routes:
            if hasattr(route, 'path') and hasattr(route, 'methods'):
                if '/api/instances/{instance_id}' in route.path and 'DELETE' in route.methods:
                    delete_routes_in_app.append(route)
        
        print(f"\n=== FastAPI应用中的删除实例路由 ===")
        if delete_routes_in_app:
            for route in delete_routes_in_app:
                print(f"找到删除实例路由: {route.methods} {route.path}")
        else:
            print("❌ FastAPI应用中未找到删除实例路由")
            
            # 列出所有包含instances的路由
            print("\n=== 所有包含instances的路由 ===")
            for route in app.routes:
                if hasattr(route, 'path') and 'instances' in route.path:
                    methods = getattr(route, 'methods', ['UNKNOWN'])
                    print(f"{methods} {route.path}")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        print(f"异常详情: {traceback.format_exc()}")

if __name__ == "__main__":
    test_api_routes()
