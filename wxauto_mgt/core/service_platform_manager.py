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
from wxauto_mgt.core.config_notifier import config_notifier, ConfigChangeType

logger = logging.getLogger(__name__)

class ServicePlatformManager:
    """服务平台管理器"""

    def __init__(self):
        """初始化服务平台管理器"""
        self._platforms: Dict[str, ServicePlatform] = {}
        self._initialized = False
        # 添加锁，用于确保并发安全
        import asyncio
        self._lock = asyncio.Lock()

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

    async def register_platform(self, platform_type: str, name: str, config: Dict[str, Any], enabled: bool = True) -> Optional[str]:
        """
        注册新的服务平台

        Args:
            platform_type: 平台类型
            name: 平台名称
            config: 平台配置
            enabled: 是否启用平台

        Returns:
            Optional[str]: 平台ID，如果注册失败则返回None
        """
        if not self._initialized:
            await self.initialize()

        # 使用锁确保同一时间只有一个注册操作
        async with self._lock:
            try:
                # 生成平台ID
                platform_id = f"{platform_type}_{uuid.uuid4().hex[:8]}"
                logger.info(f"开始注册平台: {name} (类型: {platform_type})")

                # 创建平台实例
                platform = create_platform(platform_type, platform_id, name, config)
                if not platform:
                    logger.error(f"创建平台实例失败: {name}")
                    return None

                # 只有在启用时才初始化平台
                if enabled:
                    try:
                        if not await platform.initialize():
                            logger.error(f"初始化平台失败: {name}")
                            return None
                    except Exception as init_error:
                        logger.error(f"初始化平台时出错: {init_error}")
                        return None

                # 保存到数据库
                try:
                    now = int(time.time())
                    await db_manager.insert('service_platforms', {
                        'platform_id': platform_id,
                        'name': name,
                        'type': platform_type,
                        'config': json.dumps(config),
                        'enabled': 1 if enabled else 0,
                        'create_time': now,
                        'update_time': now
                    })
                except Exception as db_error:
                    logger.error(f"保存平台到数据库时出错: {db_error}")
                    return None

                # 只有在启用时才添加到管理器
                try:
                    if enabled:
                        self._platforms[platform_id] = platform
                    logger.info(f"注册平台成功: {name} ({platform_id}) - {'启用' if enabled else '禁用'}")

                    # 发送配置变更通知
                    await config_notifier.notify(ConfigChangeType.PLATFORM_ADDED, {
                        'platform_id': platform_id,
                        'name': name,
                        'type': platform_type,
                        'enabled': enabled
                    })

                    return platform_id
                except Exception as add_error:
                    logger.error(f"添加平台到管理器时出错: {add_error}")
                    return None
            except Exception as e:
                logger.error(f"注册平台失败: {e}")
                import traceback
                logger.error(f"异常堆栈: {traceback.format_exc()}")
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
        获取所有服务平台（包括禁用的）

        Returns:
            List[Dict[str, Any]]: 服务平台列表
        """
        if not self._initialized:
            await self.initialize()

        try:
            # 从数据库获取所有平台（包括禁用的）
            platforms = await db_manager.fetchall(
                "SELECT * FROM service_platforms ORDER BY create_time DESC"
            )

            result = []
            for platform in platforms:
                try:
                    # 解析配置
                    config = json.loads(platform['config'])

                    # 检查平台是否在内存中已初始化
                    platform_id = platform['platform_id']
                    platform_instance = self._platforms.get(platform_id)
                    initialized = False

                    if platform_instance:
                        initialized = platform_instance._initialized
                    elif platform['enabled'] == 1:
                        # 如果平台启用但不在内存中，尝试加载并初始化
                        try:
                            platform_instance = create_platform(
                                platform['type'],
                                platform_id,
                                platform['name'],
                                config
                            )
                            if platform_instance:
                                initialized = await platform_instance.initialize()
                                if initialized:
                                    self._platforms[platform_id] = platform_instance
                                    logger.info(f"延迟加载平台成功: {platform['name']} ({platform_id})")
                        except Exception as init_error:
                            logger.warning(f"延迟初始化平台失败: {platform['name']} ({platform_id}) - {init_error}")

                    # 构建平台数据
                    platform_data = {
                        'platform_id': platform_id,
                        'name': platform['name'],
                        'type': platform['type'],
                        'config': config,
                        'enabled': platform['enabled'] == 1,
                        'initialized': initialized,
                        'create_time': platform['create_time'],
                        'update_time': platform['update_time']
                    }

                    result.append(platform_data)
                except Exception as e:
                    logger.error(f"解析平台数据失败: {platform.get('platform_id', 'unknown')} - {e}")
                    continue

            return result
        except Exception as e:
            logger.error(f"获取所有平台失败: {e}")
            # 如果数据库查询失败，返回内存中的平台
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

        # 使用锁确保同一时间只有一个更新操作
        async with self._lock:
            try:
                logger.info(f"开始更新平台: {platform_id}")

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
                try:
                    if not await platform.initialize():
                        logger.error(f"初始化平台失败: {name}")
                        return False
                except Exception as init_error:
                    logger.error(f"初始化平台时出错: {init_error}")
                    return False

                # 更新数据库
                try:
                    now = int(time.time())
                    await db_manager.execute(
                        """
                        UPDATE service_platforms
                        SET name = ?, config = ?, update_time = ?
                        WHERE platform_id = ?
                        """,
                        (name, json.dumps(config), now, platform_id)
                    )
                except Exception as db_error:
                    logger.error(f"更新数据库时出错: {db_error}")
                    return False

                # 更新管理器
                try:
                    self._platforms[platform_id] = platform
                    logger.info(f"更新平台成功: {name} ({platform_id})")

                    # 发送配置变更通知
                    await config_notifier.notify(ConfigChangeType.PLATFORM_UPDATED, {
                        'platform_id': platform_id,
                        'name': name,
                        'config': config
                    })

                    return True
                except Exception as update_error:
                    logger.error(f"更新平台管理器时出错: {update_error}")
                    return False
            except Exception as e:
                logger.error(f"更新平台失败: {e}")
                import traceback
                logger.error(f"异常堆栈: {traceback.format_exc()}")
                return False

    async def update_platform_simple(self, platform_id: str, name: str, config: Dict[str, Any]) -> bool:
        """
        简单更新服务平台配置

        这个方法只更新数据库中的配置，不使用锁。
        适用于UI线程调用，避免任务嵌套问题。

        更新后会自动重新加载平台实例，无需重启应用。

        Args:
            platform_id: 平台ID
            name: 平台名称
            config: 平台配置

        Returns:
            bool: 是否更新成功
        """
        try:
            # 检查平台是否存在
            platform_data = await db_manager.fetchone(
                "SELECT * FROM service_platforms WHERE platform_id = ?",
                (platform_id,)
            )

            if not platform_data:
                logger.error(f"平台不存在: {platform_id}")
                return False

            # 直接更新数据库
            now = int(time.time())
            await db_manager.execute(
                """
                UPDATE service_platforms
                SET name = ?, config = ?, update_time = ?
                WHERE platform_id = ?
                """,
                (name, json.dumps(config), now, platform_id)
            )

            # 重新加载平台实例
            try:
                # 创建新的平台实例
                platform = create_platform(
                    platform_data['type'],
                    platform_id,
                    name,
                    config
                )

                if platform:
                    # 初始化平台
                    await platform.initialize()

                    # 更新管理器中的平台实例
                    self._platforms[platform_id] = platform
                    logger.info(f"重新加载平台实例成功: {name} ({platform_id})")
                else:
                    logger.warning(f"创建平台实例失败，但数据库已更新: {name} ({platform_id})")
            except Exception as reload_error:
                logger.warning(f"重新加载平台实例失败，但数据库已更新: {reload_error}")

            logger.info(f"简单更新平台配置成功: {name} ({platform_id})")

            # 发送配置变更通知
            await config_notifier.notify(ConfigChangeType.PLATFORM_UPDATED, {
                'platform_id': platform_id,
                'name': name,
                'config': config
            })

            return True
        except Exception as e:
            logger.error(f"简单更新平台配置失败: {e}")
            import traceback
            logger.error(f"异常堆栈: {traceback.format_exc()}")
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

        # 使用锁确保同一时间只有一个删除操作
        async with self._lock:
            try:
                logger.info(f"开始删除平台: {platform_id}")

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
                try:
                    await db_manager.execute(
                        "DELETE FROM service_platforms WHERE platform_id = ?",
                        (platform_id,)
                    )
                except Exception as db_error:
                    logger.error(f"从数据库删除平台时出错: {db_error}")
                    return False

                # 从管理器删除
                try:
                    if platform_id in self._platforms:
                        del self._platforms[platform_id]
                    logger.info(f"删除平台成功: {platform_id}")

                    # 发送配置变更通知
                    await config_notifier.notify(ConfigChangeType.PLATFORM_DELETED, {
                        'platform_id': platform_id
                    })

                    return True
                except Exception as del_error:
                    logger.error(f"从管理器删除平台时出错: {del_error}")
                    return False
            except Exception as e:
                logger.error(f"删除平台失败: {e}")
                import traceback
                logger.error(f"异常堆栈: {traceback.format_exc()}")
                return False

    async def delete_platform_simple(self, platform_id: str) -> bool:
        """
        简单删除服务平台

        这个方法只从数据库中删除平台，不使用锁。
        适用于UI线程调用，避免任务嵌套问题。

        删除后会自动从内存中移除平台实例，无需重启应用。

        Args:
            platform_id: 平台ID

        Returns:
            bool: 是否删除成功
        """
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

            # 直接从数据库删除
            await db_manager.execute(
                "DELETE FROM service_platforms WHERE platform_id = ?",
                (platform_id,)
            )

            # 从内存中移除平台实例
            try:
                if platform_id in self._platforms:
                    del self._platforms[platform_id]
                    logger.info(f"从内存中移除平台实例成功: {platform_id}")
            except Exception as remove_error:
                logger.warning(f"从内存中移除平台实例失败，但数据库已更新: {remove_error}")

            logger.info(f"简单删除平台成功: {platform_id}")

            # 发送配置变更通知
            await config_notifier.notify(ConfigChangeType.PLATFORM_DELETED, {
                'platform_id': platform_id
            })

            return True
        except Exception as e:
            logger.error(f"简单删除平台失败: {e}")
            import traceback
            logger.error(f"异常堆栈: {traceback.format_exc()}")
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

        # 使用锁确保同一时间只有一个启用/禁用操作
        async with self._lock:
            try:
                logger.info(f"开始{'启用' if enabled else '禁用'}平台: {platform_id}")

                # 检查平台是否存在
                platform_data = await db_manager.fetchone(
                    "SELECT * FROM service_platforms WHERE platform_id = ?",
                    (platform_id,)
                )

                if not platform_data:
                    logger.error(f"平台不存在: {platform_id}")
                    return False

                # 更新数据库
                try:
                    now = int(time.time())
                    await db_manager.execute(
                        """
                        UPDATE service_platforms
                        SET enabled = ?, update_time = ?
                        WHERE platform_id = ?
                        """,
                        (1 if enabled else 0, now, platform_id)
                    )
                except Exception as db_error:
                    logger.error(f"更新数据库时出错: {db_error}")
                    return False

                # 更新管理器
                try:
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

                    logger.info(f"{'启用' if enabled else '禁用'}平台成功: {platform_id}")

                    # 发送配置变更通知
                    change_type = ConfigChangeType.PLATFORM_ENABLED if enabled else ConfigChangeType.PLATFORM_DISABLED
                    await config_notifier.notify(change_type, {
                        'platform_id': platform_id,
                        'enabled': enabled
                    })

                    return True
                except Exception as update_error:
                    logger.error(f"更新管理器时出错: {update_error}")
                    return False
            except Exception as e:
                logger.error(f"{'启用' if enabled else '禁用'}平台失败: {e}")
                import traceback
                logger.error(f"异常堆栈: {traceback.format_exc()}")
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
                    only_at_messages INTEGER NOT NULL DEFAULT 0,
                    at_name TEXT DEFAULT '',
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
            else:
                # 表已存在，检查并添加缺失的列
                await self._ensure_columns()

        except Exception as e:
            logger.error(f"确保数据库表存在时出错: {e}")
            raise

    async def _ensure_columns(self) -> None:
        """确保表有必要的列"""
        try:
            # 获取表结构
            columns_result = await db_manager.fetchall(
                "PRAGMA table_info(delivery_rules)"
            )

            # 转换为列名列表
            column_names = [col['name'] for col in columns_result]

            # 检查并添加缺失的列
            if 'only_at_messages' not in column_names:
                logger.info("添加only_at_messages列到delivery_rules表")
                await db_manager.execute(
                    "ALTER TABLE delivery_rules ADD COLUMN only_at_messages INTEGER DEFAULT 0"
                )

            if 'at_name' not in column_names:
                logger.info("添加at_name列到delivery_rules表")
                await db_manager.execute(
                    "ALTER TABLE delivery_rules ADD COLUMN at_name TEXT DEFAULT ''"
                )

            # 添加回复时@发送者的字段
            if 'reply_at_sender' not in column_names:
                logger.info("添加reply_at_sender列到delivery_rules表")
                await db_manager.execute(
                    "ALTER TABLE delivery_rules ADD COLUMN reply_at_sender INTEGER DEFAULT 0"
                )

        except Exception as e:
            logger.error(f"确保表列存在时出错: {e}")
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
                      platform_id: str, priority: int = 0, only_at_messages: int = 0,
                      at_name: str = '', reply_at_sender: int = 0) -> Optional[str]:
        """
        添加新规则

        Args:
            name: 规则名称
            instance_id: 实例ID
            chat_pattern: 聊天对象匹配模式
            platform_id: 服务平台ID
            priority: 规则优先级
            only_at_messages: 是否只响应@消息，0-否，1-是
            at_name: 被@的名称
            reply_at_sender: 回复时是否@发送者，0-否，1-是

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
                'only_at_messages': only_at_messages,
                'at_name': at_name,
                'reply_at_sender': reply_at_sender,
                'create_time': now,
                'update_time': now
            })

            # 重新加载规则
            await self._load_rules()

            logger.info(f"添加规则: {name} ({rule_id})")

            # 发送配置变更通知
            await config_notifier.notify(ConfigChangeType.RULE_ADDED, {
                'rule_id': rule_id,
                'name': name,
                'instance_id': instance_id,
                'chat_pattern': chat_pattern,
                'platform_id': platform_id,
                'priority': priority
            })

            return rule_id
        except Exception as e:
            logger.error(f"添加规则失败: {e}")
            return None

    async def update_rule(self, rule_id: str, name: str, instance_id: str,
                         chat_pattern: str, platform_id: str, priority: int,
                         only_at_messages: int = 0, at_name: str = '', reply_at_sender: int = 0) -> bool:
        """
        更新规则

        Args:
            rule_id: 规则ID
            name: 规则名称
            instance_id: 实例ID
            chat_pattern: 聊天对象匹配模式
            platform_id: 服务平台ID
            priority: 规则优先级
            only_at_messages: 是否只响应@消息，0-否，1-是
            at_name: 被@的名称
            reply_at_sender: 回复时是否@发送者，0-否，1-是

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
                    platform_id = ?, priority = ?, only_at_messages = ?,
                    at_name = ?, reply_at_sender = ?, update_time = ?
                WHERE rule_id = ?
                """,
                (name, instance_id, chat_pattern, platform_id, priority,
                 only_at_messages, at_name, reply_at_sender, now, rule_id)
            )

            # 重新加载规则
            await self._load_rules()

            logger.info(f"更新规则: {name} ({rule_id})")

            # 发送配置变更通知
            await config_notifier.notify(ConfigChangeType.RULE_UPDATED, {
                'rule_id': rule_id,
                'name': name,
                'instance_id': instance_id,
                'chat_pattern': chat_pattern,
                'platform_id': platform_id,
                'priority': priority
            })

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

            # 发送配置变更通知
            await config_notifier.notify(ConfigChangeType.RULE_DELETED, {
                'rule_id': rule_id
            })

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

            # 发送配置变更通知
            change_type = ConfigChangeType.RULE_ENABLED if enabled else ConfigChangeType.RULE_DISABLED
            await config_notifier.notify(change_type, {
                'rule_id': rule_id,
                'enabled': enabled
            })

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

    def _match_chat_pattern(self, pattern: str, chat_name: str) -> bool:
        """
        匹配聊天对象模式

        Args:
            pattern: 聊天对象匹配模式
            chat_name: 聊天对象名称

        Returns:
            bool: 是否匹配
        """
        # 通配符匹配
        if pattern == '*':
            return True
        # 正则表达式匹配
        elif pattern.startswith('regex:'):
            regex = pattern[6:]
            try:
                if re.match(regex, chat_name):
                    return True
            except Exception as e:
                logger.error(f"正则表达式匹配失败: {e}")
        # 逗号分隔的多个精确匹配
        elif ',' in pattern:
            # 分割并去除空白
            patterns = [p.strip() for p in pattern.split(',')]
            if chat_name in patterns:
                return True
        # 单个精确匹配
        else:
            if pattern == chat_name:
                return True

        return False

    async def get_rule_by_platform_and_chat(self, platform_id: str, instance_id: str, chat_name: str) -> Optional[Dict[str, Any]]:
        """
        根据平台ID和聊天对象获取规则

        Args:
            platform_id: 平台ID
            instance_id: 实例ID
            chat_name: 聊天对象名称

        Returns:
            Optional[Dict[str, Any]]: 匹配的规则，如果没有匹配则返回None
        """
        if not self._initialized:
            await self.initialize()

        try:
            # 查询所有规则
            rules = await self.get_all_rules()

            # 过滤出平台ID匹配的规则
            platform_rules = [rule for rule in rules if rule['platform_id'] == platform_id]

            # 按优先级排序（降序）
            platform_rules.sort(key=lambda x: (-x['priority'], x['rule_id']))

            # 遍历规则，找到匹配的规则
            for rule in platform_rules:
                # 检查实例ID是否匹配
                if rule['instance_id'] != instance_id and rule['instance_id'] != '*':
                    continue

                # 检查聊天对象是否匹配
                chat_pattern = rule['chat_pattern']
                if self._match_chat_pattern(chat_pattern, chat_name):
                    return rule

            return None
        except Exception as e:
            logger.error(f"根据平台ID和聊天对象获取规则失败: {e}")
            return None

    async def match_rule(self, instance_id: str, chat_name: str, message_content: str = None) -> Optional[Dict[str, Any]]:
        """
        匹配规则

        Args:
            instance_id: 实例ID
            chat_name: 聊天对象名称
            message_content: 消息内容，用于检查@消息

        Returns:
            Optional[Dict[str, Any]]: 匹配的规则
        """
        if not self._initialized:
            await self.initialize()

        logger.info(f"开始匹配规则: 实例={instance_id}, 聊天={chat_name}, 消息内容={message_content[:50] if message_content else 'None'}...")
        logger.info(f"当前共有 {len(self._rules)} 条规则")

        # 按优先级遍历规则
        for rule in self._rules:
            rule_id = rule.get('rule_id', '未知')
            rule_name = rule.get('name', '未知')
            rule_instance = rule.get('instance_id', '')
            rule_pattern = rule.get('chat_pattern', '')
            rule_only_at = rule.get('only_at_messages', 0)
            rule_at_name = rule.get('at_name', '')

            logger.info(f"检查规则: ID={rule_id}, 名称={rule_name}, 实例={rule_instance}, 模式={rule_pattern}, 只响应@={rule_only_at}, @名称={rule_at_name}")

            # 检查实例ID是否匹配
            if rule['instance_id'] != instance_id and rule['instance_id'] != '*':
                logger.info(f"规则 {rule_id} 实例ID不匹配: 规则={rule_instance}, 当前={instance_id}")
                continue

            # 检查聊天对象是否匹配
            pattern = rule['chat_pattern']
            is_chat_match = self._match_chat_pattern(pattern, chat_name)

            # 记录匹配结果
            if is_chat_match:
                logger.info(f"规则 {rule_id} 聊天对象匹配成功: {pattern} 匹配 {chat_name}")
            else:
                logger.info(f"规则 {rule_id} 聊天对象不匹配: {pattern} 不匹配 {chat_name}")
                continue

            # 注意：@消息的检查逻辑已移至 message_filter.py 和 message_listener.py 中
            # 这里只进行规则匹配，不进行@消息的过滤
            # 在规则匹配阶段，我们不应该过滤掉任何消息，而是返回匹配的规则
            # 然后由调用方根据规则中的 only_at_messages 和 at_name 字段决定是否过滤消息

            # 记录规则的@消息设置，但不进行过滤
            only_at_messages = rule.get('only_at_messages', 0)
            at_name = rule.get('at_name', '')

            if only_at_messages == 1:
                logger.info(f"规则 {rule_id} 要求只响应@消息，@名称: {at_name}")
                # 在调用方进行@消息的过滤，这里只返回匹配的规则
            else:
                logger.info(f"规则 {rule_id} 不要求@消息")

            # 所有条件都匹配，返回规则
            logger.info(f"规则 {rule_id} 匹配成功，返回规则")
            return rule

        logger.info(f"没有匹配到任何规则: 实例={instance_id}, 聊天={chat_name}")
        return None


# 创建全局实例
platform_manager = ServicePlatformManager()
rule_manager = DeliveryRuleManager()
