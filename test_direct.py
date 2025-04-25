#!/usr/bin/env python
"""
使用requests库直接测试API
"""

import requests
import json
import time
import logging

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# API配置
BASE_URL = "http://10.255.0.90:5000"
API_KEY = "test-key-2"

def test_health_api():
    """测试健康检查API"""
    url = f"{BASE_URL}/api/health"
    
    # 设置请求头
    headers = {
        "X-API-Key": API_KEY,
        "Accept": "*/*",
        "User-Agent": "test-script/1.0"
    }
    
    logger.info(f"请求URL: {url}")
    logger.info(f"请求头: {headers}")
    
    try:
        # 发送请求
        response = requests.get(url, headers=headers)
        
        # 打印详细信息
        logger.info(f"状态码: {response.status_code}")
        logger.info(f"响应头: {response.headers}")
        
        # 尝试解析JSON
        try:
            data = response.json()
            logger.info(f"响应数据: {json.dumps(data, indent=2, ensure_ascii=False)}")
        except:
            logger.error(f"非JSON响应: {response.text}")
            
    except Exception as e:
        logger.error(f"请求失败: {str(e)}")

if __name__ == "__main__":
    logger.info("开始测试")
    test_health_api()
    logger.info("测试完成") 