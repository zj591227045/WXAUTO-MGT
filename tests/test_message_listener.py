#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
消息监听管理器功能测试脚本
测试WxAuto管理系统的消息监听管理器在实际环境中的功能
"""

import asyncio
import logging
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, Set
import json
import time

# 将项目根目录添加到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.api_client import WxAutoApiClient
from app.data.message_store import MessageStore
from app.core.message_listener import MessageListener
from app.utils.logging import setup_logger

# 配置日志
logger = logging.getLogger("message_listener_test")
logger.setLevel(logging.DEBUG)

# 确保日志器有处理器
if not logger.handlers:
    # 添加控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    logger.addHandler(console_handler)
    
    # 添加文件处理器
    log_file = os.path.join('logs', 'message_listener_test.log')
    os.makedirs('logs', exist_ok=True)
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    logger.addHandler(file_handler)

# API配置
API_BASE_URL = "http://10.255.0.90:5000"  # 根据实际环境修改
API_KEY = "test-key-2"                    # 根据实际环境修改

class MessageListenerTester:
    def __init__(self):
        """初始化测试器"""
        logger.info("=== 初始化消息监听测试器 ===")
        logger.debug(f"API配置: 基础URL={API_BASE_URL}, API密钥={API_KEY}")
        
        self.api_client = WxAutoApiClient(API_BASE_URL, API_KEY)
        logger.info(f"已创建API客户端，基础URL: {API_BASE_URL}")
        
        self.message_store = MessageStore()
        logger.info("已初始化消息存储")
        
        self.listener = MessageListener(
            api_client=self.api_client,
            message_store=self.message_store,
            poll_interval=5,           # 5秒轮询间隔
            max_listeners=30,          # 最多30个监听对象
            timeout_minutes=2          # 2分钟超时（测试用）
        )
        logger.info("已创建消息监听管理器")
        logger.debug(f"监听器配置: 轮询间隔={self.listener.poll_interval}秒, "
                    f"最大监听数={self.listener.max_listeners}, "
                    f"超时时间={self.listener.timeout_minutes}分钟")
        
        self.monitored_chats = set()  # 记录已监听的聊天
        self.historical_chats = set()  # 记录历史上监听过的所有聊天
        self.processed_message_ids = set()  # 用于去重
        self.start_time = datetime.now()
        self.iteration_count = 0  # 迭代计数器
        self.message_stats = {
            "total_unread": 0,
            "total_monitored": 0,
            "new_chats_added": 0,
            "timeout_removed": 0
        }
        
    def get_listener_count(self) -> int:
        """获取当前监听器数量"""
        return len(self.listener.listeners) if hasattr(self.listener, 'listeners') else 0
        
    async def run_test(self, duration_minutes: int = 30):
        """
        运行测试
        
        Args:
            duration_minutes: 测试持续时间（分钟）
        """
        logger.info("\n=== 开始消息监听管理器测试 ===")
        logger.info(f"计划测试时长: {duration_minutes}分钟")
        logger.info(f"开始时间: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"预计结束时间: {(self.start_time + timedelta(minutes=duration_minutes)).strftime('%Y-%m-%d %H:%M:%S')}")
        
        try:
            # 初始化微信实例
            logger.info("正在初始化微信实例...")
            init_success = await self.api_client.initialize()
            if not init_success:
                logger.error("初始化微信实例失败")
                return
            logger.info("微信实例初始化成功")
            
            # 启动监听服务
            logger.info("正在启动消息监听服务...")
            await self.listener.start()
            logger.info("消息监听服务已启动")
            
            end_time = datetime.now() + timedelta(minutes=duration_minutes)
            self.iteration_count = 0
            
            while datetime.now() < end_time:
                self.iteration_count += 1
                logger.info(f"\n=== 开始第 {self.iteration_count} 次测试迭代 ===")
                await self._test_iteration()
                
                # 每10次迭代输出一次详细统计
                if self.iteration_count % 10 == 0:
                    await self._print_interim_stats()
                
                await asyncio.sleep(5)  # 每5秒执行一次测试循环
                
        except asyncio.CancelledError:
            logger.warning("测试被取消")
        except Exception as e:
            logger.error(f"测试过程中出现错误: {str(e)}", exc_info=True)
        finally:
            # 停止监听服务
            logger.info("\n正在停止消息监听服务...")
            try:
                await self.listener.stop()
                logger.info("消息监听服务已停止")
            except Exception as e:
                logger.error(f"停止服务时出错: {str(e)}", exc_info=True)
            
        # 输出最终测试统计
        await self._print_test_stats()
    
    async def _test_iteration(self):
        """执行一次测试迭代"""
        current_time = datetime.now()
        elapsed_minutes = (current_time - self.start_time).total_seconds() / 60
        
        logger.info(f"\n--- 测试迭代 [{current_time.strftime('%Y-%m-%d %H:%M:%S')}] ---")
        logger.info(f"已运行时间: {elapsed_minutes:.1f}分钟")
        
        try:
            # 1. 检查主窗口未读消息
            logger.debug("正在获取主窗口未读消息...")
            unread_messages = await self.api_client.get_unread_messages(
                save_pic=True,
                save_video=True,
                save_file=True,
                save_voice=True,
                parse_url=True
            )
            
            if unread_messages:
                self.message_stats["total_unread"] += len(unread_messages)
                logger.info(f"发现 {len(unread_messages)} 条未读消息")
                logger.debug("未读消息详情:")
                for i, msg in enumerate(unread_messages, 1):
                    logger.debug(f"消息 {i}:")
                    logger.debug(f"  - 来源: {msg.get('chat_name', 'Unknown')}")
                    logger.debug(f"  - 类型: {msg.get('type', 'Unknown')}")
                    logger.debug(f"  - 发送者: {msg.get('sender', 'Unknown')} ({msg.get('sender_remark', 'No remark')})")
                    logger.debug(f"  - 内容: {msg.get('content', '')[:100]}...")
                
                for msg in unread_messages:
                    chat_name = msg.get('chat_name')
                    if chat_name and chat_name not in self.monitored_chats:
                        # 添加新的监听对象
                        logger.info(f"尝试添加新的监听对象: {chat_name}")
                        success = await self.listener.add_listener(
                            chat_name,
                            save_pic=True,
                            save_video=True,
                            save_file=True,
                            save_voice=True,
                            parse_url=True
                        )
                        if success:
                            logger.info(f"成功添加新的监听对象: {chat_name}")
                            self.monitored_chats.add(chat_name)
                            # 如果这是一个全新的聊天，添加到历史列表
                            if chat_name not in self.historical_chats:
                                self.historical_chats.add(chat_name)
                                self.message_stats["new_chats_added"] += 1
                            logger.debug(f"历史监听聊天总数更新为: {len(self.historical_chats)}")
                        else:
                            logger.warning(f"添加监听对象失败: {chat_name}")
            else:
                logger.debug("未发现新的未读消息")
            
            # 2. 获取当前监听对象的消息
            listener_count = self.get_listener_count()
            logger.info(f"当前监听对象数量: {listener_count}")
            if listener_count > 0:
                logger.debug("当前监听列表:")
                for i, who in enumerate(self.listener.listeners.keys(), 1):
                    logger.debug(f"  {i}. {who}")
            
            # 3. 获取待处理消息
            pending_messages = await self.listener.get_pending_messages()
            if pending_messages:
                # 使用消息ID做去重，只计数新的消息
                new_message_ids = set()
                found_new_messages_marker = False
                
                for msg in pending_messages:
                    msg_id = msg.get('message_id')
                    content = msg.get('content', '')
                    
                    # 检查是否包含"以下为新消息"标记
                    if isinstance(content, str) and "以下为新消息" in content:
                        found_new_messages_marker = True
                        self.processed_message_ids.add(msg_id)  # 先标记处理标记消息
                        continue  # 跳过这条消息本身
                    
                    # 如果找到标记后才处理后续消息，或者始终没有找到标记则正常处理
                    if (found_new_messages_marker or 
                        not any("以下为新消息" in m.get('content', '') for m in pending_messages)):
                        if msg_id and msg_id not in self.processed_message_ids:
                            new_message_ids.add(msg_id)
                            self.processed_message_ids.add(msg_id)
                
                # 只累加新消息的数量
                new_message_count = len(new_message_ids)
                if new_message_count > 0:
                    self.message_stats["total_monitored"] += new_message_count
                    logger.info(f"待处理消息中有 {new_message_count} 条新消息")
                
                logger.info(f"待处理消息总数: {len(pending_messages)}")
                logger.debug("待处理消息详情:")
                for i, msg in enumerate(pending_messages[:5], 1):  # 只显示前5条
                    logger.debug(f"消息 {i}:")
                    logger.debug(f"  - 来源: {msg.get('chat_name', 'Unknown')}")
                    logger.debug(f"  - 内容: {msg.get('content', '')[:100]}...")
            else:
                logger.debug("当前没有待处理消息")
            
            # 4. 检查并移除超时的监听对象
            logger.debug("开始检查超时的监听对象...")
            # 手动实现超时检查逻辑，因为原始方法可能有问题
            removed_count = 0
            current_time = time.time()
            
            # 获取当前监听对象列表的副本
            listeners_copy = list(self.listener.listeners.items())
            logger.debug(f"当前有 {len(listeners_copy)} 个监听对象")
            
            for who, info in listeners_copy:
                # 检查是否超时 (2分钟无消息则超时)
                time_diff = current_time - info.last_message_time
                timeout_seconds = self.listener.timeout_minutes * 60
                logger.debug(f"监听对象 {who} 最后活动时间: {time_diff:.1f}秒前 (超时阈值: {timeout_seconds}秒)")
                
                if time_diff > timeout_seconds:
                    logger.info(f"监听对象 {who} 已超时 ({time_diff:.1f}秒 > {timeout_seconds}秒)，准备移除")
                    # 确保调用API移除监听对象
                    api_success = await self.api_client.remove_listener(who)
                    if api_success:
                        logger.info(f"成功调用API移除监听对象: {who}")
                    else:
                        logger.warning(f"调用API移除监听对象失败: {who}")
                    
                    # 仍然从内部状态移除
                    await self.listener.remove_listener(who)
                    removed_count += 1
                    # 从我们的跟踪集合中也移除
                    if who in self.monitored_chats:
                        self.monitored_chats.remove(who)
                else:
                    logger.debug(f"监听对象 {who} 未超时 ({time_diff:.1f}秒 <= {timeout_seconds}秒)")
            
            if removed_count > 0:
                self.message_stats["timeout_removed"] += removed_count
                logger.info(f"移除了 {removed_count} 个超时的监听对象")
                # 更新监听列表
                self.monitored_chats = set(self.listener.listeners.keys())
                logger.debug("更新后的监听列表:")
                for who in self.monitored_chats:
                    logger.debug(f"  - {who}")
            else:
                logger.debug("没有发现超时的监听对象")
            
        except Exception as e:
            logger.error(f"测试迭代过程中出错: {str(e)}", exc_info=True)
    
    async def _print_interim_stats(self):
        """打印中期统计信息"""
        logger.info("\n=== 中期统计 ===")
        logger.info(f"当前监听对象数量: {self.get_listener_count()}")
        logger.info(f"累计发现未读消息: {self.message_stats['total_unread']} 条")
        logger.info(f"累计监听到消息: {self.message_stats['total_monitored']} 条")
        logger.info(f"新增监听对象: {self.message_stats['new_chats_added']} 个")
        logger.info(f"超时移除对象: {self.message_stats['timeout_removed']} 个")
    
    async def _print_test_stats(self):
        """打印测试统计信息"""
        end_time = datetime.now()
        total_minutes = (end_time - self.start_time).total_seconds() / 60
        
        logger.info("\n=== 最终测试统计 ===")
        logger.info(f"测试开始时间: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"测试结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"总运行时间: {total_minutes:.1f}分钟")
        
        logger.info("\n消息统计:")
        logger.info(f"- 累计发现未读消息: {self.message_stats['total_unread']} 条")
        logger.info(f"- 累计监听到消息: {self.message_stats['total_monitored']} 条")
        
        logger.info("\n监听对象统计:")
        logger.info(f"- 最终监听对象数量: {self.get_listener_count()}")
        logger.info(f"- 历史监听过的聊天总数: {len(self.historical_chats)}")
        logger.info(f"- 新增监听对象次数: {self.message_stats['new_chats_added']}")
        logger.info(f"- 超时移除对象次数: {self.message_stats['timeout_removed']}")
        
        # 获取消息存储统计
        total_messages = await self.message_store.get_total_message_count()
        processed_messages = await self.message_store.get_processed_message_count()
        
        logger.info("\n消息存储统计:")
        logger.info(f"- 总消息数: {total_messages}")
        logger.info(f"- 已处理消息数: {processed_messages}")
        logger.info(f"- 待处理消息数: {total_messages - processed_messages}")
        if total_messages > 0:
            logger.info(f"- 消息处理率: {(processed_messages/total_messages)*100:.1f}%")
        
        # 记录数据库内容
        logger.info("\n数据库内容:")
        self.message_store.log_database_content()

async def main():
    """主函数"""
    logger.info("\n=== 测试环境配置 ===")
    logger.info(f"API地址: {API_BASE_URL}")
    logger.info(f"API密钥: {API_KEY}")
    
    # 创建并运行测试器
    tester = MessageListenerTester()
    
    try:
        # 运行测试30分钟
        await tester.run_test(duration_minutes=30)
    except KeyboardInterrupt:
        logger.warning("\n收到中断信号，正在停止测试...")
    except Exception as e:
        logger.error(f"测试过程中出现错误: {str(e)}", exc_info=True)
    finally:
        # 确保正确清理资源
        if hasattr(tester, 'listener'):
            await tester.listener.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("程序被用户中断")
    except Exception as e:
        logger.error(f"程序执行出错: {str(e)}", exc_info=True) 