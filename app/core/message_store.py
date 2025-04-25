"""
消息存储模块

该模块负责消息的持久化存储和管理。
使用SQLite数据库存储消息数据。
"""

import sqlite3
import json
import logging
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

class MessageStore:
    def __init__(self, db_path: str = "data/messages.db"):
        """
        初始化消息存储
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self._connection: Optional[sqlite3.Connection] = None
        self._lock = asyncio.Lock()
        
        # 确保数据目录存在
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # 初始化数据库
        self._init_db()
    
    def _init_db(self):
        """初始化数据库表"""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    sender TEXT NOT NULL,
                    sender_remark TEXT,
                    chat_name TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    processed BOOLEAN DEFAULT FALSE,
                    metadata TEXT,
                    created_at REAL DEFAULT (strftime('%s', 'now'))
                )
            """)
            
            # 创建索引
            conn.execute("CREATE INDEX IF NOT EXISTS idx_processed ON messages(processed)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_name ON messages(chat_name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON messages(timestamp)")
    
    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        if self._connection is None:
            self._connection = sqlite3.connect(self.db_path)
            self._connection.row_factory = sqlite3.Row
        return self._connection
    
    async def close(self):
        """关闭数据库连接"""
        if self._connection:
            self._connection.close()
            self._connection = None
    
    async def save_message(self, message: Dict[str, Any]) -> bool:
        """
        保存消息
        
        Args:
            message: 消息数据
            
        Returns:
            bool: 是否保存成功
        """
        async with self._lock:
            try:
                with self._get_connection() as conn:
                    conn.execute("""
                        INSERT OR REPLACE INTO messages (
                            id, type, content, sender, sender_remark,
                            chat_name, timestamp, metadata
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        message["id"],
                        message["type"],
                        message["content"],
                        message["sender"],
                        message.get("sender_remark"),
                        message["chat_name"],
                        message["timestamp"],
                        json.dumps(message.get("metadata", {}))
                    ))
                return True
            
            except Exception as e:
                logger.error(f"保存消息失败: {e}")
                return False
    
    async def get_unprocessed_messages(
        self,
        limit: int = 100,
        chat_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        获取未处理的消息
        
        Args:
            limit: 返回消息的最大数量
            chat_name: 聊天对象名称（可选）
            
        Returns:
            List[Dict]: 消息列表
        """
        async with self._lock:
            with self._get_connection() as conn:
                query = """
                    SELECT * FROM messages 
                    WHERE processed = FALSE
                """
                params = []
                
                if chat_name:
                    query += " AND chat_name = ?"
                    params.append(chat_name)
                
                query += " ORDER BY timestamp ASC LIMIT ?"
                params.append(limit)
                
                cursor = conn.execute(query, params)
                messages = []
                
                for row in cursor:
                    messages.append({
                        "id": row["id"],
                        "type": row["type"],
                        "content": row["content"],
                        "sender": row["sender"],
                        "sender_remark": row["sender_remark"],
                        "chat_name": row["chat_name"],
                        "timestamp": row["timestamp"],
                        "metadata": json.loads(row["metadata"]) if row["metadata"] else {}
                    })
                
                return messages
    
    async def mark_as_processed(self, message_id: str) -> bool:
        """
        标记消息为已处理
        
        Args:
            message_id: 消息ID
            
        Returns:
            bool: 是否标记成功
        """
        async with self._lock:
            try:
                with self._get_connection() as conn:
                    conn.execute(
                        "UPDATE messages SET processed = TRUE WHERE id = ?",
                        (message_id,)
                    )
                return True
            
            except Exception as e:
                logger.error(f"标记消息状态失败: {e}")
                return False
    
    async def get_messages_by_chat(
        self,
        chat_name: str,
        limit: int = 100,
        offset: int = 0,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        获取指定聊天对象的消息
        
        Args:
            chat_name: 聊天对象名称
            limit: 返回消息的最大数量
            offset: 分页偏移量
            start_time: 开始时间戳
            end_time: 结束时间戳
            
        Returns:
            List[Dict]: 消息列表
        """
        async with self._lock:
            with self._get_connection() as conn:
                query = "SELECT * FROM messages WHERE chat_name = ?"
                params = [chat_name]
                
                if start_time is not None:
                    query += " AND timestamp >= ?"
                    params.append(start_time)
                
                if end_time is not None:
                    query += " AND timestamp <= ?"
                    params.append(end_time)
                
                query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
                params.extend([limit, offset])
                
                cursor = conn.execute(query, params)
                messages = []
                
                for row in cursor:
                    messages.append({
                        "id": row["id"],
                        "type": row["type"],
                        "content": row["content"],
                        "sender": row["sender"],
                        "sender_remark": row["sender_remark"],
                        "chat_name": row["chat_name"],
                        "timestamp": row["timestamp"],
                        "metadata": json.loads(row["metadata"]) if row["metadata"] else {}
                    })
                
                return messages
    
    async def cleanup_old_messages(self, days: int = 7) -> int:
        """
        清理旧消息
        
        Args:
            days: 保留天数
            
        Returns:
            int: 清理的消息数量
        """
        async with self._lock:
            try:
                with self._get_connection() as conn:
                    cutoff_time = datetime.now().timestamp() - (days * 24 * 60 * 60)
                    cursor = conn.execute(
                        "DELETE FROM messages WHERE timestamp < ?",
                        (cutoff_time,)
                    )
                    return cursor.rowcount
            
            except Exception as e:
                logger.error(f"清理旧消息失败: {e}")
                return 0 