#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
环境设置脚本

用于初始化conda环境并安装WxAuto管理程序所需的依赖项。
"""

import os
import platform
import subprocess
import sys
from pathlib import Path

# 项目需要的conda环境名称
ENV_NAME = "wxauto_mgt"
# Python版本
PYTHON_VERSION = "3.11"

# 项目所需依赖项列表
REQUIRED_PACKAGES = [
    "aiosqlite",            # 异步SQLite
    "cryptography",         # 加密功能
    "aiohttp",              # 异步HTTP客户端
    "pytest",               # 测试框架
    "pytest-asyncio",       # 支持异步测试
    "pytest-qt",            # 支持Qt界面测试
    "PySide6"               # Qt界面库
]

def run_command(command, shell=False):
    """运行系统命令并打印输出"""
    print(f"执行: {command}")
    process = subprocess.Popen(
        command, 
        shell=shell, 
        stdout=subprocess.PIPE, 
        stderr=subprocess.STDOUT,
        universal_newlines=True
    )
    
    # 实时打印输出
    for line in process.stdout:
        print(line.strip())
    
    process.wait()
    return process.returncode

def check_conda():
    """检查是否安装了Conda"""
    try:
        subprocess.run(["conda", "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def create_conda_env():
    """创建或更新conda环境"""
    # 检查环境是否已存在
    result = subprocess.run(
        ["conda", "info", "--envs"], 
        stdout=subprocess.PIPE, 
        universal_newlines=True
    )
    
    if ENV_NAME in result.stdout:
        print(f"环境 {ENV_NAME} 已存在，将更新...")
        cmd = ["conda", "install", "-n", ENV_NAME, f"python={PYTHON_VERSION}", "-y"]
    else:
        print(f"创建新环境 {ENV_NAME}...")
        cmd = ["conda", "create", "-n", ENV_NAME, f"python={PYTHON_VERSION}", "-y"]
    
    return run_command(cmd) == 0

def install_dependencies():
    """安装依赖项"""
    # 确定激活环境的命令
    if platform.system() == "Windows":
        activate_cmd = f"conda activate {ENV_NAME} && "
        shell = True
    else:
        # Linux/MacOS
        activate_cmd = f"source activate {ENV_NAME} && "
        shell = True
    
    # 安装每个依赖项
    success = True
    for package in REQUIRED_PACKAGES:
        cmd = f"{activate_cmd}pip install {package}"
        if run_command(cmd, shell=shell) != 0:
            print(f"警告: 安装 {package} 失败")
            success = False
    
    return success

def main():
    """主函数"""
    print("WxAuto管理程序环境设置")
    print("=" * 50)
    
    # 检查conda是否已安装
    if not check_conda():
        print("错误: 未找到conda。请先安装Anaconda或Miniconda。")
        return False
    
    # 创建conda环境
    if not create_conda_env():
        print("错误: 创建conda环境失败。")
        return False
    
    # 安装依赖项
    if not install_dependencies():
        print("警告: 某些依赖项安装失败，请查看上面的错误信息。")
        return False
    
    print("=" * 50)
    print(f"环境设置完成！使用以下命令激活环境:")
    print(f"  conda activate {ENV_NAME}")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 