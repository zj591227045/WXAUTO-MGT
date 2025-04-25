"""
消息队列存储模块

提供消息的存储、查询和状态管理功能。
使用SQLite作为存储介质，提供消息队列操作的异步API。
"""

import asyncio
import json
import time
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from app.data.db_manager import db_manager
from app.utils.logging import get_logger

logger = get_logger()


class MessageStatus(Enum):
    """消息状态枚举"""
    PENDING = "pending"    # 待处理
    PROCESSING = "processing"  # 处理中
    PROCESSED = "processed"    # 已处理
    FAILED = "failed"      # 处理失败
    RETRYING = "retrying"  # 重试中


class MessageStore:
    """
    消息队列存储，负责管理消息的持久化存储和查询
    """
    
    def __init__(self):
        """初始化消息存储"""
        self._lock = asyncio.Lock()
        self._initialized = False
        logger.debug("初始化消息队列存储")
    
    async def initialize(self) -> None:
        """
        初始化消息存储
        
        确保数据库表已经创建并且索引已建立
        """
        if self._initialized:
            logger.debug("消息队列存储已初始化")
            return
        
        # 确保数据库已初始化
        await db_manager.initialize()
        
        # 创建额外的索引（如果需要）
        async with self._lock:
            try:
                # 创建时间索引，用于清理过期消息
                await db_manager.execute(
                    "CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp)"
                )
                
                # 创建状态+时间联合索引，用于查询待处理消息
                await db_manager.execute(
                    "CREATE INDEX IF NOT EXISTS idx_messages_status_time ON messages(status, timestamp)"
                )
            except Exception as e:
                logger.error(f"创建消息索引失败: {e}")
                raise
        
        self._initialized = True
        logger.info("消息队列存储初始化完成")
    
    async def save_message(self, message: Dict[str, Any]) -> bool:
        """
        保存消息
        
        Args:
            message: 消息数据，必须包含message_id, instance_id, sender, receiver, content, timestamp字段
                
        Returns:
            bool: 是否成功保存
        """
        if not self._initialized:
            await self.initialize()
        
        # 确保必要字段存在
        required_fields = ['message_id', 'instance_id', 'sender', 'receiver', 'content', 'timestamp']
        for field in required_fields:
            if field not in message:
                logger.error(f"保存消息失败: 缺少必要字段 {field}")
                return False
        
        # 为JSON等复杂内容进行处理
        msg_data = message.copy()
        if isinstance(msg_data.get('content'), (dict, list)):
            msg_data['content'] = json.dumps(msg_data['content'], ensure_ascii=False)
        
        # 设置默认状态和更新时间
        if 'status' not in msg_data:
            msg_data['status'] = MessageStatus.PENDING.value
        if 'retry_count' not in msg_data:
            msg_data['retry_count'] = 0
        if 'last_update' not in msg_data:
            msg_data['last_update'] = int(time.time())
        
        try:
            await db_manager.insert("messages", msg_data)
            logger.debug(f"已保存消息: {msg_data['message_id']}")
            return True
        except Exception as e:
            logger.error(f"保存消息失败: {e}")
            return False
    
    async def get_pending_messages(self, limit: int = 10, instance_id: Optional[str] = None) -> List[Dict]:
        """
        获取待处理的消息
        
        Args:
            limit: 获取消息的最大数量
            instance_id: 实例ID，如果指定则只获取该实例的消息
            
        Returns:
            List[Dict]: 待处理消息列表
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            params = [MessageStatus.PENDING.value]
            query = "SELECT * FROM messages WHERE status = ?"
            
            if instance_id:
                query += " AND instance_id = ?"
                params.append(instance_id)
            
            query += " ORDER BY timestamp ASC LIMIT ?"
            params.append(limit)
            
            rows = await db_manager.fetch_all(query, params)
            
            # 转换为字典列表
            messages = []
            for row in rows:
                msg = dict(row)
                
                # 尝试解析JSON内容
                try:
                    content = msg.get('content', '{}')
                    if content.startswith('{') or content.startswith('['):
                        msg['content'] = json.loads(content)
                except (json.JSONDecodeError, TypeError):
                    pass  # 如果不是JSON格式，保持原始内容
                
                messages.append(msg)
            
            if messages:
                logger.debug(f"获取到 {len(messages)} 条待处理消息")
            
            return messages
        
        except Exception as e:
            logger.error(f"获取待处理消息失败: {e}")
            return []
    
    async def update_message_status(self, message_id: str, status: Union[MessageStatus, str], 
                                   increment_retry: bool = False) -> bool:
        """
        更新消息状态
        
        Args:
            message_id: 消息ID
            status: 新状态，可以是MessageStatus枚举或状态字符串
            increment_retry: 是否增加重试计数
            
        Returns:
            bool: 是否成功更新
        """
        if not self._initialized:
            await self.initialize()
        
        # 转换状态类型
        if isinstance(status, MessageStatus):
            status = status.value
        
        try:
            update_data = {
                "status": status,
                "last_update": int(time.time())
            }
            
            if increment_retry:
                # 获取当前重试次数并增加
                row = await db_manager.fetch_one(
                    "SELECT retry_count FROM messages WHERE message_id = ?", 
                    [message_id]
                )
                
                if row:
                    current_retry = row['retry_count']
                    update_data["retry_count"] = current_retry + 1
            
            # 更新数据库
            result = await db_manager.update(
                "messages", 
                update_data,
                "message_id = ?",
                [message_id]
            )
            
            if result:
                logger.debug(f"已更新消息状态: {message_id} -> {status}")
                return True
            else:
                logger.warning(f"消息状态更新失败: {message_id} 不存在")
                return False
                
        except Exception as e:
            logger.error(f"更新消息状态失败: {e}")
            return False
    
    async def batch_update_status(self, message_ids: List[str], status: Union[MessageStatus, str], 
                                 increment_retry: bool = False) -> int:
        """
        批量更新消息状态
        
        Args:
            message_ids: 消息ID列表
            status: 新状态，可以是MessageStatus枚举或状态字符串
            increment_retry: 是否增加重试计数
            
        Returns:
            int: 成功更新的消息数量
        """
        if not self._initialized:
            await self.initialize()
        
        if not message_ids:
            return 0
        
        # 转换状态类型
        if isinstance(status, MessageStatus):
            status = status.value
            
        try:
            now = int(time.time())
            
            if increment_retry:
                # 对每个消息单独更新以增加重试计数
                success_count = 0
                for message_id in message_ids:
                    success = await self.update_message_status(message_id, status, True)
                    if success:
                        success_count += 1
                
                return success_count
            else:
                # 批量更新状态
                placeholders = ', '.join(['?' for _ in message_ids])
                query = f"""
                UPDATE messages 
                SET status = ?, last_update = ?
                WHERE message_id IN ({placeholders})
                """
                
                params = [status, now] + message_ids
                await db_manager.execute(query, params)
                
                logger.debug(f"已批量更新 {len(message_ids)} 条消息的状态为 {status}")
                return len(message_ids)
        
        except Exception as e:
            logger.error(f"批量更新消息状态失败: {e}")
            return 0
    
    async def get_failed_messages(self, max_retry: int = 3, limit: int = 10) -> List[Dict]:
        """
        获取失败的消息用于重试
        
        Args:
            max_retry: 最大重试次数，超过此次数的消息不会返回
            limit: 获取消息的最大数量
            
        Returns:
            List[Dict]: 可重试的失败消息列表
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            query = """
            SELECT * FROM messages 
            WHERE status = ? AND retry_count < ? 
            ORDER BY last_update ASC LIMIT ?
            """
            
            params = [MessageStatus.FAILED.value, max_retry, limit]
            rows = await db_manager.fetch_all(query, params)
            
            # 转换为字典列表
            messages = []
            for row in rows:
                msg = dict(row)
                
                # 尝试解析JSON内容
                try:
                    content = msg.get('content', '{}')
                    if content.startswith('{') or content.startswith('['):
                        msg['content'] = json.loads(content)
                except (json.JSONDecodeError, TypeError):
                    pass  # 如果不是JSON格式，保持原始内容
                
                messages.append(msg)
            
            if messages:
                logger.debug(f"获取到 {len(messages)} 条可重试的失败消息")
            
            return messages
        
        except Exception as e:
            logger.error(f"获取失败消息失败: {e}")
            return []
    
    async def get_message(self, message_id: str) -> Optional[Dict]:
        """
        获取指定ID的消息
        
        Args:
            message_id: 消息ID
            
        Returns:
            Optional[Dict]: 消息数据，如果不存在则返回None
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            row = await db_manager.fetch_one(
                "SELECT * FROM messages WHERE message_id = ?", 
                [message_id]
            )
            
            if not row:
                return None
            
            # 转换为字典
            msg = dict(row)
            
            # 尝试解析JSON内容
            try:
                content = msg.get('content', '{}')
                if content.startswith('{') or content.startswith('['):
                    msg['content'] = json.loads(content)
            except (json.JSONDecodeError, TypeError):
                pass  # 如果不是JSON格式，保持原始内容
            
            return msg
        
        except Exception as e:
            logger.error(f"获取消息失败: {e}")
            return None
    
    async def search_messages(self, 
                            status: Optional[Union[MessageStatus, str]] = None, 
                            instance_id: Optional[str] = None,
                            sender: Optional[str] = None,
                            receiver: Optional[str] = None,
                            start_time: Optional[int] = None,
                            end_time: Optional[int] = None,
                            limit: int = 100,
                            offset: int = 0) -> List[Dict]:
        """
        搜索消息
        
        Args:
            status: 消息状态
            instance_id: 实例ID
            sender: 发送者
            receiver: 接收者
            start_time: 开始时间戳
            end_time: 结束时间戳
            limit: 结果数量限制
            offset: 结果偏移量
            
        Returns:
            List[Dict]: 符合条件的消息列表
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            conditions = []
            params = []
            
            # 构建查询条件
            if status:
                if isinstance(status, MessageStatus):
                    status = status.value
                conditions.append("status = ?")
                params.append(status)
            
            if instance_id:
                conditions.append("instance_id = ?")
                params.append(instance_id)
            
            if sender:
                conditions.append("sender = ?")
                params.append(sender)
            
            if receiver:
                conditions.append("receiver = ?")
                params.append(receiver)
            
            if start_time is not None:
                conditions.append("timestamp >= ?")
                params.append(start_time)
            
            if end_time is not None:
                conditions.append("timestamp <= ?")
                params.append(end_time)
            
            # 构建查询语句
            query = "SELECT * FROM messages"
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            
            query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            # 执行查询
            rows = await db_manager.fetch_all(query, params)
            
            # 转换为字典列表
            messages = []
            for row in rows:
                msg = dict(row)
                
                # 尝试解析JSON内容
                try:
                    content = msg.get('content', '{}')
                    if content.startswith('{') or content.startswith('['):
                        msg['content'] = json.loads(content)
                except (json.JSONDecodeError, TypeError):
                    pass  # 如果不是JSON格式，保持原始内容
                
                messages.append(msg)
            
            logger.debug(f"搜索消息: 找到 {len(messages)} 条结果")
            return messages
        
        except Exception as e:
            logger.error(f"搜索消息失败: {e}")
            return []
    
    async def get_message_count(self, 
                              status: Optional[Union[MessageStatus, str]] = None, 
                              instance_id: Optional[str] = None) -> int:
        """
        获取消息数量
        
        Args:
            status: 消息状态
            instance_id: 实例ID
            
        Returns:
            int: 符合条件的消息数量
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            conditions = []
            params = []
            
            if status:
                if isinstance(status, MessageStatus):
                    status = status.value
                conditions.append("status = ?")
                params.append(status)
            
            if instance_id:
                conditions.append("instance_id = ?")
                params.append(instance_id)
            
            query = "SELECT COUNT(*) as count FROM messages"
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            
            row = await db_manager.fetch_one(query, params)
            return row['count'] if row else 0
        
        except Exception as e:
            logger.error(f"获取消息数量失败: {e}")
            return 0
    
    async def clean_processed_messages(self, max_age_hours: int = 24) -> int:
        """
        清理已处理的旧消息
        
        Args:
            max_age_hours: 最大保留时间（小时）
            
        Returns:
            int: 清理的消息数量
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            # 计算时间阈值
            cutoff_time = int(time.time()) - (max_age_hours * 3600)
            
            # 删除已处理的旧消息
            deleted = await db_manager.delete(
                "messages",
                "status = ? AND timestamp < ?",
                [MessageStatus.PROCESSED.value, cutoff_time]
            )
            
            if deleted > 0:
                logger.info(f"已清理 {deleted} 条已处理的旧消息")
            
            return deleted
        
        except Exception as e:
            logger.error(f"清理已处理消息失败: {e}")
            return 0
    
    async def clean_all_old_messages(self, max_age_days: int = 7) -> int:
        """
        清理所有旧消息（包括失败的消息）
        
        Args:
            max_age_days: 最大保留时间（天）
            
        Returns:
            int: 清理的消息数量
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            # 计算时间阈值
            cutoff_time = int(time.time()) - (max_age_days * 86400)
            
            # 删除所有旧消息
            deleted = await db_manager.delete(
                "messages",
                "timestamp < ?",
                [cutoff_time]
            )
            
            if deleted > 0:
                logger.info(f"已清理 {deleted} 条过期消息")
            
            return deleted
        
        except Exception as e:
            logger.error(f"清理过期消息失败: {e}")
            return 0
    
    async def get_message_statistics(self, instance_id: Optional[str] = None) -> Dict[str, int]:
        """
        获取消息统计数据
        
        Args:
            instance_id: 实例ID，如果指定则只统计该实例的消息
            
        Returns:
            Dict[str, int]: 各状态的消息数量
        """
        if not self._initialized:
            await self.initialize()
        
        results = {}
        
        try:
            for status in MessageStatus:
                count = await self.get_message_count(status, instance_id)
                results[status.value] = count
            
            # 查询总消息数
            if instance_id:
                query = "SELECT COUNT(*) as count FROM messages WHERE instance_id = ?"
                params = [instance_id]
            else:
                query = "SELECT COUNT(*) as count FROM messages"
                params = None
                
            row = await db_manager.fetch_one(query, params)
            results['total'] = row['count'] if row else 0
            
            return results
        
        except Exception as e:
            logger.error(f"获取消息统计数据失败: {e}")
            return {"error": str(e)}


# 创建全局消息存储实例
message_store = MessageStore() 