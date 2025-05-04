"""
Web服务集成示例

展示如何在wxauto_Mgt主程序中集成Web服务。
"""

import asyncio
import logging
from typing import Dict, Any

from wxauto_mgt.web import start_web_service, stop_web_service, is_web_service_running, get_web_service_config, set_web_service_config
from wxauto_mgt.web.websockets.messages import broadcast_message
from wxauto_mgt.web.websockets.status import broadcast_status_update, broadcast_system_metrics

logger = logging.getLogger(__name__)

async def example_start_web_service():
    """启动Web服务示例"""
    # 配置Web服务
    config = {
        "port": 8443,
        "host": "0.0.0.0",
        "debug": True,
        "reload": False,
        "workers": 1,
        "ssl_certfile": None,
        "ssl_keyfile": None,
    }
    
    # 启动Web服务
    success = await start_web_service(config)
    if success:
        logger.info("Web服务启动成功")
    else:
        logger.error("Web服务启动失败")

async def example_stop_web_service():
    """停止Web服务示例"""
    success = await stop_web_service()
    if success:
        logger.info("Web服务停止成功")
    else:
        logger.error("Web服务停止失败")

async def example_broadcast_message():
    """广播消息示例"""
    # 创建消息
    message = {
        "type": "new_message",
        "message_id": "msg123",
        "instance_id": "inst456",
        "chat_name": "测试群",
        "sender": "张三",
        "content": "这是一条测试消息",
        "timestamp": 1625123456
    }
    
    # 广播消息
    await broadcast_message(message)
    logger.info("消息广播成功")

async def example_broadcast_status():
    """广播状态示例"""
    # 创建状态数据
    status = {
        "status": "active",
        "cpu_usage": 25.5,
        "memory_usage": 128.3,
        "last_active": 1625123456
    }
    
    # 广播状态
    await broadcast_status_update("inst456", status)
    logger.info("状态广播成功")

async def example_broadcast_metrics():
    """广播性能指标示例"""
    # 创建性能指标数据
    metrics = {
        "cpu_usage": 35.2,
        "memory_usage": 512.7,
        "disk_usage": 75.8,
        "network_rx": 1024.5,
        "network_tx": 512.3,
        "timestamp": 1625123456
    }
    
    # 广播性能指标
    await broadcast_system_metrics(metrics)
    logger.info("性能指标广播成功")

async def example_integration():
    """集成示例"""
    # 启动Web服务
    await example_start_web_service()
    
    # 等待服务启动
    await asyncio.sleep(2)
    
    # 广播一些数据
    await example_broadcast_message()
    await example_broadcast_status()
    await example_broadcast_metrics()
    
    # 等待一段时间
    logger.info("Web服务运行中，按Ctrl+C停止...")
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("收到停止信号")
    
    # 停止Web服务
    await example_stop_web_service()

if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # 运行示例
    asyncio.run(example_integration())
