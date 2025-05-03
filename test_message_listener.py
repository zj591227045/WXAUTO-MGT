#!/usr/bin/env python
"""
测试消息监听服务

该脚本用于测试消息监听服务，包括主窗口未读消息检查和监听对象消息检查。
"""

import asyncio
import os
import sys
import logging
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.append(str(project_root))

# 导入必要的模块
from wxauto_mgt.data.db_manager import db_manager
from wxauto_mgt.core.message_listener import MessageListener
from wxauto_mgt.utils.file_logger import file_logger

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    """主函数"""
    logger.info("开始测试消息监听服务")
    
    # 初始化数据库连接
    await db_manager.initialize()
    
    # 创建消息监听服务实例
    listener = MessageListener()
    
    # 启动监听服务
    await listener.start()
    
    # 等待一段时间，让监听服务运行
    logger.info("监听服务已启动，等待10秒...")
    await asyncio.sleep(10)
    
    # 停止监听服务
    await listener.stop()
    
    # 关闭数据库连接
    await db_manager.close()
    
    logger.info("测试完成")

if __name__ == "__main__":
    asyncio.run(main())
