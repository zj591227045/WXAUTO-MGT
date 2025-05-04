"""
状态WebSocket

提供实例状态和系统性能指标的实时更新WebSocket接口。
"""

import logging
import json
import asyncio
from typing import List, Dict, Any, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from fastapi.websockets import WebSocketState

from ..security import get_current_user, User

logger = logging.getLogger(__name__)

router = APIRouter()

# 活动连接管理
active_connections: Set[WebSocket] = set()

# 状态缓存
status_cache: Dict[str, Dict[str, Any]] = {}

async def authenticate_websocket(websocket: WebSocket) -> bool:
    """
    认证WebSocket连接
    
    Args:
        websocket: WebSocket连接
        
    Returns:
        bool: 是否认证成功
    """
    try:
        # 从查询参数获取令牌
        token = websocket.query_params.get("token")
        if not token:
            await websocket.close(code=1008, reason="缺少认证令牌")
            return False
        
        # 验证令牌
        # 这里简化处理，实际应该使用与API相同的认证逻辑
        if token == "demo_token":
            return True
        
        await websocket.close(code=1008, reason="无效的认证令牌")
        return False
    
    except Exception as e:
        logger.error(f"WebSocket认证失败: {e}")
        await websocket.close(code=1011, reason="认证过程中发生错误")
        return False

@router.websocket("/ws/status")
async def websocket_status(websocket: WebSocket):
    """
    状态WebSocket接口
    
    Args:
        websocket: WebSocket连接
    """
    # 认证
    if not await authenticate_websocket(websocket):
        return
    
    # 接受连接
    await websocket.accept()
    active_connections.add(websocket)
    
    try:
        # 发送缓存的状态
        if status_cache:
            await websocket.send_json({
                "type": "status_update",
                "data": status_cache
            })
        
        # 保持连接并接收消息
        while True:
            # 接收消息（客户端可能发送心跳包或其他命令）
            data = await websocket.receive_text()
            
            # 处理客户端消息
            try:
                command = json.loads(data)
                if command.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                elif command.get("type") == "subscribe":
                    # 处理订阅请求
                    instance_id = command.get("instance_id")
                    if instance_id:
                        # 这里可以实现针对特定实例的订阅逻辑
                        pass
            except json.JSONDecodeError:
                logger.warning(f"收到无效的WebSocket消息: {data}")
    
    except WebSocketDisconnect:
        # 客户端断开连接
        logger.info("WebSocket客户端断开连接")
    
    except Exception as e:
        # 其他异常
        logger.error(f"WebSocket连接异常: {e}")
    
    finally:
        # 清理连接
        if websocket in active_connections:
            active_connections.remove(websocket)

async def broadcast_status_update(instance_id: str, status: Dict[str, Any]) -> None:
    """
    广播实例状态更新
    
    Args:
        instance_id: 实例ID
        status: 状态数据
    """
    # 更新缓存
    status_cache[instance_id] = status
    
    # 准备广播消息
    message = {
        "type": "status_update",
        "instance_id": instance_id,
        "data": status
    }
    
    # 广播到所有连接
    disconnected = set()
    for connection in active_connections:
        try:
            if connection.client_state == WebSocketState.CONNECTED:
                await connection.send_json(message)
            else:
                disconnected.add(connection)
        except Exception as e:
            logger.error(f"发送WebSocket消息失败: {e}")
            disconnected.add(connection)
    
    # 清理断开的连接
    for connection in disconnected:
        if connection in active_connections:
            active_connections.remove(connection)

async def broadcast_system_metrics(metrics: Dict[str, Any]) -> None:
    """
    广播系统性能指标
    
    Args:
        metrics: 性能指标数据
    """
    # 准备广播消息
    message = {
        "type": "system_metrics",
        "data": metrics
    }
    
    # 广播到所有连接
    disconnected = set()
    for connection in active_connections:
        try:
            if connection.client_state == WebSocketState.CONNECTED:
                await connection.send_json(message)
            else:
                disconnected.add(connection)
        except Exception as e:
            logger.error(f"发送WebSocket消息失败: {e}")
            disconnected.add(connection)
    
    # 清理断开的连接
    for connection in disconnected:
        if connection in active_connections:
            active_connections.remove(connection)

# 导出广播函数，供其他模块使用
__all__ = ["broadcast_status_update", "broadcast_system_metrics"]
