#!/usr/bin/env python
"""
对比不同的HTTP请求方式
"""

import asyncio
import httpx
import requests
import subprocess
import json
import logging
from typing import Dict, Any

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

def run_curl():
    """使用curl测试API"""
    logger.info("===== CURL测试 =====")
    
    # 构建curl命令
    cmd = [
        "curl",
        "--location",
        f"{BASE_URL}{ENDPOINT}",
        "--header", f"X-API-Key: {API_KEY}",
        "--header", "Accept: */*",
        "--header", "User-Agent: curl-test/1.0",
        "-v"
    ]
    
    # 执行curl命令
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        logger.info(f"CURL状态码: {result.returncode}")
        logger.info(f"CURL输出: {result.stdout}")
        if result.stderr:
            logger.debug(f"CURL错误输出: {result.stderr}")
    except Exception as e:
        logger.error(f"CURL执行失败: {str(e)}")
        
    logger.info("")

def test_requests():
    """使用requests库测试API"""
    logger.info("===== REQUESTS测试 =====")
    
    # 设置请求头
    headers = {
        "X-API-Key": API_KEY,
        "Accept": "*/*",
        "User-Agent": "requests-test/1.0",
        "Content-Type": "application/json",
    }
    
    url = f"{BASE_URL}{ENDPOINT}"
    logger.info(f"请求URL: {url}")
    logger.info(f"请求头: {headers}")
    
    try:
        # 发送请求
        response = requests.get(url, headers=headers)
        
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
        
    logger.info("")

async def test_httpx():
    """使用httpx库测试API"""
    logger.info("===== HTTPX测试 =====")
    
    # 设置请求头
    headers = {
        "X-API-Key": API_KEY,
        "Accept": "*/*",
        "User-Agent": "httpx-test/1.0",
        "Content-Type": "application/json"
    }
    
    url = f"{BASE_URL}{ENDPOINT}"
    logger.info(f"请求URL: {url}")
    logger.info(f"请求头: {headers}")
    
    try:
        # 发送请求
        async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
            response = await client.get(url)
            
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

async def test_httpx_with_session():
    """使用httpx库并保持会话测试API"""
    logger.info("===== HTTPX (保持会话) 测试 =====")
    
    # 设置请求头
    headers = {
        "X-API-Key": API_KEY,
        "Accept": "*/*",
        "User-Agent": "httpx-session-test/1.0",
        "Content-Type": "application/json"
    }
    
    url = f"{BASE_URL}{ENDPOINT}"
    logger.info(f"请求URL: {url}")
    logger.info(f"请求头: {headers}")
    
    try:
        # 创建客户端保持会话
        client = httpx.AsyncClient(headers=headers, timeout=30.0)
        
        try:
            # 发送请求
            response = await client.get(url)
            
            # 打印详细信息
            logger.info(f"状态码: {response.status_code}")
            logger.info(f"响应头: {dict(response.headers)}")
            
            # 尝试解析JSON
            try:
                data = response.json()
                logger.info(f"响应数据: {json.dumps(data, indent=2, ensure_ascii=False)}")
            except:
                logger.error(f"非JSON响应: {response.text}")
        finally:
            # 关闭客户端
            await client.aclose()
                
    except Exception as e:
        logger.error(f"请求失败: {str(e)}")
        logger.exception("详细错误")
        
    logger.info("")

async def test_in_sequence():
    """按顺序测试所有方法"""
    # 运行curl测试
    run_curl()
    
    # 运行requests测试
    test_requests()
    
    # 运行httpx测试
    await test_httpx()
    
    # 运行httpx会话测试
    await test_httpx_with_session()

if __name__ == "__main__":
    logger.info("开始测试")
    asyncio.run(test_in_sequence())
    logger.info("测试完成") 