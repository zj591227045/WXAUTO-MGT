"""
关键词匹配插件实现

该插件实现了基于关键词的自动回复功能，支持：
- 多种匹配模式（精确匹配、包含匹配、正则匹配）
- 随机回复选择
- 回复延迟模拟
- 灵活的规则配置
"""

import logging
import re
import random
import asyncio
from typing import Dict, Any, List

from wxauto_mgt.core.plugin_system import (
    BaseServicePlatform, PluginInfo, MessageContext, ProcessResult, MessageType
)

logger = logging.getLogger(__name__)


class KeywordPlatformPlugin(BaseServicePlatform):
    """关键词匹配插件"""
    
    def __init__(self, plugin_info: PluginInfo):
        """初始化关键词匹配插件"""
        super().__init__(plugin_info)
        
        # 设置支持的消息类型
        self._supported_message_types = [MessageType.TEXT]
        self._platform_type = "keyword"
        
        # 关键词特定配置
        self.rules = []
        self.case_sensitive = False
        self.enable_delay = True
    
    def get_config_schema(self) -> Dict[str, Any]:
        """获取配置模式定义"""
        return {
            "type": "object",
            "properties": {
                "rules": {
                    "type": "array",
                    "title": "关键词规则",
                    "description": "关键词匹配规则列表",
                    "items": {
                        "type": "object",
                        "properties": {
                            "keywords": {
                                "type": "array",
                                "title": "关键词列表",
                                "items": {"type": "string"}
                            },
                            "match_type": {
                                "type": "string",
                                "title": "匹配类型",
                                "enum": ["exact", "contains", "regex"],
                                "default": "exact"
                            },
                            "replies": {
                                "type": "array",
                                "title": "回复内容",
                                "items": {"type": "string"}
                            },
                            "is_random_reply": {
                                "type": "boolean",
                                "title": "随机回复",
                                "default": False
                            },
                            "min_reply_time": {
                                "type": "integer",
                                "title": "最小回复时间",
                                "default": 1,
                                "minimum": 0
                            },
                            "max_reply_time": {
                                "type": "integer",
                                "title": "最大回复时间",
                                "default": 3,
                                "minimum": 0
                            }
                        },
                        "required": ["keywords", "replies"]
                    },
                    "default": []
                },
                "case_sensitive": {
                    "type": "boolean",
                    "title": "区分大小写",
                    "default": False
                },
                "enable_delay": {
                    "type": "boolean",
                    "title": "启用回复延迟",
                    "default": True
                }
            }
        }
    
    def validate_config(self, config: Dict[str, Any]) -> tuple[bool, str]:
        """验证配置"""
        rules = config.get('rules', [])
        
        if not isinstance(rules, list):
            return False, "规则必须是数组格式"
        
        for i, rule in enumerate(rules):
            if not isinstance(rule, dict):
                return False, f"规则 {i+1} 必须是对象格式"
            
            # 检查必需字段
            if 'keywords' not in rule:
                return False, f"规则 {i+1} 缺少关键词字段"
            
            if 'replies' not in rule:
                return False, f"规则 {i+1} 缺少回复字段"
            
            # 检查关键词
            keywords = rule['keywords']
            if not isinstance(keywords, list) or not keywords:
                return False, f"规则 {i+1} 的关键词必须是非空数组"
            
            # 检查回复内容
            replies = rule['replies']
            if not isinstance(replies, list) or not replies:
                return False, f"规则 {i+1} 的回复内容必须是非空数组"
            
            # 检查匹配类型
            match_type = rule.get('match_type', 'exact')
            if match_type not in ['exact', 'contains', 'regex']:
                return False, f"规则 {i+1} 的匹配类型无效"
            
            # 验证正则表达式
            if match_type == 'regex':
                for keyword in keywords:
                    try:
                        re.compile(keyword)
                    except re.error as e:
                        return False, f"规则 {i+1} 的正则表达式 '{keyword}' 无效: {e}"
        
        return True, None
    
    async def _do_initialize(self):
        """执行自定义初始化逻辑"""
        # 从配置中提取参数
        self.rules = self._config.get('rules', [])
        self.case_sensitive = self._config.get('case_sensitive', False)
        self.enable_delay = self._config.get('enable_delay', True)
        
        logger.info(f"关键词插件初始化完成: {len(self.rules)} 个规则")
    
    async def _do_process_message(self, context: MessageContext) -> ProcessResult:
        """处理消息"""
        try:
            content = context.content
            if not content:
                return ProcessResult(
                    success=True,
                    response="",
                    should_reply=False
                )
            
            logger.info(f"关键词匹配处理消息: {content[:50]}...")
            
            # 匹配关键词规则
            matched_rule = None
            for rule in self.rules:
                if self._match_rule(content, rule):
                    matched_rule = rule
                    logger.info(f"找到匹配的关键词规则: {rule.get('keywords', [])}")
                    break
            
            # 如果没有匹配的规则，返回空回复
            if not matched_rule:
                logger.info("没有找到匹配的关键词规则")
                return ProcessResult(
                    success=True,
                    response="",
                    should_reply=False
                )
            
            # 获取回复内容
            replies = matched_rule.get('replies', [])
            if not replies:
                logger.warning("匹配的规则没有设置回复内容")
                return ProcessResult(
                    success=True,
                    response="",
                    should_reply=False
                )
            
            # 选择回复内容
            if matched_rule.get('is_random_reply', False):
                reply_content = random.choice(replies)
            else:
                reply_content = replies[0]
            
            # 计算延迟时间
            delay_time = 0
            if self.enable_delay:
                min_time = matched_rule.get('min_reply_time', 1)
                max_time = matched_rule.get('max_reply_time', 3)
                if max_time > min_time:
                    delay_time = random.uniform(min_time, max_time)
                else:
                    delay_time = min_time
            
            # 如果需要延迟，等待一段时间
            if delay_time > 0:
                logger.info(f"延迟 {delay_time:.1f} 秒后回复")
                await asyncio.sleep(delay_time)
            
            logger.info(f"关键词匹配处理成功: {context.message_id}")
            return ProcessResult(
                success=True,
                response=reply_content,
                should_reply=True,
                metadata={
                    "matched_keywords": matched_rule.get('keywords', []),
                    "match_type": matched_rule.get('match_type', 'exact'),
                    "delay_time": delay_time
                }
            )
        
        except Exception as e:
            logger.error(f"关键词匹配处理失败: {context.message_id}, 错误: {e}")
            return ProcessResult(
                success=False,
                error=str(e),
                should_reply=False
            )
    
    def _match_rule(self, content: str, rule: Dict[str, Any]) -> bool:
        """
        检查内容是否匹配规则
        
        Args:
            content: 消息内容
            rule: 匹配规则
            
        Returns:
            bool: 是否匹配
        """
        keywords = rule.get('keywords', [])
        match_type = rule.get('match_type', 'exact')
        
        # 处理大小写
        if not self.case_sensitive:
            content = content.lower()
            keywords = [kw.lower() for kw in keywords]
        
        # 根据匹配类型进行匹配
        for keyword in keywords:
            if match_type == 'exact':
                if content == keyword:
                    return True
            elif match_type == 'contains':
                if keyword in content:
                    return True
            elif match_type == 'regex':
                try:
                    flags = 0 if self.case_sensitive else re.IGNORECASE
                    if re.search(keyword, content, flags):
                        return True
                except re.error:
                    logger.warning(f"正则表达式错误: {keyword}")
                    continue
        
        return False
    
    async def _do_test_connection(self) -> Dict[str, Any]:
        """测试连接"""
        try:
            # 关键词匹配不需要网络连接，只需要检查配置
            rule_count = len(self.rules)
            
            if rule_count == 0:
                return {
                    "success": False,
                    "error": "没有配置任何关键词规则"
                }
            
            # 统计关键词数量
            total_keywords = sum(len(rule.get('keywords', [])) for rule in self.rules)
            total_replies = sum(len(rule.get('replies', [])) for rule in self.rules)
            
            return {
                "success": True,
                "message": f"配置检查成功",
                "rule_count": rule_count,
                "total_keywords": total_keywords,
                "total_replies": total_replies
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _do_health_check(self) -> Dict[str, Any]:
        """执行健康检查"""
        health_data = {}
        
        # 检查配置
        health_data["rule_count"] = len(self.rules)
        health_data["config_valid"] = len(self.rules) > 0
        
        # 检查规则有效性
        valid_rules = 0
        for rule in self.rules:
            if (rule.get('keywords') and rule.get('replies') and 
                len(rule['keywords']) > 0 and len(rule['replies']) > 0):
                valid_rules += 1
        
        health_data["valid_rules"] = valid_rules
        health_data["invalid_rules"] = len(self.rules) - valid_rules
        
        return health_data
