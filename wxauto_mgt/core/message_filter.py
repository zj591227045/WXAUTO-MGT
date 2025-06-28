"""
消息过滤模块

提供统一的消息过滤功能，用于过滤掉不需要处理的消息，如Self发送的消息和Time类型的消息。
"""

import logging
import json
import re
from typing import Dict, List, Any, Optional, Union

# 配置日志
logger = logging.getLogger(__name__)

class MessageFilter:
    """消息过滤器，用于过滤掉不需要处理的消息"""

    @staticmethod
    async def check_at_rule_match(message: Dict[str, Any], instance_id: str, chat_name: str) -> bool:
        """
        检查消息是否符合@规则

        Args:
            message: 消息数据
            instance_id: 实例ID
            chat_name: 聊天对象名称

        Returns:
            bool: 如果符合规则返回True，否则返回False
        """
        try:
            # 导入规则管理器
            from wxauto_mgt.core.service_platform_manager import rule_manager

            # 获取消息内容
            content = message.get('content', '')
            message_id = message.get('message_id', '')

            logger.info(f"检查消息是否符合规则: ID={message_id}, 实例={instance_id}, 聊天={chat_name}, 内容={content[:50]}...")

            # 匹配规则
            rule = await rule_manager.match_rule(instance_id, chat_name, content)

            # 如果没有匹配的规则，返回False
            if not rule:
                logger.info(f"消息没有匹配的规则: ID={message_id}, 实例={instance_id}, 聊天={chat_name}")
                return False

            # 获取规则ID和优先级
            rule_id = rule.get('rule_id', '未知')
            priority = rule.get('priority', 0)

            logger.info(f"匹配到规则: ID={rule_id}, 优先级={priority}, 实例={instance_id}, 聊天={chat_name}")

            # 检查规则是否要求@消息 - 这是针对特定聊天对象的局部设置
            only_at_messages = rule.get('only_at_messages', 0)

            # 只有当规则明确要求@消息时才进行@规则检查
            if only_at_messages == 1:
                logger.info(f"规则 {rule_id} 要求只响应@消息")
                at_name = rule.get('at_name', '')

                # 如果没有指定@名称，直接返回True
                if not at_name:
                    logger.info(f"规则要求@消息但未指定@名称，允许通过: ID={message_id}, 规则={rule_id}")
                    return True

                # 支持多个@名称，用逗号分隔
                at_names = [name.strip() for name in at_name.split(',')]
                logger.info(f"规则要求@消息，@名称列表: {at_names}, ID={message_id}, 规则={rule_id}")

                # 检查消息是否包含任意一个@名称
                for name in at_names:
                    if name and f"@{name}" in content:
                        logger.info(f"消息匹配到@{name}规则，允许通过: ID={message_id}, 规则={rule_id}")
                        return True

                # 如果没有匹配到任何@名称，返回False
                # 添加"不符合@规则"标记，用于UI显示
                # 使用特殊格式，便于UI识别并特殊处理
                logger.info(f"消息不符合@规则，将被过滤: ID={message_id}, 规则={rule_id}, 实例={instance_id}, 聊天={chat_name}, 内容={content[:50]}..., [不符合消息转发规则]")
                return False
            else:
                # 规则不要求@消息，直接返回True
                logger.info(f"规则不要求@消息，允许通过: ID={message_id}, 规则={rule_id}")
                return True

        except Exception as e:
            logger.error(f"检查规则匹配时出错: {e}")
            logger.exception(e)  # 记录完整堆栈
            # 出错时返回True，避免过滤掉消息
            return True

    @staticmethod
    def should_filter_message(message: Dict[str, Any], log_prefix: str = "") -> bool:
        """
        判断消息是否应该被过滤掉

        Args:
            message: 消息数据
            log_prefix: 日志前缀，用于区分不同调用位置的日志

        Returns:
            bool: 如果应该过滤返回True，否则返回False
        """
        if not message:
            return True

        # 提取消息的关键字段
        original_sender = message.get('sender', '')
        original_type = message.get('type', '') or message.get('message_type', '')
        content = message.get('content', '')
        message_id = message.get('id', '') or message.get('message_id', '')

        # 转换为小写进行比较
        sender = original_sender.lower() if original_sender else ''
        msg_type = original_type.lower() if original_type else ''

        # 记录详细的消息信息，便于调试
        logger.debug(f"{log_prefix}检查消息: ID={message_id}, 原始发送者={original_sender}, 小写={sender}, 原始类型={original_type}, 小写={msg_type}")
        logger.debug(f"{log_prefix}消息内容: {content[:100]}")

        try:
            logger.debug(f"{log_prefix}完整消息数据: {json.dumps(message, ensure_ascii=False)}")
        except Exception as e:
            logger.debug(f"{log_prefix}完整消息数据(无法序列化): {str(message)}")

        # 1. 检查发送者是否为Self或SYS（不区分大小写）
        is_self_sender = sender == 'self' or original_sender == 'Self'
        is_sys_sender = sender == 'sys' or original_sender == 'SYS'

        # 2. 检查消息类型是否为self、time、sys或base（不区分大小写）
        # 检查所有可能的类型字段
        message_type = message.get('message_type', '').lower() if isinstance(message.get('message_type'), str) else ''

        # 添加对SYS和base类型消息的过滤
        is_filtered_type = (
            msg_type in ['self', 'time', 'sys', 'base'] or
            message_type in ['self', 'time', 'sys', 'base'] or
            original_type in ['self', 'Self', 'time', 'Time', 'sys', 'SYS', 'base', 'Base']
        )

        # 3. 检查消息对象中是否有明确标记为self、time或sys的字段
        # 检查所有可能的字段名
        possible_fields = ['sender', 'type', 'message_type', 'mtype', 'sender_type']
        has_self_field = any(message.get(field) == 'Self' or
                            (isinstance(message.get(field), str) and message.get(field).lower() == 'self')
                            for field in possible_fields if message.get(field) is not None)

        has_time_field = any(message.get(field) == 'Time' or
                            (isinstance(message.get(field), str) and message.get(field).lower() == 'time')
                            for field in possible_fields if message.get(field) is not None)

        # 添加对SYS字段的检查
        has_sys_field = any(message.get(field) == 'SYS' or
                           (isinstance(message.get(field), str) and message.get(field).lower() == 'sys')
                           for field in possible_fields if message.get(field) is not None)

        # 添加对base字段的检查
        has_base_field = any(message.get(field) == 'Base' or
                            (isinstance(message.get(field), str) and message.get(field).lower() == 'base')
                            for field in possible_fields if message.get(field) is not None)

        # 4. 检查内容中是否包含特定标记
        has_self_content = False
        if content and isinstance(content, str):
            # 检查内容是否包含"Self"字样
            has_self_content = 'Self' in content or '<self>' in content.lower()

        # 5. 检查消息ID是否包含self或time
        has_self_id = False
        has_time_id = False
        if message_id and isinstance(message_id, str):
            message_id_lower = message_id.lower()
            has_self_id = 'self' in message_id_lower
            has_time_id = 'time' in message_id_lower

        # 6. 检查其他可能的标记
        # 如果消息有特定的标记字段，也进行检查
        is_marked_as_self = message.get('is_self', False)
        is_marked_as_time = message.get('is_time', False)

        # 记录过滤条件的判断结果
        logger.debug(
            f"{log_prefix}过滤条件判断: "
            f"is_self_sender={is_self_sender}, "
            f"is_sys_sender={is_sys_sender}, "
            f"is_filtered_type={is_filtered_type}, "
            f"has_self_field={has_self_field}, "
            f"has_time_field={has_time_field}, "
            f"has_sys_field={has_sys_field}, "
            f"has_base_field={has_base_field}, "
            f"has_self_content={has_self_content}, "
            f"has_self_id={has_self_id}, "
            f"has_time_id={has_time_id}, "
            f"is_marked_as_self={is_marked_as_self}, "
            f"is_marked_as_time={is_marked_as_time}"
        )

        # 综合判断是否应该过滤
        should_filter = (
            is_self_sender or
            is_sys_sender or  # 添加对SYS发送者的过滤
            is_filtered_type or
            has_self_field or
            has_time_field or
            has_sys_field or  # 添加对SYS字段的过滤
            has_base_field or  # 添加对base字段的过滤
            has_self_id or
            has_time_id or
            is_marked_as_self or
            is_marked_as_time
        )

        # 如果应该过滤，记录详细信息
        if should_filter:
            logger.debug(
                f"{log_prefix}过滤掉消息: ID={message_id}, "
                f"类型={original_type}({msg_type}), "
                f"发送者={original_sender}({sender})"
            )

        return should_filter

    @staticmethod
    def filter_messages(messages: List[Dict[str, Any]], log_prefix: str = "") -> List[Dict[str, Any]]:
        """
        过滤消息列表，移除应该被过滤的消息

        Args:
            messages: 消息列表
            log_prefix: 日志前缀，用于区分不同调用位置的日志

        Returns:
            List[Dict[str, Any]]: 过滤后的消息列表
        """
        if not messages:
            return []

        original_count = len(messages)
        filtered_messages = [
            msg for msg in messages
            if not MessageFilter.should_filter_message(msg, log_prefix)
        ]
        filtered_count = original_count - len(filtered_messages)

        if filtered_count > 0:
            logger.debug(f"{log_prefix}过滤前消息数量: {original_count}, 过滤后: {len(filtered_messages)}, 过滤掉 {filtered_count} 条消息")

        return filtered_messages

    @staticmethod
    def process_new_messages_marker(messages: List[Dict[str, Any]], log_prefix: str = "") -> List[Dict[str, Any]]:
        """
        处理"以下为新消息"分隔符，只保留分隔符之后的消息

        Args:
            messages: 原始消息列表
            log_prefix: 日志前缀，用于区分不同调用位置的日志

        Returns:
            List[Dict[str, Any]]: 处理后的消息列表
        """
        if not messages:
            return []

        # 查找是否有"以下为新消息"标记
        new_message_index = -1
        for i, msg in enumerate(messages):
            content = msg.get('content', '')
            msg_type = msg.get('type', '') or msg.get('message_type', '')
            sender = msg.get('sender', '')

            # 检查是否是系统消息且内容为"以下为新消息"
            if (msg_type == 'sys' or sender == 'SYS') and '以下为新消息' in content:
                new_message_index = i
                logger.debug(f"{log_prefix}找到'以下为新消息'分隔符，位于消息列表的第 {i+1} 条")
                break

        # 如果找到分隔符，只返回分隔符之后的消息，并过滤掉分隔符本身
        if new_message_index >= 0:
            # 获取分隔符后的消息
            result = messages[new_message_index + 1:]
            logger.debug(f"{log_prefix}分隔符处理: 原始消息数量 {len(messages)}, 分隔符后 {len(result)}")

            # 确保分隔符本身也被过滤掉（不会被保留在结果中）
            if new_message_index < len(messages):
                logger.debug(f"{log_prefix}过滤掉分隔符消息: {messages[new_message_index].get('content', '')[:50]}")

            return result
        else:
            # 如果没有找到分隔符，使用所有消息
            return messages

# 创建全局实例
message_filter = MessageFilter()
