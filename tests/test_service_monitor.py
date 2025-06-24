#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
服务监控功能测试

测试服务监控和诊断功能是否正常工作
"""

import asyncio
import sys
import os
import time
import json
from pathlib import Path

# 添加项目根目录到Python路径
ROOT_DIR = Path(os.path.dirname(os.path.abspath(__file__))).parent
sys.path.append(str(ROOT_DIR))

from wxauto_mgt.core.service_monitor import service_monitor
from wxauto_mgt.core.message_listener import message_listener
from wxauto_mgt.api.monitor_api import monitor_api
from wxauto_mgt.data.db_manager import db_manager
from wxauto_mgt.utils.logging import setup_logging, logger

class ServiceMonitorTester:
    """服务监控测试类"""
    
    def __init__(self):
        self.test_results = []
    
    async def test_service_monitor_basic(self):
        """测试服务监控基本功能"""
        logger.info("开始测试服务监控基本功能")
        
        # 测试错误记录
        service_monitor.record_error("test_service", "测试错误消息", "test_error")
        
        # 测试统计记录
        service_monitor.record_message_processed()
        service_monitor.record_api_call()
        service_monitor.record_listener_added()
        service_monitor.record_config_reload()
        
        # 获取统计信息
        stats = service_monitor.get_statistics()
        
        if stats['total_messages_processed'] >= 1:
            logger.info("✓ 消息处理统计测试通过")
            self.test_results.append("消息处理统计: PASS")
        else:
            logger.error("✗ 消息处理统计测试失败")
            self.test_results.append("消息处理统计: FAIL")
        
        if stats['api_calls_made'] >= 1:
            logger.info("✓ API调用统计测试通过")
            self.test_results.append("API调用统计: PASS")
        else:
            logger.error("✗ API调用统计测试失败")
            self.test_results.append("API调用统计: FAIL")
        
        if stats['listeners_added'] >= 1:
            logger.info("✓ 监听对象添加统计测试通过")
            self.test_results.append("监听对象添加统计: PASS")
        else:
            logger.error("✗ 监听对象添加统计测试失败")
            self.test_results.append("监听对象添加统计: FAIL")
        
        if stats['config_reloads'] >= 1:
            logger.info("✓ 配置重新加载统计测试通过")
            self.test_results.append("配置重新加载统计: PASS")
        else:
            logger.error("✗ 配置重新加载统计测试失败")
            self.test_results.append("配置重新加载统计: FAIL")
        
        # 获取最近错误
        recent_errors = service_monitor.get_recent_errors(5)
        
        if len(recent_errors) >= 1:
            logger.info("✓ 错误记录测试通过")
            self.test_results.append("错误记录: PASS")
        else:
            logger.error("✗ 错误记录测试失败")
            self.test_results.append("错误记录: FAIL")
    
    async def test_message_listener_status(self):
        """测试消息监听器状态获取"""
        logger.info("开始测试消息监听器状态获取")
        
        try:
            status = await service_monitor.get_message_listener_status()
            
            if status.service_name == "message_listener":
                logger.info("✓ 服务名称获取测试通过")
                self.test_results.append("服务名称获取: PASS")
            else:
                logger.error("✗ 服务名称获取测试失败")
                self.test_results.append("服务名称获取: FAIL")
            
            if isinstance(status.uptime_seconds, (int, float)) and status.uptime_seconds >= 0:
                logger.info("✓ 运行时间获取测试通过")
                self.test_results.append("运行时间获取: PASS")
            else:
                logger.error("✗ 运行时间获取测试失败")
                self.test_results.append("运行时间获取: FAIL")
            
            if isinstance(status.memory_usage_mb, (int, float)) and status.memory_usage_mb > 0:
                logger.info("✓ 内存使用量获取测试通过")
                self.test_results.append("内存使用量获取: PASS")
            else:
                logger.error("✗ 内存使用量获取测试失败")
                self.test_results.append("内存使用量获取: FAIL")
            
        except Exception as e:
            logger.error(f"✗ 消息监听器状态获取测试失败: {e}")
            self.test_results.append("消息监听器状态获取: FAIL")
    
    async def test_health_report(self):
        """测试健康报告生成"""
        logger.info("开始测试健康报告生成")
        
        try:
            report = await service_monitor.generate_health_report()
            
            if 'health_score' in report:
                logger.info(f"✓ 健康分数生成测试通过，分数: {report['health_score']}")
                self.test_results.append("健康分数生成: PASS")
            else:
                logger.error("✗ 健康分数生成测试失败")
                self.test_results.append("健康分数生成: FAIL")
            
            if 'overall_status' in report:
                logger.info(f"✓ 整体状态生成测试通过，状态: {report['overall_status']}")
                self.test_results.append("整体状态生成: PASS")
            else:
                logger.error("✗ 整体状态生成测试失败")
                self.test_results.append("整体状态生成: FAIL")
            
            if 'message_listener' in report:
                logger.info("✓ 消息监听器状态包含测试通过")
                self.test_results.append("消息监听器状态包含: PASS")
            else:
                logger.error("✗ 消息监听器状态包含测试失败")
                self.test_results.append("消息监听器状态包含: FAIL")
            
        except Exception as e:
            logger.error(f"✗ 健康报告生成测试失败: {e}")
            self.test_results.append("健康报告生成: FAIL")
    
    async def test_monitor_api(self):
        """测试监控API接口"""
        logger.info("开始测试监控API接口")
        
        # 初始化API
        await monitor_api.initialize()
        
        # 测试服务状态API
        try:
            service_status = await monitor_api.get_service_status()
            
            if service_status.get('success'):
                logger.info("✓ 服务状态API测试通过")
                self.test_results.append("服务状态API: PASS")
            else:
                logger.error("✗ 服务状态API测试失败")
                self.test_results.append("服务状态API: FAIL")
        except Exception as e:
            logger.error(f"✗ 服务状态API测试失败: {e}")
            self.test_results.append("服务状态API: FAIL")
        
        # 测试统计信息API
        try:
            statistics = await monitor_api.get_statistics()
            
            if statistics.get('success'):
                logger.info("✓ 统计信息API测试通过")
                self.test_results.append("统计信息API: PASS")
            else:
                logger.error("✗ 统计信息API测试失败")
                self.test_results.append("统计信息API: FAIL")
        except Exception as e:
            logger.error(f"✗ 统计信息API测试失败: {e}")
            self.test_results.append("统计信息API: FAIL")
        
        # 测试错误记录API
        try:
            recent_errors = await monitor_api.get_recent_errors(5)
            
            if recent_errors.get('success'):
                logger.info("✓ 错误记录API测试通过")
                self.test_results.append("错误记录API: PASS")
            else:
                logger.error("✗ 错误记录API测试失败")
                self.test_results.append("错误记录API: FAIL")
        except Exception as e:
            logger.error(f"✗ 错误记录API测试失败: {e}")
            self.test_results.append("错误记录API: FAIL")
        
        # 测试健康报告API
        try:
            health_report = await monitor_api.get_health_report()
            
            if health_report.get('success'):
                logger.info("✓ 健康报告API测试通过")
                self.test_results.append("健康报告API: PASS")
            else:
                logger.error("✗ 健康报告API测试失败")
                self.test_results.append("健康报告API: FAIL")
        except Exception as e:
            logger.error(f"✗ 健康报告API测试失败: {e}")
            self.test_results.append("健康报告API: FAIL")
    
    async def test_monitoring_integration(self):
        """测试监控集成功能"""
        logger.info("开始测试监控集成功能")
        
        # 模拟一些操作来测试监控集成
        initial_stats = service_monitor.get_statistics()
        
        # 模拟错误
        service_monitor.record_error("integration_test", "集成测试错误", "integration")
        
        # 模拟一些统计
        for i in range(3):
            service_monitor.record_message_processed()
            service_monitor.record_api_call()
        
        # 获取更新后的统计
        updated_stats = service_monitor.get_statistics()
        
        # 检查统计是否正确更新
        if updated_stats['total_messages_processed'] > initial_stats['total_messages_processed']:
            logger.info("✓ 消息处理统计集成测试通过")
            self.test_results.append("消息处理统计集成: PASS")
        else:
            logger.error("✗ 消息处理统计集成测试失败")
            self.test_results.append("消息处理统计集成: FAIL")
        
        if updated_stats['api_calls_made'] > initial_stats['api_calls_made']:
            logger.info("✓ API调用统计集成测试通过")
            self.test_results.append("API调用统计集成: PASS")
        else:
            logger.error("✗ API调用统计集成测试失败")
            self.test_results.append("API调用统计集成: FAIL")
    
    def print_test_results(self):
        """打印测试结果"""
        logger.info("=" * 50)
        logger.info("服务监控功能测试结果:")
        logger.info("=" * 50)
        
        for result in self.test_results:
            logger.info(f"  {result}")
        
        pass_count = sum(1 for result in self.test_results if "PASS" in result)
        total_count = len(self.test_results)
        
        logger.info(f"\n测试通过率: {pass_count}/{total_count} ({pass_count/total_count*100:.1f}%)")
        logger.info("=" * 50)
    
    async def generate_sample_report(self):
        """生成示例监控报告"""
        logger.info("生成示例监控报告")
        
        try:
            # 获取完整的健康报告
            health_report = await monitor_api.get_health_report()
            
            # 保存到文件
            report_file = os.path.join(ROOT_DIR, 'data', 'logs', 'health_report_sample.json')
            os.makedirs(os.path.dirname(report_file), exist_ok=True)
            
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(health_report, f, ensure_ascii=False, indent=2)
            
            logger.info(f"示例监控报告已保存到: {report_file}")
            
        except Exception as e:
            logger.error(f"生成示例监控报告失败: {e}")

async def main():
    """主测试函数"""
    # 初始化日志
    log_dir = os.path.join(ROOT_DIR, 'data', 'logs')
    os.makedirs(log_dir, exist_ok=True)
    setup_logging(log_dir, console_level="INFO", file_level="DEBUG")
    
    logger.info("开始服务监控功能测试")
    
    try:
        # 初始化数据库
        db_path = os.path.join(ROOT_DIR, 'data', 'test_monitor_wxauto_mgt.db')
        await db_manager.initialize(db_path)
        
        # 启动消息监听器（用于测试监控功能）
        await message_listener.start()
        
        # 等待一秒让服务稳定
        await asyncio.sleep(1)
        
        # 创建测试器并运行测试
        tester = ServiceMonitorTester()
        
        await tester.test_service_monitor_basic()
        await tester.test_message_listener_status()
        await tester.test_health_report()
        await tester.test_monitor_api()
        await tester.test_monitoring_integration()
        
        # 打印测试结果
        tester.print_test_results()
        
        # 生成示例报告
        await tester.generate_sample_report()
        
        # 停止消息监听器
        await message_listener.stop()
        
        logger.info("服务监控功能测试完成")
        
    except Exception as e:
        logger.error(f"测试过程中出错: {e}")
        logger.exception(e)
    finally:
        # 清理资源
        await db_manager.close()

if __name__ == "__main__":
    asyncio.run(main())
