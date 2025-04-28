"""
消息发送器

该模块负责将消息发送到微信实例，并处理发送失败的情况。
"""

import asyncio
import logging
import time
import json
import aiohttp
import requests
from typing import Dict, Any, Optional, Tuple

from wxauto_mgt.data.db_manager import db_manager
from wxauto_mgt.core.api_client import instance_manager

logger = logging.getLogger(__name__)

class MessageSender:
    """消息发送器"""

    def __init__(self):
        """初始化消息发送器"""
        self._initialized = False
        self._retry_count = 3  # 重试次数
        self._retry_interval = 2  # 重试间隔（秒）

    async def initialize(self):
        """初始化消息发送器"""
        if self._initialized:
            return

        self._initialized = True
        logger.info("消息发送器初始化完成")

    async def send_message(self, instance_id: str, chat_name: str, content: str) -> Tuple[bool, str]:
        """
        发送消息到微信实例

        Args:
            instance_id: 实例ID
            chat_name: 聊天对象名称
            content: 消息内容

        Returns:
            Tuple[bool, str]: (是否成功, 错误信息)
        """
        if not self._initialized:
            return False, "消息发送器未初始化"

        # 获取实例信息
        instance = await db_manager.fetchone(
            "SELECT * FROM instances WHERE instance_id = ?",
            (instance_id,)
        )

        if not instance:
            error_msg = f"找不到实例: {instance_id}"
            logger.error(error_msg)
            return False, error_msg

        # 尝试发送消息
        for attempt in range(self._retry_count):
            try:
                # 直接调用API发送消息
                result = await self._send_via_direct_api(instance, chat_name, content)
                if result[0]:
                    return True, "发送成功"

                # 如果失败，等待一段时间后重试
                logger.warning(f"发送消息失败，将在 {self._retry_interval} 秒后重试 ({attempt+1}/{self._retry_count})")
                await asyncio.sleep(self._retry_interval)
            except Exception as e:
                logger.error(f"发送消息时发生异常: {e}")
                await asyncio.sleep(self._retry_interval)

        return False, f"发送消息失败，已重试 {self._retry_count} 次"

    async def _send_via_api_client(self, api_client, chat_name: str, content: str) -> Tuple[bool, str]:
        """通过API客户端发送消息"""
        try:
            response = await api_client.send_message(chat_name, content)
            if response and response.get("success") == True:
                logger.info(f"通过API客户端发送消息成功: {chat_name}")
                return True, "发送成功"
            else:
                error_msg = f"通过API客户端发送消息失败: {response.get('message', '未知错误')}"
                logger.error(error_msg)
                return False, error_msg
        except Exception as e:
            logger.error(f"通过API客户端发送消息时发生异常: {e}")
            return False, f"API客户端异常: {str(e)}"

    async def _send_via_direct_api(self, instance: Dict, chat_name: str, content: str) -> Tuple[bool, str]:
        """直接调用API发送消息"""
        try:
            base_url = instance.get("base_url", "").rstrip("/")
            api_key = instance.get("api_key", "")

            if not base_url or not api_key:
                return False, "实例配置不完整，缺少base_url或api_key"

            # 构建API请求
            url = f"{base_url}/api/chat-window/message/send-typing"
            headers = {
                "X-API-Key": api_key,
                "Content-Type": "application/json",
                "User-Agent": "PostmanRuntime/7.43.0",
                "Accept": "*/*",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive"
            }
            data = {
                "who": chat_name,
                "message": content,
                "clear": True
            }

            # 使用同步requests库发送请求（在异步函数中使用）
            def send_request():
                try:
                    response = requests.post(url, headers=headers, json=data, timeout=30)
                    return response
                except Exception as e:
                    logger.error(f"同步请求异常: {e}")
                    raise e

            # 在事件循环的线程池中执行同步请求
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, send_request)

            if response.status_code == 200:
                try:
                    result = response.json()
                    if result.get("code") == 0:
                        logger.info(f"直接调用API发送消息成功: {chat_name}")
                        # 添加短暂延迟，避免自己的回复被立即捕获
                        await asyncio.sleep(1)
                        return True, "发送成功"
                    else:
                        error_msg = f"API返回错误: {result.get('message', '未知错误')}"
                        logger.error(error_msg)
                        return False, error_msg
                except Exception as e:
                    error_msg = f"解析响应JSON失败: {e}"
                    logger.error(error_msg)
                    return False, error_msg
            else:
                error_msg = f"POST请求失败，状态码: {response.status_code}"
                try:
                    result = response.text
                    error_msg += f", 响应: {result}"
                except:
                    pass
                logger.error(error_msg)
                return False, f"HTTP错误: {response.status_code}"
        except requests.RequestException as e:
            logger.error(f"HTTP请求异常: {e}")
            return False, f"HTTP请求异常: {str(e)}"
        except Exception as e:
            logger.error(f"直接调用API发送消息时发生异常: {e}")
            return False, f"API调用异常: {str(e)}"

    async def check_instance_status(self, instance_id: str) -> Tuple[bool, str]:
        """
        检查实例状态

        Args:
            instance_id: 实例ID

        Returns:
            Tuple[bool, str]: (是否在线, 状态信息)
        """
        try:
            # 获取实例信息
            instance = await db_manager.fetchone(
                "SELECT * FROM instances WHERE instance_id = ?",
                (instance_id,)
            )

            if not instance:
                return False, f"找不到实例: {instance_id}"

            base_url = instance.get("base_url", "").rstrip("/")
            api_key = instance.get("api_key", "")

            if not base_url or not api_key:
                return False, "实例配置不完整，缺少base_url或api_key"

            # 构建API请求
            url = f"{base_url}/api/health"
            headers = {
                "X-API-Key": api_key,
                "Content-Type": "application/json",
                "User-Agent": "PostmanRuntime/7.43.0",
                "Accept": "*/*",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive"
            }

            # 使用同步requests库发送请求（在异步函数中使用）
            def send_request():
                try:
                    response = requests.get(url, headers=headers, timeout=10)
                    return response
                except Exception as e:
                    logger.error(f"同步请求异常: {e}")
                    raise e

            # 在事件循环的线程池中执行同步请求
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, send_request)

            if response.status_code == 200:
                try:
                    result = response.json()
                    if result.get("code") == 0:
                        wechat_status = result.get("data", {}).get("wechat_status")
                        if wechat_status == "connected":
                            return True, "实例在线"
                        else:
                            return False, f"微信未连接: {wechat_status}"
                    else:
                        return False, f"实例离线: {result.get('message', '未知状态')}"
                except Exception as e:
                    return False, f"解析响应JSON失败: {e}"
            else:
                return False, f"状态检查失败，HTTP状态码: {response.status_code}"
        except Exception as e:
            return False, f"检查实例状态时发生异常: {str(e)}"

# 创建全局实例
message_sender = MessageSender()
