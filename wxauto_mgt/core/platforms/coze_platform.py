"""
扣子(Coze)服务平台实现

该模块实现了扣子(Coze)AI平台的集成，支持：
- 工作空间和智能体管理
- 异步对话处理
- 会话上下文保持
- 动态表单配置
"""

import logging
import json
import time
import asyncio
import aiohttp
from typing import Dict, Any, Optional, List
from .base_platform import ServicePlatform

logger = logging.getLogger(__name__)

# 创建专用的Coze调试日志记录器
coze_debug_logger = logging.getLogger('coze_debug')
coze_debug_logger.setLevel(logging.DEBUG)

# 如果还没有处理器，添加一个
if not coze_debug_logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    coze_debug_logger.addHandler(handler)


class CozeServicePlatform(ServicePlatform):
    """扣子(Coze)服务平台实现"""

    def __init__(self, platform_id: str, name: str, config: Dict[str, Any]):
        """
        初始化扣子平台

        Args:
            platform_id: 平台唯一标识符
            name: 平台显示名称
            config: 平台配置字典，包含：
                - api_key: Coze API密钥
                - workspace_id: 工作空间ID
                - bot_id: 智能体ID
                - continuous_conversation: 是否启用连续对话
                - message_send_mode: 消息发送模式
        """
        super().__init__(platform_id, name, config)
        
        # 基础配置
        self.api_key = config.get('api_key', '')
        self.workspace_id = config.get('workspace_id', '')
        self.bot_id = config.get('bot_id', '')
        self.continuous_conversation = config.get('continuous_conversation', False)
        
        # API端点配置
        self.base_url = "https://api.coze.cn"
        self.workspaces_url = "https://api.coze.cn/v1/workspaces"
        self.bots_url = "https://api.coze.cn/v1/bots"
        
        # 会话管理
        self.conversations = {}  # 用户会话映射 {user_id: conversation_id}
        
        logger.info(f"初始化Coze平台: {name} (ID: {platform_id})")
        coze_debug_logger.info(f"Coze平台配置: workspace_id={self.workspace_id}, bot_id={self.bot_id}, continuous={self.continuous_conversation}")

    async def initialize(self) -> bool:
        """
        初始化平台，验证配置

        Returns:
            bool: 初始化是否成功
        """
        try:
            # 验证基本配置（不进行网络请求）
            if not self.api_key:
                logger.error("Coze平台配置不完整：缺少API密钥")
                self._initialized = False
                return False
                
            if not self.workspace_id:
                logger.error("Coze平台配置不完整：缺少工作空间ID")
                self._initialized = False
                return False
                
            if not self.bot_id:
                logger.error("Coze平台配置不完整：缺少智能体ID")
                self._initialized = False
                return False

            # 不在初始化阶段进行网络请求测试
            # 网络连接测试将在实际使用时或通过test_connection方法进行
            logger.info("Coze平台配置验证完成，跳过网络连接测试")
            coze_debug_logger.info("Coze平台初始化成功")
            self._initialized = True
            return True
            
        except Exception as e:
            logger.error(f"初始化Coze平台失败: {e}")
            coze_debug_logger.error(f"初始化Coze平台失败: {e}")
            self._initialized = False
            return False

    def get_type(self) -> str:
        """
        获取平台类型标识符

        Returns:
            str: 平台类型
        """
        return "coze"

    def _get_headers(self) -> Dict[str, str]:
        """
        获取API请求头

        Returns:
            Dict[str, str]: 请求头
        """
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    async def get_workspaces(self) -> Dict[str, Any]:
        """
        获取工作空间列表

        Returns:
            Dict[str, Any]: 工作空间列表或错误信息
        """
        try:
            coze_debug_logger.info("开始获取工作空间列表")

            headers = self._get_headers()

            async with aiohttp.ClientSession() as session:
                async with session.get(self.workspaces_url, headers=headers) as response:
                    coze_debug_logger.info(f"工作空间API响应状态: {response.status}")

                    if response.status != 200:
                        error_text = await response.text()
                        coze_debug_logger.error(f"获取工作空间失败: {response.status}, {error_text}")
                        return {"error": f"API错误: {response.status}, {error_text[:200]}"}

                    result = await response.json()
                    # 根据新的API响应格式调整数据提取
                    if result.get('code') == 0:
                        workspaces_data = result.get('data', {}).get('workspaces', [])
                        coze_debug_logger.info(f"获取到工作空间数据: {len(workspaces_data)}个工作空间")
                        return {"data": workspaces_data}
                    else:
                        error_msg = result.get('msg', 'Unknown error')
                        coze_debug_logger.error(f"API返回错误: {error_msg}")
                        return {"error": error_msg}
                    
        except Exception as e:
            logger.error(f"获取工作空间列表失败: {e}")
            coze_debug_logger.error(f"获取工作空间列表失败: {e}")
            return {"error": str(e)}

    async def get_bots(self, workspace_id: str) -> Dict[str, Any]:
        """
        获取指定工作空间的智能体列表

        Args:
            workspace_id: 工作空间ID

        Returns:
            Dict[str, Any]: 智能体列表或错误信息
        """
        try:
            coze_debug_logger.info(f"开始获取工作空间 {workspace_id} 的智能体列表")

            headers = self._get_headers()
            params = {"workspace_id": workspace_id}

            async with aiohttp.ClientSession() as session:
                async with session.get(self.bots_url, headers=headers, params=params) as response:
                    coze_debug_logger.info(f"智能体API响应状态: {response.status}")

                    if response.status != 200:
                        error_text = await response.text()
                        coze_debug_logger.error(f"获取智能体失败: {response.status}, {error_text}")
                        return {"error": f"API错误: {response.status}, {error_text[:200]}"}

                    result = await response.json()
                    # 根据新的API响应格式调整数据提取
                    if result.get('code') == 0:
                        bots_data = result.get('data', {}).get('items', [])
                        coze_debug_logger.info(f"获取到智能体数据: {len(bots_data)}个智能体")
                        # 添加调试日志查看数据结构
                        if bots_data:
                            coze_debug_logger.info(f"第一个智能体数据结构: {bots_data[0]}")
                        return {"data": bots_data}
                    else:
                        error_msg = result.get('msg', 'Unknown error')
                        coze_debug_logger.error(f"API返回错误: {error_msg}")
                        return {"error": error_msg}
                    
        except Exception as e:
            logger.error(f"获取智能体列表失败: {e}")
            coze_debug_logger.error(f"获取智能体列表失败: {e}")
            return {"error": str(e)}

    async def test_connection(self) -> Dict[str, Any]:
        """
        测试连接

        Returns:
            Dict[str, Any]: 测试结果
        """
        try:
            coze_debug_logger.info("开始测试Coze平台连接")
            start_time = time.time()
            
            # 测试获取工作空间列表
            workspaces_result = await self.get_workspaces()
            if "error" in workspaces_result:
                return {
                    "success": False,
                    "message": f"连接测试失败: {workspaces_result['error']}",
                    "error": workspaces_result['error']
                }
            
            # 测试获取智能体列表
            if self.workspace_id:
                bots_result = await self.get_bots(self.workspace_id)
                if "error" in bots_result:
                    return {
                        "success": False,
                        "message": f"智能体列表获取失败: {bots_result['error']}",
                        "error": bots_result['error']
                    }
            
            response_time = time.time() - start_time
            coze_debug_logger.info(f"Coze平台连接测试成功，耗时: {response_time:.2f}秒")
            
            return {
                "success": True,
                "message": f"连接测试成功，耗时: {response_time:.2f}秒",
                "data": {
                    "workspaces_count": len(workspaces_result.get('data', [])),
                    "response_time": response_time
                }
            }
            
        except Exception as e:
            logger.error(f"测试Coze平台连接失败: {e}")
            coze_debug_logger.error(f"测试Coze平台连接失败: {e}")
            return {
                "success": False,
                "message": f"连接测试失败: {str(e)}",
                "error": str(e)
            }

    async def create_chat(self, user_id: str, message: str) -> Dict[str, Any]:
        """
        创建对话

        Args:
            user_id: 用户ID
            message: 消息内容

        Returns:
            Dict[str, Any]: 对话创建结果
        """
        try:
            coze_debug_logger.info(f"开始创建对话: user_id={user_id}")

            headers = self._get_headers()

            # 构建请求体
            # 根据 Coze API v3 测试结果：
            # - 当 auto_save_history=false 时，API 要求必须设置 stream 字段，但会导致错误
            # - 当 auto_save_history=true, stream=false 时，API 调用成功
            # 因此我们始终使用 auto_save_history=true 来确保 API 调用成功
            request_body = {
                "bot_id": self.bot_id,
                "user_id": user_id,
                "stream": False,  # 使用非流式输出
                "auto_save_history": True,  # 必须为 true 以避免 API 错误
                "additional_messages": [
                    {
                        "role": "user",
                        "content": message,
                        "content_type": "text"
                    }
                ]
            }

            # 如果启用连续对话且存在历史会话，使用已有的conversation_id
            if self.continuous_conversation and user_id in self.conversations:
                request_body["conversation_id"] = self.conversations[user_id]
                coze_debug_logger.info(f"使用已有会话ID: {self.conversations[user_id]}")

            coze_debug_logger.debug(f"创建对话请求体: {json.dumps(request_body, ensure_ascii=False)}")

            start_time = time.time()

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/v3/chat",
                    headers=headers,
                    json=request_body
                ) as response:
                    response_time = time.time() - start_time
                    coze_debug_logger.info(f"对话创建API响应: 状态码={response.status}, 耗时={response_time:.2f}秒")

                    if response.status != 200:
                        error_text = await response.text()
                        coze_debug_logger.error(f"创建对话失败: {response.status}, {error_text}")
                        return {"error": f"API错误: {response.status}, {error_text[:200]}"}

                    result = await response.json()
                    coze_debug_logger.debug(f"对话创建响应: {json.dumps(result, ensure_ascii=False)}")

                    # 保存会话ID用于连续对话
                    if self.continuous_conversation and "data" in result:
                        conversation_id = result["data"].get("conversation_id")
                        if conversation_id:
                            self.conversations[user_id] = conversation_id
                            coze_debug_logger.info(f"保存会话ID: {conversation_id}")

                    return result

        except Exception as e:
            logger.error(f"创建对话失败: {e}")
            coze_debug_logger.error(f"创建对话失败: {e}")
            return {"error": str(e)}

    async def retrieve_chat(self, conversation_id: str, chat_id: str) -> Dict[str, Any]:
        """
        检查对话状态

        Args:
            conversation_id: 会话ID
            chat_id: 对话ID

        Returns:
            Dict[str, Any]: 对话状态信息
        """
        try:
            coze_debug_logger.info(f"检查对话状态: conversation_id={conversation_id}, chat_id={chat_id}")

            headers = self._get_headers()
            params = {
                "conversation_id": conversation_id,
                "chat_id": chat_id
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/v3/chat/retrieve",
                    headers=headers,
                    params=params
                ) as response:
                    coze_debug_logger.info(f"对话状态API响应: 状态码={response.status}")

                    if response.status != 200:
                        error_text = await response.text()
                        coze_debug_logger.error(f"检查对话状态失败: {response.status}, {error_text}")
                        return {"error": f"API错误: {response.status}, {error_text[:200]}"}

                    result = await response.json()
                    coze_debug_logger.debug(f"对话状态响应: {json.dumps(result, ensure_ascii=False)}")
                    return result

        except Exception as e:
            logger.error(f"检查对话状态失败: {e}")
            coze_debug_logger.error(f"检查对话状态失败: {e}")
            return {"error": str(e)}

    async def get_chat_messages(self, conversation_id: str, chat_id: str) -> Dict[str, Any]:
        """
        获取对话消息列表

        Args:
            conversation_id: 会话ID
            chat_id: 对话ID

        Returns:
            Dict[str, Any]: 消息列表
        """
        try:
            coze_debug_logger.info(f"获取对话消息: conversation_id={conversation_id}, chat_id={chat_id}")

            headers = self._get_headers()
            params = {
                "conversation_id": conversation_id,
                "chat_id": chat_id
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/v3/chat/message/list",
                    headers=headers,
                    params=params
                ) as response:
                    coze_debug_logger.info(f"消息列表API响应: 状态码={response.status}")

                    if response.status != 200:
                        error_text = await response.text()
                        coze_debug_logger.error(f"获取消息列表失败: {response.status}, {error_text}")
                        return {"error": f"API错误: {response.status}, {error_text[:200]}"}

                    result = await response.json()
                    coze_debug_logger.debug(f"消息列表响应: {json.dumps(result, ensure_ascii=False)}")
                    return result

        except Exception as e:
            logger.error(f"获取对话消息失败: {e}")
            coze_debug_logger.error(f"获取对话消息失败: {e}")
            return {"error": str(e)}

    async def process_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理消息

        Args:
            message: 消息数据

        Returns:
            Dict[str, Any]: 处理结果，包含回复内容
        """
        if not self._initialized:
            await self.initialize()
            if not self._initialized:
                return {"error": "平台未初始化"}

        try:
            # 提取消息信息
            content = message.get('content', '')
            sender = message.get('sender', '')
            sender_remark = message.get('sender_remark', '')
            chat_name = message.get('chat_name', '')
            message_id = message.get('id', 'unknown')

            # 使用sender_remark作为用户ID，如果没有则使用sender
            user_id = sender_remark or sender or 'default_user'

            coze_debug_logger.info(f"开始处理消息: ID={message_id}, 用户={user_id}, 内容长度={len(content)}")
            coze_debug_logger.debug(f"消息内容: {content[:100]}{'...' if len(content) > 100 else ''}")

            # 记录并发处理信息
            import threading
            current_thread = threading.current_thread()
            coze_debug_logger.info(f"🔄 并发处理: 线程={current_thread.name}, 消息ID={message_id}")

            # 记录请求开始时间
            start_time = time.time()

            # 1. 创建对话
            coze_debug_logger.info("步骤1: 创建对话")
            chat_result = await self.create_chat(user_id, content)

            if "error" in chat_result:
                coze_debug_logger.error(f"创建对话失败: {chat_result['error']}")
                return {"error": f"创建对话失败: {chat_result['error']}"}

            # 提取对话信息
            chat_data = chat_result.get("data", {})
            conversation_id = chat_data.get("conversation_id")
            chat_id = chat_data.get("id")

            if not conversation_id or not chat_id:
                coze_debug_logger.error(f"对话创建响应缺少必要信息: conversation_id={conversation_id}, chat_id={chat_id}")
                return {"error": "对话创建响应格式错误"}

            coze_debug_logger.info(f"对话创建成功: conversation_id={conversation_id}, chat_id={chat_id}")

            # 2. 轮询对话状态直到完成
            coze_debug_logger.info("步骤2: 开始轮询对话状态")
            max_polls = 60  # 最多轮询60次
            poll_interval = 2  # 每2秒轮询一次

            # 使用指数退避策略优化轮询间隔
            base_interval = 1  # 基础间隔1秒
            max_interval = 5   # 最大间隔5秒

            for poll_count in range(max_polls):
                coze_debug_logger.debug(f"轮询第{poll_count + 1}次")

                # 检查对话状态
                status_result = await self.retrieve_chat(conversation_id, chat_id)

                if "error" in status_result:
                    coze_debug_logger.error(f"检查对话状态失败: {status_result['error']}")
                    return {"error": f"检查对话状态失败: {status_result['error']}"}

                status_data = status_result.get("data", {})
                status = status_data.get("status")

                coze_debug_logger.debug(f"对话状态: {status}")

                if status == "completed":
                    coze_debug_logger.info(f"对话完成，轮询{poll_count + 1}次")
                    break
                elif status == "failed":
                    error_msg = status_data.get("last_error", {}).get("msg", "对话处理失败")
                    coze_debug_logger.error(f"对话处理失败: {error_msg}")
                    return {"error": f"对话处理失败: {error_msg}"}
                elif status in ["created", "in_progress"]:
                    # 使用动态间隔：前几次快速轮询，后面逐渐增加间隔
                    if poll_count < 3:
                        # 前3次快速轮询（1秒间隔）
                        current_interval = base_interval
                    else:
                        # 后续使用指数退避，但不超过最大间隔
                        current_interval = min(base_interval * (1.5 ** (poll_count - 2)), max_interval)

                    coze_debug_logger.debug(f"等待 {current_interval:.1f} 秒后继续轮询")
                    await asyncio.sleep(current_interval)
                else:
                    coze_debug_logger.warning(f"未知对话状态: {status}")
                    await asyncio.sleep(poll_interval)
            else:
                # 轮询超时
                coze_debug_logger.error(f"对话处理超时，已轮询{max_polls}次")
                return {"error": "对话处理超时"}

            # 3. 获取对话消息
            coze_debug_logger.info("步骤3: 获取对话消息")
            messages_result = await self.get_chat_messages(conversation_id, chat_id)

            if "error" in messages_result:
                coze_debug_logger.error(f"获取消息失败: {messages_result['error']}")
                return {"error": f"获取消息失败: {messages_result['error']}"}

            # 4. 提取回复内容
            messages_data = messages_result.get("data", [])
            reply_content = ""

            # 查找助手的回复消息
            for msg in messages_data:
                if msg.get("role") == "assistant" and msg.get("type") == "answer":
                    reply_content = msg.get("content", "")
                    break

            if not reply_content:
                coze_debug_logger.warning("未找到助手回复内容")
                return {"error": "未找到助手回复"}

            # 记录处理完成
            total_time = time.time() - start_time
            coze_debug_logger.info(f"消息处理完成: 总耗时={total_time:.2f}秒, 回复长度={len(reply_content)}")
            coze_debug_logger.debug(f"回复内容: {reply_content[:200]}{'...' if len(reply_content) > 200 else ''}")

            return {
                "content": reply_content,
                "conversation_id": conversation_id,
                "chat_id": chat_id,
                "raw_response": {
                    "chat_result": chat_result,
                    "messages_result": messages_result
                }
            }

        except Exception as e:
            logger.error(f"处理消息时出错: {e}")
            coze_debug_logger.error(f"处理消息时出错: {e}")

            # 记录详细错误信息
            import traceback
            error_traceback = traceback.format_exc()
            coze_debug_logger.error(f"详细错误堆栈: {error_traceback}")

            return {"error": str(e)}
