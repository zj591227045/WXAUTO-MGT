"""
WxAuto API客户端模块
使用简单的requests方法实现API调用，支持多实例管理
"""

import logging
import requests
import json
from typing import Dict, List, Optional, Any
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
        
    def _get(self, endpoint: str, params: Dict = None) -> Dict:
        """发送GET请求"""
        try:
            # 将布尔值转换为小写字符串
            if params:
                params = {k: str(v).lower() if isinstance(v, bool) else v 
                         for k, v in params.items()}
            
            response = requests.get(
                f"{self.base_url}{endpoint}",
                params=params,
                headers={'X-API-Key': self.api_key}
            )
            response.raise_for_status()
            data = response.json()
            if data.get('code') != 0:
                raise ApiError(data.get('message', '未知错误'), data.get('code', -1))
            return data.get('data', {})
        except requests.exceptions.RequestException as e:
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
            data = self._get('/api/wechat/status')
            self._connected = data.get('isOnline', False)
            return data
        except Exception as e:
            logger.error(f"获取状态失败: {e}")
            self._connected = False
            return {}
            
    async def get_health_info(self) -> Dict:
        """获取服务健康状态信息，包含启动时间和状态"""
        try:
            data = self._get('/api/health')
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
            data = self._get('/api/system/resources')
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
            
    async def send_message(self, receiver: str, message: str, at_list: List[str] = None) -> bool:
        """发送消息"""
        try:
            data = {
                'receiver': receiver,
                'message': message,
                'at_list': at_list or []
            }
            await self._post('/api/message/send', json=data)
            return True
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            return False
            
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
            data = self._get('/api/message/get-next-new', params=params)
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
            
            logger.debug(f"添加监听对象参数: {api_params}")
            result = await self._post('/api/message/listen/add', json=api_params)
            logger.info(f"成功添加监听对象 {who}")
            return True
        except Exception as e:
            logger.error(f"添加监听对象失败: {e}")
            return False
            
    async def remove_listener(self, who: str) -> bool:
        """移除监听对象"""
        try:
            data = {'who': who}
            result = await self._post('/api/message/listen/remove', json=data)
            # 检查结果 - API成功时返回data中包含who字段，这表示成功
            success = isinstance(result, dict) and 'who' in result
            if success:
                logger.debug(f"成功移除监听对象 {who}")
                return True
            else:
                logger.error(f"移除监听对象失败，API返回: {result}")
                return False
        except Exception as e:
            logger.error(f"移除监听对象失败: {e}")
            logger.exception(e)  # 记录完整堆栈
            return False
            
    async def get_listener_messages(self, who: str) -> List[Dict]:
        """获取监听对象的消息"""
        try:
            params = {'who': who}
            logger.debug(f"获取监听对象[{who}]消息，参数: {params}")
            data = self._get('/api/message/listen/get', params=params)
            
            if 'messages' not in data:
                logger.warning(f"获取监听对象[{who}]消息响应格式异常: {data}")
                return []
                
            messages_data = data.get('messages', {}).get(who, [])
            if messages_data:
                logger.info(f"获取到监听对象[{who}]的 {len(messages_data)} 条消息")
            return messages_data
        except Exception as e:
            logger.error(f"获取监听消息失败: {e}")
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