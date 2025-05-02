"""
WxAuto API客户端模块
使用简单的requests方法实现API调用，支持多实例管理
"""

import logging
import requests
import json
from typing import Dict, List, Optional, Any, Tuple
import aiohttp

logger = logging.getLogger(__name__)

class ApiError(Exception):
    """API错误"""
    def __init__(self, message: str, code: int = -1):
        self.message = message
        self.code = code
        super().__init__(f"API错误 [{code}]: {message}")

class WxAutoApiClient:
    """WxAuto API客户端"""

    def __init__(self, instance_id: str, base_url: str, api_key: str):
        """
        初始化API客户端

        Args:
            instance_id: 实例ID
            base_url: API基础URL
            api_key: API密钥
        """
        self.instance_id = instance_id
        self.base_url = base_url
        self.api_key = api_key
        self._initialized = False
        self._connected = False

    async def _get(self, endpoint: str, params: Dict = None) -> Dict:
        """发送GET请求"""
        try:
            # 将布尔值转换为小写字符串
            if params:
                params = {k: str(v).lower() if isinstance(v, bool) else v
                         for k, v in params.items()}

            # 使用aiohttp发送异步请求
            url = f"{self.base_url}{endpoint}"
            headers = {'X-API-Key': self.api_key}

            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=headers) as response:
                    if response.status != 200:
                        text = await response.text()
                        logger.error(f"GET请求失败，状态码: {response.status}, 响应: {text}")
                        raise ApiError(f"HTTP错误: {response.status}")

                    data = await response.json()

                    if data.get('code') != 0:
                        raise ApiError(data.get('message', '未知错误'), data.get('code', -1))

                    return data.get('data', {})
        except aiohttp.ClientError as e:
            logger.error(f"GET请求网络错误: {e}")
            raise ApiError(str(e))
        except Exception as e:
            logger.error(f"GET请求失败: {e}")
            raise ApiError(str(e))

    async def _post(self, endpoint: str, json: Dict = None) -> Dict:
        """发送POST请求"""
        try:
            # 构建完整URL和请求头
            url = f"{self.base_url}{endpoint}"
            headers = {
                'X-API-Key': self.api_key,
                'Content-Type': 'application/json'
            }

            # 使用aiohttp发送异步请求
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=json, headers=headers) as response:
                    if response.status != 200:
                        text = await response.text()
                        logger.error(f"POST请求失败，状态码: {response.status}, 响应: {text}")
                        raise ApiError(f"HTTP错误: {response.status}")

                    data = await response.json()

                    # 检查API响应状态码
                    if data.get('code') != 0:
                        logger.error(f"API错误: [{data.get('code', -1)}] {data.get('message', '未知错误')}")
                        raise ApiError(data.get('message', '未知错误'), data.get('code', -1))

                    return data.get('data', {})
        except aiohttp.ClientError as e:
            logger.error(f"POST请求网络错误: {e}")
            raise ApiError(str(e))
        except Exception as e:
            logger.error(f"POST请求失败: {e}")
            raise ApiError(str(e))

    async def initialize(self) -> bool:
        """初始化微信实例"""
        try:
            response = requests.post(
                f"{self.base_url}/api/wechat/initialize",
                headers={'X-API-Key': self.api_key}
            )
            response.raise_for_status()
            data = response.json()
            if data.get('code') != 0:
                raise ApiError(data.get('message', '未知错误'), data.get('code', -1))
            self._initialized = True
            return True
        except Exception as e:
            logger.error(f"初始化失败: {e}")
            return False

    async def get_status(self) -> Dict:
        """获取微信状态"""
        try:
            data = await self._get('/api/wechat/status')
            self._connected = data.get('isOnline', False)
            return data
        except Exception as e:
            logger.error(f"获取状态失败: {e}")
            self._connected = False
            return {}

    async def get_health_info(self) -> Dict:
        """获取服务健康状态信息，包含启动时间和状态"""
        try:
            data = await self._get('/api/health')
            return {
                "status": data.get('status', 'error'),
                "uptime": data.get('uptime', 0),
                "wechat_status": data.get('wechat_status', 'disconnected')
            }
        except Exception as e:
            logger.error(f"获取健康状态信息失败: {e}")
            return {
                "status": "error",
                "uptime": 0,
                "wechat_status": "disconnected"
            }

    async def get_system_metrics(self) -> Dict:
        """
        获取系统资源使用情况

        Returns:
            Dict: 系统资源指标，包括CPU和内存使用率
        """
        try:
            data = await self._get('/api/system/resources')
            cpu_data = data.get('cpu', {})
            memory_data = data.get('memory', {})

            metrics = {
                'cpu_usage': cpu_data.get('usage_percent', 0),
                'memory_usage': memory_data.get('used', 0),  # 使用已用内存量(MB)
                'instance_id': self.instance_id
            }

            logger.debug(f"获取系统资源指标: CPU={metrics['cpu_usage']}%, 内存={metrics['memory_usage']}MB")
            return metrics
        except Exception as e:
            logger.error(f"获取系统资源指标失败: {e}")
            return {
                'cpu_usage': 0,
                'memory_usage': 0,
                'instance_id': self.instance_id
            }

    async def send_message(self, receiver: str, message: str, at_list: List[str] = None) -> Dict:
        """
        发送消息

        Args:
            receiver: 接收者
            message: 消息内容
            at_list: @用户列表

        Returns:
            Dict: 发送结果
        """
        try:
            # 使用requests库直接发送请求，模拟curl方式
            url = f"{self.base_url}/api/chat-window/message/send-typing"
            headers = {
                "X-API-Key": self.api_key,
                "Content-Type": "application/json",
                "User-Agent": "PostmanRuntime/7.43.0",
                "Accept": "*/*",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive"
            }

            data = {
                "who": receiver,
                "message": message,
                "clear": True
            }

            if at_list and len(at_list) > 0:
                data["at_list"] = at_list

            # 使用同步requests库发送请求
            def send_request():
                try:
                    response = requests.post(url, headers=headers, json=data, timeout=30)
                    return response
                except Exception as e:
                    logger.error(f"同步请求异常: {e}")
                    raise e

            # 在事件循环的线程池中执行同步请求
            import asyncio
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, send_request)

            if response.status_code == 200:
                try:
                    result = response.json()
                    if result.get("code") == 0:
                        logger.info(f"发送消息成功: {receiver}")
                        return {"success": True, "message": "发送成功"}
                    else:
                        error_msg = f"API返回错误: {result.get('message', '未知错误')}"
                        logger.error(error_msg)
                        return {"success": False, "message": error_msg}
                except Exception as e:
                    error_msg = f"解析响应JSON失败: {e}"
                    logger.error(error_msg)
                    return {"success": False, "message": error_msg}
            else:
                error_msg = f"POST请求失败，状态码: {response.status_code}"
                try:
                    result = response.text
                    error_msg += f", 响应: {result}"
                except:
                    pass
                logger.error(error_msg)
                return {"success": False, "message": f"HTTP错误: {response.status_code}"}
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            return {"success": False, "message": str(e)}

    async def get_unread_messages(self,
                                save_pic: bool = False,
                                save_video: bool = False,
                                save_file: bool = False,
                                save_voice: bool = False,
                                parse_url: bool = False) -> List[Dict]:
        """获取未读消息"""
        try:
            params = {
                'savePic': str(save_pic).lower(),
                'saveVideo': str(save_video).lower(),
                'saveFile': str(save_file).lower(),
                'saveVoice': str(save_voice).lower(),
                'parseUrl': str(parse_url).lower()
            }
            data = await self._get('/api/message/get-next-new', params=params)
            messages = []
            for chat_name, chat_messages in data.get('messages', {}).items():
                for msg in chat_messages:
                    msg['chat_name'] = chat_name  # 添加聊天名称到消息中
                    messages.append(msg)
            return messages
        except Exception as e:
            logger.error(f"获取未读消息失败: {e}")
            return []

    async def add_listener(self, who: str, **kwargs) -> bool:
        """添加监听对象"""
        try:
            import requests
            import json
            import asyncio

            api_params = {
                'who': who,
                'savepic': kwargs.get('save_pic', False),
                'savevideo': kwargs.get('save_video', False),
                'savefile': kwargs.get('save_file', False),
                'savevoice': kwargs.get('save_voice', False),
                'parseurl': kwargs.get('parse_url', False),
                'exact': kwargs.get('exact', False)
            }

            api_params = {k: v for k, v in api_params.items() if v is not None}

            # 构建完整的API URL和请求头
            url = f"{self.base_url}/api/message/listen/add"
            headers = {
                'X-API-Key': self.api_key,
                'Content-Type': 'application/json'
            }

            # 记录完整的curl命令，方便调试
            curl_cmd = f"""curl -X POST '{url}' \\
  -H 'X-API-Key: {self.api_key}' \\
  -H 'Content-Type: application/json' \\
  -d '{json.dumps(api_params)}'"""
            logger.debug(f"执行API请求，等效curl命令: \n{curl_cmd}")

            # 使用同步requests库发送请求
            def send_request():
                try:
                    response = requests.post(url, headers=headers, json=api_params, timeout=30)
                    return response
                except Exception as e:
                    logger.error(f"同步请求异常: {e}")
                    raise e

            # 在事件循环的线程池中执行同步请求
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, send_request)
            status_code = response.status_code

            if status_code != 200:
                logger.error(f"添加监听对象请求失败，状态码: {status_code}, 响应: {response.text}")
                return False

            # 解析JSON响应
            result = response.json()
            logger.debug(f"添加监听对象API响应: {result}")

            # 检查结果
            success = result.get('code') == 0
            if success:
                logger.info(f"成功添加监听对象 {who}")
                return True
            else:
                logger.error(f"添加监听对象失败，API返回: {result}")
                return False
        except requests.RequestException as e:
            logger.error(f"添加监听对象网络错误: {e}")
            logger.exception(e)
            return False
        except Exception as e:
            logger.error(f"添加监听对象失败: {e}")
            logger.exception(e)
            return False

    async def remove_listener(self, who: str) -> bool:
        """移除监听对象"""
        try:
            import requests
            import json
            import asyncio
            data = {'who': who}

            # 构建完整的API URL和请求头
            url = f"{self.base_url}/api/message/listen/remove"
            headers = {
                'X-API-Key': self.api_key,
                'Content-Type': 'application/json'
            }

            # 记录完整的curl命令，方便调试
            curl_cmd = f"""curl -X POST '{url}' \\
  -H 'X-API-Key: {self.api_key}' \\
  -H 'Content-Type: application/json' \\
  -d '{json.dumps(data)}'"""
            logger.debug(f"执行API请求，等效curl命令: \n{curl_cmd}")

            # 使用同步requests库发送请求
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
            status_code = response.status_code

            if status_code != 200:
                logger.error(f"移除监听对象请求失败，状态码: {status_code}, 响应: {response.text}")
                return False

            # 解析JSON响应
            result = response.json()
            logger.debug(f"移除监听对象API响应: {result}")

            # 检查结果 - API成功时返回data中包含who字段，这表示成功
            success = isinstance(result.get('data'), dict) and 'who' in result.get('data', {})
            if success:
                logger.debug(f"成功移除监听对象 {who}")
                return True
            else:
                logger.error(f"移除监听对象失败，API返回: {result}")
                return False
        except requests.RequestException as e:
            logger.error(f"移除监听对象网络错误: {e}")
            logger.exception(e)
            return False
        except Exception as e:
            logger.error(f"移除监听对象失败: {e}")
            logger.exception(e)
            return False

    async def download_file(self, file_path: str) -> Optional[bytes]:
        """
        下载文件

        Args:
            file_path: 文件路径

        Returns:
            Optional[bytes]: 文件内容，如果下载失败则返回None
        """
        try:
            import requests
            import json
            import asyncio

            # 构建请求数据
            data = {'file_path': file_path}

            # 构建完整的API URL和请求头
            url = f"{self.base_url}/api/file/download"
            headers = {
                'X-API-Key': self.api_key,
                'Content-Type': 'application/json'
            }

            # 记录完整的curl命令，方便调试
            curl_cmd = f"""curl -X POST '{url}' \\
  -H 'X-API-Key: {self.api_key}' \\
  -H 'Content-Type: application/json' \\
  -d '{json.dumps(data)}'"""
            logger.debug(f"执行文件下载API请求，等效curl命令: \n{curl_cmd}")

            # 使用同步requests库发送请求
            def send_request():
                try:
                    response = requests.post(url, headers=headers, json=data, timeout=60)  # 文件下载可能需要更长的超时时间
                    return response
                except Exception as e:
                    logger.error(f"文件下载同步请求异常: {e}")
                    raise e

            # 在事件循环的线程池中执行同步请求
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, send_request)
            status_code = response.status_code

            if status_code != 200:
                # 尝试解析错误信息
                try:
                    error_data = response.json()
                    error_msg = error_data.get('message', '未知错误')
                    error_code = error_data.get('code', -1)
                    error_detail = error_data.get('data', {}).get('error', '')
                    logger.error(f"文件下载失败，状态码: {status_code}, 错误码: {error_code}, 错误信息: {error_msg}, 详情: {error_detail}")
                except:
                    logger.error(f"文件下载失败，状态码: {status_code}, 响应: {response.text[:200]}")
                return None

            # 检查Content-Type
            content_type = response.headers.get('Content-Type', '')
            if 'application/octet-stream' in content_type:
                # 成功获取文件内容
                file_content = response.content
                file_size = len(file_content)
                logger.info(f"成功下载文件: {file_path}, 大小: {file_size} 字节")
                return file_content
            else:
                # 可能是错误响应
                try:
                    error_data = response.json()
                    logger.error(f"文件下载API返回非文件内容: {error_data}")
                except:
                    logger.error(f"文件下载API返回非文件内容且无法解析: {response.text[:200]}")
                return None

        except Exception as e:
            logger.error(f"下载文件失败: {e}")
            logger.exception(e)
            return None

    async def get_listener_messages(self, who: str) -> List[Dict]:
        """获取监听对象的消息"""
        try:
            import requests
            params = {'who': who}

            # 使用requests执行请求，模拟curl方式
            url = f"{self.base_url}/api/message/listen/get"
            headers = {'X-API-Key': self.api_key}

            # 记录完整的curl命令，方便调试
            curl_cmd = f"curl -X GET '{url}?who={who}' -H 'X-API-Key: {self.api_key}'"
            logger.debug(f"执行API请求，等效curl命令: {curl_cmd}")

            # 执行请求
            response = requests.get(url, params=params, headers=headers)
            status_code = response.status_code

            if status_code != 200:
                logger.error(f"获取监听消息请求失败，状态码: {status_code}, 响应: {response.text}")
                return []

            # 解析JSON响应
            data = response.json()
            logger.debug(f"获取消息API响应: {data}")

            # 检查API响应状态码
            if data.get('code') != 0:
                logger.error(f"获取监听消息API错误: [{data.get('code', -1)}] {data.get('message', '未知错误')}")
                return []

            # 获取消息数据
            result_data = data.get('data', {})
            messages_data = result_data.get('messages', {})

            # 处理空消息情况 - 这是正常的，表示没有新消息
            if not messages_data or (isinstance(messages_data, dict) and not messages_data.get(who)):
                logger.debug(f"监听对象[{who}]没有新消息")
                # 返回空列表，但这是正常情况，不是错误
                return []

            # 兼容处理不同响应格式
            # 如果messages是字典，根据who获取对应消息
            if isinstance(messages_data, dict):
                messages = messages_data.get(who, [])
            # 如果messages是列表，直接使用
            elif isinstance(messages_data, list):
                messages = messages_data
            else:
                logger.warning(f"未知的消息数据格式: {type(messages_data)}")
                return []

            if messages:
                logger.info(f"获取到监听对象[{who}]的 {len(messages)} 条消息")
                # 记录每条消息的详细信息，便于调试
                for i, msg in enumerate(messages):
                    original_sender = msg.get('sender', '')
                    original_type = msg.get('type', '')
                    sender = original_sender.lower() if original_sender else ''
                    msg_type = original_type.lower() if original_type else ''
                    logger.info(f"消息[{i+1}]: 原始发送者={original_sender}, 小写={sender}, 原始类型={original_type}, 小写={msg_type}")

                    # 检查是否是Self或time类型的消息，或者类型为self的消息
                    if (sender and sender == 'self') or (msg_type and (msg_type == 'time' or msg_type == 'self')):
                        logger.info(f"API返回了应该过滤的消息: 类型={msg_type}, 发送者={sender}, 内容={msg.get('content', '')[:30]}")

                # 使用统一的消息过滤模块过滤消息
                from wxauto_mgt.core.message_filter import message_filter
                filtered_messages = message_filter.filter_messages(messages, log_prefix="API层")

                if len(messages) != len(filtered_messages):
                    logger.info(f"API层过滤前消息数量: {len(messages)}, 过滤后: {len(filtered_messages)}")

                # 使用过滤后的消息列表
                messages = filtered_messages
            else:
                logger.debug(f"监听对象[{who}]没有新消息")

            return messages
        except requests.RequestException as e:
            logger.error(f"获取监听消息网络错误: {e}")
            logger.exception(e)
            return []
        except Exception as e:
            logger.error(f"获取监听消息失败: {e}")
            logger.exception(e)
            return []

    @property
    def initialized(self) -> bool:
        """是否已初始化"""
        return self._initialized

    @property
    def connected(self) -> bool:
        """是否已连接"""
        return self._connected

class InstanceManager:
    """实例管理器"""

    def __init__(self):
        """初始化实例管理器"""
        self._instances: Dict[str, WxAutoApiClient] = {}

    def add_instance(self, instance_id: str, base_url: str, api_key: str, timeout: int = 30) -> WxAutoApiClient:
        """
        添加新的实例

        Args:
            instance_id: 实例ID
            base_url: API基础URL
            api_key: API密钥
            timeout: 超时时间（秒）

        Returns:
            WxAutoApiClient: API客户端实例
        """
        client = WxAutoApiClient(instance_id, base_url, api_key)
        self._instances[instance_id] = client
        return client

    def get_instance(self, instance_id: str) -> Optional[WxAutoApiClient]:
        """获取指定实例"""
        return self._instances.get(instance_id)

    def remove_instance(self, instance_id: str):
        """移除指定实例"""
        if instance_id in self._instances:
            del self._instances[instance_id]

    def get_all_instances(self) -> Dict[str, WxAutoApiClient]:
        """获取所有实例"""
        return self._instances.copy()

    async def close_all(self):
        """关闭所有实例"""
        self._instances.clear()

# 创建全局实例管理器
instance_manager = InstanceManager()