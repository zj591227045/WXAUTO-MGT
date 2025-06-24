#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
SSL模块的PyInstaller hook文件
确保SSL相关模块和文件被正确包含
"""

from PyInstaller.utils.hooks import collect_all, collect_data_files
import os
import sys

# 收集ssl模块的所有内容
datas, binaries, hiddenimports = collect_all('ssl')

# 添加额外的隐藏导入
hiddenimports += [
    '_ssl',
    '_hashlib',
    '_socket',
    'socket',
    'select'
]

# 在Windows上添加SSL DLL文件
if sys.platform == 'win32':
    # 查找SSL DLL文件
    ssl_dlls = []
    
    # 检查conda环境
    if 'CONDA_PREFIX' in os.environ:
        conda_lib = os.path.join(os.environ['CONDA_PREFIX'], 'Library', 'bin')
        for dll_name in ['libssl-3-x64.dll', 'libcrypto-3-x64.dll']:
            dll_path = os.path.join(conda_lib, dll_name)
            if os.path.exists(dll_path):
                ssl_dlls.append((dll_path, '.'))
    
    # 检查Python DLLs目录
    python_dlls = os.path.join(os.path.dirname(sys.executable), 'DLLs')
    for dll_name in ['_ssl.pyd', '_hashlib.pyd']:
        dll_path = os.path.join(python_dlls, dll_name)
        if os.path.exists(dll_path):
            ssl_dlls.append((dll_path, '.'))
    
    binaries.extend(ssl_dlls)
