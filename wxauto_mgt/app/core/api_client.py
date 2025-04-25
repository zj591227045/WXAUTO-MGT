"""
API客户端模块

提供与WxAuto HTTP API通信的客户端实现，负责封装API调用、处理认证和请求/响应。
"""

import asyncio
import json
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple, Union

import aiohttp

from app.utils.logging import get_logger

logger = get_logger()


class ApiError(Exception):
    """API调用异常类"""
    
    def __init__(self, code: int, message: str, details: Optional[Dict] = None):
        """
        初始化API异常
        
        Args:
            code: 错误代码
            message: 错误消息
            details: 错误详情（可选）
        """
        self.code = code
        self.message = message
        self.details = details
        super().__init__(f"API Error {code}: {message}")


class WxAutoApiClient:
    """
    WxAuto API客户端类，负责与WxAuto HTTP API进行通信
    """
    
    def __init__(self, base_url: str, api_key: str, timeout: int = 30, retry_limit: int = 3, retry_delay: int = 2):
        """
        初始化WxAuto API客户端
        
        Args:
            base_url: API基础URL，例如 http://localhost:8080
            api_key: API密钥
            timeout: 请求超时时间（秒）
            retry_limit: 请求重试次数
            retry_delay: 请求重试延迟（秒）
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.retry_limit = retry_limit
        self.retry_delay = retry_delay
        self.session = None
        self._initialized = False
        self._connected = False
        self._client_id = str(uuid.uuid4())
        
        logger.debug(f"初始化WxAuto API客户端: {base_url}, 客户端ID: {self._client_id}")
    
    async def _ensure_session(self) -> None:
        """确保HTTP会话已创建"""
        if self.session is None or self.session.closed:
            # 不在会话级别设置授权头，而是在每个请求中单独添加
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )
            logger.debug("已创建新的HTTP会话")
    
    async def close(self) -> None:
        """关闭HTTP会话"""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None
            logger.debug("API客户端会话已关闭")
    
    async def _request(self, method: str, endpoint: str, data: Optional[Dict] = None, 
                       params: Optional[Dict] = None, retry: bool = True) -> Dict:
        """
        发送API请求
        
        Args:
            method: HTTP方法（GET, POST, PUT, DELETE等）
            endpoint: API端点路径
            data: 请求体数据（可选）
            params: 查询参数（可选）
            retry: 是否在失败时重试
            
        Returns:
            Dict: API响应数据
            
        Raises:
            ApiError: API调用失败
        """
        await self._ensure_session()
        
        # 检查API密钥是否设置
        if not self.api_key:
            logger.error("API密钥未设置")
            raise ApiError(401, "API密钥未设置")
            
        # 确保endpoint以/api开头
        if not endpoint.startswith('/api'):
            endpoint = f'/api/{endpoint.lstrip("/")}'
        
        url = f"{self.base_url}{endpoint}"
        retry_count = 0
        
        # 为每个请求创建特定的请求头，确保包含当前的API密钥
        headers = {"X-API-Key": self.api_key}
        logger.debug(f"正在发送请求至 {url}，使用API密钥: {self.api_key[:3]}***{self.api_key[-3:] if len(self.api_key)>6 else ''}")
        
        while True:
            try:
                async with self.session.request(method, url, json=data, params=params, headers=headers) as response:
                    response_text = await response.text()
                    if not response_text:
                        raise ApiError(response.status, "空响应")
                    
                    try:
                        response_data = json.loads(response_text)
                    except json.JSONDecodeError:
                        raise ApiError(response.status, f"无效的JSON响应: {response_text[:100]}")
                    
                    if response.status >= 400:
                        error_message = response_data.get("message", "未知错误")
                        raise ApiError(response.status, error_message, response_data)
                    
                    return response_data
            
            except (aiohttp.ClientError, asyncio.TimeoutError, ApiError) as e:
                retry_count += 1
                
                if not retry or retry_count > self.retry_limit:
                    if isinstance(e, ApiError):
                        raise
                    raise ApiError(500, f"请求失败: {str(e)}")
                
                logger.warning(f"API请求失败 ({retry_count}/{self.retry_limit}): {e}, 将在 {self.retry_delay} 秒后重试")
                await asyncio.sleep(self.retry_delay)
    
    async def initialize(self) -> Dict:
        """
        初始化微信实例
        
        Returns:
            Dict: 初始化结果
        """
        try:
            logger.info(f"正在初始化微信实例, URL: {self.base_url}")
            result = await self._request("POST", "/api/wechat/initialize")
            self._initialized = True
            logger.info("微信实例初始化成功")
            return result
        except ApiError as e:
            logger.error(f"微信实例初始化失败: {e}")
            logger.error(f"请确认API地址({self.base_url})和认证方式(X-API-Key)是否正确")
            self._initialized = False
            raise
    
    async def get_status(self) -> Dict:
        """
        获取微信状态
        
        Returns:
            Dict: 微信状态信息
        """
        try:
            result = await self._request("GET", "/api/wechat/status")
            self._connected = result.get("isOnline", False)
            return result
        except ApiError as e:
            logger.error(f"获取微信状态失败: {e}")
            self._connected = False
            raise
    
    async def get_system_metrics(self) -> Dict:
        """
        获取系统资源使用情况
        
        Returns:
            Dict: 系统资源指标，包括CPU和内存使用率
        """
        try:
            # 获取系统资源数据
            result = await self._request("GET", "system/resources")
            
            # 提取数据
            data = result.get("data", {})
            cpu_data = data.get("cpu", {})
            memory_data = data.get("memory", {})
            
            # 构建指标字典
            metrics = {
                "cpu_usage": cpu_data.get("usage_percent", 0),
                "memory_usage": memory_data.get("used", 0)  # 使用已用内存量(MB)
            }
            
            logger.debug(f"获取系统资源指标: CPU={metrics['cpu_usage']}%, 内存={metrics['memory_usage']}MB")
            return metrics
        except ApiError as e:
            logger.error(f"获取系统资源指标失败: {e}")
            return {
                "cpu_usage": 0,
                "memory_usage": 0
            }
    
    # 消息发送相关接口 --------------------
    
    async def send_message(self, receiver: str, message: str, at_list: Optional[List[str]] = None, 
                           clear: bool = True) -> Dict:
        """
        发送普通文本消息
        
        Args:
            receiver: 接收者（微信ID或群ID）
            message: 消息内容
            at_list: @用户列表（仅群消息有效）
            clear: 发送后是否清空输入框
            
        Returns:
            Dict: 发送结果
        """
        data = {
            "wxid": receiver,
            "msg": message,
            "clear": clear
        }
        
        if at_list:
            data["at_list"] = at_list
        
        try:
            return await self._request("POST", "wx/send/text", data)
        except ApiError as e:
            logger.error(f"发送文本消息失败: {e}")
            raise
    
    async def send_file(self, receiver: str, file_path: str) -> Dict:
        """
        发送文件消息
        
        Args:
            receiver: 接收者（微信ID或群ID）
            file_path: 文件路径
            
        Returns:
            Dict: 发送结果
        """
        data = {
            "wxid": receiver,
            "file": file_path
        }
        
        try:
            return await self._request("POST", "wx/send/file", data)
        except ApiError as e:
            logger.error(f"发送文件消息失败: {e}")
            raise
    
    async def send_image(self, receiver: str, image_path: str) -> Dict:
        """
        发送图片消息
        
        Args:
            receiver: 接收者（微信ID或群ID）
            image_path: 图片路径
            
        Returns:
            Dict: 发送结果
        """
        data = {
            "wxid": receiver,
            "image": image_path
        }
        
        try:
            return await self._request("POST", "wx/send/image", data)
        except ApiError as e:
            logger.error(f"发送图片消息失败: {e}")
            raise
    
    async def send_article(self, receiver: str, title: str, abstract: str, url: str, 
                          image_path: Optional[str] = None) -> Dict:
        """
        发送图文链接消息
        
        Args:
            receiver: 接收者（微信ID或群ID）
            title: 标题
            abstract: 摘要
            url: 链接URL
            image_path: 缩略图路径（可选）
            
        Returns:
            Dict: 发送结果
        """
        data = {
            "wxid": receiver,
            "title": title,
            "abstract": abstract,
            "url": url
        }
        
        if image_path:
            data["image"] = image_path
        
        try:
            return await self._request("POST", "wx/send/article", data)
        except ApiError as e:
            logger.error(f"发送图文链接消息失败: {e}")
            raise
    
    # 消息接收相关接口 --------------------
    
    async def get_unread_messages(self, count: int = 10) -> List[Dict]:
        """
        获取主窗口未读消息
        
        Args:
            count: 获取的消息数量
            
        Returns:
            List[Dict]: 未读消息列表
        """
        params = {"count": count}
        
        try:
            result = await self._request("GET", "wx/message/unread", params=params)
            return result.get("messages", [])
        except ApiError as e:
            logger.error(f"获取未读消息失败: {e}")
            return []
    
    async def get_messages(self, wxid: str, count: int = 10) -> List[Dict]:
        """
        获取指定对象的消息
        
        Args:
            wxid: 微信ID或群ID
            count: 获取的消息数量
            
        Returns:
            List[Dict]: 消息列表
        """
        params = {
            "wxid": wxid,
            "count": count
        }
        
        try:
            result = await self._request("GET", "wx/message/get", params=params)
            return result.get("messages", [])
        except ApiError as e:
            logger.error(f"获取消息失败: {e}")
            return []
    
    async def get_message_history(self, wxid: str, limit: int = 20, offset: int = 0) -> List[Dict]:
        """
        获取消息历史记录
        
        Args:
            wxid: 微信ID或群ID
            limit: 获取的消息数量
            offset: 起始偏移量
            
        Returns:
            List[Dict]: 消息列表
        """
        params = {
            "wxid": wxid,
            "limit": limit,
            "offset": offset
        }
        
        try:
            result = await self._request("GET", "wx/message/history", params=params)
            return result.get("messages", [])
        except ApiError as e:
            logger.error(f"获取消息历史记录失败: {e}")
            return []
    
    async def search_message(self, keyword: str, wxid: Optional[str] = None, count: int = 20) -> List[Dict]:
        """
        搜索消息
        
        Args:
            keyword: 搜索关键词
            wxid: 微信ID或群ID（可选，为None时搜索所有聊天）
            count: 返回的最大消息数量
            
        Returns:
            List[Dict]: 匹配的消息列表
        """
        params = {
            "keyword": keyword,
            "count": count
        }
        
        if wxid:
            params["wxid"] = wxid
        
        try:
            result = await self._request("GET", "wx/message/search", params=params)
            return result.get("messages", [])
        except ApiError as e:
            logger.error(f"搜索消息失败: {e}")
            return []
    
    # 监听相关接口 --------------------
    
    async def get_listeners(self) -> List[Dict]:
        """
        获取当前监听对象列表
        
        Returns:
            List[Dict]: 监听对象列表
        """
        try:
            result = await self._request("GET", "wx/listener/list")
            return result.get("listeners", [])
        except ApiError as e:
            logger.error(f"获取监听对象列表失败: {e}")
            return []
    
    async def add_listener(self, wxid: str) -> Dict:
        """
        添加监听对象
        
        Args:
            wxid: 微信ID或群ID
            
        Returns:
            Dict: 添加结果
        """
        data = {"wxid": wxid}
        
        try:
            return await self._request("POST", "wx/listener/add", data)
        except ApiError as e:
            logger.error(f"添加监听对象失败: {e}")
            raise
    
    async def remove_listener(self, wxid: str) -> Dict:
        """
        移除监听对象
        
        Args:
            wxid: 微信ID或群ID
            
        Returns:
            Dict: 移除结果
        """
        data = {"wxid": wxid}
        
        try:
            return await self._request("POST", "wx/listener/remove", data)
        except ApiError as e:
            logger.error(f"移除监听对象失败: {e}")
            raise
    
    async def get_listener_messages(self, wxid: str, count: int = 10) -> List[Dict]:
        """
        获取监听对象的新消息
        
        Args:
            wxid: 微信ID或群ID
            count: 获取的消息数量
            
        Returns:
            List[Dict]: 新消息列表
        """
        params = {
            "wxid": wxid,
            "count": count
        }
        
        try:
            result = await self._request("GET", "wx/listener/messages", params=params)
            return result.get("messages", [])
        except ApiError as e:
            logger.error(f"获取监听对象新消息失败: {e}")
            return []
    
    async def clear_listener_messages(self, wxid: str) -> Dict:
        """
        清除监听对象的消息缓存
        
        Args:
            wxid: 微信ID或群ID
            
        Returns:
            Dict: 清除结果
        """
        data = {"wxid": wxid}
        
        try:
            return await self._request("POST", "wx/listener/clear", data)
        except ApiError as e:
            logger.error(f"清除监听对象消息缓存失败: {e}")
            raise
    
    async def check_listener_status(self, wxid: str) -> Dict:
        """
        检查监听对象状态
        
        Args:
            wxid: 微信ID或群ID
            
        Returns:
            Dict: 状态信息
        """
        params = {"wxid": wxid}
        
        try:
            return await self._request("GET", "wx/listener/status", params=params)
        except ApiError as e:
            logger.error(f"检查监听对象状态失败: {e}")
            raise
    
    # 联系人和群相关接口 --------------------
    
    async def get_contacts(self) -> List[Dict]:
        """
        获取联系人列表
        
        Returns:
            List[Dict]: 联系人列表
        """
        try:
            result = await self._request("GET", "wx/contacts")
            return result.get("contacts", [])
        except ApiError as e:
            logger.error(f"获取联系人列表失败: {e}")
            return []
    
    async def get_groups(self) -> List[Dict]:
        """
        获取群列表
        
        Returns:
            List[Dict]: 群列表
        """
        try:
            result = await self._request("GET", "wx/groups")
            return result.get("groups", [])
        except ApiError as e:
            logger.error(f"获取群列表失败: {e}")
            return []
    
    async def get_group_members(self, group_id: str) -> List[Dict]:
        """
        获取群成员列表
        
        Args:
            group_id: 群ID
            
        Returns:
            List[Dict]: 群成员列表
        """
        params = {"group_id": group_id}
        
        try:
            result = await self._request("GET", "wx/group/members", params=params)
            return result.get("members", [])
        except ApiError as e:
            logger.error(f"获取群成员列表失败: {e}")
            return []
    
    @property
    def initialized(self) -> bool:
        """微信实例是否已初始化"""
        return self._initialized
    
    @property
    def connected(self) -> bool:
        """微信是否已连接"""
        return self._connected
    
    @property
    def client_id(self) -> str:
        """客户端唯一标识"""
        return self._client_id


class WxAutoInstanceManager:
    """
    WxAuto实例管理器，管理多个WxAuto API实例
    """
    
    def __init__(self):
        """初始化实例管理器"""
        self.instances = {}  # 实例字典，键为实例ID，值为WxAutoApiClient实例
        logger.debug("初始化WxAuto实例管理器")
    
    def add_instance(self, instance_id: str, base_url: str, api_key: str, timeout: int = 30, retry_limit: int = 3, retry_delay: int = 2) -> WxAutoApiClient:
        """
        添加新的WxAuto实例
        
        Args:
            instance_id: 实例ID
            base_url: API基础URL
            api_key: API密钥
            timeout: 请求超时时间（秒）
            retry_limit: 请求重试次数
            retry_delay: 请求重试延迟（秒）
            
        Returns:
            WxAutoApiClient: 创建的API客户端实例
        """
        if instance_id in self.instances:
            logger.warning(f"实例 {instance_id} 已存在，将替换现有实例")
            asyncio.create_task(self.instances[instance_id].close())
        
        client = WxAutoApiClient(base_url, api_key, timeout, retry_limit, retry_delay)
        self.instances[instance_id] = client
        logger.info(f"已添加WxAuto实例: {instance_id} ({base_url})")
        return client
    
    def get_instance(self, instance_id: str) -> Optional[WxAutoApiClient]:
        """
        获取指定实例
        
        Args:
            instance_id: 实例ID
            
        Returns:
            Optional[WxAutoApiClient]: API客户端实例，如果不存在则返回None
        """
        return self.instances.get(instance_id)
    
    def list_instances(self) -> Dict[str, WxAutoApiClient]:
        """
        列出所有实例
        
        Returns:
            Dict[str, WxAutoApiClient]: 实例字典
        """
        return self.instances.copy()
    
    def remove_instance(self, instance_id: str) -> bool:
        """
        移除指定实例
        
        Args:
            instance_id: 实例ID
            
        Returns:
            bool: 是否成功移除
        """
        if instance_id in self.instances:
            asyncio.create_task(self.instances[instance_id].close())
            del self.instances[instance_id]
            logger.info(f"已移除WxAuto实例: {instance_id}")
            return True
        return False
    
    async def close_all(self) -> None:
        """关闭所有实例连接"""
        close_tasks = []
        for instance_id, client in self.instances.items():
            logger.debug(f"正在关闭实例连接: {instance_id}")
            close_tasks.append(asyncio.create_task(client.close()))
        
        if close_tasks:
            await asyncio.gather(*close_tasks)
        
        self.instances.clear()
        logger.info("已关闭所有WxAuto实例连接")


# 创建全局实例管理器
instance_manager = WxAutoInstanceManager() 