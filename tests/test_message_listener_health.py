#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
消息监听器健康检查测试

测试消息监听器的异常处理和健康检查功能
"""

import asyncio
import sys
import os
import time
from pathlib import Path

# 添加项目根目录到Python路径
ROOT_DIR = Path(os.path.dirname(os.path.abspath(__file__))).parent
sys.path.append(str(ROOT_DIR))

from wxauto_mgt.core.message_listener import message_listener
from wxauto_mgt.core.api_client import instance_manager
from wxauto_mgt.data.db_manager import db_manager
from wxauto_mgt.utils.logging import setup_logging, logger

class MockAPIClient:
    """模拟API客户端，用于测试"""
    
    def __init__(self, instance_id: str, should_fail: bool = False):
        self.instance_id = instance_id
        self.initialized = True
        self.should_fail = should_fail
        self.health_check_count = 0
        self.initialize_count = 0
    
    async def initialize(self):
        """模拟初始化"""
        self.initialize_count += 1
        if self.should_fail and self.initialize_count <= 2:
            logger.info(f"模拟API客户端 {self.instance_id} 初始化失败 (第{self.initialize_count}次)")
            return False
        
        logger.info(f"模拟API客户端 {self.instance_id} 初始化成功 (第{self.initialize_count}次)")
        self.initialized = True
        return True
    
    async def health_check(self):
        """模拟健康检查"""
        self.health_check_count += 1
        if self.should_fail and self.health_check_count <= 3:
            logger.info(f"模拟API客户端 {self.instance_id} 健康检查失败 (第{self.health_check_count}次)")
            raise Exception(f"模拟健康检查失败 - 第{self.health_check_count}次")
        
        logger.info(f"模拟API客户端 {self.instance_id} 健康检查成功 (第{self.health_check_count}次)")
        return True
    
    async def get_unread_messages(self, **kwargs):
        """模拟获取未读消息"""
        if self.should_fail:
            raise Exception("模拟获取未读消息失败")
        return []
    
    async def get_listener_messages(self, who):
        """模拟获取监听对象消息"""
        if self.should_fail:
            raise Exception("模拟获取监听对象消息失败")
        return []

class MessageListenerHealthTester:
    """消息监听器健康检查测试类"""
    
    def __init__(self):
        self.test_results = []
    
    async def test_api_client_health_check(self):
        """测试API客户端健康检查"""
        logger.info("开始测试API客户端健康检查")
        
        # 创建正常的模拟客户端
        normal_client = MockAPIClient("test_normal", should_fail=False)
        
        # 测试正常客户端的健康检查
        health_result = await message_listener._check_api_client_health("test_normal", normal_client)
        
        if health_result:
            logger.info("✓ 正常API客户端健康检查测试通过")
            self.test_results.append("正常API客户端健康检查: PASS")
        else:
            logger.error("✗ 正常API客户端健康检查测试失败")
            self.test_results.append("正常API客户端健康检查: FAIL")
        
        # 创建有问题的模拟客户端
        failing_client = MockAPIClient("test_failing", should_fail=True)
        
        # 测试有问题客户端的健康检查和恢复
        health_result = await message_listener._check_api_client_health("test_failing", failing_client)
        
        # 第一次应该失败，但经过重试后应该成功
        if health_result and failing_client.initialize_count > 1:
            logger.info("✓ 故障API客户端健康检查和恢复测试通过")
            self.test_results.append("故障API客户端健康检查和恢复: PASS")
        else:
            logger.error("✗ 故障API客户端健康检查和恢复测试失败")
            self.test_results.append("故障API客户端健康检查和恢复: FAIL")
    
    async def test_config_change_handling(self):
        """测试配置变更处理"""
        logger.info("开始测试配置变更处理")
        
        # 检查消息监听器是否正确注册了配置变更监听
        if hasattr(message_listener, '_config_listeners_registered'):
            if message_listener._config_listeners_registered:
                logger.info("✓ 配置变更监听器注册测试通过")
                self.test_results.append("配置变更监听器注册: PASS")
            else:
                logger.warning("配置变更监听器未注册")
                self.test_results.append("配置变更监听器注册: FAIL")
        else:
            logger.warning("消息监听器缺少配置监听标志")
            self.test_results.append("配置变更监听器注册: FAIL")
        
        # 测试配置重新加载方法
        try:
            await message_listener._reload_config_cache()
            logger.info("✓ 配置缓存重新加载测试通过")
            self.test_results.append("配置缓存重新加载: PASS")
        except Exception as e:
            logger.error(f"✗ 配置缓存重新加载测试失败: {e}")
            self.test_results.append("配置缓存重新加载: FAIL")
    
    async def test_service_robustness(self):
        """测试服务健壮性"""
        logger.info("开始测试服务健壮性")
        
        # 检查消息监听器是否正在运行
        if message_listener.running:
            logger.info("✓ 消息监听器运行状态检查通过")
            self.test_results.append("消息监听器运行状态: PASS")
        else:
            logger.warning("消息监听器未运行")
            self.test_results.append("消息监听器运行状态: FAIL")
        
        # 检查任务数量
        if hasattr(message_listener, '_tasks') and len(message_listener._tasks) > 0:
            logger.info(f"✓ 消息监听器任务检查通过，当前有 {len(message_listener._tasks)} 个任务")
            self.test_results.append("消息监听器任务检查: PASS")
        else:
            logger.warning("消息监听器没有运行任务")
            self.test_results.append("消息监听器任务检查: FAIL")
        
        # 测试暂停和恢复功能
        try:
            await message_listener.pause_listening()
            logger.info("消息监听器暂停成功")
            
            await message_listener.resume_listening()
            logger.info("消息监听器恢复成功")
            
            logger.info("✓ 暂停/恢复功能测试通过")
            self.test_results.append("暂停/恢复功能: PASS")
        except Exception as e:
            logger.error(f"✗ 暂停/恢复功能测试失败: {e}")
            self.test_results.append("暂停/恢复功能: FAIL")
    
    async def test_error_handling(self):
        """测试错误处理"""
        logger.info("开始测试错误处理")
        
        # 添加一个故障的模拟实例到实例管理器
        failing_client = MockAPIClient("test_error_handling", should_fail=True)
        instance_manager._instances["test_error_handling"] = failing_client
        
        try:
            # 尝试检查主窗口消息（应该能处理异常）
            await message_listener.check_main_window_messages("test_error_handling", failing_client)
            logger.info("✓ 主窗口消息检查错误处理测试通过")
            self.test_results.append("主窗口消息检查错误处理: PASS")
        except Exception as e:
            logger.error(f"✗ 主窗口消息检查错误处理测试失败: {e}")
            self.test_results.append("主窗口消息检查错误处理: FAIL")
        
        try:
            # 尝试检查监听对象消息（应该能处理异常）
            await message_listener.check_listener_messages("test_error_handling", failing_client)
            logger.info("✓ 监听对象消息检查错误处理测试通过")
            self.test_results.append("监听对象消息检查错误处理: PASS")
        except Exception as e:
            logger.error(f"✗ 监听对象消息检查错误处理测试失败: {e}")
            self.test_results.append("监听对象消息检查错误处理: FAIL")
        
        # 清理测试实例
        if "test_error_handling" in instance_manager._instances:
            del instance_manager._instances["test_error_handling"]
    
    def print_test_results(self):
        """打印测试结果"""
        logger.info("=" * 50)
        logger.info("消息监听器健康检查测试结果:")
        logger.info("=" * 50)
        
        for result in self.test_results:
            logger.info(f"  {result}")
        
        pass_count = sum(1 for result in self.test_results if "PASS" in result)
        total_count = len(self.test_results)
        
        logger.info(f"\n测试通过率: {pass_count}/{total_count} ({pass_count/total_count*100:.1f}%)")
        logger.info("=" * 50)

async def main():
    """主测试函数"""
    # 初始化日志
    log_dir = os.path.join(ROOT_DIR, 'data', 'logs')
    os.makedirs(log_dir, exist_ok=True)
    setup_logging(log_dir, console_level="INFO", file_level="DEBUG")
    
    logger.info("开始消息监听器健康检查测试")
    
    try:
        # 初始化数据库
        db_path = os.path.join(ROOT_DIR, 'data', 'test_health_wxauto_mgt.db')
        await db_manager.initialize(db_path)
        
        # 启动消息监听器
        await message_listener.start()
        
        # 创建测试器并运行测试
        tester = MessageListenerHealthTester()
        
        await tester.test_api_client_health_check()
        await tester.test_config_change_handling()
        await tester.test_service_robustness()
        await tester.test_error_handling()
        
        # 打印测试结果
        tester.print_test_results()
        
        # 停止消息监听器
        await message_listener.stop()
        
        logger.info("消息监听器健康检查测试完成")
        
    except Exception as e:
        logger.error(f"测试过程中出错: {e}")
        logger.exception(e)
    finally:
        # 清理资源
        await db_manager.close()

if __name__ == "__main__":
    asyncio.run(main())
