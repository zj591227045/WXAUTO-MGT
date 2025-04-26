"""
消息存储模块

负责管理消息的存储和检索，支持多实例管理。
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any

from ..data.db_manager import db_manager

logger = logging.getLogger(__name__)

class MessageStore:
    """消息存储管理器，负责消息的存储和检索"""
    
    def __init__(self):
        """初始化消息存储管理器"""
        self._lock = asyncio.Lock()
        
    async def save_message(self, instance_id: str, message: Dict[str, Any]) -> bool:
        """
        保存消息到数据库
        
        Args:
            instance_id: 实例ID
            message: 消息数据
            
        Returns:
            bool: 是否成功保存
        """
        try:
            # 准备消息数据
            message_data = {
                'instance_id': instance_id,
                'message_id': message.get('message_id'),
                'chat_name': message.get('chat_name'),
                'message_type': message.get('message_type'),
                'content': message.get('content'),
                'sender': message.get('sender'),
                'sender_remark': message.get('sender_remark'),
                'mtype': message.get('mtype'),
                'processed': 0,
                'create_time': int(time.time())
            }
            
            # 保存到数据库
            await db_manager.insert('messages', message_data)
            logger.debug(f"消息已保存: {message.get('message_id')}")
            return True
        except Exception as e:
            logger.error(f"保存消息失败: {str(e)}")
            return False
            
    async def get_unprocessed_messages(self, instance_id: str, limit: int = 100) -> List[Dict]:
        """
        获取未处理的消息
        
        Args:
            instance_id: 实例ID
            limit: 返回消息数量限制
            
        Returns:
            List[Dict]: 未处理消息列表
        """
        try:
            sql = """
            SELECT * FROM messages 
            WHERE instance_id = ? AND processed = 0 
            ORDER BY create_time ASC 
            LIMIT ?
            """
            messages = await db_manager.fetchall(sql, (instance_id, limit))
            return messages
        except Exception as e:
            logger.error(f"获取未处理消息失败: {str(e)}")
            return []
            
    async def mark_message_processed(self, instance_id: str, message_id: str) -> bool:
        """
        标记消息为已处理
        
        Args:
            instance_id: 实例ID
            message_id: 消息ID
            
        Returns:
            bool: 是否成功标记
        """
        try:
            conditions = {
                'instance_id': instance_id,
                'message_id': message_id
            }
            data = {
                'processed': 1
            }
            await db_manager.update('messages', data, conditions)
            logger.debug(f"消息已标记为处理: {message_id}")
            return True
        except Exception as e:
            logger.error(f"标记消息处理状态失败: {str(e)}")
            return False
            
    async def get_message_by_id(self, instance_id: str, message_id: str) -> Optional[Dict]:
        """
        根据消息ID获取消息
        
        Args:
            instance_id: 实例ID
            message_id: 消息ID
            
        Returns:
            Optional[Dict]: 消息数据
        """
        try:
            sql = "SELECT * FROM messages WHERE instance_id = ? AND message_id = ?"
            message = await db_manager.fetchone(sql, (instance_id, message_id))
            return message
        except Exception as e:
            logger.error(f"获取消息失败: {str(e)}")
            return None
            
    async def get_messages_by_chat(self, instance_id: str, chat_name: str, limit: int = 100) -> List[Dict]:
        """
        获取指定聊天的消息
        
        Args:
            instance_id: 实例ID
            chat_name: 聊天名称
            limit: 返回消息数量限制
            
        Returns:
            List[Dict]: 消息列表
        """
        try:
            sql = """
            SELECT * FROM messages 
            WHERE instance_id = ? AND chat_name = ? 
            ORDER BY create_time DESC 
            LIMIT ?
            """
            messages = await db_manager.fetchall(sql, (instance_id, chat_name, limit))
            return messages
        except Exception as e:
            logger.error(f"获取聊天消息失败: {str(e)}")
            return []
            
    async def delete_messages(self, instance_id: str, before_time: int = None) -> bool:
        """
        删除消息
        
        Args:
            instance_id: 实例ID
            before_time: 删除此时间戳之前的消息，如果为None则删除所有消息
            
        Returns:
            bool: 是否成功删除
        """
        try:
            if before_time:
                conditions = {
                    'instance_id': instance_id,
                    'create_time': ('<=', before_time)
                }
            else:
                conditions = {
                    'instance_id': instance_id
                }
            await db_manager.delete('messages', conditions)
            logger.info(f"已删除消息, instance_id: {instance_id}")
            return True
        except Exception as e:
            logger.error(f"删除消息失败: {str(e)}")
            return False
            
    async def cleanup_old_messages(self, max_age_days: int = 7) -> bool:
        """
        清理旧消息
        
        Args:
            max_age_days: 保留消息的最大天数
            
        Returns:
            bool: 是否成功清理
        """
        try:
            cutoff_time = int(time.time()) - (max_age_days * 24 * 60 * 60)
            sql = "DELETE FROM messages WHERE create_time < ?"
            await db_manager.execute(sql, (cutoff_time,))
            logger.info(f"已清理{max_age_days}天前的旧消息")
            return True
        except Exception as e:
            logger.error(f"清理旧消息失败: {str(e)}")
            return False

# 创建全局实例
message_store = MessageStore() 