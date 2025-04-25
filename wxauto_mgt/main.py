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
sys.path.append(str(ROOT_DIR))

import qasync
from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow
from app.core.api_client import instance_manager
from app.core.config_manager import config_manager
from app.core.message_listener import message_listener
from app.core.status_monitor import status_monitor
from app.data.db_manager import db_manager
from app.utils.logging import log_manager


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
    
    logger = log_manager.get_logger()
    logger.critical("未捕获的异常", exc_info=(exc_type, exc_value, exc_traceback))


async def init_services():
    """初始化各服务"""
    logger = log_manager.get_logger()
    
    try:
        # 初始化数据库
        logger.info("正在初始化数据库...")
        db_initialized = False
        
        # 确保data目录存在
        data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
        if not os.path.exists(data_dir):
            try:
                os.makedirs(data_dir, exist_ok=True)
                logger.info(f"已创建数据目录: {data_dir}")
            except Exception as e:
                logger.error(f"创建数据目录失败: {str(e)}")
        
        # 设置数据目录权限
        try:
            import stat
            current_mode = os.stat(data_dir).st_mode
            new_mode = current_mode | stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IWGRP
            os.chmod(data_dir, new_mode)
            logger.info(f"已设置数据目录权限: {data_dir}")
            
            # 检查数据库文件权限
            db_file = os.path.join(data_dir, "wxauto_mgt.db")
            if os.path.exists(db_file):
                current_db_mode = os.stat(db_file).st_mode
                new_db_mode = current_db_mode | stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP
                if current_db_mode != new_db_mode:
                    os.chmod(db_file, new_db_mode)
                    logger.info(f"已修正数据库文件权限: {db_file}")
        except Exception as e:
            logger.warning(f"设置目录或文件权限失败: {str(e)}")
        
        # 尝试初始化数据库
        try:
            db_initialized = await db_manager.initialize(recreate_db=False)
        except Exception as e:
            logger.error(f"数据库初始化失败: {str(e)}")
            db_initialized = False
        
        # 如果数据库初始化失败，尝试应急方案
        if not db_initialized:
            logger.warning("数据库初始化失败，尝试应急方案...")
            
            # 尝试备份并重置数据库
            db_file = db_manager._db_path
            if db_file and os.path.exists(db_file):
                # 创建备份
                backup_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "backup")
                os.makedirs(backup_dir, exist_ok=True)
                
                backup_file = os.path.join(backup_dir, f"wxauto_mgt.db.bak.{int(time.time())}")
                try:
                    import shutil
                    shutil.copy2(db_file, backup_file)
                    logger.info(f"已创建数据库备份: {backup_file}")
                    
                    # 不再删除数据库文件，仅尝试再次连接
                    logger.info("尝试重新连接数据库...")
                    
                    # 尝试修复WAL模式文件（可能是因为WAL/SHM文件损坏）
                    wal_file = f"{db_file}-wal"
                    if os.path.exists(wal_file):
                        try:
                            os.remove(wal_file)
                            logger.info(f"已删除可能损坏的WAL文件: {wal_file}")
                        except:
                            pass
                    
                    # 尝试删除SHM文件
                    shm_file = f"{db_file}-shm"
                    if os.path.exists(shm_file):
                        try:
                            os.remove(shm_file)
                            logger.info(f"已删除可能损坏的SHM文件: {shm_file}")
                        except:
                            pass
                    
                    # 再次尝试初始化（不重建数据库）
                    logger.info("尝试重新初始化数据库...")
                    db_initialized = await db_manager.initialize(recreate_db=False)
                    
                    if db_initialized:
                        logger.info("应急方案成功：数据库已重新初始化")
                    else:
                        # 只有在尝试连接现有数据库失败后，才重建数据库
                        logger.warning("连接现有数据库失败，尝试重建数据库...")
                        db_initialized = await db_manager.initialize(recreate_db=True)
                        
                        if db_initialized:
                            logger.info("应急方案成功：数据库已重建并初始化")
                        else:
                            logger.error("应急方案失败：无法初始化数据库")
                            return False
                except Exception as e:
                    logger.error(f"应急方案执行失败: {str(e)}")
                    return False
            else:
                # 尝试创建新的数据库目录和文件
                try:
                    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
                    db_file = os.path.join(data_dir, "wxauto_mgt.db")
                    
                    # 确保目录存在
                    os.makedirs(os.path.dirname(db_file), exist_ok=True)
                    
                    # 设置DB路径
                    db_manager._db_path = db_file
                    
                    # 初始化数据库（创建新文件）
                    logger.info("数据库文件不存在，将创建新数据库...")
                    db_initialized = await db_manager.initialize(recreate_db=True)
                    
                    if db_initialized:
                        logger.info("应急方案成功：已创建并初始化新数据库")
                    else:
                        logger.error("应急方案失败：无法创建新数据库")
                        return False
                except Exception as e:
                    logger.error(f"创建新数据库文件失败: {str(e)}")
                    return False
        
        # 初始化配置管理器
        logger.info("正在初始化配置管理器...")
        await config_manager.initialize()
        
        # 加载实例
        logger.info("正在加载实例...")
        instances = config_manager.get_enabled_instances()
        logger.info(f"从配置管理器中获取到 {len(instances)} 个启用的实例")
        
        if not instances:
            logger.warning("未找到已启用的实例配置，请检查数据库或默认配置")
            # 从配置中检查是否有实例配置但未启用
            all_instances = config_manager.get('instances', [])
            if all_instances:
                logger.info(f"找到 {len(all_instances)} 个实例配置，但可能未启用")
                for inst in all_instances:
                    logger.info(f"实例: {inst.get('name')} ({inst.get('instance_id')}) - 启用状态: {inst.get('enabled', False)}")
        
        for instance in instances:
            instance_id = instance.get("instance_id")
            base_url = instance.get("base_url")
            api_key = instance.get("api_key")
            timeout = instance.get("timeout", 30)
            
            logger.info(f"正在加载实例: {instance_id} ({instance.get('name', '未命名')})")
            instance_manager.add_instance(instance_id, base_url, api_key, timeout)
            logger.info(f"已加载实例: {instance_id}")
        
        # 初始化状态监控
        logger.info("正在初始化状态监控...")
        await status_monitor.start()
        
        # 初始化消息监听
        auto_start = config_manager.get("message_listener.auto_start", False)
        if auto_start:
            logger.info("正在启动消息监听...")
            await message_listener.start()
        
        logger.info("服务初始化完成")
        return True
    except Exception as e:
        logger.error(f"服务初始化失败: {e}")
        return False


async def cleanup_services():
    """清理各服务"""
    logger = log_manager.get_logger()
    
    try:
        # 停止消息监听
        logger.info("正在停止消息监听...")
        await message_listener.stop()
        
        # 停止状态监控
        logger.info("正在停止状态监控...")
        await status_monitor.stop()
        
        # 关闭所有API客户端
        logger.info("正在关闭API客户端...")
        await instance_manager.close_all()
        
        # 关闭数据库连接
        logger.info("正在关闭数据库连接...")
        await db_manager.close()
        
        logger.info("服务清理完成")
        return True
    except Exception as e:
        logger.error(f"服务清理失败: {e}")
        return False


async def main_async():
    """异步主函数"""
    # 设置未捕获异常处理器
    sys.excepthook = handle_exception
    
    # 初始化日志系统
    log_manager.initialize(log_level="DEBUG")
    logger = log_manager.get_logger()
    
    # 创建Qt应用
    app = QApplication(sys.argv)
    app.setApplicationName("WxAuto管理工具")
    
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    
    # 设置信号处理
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(handle_shutdown(app)))
    
    logger.info("WxAuto管理程序启动中...")
    
    try:
        # 初始化服务
        init_success = False
        retry_count = 0
        max_retries = 3
        
        while not init_success and retry_count < max_retries:
            init_success = await init_services()
            if not init_success:
                retry_count += 1
                if retry_count < max_retries:
                    logger.warning(f"初始化服务失败，正在重试 ({retry_count}/{max_retries})...")
                    await asyncio.sleep(1)  # 等待1秒后重试
        
        if not init_success:
            logger.error("初始化服务失败，程序退出")
            return 1
        
        # 创建并显示主窗口
        window = MainWindow()
        window.show()
        
        # 在Qt主循环结束前执行清理任务
        app.aboutToQuit.connect(lambda: asyncio.create_task(cleanup_services()))
        
        # 启动Qt主循环
        logger.info("程序已启动")
        return await loop.run_forever()
    except Exception as e:
        logger.exception(f"程序运行出错: {e}")
        return 1
    finally:
        await cleanup_services()
        log_manager.shutdown()


async def handle_shutdown(app):
    """处理程序关闭"""
    logger = log_manager.get_logger()
    logger.info("正在关闭程序...")
    app.quit()


def main():
    """程序入口点"""
    try:
        # 初始化异步事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # 运行主函数
        return loop.run_until_complete(main_async())
    except Exception as e:
        print(f"程序启动失败: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 