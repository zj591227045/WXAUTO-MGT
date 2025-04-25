#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
运行测试脚本

首先检查依赖项，然后运行修复后的测试。
"""

import importlib
import os
import subprocess
import sys
from pathlib import Path

# 获取项目根目录
ROOT_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(str(ROOT_DIR))

# 确保测试目录存在
TEST_DIR = ROOT_DIR / "tests"
FIXED_TEST_PATH = ROOT_DIR / "tests" / "core" / "test_config_manager_fix.py"

def check_dependencies():
    """检查所需依赖项"""
    try:
        from scripts.check_dependencies import main as check_deps
        return check_deps()
    except ImportError:
        print("无法导入依赖检查模块，请先运行 python scripts/check_dependencies.py")
        return False

def copy_fix_files():
    """将修复的文件复制到正确位置"""
    import shutil
    try:
        # 备份原始测试文件
        orig_test_path = ROOT_DIR / "tests" / "core" / "test_config_manager.py"
        if orig_test_path.exists():
            backup_path = orig_test_path.with_suffix(".py.bak")
            shutil.copy2(orig_test_path, backup_path)
            print(f"已备份原始测试文件到: {backup_path}")
        
        # 确保tests/core目录存在
        os.makedirs(os.path.dirname(FIXED_TEST_PATH), exist_ok=True)
        
        # 复制修复的测试文件
        fixed_src_path = ROOT_DIR / "tests" / "core" / "test_config_manager_fix.py"
        if fixed_src_path.exists():
            shutil.copy2(fixed_src_path, FIXED_TEST_PATH)
            print(f"已复制修复的测试文件到: {FIXED_TEST_PATH}")
        
        return True
    except Exception as e:
        print(f"复制文件时出错: {e}")
        return False

def apply_env_patch():
    """应用环境变量加载补丁"""
    try:
        patch_file = ROOT_DIR / "app" / "core" / "config_manager_env_patch.py"
        config_manager_file = ROOT_DIR / "app" / "core" / "config_manager.py"
        
        if patch_file.exists() and config_manager_file.exists():
            # 读取补丁文件中的函数
            with open(patch_file, 'r', encoding='utf-8') as f:
                patch_content = f.read()
            
            # 提取补丁函数代码
            import re
            func_pattern = r"def patch_load_from_env\(self.*?return config"
            func_match = re.search(func_pattern, patch_content, re.DOTALL)
            
            if not func_match:
                print("无法从补丁文件中提取函数")
                return False
            
            patch_func = func_match.group()
            
            # 读取配置管理器文件
            with open(config_manager_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 寻找并替换load_from_env函数
            func_pattern = r"def load_from_env\(self.*?return config"
            if re.search(func_pattern, content, re.DOTALL):
                new_content = re.sub(func_pattern, patch_func.replace("patch_load_from_env", "load_from_env"), content, flags=re.DOTALL)
                
                # 备份原始文件
                import shutil
                backup_path = config_manager_file.with_suffix(".py.bak")
                shutil.copy2(config_manager_file, backup_path)
                print(f"已备份原始配置管理器文件到: {backup_path}")
                
                # 写入修改后的文件
                with open(config_manager_file, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                
                print("已应用环境变量加载补丁")
                return True
            else:
                print("无法在配置管理器文件中找到load_from_env函数")
                return False
        else:
            print("补丁文件或配置管理器文件不存在")
            return False
    except Exception as e:
        print(f"应用补丁时出错: {e}")
        return False

def run_tests():
    """运行修复后的测试"""
    print("开始运行测试...")
    try:
        # 运行特定的修复测试
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(FIXED_TEST_PATH), "-v"],
            check=False,
            text=True,
            capture_output=True
        )
        
        print(result.stdout)
        if result.stderr:
            print("错误输出:")
            print(result.stderr)
        
        return result.returncode == 0
    except Exception as e:
        print(f"运行测试时出错: {e}")
        return False

def main():
    """主函数"""
    print("准备运行修复后的测试...")
    
    # 检查依赖项
    if not check_dependencies():
        return False
    
    # 准备修复的测试文件
    if not copy_fix_files():
        print("无法准备测试文件，终止测试")
        return False
    
    # 应用环境变量加载补丁
    if not apply_env_patch():
        print("警告: 未能应用环境变量加载补丁，某些测试可能会失败")
    
    # 运行测试
    return run_tests()

if __name__ == "__main__":
    success = main()
    print("测试" + ("成功" if success else "失败"))
    sys.exit(0 if success else 1) 