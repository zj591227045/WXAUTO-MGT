"""
API接口实现

提供Web管理界面所需的API接口。
"""

from fastapi import FastAPI, APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, List, Optional, Any, Union
import platform
import psutil
import time
import datetime
import os
import sys
import logging
import traceback
import aiohttp
import asyncio

from wxauto_mgt.utils.logging import logger
from wxauto_mgt.core.api_client import instance_manager
from wxauto_mgt.core.service_platform_manager import platform_manager, rule_manager
from wxauto_mgt.core.message_listener import message_listener
from wxauto_mgt.data.db_manager import db_manager
from wxauto_mgt.data.config_store import config_store
from wxauto_mgt.config import get_version

# 创建API路由器
api_router = APIRouter()

# 初始化标志
_initialized = False

async def verify_request_auth(request: Request):
    """
    验证请求的认证状态

    Args:
        request: FastAPI请求对象

    Raises:
        HTTPException: 认证失败时抛出
    """
    try:
        from .security import check_password_required, verify_token

        # 检查是否需要密码验证
        password_required = await check_password_required()
        if not password_required:
            # 如果没有设置密码，则跳过验证
            return

        # 首先尝试从Cookie获取token
        token = request.cookies.get("auth_token")

        # 如果Cookie中没有token，尝试从Authorization头获取
        if not token:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header[7:]  # 移除"Bearer "前缀

        # 如果仍然没有token，返回认证错误
        if not token:
            raise HTTPException(
                status_code=401,
                detail="需要认证令牌",
                headers={"WWW-Authenticate": "Bearer"}
            )

        # 验证token
        payload = verify_token(token)
        if payload is None:
            raise HTTPException(
                status_code=401,
                detail="无效的认证令牌",
                headers={"WWW-Authenticate": "Bearer"}
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"认证验证失败: {e}")
        raise HTTPException(
            status_code=500,
            detail="认证服务错误"
        )

async def initialize_managers():
    """初始化管理器"""
    global _initialized
    if _initialized:
        return

    try:
        # 初始化数据库
        if not hasattr(db_manager, '_initialized') or not db_manager._initialized:
            # 获取数据库路径
            import os
            data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')
            if not os.path.exists(data_dir):
                os.makedirs(data_dir)
            db_path = os.path.join(data_dir, 'wxauto_mgt.db')
            await db_manager.initialize(db_path)
            logger.info("数据库管理器初始化完成")

        # 初始化服务平台管理器
        if not hasattr(platform_manager, '_initialized') or not platform_manager._initialized:
            await platform_manager.initialize()
            logger.info("服务平台管理器初始化完成")

        # 初始化规则管理器
        if not hasattr(rule_manager, '_initialized') or not rule_manager._initialized:
            await rule_manager.initialize()
            logger.info("规则管理器初始化完成")

        # 初始化消息监听器
        if hasattr(message_listener, 'initialize') and not getattr(message_listener, '_initialized', False):
            await message_listener.initialize()
            logger.info("消息监听器初始化完成")

        _initialized = True
        logger.info("所有管理器初始化完成")
    except Exception as e:
        logger.error(f"初始化管理器失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise

# 添加测试API路由
@api_router.get("/test")
async def test_api():
    """API测试接口"""
    # 确保管理器已初始化
    await initialize_managers()
    return {"status": "ok", "message": "API测试成功"}

# 登录API
@api_router.post("/auth/login")
async def login(request: Request):
    """
    用户登录接口

    请求体:
        {
            "password": "用户密码"
        }

    返回:
        {
            "code": 0,
            "message": "登录成功",
            "data": {
                "token": "JWT令牌",
                "expires_in": 86400
            }
        }
    """
    try:
        from .security import authenticate_password, create_access_token, check_password_required

        # 检查是否需要密码验证
        password_required = await check_password_required()
        if not password_required:
            # 如果没有设置密码，直接返回成功（无需token）
            return {
                "code": 0,
                "message": "无需密码验证",
                "data": {
                    "token": None,
                    "expires_in": 0,
                    "password_required": False
                }
            }

        # 获取请求数据
        data = await request.json()
        password = data.get("password", "")

        if not password:
            raise HTTPException(status_code=400, detail="密码不能为空")

        # 验证密码
        is_valid = await authenticate_password(password)
        if not is_valid:
            raise HTTPException(status_code=401, detail="密码错误")

        # 创建JWT令牌
        token_data = {"sub": "web_user", "type": "access"}
        token = create_access_token(token_data)

        # 创建响应并设置Cookie
        from fastapi.responses import JSONResponse
        response = JSONResponse({
            "code": 0,
            "message": "登录成功",
            "data": {
                "token": token,
                "expires_in": 86400,  # 24小时
                "password_required": True
            }
        })

        # 设置Cookie，有效期24小时
        response.set_cookie(
            key="auth_token",
            value=token,
            max_age=24 * 60 * 60,  # 24小时
            httponly=True,  # 防止XSS攻击
            secure=False,   # 开发环境使用HTTP
            samesite="lax"  # CSRF保护
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"登录失败: {e}")
        raise HTTPException(status_code=500, detail="登录服务错误")

# 退出登录API
@api_router.post("/auth/logout")
async def logout():
    """
    用户退出登录接口

    返回:
        {
            "code": 0,
            "message": "退出成功"
        }
    """
    try:
        # 创建响应并清除Cookie
        from fastapi.responses import JSONResponse
        response = JSONResponse({
            "code": 0,
            "message": "退出成功"
        })

        # 删除认证Cookie
        response.delete_cookie("auth_token")

        return response

    except Exception as e:
        logger.error(f"退出登录失败: {e}")
        raise HTTPException(status_code=500, detail="退出登录服务错误")

# 检查认证状态API
@api_router.get("/auth/status")
async def auth_status():
    """
    检查认证状态

    返回:
        {
            "code": 0,
            "message": "成功",
            "data": {
                "password_required": true/false
            }
        }
    """
    try:
        from .security import check_password_required

        password_required = await check_password_required()

        return {
            "code": 0,
            "message": "成功",
            "data": {
                "password_required": password_required
            }
        }

    except Exception as e:
        logger.error(f"检查认证状态失败: {e}")
        raise HTTPException(status_code=500, detail="认证服务错误")

# 实例状态API
@api_router.get("/instances/{instance_id}/status")
async def get_instance_status(instance_id: str, request: Request):
    """
    获取实例状态和uptime信息

    Args:
        instance_id: 实例ID
    """
    try:
        # 验证认证
        await verify_request_auth(request)
        # 记录API调用
        logger.debug(f"获取实例状态 API 被调用，参数：instance_id={instance_id}")

        # 从数据库获取实例信息
        query = "SELECT * FROM instances WHERE instance_id = ?"
        instance = await db_manager.fetchone(query, (instance_id,))

        if not instance:
            raise HTTPException(status_code=404, detail=f"实例 {instance_id} 不存在")

        # 获取实例的API URL和API KEY
        base_url = instance.get('base_url')
        api_key = instance.get('api_key')

        if not base_url or not api_key:
            raise HTTPException(status_code=400, detail=f"实例 {instance_id} 缺少API URL或API KEY")

        # 构建实例health API URL
        import requests
        if not base_url.endswith('/'):
            base_url += '/'

        status_url = f"{base_url}api/health"
        headers = {
            'X-API-Key': api_key,
            'Content-Type': 'application/json'
        }

        # 获取状态信息
        logger.debug(f"向实例 {instance_id} 发送状态请求: {status_url}")
        response = requests.get(status_url, headers=headers, timeout=5)

        # 检查响应状态
        if response.status_code != 200:
            logger.warning(f"实例 {instance_id} 状态请求失败，状态码: {response.status_code}")
            return {
                "code": 1,
                "message": "实例离线或无法访问",
                "data": {
                    "status": "offline",
                    "uptime": 0,
                    "wechat_status": "disconnected"
                }
            }

        # 解析响应
        result = response.json()
        logger.debug(f"实例 {instance_id} 状态响应: {result}")

        # 如果响应中已经包含code字段，直接返回
        if 'code' in result:
            return result

        # 否则包装响应数据
        return {
            "code": 0,
            "message": "获取成功",
            "data": result
        }

    except Exception as e:
        logger.warning(f"获取实例 {instance_id} 状态失败: {e}")
        logger.warning(traceback.format_exc())
        return {
            "code": 1,
            "message": f"获取状态失败: {str(e)}",
            "data": {
                "status": "error",
                "uptime": 0,
                "wechat_status": "disconnected"
            }
        }

# 系统资源API
@api_router.get("/system/resources")
async def get_system_resources(request: Request, instance_id: Optional[str] = None):
    """
    获取系统资源使用情况

    Args:
        instance_id: 可选的实例ID，如果提供则返回该实例的资源使用情况
    """
    try:
        # 验证认证
        await verify_request_auth(request)
        # 记录API调用
        logger.debug(f"获取系统资源 API 被调用，参数：instance_id={instance_id}")

        # 如果提供了实例ID，尝试获取该实例的资源使用情况
        if instance_id:
            try:
                # 从数据库获取实例信息
                query = "SELECT * FROM instances WHERE instance_id = ?"
                instance = await db_manager.fetchone(query, (instance_id,))

                if not instance:
                    raise HTTPException(status_code=404, detail=f"实例 {instance_id} 不存在")

                # 获取实例的API URL和API KEY
                base_url = instance.get('base_url')
                api_key = instance.get('api_key')

                if not base_url or not api_key:
                    raise HTTPException(status_code=400, detail=f"实例 {instance_id} 缺少API URL或API KEY")

                # 构建请求URL
                import requests

                # 先获取健康状态信息（包含uptime）
                health_url = f"{base_url}/api/health"
                resources_url = f"{base_url}/api/system/resources"
                headers = {'X-API-Key': api_key}

                # 获取健康状态
                logger.debug(f"向实例 {instance_id} 发送健康状态请求: {health_url}")
                health_data = None
                try:
                    health_response = requests.get(health_url, headers=headers, timeout=5)
                    if health_response.status_code == 200:
                        health_data = health_response.json()
                        logger.debug(f"实例 {instance_id} 健康状态响应: {health_data}")
                except Exception as e:
                    logger.warning(f"获取实例 {instance_id} 健康状态失败: {e}")

                # 获取资源信息
                logger.debug(f"向实例 {instance_id} 发送资源请求: {resources_url}")
                response = requests.get(resources_url, headers=headers, timeout=5)

                # 检查响应状态
                if response.status_code != 200:
                    logger.warning(f"实例 {instance_id} 资源请求失败，状态码: {response.status_code}")
                    # 返回默认资源信息
                    return {
                        "code": 0,
                        "message": "获取成功（使用默认值）",
                        "data": {
                            "cpu": {
                                "core_count": 4,
                                "usage_percent": 0
                            },
                            "memory": {
                                "used": 0,
                                "total": 0,
                                "usage_percent": 0,
                                "free": 0
                            }
                        }
                    }

                # 解析响应
                result = response.json()
                logger.debug(f"实例 {instance_id} 资源响应: {result}")

                # 确保响应中包含启动时间
                if 'data' in result and isinstance(result['data'], dict):
                    data = result['data']

                    # 如果响应中没有uptime字段，尝试获取
                    if 'uptime' not in data:
                        try:
                            # 尝试从实例信息中获取
                            if instance.get('uptime'):
                                data['uptime'] = instance.get('uptime')
                            # 尝试从实例的启动时间计算
                            elif instance.get('start_time'):
                                start_time = instance.get('start_time')
                                uptime_seconds = time.time() - start_time
                                days, remainder = divmod(uptime_seconds, 86400)
                                hours, remainder = divmod(remainder, 3600)
                                minutes, seconds = divmod(remainder, 60)
                                data['uptime'] = f"{int(days)}天{int(hours)}小时{int(minutes)}分钟"
                            # 尝试从实例的runtime字段获取
                            elif instance.get('runtime'):
                                data['uptime'] = instance.get('runtime')
                            # 尝试从响应中的其他字段获取
                            elif 'runtime' in data:
                                data['uptime'] = data['runtime']
                            elif 'boot_time' in data:
                                boot_time = data['boot_time']
                                if isinstance(boot_time, (int, float)):
                                    uptime_seconds = time.time() - boot_time
                                    days, remainder = divmod(uptime_seconds, 86400)
                                    hours, remainder = divmod(remainder, 3600)
                                    minutes, seconds = divmod(remainder, 60)
                                    data['uptime'] = f"{int(days)}天{int(hours)}小时{int(minutes)}分钟"
                            else:
                                # 默认值
                                data['uptime'] = "未知"
                        except Exception as e:
                            logger.warning(f"计算实例 {instance_id} 的运行时间失败: {e}")
                            data['uptime'] = "未知"

                    # 如果响应中没有runtime字段，使用uptime
                    if 'runtime' not in data and 'uptime' in data:
                        data['runtime'] = data['uptime']

                # 返回结果
                return result

            except Exception as e:
                logger.warning(f"获取实例 {instance_id} 资源使用情况失败: {e}")
                logger.warning(traceback.format_exc())
                # 返回默认资源信息
                return {
                    "code": 0,
                    "message": "获取成功（使用默认值）",
                    "data": {
                        "cpu": {
                            "core_count": 4,
                            "usage_percent": 0
                        },
                        "memory": {
                            "used": 0,
                            "total": 0,
                            "usage_percent": 0,
                            "free": 0
                        }
                    }
                }

        # 获取系统资源使用情况
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        memory_used_mb = memory.used / (1024 * 1024)
        memory_total_mb = memory.total / (1024 * 1024)
        memory_percent = memory.percent
        memory_free_mb = memory.available / (1024 * 1024)

        return {
            "code": 0,
            "message": "获取成功",
            "data": {
                "cpu": {
                    "core_count": psutil.cpu_count(),
                    "usage_percent": cpu_percent
                },
                "memory": {
                    "used": round(memory_used_mb),
                    "total": round(memory_total_mb),
                    "usage_percent": memory_percent,
                    "free": round(memory_free_mb)
                }
            }
        }
    except Exception as e:
        logger.error(f"获取系统资源失败: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"获取系统资源失败: {str(e)}")

# 系统状态API
@api_router.get("/system/status")
async def get_system_status(request: Request):
    """获取系统状态"""
    try:
        # 验证认证
        await verify_request_auth(request)

        # 确保管理器已初始化
        await initialize_managers()

        # 获取系统启动时间
        boot_time = psutil.boot_time()
        boot_time_str = datetime.datetime.fromtimestamp(boot_time).strftime("%Y-%m-%d %H:%M:%S")
        uptime_seconds = time.time() - boot_time

        # 格式化运行时间
        days, remainder = divmod(uptime_seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, _ = divmod(remainder, 60)  # 使用_忽略秒数
        uptime_str = f"{int(days)}天{int(hours)}小时{int(minutes)}分钟"

        # 获取系统资源使用情况
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        memory_used_gb = memory.used / (1024 ** 3)
        memory_total_gb = memory.total / (1024 ** 3)
        memory_percent = memory.percent

        # 获取磁盘使用情况
        disk = psutil.disk_usage('/')
        disk_used_gb = disk.used / (1024 ** 3)
        disk_total_gb = disk.total / (1024 ** 3)
        disk_percent = disk.percent

        # 获取wxauto_mgt版本
        version = get_version()

        # 获取实例状态
        try:
            # 从数据库获取实例列表
            instances_query = "SELECT * FROM instances WHERE enabled = 1"
            db_instances = await db_manager.fetchall(instances_query)

            # 初始化计数器
            online_count = 0
            offline_count = 0
            error_count = 0

            # 检查每个实例的实际连接状态
            for instance in db_instances:
                instance_id = instance.get('instance_id')
                base_url = instance.get('base_url')
                api_key = instance.get('api_key')

                if not base_url or not api_key:
                    offline_count += 1
                    continue

                try:
                    # 调用健康检查API获取微信连接状态
                    import requests
                    health_url = f"{base_url}/api/health"
                    headers = {'X-API-Key': api_key}

                    health_response = requests.get(health_url, headers=headers, timeout=5)
                    if health_response.status_code == 200:
                        health_data = health_response.json()
                        if 'data' in health_data and health_data['data'].get('wechat_status') == 'connected':
                            online_count += 1
                        else:
                            offline_count += 1
                    else:
                        offline_count += 1
                except Exception as e:
                    logger.warning(f"检查实例 {instance_id} 连接状态失败: {e}")
                    offline_count += 1

        except Exception as e:
            logger.warning(f"获取实例状态失败: {e}")
            logger.warning(traceback.format_exc())
            online_count = 0
            offline_count = 0
            error_count = 0

        # 获取消息处理状态
        today_start = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_start_timestamp = int(today_start.timestamp())

        # 获取今日消息数量
        try:
            today_messages_query = "SELECT COUNT(*) as count FROM messages WHERE create_time >= ?"
            today_messages_result = await db_manager.fetchone(today_messages_query, (today_start_timestamp,))
            today_messages_count = today_messages_result['count'] if today_messages_result else 0
        except Exception:
            today_messages_count = 0

        # 获取待处理消息数量
        try:
            pending_messages_query = "SELECT COUNT(*) as count FROM messages WHERE delivery_status = 0"
            pending_messages_result = await db_manager.fetchone(pending_messages_query)
            pending_messages_count = pending_messages_result['count'] if pending_messages_result else 0
        except Exception:
            pending_messages_count = 0

        # 获取消息总数
        try:
            total_messages_query = "SELECT COUNT(*) as count FROM messages"
            total_messages_result = await db_manager.fetchone(total_messages_query)
            total_messages_count = total_messages_result['count'] if total_messages_result else 0
        except Exception:
            total_messages_count = 0

        # 获取监听对象总数
        try:
            # 直接从数据库获取监听对象总数
            listeners_query = "SELECT COUNT(*) as count FROM listeners"
            listeners_result = await db_manager.fetchone(listeners_query)
            listeners_count = listeners_result['count'] if listeners_result and 'count' in listeners_result else 0

            # 如果数据库中没有记录，尝试从消息监听器获取
            if listeners_count == 0 and hasattr(message_listener, 'get_all_listeners'):
                all_listeners = message_listener.get_all_listeners()
                listeners_count = len(all_listeners) if all_listeners else 0

            # 记录实际的监听对象数量
            logger.debug(f"获取到实际监听对象数量: {listeners_count}")

            # 不再强制设置为至少1个
        except Exception as e:
            logger.warning(f"获取监听对象总数失败: {e}")
            listeners_count = 0  # 出错时默认为0

        # 计算消息处理成功率
        try:
            success_query = "SELECT COUNT(*) as count FROM messages WHERE delivery_status = 1"
            success_result = await db_manager.fetchone(success_query)
            success_count = success_result['count'] if success_result else 0

            total_query = "SELECT COUNT(*) as count FROM messages WHERE delivery_status IN (0, 1, 2)"
            total_result = await db_manager.fetchone(total_query)
            total_count = total_result['count'] if total_result else 0

            success_rate = round((success_count / total_count) * 100) if total_count > 0 else 100
        except Exception:
            success_rate = 100

        # 获取最近活跃的实例
        active_instance_name = ""  # 默认为空
        try:
            # 查询最新的消息记录对应的实例
            latest_message_query = """
                SELECT m.instance_id, i.name
                FROM messages m
                JOIN instances i ON m.instance_id = i.instance_id
                ORDER BY m.create_time DESC
                LIMIT 1
            """
            latest_message = await db_manager.fetchone(latest_message_query)
            if latest_message and 'name' in latest_message:
                active_instance_name = latest_message['name']
            else:
                # 如果没有消息记录，尝试获取任意一个实例名称
                instance_query = "SELECT name FROM instances LIMIT 1"
                instance_result = await db_manager.fetchone(instance_query)
                if instance_result and 'name' in instance_result:
                    active_instance_name = instance_result['name']
        except Exception as e:
            logger.warning(f"获取最近活跃实例失败: {e}")
            # 保持默认值为空

        return {
            "system_status": {
                "status": "running",
                "uptime": uptime_str,
                "version": version
            },
            "instance_status": {
                "online": online_count,
                "offline": offline_count,
                "error": error_count,
                "active_instance": active_instance_name
            },
            "message_processing": {
                "today_messages": today_messages_count,
                "success_rate": success_rate,
                "pending": pending_messages_count,
                "total_messages": total_messages_count,
                "listeners_count": listeners_count
            },
            "system_resources": {
                "cpu_percent": cpu_percent,
                "memory_used_gb": round(memory_used_gb, 2),
                "memory_total_gb": round(memory_total_gb, 2),
                "memory_percent": memory_percent,
                "disk_used_gb": round(disk_used_gb, 2),
                "disk_total_gb": round(disk_total_gb, 2),
                "disk_percent": disk_percent
            }
        }
    except Exception as e:
        logger.error(f"获取系统状态失败: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"获取系统状态失败: {str(e)}")

# 实例状态缓存（避免频繁请求）
_instance_cache = {}
_cache_timeout = 30  # 缓存30秒

async def get_instance_status_cached(instance_id: str, base_url: str, api_key: str):
    """获取实例状态（带缓存）"""
    import time
    current_time = time.time()

    # 检查缓存
    if instance_id in _instance_cache:
        cache_data = _instance_cache[instance_id]
        if current_time - cache_data['timestamp'] < _cache_timeout:
            logger.debug(f"使用缓存的实例 {instance_id} 状态")
            return cache_data['data']

    # 缓存过期或不存在，重新获取
    import requests
    import asyncio

    result = {
        'status': 'OFFLINE',
        'runtime': '未知',
        'cpu_percent': 0,
        'memory_used': 0,
        'memory_total': 0,
        'memory_percent': 0
    }

    try:
        headers = {'X-API-Key': api_key}

        # 并发发送健康检查和资源请求
        async def fetch_health():
            try:
                health_url = f"{base_url}/api/health"
                async with aiohttp.ClientSession() as session:
                    async with session.get(health_url, headers=headers, timeout=aiohttp.ClientTimeout(total=2)) as response:
                        if response.status == 200:
                            return await response.json()
                        return None
            except:
                return None

        async def fetch_resources():
            try:
                resources_url = f"{base_url}/api/system/resources"
                async with aiohttp.ClientSession() as session:
                    async with session.get(resources_url, headers=headers, timeout=aiohttp.ClientTimeout(total=2)) as response:
                        if response.status == 200:
                            return await response.json()
                        return None
            except:
                return None

        # 并发执行请求
        health_data, resources_data = await asyncio.gather(
            fetch_health(),
            fetch_resources(),
            return_exceptions=True
        )

        # 处理健康检查结果
        if health_data and 'data' in health_data:
            data = health_data['data']

            # 更新状态
            if data.get('wechat_status') == 'connected':
                result['status'] = 'ONLINE'

            # 格式化运行时间
            if 'uptime' in data:
                uptime_seconds = data['uptime']
                days, remainder = divmod(uptime_seconds, 86400)
                hours, remainder = divmod(remainder, 3600)
                minutes, _ = divmod(remainder, 60)

                if days > 0:
                    result['runtime'] = f"{int(days)}天{int(hours)}小时{int(minutes)}分钟"
                elif hours > 0:
                    result['runtime'] = f"{int(hours)}小时{int(minutes)}分钟"
                else:
                    result['runtime'] = f"{int(minutes)}分钟"

        # 处理资源信息结果
        if resources_data and 'data' in resources_data:
            data = resources_data['data']

            if 'cpu' in data and 'usage_percent' in data['cpu']:
                result['cpu_percent'] = data['cpu']['usage_percent']

            if 'memory' in data:
                memory_data = data['memory']
                result['memory_used'] = round(memory_data.get('used', 0) / 1024, 1)
                result['memory_total'] = round(memory_data.get('total', 0) / 1024, 1)
                result['memory_percent'] = memory_data.get('usage_percent', 0)

    except Exception as e:
        logger.warning(f"获取实例 {instance_id} 状态失败: {e}")

    # 更新缓存
    _instance_cache[instance_id] = {
        'timestamp': current_time,
        'data': result
    }

    return result

# 实例列表API
@api_router.get("/instances")
async def get_instances(request: Request):
    """获取所有实例"""
    try:
        # 验证认证
        await verify_request_auth(request)

        # 确保管理器已初始化
        await initialize_managers()

        # 尝试从数据库获取实例列表
        result = []
        try:
            # 构建查询
            instances_query = "SELECT * FROM instances"
            db_instances = await db_manager.fetchall(instances_query)

            # 获取每个实例的详细信息
            for instance in db_instances:
                instance_id = instance.get('instance_id')

                # 获取实例消息数量
                try:
                    messages_query = "SELECT COUNT(*) as count FROM messages WHERE instance_id = ?"
                    messages_result = await db_manager.fetchone(messages_query, (instance_id,))
                    messages_count = messages_result['count'] if messages_result else 0
                except Exception:
                    messages_count = 0

                # 获取实例监听对象数量
                try:
                    # 首先尝试从数据库获取监听对象数量
                    listeners_query = "SELECT COUNT(*) as count FROM listeners WHERE instance_id = ?"
                    listeners_result = await db_manager.fetchone(listeners_query, (instance_id,))

                    if listeners_result and 'count' in listeners_result:
                        listeners_count = listeners_result['count']
                    else:
                        # 如果数据库查询失败，尝试从消息监听器获取
                        if hasattr(message_listener, 'get_listeners_by_instance'):
                            listeners_count = len(message_listener.get_listeners_by_instance(instance_id))
                        else:
                            listeners_count = 0
                except Exception as e:
                    logger.warning(f"获取实例 {instance_id} 监听对象数量失败: {e}")
                    listeners_count = 0

                # 构建实例信息（不包含资源信息，资源信息通过专门的API获取）
                result.append({
                    **instance,
                    "messages_count": messages_count,
                    "listeners_count": listeners_count
                })
        except Exception as e:
            logger.warning(f"从数据库获取实例列表失败: {e}")

        return result
    except Exception as e:
        logger.error(f"获取实例列表失败: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"获取实例列表失败: {str(e)}")

# 添加实例API
@api_router.post("/instances")
async def create_instance(request: Request):
    """创建新的实例"""
    try:
        # 验证认证
        await verify_request_auth(request)

        # 确保管理器已初始化
        await initialize_managers()

        data = await request.json()
        logger.debug(f"收到创建实例请求: {data}")

        # 验证必需字段
        required_fields = ['name', 'base_url', 'api_key']
        for field in required_fields:
            if field not in data:
                raise HTTPException(status_code=400, detail=f"缺少必需字段: {field}")

        # 生成实例ID（如果没有提供）
        if 'instance_id' not in data or not data['instance_id']:
            import uuid
            data['instance_id'] = f"wxauto_{uuid.uuid4().hex[:8]}"

        # 调用 Python 端的配置管理器添加实例
        from wxauto_mgt.core.config_manager import config_manager
        from wxauto_mgt.core.api_client import instance_manager

        # 准备配置参数
        config_params = {}
        if 'config' in data and isinstance(data['config'], dict):
            config_params = data['config']

        # 添加实例到配置管理器
        result = await config_manager.add_instance(
            instance_id=data['instance_id'],
            name=data['name'],
            base_url=data['base_url'],
            api_key=data['api_key'],
            enabled=bool(data.get('enabled', True)),
            **config_params
        )

        if result:
            # 添加实例到API客户端
            instance_manager.add_instance(
                data['instance_id'],
                data['base_url'],
                data['api_key'],
                config_params.get('timeout', 30)
            )

            logger.info(f"成功创建实例: {data['instance_id']}")
            return {"code": 0, "message": "实例创建成功", "data": {"instance_id": data['instance_id']}}
        else:
            raise HTTPException(status_code=500, detail="实例创建失败")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建实例失败: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"创建实例失败: {str(e)}")

# 更新实例API
@api_router.put("/instances/{instance_id}")
async def update_instance(instance_id: str, request: Request):
    """更新实例"""
    try:
        # 验证认证
        await verify_request_auth(request)

        # 确保管理器已初始化
        await initialize_managers()

        data = await request.json()
        logger.debug(f"收到更新实例请求: {instance_id}, 数据: {data}")

        # 验证必需字段
        required_fields = ['name', 'base_url', 'api_key']
        for field in required_fields:
            if field not in data:
                raise HTTPException(status_code=400, detail=f"缺少必需字段: {field}")

        # 调用 Python 端的配置管理器更新实例
        from wxauto_mgt.core.config_manager import config_manager
        from wxauto_mgt.core.api_client import instance_manager

        # 准备更新数据
        update_data = {
            'name': data['name'],
            'base_url': data['base_url'],
            'api_key': data['api_key'],
            'enabled': bool(data.get('enabled', True))
        }

        # 添加配置参数
        if 'config' in data and isinstance(data['config'], dict):
            update_data['config'] = data['config']

        # 更新实例配置
        success = await config_manager.update_instance(instance_id, update_data)

        if success:
            # 更新API客户端中的实例（先移除再添加）
            timeout = 30
            if 'config' in data and isinstance(data['config'], dict):
                timeout = data['config'].get('timeout', 30)

            # 移除旧的实例
            instance_manager.remove_instance(instance_id)
            # 添加新的实例
            instance_manager.add_instance(
                instance_id,
                data['base_url'],
                data['api_key'],
                timeout
            )

            logger.info(f"成功更新实例: {instance_id}")
            return {"code": 0, "message": "实例更新成功"}
        else:
            raise HTTPException(status_code=404, detail="实例不存在或更新失败")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新实例失败: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"更新实例失败: {str(e)}")

# 删除实例API
@api_router.delete("/instances/{instance_id}")
async def delete_instance(instance_id: str, request: Request):
    """删除实例"""
    try:
        # 验证认证
        await verify_request_auth(request)

        # 确保管理器已初始化
        await initialize_managers()

        # 调用 Python 端的配置管理器删除实例
        from wxauto_mgt.core.config_manager import config_manager
        from wxauto_mgt.core.api_client import instance_manager

        success = await config_manager.remove_instance(instance_id)

        if success:
            # 从API客户端中移除实例
            instance_manager.remove_instance(instance_id)

            logger.info(f"成功删除实例: {instance_id}")
            return {"code": 0, "message": "实例删除成功"}
        else:
            # 不抛出HTTPException，直接返回错误响应
            logger.warning(f"删除实例失败: {instance_id} 不存在")
            return {"code": 1, "message": "实例不存在或删除失败"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除实例失败: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"删除实例失败: {str(e)}")

# 服务平台列表API
@api_router.get("/platforms")
async def get_platforms(request: Request):
    """获取所有服务平台"""
    try:
        # 验证认证
        await verify_request_auth(request)

        # 确保管理器已初始化
        await initialize_managers()

        # 从服务平台管理器获取所有平台
        platforms = await platform_manager.get_all_platforms()

        # 处理敏感信息
        for platform in platforms:
            # 对于包含API密钥的配置，隐藏密钥
            if 'config' in platform and isinstance(platform['config'], dict):
                config = platform['config']
                if 'api_key' in config and config['api_key']:
                    # 只显示前4位和后4位，中间用星号代替
                    api_key = config['api_key']
                    if len(api_key) > 8:
                        config['api_key'] = api_key[:4] + '*' * (len(api_key) - 8) + api_key[-4:]
                    else:
                        config['api_key'] = '********'

        return platforms
    except Exception as e:
        logger.error(f"获取服务平台列表失败: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"获取服务平台列表失败: {str(e)}")

# 消息转发规则列表API
@api_router.get("/rules")
async def get_rules(request: Request, instance_id: Optional[str] = None):
    """获取所有消息转发规则"""
    try:
        # 验证认证
        await verify_request_auth(request)

        # 确保管理器已初始化
        await initialize_managers()

        # 从规则管理器获取所有规则
        rules = await rule_manager.get_all_rules()

        # 如果指定了实例ID，则过滤规则
        if instance_id:
            rules = [rule for rule in rules if rule['instance_id'] == instance_id or rule['instance_id'] == '*']

        # 按优先级排序（降序）
        rules.sort(key=lambda x: (-x.get('priority', 0), x.get('rule_id', '')))

        return rules
    except Exception as e:
        logger.error(f"获取消息转发规则列表失败: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"获取消息转发规则列表失败: {str(e)}")

# 添加服务平台API
@api_router.post("/platforms")
async def create_platform(request: Request):
    """创建新的服务平台"""
    try:
        # 验证认证
        await verify_request_auth(request)

        # 确保管理器已初始化
        await initialize_managers()

        data = await request.json()

        # 验证必需字段
        required_fields = ['name', 'type', 'config']
        for field in required_fields:
            if field not in data:
                raise HTTPException(status_code=400, detail=f"缺少必需字段: {field}")

        # 调用 Python 端的平台管理器
        platform_id = await platform_manager.register_platform(
            data['type'],
            data['name'],
            data['config'],
            enabled=data.get('enabled', True)
        )

        if platform_id:
            return {"code": 0, "message": "平台创建成功", "data": {"platform_id": platform_id}}
        else:
            raise HTTPException(status_code=500, detail="平台创建失败")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建服务平台失败: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"创建服务平台失败: {str(e)}")

# 更新服务平台API
@api_router.put("/platforms/{platform_id}")
async def update_platform(platform_id: str, request: Request):
    """更新服务平台"""
    try:
        # 验证认证
        await verify_request_auth(request)

        data = await request.json()

        # 验证必需字段
        required_fields = ['name', 'config']
        for field in required_fields:
            if field not in data:
                raise HTTPException(status_code=400, detail=f"缺少必需字段: {field}")

        # 处理启用状态
        enabled = data.get('enabled', True)

        # 调用 Python 端的平台管理器
        success = await platform_manager.update_platform_simple(
            platform_id,
            data['name'],
            data['config']
        )

        # 如果更新成功，再更新启用状态
        if success and 'enabled' in data:
            await platform_manager.set_platform_enabled(platform_id, enabled)

        if success:
            return {"code": 0, "message": "平台更新成功"}
        else:
            raise HTTPException(status_code=404, detail="平台不存在或更新失败")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新服务平台失败: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"更新服务平台失败: {str(e)}")

# 删除服务平台API
@api_router.delete("/platforms/{platform_id}")
async def delete_platform(platform_id: str, request: Request):
    """删除服务平台"""
    try:
        # 验证认证
        await verify_request_auth(request)

        # 调用 Python 端的平台管理器
        success = await platform_manager.delete_platform(platform_id)

        if success:
            return {"code": 0, "message": "平台删除成功"}
        else:
            raise HTTPException(status_code=404, detail="平台不存在或删除失败")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除服务平台失败: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"删除服务平台失败: {str(e)}")

# 测试服务平台连接API
@api_router.post("/platforms/{platform_id}/test")
async def test_platform_connection(platform_id: str, request: Request):
    """测试服务平台连接"""
    try:
        # 验证认证
        await verify_request_auth(request)

        # 获取平台实例
        platform = await platform_manager.get_platform(platform_id)
        if not platform:
            raise HTTPException(status_code=404, detail="平台不存在")

        # 调用平台的测试连接方法
        result = await platform.test_connection()

        return {"code": 0, "message": "测试完成", "data": result}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"测试平台连接失败: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"测试平台连接失败: {str(e)}")

# 添加消息转发规则API
@api_router.post("/rules")
async def create_rule(request: Request):
    """创建新的消息转发规则"""
    try:
        # 验证认证
        await verify_request_auth(request)

        # 确保管理器已初始化
        await initialize_managers()

        data = await request.json()

        # 验证必需字段
        required_fields = ['name', 'instance_id', 'chat_pattern', 'platform_id']
        for field in required_fields:
            if field not in data:
                raise HTTPException(status_code=400, detail=f"缺少必需字段: {field}")

        # 调用 Python 端的规则管理器
        rule_id = await rule_manager.add_rule(
            name=data['name'],
            instance_id=data['instance_id'],
            chat_pattern=data['chat_pattern'],
            platform_id=data['platform_id'],
            priority=data.get('priority', 0),
            only_at_messages=data.get('only_at_messages', 0),
            at_name=data.get('at_name', ''),
            reply_at_sender=data.get('reply_at_sender', 0)
        )

        if rule_id:
            return {"code": 0, "message": "规则创建成功", "data": {"rule_id": rule_id}}
        else:
            raise HTTPException(status_code=500, detail="规则创建失败")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建消息转发规则失败: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"创建消息转发规则失败: {str(e)}")

# 更新消息转发规则API
@api_router.put("/rules/{rule_id}")
async def update_rule(rule_id: str, request: Request):
    """更新消息转发规则"""
    try:
        # 验证认证
        await verify_request_auth(request)

        data = await request.json()

        # 验证必需字段
        required_fields = ['name', 'instance_id', 'chat_pattern', 'platform_id']
        for field in required_fields:
            if field not in data:
                raise HTTPException(status_code=400, detail=f"缺少必需字段: {field}")

        # 调用 Python 端的规则管理器
        success = await rule_manager.update_rule(
            rule_id=rule_id,
            name=data['name'],
            instance_id=data['instance_id'],
            chat_pattern=data['chat_pattern'],
            platform_id=data['platform_id'],
            priority=data.get('priority', 0),
            only_at_messages=data.get('only_at_messages', 0),
            at_name=data.get('at_name', ''),
            reply_at_sender=data.get('reply_at_sender', 0)
        )

        if success:
            return {"code": 0, "message": "规则更新成功"}
        else:
            raise HTTPException(status_code=404, detail="规则不存在或更新失败")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新消息转发规则失败: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"更新消息转发规则失败: {str(e)}")

# 删除消息转发规则API
@api_router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: str, request: Request):
    """删除消息转发规则"""
    try:
        # 验证认证
        await verify_request_auth(request)

        # 调用 Python 端的规则管理器
        success = await rule_manager.delete_rule(rule_id)

        if success:
            return {"code": 0, "message": "规则删除成功"}
        else:
            raise HTTPException(status_code=404, detail="规则不存在或删除失败")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除消息转发规则失败: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"删除消息转发规则失败: {str(e)}")

# 添加监听对象API
@api_router.post("/listeners")
async def add_listener(request: Request):
    """添加监听对象"""
    try:
        # 验证认证
        await verify_request_auth(request)

        data = await request.json()

        # 验证必需字段
        required_fields = ['instance_id', 'chat_name']
        for field in required_fields:
            if field not in data:
                raise HTTPException(status_code=400, detail=f"缺少必需字段: {field}")

        # 调用 Python 端的消息监听器（标记为手动添加，不受超时限制）
        success = await message_listener.add_listener(
            instance_id=data['instance_id'],
            who=data['chat_name'],
            conversation_id="",  # 初始时会话ID为空
            manual_added=True,  # 手动添加的监听对象不受超时限制
            save_pic=True,
            save_file=True,
            save_voice=True,
            parse_url=True
        )

        if success:
            return {"code": 0, "message": "监听对象添加成功"}
        else:
            raise HTTPException(status_code=500, detail="监听对象添加失败")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"添加监听对象失败: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"添加监听对象失败: {str(e)}")

# 删除监听对象API
@api_router.delete("/listeners")
async def remove_listener(request: Request):
    """删除监听对象"""
    try:
        # 验证认证
        await verify_request_auth(request)

        data = await request.json()

        # 验证必需字段
        required_fields = ['instance_id', 'chat_name']
        for field in required_fields:
            if field not in data:
                raise HTTPException(status_code=400, detail=f"缺少必需字段: {field}")

        # 调用 Python 端的消息监听器
        success = await message_listener.remove_listener(
            instance_id=data['instance_id'],
            who=data['chat_name']
        )

        if success:
            return {"code": 0, "message": "监听对象删除成功"}
        else:
            raise HTTPException(status_code=404, detail="监听对象不存在或删除失败")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除监听对象失败: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"删除监听对象失败: {str(e)}")

# 监听对象列表API
@api_router.get("/listeners")
async def get_listeners(request: Request, instance_id: Optional[str] = None, since: Optional[int] = None):
    """
    获取所有监听对象

    Args:
        instance_id: 可选的实例ID，如果提供则只返回该实例的监听对象
        since: 可选的时间戳，如果提供则只返回自该时间戳以来更新的监听对象
    """
    try:
        # 验证认证
        await verify_request_auth(request)
        # 记录API调用
        logger.debug(f"获取监听对象列表 API 被调用，参数：instance_id={instance_id}, since={since}")

        # 尝试从数据库获取监听对象
        listeners = []
        try:
            # 构建查询条件，添加排序逻辑
            query = "SELECT * FROM listeners WHERE 1=1"
            params = []

            if instance_id:
                query += " AND instance_id = ?"
                params.append(instance_id)

            if since:
                query += " AND update_time > ?"
                params.append(since)

            # 添加排序：按状态排序（活跃在前），然后按最后消息时间降序排序
            query += " ORDER BY CASE WHEN status = 'active' THEN 0 ELSE 1 END, last_message_time DESC"

            # 执行查询
            db_listeners = await db_manager.fetchall(query, tuple(params))
            if db_listeners:
                listeners = db_listeners
                logger.debug(f"从数据库获取到 {len(listeners)} 个监听对象")
        except Exception as e:
            logger.warning(f"从数据库获取监听对象失败: {e}")

        # 如果指定了实例ID，则过滤监听对象
        if instance_id and listeners:
            listeners = [listener for listener in listeners if listener.get('instance_id') == instance_id]
            logger.debug(f"过滤后剩余 {len(listeners)} 个监听对象")

        # 添加额外信息并统一字段名
        for listener in listeners:
            # 统一字段名：将 'who' 字段映射为 'chat_name'
            if 'who' in listener:
                listener['chat_name'] = listener['who']

            # 设置状态信息
            status = listener.get('status', 'active')
            listener['status'] = status

            # 获取最后一条消息时间
            try:
                # 始终尝试获取最新的消息时间
                listener_instance_id = listener.get('instance_id')
                chat_name = listener.get('chat_name') or listener.get('who')

                # 查询最后一条消息
                query = """
                    SELECT create_time FROM messages
                    WHERE instance_id = ? AND chat_name = ?
                    ORDER BY create_time DESC LIMIT 1
                """
                result = await db_manager.fetchone(query, (listener_instance_id, chat_name))
                if result and 'create_time' in result:
                    listener['last_message_time'] = result['create_time']
                    logger.debug(f"更新监听对象 {chat_name} 的最后消息时间为 {result['create_time']}")
            except Exception as e:
                logger.warning(f"获取监听对象最后消息时间失败: {e}")
                # 保留现有的last_message_time值
                listener['last_message_time'] = listener.get('last_message_time', 0)

        return listeners
    except Exception as e:
        logger.error(f"获取监听对象列表失败: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"获取监听对象列表失败: {str(e)}")

# 消息列表API
@api_router.get("/messages")
async def get_messages(
    request: Request,
    instance_id: Optional[str] = None,
    chat_name: Optional[str] = None,
    limit: int = 50,
    since: Optional[int] = None
):
    """
    获取消息列表

    Args:
        instance_id: 可选的实例ID
        chat_name: 可选的聊天对象名称
        limit: 返回消息数量限制
        since: 可选的时间戳，如果提供则只返回自该时间戳以来的消息
    """
    try:
        # 验证认证
        await verify_request_auth(request)
        # 记录API调用
        logger.debug(f"获取消息列表 API 被调用，参数：instance_id={instance_id}, chat_name={chat_name}, limit={limit}, since={since}")

        # 构建查询条件
        query = "SELECT * FROM messages WHERE 1=1"
        params = []

        if instance_id:
            query += " AND instance_id = ?"
            params.append(instance_id)

        if chat_name:
            query += " AND chat_name = ?"
            params.append(chat_name)

        if since:
            query += " AND create_time > ?"
            params.append(since)

        # 按时间降序排序，限制数量
        query += " ORDER BY create_time DESC LIMIT ?"
        params.append(limit)

        logger.debug(f"执行消息查询：{query} 参数：{params}")

        # 执行查询
        messages = await db_manager.fetchall(query, tuple(params))
        # logger.debug(f"查询到 {len(messages)} 条消息")  # 避免循环日志

        return messages
    except Exception as e:
        logger.error(f"获取消息列表失败: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"获取消息列表失败: {str(e)}")

# 日志API
@api_router.get("/logs")
async def get_logs(request: Request, limit: int = 50, since: Optional[int] = None):
    """
    获取最近的日志

    Args:
        limit: 返回日志数量限制
        since: 可选的时间戳，如果提供则只返回自该时间戳以来的日志
    """
    try:
        # 验证认证
        await verify_request_auth(request)
        # 记录API调用
        # logger.debug(f"获取日志 API 被调用，参数：limit={limit}, since={since}")  # 避免循环日志

        # 尝试从日志文件中读取日志
        logs = []

        try:
            # 获取日志文件路径
            import os
            from wxauto_mgt.utils.logging import get_log_file_path

            log_file = get_log_file_path()
            # logger.debug(f"日志文件路径: {log_file}")  # 避免循环日志

            if os.path.exists(log_file):
                # 读取日志文件的最后几行
                with open(log_file, 'r', encoding='utf-8') as f:
                    # 读取所有行
                    lines = f.readlines()
                    # logger.debug(f"日志文件共有 {len(lines)} 行")  # 避免循环日志

                    # 获取最后limit行
                    last_lines = lines[-limit*2:] if len(lines) > limit*2 else lines
                    # logger.debug(f"读取了最后 {len(last_lines)} 行进行解析")  # 避免循环日志

                    # 解析日志行
                    for line in last_lines:
                        try:
                            # 尝试解析日志行
                            # 格式示例: 2023-05-15 12:34:56.789 | INFO     | wxauto_mgt.core.message_listener:start:123 - 消息监听服务已启动
                            parts = line.strip().split(' | ', 2)
                            if len(parts) >= 3:
                                timestamp_str = parts[0].strip()
                                level = parts[1].strip()
                                message_part = parts[2].strip()

                                # 解析时间戳
                                import datetime
                                try:
                                    dt = datetime.datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S.%f')
                                    timestamp = int(dt.timestamp())
                                except ValueError:
                                    timestamp = int(time.time())

                                # 如果提供了since参数，则过滤早于since的日志
                                if since and timestamp <= since:
                                    continue

                                # 提取消息内容
                                message = message_part
                                if ' - ' in message_part:
                                    message = message_part.split(' - ', 1)[1]

                                logs.append({
                                    "timestamp": timestamp,
                                    "level": level,
                                    "message": message
                                })
                        except Exception as e:
                            # 如果解析失败，添加原始行
                            current_time = int(time.time())
                            # 如果提供了since参数，则过滤早于since的日志
                            if since and current_time <= since:
                                continue

                            logs.append({
                                "timestamp": current_time,
                                "level": "INFO",
                                "message": line.strip()
                            })

                    # logger.debug(f"成功解析了 {len(logs)} 条日志")  # 避免循环日志
        except Exception as e:
            logger.warning(f"从日志文件读取日志失败: {e}")

        # 按时间戳降序排序
        logs.sort(key=lambda x: x.get('timestamp', 0), reverse=True)

        # 限制数量
        logs = logs[:limit]
        # logger.debug(f"返回 {len(logs)} 条日志")  # 避免循环日志

        return logs
    except Exception as e:
        logger.error(f"获取日志失败: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"获取日志失败: {str(e)}")

# 记账平台相关API

@api_router.post("/platforms/zhiweijz")
async def create_zhiweijz_platform(request: Request):
    """创建只为记账平台"""
    try:
        # 验证认证
        await verify_request_auth(request)

        # 确保管理器已初始化
        await initialize_managers()

        data = await request.json()

        # 验证必需字段
        required_fields = ['name', 'server_url', 'username', 'password']
        for field in required_fields:
            if field not in data:
                raise HTTPException(status_code=400, detail=f"缺少必需字段: {field}")

        # 创建平台配置
        config = {
            'server_url': data['server_url'].rstrip('/'),
            'username': data['username'],
            'password': data['password'],
            'account_book_id': data.get('account_book_id', ''),
            'account_book_name': data.get('account_book_name', ''),
            'auto_login': data.get('auto_login', True),
            'token_refresh_interval': data.get('token_refresh_interval', 300),
            'request_timeout': data.get('request_timeout', 30),
            'max_retries': data.get('max_retries', 3)
        }

        # 注册平台
        platform_id = await platform_manager.register_platform(
            "zhiweijz",
            data['name'],
            config,
            enabled=data.get('enabled', True)
        )

        if platform_id:
            return {"code": 0, "message": "只为记账平台创建成功", "data": {"platform_id": platform_id}}
        else:
            raise HTTPException(status_code=500, detail="创建只为记账平台失败")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建只为记账平台失败: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"创建只为记账平台失败: {str(e)}")

@api_router.get("/accounting/records")
async def get_accounting_records(
    request: Request,
    platform_id: Optional[str] = None,
    instance_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    success_only: Optional[bool] = None
):
    """获取记账记录"""
    try:
        # 验证认证
        await verify_request_auth(request)

        # 确保管理器已初始化
        await initialize_managers()

        # 构建查询条件
        query = "SELECT * FROM accounting_records WHERE 1=1"
        params = []

        if platform_id:
            query += " AND platform_id = ?"
            params.append(platform_id)

        if instance_id:
            query += " AND instance_id = ?"
            params.append(instance_id)

        if success_only is not None:
            query += " AND success = ?"
            params.append(1 if success_only else 0)

        # 添加排序和分页
        query += " ORDER BY create_time DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        # 执行查询
        records = await db_manager.fetchall(query, tuple(params))

        # 获取总数
        count_query = "SELECT COUNT(*) as total FROM accounting_records WHERE 1=1"
        count_params = []

        if platform_id:
            count_query += " AND platform_id = ?"
            count_params.append(platform_id)

        if instance_id:
            count_query += " AND instance_id = ?"
            count_params.append(instance_id)

        if success_only is not None:
            count_query += " AND success = ?"
            count_params.append(1 if success_only else 0)

        total_result = await db_manager.fetchone(count_query, tuple(count_params))
        total = total_result['total'] if total_result else 0

        return {
            "code": 0,
            "message": "获取成功",
            "data": {
                "records": records,
                "total": total,
                "limit": limit,
                "offset": offset
            }
        }

    except Exception as e:
        logger.error(f"获取记账记录失败: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"获取记账记录失败: {str(e)}")

@api_router.get("/accounting/stats")
async def get_accounting_stats(request: Request, platform_id: Optional[str] = None):
    """获取记账统计信息"""
    try:
        # 验证认证
        await verify_request_auth(request)

        # 确保管理器已初始化
        await initialize_managers()

        # 构建查询条件
        if platform_id:
            query = "SELECT * FROM accounting_stats WHERE platform_id = ?"
            params = (platform_id,)
        else:
            query = "SELECT * FROM accounting_stats"
            params = ()

        # 执行查询
        stats = await db_manager.fetchall(query, params)

        return {
            "code": 0,
            "message": "获取成功",
            "data": stats
        }

    except Exception as e:
        logger.error(f"获取记账统计信息失败: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"获取记账统计信息失败: {str(e)}")

@api_router.post("/accounting/test")
async def test_accounting_connection(request: Request):
    """测试记账平台连接"""
    try:
        # 验证认证
        await verify_request_auth(request)

        data = await request.json()

        # 验证必需字段
        required_fields = ['server_url', 'username', 'password']
        for field in required_fields:
            if field not in data:
                raise HTTPException(status_code=400, detail=f"缺少必需字段: {field}")

        # 创建临时记账管理器进行测试
        from wxauto_mgt.core.async_accounting_manager import AsyncAccountingManager

        config = {
            'server_url': data['server_url'].rstrip('/'),
            'username': data['username'],
            'password': data['password'],
            'account_book_id': data.get('account_book_id', ''),
            'auto_login': True,
            'request_timeout': 30
        }

        async with AsyncAccountingManager(config) as manager:
            # 测试登录
            success, message = await manager.login()

            if success:
                # 测试获取账本列表
                books_success, books_message, books = await manager.get_account_books()

                return {
                    "code": 0,
                    "message": "连接测试成功",
                    "data": {
                        "login_success": True,
                        "login_message": message,
                        "books_success": books_success,
                        "books_message": books_message,
                        "account_books": books if books_success else []
                    }
                }
            else:
                return {
                    "code": 1,
                    "message": f"连接测试失败: {message}",
                    "data": {
                        "login_success": False,
                        "login_message": message,
                        "books_success": False,
                        "books_message": "",
                        "account_books": []
                    }
                }

    except Exception as e:
        logger.error(f"测试记账连接失败: {e}")
        logger.error(traceback.format_exc())
        return {
            "code": 1,
            "message": f"测试失败: {str(e)}",
            "data": {
                "login_success": False,
                "login_message": str(e),
                "books_success": False,
                "books_message": "",
                "account_books": []
            }
        }

# ==================== 固定监听配置API ====================

@api_router.get("/fixed-listeners")
async def get_fixed_listeners():
    """获取所有固定监听配置"""
    try:
        fixed_listeners = await message_listener.get_fixed_listeners()
        return {
            "code": 0,
            "message": "获取固定监听配置成功",
            "data": fixed_listeners
        }
    except Exception as e:
        logger.error(f"获取固定监听配置失败: {e}")
        return {
            "code": 1,
            "message": f"获取固定监听配置失败: {str(e)}",
            "data": []
        }

@api_router.post("/fixed-listeners")
async def add_fixed_listener(request: Request):
    """添加固定监听配置"""
    try:
        data = await request.json()
        session_name = data.get('session_name', '').strip()
        description = data.get('description', '').strip()
        enabled = bool(data.get('enabled', True))

        # 验证输入
        if not session_name:
            return {
                "code": 1,
                "message": "会话名称不能为空",
                "data": None
            }

        # 添加固定监听配置
        success = await message_listener.add_fixed_listener(session_name, description, enabled)

        if success:
            return {
                "code": 0,
                "message": "添加固定监听配置成功",
                "data": None
            }
        else:
            return {
                "code": 1,
                "message": "添加固定监听配置失败，可能会话名称已存在",
                "data": None
            }

    except Exception as e:
        logger.error(f"添加固定监听配置失败: {e}")
        return {
            "code": 1,
            "message": f"添加固定监听配置失败: {str(e)}",
            "data": None
        }

@api_router.put("/fixed-listeners/{listener_id}")
async def update_fixed_listener(listener_id: int, request: Request):
    """更新固定监听配置"""
    try:
        data = await request.json()
        session_name = data.get('session_name')
        description = data.get('description')
        enabled = data.get('enabled')

        # 验证会话名称（如果提供）
        if session_name is not None:
            session_name = session_name.strip()
            if not session_name:
                return {
                    "code": 1,
                    "message": "会话名称不能为空",
                    "data": None
                }

        # 处理描述（如果提供）
        if description is not None:
            description = description.strip()

        # 更新固定监听配置
        success = await message_listener.update_fixed_listener(
            listener_id, session_name, description, enabled
        )

        if success:
            return {
                "code": 0,
                "message": "更新固定监听配置成功",
                "data": None
            }
        else:
            return {
                "code": 1,
                "message": "更新固定监听配置失败，可能配置不存在或会话名称已存在",
                "data": None
            }

    except Exception as e:
        logger.error(f"更新固定监听配置失败: {e}")
        return {
            "code": 1,
            "message": f"更新固定监听配置失败: {str(e)}",
            "data": None
        }

@api_router.delete("/fixed-listeners/{listener_id}")
async def delete_fixed_listener(listener_id: int):
    """删除固定监听配置"""
    try:
        success = await message_listener.delete_fixed_listener(listener_id)

        if success:
            return {
                "code": 0,
                "message": "删除固定监听配置成功",
                "data": None
            }
        else:
            return {
                "code": 1,
                "message": "删除固定监听配置失败，可能配置不存在",
                "data": None
            }

    except Exception as e:
        logger.error(f"删除固定监听配置失败: {e}")
        return {
            "code": 1,
            "message": f"删除固定监听配置失败: {str(e)}",
            "data": None
        }

def register_api_routes(app: FastAPI):
    """
    注册API路由

    Args:
        app: FastAPI应用实例
    """
    app.include_router(api_router)
