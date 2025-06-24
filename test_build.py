#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试打包配置脚本
"""

import os
import sys
import platform
from pathlib import Path

def test_ssl_detection():
    """测试SSL文件检测"""
    print("测试SSL文件检测...")
    
    ssl_files = []
    binaries = []
    
    try:
        # 添加certifi证书文件
        import certifi
        cert_path = certifi.where()
        if os.path.exists(cert_path):
            ssl_files.append((cert_path, '.'))
            print(f"✓ 找到证书文件: {cert_path}")
    except ImportError:
        print("✗ certifi未安装")
    
    # 检测SSL DLL文件
    if platform.system() == "Windows":
        # 常见的SSL DLL位置
        possible_ssl_paths = []
        
        # 检查conda环境
        if 'CONDA_PREFIX' in os.environ:
            conda_lib = os.path.join(os.environ['CONDA_PREFIX'], 'Library', 'bin')
            possible_ssl_paths.append(conda_lib)
            print(f"检查conda路径: {conda_lib}")
        
        # 检查Python安装目录
        python_dir = os.path.dirname(sys.executable)
        possible_ssl_paths.extend([
            os.path.join(python_dir, 'DLLs'),
            os.path.join(python_dir, 'Library', 'bin'),
            python_dir
        ])
        
        print(f"检查Python路径: {python_dir}")
        
        # 要查找的SSL相关DLL
        ssl_dlls = [
            'libssl-3-x64.dll',
            'libcrypto-3-x64.dll',
            'libssl-1_1-x64.dll',
            'libcrypto-1_1-x64.dll',
            '_ssl.pyd'
        ]
        
        for search_path in possible_ssl_paths:
            if not os.path.exists(search_path):
                print(f"路径不存在: {search_path}")
                continue
                
            print(f"搜索路径: {search_path}")
            for dll_name in ssl_dlls:
                dll_path = os.path.join(search_path, dll_name)
                if os.path.exists(dll_path):
                    if dll_name.endswith('.pyd'):
                        ssl_files.append((dll_path, '.'))
                    else:
                        binaries.append((dll_path, '.'))
                    print(f"✓ 找到SSL文件: {dll_path}")
    
    print(f"\n找到的SSL数据文件: {len(ssl_files)}")
    for src, dst in ssl_files:
        print(f"  {src} -> {dst}")
    
    print(f"\n找到的SSL二进制文件: {len(binaries)}")
    for src, dst in binaries:
        print(f"  {src} -> {dst}")
    
    return ssl_files, binaries

def test_imports():
    """测试关键模块导入"""
    print("\n测试关键模块导入...")
    
    modules = [
        'ssl', '_ssl', 'certifi', 'requests', 'urllib3',
        'cryptography', 'fastapi', 'uvicorn', 'pydantic'
    ]
    
    for module in modules:
        try:
            __import__(module)
            print(f"✓ {module}")
        except ImportError as e:
            print(f"✗ {module}: {e}")

def main():
    """主函数"""
    print("=" * 60)
    print("打包配置测试")
    print("=" * 60)
    
    print(f"Python版本: {sys.version}")
    print(f"平台: {platform.system()} {platform.machine()}")
    print(f"Python路径: {sys.executable}")
    
    if 'CONDA_PREFIX' in os.environ:
        print(f"Conda环境: {os.environ['CONDA_PREFIX']}")
    
    print("\n" + "-" * 60)
    
    # 测试SSL文件检测
    ssl_files, binaries = test_ssl_detection()
    
    # 测试模块导入
    test_imports()
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

if __name__ == "__main__":
    main()
