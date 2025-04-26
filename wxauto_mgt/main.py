#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
WxAuto管理程序入口文件
"""

import asyncio
import os
import signal
import sys
import time
from pathlib import Path

# 添加项目根目录到Python路径
ROOT_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(str(ROOT_DIR.parent))

import qasync
from PySide6.QtWidgets import QApplication
import logging

from wxauto_mgt.ui.main_window import MainWindow
from wxauto_mgt.data.db_manager import db_manager
from wxauto_mgt.data.config_store import config_store
from wxauto_mgt.core.api_client import instance_manager
from wxauto_mgt.core.message_listener import message_listener
from wxauto_mgt.utils.logging import setup_logging, logger

def handle_exception(exc_type, exc_value, exc_traceback):
    """
    处理未捕获的异常
    
    Args:
        exc_type: 异常类型
        exc_value: 异常值
        exc_traceback: 异常追踪
    """
    # 忽略KeyboardInterrupt异常
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    
    # 打印完整的异常信息到控制台
    import traceback
    print("="*80)
    print("发生未捕获的异常:")
    print(f"异常类型: {exc_type.__name__}")
    print(f"异常值: {exc_value}")
    print("-"*80)
    print("异常堆栈:")
    traceback.print_tb(exc_traceback)
    print("="*80)
    
    logger.critical("未捕获的异常", exc_info=(exc_type, exc_value, exc_traceback))

async def init_services():
    """初始化各服务"""
    try:
        # 初始化日志
        log_dir = os.path.join(os.path.dirname(__file__), 'logs')
        setup_logging(log_dir, console_level="DEBUG", file_level="DEBUG")
        
        # 初始化数据库
        db_path = os.path.join(os.path.dirname(__file__), 'data', 'wxauto_mgt.db')
        await db_manager.initialize(db_path)
        
        # 等待一下确保表创建完成
        await asyncio.sleep(0.1)
        
        # 加载实例配置
        logger.info("正在加载实例配置...")
        try:
            # 检查表是否存在
            check_sql = "SELECT name FROM sqlite_master WHERE type='table' AND name='instances'"
            table_exists = await db_manager.fetchone(check_sql)
            
            if not table_exists:
                logger.warning("实例表不存在，可能是首次运行")
                return True
            
            instances = await db_manager.fetchall(
                "SELECT * FROM instances WHERE enabled = 1"
            )
            logger.info(f"从数据库中获取到 {len(instances)} 个实例")
            
            # 初始化实例
            for instance in instances:
                try:
                    instance_id = instance.get("instance_id")
                    if not instance_id:
                        logger.error(f"实例配置错误: 缺少 instance_id")
                        continue
                        
                    base_url = instance.get("base_url")
                    if not base_url:
                        logger.error(f"实例配置错误: {instance_id} 缺少 base_url")
                        continue
                        
                    api_key = instance.get("api_key")
                    timeout = instance.get("timeout", 30)
                    name = instance.get("name", "未命名")
                    
                    logger.info(f"正在加载实例: {instance_id} ({name})")
                    instance_manager.add_instance(instance_id, base_url, api_key, timeout)
                    logger.info(f"已加载实例: {instance_id}")
                except Exception as e:
                    logger.error(f"加载实例失败: {str(e)}")
                    continue
        except Exception as e:
            logger.error(f"获取实例配置失败: {str(e)}")
            return False
        
        # 初始化消息监听
        try:
            auto_start = await config_store.get_config('system', 'message_listener_auto_start', False)
            if auto_start:
                logger.info("正在启动消息监听...")
                await message_listener.start()
        except Exception as e:
            logger.error(f"初始化消息监听失败: {str(e)}")
            # 不中断启动流程
        
        logger.info("服务初始化完成")
        return True
    except Exception as e:
        logger.error(f"服务初始化失败: {str(e)}")
        return False

async def cleanup_services():
    """清理各服务"""
    try:
        # 停止消息监听
        if message_listener:
            logger.info("正在停止消息监听...")
            await message_listener.stop()
        
        # 关闭所有API客户端
        if instance_manager:
            logger.info("正在关闭API客户端...")
            await instance_manager.close_all()
        
        # 关闭数据库连接
        if db_manager:
            logger.info("正在关闭数据库连接...")
            await db_manager.close()
        
        logger.info("服务清理完成")
        return True
    except Exception as e:
        logger.error(f"服务清理失败: {str(e)}")
        return False

def main():
    """主程序入口"""
    try:
        # 设置未捕获异常处理器
        sys.excepthook = handle_exception
        
        # 初始化Qt应用
        app = QApplication.instance()
        if not app:
            app = QApplication(sys.argv)
            app.setApplicationName("WxAuto管理工具")
        
        # 创建事件循环
        loop = qasync.QEventLoop(app)
        asyncio.set_event_loop(loop)
        
        # 初始化服务
        if not loop.run_until_complete(init_services()):
            logger.error("服务初始化失败")
            return 1
            
        # 创建主窗口
        window = MainWindow()
        window.show()
        
        # 设置信号处理
        loop.add_signal_handler(signal.SIGINT, loop.stop)
        
        # 运行事件循环
        with loop:
            logger.info("程序已启动")
            loop.run_forever()
            
        return 0
            
    except Exception as e:
        logger.error(f"程序启动失败: {str(e)}")
        return 1
    finally:
        # 执行清理
        if 'loop' in locals():
            loop.run_until_complete(cleanup_services())

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n程序已终止")
        sys.exit(0)
    except Exception as e:
        print(f"程序启动失败: {e}")
        sys.exit(1) 