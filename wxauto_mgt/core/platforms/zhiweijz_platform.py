"""
只为记账服务平台实现

该模块实现了与只为记账平台的集成，包括：
- 智能记账功能
- 账本管理
- 配置管理
- 错误处理和重试机制
"""

import logging
import json
from typing import Dict, Any, Optional

from .base_platform import ServicePlatform
from ..async_accounting_manager import AsyncAccountingManager

# 导入标准日志记录器
logger = logging.getLogger('wxauto_mgt')


class ZhiWeiJZPlatform(ServicePlatform):
    """只为记账服务平台实现"""
    
    def __init__(self, platform_id: str, name: str, config: Dict[str, Any]):
        """
        初始化只为记账平台
        
        Args:
            platform_id: 平台ID
            name: 平台名称
            config: 平台配置，必须包含server_url、username、password等
        """
        super().__init__(platform_id, name, config)
        
        # 记账管理器
        self.accounting_manager: Optional[AsyncAccountingManager] = None
        
        # 配置验证
        self.server_url = config.get('server_url', '').rstrip('/')
        self.username = config.get('username', '')
        self.password = config.get('password', '')
        self.account_book_id = config.get('account_book_id', '')
        self.account_book_name = config.get('account_book_name', '')
        
        # 记账相关配置
        self.auto_login = config.get('auto_login', True)
        self.token_refresh_interval = config.get('token_refresh_interval', 300)
        self.request_timeout = config.get('request_timeout', 30)
        self.max_retries = config.get('max_retries', 3)
        
        logger.info(f"只为记账平台初始化: {name} ({platform_id})")
    
    async def initialize(self) -> bool:
        """
        初始化平台
        
        Returns:
            bool: 是否初始化成功
        """
        try:
            logger.info(f"开始初始化只为记账平台: {self.name}")
            
            # 验证必需配置
            if not all([self.server_url, self.username, self.password]):
                logger.error("缺少必需的配置参数: server_url, username, password")
                self._initialized = False
                return False
            
            # 创建记账管理器
            self.accounting_manager = AsyncAccountingManager(self.config)
            
            # 初始化记账管理器（不进行网络请求）
            if not await self.accounting_manager.initialize():
                logger.error("记账管理器初始化失败")
                self._initialized = False
                return False

            # 不在初始化阶段进行网络请求测试
            # 网络连接测试将在实际使用时或通过test_connection方法进行
            logger.info("只为记账平台配置验证完成，跳过网络连接测试")
            
            logger.info(f"只为记账平台初始化成功: {self.name}")
            self._initialized = True
            return True
            
        except Exception as e:
            logger.error(f"初始化只为记账平台失败: {e}")
            self._initialized = False
            return False
    
    async def process_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理记账消息

        Args:
            message: 消息字典，包含content、sender等字段

        Returns:
            Dict[str, Any]: 处理结果
        """
        try:
            # 添加详细的调试日志
            logger.info(f"[记账平台] 开始处理消息，平台初始化状态: {self._initialized}")
            logger.info(f"[记账平台] 记账管理器状态: {self.accounting_manager is not None}")

            if not self._initialized or not self.accounting_manager:
                error_msg = f"平台未初始化 - initialized: {self._initialized}, manager: {self.accounting_manager is not None}"
                logger.error(f"[记账平台] {error_msg}")
                return {
                    'success': False,
                    'response': '平台未初始化',
                    'platform': 'zhiweijz',
                    'should_reply': False
                }

            # 提取消息内容和发送者
            content = message.get('content', '')
            # 优先使用sender_remark字段，如果没有值则回退使用sender字段
            sender_name = message.get('sender_remark') or message.get('sender', '')

            # 记录处理开始
            logger.info(f"[记账平台] 开始处理记账消息: {content[:50]}... (发送者: {sender_name})")
            
            # 调用智能记账API
            logger.info(f"[记账平台] 准备调用智能记账API...")
            success, result = await self.accounting_manager.smart_accounting(
                description=content,
                sender_name=sender_name
            )
            logger.info(f"[记账平台] 智能记账API调用完成，成功: {success}")

            # 判断是否应该发送回复（参考旧版代码逻辑）
            should_reply = self._should_send_reply(result)

            if success:
                logger.info(f"[记账平台] 记账成功: {result}")
                return {
                    'success': True,
                    'response': result,
                    'platform': 'zhiweijz',
                    'should_reply': should_reply,
                    'reply_content': result  # 直接使用格式化后的结果
                }
            else:
                logger.warning(f"[记账平台] 记账失败: {result}")
                return {
                    'success': False,
                    'response': result,
                    'platform': 'zhiweijz',
                    'should_reply': should_reply,
                    'reply_content': result  # 直接使用格式化后的结果
                }
                
        except Exception as e:
            error_msg = f"记账处理异常: {str(e)}"
            logger.error(f"[记账平台] {error_msg}")
            import traceback
            logger.error(f"[记账平台] 异常堆栈: {traceback.format_exc()}")
            return {
                'success': False,
                'response': error_msg,
                'platform': 'zhiweijz',
                'should_reply': False
            }

    def _should_send_reply(self, accounting_result: str) -> bool:
        """
        判断是否应该发送回复（参考旧版代码逻辑）

        Args:
            accounting_result: 记账结果消息

        Returns:
            True表示应该发送回复，False表示不应该发送
        """
        # 如果是"信息与记账无关"，根据配置决定是否发送回复
        if "信息与记账无关" in accounting_result:
            # 检查配置中的warn_on_irrelevant选项
            warn_on_irrelevant = self.config.get("warn_on_irrelevant", False)
            logger.info(f"消息与记账无关，warn_on_irrelevant配置: {warn_on_irrelevant}")
            return warn_on_irrelevant

        # 其他情况（记账成功、失败、错误等）都发送回复
        return True

    async def test_connection(self) -> Dict[str, Any]:
        """
        测试记账平台连接

        Returns:
            Dict[str, Any]: 测试结果
        """
        try:
            logger.info(f"开始测试只为记账平台连接: {self.name}")

            if not self.accounting_manager:
                # 创建临时记账管理器进行测试
                temp_manager = AsyncAccountingManager(self.config)
                await temp_manager.initialize()

                try:
                    # 测试登录
                    success, message = await temp_manager.login()
                    if not success:
                        return {
                            'success': False,
                            'message': f'登录测试失败: {message}',
                            'details': {
                                'server_url': self.server_url,
                                'username': self.username
                            }
                        }

                    # 测试获取账本列表
                    books_success, books_message, books = await temp_manager.get_account_books()

                    result = {
                        'success': True,
                        'message': '连接测试成功',
                        'details': {
                            'server_url': self.server_url,
                            'username': self.username,
                            'account_books_count': len(books) if books_success else 0,
                            'current_account_book': self.account_book_name or self.account_book_id
                        }
                    }

                    if books_success and books:
                        result['data'] = {'account_books': books}

                    return result

                finally:
                    await temp_manager.cleanup()
            else:
                # 使用现有的记账管理器
                # 测试获取账本列表
                books_success, books_message, books = await self.accounting_manager.get_account_books()

                if books_success:
                    return {
                        'success': True,
                        'message': '连接测试成功',
                        'details': {
                            'server_url': self.server_url,
                            'username': self.username,
                            'account_books_count': len(books),
                            'current_account_book': self.account_book_name or self.account_book_id
                        },
                        'data': {'account_books': books}
                    }
                else:
                    return {
                        'success': False,
                        'message': f'获取账本列表失败: {books_message}',
                        'details': {
                            'server_url': self.server_url,
                            'username': self.username
                        }
                    }

        except Exception as e:
            error_msg = f'连接测试异常: {str(e)}'
            logger.error(error_msg)
            return {
                'success': False,
                'message': error_msg,
                'details': {
                    'server_url': self.server_url,
                    'username': self.username
                }
            }

    def get_type(self) -> str:
        """
        获取平台类型

        Returns:
            str: 平台类型
        """
        return "zhiweijz"

    def get_safe_config(self) -> Dict[str, Any]:
        """
        获取安全的配置（隐藏敏感信息）

        Returns:
            Dict[str, Any]: 安全的配置
        """
        safe_config = self.config.copy()
        # 隐藏密码等敏感信息
        if 'password' in safe_config:
            safe_config['password'] = '******'
        return safe_config

    async def cleanup(self):
        """清理资源"""
        if self.accounting_manager:
            await self.accounting_manager.cleanup()
            self.accounting_manager = None
        logger.info(f"只为记账平台资源已清理: {self.name}")

    def get_stats(self) -> Dict[str, Any]:
        """
        获取平台统计信息

        Returns:
            Dict[str, Any]: 统计信息
        """
        if self.accounting_manager:
            return self.accounting_manager.get_stats()
        return {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'token_refreshes': 0
        }
