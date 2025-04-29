"""
服务平台管理器模块

该模块负责管理服务平台，包括：
- 服务平台的注册、获取和删除
- 服务平台配置的保存和加载
- 投递规则的管理和匹配
"""

import logging
import json
import time
import uuid
import re
from typing import Dict, List, Optional, Any

from wxauto_mgt.data.db_manager import db_manager
from wxauto_mgt.core.service_platform import ServicePlatform, create_platform

logger = logging.getLogger(__name__)

class ServicePlatformManager:
    """服务平台管理器"""

    def __init__(self):
        """初始化服务平台管理器"""
        self._platforms: Dict[str, ServicePlatform] = {}
        self._initialized = False

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

            # 从数据库加载平台配置
            await self._load_platforms()

            self._initialized = True
            logger.info(f"服务平台管理器初始化完成，加载了 {len(self._platforms)} 个平台")
            return True
        except Exception as e:
            logger.error(f"初始化服务平台管理器失败: {e}")
            return False

    async def _ensure_table(self) -> None:
        """确保数据库表已创建"""
        try:
            # 检查表是否存在
            result = await db_manager.fetchone(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='service_platforms'"
            )

            if not result:
                # 创建表
                await db_manager.execute("""
                CREATE TABLE IF NOT EXISTS service_platforms (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform_id TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    config TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    create_time INTEGER NOT NULL,
                    update_time INTEGER NOT NULL
                )
                """)
                logger.info("创建service_platforms表")
        except Exception as e:
            logger.error(f"确保数据库表存在时出错: {e}")
            raise

    async def _load_platforms(self) -> None:
        """从数据库加载平台配置"""
        try:
            # 查询所有启用的平台
            platforms = await db_manager.fetchall(
                "SELECT * FROM service_platforms WHERE enabled = 1"
            )

            for platform in platforms:
                try:
                    # 解析配置
                    config = json.loads(platform['config'])

                    # 创建平台实例
                    platform_instance = create_platform(
                        platform['type'],
                        platform['platform_id'],
                        platform['name'],
                        config
                    )

                    if platform_instance:
                        # 初始化平台
                        await platform_instance.initialize()

                        # 添加到管理器
                        self._platforms[platform['platform_id']] = platform_instance
                        logger.info(f"加载平台: {platform['name']} ({platform['platform_id']})")
                    else:
                        logger.error(f"创建平台实例失败: {platform['name']} ({platform['platform_id']})")
                except Exception as e:
                    logger.error(f"加载平台 {platform['platform_id']} 失败: {e}")
        except Exception as e:
            logger.error(f"加载平台配置失败: {e}")
            raise

    async def register_platform(self, platform_type: str, name: str, config: Dict[str, Any]) -> Optional[str]:
        """
        注册新的服务平台

        Args:
            platform_type: 平台类型
            name: 平台名称
            config: 平台配置

        Returns:
            Optional[str]: 平台ID，如果注册失败则返回None
        """
        if not self._initialized:
            await self.initialize()

        try:
            # 生成平台ID
            platform_id = f"{platform_type}_{uuid.uuid4().hex[:8]}"

            # 创建平台实例
            platform = create_platform(platform_type, platform_id, name, config)
            if not platform:
                logger.error(f"创建平台实例失败: {name}")
                return None

            # 初始化平台
            if not await platform.initialize():
                logger.error(f"初始化平台失败: {name}")
                return None

            # 保存到数据库
            now = int(time.time())
            await db_manager.insert('service_platforms', {
                'platform_id': platform_id,
                'name': name,
                'type': platform_type,
                'config': json.dumps(config),
                'enabled': 1,
                'create_time': now,
                'update_time': now
            })

            # 添加到管理器
            self._platforms[platform_id] = platform
            logger.info(f"注册平台: {name} ({platform_id})")

            return platform_id
        except Exception as e:
            logger.error(f"注册平台失败: {e}")
            return None

    async def get_platform(self, platform_id: str) -> Optional[ServicePlatform]:
        """
        获取指定ID的服务平台

        Args:
            platform_id: 平台ID

        Returns:
            Optional[ServicePlatform]: 服务平台实例
        """
        if not self._initialized:
            await self.initialize()

        return self._platforms.get(platform_id)

    async def get_all_platforms(self) -> List[Dict[str, Any]]:
        """
        获取所有服务平台

        Returns:
            List[Dict[str, Any]]: 服务平台列表
        """
        if not self._initialized:
            await self.initialize()

        return [platform.to_dict() for platform in self._platforms.values()]

    async def update_platform(self, platform_id: str, name: str, config: Dict[str, Any]) -> bool:
        """
        更新服务平台配置

        Args:
            platform_id: 平台ID
            name: 平台名称
            config: 平台配置

        Returns:
            bool: 是否更新成功
        """
        if not self._initialized:
            await self.initialize()

        try:
            # 检查平台是否存在
            platform_data = await db_manager.fetchone(
                "SELECT * FROM service_platforms WHERE platform_id = ?",
                (platform_id,)
            )

            if not platform_data:
                logger.error(f"平台不存在: {platform_id}")
                return False

            # 创建新的平台实例
            platform = create_platform(
                platform_data['type'],
                platform_id,
                name,
                config
            )

            if not platform:
                logger.error(f"创建平台实例失败: {name}")
                return False

            # 初始化平台
            if not await platform.initialize():
                logger.error(f"初始化平台失败: {name}")
                return False

            # 更新数据库
            now = int(time.time())
            await db_manager.execute(
                """
                UPDATE service_platforms
                SET name = ?, config = ?, update_time = ?
                WHERE platform_id = ?
                """,
                (name, json.dumps(config), now, platform_id)
            )

            # 更新管理器
            self._platforms[platform_id] = platform
            logger.info(f"更新平台: {name} ({platform_id})")

            return True
        except Exception as e:
            logger.error(f"更新平台失败: {e}")
            return False

    async def delete_platform(self, platform_id: str) -> bool:
        """
        删除服务平台

        Args:
            platform_id: 平台ID

        Returns:
            bool: 是否删除成功
        """
        if not self._initialized:
            await self.initialize()

        try:
            # 检查平台是否存在
            platform_data = await db_manager.fetchone(
                "SELECT * FROM service_platforms WHERE platform_id = ?",
                (platform_id,)
            )

            if not platform_data:
                logger.error(f"平台不存在: {platform_id}")
                return False

            # 检查是否有规则使用该平台
            rules = await db_manager.fetchall(
                "SELECT * FROM delivery_rules WHERE platform_id = ?",
                (platform_id,)
            )

            if rules:
                logger.error(f"平台 {platform_id} 被 {len(rules)} 个规则使用，无法删除")
                return False

            # 从数据库删除
            await db_manager.execute(
                "DELETE FROM service_platforms WHERE platform_id = ?",
                (platform_id,)
            )

            # 从管理器删除
            if platform_id in self._platforms:
                del self._platforms[platform_id]

            logger.info(f"删除平台: {platform_id}")

            return True
        except Exception as e:
            logger.error(f"删除平台失败: {e}")
            return False

    async def enable_platform(self, platform_id: str, enabled: bool) -> bool:
        """
        启用或禁用服务平台

        Args:
            platform_id: 平台ID
            enabled: 是否启用

        Returns:
            bool: 是否操作成功
        """
        if not self._initialized:
            await self.initialize()

        try:
            # 检查平台是否存在
            platform_data = await db_manager.fetchone(
                "SELECT * FROM service_platforms WHERE platform_id = ?",
                (platform_id,)
            )

            if not platform_data:
                logger.error(f"平台不存在: {platform_id}")
                return False

            # 更新数据库
            now = int(time.time())
            await db_manager.execute(
                """
                UPDATE service_platforms
                SET enabled = ?, update_time = ?
                WHERE platform_id = ?
                """,
                (1 if enabled else 0, now, platform_id)
            )

            # 更新管理器
            if enabled:
                if platform_id not in self._platforms:
                    # 重新加载平台
                    config = json.loads(platform_data['config'])
                    platform = create_platform(
                        platform_data['type'],
                        platform_id,
                        platform_data['name'],
                        config
                    )

                    if platform:
                        await platform.initialize()
                        self._platforms[platform_id] = platform
            else:
                if platform_id in self._platforms:
                    del self._platforms[platform_id]

            logger.info(f"{'启用' if enabled else '禁用'}平台: {platform_id}")

            return True
        except Exception as e:
            logger.error(f"{'启用' if enabled else '禁用'}平台失败: {e}")
            return False


class DeliveryRuleManager:
    """投递规则管理器"""

    def __init__(self):
        """初始化投递规则管理器"""
        self._rules: List[Dict[str, Any]] = []
        self._initialized = False

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

            # 从数据库加载规则
            await self._load_rules()

            self._initialized = True
            logger.info(f"投递规则管理器初始化完成，加载了 {len(self._rules)} 个规则")
            return True
        except Exception as e:
            logger.error(f"初始化投递规则管理器失败: {e}")
            return False

    async def _ensure_table(self) -> None:
        """确保数据库表已创建"""
        try:
            # 检查表是否存在
            result = await db_manager.fetchone(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='delivery_rules'"
            )

            if not result:
                # 创建表
                await db_manager.execute("""
                CREATE TABLE IF NOT EXISTS delivery_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rule_id TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    instance_id TEXT NOT NULL,
                    chat_pattern TEXT NOT NULL,
                    platform_id TEXT NOT NULL,
                    priority INTEGER NOT NULL DEFAULT 0,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    create_time INTEGER NOT NULL,
                    update_time INTEGER NOT NULL,
                    FOREIGN KEY (platform_id) REFERENCES service_platforms (platform_id)
                )
                """)

                # 创建索引
                await db_manager.execute(
                    "CREATE INDEX IF NOT EXISTS idx_delivery_rules_instance_id ON delivery_rules(instance_id)"
                )
                await db_manager.execute(
                    "CREATE INDEX IF NOT EXISTS idx_delivery_rules_platform_id ON delivery_rules(platform_id)"
                )
                await db_manager.execute(
                    "CREATE INDEX IF NOT EXISTS idx_delivery_rules_priority ON delivery_rules(priority)"
                )

                logger.info("创建delivery_rules表")
        except Exception as e:
            logger.error(f"确保数据库表存在时出错: {e}")
            raise

    async def _load_rules(self) -> None:
        """从数据库加载规则"""
        try:
            # 查询所有启用的规则，按优先级降序排序
            rules = await db_manager.fetchall(
                "SELECT * FROM delivery_rules WHERE enabled = 1 ORDER BY priority DESC"
            )

            self._rules = rules
            logger.info(f"加载了 {len(rules)} 个投递规则")
        except Exception as e:
            logger.error(f"加载投递规则失败: {e}")
            raise

    async def add_rule(self, name: str, instance_id: str, chat_pattern: str,
                      platform_id: str, priority: int = 0) -> Optional[str]:
        """
        添加新规则

        Args:
            name: 规则名称
            instance_id: 实例ID
            chat_pattern: 聊天对象匹配模式
            platform_id: 服务平台ID
            priority: 规则优先级

        Returns:
            Optional[str]: 规则ID，如果添加失败则返回None
        """
        if not self._initialized:
            await self.initialize()

        try:
            # 检查平台是否存在
            platform_data = await db_manager.fetchone(
                "SELECT * FROM service_platforms WHERE platform_id = ?",
                (platform_id,)
            )

            if not platform_data:
                logger.error(f"平台不存在: {platform_id}")
                return None

            # 生成规则ID
            rule_id = f"rule_{uuid.uuid4().hex[:8]}"

            # 保存到数据库
            now = int(time.time())
            await db_manager.insert('delivery_rules', {
                'rule_id': rule_id,
                'name': name,
                'instance_id': instance_id,
                'chat_pattern': chat_pattern,
                'platform_id': platform_id,
                'priority': priority,
                'enabled': 1,
                'create_time': now,
                'update_time': now
            })

            # 重新加载规则
            await self._load_rules()

            logger.info(f"添加规则: {name} ({rule_id})")

            return rule_id
        except Exception as e:
            logger.error(f"添加规则失败: {e}")
            return None

    async def update_rule(self, rule_id: str, name: str, instance_id: str,
                         chat_pattern: str, platform_id: str, priority: int) -> bool:
        """
        更新规则

        Args:
            rule_id: 规则ID
            name: 规则名称
            instance_id: 实例ID
            chat_pattern: 聊天对象匹配模式
            platform_id: 服务平台ID
            priority: 规则优先级

        Returns:
            bool: 是否更新成功
        """
        if not self._initialized:
            await self.initialize()

        try:
            # 检查规则是否存在
            rule_data = await db_manager.fetchone(
                "SELECT * FROM delivery_rules WHERE rule_id = ?",
                (rule_id,)
            )

            if not rule_data:
                logger.error(f"规则不存在: {rule_id}")
                return False

            # 检查平台是否存在
            platform_data = await db_manager.fetchone(
                "SELECT * FROM service_platforms WHERE platform_id = ?",
                (platform_id,)
            )

            if not platform_data:
                logger.error(f"平台不存在: {platform_id}")
                return False

            # 更新数据库
            now = int(time.time())
            await db_manager.execute(
                """
                UPDATE delivery_rules
                SET name = ?, instance_id = ?, chat_pattern = ?,
                    platform_id = ?, priority = ?, update_time = ?
                WHERE rule_id = ?
                """,
                (name, instance_id, chat_pattern, platform_id, priority, now, rule_id)
            )

            # 重新加载规则
            await self._load_rules()

            logger.info(f"更新规则: {name} ({rule_id})")

            return True
        except Exception as e:
            logger.error(f"更新规则失败: {e}")
            return False

    async def delete_rule(self, rule_id: str) -> bool:
        """
        删除规则

        Args:
            rule_id: 规则ID

        Returns:
            bool: 是否删除成功
        """
        if not self._initialized:
            await self.initialize()

        try:
            # 检查规则是否存在
            rule_data = await db_manager.fetchone(
                "SELECT * FROM delivery_rules WHERE rule_id = ?",
                (rule_id,)
            )

            if not rule_data:
                logger.error(f"规则不存在: {rule_id}")
                return False

            # 从数据库删除
            await db_manager.execute(
                "DELETE FROM delivery_rules WHERE rule_id = ?",
                (rule_id,)
            )

            # 重新加载规则
            await self._load_rules()

            logger.info(f"删除规则: {rule_id}")

            return True
        except Exception as e:
            logger.error(f"删除规则失败: {e}")
            return False

    async def enable_rule(self, rule_id: str, enabled: bool) -> bool:
        """
        启用或禁用规则

        Args:
            rule_id: 规则ID
            enabled: 是否启用

        Returns:
            bool: 是否操作成功
        """
        if not self._initialized:
            await self.initialize()

        try:
            # 检查规则是否存在
            rule_data = await db_manager.fetchone(
                "SELECT * FROM delivery_rules WHERE rule_id = ?",
                (rule_id,)
            )

            if not rule_data:
                logger.error(f"规则不存在: {rule_id}")
                return False

            # 更新数据库
            now = int(time.time())
            await db_manager.execute(
                """
                UPDATE delivery_rules
                SET enabled = ?, update_time = ?
                WHERE rule_id = ?
                """,
                (1 if enabled else 0, now, rule_id)
            )

            # 重新加载规则
            await self._load_rules()

            logger.info(f"{'启用' if enabled else '禁用'}规则: {rule_id}")

            return True
        except Exception as e:
            logger.error(f"{'启用' if enabled else '禁用'}规则失败: {e}")
            return False

    async def get_rule(self, rule_id: str) -> Optional[Dict[str, Any]]:
        """
        获取指定规则

        Args:
            rule_id: 规则ID

        Returns:
            Optional[Dict[str, Any]]: 规则数据
        """
        if not self._initialized:
            await self.initialize()

        try:
            rule_data = await db_manager.fetchone(
                "SELECT * FROM delivery_rules WHERE rule_id = ?",
                (rule_id,)
            )

            return rule_data
        except Exception as e:
            logger.error(f"获取规则失败: {e}")
            return None

    async def get_all_rules(self) -> List[Dict[str, Any]]:
        """
        获取所有规则

        Returns:
            List[Dict[str, Any]]: 规则列表
        """
        if not self._initialized:
            await self.initialize()

        return self._rules

    async def match_rule(self, instance_id: str, chat_name: str) -> Optional[Dict[str, Any]]:
        """
        匹配规则

        Args:
            instance_id: 实例ID
            chat_name: 聊天对象名称

        Returns:
            Optional[Dict[str, Any]]: 匹配的规则
        """
        if not self._initialized:
            await self.initialize()

        # 按优先级遍历规则
        for rule in self._rules:
            # 检查实例ID是否匹配
            if rule['instance_id'] != instance_id and rule['instance_id'] != '*':
                continue

            # 检查聊天对象是否匹配
            pattern = rule['chat_pattern']

            # 通配符匹配
            if pattern == '*':
                # 通配符，匹配所有
                return rule
            # 正则表达式匹配
            elif pattern.startswith('regex:'):
                regex = pattern[6:]
                try:
                    if re.match(regex, chat_name):
                        return rule
                except Exception as e:
                    logger.error(f"正则表达式匹配失败: {e}")
            # 逗号分隔的多个精确匹配
            elif ',' in pattern:
                # 分割并去除空白
                patterns = [p.strip() for p in pattern.split(',')]
                if chat_name in patterns:
                    return rule
            # 单个精确匹配
            else:
                if pattern == chat_name:
                    return rule

        return None


# 创建全局实例
platform_manager = ServicePlatformManager()
rule_manager = DeliveryRuleManager()
