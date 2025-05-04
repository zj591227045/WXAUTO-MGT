"""
消息WebSocket

提供实时消息流的WebSocket接口，用于向客户端推送新消息和消息状态更新。
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

# 消息缓存
message_cache: List[Dict[str, Any]] = []
MAX_CACHE_SIZE = 100

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

@router.websocket("/ws/messages")
async def websocket_messages(websocket: WebSocket):
    """
    消息WebSocket接口
    
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
        # 发送缓存的消息
        for message in message_cache:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_json(message)
        
        # 保持连接并接收消息
        while True:
            # 接收消息（客户端可能发送心跳包或其他命令）
            data = await websocket.receive_text()
            
            # 处理客户端消息
            try:
                command = json.loads(data)
                if command.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
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

async def broadcast_message(message: Dict[str, Any]) -> None:
    """
    广播消息到所有连接的客户端
    
    Args:
        message: 要广播的消息
    """
    # 添加到缓存
    message_cache.append(message)
    if len(message_cache) > MAX_CACHE_SIZE:
        message_cache.pop(0)
    
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
__all__ = ["broadcast_message"]
