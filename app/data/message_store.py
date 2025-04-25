"""
消息存储模块

负责消息的持久化存储和查询
"""

import asyncio
import json
import sqlite3
import time
import threading
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
import logging
import os
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class MessageStore:
    """消息存储类，负责消息的持久化存储和查询"""
    
    def __init__(self, db_path: str = "data/messages.db"):
        """
        初始化消息存储
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self._ensure_dir_exists()
        # 使用线程本地存储，确保每个线程有独立的数据库连接
        self._local = threading.local()
        self._init_db()
        self.logger = logging.getLogger(__name__)
        logger.debug(f"消息存储初始化完成, 路径: {self.db_path}")
    
    def _ensure_dir_exists(self):
        """确保数据库目录存在"""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(exist_ok=True, parents=True)
    
    def _init_db(self):
        """初始化数据库表结构"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 创建消息表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                instance_id TEXT,
                chat_name TEXT,
                message_type TEXT,
                content TEXT,
                sender TEXT,
                sender_remark TEXT,
                message_id TEXT,
                mtype INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                processed BOOLEAN DEFAULT FALSE
            )
            ''')
            # 创建索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_processed ON messages (processed)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages (timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_chat_name ON messages (chat_name)')
            conn.commit()
    
    async def save_message(self, message: Dict[str, Any]) -> bool:
        """异步保存消息"""
        try:
            # 在事件循环中执行同步操作
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._save_message_sync, message)
            return result
        except Exception as e:
            self.logger.error(f"异步保存消息失败: {e}")
            return False
    
    def _save_message_sync(self, message: Dict[str, Any]) -> bool:
        """同步保存消息到数据库"""
        try:
            content = message.get('content', '')
            content_preview = content[:20] + '...' if content and len(content) > 20 else content
            self.logger.debug(f"保存消息: {message.get('chat_name')} - {content_preview}")
            
            # 获取当前时间作为时间戳
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO messages (
                        instance_id, chat_name, message_type, content,
                        sender, sender_remark, message_id, mtype, timestamp
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    message.get('instance_id'),
                    message.get('chat_name'),
                    message.get('message_type') or message.get('type'),
                    message.get('content'),
                    message.get('sender'),
                    message.get('sender_remark'),
                    message.get('message_id') or message.get('id'),
                    message.get('mtype'),
                    now
                ))
                conn.commit()
            self.logger.debug(f"成功保存消息: {message.get('chat_name')} - {content_preview}")
            return True
        except Exception as e:
            self.logger.error(f"保存消息失败: {e}, 消息内容: {message}")
            return False
    
    async def get_messages(self, 
                         processed: Optional[bool] = None,
                         instance_id: Optional[str] = None,
                         chat_name: Optional[str] = None,
                         limit: int = 100) -> List[Dict[str, Any]]:
        """获取消息列表"""
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, 
                self._get_messages_sync, 
                processed, instance_id, chat_name, limit
            )
        except Exception as e:
            self.logger.error(f"异步获取消息列表失败: {e}")
            return []
    
    def _get_messages_sync(self,
                          processed: Optional[bool] = None,
                          instance_id: Optional[str] = None,
                          chat_name: Optional[str] = None,
                          limit: int = 100) -> List[Dict[str, Any]]:
        """同步获取消息列表"""
        try:
            with self._get_connection() as conn:
                query = "SELECT * FROM messages WHERE 1=1"
                params = []

                if processed is not None:
                    query += " AND processed = ?"
                    params.append(processed)

                if instance_id:
                    query += " AND instance_id = ?"
                    params.append(instance_id)

                if chat_name:
                    query += " AND chat_name = ?"
                    params.append(chat_name)

                query += " ORDER BY timestamp DESC LIMIT ?"
                params.append(limit)

                cursor = conn.execute(query, params)
                messages = []
                for row in cursor:
                    messages.append({
                        'id': row[0],
                        'instance_id': row[1],
                        'chat_name': row[2],
                        'type': row[3],
                        'content': row[4],
                        'sender': row[5],
                        'sender_remark': row[6],
                        'message_id': row[7],
                        'mtype': row[8],
                        'timestamp': row[9],
                        'processed': bool(row[10])
                    })
                
                self.logger.debug(f"查询到 {len(messages)} 条消息")
                return messages
        except Exception as e:
            self.logger.error(f"获取消息失败: {e}")
            return []
    
    async def mark_as_processed(self, message_id: Union[int, str]) -> bool:
        """标记消息为已处理"""
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._mark_as_processed_sync, message_id)
            return result
        except Exception as e:
            self.logger.error(f"异步标记消息处理状态失败: {e}")
            return False
    
    def _mark_as_processed_sync(self, message_id: Union[int, str]) -> bool:
        """同步标记消息为已处理"""
        try:
            with self._get_connection() as conn:
                # 可以接受数字ID或字符串message_id
                if isinstance(message_id, int):
                    conn.execute("""
                        UPDATE messages SET processed = TRUE
                        WHERE id = ?
                    """, (message_id,))
                else:
                    conn.execute("""
                        UPDATE messages SET processed = TRUE
                        WHERE message_id = ?
                    """, (message_id,))
                conn.commit()
            self.logger.debug(f"标记消息 {message_id} 为已处理")
            return True
        except Exception as e:
            self.logger.error(f"标记消息处理状态失败: {e}")
            return False
    
    async def clean_old_messages(self, days: int = 30) -> bool:
        """清理旧消息"""
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._clean_old_messages_sync, days)
            return result
        except Exception as e:
            self.logger.error(f"异步清理旧消息失败: {e}")
            return False
    
    def _clean_old_messages_sync(self, days: int) -> bool:
        """同步清理旧消息"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            with self._get_connection() as conn:
                conn.execute("""
                    DELETE FROM messages
                    WHERE timestamp < ?
                """, (cutoff_date.strftime('%Y-%m-%d %H:%M:%S'),))
                conn.commit()
            return True
        except Exception as e:
            self.logger.error(f"清理旧消息失败: {e}")
            return False
    
    async def get_total_message_count(self) -> int:
        """获取消息总数"""
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._get_total_message_count_sync)
        except Exception as e:
            self.logger.error(f"异步获取消息总数失败: {e}")
            return 0
            
    def _get_total_message_count_sync(self) -> int:
        """同步获取消息总数"""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM messages")
                return cursor.fetchone()[0]
        except Exception as e:
            self.logger.error(f"获取消息总数失败: {e}")
            return 0
    
    async def get_processed_message_count(self) -> int:
        """获取已处理消息数量"""
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._get_processed_message_count_sync)
        except Exception as e:
            self.logger.error(f"异步获取已处理消息数量失败: {e}")
            return 0
            
    def _get_processed_message_count_sync(self) -> int:
        """同步获取已处理消息数量"""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM messages WHERE processed = TRUE")
                return cursor.fetchone()[0]
        except Exception as e:
            self.logger.error(f"获取已处理消息数量失败: {e}")
            return 0
    
    async def get_unprocessed_messages(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取未处理的消息"""
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._get_unprocessed_messages_sync, limit)
        except Exception as e:
            self.logger.error(f"异步获取未处理消息失败: {e}")
            return []
            
    def _get_unprocessed_messages_sync(self, limit: int) -> List[Dict[str, Any]]:
        """同步获取未处理的消息"""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    SELECT * FROM messages 
                    WHERE processed = FALSE 
                    ORDER BY timestamp ASC 
                    LIMIT ?
                """, (limit,))
                
                messages = []
                for row in cursor:
                    messages.append({
                        'id': row[0],
                        'instance_id': row[1],
                        'chat_name': row[2],
                        'type': row[3],
                        'content': row[4],
                        'sender': row[5],
                        'sender_remark': row[6],
                        'message_id': row[7],
                        'mtype': row[8],
                        'timestamp': row[9],
                        'processed': bool(row[10])
                    })
                
                self.logger.debug(f"获取到 {len(messages)} 条未处理消息")
                return messages
        except Exception as e:
            self.logger.error(f"获取未处理消息失败: {e}")
            return []
    
    async def close(self):
        """关闭数据库连接"""
        # SQLite连接不需要显式关闭，作为占位符
        pass 

    def _get_connection(self):
        """获取当前线程的数据库连接"""
        if not hasattr(self._local, 'connection'):
            self._local.connection = sqlite3.connect(self.db_path)
        return self._local.connection 

    def log_database_content(self):
        """记录数据库内容到日志"""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM messages")
                total_count = cursor.fetchone()[0]
                self.logger.info(f"数据库共有 {total_count} 条消息")
                
                if total_count > 0:
                    # 获取最新的10条消息
                    cursor = conn.execute("""
                        SELECT id, chat_name, message_type, content, sender, timestamp, processed 
                        FROM messages 
                        ORDER BY id DESC 
                        LIMIT 10
                    """)
                    
                    self.logger.info("最新的10条消息:")
                    for row in cursor:
                        self.logger.info(f"- ID: {row[0]}, 来源: {row[1]}, 类型: {row[2]}, "
                                         f"发送者: {row[4]}, 时间: {row[5]}, "
                                         f"内容: {row[3][:30]}...")
                        
            return True
        except Exception as e:
            self.logger.error(f"记录数据库内容失败: {e}")
            return False 