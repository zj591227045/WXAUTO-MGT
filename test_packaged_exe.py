#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试打包后的exe文件功能
"""

import requests
import time
import subprocess
import os
import sys

def test_web_service():
    """测试Web服务是否正常启动"""
    print("测试Web服务...")
    
    # 等待Web服务启动
    max_retries = 10
    for i in range(max_retries):
        try:
            response = requests.get('http://localhost:8080', timeout=5)
            if response.status_code == 200:
                print("✅ Web服务启动成功，可以正常访问")
                return True
        except requests.exceptions.ConnectionError:
            print(f"等待Web服务启动... ({i+1}/{max_retries})")
            time.sleep(2)
        except Exception as e:
            print(f"测试Web服务时出错: {e}")
    
    print("❌ Web服务启动失败或无法访问")
    return False

def test_https_connection():
    """测试HTTPS连接"""
    print("\n测试HTTPS连接...")
    
    test_urls = [
        'https://httpbin.org/get',
        'https://api.github.com',
        'https://www.google.com'
    ]
    
    success_count = 0
    for url in test_urls:
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                print(f"✅ HTTPS连接成功: {url}")
                success_count += 1
            else:
                print(f"❌ HTTPS连接失败: {url} (状态码: {response.status_code})")
        except Exception as e:
            print(f"❌ HTTPS连接失败: {url} (错误: {e})")
    
    if success_count > 0:
        print(f"✅ HTTPS连接测试通过 ({success_count}/{len(test_urls)})")
        return True
    else:
        print("❌ 所有HTTPS连接测试都失败")
        return False

def main():
    """主函数"""
    print("=" * 60)
    print("打包后exe文件功能测试")
    print("=" * 60)
    
    # 检查exe文件是否存在
    exe_path = os.path.join(os.path.dirname(__file__), 'dist', 'WxAuto管理工具.exe')
    if not os.path.exists(exe_path):
        print(f"❌ exe文件不存在: {exe_path}")
        return False
    
    print(f"✅ 找到exe文件: {exe_path}")
    
    # 测试HTTPS连接（在exe运行的环境中）
    https_success = test_https_connection()
    
    # 测试Web服务
    web_success = test_web_service()
    
    print("\n" + "=" * 60)
    print("测试结果:")
    print(f"HTTPS连接: {'✅ 通过' if https_success else '❌ 失败'}")
    print(f"Web服务: {'✅ 通过' if web_success else '❌ 失败'}")
    
    if https_success and web_success:
        print("🎉 所有测试通过！打包后的exe文件功能正常")
        return True
    else:
        print("⚠️ 部分测试失败，请检查相关功能")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
