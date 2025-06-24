#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
配置变更通知集成测试

测试配置变更通知机制是否正常工作
"""

import asyncio
import sys
import os
import time
from pathlib import Path

# 添加项目根目录到Python路径
ROOT_DIR = Path(os.path.dirname(os.path.abspath(__file__))).parent
sys.path.append(str(ROOT_DIR))

from wxauto_mgt.core.config_notifier import config_notifier, ConfigChangeType, ConfigChangeEvent
from wxauto_mgt.core.service_platform_manager import platform_manager, rule_manager
from wxauto_mgt.core.message_listener import message_listener
from wxauto_mgt.data.db_manager import db_manager
from wxauto_mgt.utils.logging import setup_logging, logger

class ConfigNotifierTester:
    """配置通知器测试类"""
    
    def __init__(self):
        self.received_events = []
        self.test_results = []
    
    async def on_config_changed(self, event: ConfigChangeEvent):
        """配置变更事件处理器"""
        self.received_events.append(event)
        logger.info(f"测试收到配置变更事件: {event}")
    
    async def test_platform_notifications(self):
        """测试平台配置变更通知"""
        logger.info("开始测试平台配置变更通知")
        
        # 订阅平台相关事件
        await config_notifier.subscribe(ConfigChangeType.PLATFORM_ADDED, self.on_config_changed)
        await config_notifier.subscribe(ConfigChangeType.PLATFORM_UPDATED, self.on_config_changed)
        await config_notifier.subscribe(ConfigChangeType.PLATFORM_DELETED, self.on_config_changed)
        
        initial_count = len(self.received_events)
        
        # 测试添加平台 - 使用禁用状态避免初始化失败
        platform_id = await platform_manager.register_platform(
            platform_type="dify",
            name="测试平台",
            config={
                "api_key": "test_key",
                "base_url": "http://test.com"
            },
            enabled=False  # 禁用状态，避免初始化
        )
        
        # 等待事件处理
        await asyncio.sleep(0.1)
        
        if len(self.received_events) > initial_count:
            logger.info("✓ 平台添加通知测试通过")
            self.test_results.append("平台添加通知: PASS")
        else:
            logger.error("✗ 平台添加通知测试失败")
            self.test_results.append("平台添加通知: FAIL")
        
        if platform_id:
            # 测试更新平台
            update_count = len(self.received_events)
            await platform_manager.update_platform_simple(
                platform_id=platform_id,
                name="更新后的测试平台",
                config={
                    "api_key": "updated_test_key",
                    "base_url": "http://updated-test.com"
                }
            )
            
            await asyncio.sleep(0.1)
            
            if len(self.received_events) > update_count:
                logger.info("✓ 平台更新通知测试通过")
                self.test_results.append("平台更新通知: PASS")
            else:
                logger.error("✗ 平台更新通知测试失败")
                self.test_results.append("平台更新通知: FAIL")
            
            # 测试删除平台
            delete_count = len(self.received_events)
            await platform_manager.delete_platform_simple(platform_id)
            
            await asyncio.sleep(0.1)
            
            if len(self.received_events) > delete_count:
                logger.info("✓ 平台删除通知测试通过")
                self.test_results.append("平台删除通知: PASS")
            else:
                logger.error("✗ 平台删除通知测试失败")
                self.test_results.append("平台删除通知: FAIL")
    
    async def test_rule_notifications(self):
        """测试规则配置变更通知"""
        logger.info("开始测试规则配置变更通知")
        
        # 订阅规则相关事件
        await config_notifier.subscribe(ConfigChangeType.RULE_ADDED, self.on_config_changed)
        await config_notifier.subscribe(ConfigChangeType.RULE_UPDATED, self.on_config_changed)
        await config_notifier.subscribe(ConfigChangeType.RULE_DELETED, self.on_config_changed)
        
        # 首先创建一个测试平台 - 使用禁用状态避免初始化失败
        platform_id = await platform_manager.register_platform(
            platform_type="dify",
            name="规则测试平台",
            config={
                "api_key": "rule_test_key",
                "base_url": "http://rule-test.com"
            },
            enabled=False  # 禁用状态，避免初始化
        )
        
        if not platform_id:
            logger.error("无法创建测试平台，跳过规则测试")
            return
        
        initial_count = len(self.received_events)
        
        # 测试添加规则
        rule_id = await rule_manager.add_rule(
            name="测试规则",
            instance_id="test_instance",
            chat_pattern="测试群",
            platform_id=platform_id,
            priority=1
        )
        
        await asyncio.sleep(0.1)
        
        if len(self.received_events) > initial_count:
            logger.info("✓ 规则添加通知测试通过")
            self.test_results.append("规则添加通知: PASS")
        else:
            logger.error("✗ 规则添加通知测试失败")
            self.test_results.append("规则添加通知: FAIL")
        
        if rule_id:
            # 测试更新规则
            update_count = len(self.received_events)
            await rule_manager.update_rule(
                rule_id=rule_id,
                name="更新后的测试规则",
                instance_id="test_instance",
                chat_pattern="更新后的测试群",
                platform_id=platform_id,
                priority=2
            )
            
            await asyncio.sleep(0.1)
            
            if len(self.received_events) > update_count:
                logger.info("✓ 规则更新通知测试通过")
                self.test_results.append("规则更新通知: PASS")
            else:
                logger.error("✗ 规则更新通知测试失败")
                self.test_results.append("规则更新通知: FAIL")
            
            # 测试删除规则
            delete_count = len(self.received_events)
            await rule_manager.delete_rule(rule_id)
            
            await asyncio.sleep(0.1)
            
            if len(self.received_events) > delete_count:
                logger.info("✓ 规则删除通知测试通过")
                self.test_results.append("规则删除通知: PASS")
            else:
                logger.error("✗ 规则删除通知测试失败")
                self.test_results.append("规则删除通知: FAIL")
        
        # 清理测试平台
        await platform_manager.delete_platform_simple(platform_id)
    
    async def test_message_listener_integration(self):
        """测试消息监听器集成"""
        logger.info("开始测试消息监听器配置变更集成")
        
        # 检查消息监听器是否正确注册了配置变更监听
        if hasattr(message_listener, '_config_listeners_registered'):
            if message_listener._config_listeners_registered:
                logger.info("✓ 消息监听器已注册配置变更监听")
                self.test_results.append("消息监听器配置监听: PASS")
            else:
                logger.warning("消息监听器未注册配置变更监听")
                self.test_results.append("消息监听器配置监听: FAIL")
        else:
            logger.warning("消息监听器缺少配置监听标志")
            self.test_results.append("消息监听器配置监听: FAIL")
    
    def print_test_results(self):
        """打印测试结果"""
        logger.info("=" * 50)
        logger.info("配置变更通知测试结果:")
        logger.info("=" * 50)
        
        for result in self.test_results:
            logger.info(f"  {result}")
        
        logger.info(f"\n总共收到 {len(self.received_events)} 个配置变更事件")
        
        pass_count = sum(1 for result in self.test_results if "PASS" in result)
        total_count = len(self.test_results)
        
        logger.info(f"测试通过率: {pass_count}/{total_count} ({pass_count/total_count*100:.1f}%)")
        logger.info("=" * 50)

async def main():
    """主测试函数"""
    # 初始化日志
    log_dir = os.path.join(ROOT_DIR, 'data', 'logs')
    os.makedirs(log_dir, exist_ok=True)
    setup_logging(log_dir, console_level="INFO", file_level="DEBUG")
    
    logger.info("开始配置变更通知集成测试")
    
    try:
        # 初始化数据库
        db_path = os.path.join(ROOT_DIR, 'data', 'test_wxauto_mgt.db')
        await db_manager.initialize(db_path)
        
        # 初始化管理器
        await platform_manager.initialize()
        await rule_manager.initialize()
        
        # 启动消息监听器（仅用于测试配置监听注册）
        await message_listener.start()
        
        # 创建测试器并运行测试
        tester = ConfigNotifierTester()
        
        await tester.test_platform_notifications()
        await tester.test_rule_notifications()
        await tester.test_message_listener_integration()
        
        # 打印测试结果
        tester.print_test_results()
        
        # 停止消息监听器
        await message_listener.stop()
        
        logger.info("配置变更通知集成测试完成")
        
    except Exception as e:
        logger.error(f"测试过程中出错: {e}")
        logger.exception(e)
    finally:
        # 清理资源
        await db_manager.close()

if __name__ == "__main__":
    asyncio.run(main())
