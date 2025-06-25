"""
智能记账插件实现

该插件实现了与只为记账平台的集成，支持：
- 智能记账功能
- 账本管理
- 自动登录
- 记账结果回复
"""

import logging
import json
import asyncio
import aiohttp
from typing import Dict, Any

from wxauto_mgt.core.plugin_system import (
    BaseServicePlatform, PluginInfo, MessageContext, ProcessResult, MessageType
)

logger = logging.getLogger(__name__)


class AccountingPlatformPlugin(BaseServicePlatform):
    """智能记账插件"""
    
    def __init__(self, plugin_info: PluginInfo):
        """初始化智能记账插件"""
        super().__init__(plugin_info)
        
        # 设置支持的消息类型
        self._supported_message_types = [MessageType.TEXT]
        self._platform_type = "accounting"
        
        # 记账特定配置
        self.server_url = ""
        self.username = ""
        self.password = ""
        self.account_book_id = ""
        self.account_book_name = "个人账本"
        self.auto_login = True
        self.timeout = 30
        self.enable_smart_accounting = True
        self.reply_format = "记账成功：{amount}元 - {description}"
        
        # 运行时状态
        self.access_token = None
        self.logged_in = False
    
    def get_config_schema(self) -> Dict[str, Any]:
        """获取配置模式定义"""
        return {
            "type": "object",
            "properties": {
                "server_url": {
                    "type": "string",
                    "title": "服务器地址",
                    "description": "只为记账服务器地址"
                },
                "username": {
                    "type": "string",
                    "title": "用户名",
                    "description": "只为记账账号用户名"
                },
                "password": {
                    "type": "string",
                    "title": "密码",
                    "description": "只为记账账号密码",
                    "format": "password"
                },
                "account_book_id": {
                    "type": "string",
                    "title": "账本ID",
                    "description": "默认账本ID"
                },
                "account_book_name": {
                    "type": "string",
                    "title": "账本名称",
                    "description": "默认账本名称",
                    "default": "个人账本"
                },
                "auto_login": {
                    "type": "boolean",
                    "title": "自动登录",
                    "description": "是否自动登录",
                    "default": True
                },
                "enable_smart_accounting": {
                    "type": "boolean",
                    "title": "启用智能记账",
                    "description": "是否启用智能记账功能",
                    "default": True
                },
                "reply_format": {
                    "type": "string",
                    "title": "回复格式",
                    "description": "记账成功后的回复格式",
                    "default": "记账成功：{amount}元 - {description}"
                }
            },
            "required": ["server_url", "username", "password", "account_book_id"]
        }
    
    def validate_config(self, config: Dict[str, Any]) -> tuple[bool, str]:
        """验证配置"""
        required_fields = ["server_url", "username", "password", "account_book_id"]
        
        for field in required_fields:
            if not config.get(field):
                return False, f"{field} 不能为空"
        
        # 验证服务器URL格式
        server_url = config['server_url'].strip()
        if not (server_url.startswith('http://') or server_url.startswith('https://')):
            return False, "服务器地址必须以http://或https://开头"
        
        return True, None
    
    async def _do_initialize(self):
        """执行自定义初始化逻辑"""
        # 从配置中提取参数
        self.server_url = self._config.get('server_url', '').rstrip('/')
        self.username = self._config.get('username', '')
        self.password = self._config.get('password', '')
        self.account_book_id = self._config.get('account_book_id', '')
        self.account_book_name = self._config.get('account_book_name', '个人账本')
        self.auto_login = self._config.get('auto_login', True)
        self.timeout = self._config.get('timeout', 30)
        self.enable_smart_accounting = self._config.get('enable_smart_accounting', True)
        self.reply_format = self._config.get('reply_format', '记账成功：{amount}元 - {description}')
        
        # 如果启用自动登录，尝试登录
        if self.auto_login:
            await self._login()
        
        logger.info(f"记账插件初始化完成: {self.server_url}")
    
    async def _login(self) -> bool:
        """登录到记账平台"""
        try:
            login_data = {
                "username": self.username,
                "password": self.password
            }
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.post(
                    f"{self.server_url}/api/auth/login",
                    json=login_data
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        self.access_token = result.get('access_token')
                        self.logged_in = True
                        logger.info("记账平台登录成功")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"记账平台登录失败: {response.status}, {error_text}")
                        return False
        
        except Exception as e:
            logger.error(f"记账平台登录异常: {e}")
            return False
    
    async def _do_process_message(self, context: MessageContext) -> ProcessResult:
        """处理消息"""
        try:
            if not self.enable_smart_accounting:
                return ProcessResult(
                    success=True,
                    response="",
                    should_reply=False
                )
            
            # 检查登录状态
            if not self.logged_in and not await self._login():
                return ProcessResult(
                    success=False,
                    error="记账平台未登录",
                    should_reply=False
                )
            
            # 调用智能记账API
            content = context.content
            sender_name = context.sender_remark or context.sender
            
            logger.info(f"开始处理记账消息: {content[:50]}... (发送者: {sender_name})")
            
            # 构建记账请求
            accounting_data = {
                "description": content,
                "sender_name": sender_name,
                "account_book_id": self.account_book_id
            }
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.post(
                    f"{self.server_url}/api/accounting/smart",
                    headers=headers,
                    json=accounting_data
                ) as response:
                    if response.status == 401:
                        # Token过期，重新登录
                        if await self._login():
                            headers["Authorization"] = f"Bearer {self.access_token}"
                            # 重试请求
                            async with session.post(
                                f"{self.server_url}/api/accounting/smart",
                                headers=headers,
                                json=accounting_data
                            ) as retry_response:
                                if retry_response.status != 200:
                                    error_text = await retry_response.text()
                                    return ProcessResult(
                                        success=False,
                                        error=f"记账失败: {error_text}",
                                        should_reply=False
                                    )
                                result = await retry_response.json()
                        else:
                            return ProcessResult(
                                success=False,
                                error="重新登录失败",
                                should_reply=False
                            )
                    elif response.status != 200:
                        error_text = await response.text()
                        return ProcessResult(
                            success=False,
                            error=f"记账失败: {error_text}",
                            should_reply=False
                        )
                    else:
                        result = await response.json()
            
            # 处理记账结果
            if result.get('success'):
                # 格式化回复消息
                amount = result.get('amount', 0)
                description = result.get('description', content)
                
                reply_message = self.reply_format.format(
                    amount=amount,
                    description=description
                )
                
                logger.info(f"记账成功: {context.message_id}")
                return ProcessResult(
                    success=True,
                    response=reply_message,
                    should_reply=True,
                    metadata={
                        "amount": amount,
                        "description": description,
                        "account_book_id": self.account_book_id,
                        "record_id": result.get('record_id')
                    }
                )
            else:
                error_msg = result.get('error', '记账失败')
                logger.warning(f"记账失败: {error_msg}")
                return ProcessResult(
                    success=False,
                    error=error_msg,
                    should_reply=False
                )
        
        except Exception as e:
            logger.error(f"记账处理失败: {context.message_id}, 错误: {e}")
            return ProcessResult(
                success=False,
                error=str(e),
                should_reply=False
            )
    
    async def _do_test_connection(self) -> Dict[str, Any]:
        """测试连接"""
        try:
            # 测试登录
            if await self._login():
                return {
                    "success": True,
                    "message": "连接测试成功",
                    "logged_in": True,
                    "account_book": self.account_book_name
                }
            else:
                return {
                    "success": False,
                    "error": "登录失败"
                }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _do_health_check(self) -> Dict[str, Any]:
        """执行健康检查"""
        health_data = {}
        
        # 检查配置
        health_data["config_valid"] = bool(
            self.server_url and self.username and 
            self.password and self.account_book_id
        )
        
        # 检查登录状态
        health_data["logged_in"] = self.logged_in
        health_data["account_book_id"] = self.account_book_id
        health_data["account_book_name"] = self.account_book_name
        
        # 检查网络连接
        try:
            test_result = await self._do_test_connection()
            health_data["connection_ok"] = test_result.get("success", False)
            if not test_result.get("success"):
                health_data["connection_error"] = test_result.get("error")
        except Exception as e:
            health_data["connection_ok"] = False
            health_data["connection_error"] = str(e)
        
        return health_data
