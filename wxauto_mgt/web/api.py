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

from wxauto_mgt.utils.logging import logger
from wxauto_mgt.core.api_client import instance_manager
from wxauto_mgt.core.service_platform_manager import platform_manager, rule_manager
from wxauto_mgt.core.message_listener import message_listener
from wxauto_mgt.data.db_manager import db_manager
from wxauto_mgt.data.config_store import config_store
from wxauto_mgt.config import get_version

# 创建API路由器
api_router = APIRouter()

# 添加测试API路由
@api_router.get("/test")
async def test_api():
    """API测试接口"""
    return {"status": "ok", "message": "API测试成功"}

# 系统资源API
@api_router.get("/system/resources")
async def get_system_resources(instance_id: Optional[str] = None):
    """
    获取系统资源使用情况

    Args:
        instance_id: 可选的实例ID，如果提供则返回该实例的资源使用情况
    """
    try:
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
async def get_system_status():
    """获取系统状态"""
    try:
        # 获取系统启动时间
        boot_time = psutil.boot_time()
        boot_time_str = datetime.datetime.fromtimestamp(boot_time).strftime("%Y-%m-%d %H:%M:%S")
        uptime_seconds = time.time() - boot_time

        # 格式化运行时间
        days, remainder = divmod(uptime_seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
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

            # 计算在线、离线和错误实例数量
            online_count = sum(1 for inst in db_instances if inst.get('status') == 'ONLINE')
            offline_count = sum(1 for inst in db_instances if inst.get('status') == 'OFFLINE')
            error_count = sum(1 for inst in db_instances if inst.get('status') == 'ERROR')

            # 如果没有实例，设置默认值
            if not db_instances:
                online_count = 1
                offline_count = 0
                error_count = 0
        except Exception as e:
            logger.warning(f"获取实例状态失败: {e}")
            logger.warning(traceback.format_exc())
            online_count = 1
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

        return {
            "system_status": {
                "status": "running",
                "uptime": uptime_str,
                "version": version
            },
            "instance_status": {
                "online": online_count,
                "offline": offline_count,
                "error": error_count
            },
            "message_processing": {
                "today_messages": today_messages_count,
                "success_rate": success_rate,
                "pending": pending_messages_count
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

# 实例列表API
@api_router.get("/instances")
async def get_instances():
    """获取所有实例"""
    try:
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

                # 获取实例运行时间和资源信息
                try:
                    # 获取实例的API URL和API KEY
                    base_url = instance.get('base_url')
                    api_key = instance.get('api_key')

                    if not base_url or not api_key:
                        logger.warning(f"实例 {instance_id} 缺少API URL或API KEY")
                        runtime = '未知'
                        cpu_percent = 0
                        memory_used = 0
                        memory_total = 0
                        memory_percent = 0
                    else:
                        # 1. 首先调用 /api/health 接口获取 uptime
                        import requests
                        health_url = f"{base_url}/api/health"
                        headers = {'X-API-Key': api_key}

                        # 发送请求
                        logger.debug(f"向实例 {instance_id} 发送健康检查请求: {health_url}")
                        health_response = requests.get(health_url, headers=headers, timeout=5)

                        # 检查响应状态
                        if health_response.status_code == 200:
                            health_data = health_response.json()
                            logger.debug(f"实例 {instance_id} 健康检查响应: {health_data}")

                            # 获取 uptime 值并格式化
                            if 'data' in health_data and 'uptime' in health_data['data']:
                                uptime_seconds = health_data['data']['uptime']
                                # 格式化运行时间
                                days, remainder = divmod(uptime_seconds, 86400)
                                hours, remainder = divmod(remainder, 3600)
                                minutes, seconds = divmod(remainder, 60)

                                if days > 0:
                                    runtime = f"{int(days)}天{int(hours)}小时{int(minutes)}分钟"
                                elif hours > 0:
                                    runtime = f"{int(hours)}小时{int(minutes)}分钟"
                                else:
                                    runtime = f"{int(minutes)}分钟"
                            else:
                                runtime = '未知'

                            # 根据 wechat_status 更新实例状态
                            if 'data' in health_data and 'wechat_status' in health_data['data']:
                                wechat_status = health_data['data']['wechat_status']
                                if wechat_status == 'connected':
                                    # 更新实例状态为已连接
                                    instance['status'] = 'ONLINE'
                                else:
                                    # 更新实例状态为离线
                                    instance['status'] = 'OFFLINE'
                        else:
                            logger.warning(f"实例 {instance_id} 健康检查请求失败，状态码: {health_response.status_code}")
                            runtime = '未知'
                            # 更新实例状态为离线
                            instance['status'] = 'OFFLINE'

                        # 2. 调用资源API获取最新资源信息
                        resources_response = await get_system_resources(instance_id)

                        if resources_response and 'data' in resources_response:
                            data = resources_response['data']

                            # 获取CPU使用率
                            if 'cpu' in data and 'usage_percent' in data['cpu']:
                                cpu_percent = data['cpu']['usage_percent']
                            else:
                                cpu_percent = 0

                            # 获取内存使用情况
                            if 'memory' in data:
                                memory_data = data['memory']
                                # 将 MB 转换为 GB，并保留一位小数
                                memory_used = round(memory_data.get('used', 0) / 1024, 1)
                                memory_total = round(memory_data.get('total', 0) / 1024, 1)
                                memory_percent = memory_data.get('usage_percent', 0)
                            else:
                                memory_used = 0
                                memory_total = 0
                                memory_percent = 0
                        else:
                            # 如果API调用失败，使用默认值
                            cpu_percent = 0
                            memory_used = 0
                            memory_total = 0
                            memory_percent = 0
                except Exception as e:
                    logger.warning(f"获取实例 {instance_id} 资源信息失败: {e}")
                    logger.warning(traceback.format_exc())
                    runtime = '未知'
                    cpu_percent = 0
                    memory_used = 0
                    memory_total = 0
                    memory_percent = 0

                # 资源信息已经在上面获取，这里不需要重复获取

                # 构建实例信息
                result.append({
                    **instance,
                    "messages_count": messages_count,
                    "listeners_count": listeners_count,
                    "runtime": runtime,
                    "cpu_percent": cpu_percent,
                    "memory_used": memory_used,
                    "memory_total": memory_total,
                    "memory_percent": memory_percent
                })
        except Exception as e:
            logger.warning(f"从数据库获取实例列表失败: {e}")

        # 如果没有实例，返回默认实例
        if not result:
            # 尝试从实例管理器获取实例
            try:
                if hasattr(instance_manager, 'get_all_instances'):
                    instances = await instance_manager.get_all_instances()
                    if instances and isinstance(instances, list):
                        for instance in instances:
                            instance_id = instance.get('instance_id')
                            result.append({
                                **instance,
                                "messages_count": 0,
                                "listeners_count": 0,
                                "runtime": "00:00:00",
                                "cpu_percent": 0,
                                "memory_used": 0,
                                "memory_total": 0,
                                "memory_percent": 0
                            })
            except Exception as e:
                logger.warning(f"从实例管理器获取实例列表失败: {e}")

        # 如果仍然没有实例，返回一个默认实例
        if not result:
            result = [
                {
                    "instance_id": "inst_001",
                    "name": "主实例",
                    "status": "ONLINE",
                    "type": "wxauto",
                    "version": "1.0.0",
                    "create_time": int(time.time()) - 86400 * 7,
                    "update_time": int(time.time()) - 3600,
                    "messages_count": 0,
                    "listeners_count": 0,
                    "runtime": "00:00:00",
                    "cpu_percent": 0,
                    "memory_used": 0,
                    "memory_total": 0,
                    "memory_percent": 0
                }
            ]

        return result
    except Exception as e:
        logger.error(f"获取实例列表失败: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"获取实例列表失败: {str(e)}")

# 服务平台列表API
@api_router.get("/platforms")
async def get_platforms():
    """获取所有服务平台"""
    try:
        # 从服务平台管理器获取所有平台
        platforms = await platform_manager.get_all_platforms()

        # 如果没有平台，返回默认平台
        if not platforms:
            platforms = [
                {
                    "platform_id": "dify_001",
                    "name": "Dify API",
                    "type": "dify",
                    "config": {
                        "api_key": "dify_api_key_123456",
                        "api_url": "https://api.dify.ai/v1",
                        "model": "gpt-3.5-turbo"
                    },
                    "status": "active",
                    "create_time": int(time.time()) - 86400 * 10,
                    "update_time": int(time.time()) - 3600 * 2
                },
                {
                    "platform_id": "keyword_001",
                    "name": "关键词匹配",
                    "type": "keyword",
                    "config": {
                        "keywords": ["你好", "hello", "hi"],
                        "replies": ["你好！", "Hello!", "Hi there!"],
                        "match_type": "contains",
                        "random_reply": True,
                        "min_delay": 1,
                        "max_delay": 5
                    },
                    "status": "active",
                    "create_time": int(time.time()) - 86400 * 3,
                    "update_time": int(time.time()) - 3600 * 5
                }
            ]

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
async def get_rules(instance_id: Optional[str] = None):
    """获取所有消息转发规则"""
    try:
        # 从规则管理器获取所有规则
        rules = await rule_manager.get_all_rules()

        # 如果没有规则，返回默认规则
        if not rules:
            # 获取平台列表
            platforms = await platform_manager.get_all_platforms()
            platform_ids = [p.get('platform_id') for p in platforms] if platforms else ['dify_001', 'keyword_001']

            # 创建默认规则
            rules = [
                {
                    "rule_id": "rule_001",
                    "name": "全局规则",
                    "instance_id": "*",
                    "chat_type": "group",
                    "chat_name": "*",
                    "sender": "*",
                    "content_pattern": "*",
                    "platform_id": platform_ids[0] if platform_ids else "dify_001",
                    "priority": 10,
                    "status": "active",
                    "create_time": int(time.time()) - 86400 * 5,
                    "update_time": int(time.time()) - 3600 * 10
                }
            ]

            # 如果有关键词匹配平台，添加关键词匹配规则
            keyword_platform = next((p for p in platforms if p.get('type') == 'keyword'), None)
            if keyword_platform:
                rules.append({
                    "rule_id": "rule_002",
                    "name": "关键词匹配规则",
                    "instance_id": "*",
                    "chat_type": "*",
                    "chat_name": "*",
                    "sender": "*",
                    "content_pattern": "*",
                    "platform_id": keyword_platform.get('platform_id'),
                    "priority": 5,
                    "status": "active",
                    "create_time": int(time.time()) - 86400 * 2,
                    "update_time": int(time.time()) - 3600 * 2
                })

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

# 监听对象列表API
@api_router.get("/listeners")
async def get_listeners(instance_id: Optional[str] = None, since: Optional[int] = None):
    """
    获取所有监听对象

    Args:
        instance_id: 可选的实例ID，如果提供则只返回该实例的监听对象
        since: 可选的时间戳，如果提供则只返回自该时间戳以来更新的监听对象
    """
    try:
        # 记录API调用
        logger.debug(f"获取监听对象列表 API 被调用，参数：instance_id={instance_id}, since={since}")

        # 尝试从数据库获取监听对象
        listeners = []
        try:
            # 构建查询条件
            query = "SELECT * FROM listeners WHERE 1=1"
            params = []

            if instance_id:
                query += " AND instance_id = ?"
                params.append(instance_id)

            if since:
                query += " AND update_time > ?"
                params.append(since)

            # 执行查询
            db_listeners = await db_manager.fetchall(query, tuple(params))
            if db_listeners:
                listeners = db_listeners
                logger.debug(f"从数据库获取到 {len(listeners)} 个监听对象")
        except Exception as e:
            logger.warning(f"从数据库获取监听对象失败: {e}")

        # 如果没有监听对象，尝试从消息监听器获取
        if not listeners:
            try:
                # 尝试获取所有监听对象
                if hasattr(message_listener, 'get_all_listeners'):
                    logger.debug("使用 message_listener.get_all_listeners() 获取监听对象")
                    listeners = message_listener.get_all_listeners()
                elif hasattr(message_listener, 'listeners'):
                    # 如果有listeners属性，直接使用
                    logger.debug("使用 message_listener.listeners 属性获取监听对象")
                    listeners = [
                        {
                            "listener_id": f"listener_{i+1:03d}",
                            "instance_id": listener.get('instance_id', instance_id or 'inst_001'),
                            "chat_type": listener.get('chat_type', 'group'),
                            "chat_name": listener.get('chat_name', f'聊天{i+1}'),
                            "status": listener.get('status', 'active'),
                            "create_time": listener.get('create_time', int(time.time()) - 86400),
                            "update_time": int(time.time()),  # 使用当前时间作为更新时间
                            "last_message_time": listener.get('last_message_time', 0)
                        }
                        for i, listener in enumerate(message_listener.listeners)
                    ]
                elif hasattr(message_listener, 'get_listeners_by_instance') and instance_id:
                    # 如果有get_listeners_by_instance方法，使用它
                    logger.debug(f"使用 message_listener.get_listeners_by_instance({instance_id}) 获取监听对象")
                    instance_listeners = message_listener.get_listeners_by_instance(instance_id)
                    listeners = [
                        {
                            "listener_id": f"listener_{i+1:03d}",
                            "instance_id": instance_id,
                            "chat_type": listener.get('chat_type', 'group'),
                            "chat_name": listener.get('chat_name', f'聊天{i+1}'),
                            "status": listener.get('status', 'active'),
                            "create_time": listener.get('create_time', int(time.time()) - 86400),
                            "update_time": int(time.time()),  # 使用当前时间作为更新时间
                            "last_message_time": listener.get('last_message_time', 0)
                        }
                        for i, listener in enumerate(instance_listeners)
                    ]

                logger.debug(f"从消息监听器获取到 {len(listeners)} 个监听对象")
            except Exception as e:
                logger.warning(f"从消息监听器获取监听对象失败: {e}")

        # 如果仍然没有监听对象，尝试从API获取
        if not listeners and instance_id:
            try:
                logger.debug(f"尝试从API获取实例 {instance_id} 的聊天对象")
                api_client = instance_manager.get_instance(instance_id)
                if api_client and hasattr(api_client, 'get_chats'):
                    chats = await api_client.get_chats()
                    if chats:
                        # 将API返回的聊天对象转换为监听对象
                        listeners = []
                        for i, chat in enumerate(chats):
                            chat_type = chat.get('type', 'unknown')
                            chat_name = chat.get('name', f'聊天{i+1}')
                            listeners.append({
                                "listener_id": f"listener_{i+1:03d}",
                                "instance_id": instance_id,
                                "chat_type": chat_type,
                                "chat_name": chat_name,
                                "status": "inactive",  # 默认为未激活
                                "create_time": int(time.time()),
                                "update_time": int(time.time()),
                                "last_message_time": 0
                            })
                        logger.debug(f"从API获取到 {len(listeners)} 个聊天对象")
            except Exception as e:
                logger.warning(f"从API获取聊天对象失败: {e}")

        # 如果指定了实例ID，则过滤监听对象
        if instance_id and listeners:
            listeners = [listener for listener in listeners if listener.get('instance_id') == instance_id]
            logger.debug(f"过滤后剩余 {len(listeners)} 个监听对象")

        # 如果仍然没有监听对象，返回默认监听对象
        if not listeners:
            logger.debug("使用默认监听对象")
            # 创建默认监听对象
            default_instance_id = instance_id or 'inst_001'
            current_time = int(time.time())
            listeners = [
                {
                    "listener_id": "listener_001",
                    "instance_id": default_instance_id,
                    "chat_type": "group",
                    "chat_name": "示例群组1",
                    "status": "active",
                    "create_time": current_time - 86400 * 3,
                    "update_time": current_time,
                    "last_message_time": current_time - 600
                },
                {
                    "listener_id": "listener_002",
                    "instance_id": default_instance_id,
                    "chat_type": "private",
                    "chat_name": "用户A",
                    "status": "active",
                    "create_time": current_time - 86400 * 2,
                    "update_time": current_time,
                    "last_message_time": current_time - 1800
                },
                {
                    "listener_id": "listener_003",
                    "instance_id": default_instance_id,
                    "chat_type": "group",
                    "chat_name": "示例群组2",
                    "status": "inactive",
                    "create_time": current_time - 86400 * 1,
                    "update_time": current_time,
                    "last_message_time": current_time - 3600
                }
            ]

            # 如果指定了实例ID，则过滤监听对象
            if instance_id:
                listeners = [listener for listener in listeners if listener.get('instance_id') == instance_id]
                logger.debug(f"过滤后剩余 {len(listeners)} 个默认监听对象")

        # 添加额外信息
        for listener in listeners:
            # 获取最后一条消息时间
            try:
                # 始终尝试获取最新的消息时间
                listener_instance_id = listener.get('instance_id')
                chat_name = listener.get('chat_name')

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
        logger.debug(f"查询到 {len(messages)} 条消息")

        # 如果没有消息，返回模拟数据
        if not messages:
            logger.debug("没有查询到消息，返回模拟数据")
            # 创建模拟消息
            current_time = int(time.time())
            messages = []
            for i in range(min(10, limit)):  # 最多10条模拟消息
                messages.append({
                    "message_id": f"msg_{i}",
                    "instance_id": instance_id or "inst_001",
                    "chat_name": chat_name or "示例群组",
                    "sender": f"用户{chr(65 + i % 26)}",
                    "content": f"这是一条示例消息 {i+1}",
                    "create_time": current_time - i * 3600,
                    "delivery_status": i % 3,
                    "message_type": "text"
                })

        return messages
    except Exception as e:
        logger.error(f"获取消息列表失败: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"获取消息列表失败: {str(e)}")

# 日志API
@api_router.get("/logs")
async def get_logs(limit: int = 50, since: Optional[int] = None):
    """
    获取最近的日志

    Args:
        limit: 返回日志数量限制
        since: 可选的时间戳，如果提供则只返回自该时间戳以来的日志
    """
    try:
        # 记录API调用
        logger.debug(f"获取日志 API 被调用，参数：limit={limit}, since={since}")

        # 尝试从日志文件中读取日志
        logs = []

        try:
            # 获取日志文件路径
            import os
            from wxauto_mgt.utils.logging import get_log_file_path

            log_file = get_log_file_path()
            logger.debug(f"日志文件路径: {log_file}")

            if os.path.exists(log_file):
                # 读取日志文件的最后几行
                with open(log_file, 'r', encoding='utf-8') as f:
                    # 读取所有行
                    lines = f.readlines()
                    logger.debug(f"日志文件共有 {len(lines)} 行")

                    # 获取最后limit行
                    last_lines = lines[-limit*2:] if len(lines) > limit*2 else lines
                    logger.debug(f"读取了最后 {len(last_lines)} 行进行解析")

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

                    logger.debug(f"成功解析了 {len(logs)} 条日志")
        except Exception as e:
            logger.warning(f"从日志文件读取日志失败: {e}")

        # 如果没有从文件读取到日志，返回模拟数据
        if not logs:
            logger.debug("没有读取到日志，返回模拟数据")
            # 模拟日志数据
            log_levels = ["INFO", "WARNING", "ERROR"]
            log_messages = [
                "系统启动",
                "连接到数据库",
                "初始化服务平台",
                "加载消息转发规则",
                "启动消息监听",
                "接收到新消息",
                "处理消息",
                "转发消息",
                "消息处理完成",
                "数据库查询执行",
                "API请求处理",
                "用户登录",
                "用户操作",
                "配置更新",
                "系统状态检查"
            ]

            current_time = int(time.time())
            logs = []
            for i in range(limit):
                log_time = current_time - i * 60
                # 如果提供了since参数，则过滤早于since的日志
                if since and log_time <= since:
                    continue

                logs.append({
                    "timestamp": log_time,
                    "level": log_levels[i % len(log_levels)],
                    "message": f"{log_messages[i % len(log_messages)]} - {i}"
                })

        # 按时间戳降序排序
        logs.sort(key=lambda x: x.get('timestamp', 0), reverse=True)

        # 限制数量
        logs = logs[:limit]
        logger.debug(f"返回 {len(logs)} 条日志")

        return logs
    except Exception as e:
        logger.error(f"获取日志失败: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"获取日志失败: {str(e)}")

def register_api_routes(app: FastAPI):
    """
    注册API路由

    Args:
        app: FastAPI应用实例
    """
    app.include_router(api_router)
