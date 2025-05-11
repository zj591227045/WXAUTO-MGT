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
from typing import Dict, Any, Optional, Tuple, List

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

    async def send_message(self, instance_id: str, chat_name: str, content: str, message_send_mode: str = None, at_list: List[str] = None) -> Tuple[bool, str]:
        """
        发送消息到微信实例

        Args:
            instance_id: 实例ID
            chat_name: 聊天对象名称
            content: 消息内容
            message_send_mode: 消息发送模式，可选值为"normal"或"typing"，默认为None（使用平台配置）
            at_list: 要@的用户列表，默认为None

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

        # 如果未指定消息发送模式，尝试从消息来源的平台获取
        if message_send_mode is None:
            try:
                # 查询消息对应的平台ID
                message_platform = await db_manager.fetchone(
                    "SELECT platform_id FROM messages WHERE instance_id = ? AND chat_name = ? ORDER BY create_time DESC LIMIT 1",
                    (instance_id, chat_name)
                )

                if message_platform and message_platform.get('platform_id'):
                    platform_id = message_platform.get('platform_id')
                    # 查询平台配置
                    platform_data = await db_manager.fetchone(
                        "SELECT config FROM service_platforms WHERE platform_id = ?",
                        (platform_id,)
                    )

                    if platform_data and platform_data.get('config'):
                        try:
                            config = json.loads(platform_data.get('config'))
                            message_send_mode = config.get('message_send_mode', 'normal')
                            logger.info(f"从平台配置获取消息发送模式: {message_send_mode}")
                        except Exception as e:
                            logger.error(f"解析平台配置失败: {e}")
                            message_send_mode = 'normal'  # 默认使用普通模式
            except Exception as e:
                logger.error(f"获取平台配置失败: {e}")
                message_send_mode = 'normal'  # 默认使用普通模式

        # 如果仍未确定发送模式，使用默认值
        if message_send_mode is None:
            message_send_mode = 'normal'

        logger.info(f"使用消息发送模式: {message_send_mode}")

        # 导入消息监听器，用于暂停/恢复监听
        from wxauto_mgt.core.message_listener import message_listener

        # 尝试发送消息
        for attempt in range(self._retry_count):
            try:
                # 暂停消息监听服务，确保发送消息时不受干扰
                await message_listener.pause_listening()
                logger.info(f"发送消息前暂停监听服务: 实例 {instance_id}, 聊天对象 {chat_name}")

                try:
                    # 直接调用API发送消息
                    result = await self._send_via_direct_api(instance, chat_name, content, message_send_mode, at_list)
                finally:
                    # 恢复消息监听服务
                    await message_listener.resume_listening()
                    logger.info(f"发送消息后恢复监听服务: 实例 {instance_id}, 聊天对象 {chat_name}")

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

    async def _send_via_direct_api(self, instance: Dict, chat_name: str, content: str, message_send_mode: str = "normal", at_list: List[str] = None) -> Tuple[bool, str]:
        """
        直接调用API发送消息

        Args:
            instance: 实例信息
            chat_name: 聊天对象名称
            content: 消息内容
            message_send_mode: 消息发送模式，可选值为"normal"或"typing"，默认为"normal"
            at_list: 要@的用户列表，默认为None

        Returns:
            Tuple[bool, str]: (是否成功, 错误信息)
        """
        try:
            base_url = instance.get("base_url", "").rstrip("/")
            api_key = instance.get("api_key", "")

            if not base_url or not api_key:
                return False, "实例配置不完整，缺少base_url或api_key"

            # 根据消息发送模式选择API端点
            if message_send_mode == "typing":
                url = f"{base_url}/api/chat-window/message/send-typing"
                logger.info(f"使用打字机模式发送消息: {chat_name}")
            else:
                url = f"{base_url}/api/chat-window/message/send"
                logger.info(f"使用普通模式发送消息: {chat_name}")

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

            # 记录完整的请求数据，方便调试
            logger.info(f"发送消息完整数据: URL={url}, 聊天对象={chat_name}, 消息模式={message_send_mode}")
            logger.debug(f"请求头: {headers}")
            logger.debug(f"初始请求体: {data}")

            # 如果有@列表，添加到数据中
            if at_list and len(at_list) > 0:
                data["at_list"] = at_list
                logger.info(f"添加@列表到消息: {at_list}")
                logger.debug(f"添加@列表后的请求体: {data}")
            else:
                logger.info(f"没有@列表，不添加at_list参数")

            # 使用同步requests库发送请求（在异步函数中使用）
            def send_request():
                try:
                    logger.info(f"开始发送消息请求: {chat_name}")
                    response = requests.post(url, headers=headers, json=data, timeout=30)
                    logger.info(f"消息请求完成，状态码: {response.status_code}")

                    # 记录响应内容
                    try:
                        response_json = response.json()
                        logger.debug(f"响应内容: {response_json}")
                    except Exception as e:
                        logger.error(f"解析响应JSON失败: {e}")
                        logger.debug(f"原始响应内容: {response.text}")

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
