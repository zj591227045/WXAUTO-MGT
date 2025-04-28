"""
修复消息循环问题的脚本

该脚本提供了一个彻底的解决方案，用于解决系统自己发送的回复消息被再次处理的问题。
"""

import asyncio
import logging
import os
import sqlite3
import time
from typing import List, Dict, Any

# 配置日志
os.makedirs(os.path.join('data', 'logs'), exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join('data', 'logs', 'fix_message_loop.log'))
    ]
)

logger = logging.getLogger(__name__)

# 数据库路径
DB_PATH = os.path.join('data', 'wxauto_mgt.db')

class DBHelper:
    """数据库辅助类"""

    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = None

    async def connect(self):
        """连接数据库"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            logger.info(f"已连接到数据库: {self.db_path}")
            return True
        except Exception as e:
            logger.error(f"连接数据库失败: {e}")
            return False

    async def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            logger.info("已关闭数据库连接")

    async def execute(self, sql, params=None):
        """执行SQL语句"""
        try:
            if params:
                self.conn.execute(sql, params)
            else:
                self.conn.execute(sql)
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"执行SQL失败: {e}")
            return False

    async def fetchall(self, sql, params=None):
        """查询多条记录"""
        try:
            if params:
                cursor = self.conn.execute(sql, params)
            else:
                cursor = self.conn.execute(sql)

            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"查询失败: {e}")
            return []

async def identify_self_messages(db) -> List[Dict[str, Any]]:
    """
    识别数据库中的Self消息

    Returns:
        List[Dict[str, Any]]: Self消息列表
    """
    try:
        # 查询所有sender为Self的消息
        query = """
        SELECT * FROM messages
        WHERE sender = 'Self' OR sender = 'self'
        ORDER BY create_time DESC
        """
        messages = await db.fetchall(query)
        logger.info(f"找到 {len(messages)} 条Self发送的消息")
        return messages
    except Exception as e:
        logger.error(f"查询Self消息失败: {e}")
        return []

async def identify_reply_messages(db) -> List[Dict[str, Any]]:
    """
    识别数据库中的回复消息

    Returns:
        List[Dict[str, Any]]: 回复消息列表
    """
    try:
        # 查询所有已回复的消息
        query = """
        SELECT * FROM messages
        WHERE reply_status = 1 AND reply_content IS NOT NULL AND reply_content != ''
        ORDER BY reply_time DESC
        """
        messages = await db.fetchall(query)
        logger.info(f"找到 {len(messages)} 条已回复的消息")
        return messages
    except Exception as e:
        logger.error(f"查询回复消息失败: {e}")
        return []

async def find_message_loops(db) -> List[Dict[str, Any]]:
    """
    查找消息循环

    Returns:
        List[Dict[str, Any]]: 形成循环的消息列表
    """
    try:
        # 获取所有回复消息
        reply_messages = await identify_reply_messages(db)

        # 获取所有Self消息
        self_messages = await identify_self_messages(db)

        # 查找内容匹配的消息
        loop_messages = []
        for self_msg in self_messages:
            self_content = self_msg.get('content', '')
            if not self_content:
                continue

            for reply_msg in reply_messages:
                reply_content = reply_msg.get('reply_content', '')
                if not reply_content:
                    continue

                # 检查内容是否匹配
                if self_content == reply_content:
                    # 检查时间差是否合理（5分钟内）
                    self_time = self_msg.get('create_time', 0)
                    reply_time = reply_msg.get('reply_time', 0)

                    if 0 < self_time - reply_time < 300:  # 5分钟 = 300秒
                        loop_messages.append(self_msg)
                        logger.info(f"找到循环消息: ID={self_msg.get('message_id')}, 内容={self_content[:50]}")
                        break

        logger.info(f"找到 {len(loop_messages)} 条形成循环的消息")
        return loop_messages
    except Exception as e:
        logger.error(f"查找消息循环失败: {e}")
        return []

async def mark_messages_as_processed(db, messages: List[Dict[str, Any]]) -> int:
    """
    标记消息为已处理

    Args:
        messages: 消息列表

    Returns:
        int: 标记成功的消息数量
    """
    try:
        count = 0
        for msg in messages:
            message_id = msg.get('message_id')
            if not message_id:
                continue

            # 标记为已处理
            await db.execute(
                "UPDATE messages SET processed = 1 WHERE message_id = ?",
                (message_id,)
            )
            count += 1
            logger.info(f"已标记消息为已处理: ID={message_id}")

        logger.info(f"共标记 {count} 条消息为已处理")
        return count
    except Exception as e:
        logger.error(f"标记消息为已处理失败: {e}")
        return 0

async def fix_message_filter(db) -> bool:
    """
    修复消息过滤器

    Returns:
        bool: 是否修复成功
    """
    try:
        # 查询所有未处理的Self消息
        query = """
        SELECT * FROM messages
        WHERE (sender = 'Self' OR sender = 'self') AND processed = 0
        """
        messages = await db.fetchall(query)
        logger.info(f"找到 {len(messages)} 条未处理的Self消息")

        # 标记为已处理
        count = await mark_messages_as_processed(db, messages)

        # 查找并修复消息循环
        loop_messages = await find_message_loops(db)
        loop_count = await mark_messages_as_processed(db, loop_messages)

        logger.info(f"共修复 {count + loop_count} 条消息")
        return True
    except Exception as e:
        logger.error(f"修复消息过滤器失败: {e}")
        return False

async def add_permanent_fix(db) -> bool:
    """
    添加永久性修复

    Returns:
        bool: 是否添加成功
    """
    try:
        # 创建触发器，自动删除Self和Time类型的消息
        # 先删除旧的触发器（如果存在）
        drop_trigger_sql = """
        DROP TRIGGER IF EXISTS delete_self_time_messages;
        """
        await db.execute(drop_trigger_sql)

        # 创建新的触发器，确保匹配所有可能的大小写和字段名
        trigger_sql = """
        CREATE TRIGGER IF NOT EXISTS delete_self_time_messages
        AFTER INSERT ON messages
        FOR EACH ROW
        WHEN LOWER(NEW.sender) = 'self' OR
             LOWER(NEW.message_type) = 'self' OR
             LOWER(NEW.message_type) = 'time'
        BEGIN
            DELETE FROM messages WHERE message_id = NEW.message_id;
        END;
        """

        await db.execute(trigger_sql)
        logger.info("已添加数据库触发器，自动删除Self和Time类型的消息")

        # 创建触发器，自动将内容与回复匹配的消息标记为已处理
        match_trigger_sql = """
        CREATE TRIGGER IF NOT EXISTS mark_reply_match_processed
        AFTER INSERT ON messages
        FOR EACH ROW
        BEGIN
            UPDATE messages
            SET processed = 1
            WHERE message_id = NEW.message_id
            AND EXISTS (
                SELECT 1 FROM messages
                WHERE reply_content = NEW.content
                AND reply_status = 1
                AND reply_time > (NEW.create_time - 300)
            );
        END;
        """

        await db.execute(match_trigger_sql)
        logger.info("已添加数据库触发器，自动将内容与回复匹配的消息标记为已处理")

        return True
    except Exception as e:
        logger.error(f"添加永久性修复失败: {e}")
        return False

async def main():
    """主函数"""
    db = DBHelper(DB_PATH)
    try:
        logger.info("开始修复消息循环问题")

        # 连接数据库
        await db.connect()

        # 修复现有问题
        await fix_message_filter(db)

        # 添加永久性修复
        await add_permanent_fix(db)

        logger.info("修复完成")
    except Exception as e:
        logger.error(f"修复过程出错: {e}")
    finally:
        # 关闭数据库连接
        await db.close()

if __name__ == "__main__":
    asyncio.run(main())
