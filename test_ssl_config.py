#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试SSL配置脚本
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'wxauto_mgt'))

def test_ssl_imports():
    """测试SSL相关模块导入"""
    print("测试SSL相关模块导入...")
    
    try:
        import ssl
        print("✓ ssl模块导入成功")
    except ImportError as e:
        print(f"✗ ssl模块导入失败: {e}")
        return False
    
    try:
        import _ssl
        print("✓ _ssl模块导入成功")
    except ImportError as e:
        print(f"✗ _ssl模块导入失败: {e}")
        return False
    
    try:
        import certifi
        cert_path = certifi.where()
        print(f"✓ certifi模块导入成功，证书路径: {cert_path}")
        if os.path.exists(cert_path):
            print("✓ 证书文件存在")
        else:
            print("✗ 证书文件不存在")
            return False
    except ImportError as e:
        print(f"✗ certifi模块导入失败: {e}")
        return False
    
    try:
        import requests
        print("✓ requests模块导入成功")
    except ImportError as e:
        print(f"✗ requests模块导入失败: {e}")
        return False
    
    return True

def test_https_connection():
    """测试HTTPS连接"""
    print("\n测试HTTPS连接...")
    
    try:
        import requests
        
        # 测试简单的HTTPS请求
        response = requests.get('https://httpbin.org/get', timeout=10)
        if response.status_code == 200:
            print("✓ HTTPS连接测试成功")
            return True
        else:
            print(f"✗ HTTPS连接测试失败，状态码: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ HTTPS连接测试失败: {e}")
        return False

def test_ssl_config_module():
    """测试SSL配置模块"""
    print("\n测试SSL配置模块...")
    
    try:
        from wxauto_mgt.utils.ssl_config import configure_ssl, verify_ssl_setup
        
        # 测试配置SSL
        ssl_configured = configure_ssl()
        if ssl_configured:
            print("✓ SSL配置成功")
        else:
            print("✗ SSL配置失败")
            return False
        
        # 测试验证SSL
        ssl_verified = verify_ssl_setup()
        if ssl_verified:
            print("✓ SSL验证成功")
        else:
            print("✗ SSL验证失败")
            return False
        
        return True
    except Exception as e:
        print(f"✗ SSL配置模块测试失败: {e}")
        return False

def main():
    """主函数"""
    print("=" * 60)
    print("SSL配置测试")
    print("=" * 60)
    
    # 测试SSL模块导入
    if not test_ssl_imports():
        print("\n❌ SSL模块导入测试失败")
        return False
    
    # 测试HTTPS连接
    if not test_https_connection():
        print("\n❌ HTTPS连接测试失败")
        return False
    
    # 测试SSL配置模块
    if not test_ssl_config_module():
        print("\n❌ SSL配置模块测试失败")
        return False
    
    print("\n" + "=" * 60)
    print("✅ 所有SSL测试通过！")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
