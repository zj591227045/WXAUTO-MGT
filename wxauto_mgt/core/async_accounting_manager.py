"""
异步记账管理器模块

该模块提供与只为记账平台的异步交互功能，包括：
- 异步登录和token管理
- 异步智能记账API调用
- 账本管理
- 错误处理和重试机制
"""

import asyncio
import json
import base64
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass

# 尝试导入aiohttp，如果失败则使用备用方案
try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    aiohttp = None

# 导入标准日志记录器
logger = logging.getLogger('wxauto_mgt')


@dataclass
class TokenInfo:
    """Token信息"""
    token: str
    expires_at: Optional[datetime] = None
    user_id: str = ""
    email: str = ""
    
    def is_expired(self) -> bool:
        """检查token是否过期"""
        if not self.expires_at:
            return False
        return datetime.now() >= self.expires_at - timedelta(minutes=5)  # 提前5分钟过期


@dataclass
class AccountingConfig:
    """记账配置"""
    server_url: str = ""
    username: str = ""
    password: str = ""
    account_book_id: str = ""
    account_book_name: str = ""
    auto_login: bool = True
    token_refresh_interval: int = 300  # 5分钟检查一次
    request_timeout: int = 30
    max_retries: int = 3


class AsyncAccountingManager:
    """异步记账管理器"""
    
    def __init__(self, config):
        """
        初始化异步记账管理器

        Args:
            config: 记账配置字典或AccountingConfig对象
        """
        # 支持传入字典或AccountingConfig对象
        if isinstance(config, AccountingConfig):
            self.config = config
        else:
            # 传入的是字典
            self.config = AccountingConfig(
                server_url=config.get('server_url', ''),
                username=config.get('username', ''),
                password=config.get('password', ''),
                account_book_id=config.get('account_book_id', ''),
                account_book_name=config.get('account_book_name', ''),
                auto_login=config.get('auto_login', True),
                token_refresh_interval=config.get('token_refresh_interval', 300),
                request_timeout=config.get('request_timeout', 30),
                max_retries=config.get('max_retries', 3)
            )
        
        self.session: Optional[Any] = None  # aiohttp.ClientSession if available
        self.token_info: Optional[TokenInfo] = None
        self._lock = asyncio.Lock()
        
        # 统计信息
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'token_refreshes': 0
        }
        
        logger.info("异步记账管理器初始化完成")
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.cleanup()
    
    async def initialize(self) -> bool:
        """初始化会话"""
        try:
            if not AIOHTTP_AVAILABLE:
                logger.error("aiohttp库未安装，无法初始化记账管理器")
                logger.error("请安装aiohttp: pip install aiohttp")
                return False

            if not self.session:
                timeout = aiohttp.ClientTimeout(total=self.config.request_timeout)
                self.session = aiohttp.ClientSession(timeout=timeout)
                logger.info("HTTP会话初始化完成")
            return True
        except Exception as e:
            logger.error(f"初始化会话失败: {e}")
            return False
    
    async def cleanup(self):
        """清理资源"""
        if self.session:
            await self.session.close()
            self.session = None
            logger.info("HTTP会话已关闭")
    
    async def login(self, server_url: str = None, username: str = None, password: str = None) -> Tuple[bool, str]:
        """
        异步登录
        
        Args:
            server_url: 服务器地址（可选，默认使用配置中的地址）
            username: 用户名（可选，默认使用配置中的用户名）
            password: 密码（可选，默认使用配置中的密码）
            
        Returns:
            Tuple[bool, str]: (是否成功, 消息)
        """
        # 移除锁，避免与_smart_accounting_internal中的锁冲突导致死锁
        try:
                self.stats['total_requests'] += 1
                
                # 使用传入参数或配置中的参数
                url = (server_url or self.config.server_url).rstrip('/')
                user = username or self.config.username
                pwd = password or self.config.password
                
                if not all([url, user, pwd]):
                    error_msg = "缺少必要的登录参数"
                    logger.error(error_msg)
                    self.stats['failed_requests'] += 1
                    return False, error_msg
                
                # 确保会话已初始化
                if not self.session:
                    await self.initialize()
                
                # 构建登录请求
                login_url = f"{url}/api/auth/login"
                data = {
                    "email": user,
                    "password": pwd
                }
                
                logger.info(f"开始登录: {user}")
                logger.debug(f"登录URL: {login_url}")
                
                async with self.session.post(login_url, json=data) as response:
                    logger.debug(f"登录响应状态码: {response.status}")
                    
                    if response.status == 200:
                        result = await response.json()
                        logger.debug(f"登录响应: {result}")
                        
                        if 'token' in result:
                            # 解析token信息
                            self.token_info = self._parse_token(result['token'])
                            
                            # 更新session headers
                            if self.session:
                                self.session.headers.update({
                                    'Authorization': f'Bearer {result["token"]}'
                                })
                            
                            self.stats['successful_requests'] += 1
                            logger.info("登录成功")
                            return True, "登录成功"
                        else:
                            error_msg = "登录响应格式错误：缺少token"
                            logger.error(error_msg)
                            self.stats['failed_requests'] += 1
                            return False, error_msg
                    else:
                        error_text = await response.text()
                        error_msg = f"登录失败: {response.status} - {error_text}"
                        logger.error(error_msg)
                        self.stats['failed_requests'] += 1
                        return False, error_msg

        except aiohttp.ClientError as e:
            error_msg = f"网络请求失败: {str(e)}"
            logger.error(error_msg)
            self.stats['failed_requests'] += 1
            return False, error_msg
        except Exception as e:
            error_msg = f"登录异常: {str(e)}"
            logger.error(error_msg)
            self.stats['failed_requests'] += 1
            return False, error_msg
    
    async def smart_accounting(self, description: str, sender_name: str = None) -> Tuple[bool, str]:
        """
        异步智能记账

        Args:
            description: 记账描述
            sender_name: 发送者名称（可选）

        Returns:
            Tuple[bool, str]: (是否成功, 结果消息)
        """
        # 检查aiohttp可用性
        if not AIOHTTP_AVAILABLE:
            error_msg = "aiohttp库未安装，无法进行记账操作。请安装: pip install aiohttp"
            logger.error(error_msg)
            self.stats['failed_requests'] += 1
            return False, error_msg

        # 使用超时机制避免死锁
        try:
            async with asyncio.timeout(30):  # 30秒超时
                return await self._smart_accounting_internal(description, sender_name)
        except asyncio.TimeoutError:
            error_msg = f"记账请求超时: {description[:50]}..."
            logger.error(error_msg)
            self.stats['failed_requests'] += 1
            return False, error_msg
        except Exception as e:
            error_msg = f"记账请求异常: {str(e)}"
            logger.error(error_msg)
            self.stats['failed_requests'] += 1
            return False, error_msg

    async def _smart_accounting_internal(self, description: str, sender_name: str = None) -> Tuple[bool, str]:
        """
        内部智能记账实现（移除全局锁避免死锁）

        Args:
            description: 记账描述
            sender_name: 发送者名称（可选）

        Returns:
            Tuple[bool, str]: (是否成功, 结果消息)
        """
        # 移除全局锁，避免异步任务冲突导致的死锁
        # 改为使用局部锁保护关键资源
        try:
            self.stats['total_requests'] += 1

            # 检查token（移除锁，避免死锁）
            if not self.token_info or not self.token_info.token:
                # 尝试自动登录
                if self.config.auto_login:
                    success, message = await self.login()
                    if not success:
                        error_msg = f"未登录且自动登录失败: {message}"
                        logger.error(error_msg)
                        self.stats['failed_requests'] += 1
                        return False, error_msg
                else:
                    error_msg = "未登录且未启用自动登录"
                    logger.error(error_msg)
                    self.stats['failed_requests'] += 1
                    return False, error_msg

            # 检查token是否过期
            if self.token_info.is_expired():
                success, message = await self.login()
                if not success:
                    error_msg = f"Token已过期且刷新失败: {message}"
                    logger.error(error_msg)
                    self.stats['failed_requests'] += 1
                    return False, error_msg

            # 确保会话已初始化
            if not self.session:
                await self.initialize()

            # 构建记账请求
            url = f"{self.config.server_url.rstrip('/')}/api/ai/smart-accounting/direct"
            data = {
                "description": description,
                "accountBookId": self.config.account_book_id
            }

            # 添加发送者信息
            if sender_name:
                data["userName"] = sender_name

            headers = {
                'Authorization': f'Bearer {self.token_info.token}',
                'Content-Type': 'application/json'
            }

            logger.info(f"调用智能记账API: {description[:50]}...")
            logger.debug(f"请求URL: {url}")
            logger.debug(f"请求数据: {data}")

            # 设置请求超时
            timeout = aiohttp.ClientTimeout(total=self.config.request_timeout)
            async with self.session.post(url, json=data, headers=headers, timeout=timeout) as response:
                    logger.debug(f"记账响应状态码: {response.status}")
                    
                    if response.status == 401:
                        # 认证失败，尝试重新登录
                        logger.warning("认证失败，尝试重新登录")
                        success, message = await self.login()
                        if success:
                            # 使用新token重试
                            headers['Authorization'] = f'Bearer {self.token_info.token}'
                            async with self.session.post(url, json=data, headers=headers) as retry_response:
                                if retry_response.status in [200, 201]:  # 200 OK 或 201 Created 都表示成功
                                    result = await retry_response.json()
                                    success_msg = self._parse_accounting_response(result)
                                    self.stats['successful_requests'] += 1
                                    logger.info(f"智能记账成功（重试后，状态码: {retry_response.status}）")
                                    return True, success_msg
                                elif retry_response.status == 400:
                                    # 400状态码可能是"消息与记账无关"
                                    try:
                                        result = await retry_response.json()
                                        if 'info' in result and '消息与记账无关' in result['info']:
                                            logger.info("API返回：消息与记账无关（重试后）")
                                            self.stats['successful_requests'] += 1
                                            return True, "信息与记账无关"
                                        else:
                                            error_msg = f"请求错误（重试后）: {retry_response.status} - {result}"
                                            logger.error(error_msg)
                                            self.stats['failed_requests'] += 1
                                            return False, error_msg
                                    except:
                                        error_text = await retry_response.text()
                                        if '消息与记账无关' in error_text:
                                            logger.info("API返回：消息与记账无关（重试后）")
                                            self.stats['successful_requests'] += 1
                                            return True, "信息与记账无关"
                                        else:
                                            error_msg = f"请求错误（重试后）: {retry_response.status} - {error_text}"
                                            logger.error(error_msg)
                                            self.stats['failed_requests'] += 1
                                            return False, error_msg
                                else:
                                    error_text = await retry_response.text()
                                    error_msg = f"记账失败（重试后）: {retry_response.status} - {error_text}"
                                    logger.error(error_msg)
                                    self.stats['failed_requests'] += 1
                                    return False, error_msg
                        else:
                            error_msg = f"重新登录失败: {message}"
                            logger.error(error_msg)
                            self.stats['failed_requests'] += 1
                            return False, error_msg
                    elif response.status in [200, 201]:  # 200 OK 或 201 Created 都表示成功
                        result = await response.json()
                        success_msg = self._parse_accounting_response(result)
                        self.stats['successful_requests'] += 1
                        logger.info(f"智能记账成功 (状态码: {response.status})")
                        return True, success_msg
                    elif response.status == 400:
                        # 400状态码可能是"消息与记账无关"
                        try:
                            result = await response.json()
                            if 'info' in result and '消息与记账无关' in result['info']:
                                logger.info("API返回：消息与记账无关")
                                self.stats['successful_requests'] += 1  # 这不算失败，只是无关
                                return True, "信息与记账无关"
                            else:
                                # 其他400错误
                                error_msg = f"请求错误: {response.status} - {result}"
                                logger.error(error_msg)
                                self.stats['failed_requests'] += 1
                                return False, error_msg
                        except:
                            # 如果无法解析JSON，使用原始文本
                            error_text = await response.text()
                            if '消息与记账无关' in error_text:
                                logger.info("API返回：消息与记账无关")
                                self.stats['successful_requests'] += 1
                                return True, "信息与记账无关"
                            else:
                                error_msg = f"请求错误: {response.status} - {error_text}"
                                logger.error(error_msg)
                                self.stats['failed_requests'] += 1
                                return False, error_msg
                    else:
                        error_text = await response.text()
                        error_msg = f"记账失败: {response.status} - {error_text}"
                        logger.error(error_msg)
                        self.stats['failed_requests'] += 1
                        return False, error_msg

        except aiohttp.ClientError as e:
            error_msg = f"网络请求失败: {str(e)}"
            logger.error(error_msg)
            self.stats['failed_requests'] += 1
            return False, error_msg
        except Exception as e:
            error_msg = f"智能记账异常: {str(e)}"
            logger.error(error_msg)
            self.stats['failed_requests'] += 1
            return False, error_msg

    async def get_account_books(self) -> Tuple[bool, str, List[Dict[str, Any]]]:
        """
        获取账本列表

        Returns:
            Tuple[bool, str, List[Dict[str, Any]]]: (是否成功, 消息, 账本列表)
        """
        async with self._lock:
            try:
                self.stats['total_requests'] += 1

                # 检查token
                if not self.token_info or not self.token_info.token:
                    # 尝试自动登录
                    if self.config.auto_login:
                        success, message = await self.login()
                        if not success:
                            error_msg = f"未登录且自动登录失败: {message}"
                            logger.error(error_msg)
                            self.stats['failed_requests'] += 1
                            return False, error_msg, []
                    else:
                        error_msg = "未登录且未启用自动登录"
                        logger.error(error_msg)
                        self.stats['failed_requests'] += 1
                        return False, error_msg, []

                # 检查token是否过期
                if self.token_info.is_expired():
                    success, message = await self.login()
                    if not success:
                        error_msg = f"Token已过期且刷新失败: {message}"
                        logger.error(error_msg)
                        self.stats['failed_requests'] += 1
                        return False, error_msg, []

                # 确保会话已初始化
                if not self.session:
                    await self.initialize()

                # 构建请求
                url = f"{self.config.server_url.rstrip('/')}/api/account-books"
                headers = {
                    'Authorization': f'Bearer {self.token_info.token}',
                    'Content-Type': 'application/json'
                }

                logger.info("获取账本列表")
                logger.debug(f"请求URL: {url}")

                async with self.session.get(url, headers=headers) as response:
                    logger.debug(f"账本列表响应状态码: {response.status}")

                    if response.status == 200:
                        result = await response.json()
                        books = result.get('data', [])
                        self.stats['successful_requests'] += 1
                        logger.info(f"获取账本列表成功，共{len(books)}个账本")
                        return True, "获取成功", books
                    elif response.status == 401:
                        # 认证失败，尝试重新登录
                        logger.warning("认证失败，尝试重新登录")
                        success, message = await self.login()
                        if success:
                            # 使用新token重试
                            headers['Authorization'] = f'Bearer {self.token_info.token}'
                            async with self.session.get(url, headers=headers) as retry_response:
                                if retry_response.status == 200:
                                    result = await retry_response.json()
                                    books = result.get('data', [])
                                    self.stats['successful_requests'] += 1
                                    logger.info(f"获取账本列表成功（重试后），共{len(books)}个账本")
                                    return True, "获取成功", books
                                else:
                                    error_text = await retry_response.text()
                                    error_msg = f"获取失败（重试后）: {retry_response.status} - {error_text}"
                                    logger.error(error_msg)
                                    self.stats['failed_requests'] += 1
                                    return False, error_msg, []
                        else:
                            error_msg = f"重新登录失败: {message}"
                            logger.error(error_msg)
                            self.stats['failed_requests'] += 1
                            return False, error_msg, []
                    else:
                        error_text = await response.text()
                        error_msg = f"获取失败: {response.status} - {error_text}"
                        logger.error(error_msg)
                        self.stats['failed_requests'] += 1
                        return False, error_msg, []

            except aiohttp.ClientError as e:
                error_msg = f"网络请求失败: {str(e)}"
                logger.error(error_msg)
                self.stats['failed_requests'] += 1
                return False, error_msg, []
            except Exception as e:
                error_msg = f"获取账本列表异常: {str(e)}"
                logger.error(error_msg)
                self.stats['failed_requests'] += 1
                return False, error_msg, []

    def get_token(self) -> Optional[str]:
        """
        获取有效token

        Returns:
            Optional[str]: token字符串，如果无效则返回None
        """
        if not self.token_info:
            return None

        if self.token_info.is_expired():
            return None

        return self.token_info.token

    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息

        Returns:
            Dict[str, Any]: 统计信息字典
        """
        return self.stats.copy()

    def _parse_token(self, token: str) -> Optional[TokenInfo]:
        """
        解析token

        Args:
            token: JWT token字符串

        Returns:
            Optional[TokenInfo]: 解析后的token信息
        """
        try:
            # 解析JWT token
            parts = token.split('.')
            if len(parts) >= 2:
                payload = parts[1]
                # 添加padding
                payload += '=' * (4 - len(payload) % 4)
                decoded = base64.b64decode(payload)
                token_data = json.loads(decoded)

                expires_at = None
                if 'exp' in token_data:
                    expires_at = datetime.fromtimestamp(token_data['exp'])

                return TokenInfo(
                    token=token,
                    expires_at=expires_at,
                    user_id=token_data.get('id', ''),
                    email=token_data.get('email', '')
                )
            else:
                # 非JWT格式，创建简单的token信息
                return TokenInfo(token=token)

        except Exception as e:
            logger.warning(f"解析token失败: {e}")
            return TokenInfo(token=token)

    def _parse_accounting_response(self, result: Dict[str, Any]) -> str:
        """
        解析记账响应（参考旧版代码，支持多种API格式）

        Args:
            result: API响应结果

        Returns:
            格式化的消息
        """
        try:
            # 检查是否有smartAccountingResult字段（智能记账API的新格式）
            if 'smartAccountingResult' in result:
                return self._format_smart_accounting_response(result)

            # 检查是否有data字段（只为记账API的格式）
            elif 'data' in result:
                return self._format_zhiwei_accounting_response(result)

            # 简单的成功响应
            else:
                return "✅ 记账成功！"

        except Exception as e:
            logger.warning(f"解析记账响应失败: {e}")
            return "✅ 记账成功！"

    def _format_smart_accounting_response(self, result: Dict[str, Any]) -> str:
        """
        格式化智能记账API响应（参考旧版代码）

        Args:
            result: API响应结果

        Returns:
            格式化的消息
        """
        try:
            smart_result = result.get('smartAccountingResult', {})

            # 检查是否与记账无关
            if smart_result.get('isRelevant') is False:
                return "信息与记账无关"

            # 检查是否有错误信息
            if 'error' in smart_result:
                error_msg = smart_result.get('error', '记账失败')
                if 'token' in error_msg.lower() and ('limit' in error_msg.lower() or '限制' in error_msg):
                    return f"💳 token使用达到限制: {error_msg}"
                elif 'rate' in error_msg.lower() or '频繁' in error_msg or 'too many' in error_msg.lower():
                    return f"⏱️ 访问过于频繁: {error_msg}"
                else:
                    return f"❌ 记账失败: {error_msg}"

            # 检查是否有记账成功的信息
            if 'amount' in smart_result:
                # 记账成功，格式化详细信息
                message_lines = ["✅ 记账成功！"]

                # 基本信息 - 使用note字段作为明细，而不是originalDescription
                # note字段包含处理后的记账明细（如"买香蕉"），originalDescription包含原始消息（如"买香蕉，27元"）
                description = smart_result.get('note', smart_result.get('description', ''))
                if description:
                    message_lines.append(f"📝 明细：{description}")

                # 日期信息
                date = smart_result.get('date', '')
                if date:
                    # 简化日期格式
                    try:
                        if 'T' in date:
                            date = date.split('T')[0]
                        message_lines.append(f"📅 日期：{date}")
                    except:
                        message_lines.append(f"📅 日期：{date}")

                # 方向和分类信息
                # 从API响应中提取正确的字段
                direction = smart_result.get('type', smart_result.get('direction', ''))  # type字段是主要的
                category = smart_result.get('categoryName', smart_result.get('category', ''))  # categoryName是主要的

                # 添加调试日志
                logger.debug(f"格式化响应 - direction: '{direction}', category: '{category}'")

                # 获取分类图标
                category_icon = self._get_category_icon(category)

                # 获取方向信息
                type_info = self._get_direction_info(direction)

                # 构建方向和分类信息行
                direction_category_parts = []
                if direction:
                    direction_category_parts.append(f"{type_info['icon']} 方向：{type_info['text']}")
                if category:
                    direction_category_parts.append(f"分类：{category_icon}{category}")

                if direction_category_parts:
                    message_lines.append("；".join(direction_category_parts))
                elif direction:  # 只有方向没有分类
                    message_lines.append(f"{type_info['icon']} 方向：{type_info['text']}")
                elif category:  # 只有分类没有方向
                    message_lines.append(f"📂 分类：{category_icon}{category}")

                # 金额信息
                amount = smart_result.get('amount', '')
                if amount:
                    message_lines.append(f"💰 金额：{amount}元")

                # 预算信息 - 只有当budgetName等于"个人预算"时才显示所有者姓名
                budget_name = smart_result.get('budgetName', smart_result.get('budget', ''))
                budget_owner = smart_result.get('budgetOwnerName', smart_result.get('budgetOwner', ''))

                if budget_name:
                    if budget_name == "个人预算" and budget_owner:
                        message_lines.append(f"📊 预算：{budget_name}（{budget_owner}）")
                    else:
                        message_lines.append(f"📊 预算：{budget_name}")

                return "\n".join(message_lines)
            else:
                # 没有amount字段，可能是失败或其他情况
                error_msg = smart_result.get('message', '记账失败')
                return f"❌ 记账失败: {error_msg}"

        except Exception as e:
            logger.error(f"格式化智能记账响应失败: {e}")
            # 如果格式化失败，尝试提取基本信息
            try:
                smart_result = result.get('smartAccountingResult', {})
                amount = smart_result.get('amount', '')
                description = smart_result.get('originalDescription', '')
                if amount and description:
                    return f"✅ 记账成功！\n💰 {description} {amount}元"
                else:
                    return "✅ 记账完成"
            except:
                return "✅ 记账完成"

    def _format_zhiwei_accounting_response(self, result: Dict[str, Any]) -> str:
        """
        格式化只为记账API响应

        Args:
            result: API响应结果

        Returns:
            格式化的消息
        """
        try:
            data = result.get('data', {})

            # 构建成功消息
            success_parts = ["✅ 记账成功！"]

            if 'description' in data:
                success_parts.append(f"📝 明细：{data['description']}")

            if 'date' in data:
                success_parts.append(f"📅 日期：{data['date']}")

            # 处理方向和分类信息
            direction = data.get('direction', '支出')
            category = data.get('category', '')

            # 添加调试日志
            logger.debug(f"只为记账格式化 - direction: '{direction}', category: '{category}'")

            # 获取分类图标和方向信息
            category_icon = self._get_category_icon(category)
            type_info = self._get_direction_info(direction)

            # 构建方向和分类信息行
            direction_category_parts = []
            if direction:
                direction_category_parts.append(f"{type_info['icon']} 方向：{type_info['text']}")
            if category:
                direction_category_parts.append(f"分类：{category_icon}{category}")

            if direction_category_parts:
                success_parts.append("；".join(direction_category_parts))

            # 处理金额信息
            amount = data.get('amount', '')
            if amount:
                success_parts.append(f"💰 金额：{amount}元")

            if 'budget' in data:
                budget_info = data['budget']
                if isinstance(budget_info, dict):
                    remaining = budget_info.get('remaining', 0)
                    success_parts.append(f"📊 预算余额：{remaining}元")
                elif isinstance(budget_info, str):
                    success_parts.append(f"📊 预算：{budget_info}")

            return "\n".join(success_parts)

        except Exception as e:
            logger.warning(f"格式化只为记账响应失败: {e}")
            return "✅ 记账成功！"

    def _get_category_icon(self, category: str) -> str:
        """
        获取分类图标

        Args:
            category: 分类名称

        Returns:
            对应的图标
        """
        category_icons = {
            '餐饮': '🍽️',
            '交通': '🚗',
            '购物': '🛒',
            '娱乐': '🎮',
            '医疗': '🏥',
            '教育': '📚',
            '学习': '📝',
            '日用': '🧴',  # 添加日用分类
            '住房': '🏠',
            '通讯': '📱',
            '服装': '👕',
            '美容': '💄',
            '运动': '⚽',
            '旅游': '✈️',
            '投资': '💰',
            '保险': '🛡️',
            '转账': '💸',
            '红包': '🧧',
            '工资': '💼',
            '奖金': '🎁',
            '兼职': '👨‍💻',
            '理财': '📈',
            '其他': '📦'
        }
        return category_icons.get(category, '📂')

    def _get_direction_info(self, direction: str) -> Dict[str, str]:
        """
        获取方向信息

        Args:
            direction: 方向（支出/收入等）

        Returns:
            包含图标和文本的字典
        """
        direction_map = {
            '支出': {'icon': '💸', 'text': '支出'},
            '收入': {'icon': '💰', 'text': '收入'},
            'expense': {'icon': '💸', 'text': '支出'},
            'EXPENSE': {'icon': '💸', 'text': '支出'},  # API返回的大写格式
            'income': {'icon': '💰', 'text': '收入'},
            'INCOME': {'icon': '💰', 'text': '收入'},   # API返回的大写格式
            'transfer': {'icon': '🔄', 'text': '转账'},
            'TRANSFER': {'icon': '🔄', 'text': '转账'}  # API返回的大写格式
        }

        # 默认值
        default_info = {'icon': '💸', 'text': direction or '支出'}

        return direction_map.get(direction.lower() if direction else '', default_info)
