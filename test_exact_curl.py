#!/usr/bin/env python
"""
完全模拟CURL请求的Python脚本
"""

import asyncio
import httpx
import json
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
ENDPOINT = "/api/health"

async def test_exact_curl():
    """完全模拟CURL请求测试API"""
    logger.info("===== 完全模拟CURL请求 =====")
    
    # 设置与CURL完全一致的请求头
    headers = {
        "Host": "10.255.0.90:5000",
        "X-API-Key": API_KEY,
        "Accept": "*/*",
        "User-Agent": "curl/8.7.1"  # 设置为与curl相同的值
    }
    
    url = f"{BASE_URL}{ENDPOINT}"
    logger.info(f"请求URL: {url}")
    logger.info(f"请求头: {headers}")
    
    try:
        # 创建httpx客户端但不设置默认头部
        transport = httpx.AsyncHTTPTransport(retries=0)
        async with httpx.AsyncClient(transport=transport, timeout=30.0, headers=None) as client:
            # 使用完全定制的头部发送请求
            response = await client.get(url, headers=headers)
            
            # 打印详细信息
            logger.info(f"状态码: {response.status_code}")
            logger.info(f"响应头: {dict(response.headers)}")
            
            # 尝试解析JSON
            try:
                data = response.json()
                logger.info(f"响应数据: {json.dumps(data, indent=2, ensure_ascii=False)}")
            except:
                logger.error(f"非JSON响应: {response.text}")
                
    except Exception as e:
        logger.error(f"请求失败: {str(e)}")
        logger.exception("详细错误")
        
    logger.info("")

if __name__ == "__main__":
    logger.info("开始测试")
    asyncio.run(test_exact_curl())
    logger.info("测试完成") 