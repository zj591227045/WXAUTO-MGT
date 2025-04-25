"""
消息存储模块

负责消息的持久化存储和查询
"""

import asyncio
import json
import sqlite3
import time
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
        self._init_db()
        self.logger = logging.getLogger(__name__)
        logger.debug(f"消息存储初始化完成, 路径: {self.db_path}")
    
    def _ensure_dir_exists(self):
        """确保数据库目录存在"""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(exist_ok=True, parents=True)
    
    def _init_db(self):
        """初始化数据库表结构"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # 创建消息表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                instance_id TEXT,
                chat_name TEXT,
                message_type TEXT,
                content TEXT,
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
        return await self._save_message_sync(message)
    
    def _save_message_sync(self, message: Dict[str, Any]) -> bool:
        """同步保存消息到数据库"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO messages (instance_id, chat_name, message_type, content)
                    VALUES (?, ?, ?, ?)
                """, (
                    message.get('instance_id'),
                    message.get('chat_name'),
                    message.get('type'),
                    message.get('content')
                ))
                conn.commit()
            return True
        except Exception as e:
            self.logger.error(f"保存消息失败: {e}")
            return False
    
    async def get_messages(self, 
                         processed: Optional[bool] = None,
                         instance_id: Optional[str] = None,
                         chat_name: Optional[str] = None,
                         limit: int = 100) -> List[Dict[str, Any]]:
        """获取消息列表"""
        try:
            with sqlite3.connect(self.db_path) as conn:
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
                        'timestamp': row[5],
                        'processed': bool(row[6])
                    })
                return messages
        except Exception as e:
            self.logger.error(f"获取消息失败: {e}")
            return []
    
    async def mark_as_processed(self, message_id: int) -> bool:
        """标记消息为已处理"""
        return await self._mark_as_processed_sync(message_id)
    
    def _mark_as_processed_sync(self, message_id: int) -> bool:
        """同步标记消息为已处理"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE messages SET processed = TRUE
                    WHERE id = ?
                """, (message_id,))
                conn.commit()
            return True
        except Exception as e:
            self.logger.error(f"标记消息处理状态失败: {e}")
            return False
    
    async def clean_old_messages(self, days: int = 30) -> bool:
        """清理旧消息"""
        return await self._clean_old_messages_sync(days)
    
    def _clean_old_messages_sync(self, days: int) -> bool:
        """同步清理旧消息"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            with sqlite3.connect(self.db_path) as conn:
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
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM messages")
                return cursor.fetchone()[0]
        except Exception as e:
            self.logger.error(f"获取消息总数失败: {e}")
            return 0
    
    async def get_processed_message_count(self) -> int:
        """获取已处理消息数量"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM messages WHERE processed = TRUE")
                return cursor.fetchone()[0]
        except Exception as e:
            self.logger.error(f"获取已处理消息数量失败: {e}")
            return 0
    
    async def get_unprocessed_messages(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取未处理的消息"""
        try:
            with sqlite3.connect(self.db_path) as conn:
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
                        'timestamp': row[5],
                        'processed': bool(row[6])
                    })
                return messages
        except Exception as e:
            self.logger.error(f"获取未处理消息失败: {e}")
            return []
    
    async def close(self):
        """关闭数据库连接"""
        # SQLite连接不需要显式关闭，作为占位符
        pass 