#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
certifi模块的PyInstaller hook文件
确保SSL证书文件被正确包含
"""

from PyInstaller.utils.hooks import collect_data_files
import certifi
import os

# 收集certifi的证书文件
datas = collect_data_files('certifi')

# 确保包含cacert.pem文件
try:
    cert_path = certifi.where()
    if os.path.exists(cert_path):
        datas.append((cert_path, '.'))
except Exception:
    pass
