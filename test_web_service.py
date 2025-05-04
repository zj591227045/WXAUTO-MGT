"""
测试Web服务启动
"""

import asyncio
import logging
from wxauto_mgt.web import start_web_service, stop_web_service, is_web_service_running, get_web_service_config

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

async def test_web_service():
    """测试Web服务启动和停止"""
    try:
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
        logger.info("正在启动Web服务...")
        success = await start_web_service(config)
        
        if success:
            logger.info("Web服务启动成功")
            logger.info(f"Web服务配置: {get_web_service_config()}")
            logger.info(f"Web服务运行状态: {is_web_service_running()}")
            
            # 等待一段时间
            logger.info("Web服务运行中，10秒后自动停止...")
            await asyncio.sleep(10)
            
            # 停止Web服务
            logger.info("正在停止Web服务...")
            stop_success = await stop_web_service()
            
            if stop_success:
                logger.info("Web服务停止成功")
            else:
                logger.error("Web服务停止失败")
        else:
            logger.error("Web服务启动失败")
    
    except Exception as e:
        logger.error(f"测试Web服务时出错: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(test_web_service())
