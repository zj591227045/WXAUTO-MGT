#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
urllib3模块的PyInstaller hook文件
确保urllib3的SSL功能正常工作
"""

from PyInstaller.utils.hooks import collect_all

# 收集urllib3模块的所有内容
datas, binaries, hiddenimports = collect_all('urllib3')

# 添加额外的隐藏导入
hiddenimports += [
    'urllib3.util',
    'urllib3.util.ssl_',
    'urllib3.util.connection',
    'urllib3.util.request',
    'urllib3.util.response',
    'urllib3.util.retry',
    'urllib3.util.timeout',
    'urllib3.util.url',
    'urllib3.contrib',
    'urllib3.contrib.pyopenssl',
    'urllib3.contrib.securetransport',
    'urllib3.packages',
    'urllib3.packages.ssl_match_hostname',
    'urllib3.poolmanager',
    'urllib3.connectionpool',
    'urllib3.connection',
    'urllib3.response',
    'urllib3.request',
    'urllib3.fields',
    'urllib3.filepost',
    'urllib3.exceptions'
]
