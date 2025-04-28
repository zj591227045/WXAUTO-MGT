"""
添加默认投递规则

该脚本用于添加默认投递规则，使所有的wxauto实例都使用当前设置的Dify实例。
"""

import asyncio
import logging
import time
import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
ROOT_DIR = Path(os.path.dirname(os.path.abspath(__file__))).parent.parent
sys.path.append(str(ROOT_DIR))

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# 导入必要的模块
from wxauto_mgt.data.db_manager import db_manager
from wxauto_mgt.core.service_platform_manager import platform_manager, rule_manager

async def add_default_rule():
    """添加默认投递规则"""
    try:
        # 初始化数据库
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        db_path = os.path.join(project_root, 'data', 'wxauto_mgt.db')
        await db_manager.initialize(db_path)
        
        # 初始化服务平台管理器
        await platform_manager.initialize()
        
        # 获取所有服务平台
        platforms = await platform_manager.get_all_platforms()
        
        if not platforms:
            logger.error("没有找到任何服务平台，请先添加服务平台")
            return
        
        # 查找Dify平台
        dify_platform = None
        for platform in platforms:
            if platform['type'] == 'dify':
                dify_platform = platform
                break
        
        if not dify_platform:
            logger.error("没有找到Dify平台，请先添加Dify平台")
            return
        
        logger.info(f"找到Dify平台: {dify_platform['name']} ({dify_platform['platform_id']})")
        
        # 初始化投递规则管理器
        await rule_manager.initialize()
        
        # 检查是否已存在默认规则
        rules = await rule_manager.get_all_rules()
        default_rule = None
        
        for rule in rules:
            if rule['instance_id'] == '*' and rule['chat_pattern'] == '*':
                default_rule = rule
                break
        
        if default_rule:
            logger.info(f"已存在默认规则: {default_rule['name']} ({default_rule['rule_id']})")
            
            # 如果默认规则不是指向Dify平台，则更新规则
            if default_rule['platform_id'] != dify_platform['platform_id']:
                logger.info(f"更新默认规则，指向Dify平台: {dify_platform['name']} ({dify_platform['platform_id']})")
                
                await rule_manager.update_rule(
                    default_rule['rule_id'],
                    "默认规则 - 所有实例使用Dify",
                    "*",  # 匹配所有实例
                    "*",  # 匹配所有聊天对象
                    dify_platform['platform_id'],
                    100  # 高优先级
                )
                
                logger.info("默认规则更新成功")
            else:
                logger.info("默认规则已经指向Dify平台，无需更新")
        else:
            # 创建默认规则
            logger.info(f"创建默认规则，指向Dify平台: {dify_platform['name']} ({dify_platform['platform_id']})")
            
            rule_id = await rule_manager.add_rule(
                name="默认规则 - 所有实例使用Dify",
                instance_id="*",  # 匹配所有实例
                chat_pattern="*",  # 匹配所有聊天对象
                platform_id=dify_platform['platform_id'],
                priority=100  # 高优先级
            )
            
            if rule_id:
                logger.info(f"默认规则创建成功: {rule_id}")
            else:
                logger.error("默认规则创建失败")
    except Exception as e:
        logger.error(f"添加默认规则失败: {e}")
    finally:
        # 关闭数据库连接
        await db_manager.close()

async def main():
    """主函数"""
    try:
        await add_default_rule()
    except Exception as e:
        logger.error(f"执行过程中出错: {e}")

if __name__ == "__main__":
    # 运行脚本
    asyncio.run(main())
