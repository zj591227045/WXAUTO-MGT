"""
WxAuto API客户端模块
使用简单的requests方法实现API调用，支持多实例管理
"""

import logging
import requests
import json
import asyncio
from typing import Dict, List, Optional, Any, Tuple
import aiohttp

# 导入标准日志记录器
logger = logging.getLogger(__name__)

# 导入文件处理专用日志记录器
from wxauto_mgt.utils import file_logger
from wxauto_mgt.utils.performance_monitor import monitor_performance

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

            # 设置超时时间，避免长时间阻塞UI
            timeout = aiohttp.ClientTimeout(total=3.0, connect=1.0)
            async with aiohttp.ClientSession(timeout=timeout) as session:
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

            # 使用aiohttp发送异步请求，设置超时时间
            timeout = aiohttp.ClientTimeout(total=5.0, connect=1.0)
            async with aiohttp.ClientSession(timeout=timeout) as session:
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

    @monitor_performance("api_initialize")
    async def initialize(self) -> bool:
        """初始化微信实例"""
        try:
            # 使用异步POST请求替代同步requests
            data = await self._post('/api/wechat/initialize')
            self._initialized = True
            return True
        except Exception as e:
            logger.error(f"初始化失败: {e}")
            return False

    @monitor_performance("api_get_status")
    async def get_status(self) -> Dict:
        """获取微信状态"""
        try:
            # 使用较短的超时时间，避免UI阻塞
            data = await asyncio.wait_for(self._get('/api/wechat/status'), timeout=2.0)
            self._connected = data.get('isOnline', False)
            return data
        except asyncio.TimeoutError:
            logger.warning(f"获取微信状态超时: {self.instance_id}")
            self._connected = False
            return {"isOnline": False, "status": "timeout"}
        except Exception as e:
            logger.error(f"获取状态失败: {e}")
            self._connected = False
            return {"isOnline": False, "status": "error"}

    async def get_health_info(self) -> Dict:
        """获取服务健康状态信息，包含启动时间和状态"""
        try:
            # 使用较短的超时时间，避免UI阻塞
            data = await asyncio.wait_for(self._get('/api/health'), timeout=2.0)
            return {
                "status": data.get('status', 'error'),
                "uptime": data.get('uptime', 0),
                "wechat_status": data.get('wechat_status', 'disconnected')
            }
        except asyncio.TimeoutError:
            logger.warning(f"获取健康状态信息超时: {self.instance_id}")
            return {
                "status": "timeout",
                "uptime": 0,
                "wechat_status": "disconnected"
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
            # 使用较短的超时时间，避免UI阻塞
            data = await asyncio.wait_for(self._get('/api/system/resources'), timeout=2.0)
            cpu_data = data.get('cpu', {})
            memory_data = data.get('memory', {})

            metrics = {
                'cpu_usage': cpu_data.get('usage_percent', 0),
                'memory_usage': memory_data.get('used', 0),  # 使用已用内存量(MB)
                'instance_id': self.instance_id
            }

            logger.debug(f"获取系统资源指标: CPU={metrics['cpu_usage']}%, 内存={metrics['memory_usage']}MB")
            return metrics
        except asyncio.TimeoutError:
            logger.warning(f"获取系统资源指标超时: {self.instance_id}")
            return {
                'cpu_usage': 0,
                'memory_usage': 0,
                'instance_id': self.instance_id,
                'status': 'timeout'
            }
        except Exception as e:
            logger.error(f"获取系统资源指标失败: {e}")
            return {
                'cpu_usage': 0,
                'memory_usage': 0,
                'instance_id': self.instance_id,
                'status': 'error'
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
            # 使用正确的API参数名称
            params = {
                'savepic': str(save_pic).lower(),
                'savevideo': str(save_video).lower(),
                'savefile': str(save_file).lower(),
                'savevoice': str(save_voice).lower(),
                'parseurl': str(parse_url).lower()
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

            # 新的API只需要nickname参数，移除其他多余参数
            api_params = {
                'nickname': who
            }

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
            data = {'nickname': who}

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
            import platform
            import os

            file_logger.info(f"开始下载文件，原始路径: {file_path}")
            logger.info(f"开始下载文件: {file_path}")

            # 确保文件路径格式正确（根据操作系统）
            if platform.system() == "Windows":
                # Windows下确保使用反斜杠
                file_path_fixed = file_path.replace('/', '\\')
            else:
                # macOS/Linux下确保使用正斜杠
                file_path_fixed = file_path.replace('\\', '/')

            file_logger.debug(f"修正后的文件路径: {file_path_fixed}")
            file_logger.debug(f"当前操作系统: {platform.system()}")

            # 构建请求数据
            data = {'file_path': file_path_fixed}
            file_logger.debug(f"下载文件请求数据: {data}")

            # 记录文件路径信息，便于调试
            file_logger.debug(f"文件路径详情: 原始={file_path}, 修正后={file_path_fixed}")
            file_logger.debug(f"文件名: {os.path.basename(file_path_fixed)}")

            # 构建完整的API URL和请求头
            url = f"{self.base_url}/api/file/download"
            headers = {
                'X-API-Key': self.api_key,
                'Content-Type': 'application/json'
            }

            file_logger.debug(f"下载文件请求URL: {url}")
            file_logger.debug(f"下载文件请求头: {headers}")

            # 记录完整的curl命令，方便调试
            curl_cmd = f"""curl -X POST '{url}' \\
  -H 'X-API-Key: {self.api_key}' \\
  -H 'Content-Type: application/json' \\
  -d '{json.dumps(data)}'"""
            file_logger.debug(f"执行文件下载API请求，等效curl命令: \n{curl_cmd}")

            # 使用同步requests库发送请求
            def send_request():
                try:
                    file_logger.debug(f"开始发送同步下载请求...")
                    # 增加重试机制
                    max_retries = 3
                    retry_count = 0

                    while retry_count < max_retries:
                        try:
                            response = requests.post(url, headers=headers, json=data, timeout=60)  # 文件下载可能需要更长的超时时间
                            file_logger.debug(f"同步下载请求完成，状态码: {response.status_code}")
                            return response
                        except requests.exceptions.RequestException as e:
                            retry_count += 1
                            file_logger.warning(f"下载请求失败，正在重试 ({retry_count}/{max_retries}): {e}")
                            if retry_count >= max_retries:
                                raise
                            # 等待一段时间再重试
                            import time
                            time.sleep(1)
                except Exception as e:
                    file_logger.error(f"文件下载同步请求异常: {e}")
                    logger.error(f"文件下载同步请求异常: {e}")
                    raise e

            # 在事件循环的线程池中执行同步请求
            file_logger.debug(f"准备在事件循环中执行同步请求...")
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, send_request)
            status_code = response.status_code
            file_logger.debug(f"下载请求响应状态码: {status_code}")

            if status_code != 200:
                # 尝试解析错误信息
                try:
                    error_data = response.json()
                    error_msg = error_data.get('message', '未知错误')
                    error_code = error_data.get('code', -1)
                    error_detail = error_data.get('data', {}).get('error', '')
                    file_logger.error(f"文件下载失败，状态码: {status_code}, 错误码: {error_code}, 错误信息: {error_msg}, 详情: {error_detail}")
                    logger.error(f"文件下载失败，状态码: {status_code}")
                except:
                    file_logger.error(f"文件下载失败，状态码: {status_code}, 响应: {response.text[:200]}")
                    logger.error(f"文件下载失败，状态码: {status_code}")
                return None

            # 检查Content-Type
            content_type = response.headers.get('Content-Type', '')
            file_logger.debug(f"响应Content-Type: {content_type}")

            # 更宽松地检查Content-Type，有些服务器可能返回不同的MIME类型
            valid_content_types = ['application/octet-stream', 'binary/octet-stream', 'application/binary']
            is_binary_content = any(ct in content_type for ct in valid_content_types) or len(response.content) > 0

            if is_binary_content:
                # 成功获取文件内容
                file_content = response.content
                file_size = len(file_content)
                file_logger.info(f"成功下载文件: {file_path}, 大小: {file_size} 字节")
                logger.info(f"成功下载文件: {file_path}, 大小: {file_size} 字节")

                # 检查文件内容是否为空
                if file_size == 0:
                    file_logger.warning(f"下载的文件内容为空: {file_path}")
                    logger.warning(f"下载的文件内容为空: {file_path}")
                    return None
                else:
                    file_logger.debug(f"文件内容前100字节: {file_content[:100]}")

                    # 检查文件类型
                    _, ext = os.path.splitext(file_path)
                    if ext:
                        file_logger.info(f"文件扩展名: {ext.upper()}")

                return file_content
            else:
                # 可能是错误响应
                try:
                    error_data = response.json()
                    file_logger.error(f"文件下载API返回非文件内容: {error_data}")
                    logger.error(f"文件下载API返回非文件内容")
                except:
                    file_logger.error(f"文件下载API返回非文件内容且无法解析: {response.text[:200]}")
                    logger.error(f"文件下载API返回非文件内容且无法解析")
                return None

        except Exception as e:
            file_logger.error(f"下载文件失败: {e}")
            file_logger.exception(e)
            logger.error(f"下载文件失败: {e}")
            return None

    async def get_all_listener_messages(self) -> Dict[str, List[Dict]]:
        """获取所有监听对象的消息"""
        try:
            import requests

            # 使用requests执行请求，不带who参数获取所有监听对象的消息
            url = f"{self.base_url}/api/message/listen/get"
            headers = {'X-API-Key': self.api_key}

            # 记录完整的curl命令，方便调试
            curl_cmd = f"curl -X GET '{url}' -H 'X-API-Key: {self.api_key}'"
            logger.debug(f"执行API请求，等效curl命令: {curl_cmd}")

            # 执行请求
            response = requests.get(url, headers=headers)
            status_code = response.status_code

            if status_code != 200:
                logger.error(f"获取监听消息请求失败，状态码: {status_code}, 响应: {response.text}")
                return {}

            # 解析JSON响应
            data = response.json()
            logger.debug(f"获取消息API响应: {data}")

            # 检查API响应状态码
            if data.get('code') != 0:
                logger.error(f"获取监听消息API错误: [{data.get('code', -1)}] {data.get('message', '未知错误')}")
                return {}

            # 获取消息数据
            result_data = data.get('data', {})
            messages_data = result_data.get('messages', {})

            # 处理空消息情况 - 这是正常的，表示没有新消息
            if not messages_data:
                logger.debug(f"没有任何监听对象的新消息")
                return {}

            # 确保messages_data是字典格式
            if not isinstance(messages_data, dict):
                logger.warning(f"未知的消息数据格式: {type(messages_data)}")
                return {}

            # 过滤掉type为base或sender为self的消息
            filtered_messages_data = {}
            for chat_name, messages in messages_data.items():
                if not isinstance(messages, list):
                    continue

                filtered_messages = []
                for msg in messages:
                    # 获取消息类型和发送者
                    msg_type = msg.get('type', '').lower()
                    sender = msg.get('sender', '').lower()

                    # 忽略type为base或sender为self的消息
                    if msg_type == 'base' or sender == 'self':
                        logger.debug(f"过滤掉消息: 聊天={chat_name}, 类型={msg_type}, 发送者={sender}")
                        continue

                    filtered_messages.append(msg)

                # 只有当有过滤后的消息时才添加到结果中
                if filtered_messages:
                    filtered_messages_data[chat_name] = filtered_messages
                    logger.info(f"获取到监听对象[{chat_name}]的 {len(filtered_messages)} 条有效消息")

            return filtered_messages_data

        except requests.RequestException as e:
            logger.error(f"获取监听消息网络错误: {e}")
            logger.exception(e)
            return {}
        except Exception as e:
            logger.error(f"获取监听消息失败: {e}")
            logger.exception(e)
            return {}

    async def get_listener_messages(self, who: str) -> List[Dict]:
        """获取指定监听对象的消息（向后兼容方法）"""
        all_messages = await self.get_all_listener_messages()
        return all_messages.get(who, [])

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