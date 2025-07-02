"""
关键词匹配平台实现

该模块实现了基于关键词匹配的自动回复功能，包括：
- 多种匹配模式（完全匹配、包含匹配、模糊匹配）
- 随机回复选择
- 延时回复
- 配置验证
"""

import asyncio
import logging
import random
from typing import Dict, Any, List

from .base_platform import ServicePlatform

# 导入标准日志记录器
logger = logging.getLogger('wxauto_mgt')


class KeywordMatchPlatform(ServicePlatform):
    """关键词匹配平台实现"""

    def __init__(self, platform_id: str, name: str, config: Dict[str, Any]):
        """
        初始化关键词匹配平台

        Args:
            platform_id: 平台ID
            name: 平台名称
            config: 平台配置，包含关键词规则和回复时间范围
        """
        super().__init__(platform_id, name, config)
        # 从配置中加载规则
        self.rules = config.get('rules', [])
        # 默认回复时间范围（秒）
        self.min_reply_time = config.get('min_reply_time', 1)
        self.max_reply_time = config.get('max_reply_time', 3)
        # 消息发送模式已在父类中初始化

    async def initialize(self) -> bool:
        """
        初始化平台

        Returns:
            bool: 是否初始化成功
        """
        try:
            # 验证基本配置（不进行网络请求）
            if not isinstance(self.rules, list):
                logger.error("关键词匹配平台配置不完整：规则配置无效")
                self._initialized = False
                return False

            # 基本配置验证完成
            logger.info("关键词匹配平台配置验证完成")
            self._initialized = True
            return True
        except Exception as e:
            logger.error(f"初始化关键词匹配平台失败: {e}")
            self._initialized = False
            return False

    async def process_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理消息，匹配关键词并返回回复

        Args:
            message: 消息数据

        Returns:
            Dict[str, Any]: 处理结果，包含回复内容
        """
        if not self._initialized:
            await self.initialize()
            if not self._initialized:
                return {"error": "平台未初始化"}

        try:
            # 获取消息内容
            content = message.get('content', '')
            if not content:
                return {"error": "消息内容为空"}

            logger.info(f"关键词匹配平台处理消息: {content[:50]}...")

            # 匹配关键词
            matched_rule = None
            for rule in self.rules:
                # 获取规则信息
                keywords = rule.get('keywords', [])
                match_type = rule.get('match_type', 'exact')  # 默认为完全匹配

                # 检查是否匹配
                if self._match_keywords(content, keywords, match_type):
                    matched_rule = rule
                    logger.info(f"找到匹配的关键词规则: {keywords}")
                    break

            # 如果没有匹配的规则，返回空回复
            if not matched_rule:
                logger.info("没有找到匹配的关键词规则")
                return {"content": ""}

            # 获取回复内容
            replies = matched_rule.get('replies', [])
            if not replies:
                logger.warning("匹配的规则没有设置回复内容")
                return {"content": ""}

            # 是否随机选择回复
            is_random_reply = matched_rule.get('is_random_reply', False)

            # 选择回复内容
            reply_content = ""
            if is_random_reply and len(replies) > 1:
                # 随机选择一条回复
                reply_content = random.choice(replies)
                logger.info(f"随机选择回复内容: {reply_content[:50]}...")
            else:
                # 使用第一条回复
                reply_content = replies[0]
                logger.info(f"使用固定回复内容: {reply_content[:50]}...")

            # 计算随机回复时间
            min_time = matched_rule.get('min_reply_time', self.min_reply_time)
            max_time = matched_rule.get('max_reply_time', self.max_reply_time)

            # 确保最小时间不大于最大时间
            if min_time > max_time:
                min_time, max_time = max_time, min_time

            # 随机延时
            delay_time = random.uniform(min_time, max_time)
            logger.info(f"关键词匹配将延时 {delay_time:.2f} 秒后回复")

            # 延时
            await asyncio.sleep(delay_time)

            # 返回回复内容
            return {
                "content": reply_content,
                "raw_response": {
                    "matched_rule": matched_rule,
                    "delay_time": delay_time
                }
            }
        except Exception as e:
            logger.error(f"关键词匹配处理消息时出错: {e}")
            return {"error": str(e)}

    def _match_keywords(self, content: str, keywords: List[str], match_type: str) -> bool:
        """
        匹配关键词

        Args:
            content: 消息内容
            keywords: 关键词列表
            match_type: 匹配类型（exact-完全匹配，contains-包含匹配，fuzzy-模糊匹配）

        Returns:
            bool: 是否匹配
        """
        if not keywords:
            return False

        # 转换为小写进行不区分大小写的匹配
        content_lower = content.lower()

        for keyword in keywords:
            keyword_lower = keyword.lower()

            # 根据匹配类型进行匹配
            if match_type == 'exact':
                # 完全匹配
                if content_lower == keyword_lower:
                    return True
            elif match_type == 'contains':
                # 包含匹配
                if keyword_lower in content_lower:
                    return True
            elif match_type == 'fuzzy':
                # 模糊匹配（使用简单的相似度算法）
                try:
                    from difflib import SequenceMatcher
                    similarity = SequenceMatcher(None, content_lower, keyword_lower).ratio()
                    # 相似度阈值设为0.8
                    if similarity >= 0.8:
                        return True
                except Exception as e:
                    logger.error(f"模糊匹配算法出错: {e}")
                    # 降级为包含匹配
                    if keyword_lower in content_lower:
                        return True

        return False

    async def test_connection(self) -> Dict[str, Any]:
        """
        测试连接

        Returns:
            Dict[str, Any]: 测试结果
        """
        try:
            # 检查规则配置
            if not isinstance(self.rules, list):
                return {"error": "规则配置无效，应为列表类型"}

            # 检查规则格式
            for i, rule in enumerate(self.rules):
                if not isinstance(rule, dict):
                    return {"error": f"规则 #{i+1} 格式无效，应为字典类型"}

                # 检查关键词
                keywords = rule.get('keywords', [])
                if not isinstance(keywords, list) or not keywords:
                    return {"error": f"规则 #{i+1} 的关键词配置无效"}

                # 检查回复内容
                replies = rule.get('replies', [])
                if not isinstance(replies, list) or not replies:
                    return {"error": f"规则 #{i+1} 的回复内容配置无效"}

            # 检查回复时间范围
            min_time = self.min_reply_time
            max_time = self.max_reply_time

            if not isinstance(min_time, (int, float)) or min_time < 0:
                return {"error": "最小回复时间配置无效"}

            if not isinstance(max_time, (int, float)) or max_time < 0:
                return {"error": "最大回复时间配置无效"}

            if min_time > max_time:
                return {"error": "最小回复时间不能大于最大回复时间"}

            # 所有检查通过
            return {
                "success": True,
                "message": "配置有效",
                "data": {
                    "rules_count": len(self.rules),
                    "min_reply_time": min_time,
                    "max_reply_time": max_time
                }
            }
        except Exception as e:
            logger.error(f"测试关键词匹配平台配置时出错: {e}")
            return {"error": str(e)}

    def get_type(self) -> str:
        """
        获取平台类型

        Returns:
            str: 平台类型
        """
        return "keyword"
