"""
用户会话管理器模块

负责管理用户ID与会话ID的映射关系，支持多平台、多实例、多聊天对象的会话管理。
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any

from ..data.db_manager import db_manager

logger = logging.getLogger(__name__)

class UserConversationManager:
    """用户会话管理器，管理用户ID与会话ID的映射关系"""

    def __init__(self):
        """初始化用户会话管理器"""
        self._initialized = False
        self._lock = asyncio.Lock()
        self._cache = {}  # 缓存，格式: {(instance_id, chat_name, user_id, platform_id): conversation_id}

    async def initialize(self) -> bool:
        """
        初始化管理器

        Returns:
            bool: 是否初始化成功
        """
        if self._initialized:
            return True

        try:
            # 确保数据库表已创建
            await self._ensure_table()

            # 从数据库加载会话映射
            await self._load_conversations()

            self._initialized = True
            logger.info("用户会话管理器初始化完成")
            return True
        except Exception as e:
            logger.error(f"初始化用户会话管理器失败: {e}")
            return False

    async def _ensure_table(self) -> None:
        """确保数据库表已创建"""
        try:
            # 检查表是否存在
            result = await db_manager.fetchone(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='user_conversations'"
            )

            if not result:
                # 创建表
                await db_manager.execute("""
                CREATE TABLE IF NOT EXISTS user_conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    instance_id TEXT NOT NULL,
                    chat_name TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    conversation_id TEXT NOT NULL,
                    platform_id TEXT NOT NULL,
                    last_active INTEGER NOT NULL,
                    create_time INTEGER NOT NULL,
                    UNIQUE(instance_id, chat_name, user_id, platform_id)
                )
                """)
                
                # 创建索引
                await db_manager.execute(
                    "CREATE INDEX IF NOT EXISTS idx_user_conversations_instance_id ON user_conversations(instance_id)"
                )
                await db_manager.execute(
                    "CREATE INDEX IF NOT EXISTS idx_user_conversations_user_id ON user_conversations(user_id)"
                )
                await db_manager.execute(
                    "CREATE INDEX IF NOT EXISTS idx_user_conversations_conversation_id ON user_conversations(conversation_id)"
                )
                
                logger.info("创建user_conversations表")
        except Exception as e:
            logger.error(f"确保数据库表存在时出错: {e}")
            raise

    async def _load_conversations(self) -> None:
        """从数据库加载会话映射"""
        try:
            # 查询所有会话映射
            conversations = await db_manager.fetchall(
                "SELECT * FROM user_conversations"
            )

            # 更新缓存
            self._cache = {
                (conv['instance_id'], conv['chat_name'], conv['user_id'], conv['platform_id']): conv['conversation_id']
                for conv in conversations
            }
            
            logger.info(f"加载了 {len(conversations)} 个用户会话映射")
        except Exception as e:
            logger.error(f"加载用户会话映射失败: {e}")
            raise

    async def get_conversation_id(self, instance_id: str, chat_name: str, user_id: str, platform_id: str) -> Optional[str]:
        """
        获取用户的会话ID

        Args:
            instance_id: 实例ID
            chat_name: 聊天对象名称
            user_id: 用户ID
            platform_id: 平台ID

        Returns:
            Optional[str]: 会话ID，如果不存在则返回None
        """
        if not self._initialized:
            await self.initialize()

        # 先从缓存中查找
        cache_key = (instance_id, chat_name, user_id, platform_id)
        if cache_key in self._cache:
            # 更新最后活跃时间
            current_time = int(time.time())
            await db_manager.execute(
                "UPDATE user_conversations SET last_active = ? WHERE instance_id = ? AND chat_name = ? AND user_id = ? AND platform_id = ?",
                (current_time, instance_id, chat_name, user_id, platform_id)
            )
            return self._cache[cache_key]

        # 从数据库中查找
        conversation = await db_manager.fetchone(
            """
            SELECT conversation_id FROM user_conversations
            WHERE instance_id = ? AND chat_name = ? AND user_id = ? AND platform_id = ?
            """,
            (instance_id, chat_name, user_id, platform_id)
        )

        if conversation:
            # 更新缓存
            self._cache[cache_key] = conversation['conversation_id']
            
            # 更新最后活跃时间
            current_time = int(time.time())
            await db_manager.execute(
                "UPDATE user_conversations SET last_active = ? WHERE instance_id = ? AND chat_name = ? AND user_id = ? AND platform_id = ?",
                (current_time, instance_id, chat_name, user_id, platform_id)
            )
            
            return conversation['conversation_id']

        return None

    async def save_conversation_id(self, instance_id: str, chat_name: str, user_id: str, platform_id: str, conversation_id: str) -> bool:
        """
        保存用户的会话ID

        Args:
            instance_id: 实例ID
            chat_name: 聊天对象名称
            user_id: 用户ID
            platform_id: 平台ID
            conversation_id: 会话ID

        Returns:
            bool: 是否保存成功
        """
        if not self._initialized:
            await self.initialize()

        try:
            async with self._lock:
                current_time = int(time.time())
                
                # 检查是否已存在
                existing = await db_manager.fetchone(
                    """
                    SELECT id FROM user_conversations
                    WHERE instance_id = ? AND chat_name = ? AND user_id = ? AND platform_id = ?
                    """,
                    (instance_id, chat_name, user_id, platform_id)
                )
                
                if existing:
                    # 更新现有记录
                    await db_manager.execute(
                        """
                        UPDATE user_conversations
                        SET conversation_id = ?, last_active = ?
                        WHERE instance_id = ? AND chat_name = ? AND user_id = ? AND platform_id = ?
                        """,
                        (conversation_id, current_time, instance_id, chat_name, user_id, platform_id)
                    )
                else:
                    # 插入新记录
                    await db_manager.execute(
                        """
                        INSERT INTO user_conversations
                        (instance_id, chat_name, user_id, platform_id, conversation_id, last_active, create_time)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (instance_id, chat_name, user_id, platform_id, conversation_id, current_time, current_time)
                    )
                
                # 更新缓存
                cache_key = (instance_id, chat_name, user_id, platform_id)
                self._cache[cache_key] = conversation_id
                
                logger.info(f"保存用户会话ID成功: {instance_id} - {chat_name} - {user_id} - {conversation_id}")
                return True
        except Exception as e:
            logger.error(f"保存用户会话ID失败: {e}")
            return False

    async def delete_conversation_id(self, instance_id: str, chat_name: str, user_id: str, platform_id: str) -> bool:
        """
        删除用户的会话ID

        Args:
            instance_id: 实例ID
            chat_name: 聊天对象名称
            user_id: 用户ID
            platform_id: 平台ID

        Returns:
            bool: 是否删除成功
        """
        if not self._initialized:
            await self.initialize()

        try:
            async with self._lock:
                # 从数据库中删除
                await db_manager.execute(
                    """
                    DELETE FROM user_conversations
                    WHERE instance_id = ? AND chat_name = ? AND user_id = ? AND platform_id = ?
                    """,
                    (instance_id, chat_name, user_id, platform_id)
                )
                
                # 从缓存中删除
                cache_key = (instance_id, chat_name, user_id, platform_id)
                if cache_key in self._cache:
                    del self._cache[cache_key]
                
                logger.info(f"删除用户会话ID成功: {instance_id} - {chat_name} - {user_id}")
                return True
        except Exception as e:
            logger.error(f"删除用户会话ID失败: {e}")
            return False

    async def clear_expired_conversations(self, expire_days: int = 30) -> int:
        """
        清理过期的会话ID

        Args:
            expire_days: 过期天数，默认30天

        Returns:
            int: 清理的记录数
        """
        if not self._initialized:
            await self.initialize()

        try:
            # 计算过期时间
            expire_time = int(time.time()) - expire_days * 24 * 60 * 60
            
            # 删除过期记录
            result = await db_manager.execute(
                "DELETE FROM user_conversations WHERE last_active < ?",
                (expire_time,)
            )
            
            # 获取影响的行数
            affected_rows = result.rowcount if hasattr(result, 'rowcount') else 0
            
            # 重新加载缓存
            await self._load_conversations()
            
            logger.info(f"清理了 {affected_rows} 个过期的用户会话")
            return affected_rows
        except Exception as e:
            logger.error(f"清理过期用户会话失败: {e}")
            return 0

# 创建单例实例
user_conversation_manager = UserConversationManager()
