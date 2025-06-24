#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
requests模块的PyInstaller hook文件
确保requests相关的SSL功能正常工作
"""

from PyInstaller.utils.hooks import collect_all

# 收集requests模块的所有内容
datas, binaries, hiddenimports = collect_all('requests')

# 添加额外的隐藏导入
hiddenimports += [
    'requests.packages.urllib3',
    'requests.packages.urllib3.util',
    'requests.packages.urllib3.util.ssl_',
    'requests.packages.urllib3.contrib',
    'requests.packages.urllib3.contrib.pyopenssl',
    'requests.adapters',
    'requests.auth',
    'requests.cookies',
    'requests.models',
    'requests.sessions',
    'requests.structures',
    'requests.utils',
    'requests.certs'
]
