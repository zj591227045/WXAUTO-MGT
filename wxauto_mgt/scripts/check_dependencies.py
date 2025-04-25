#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
依赖项检查和安装脚本

检查项目所需的Python依赖项，并自动安装缺少的依赖。
"""

import importlib
import os
import subprocess
import sys

# 项目所需依赖项列表
REQUIRED_PACKAGES = [
    "aiosqlite",
    "cryptography",
    "aiohttp",
    "pytest",
    "pytest-asyncio",
    "pytest-qt",
    "PySide6"
]

def check_package(package_name):
    """检查是否已安装指定的包"""
    try:
        importlib.import_module(package_name)
        return True
    except ImportError:
        return False

def install_package(package_name):
    """安装指定的包"""
    try:
        print(f"正在安装 {package_name}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
        return True
    except subprocess.CalledProcessError:
        print(f"安装 {package_name} 失败。请尝试手动安装: pip install {package_name}")
        return False

def main():
    """主函数"""
    print("检查项目依赖项...")
    
    missing_packages = []
    for package in REQUIRED_PACKAGES:
        if not check_package(package):
            missing_packages.append(package)
    
    if not missing_packages:
        print("所有依赖项已安装。")
        return True
    
    print(f"发现 {len(missing_packages)} 个缺少的依赖项: {', '.join(missing_packages)}")
    choice = input("是否要安装缺少的依赖项? (y/n): ")
    
    if choice.lower() != 'y':
        print("操作已取消。您需要手动安装缺少的依赖项: pip install " + " ".join(missing_packages))
        return False
    
    # 安装缺少的依赖项
    installed_count = 0
    for package in missing_packages:
        if install_package(package):
            installed_count += 1
    
    # 打印安装结果
    if installed_count == len(missing_packages):
        print("所有依赖项已成功安装。")
    else:
        print(f"已安装 {installed_count} 个依赖项，{len(missing_packages) - installed_count} 个安装失败。")
        print("请尝试手动安装失败的依赖项。")
    
    return installed_count == len(missing_packages)

if __name__ == "__main__":
    status = main()
    sys.exit(0 if status else 1) 