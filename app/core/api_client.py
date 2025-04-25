"""
WxAuto API客户端模块
使用简单的requests方法实现API调用
"""

import logging
import requests
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

class ApiError(Exception):
    """API错误"""
    def __init__(self, message: str, code: int = -1):
        self.message = message
        self.code = code
        super().__init__(f"API错误 [{code}]: {message}")

class WxAutoApiClient:
    """WxAuto API客户端"""
    
    def __init__(self, base_url: str, api_key: str):
        """初始化API客户端"""
        self.base_url = base_url
        self.api_key = api_key
        
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
            
    def _post(self, endpoint: str, json: Dict = None) -> Dict:
        """发送POST请求"""
        try:
            response = requests.post(
                f"{self.base_url}{endpoint}",
                json=json,  # 布尔值在JSON中保持Python布尔类型
                headers={
                    'X-API-Key': self.api_key,
                    'Content-Type': 'application/json'
                }
            )
            response.raise_for_status()
            data = response.json()
            if data.get('code') != 0:
                raise ApiError(data.get('message', '未知错误'), data.get('code', -1))
            return data.get('data', {})
        except requests.exceptions.RequestException as e:
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
            return True
        except Exception as e:
            logger.error(f"初始化失败: {e}")
            return False
            
    async def get_status(self) -> Dict:
        """获取微信状态"""
        try:
            return self._get('/api/wechat/status')
        except Exception as e:
            logger.error(f"获取状态失败: {e}")
            return {}
            
    async def send_message(self, receiver: str, message: str, at_list: List[str] = None) -> bool:
        """发送消息"""
        try:
            data = {
                'receiver': receiver,
                'message': message,
                'at_list': at_list or []
            }
            self._post('/api/message/send', json=data)
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
            
    async def add_listener(self, instance_id: str, wxid: str, **kwargs) -> bool:
        """添加监听对象"""
        try:
            data = {'who': wxid, **kwargs}
            self._post('/api/message/listen/add', json=data)
            return True
        except Exception as e:
            logger.error(f"添加监听对象失败: {e}")
            return False
            
    async def remove_listener(self, instance_id: str, wxid: str) -> bool:
        """移除监听对象"""
        try:
            data = {'who': wxid}
            self._post('/api/message/listen/remove', json=data)
            return True
        except Exception as e:
            logger.error(f"移除监听对象失败: {e}")
            return False
            
    async def get_listener_messages(self, instance_id: str, wxid: str) -> List[Dict]:
        """获取监听对象的消息"""
        try:
            params = {'who': wxid}
            data = self._get('/api/message/listen/get', params=params)
            return data.get('messages', {}).get(wxid, [])
        except Exception as e:
            logger.error(f"获取监听消息失败: {e}")
            return [] 