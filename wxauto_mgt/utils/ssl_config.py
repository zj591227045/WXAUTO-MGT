#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
SSL配置工具模块

用于确保在打包后的exe文件中SSL功能正常工作
"""

import os
import sys
import ssl
import certifi
from wxauto_mgt.utils.logging import logger


def configure_ssl():
    """配置SSL环境，确保HTTPS连接正常工作"""
    try:
        # 设置SSL证书路径
        cert_path = None
        
        # 首先尝试使用certifi提供的证书
        try:
            cert_path = certifi.where()
            if os.path.exists(cert_path):
                logger.info(f"使用certifi证书: {cert_path}")
            else:
                cert_path = None
        except Exception as e:
            logger.warning(f"无法获取certifi证书路径: {e}")
        
        # 如果certifi证书不可用，尝试查找打包后的证书文件
        if not cert_path:
            # 在exe文件同目录下查找证书文件
            exe_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(__file__)
            possible_cert_paths = [
                os.path.join(exe_dir, 'cacert.pem'),
                os.path.join(exe_dir, 'cert.pem'),
                os.path.join(exe_dir, '_internal', 'cacert.pem'),
                os.path.join(exe_dir, '_internal', 'cert.pem')
            ]
            
            for path in possible_cert_paths:
                if os.path.exists(path):
                    cert_path = path
                    logger.info(f"找到打包后的证书文件: {cert_path}")
                    break
        
        # 设置SSL环境变量
        if cert_path:
            os.environ['SSL_CERT_FILE'] = cert_path
            os.environ['REQUESTS_CA_BUNDLE'] = cert_path
            os.environ['CURL_CA_BUNDLE'] = cert_path
            logger.info(f"SSL证书路径已设置: {cert_path}")
        else:
            logger.warning("未找到SSL证书文件，HTTPS连接可能会失败")
        
        # 创建默认SSL上下文
        try:
            context = ssl.create_default_context()
            if cert_path:
                context.load_verify_locations(cert_path)
            logger.info("SSL上下文创建成功")
            return True
        except Exception as e:
            logger.error(f"创建SSL上下文失败: {e}")
            return False
            
    except Exception as e:
        logger.error(f"配置SSL环境失败: {e}")
        return False


def verify_ssl_setup():
    """验证SSL设置是否正常"""
    try:
        import requests
        
        # 测试HTTPS连接
        test_urls = [
            'https://httpbin.org/get',
            'https://www.google.com',
            'https://api.github.com'
        ]
        
        for url in test_urls:
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    logger.info(f"SSL连接测试成功: {url}")
                    return True
            except Exception as e:
                logger.warning(f"SSL连接测试失败 {url}: {e}")
                continue
        
        logger.error("所有SSL连接测试都失败")
        return False
        
    except Exception as e:
        logger.error(f"SSL验证过程出错: {e}")
        return False


def init_ssl():
    """初始化SSL配置"""
    logger.info("初始化SSL配置...")
    
    # 配置SSL环境
    ssl_configured = configure_ssl()
    
    if ssl_configured:
        # 验证SSL设置
        ssl_verified = verify_ssl_setup()
        if ssl_verified:
            logger.info("SSL配置和验证完成")
            return True
        else:
            logger.warning("SSL配置完成但验证失败")
            return False
    else:
        logger.error("SSL配置失败")
        return False


# 在模块导入时自动初始化SSL
if __name__ != '__main__':
    try:
        init_ssl()
    except Exception as e:
        logger.error(f"自动初始化SSL失败: {e}")
