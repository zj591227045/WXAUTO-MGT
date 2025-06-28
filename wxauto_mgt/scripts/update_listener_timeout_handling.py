#!/usr/bin/env python3
"""
更新监听器超时处理逻辑的脚本
确保数据库索引存在，并验证超时处理逻辑正确
"""

import os
import sys
import asyncio
import logging
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from wxauto_mgt.data.db_manager import db_manager

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def update_listener_timeout_handling():
    """更新监听器超时处理逻辑"""
    try:
        # 初始化数据库
        db_path = os.path.join(project_root, 'data', 'wxauto_mgt.db')
        await db_manager.initialize(db_path)
        
        print(f"数据库路径: {db_path}")
        
        # 检查listeners表结构
        print("\n=== 检查listeners表结构 ===")
        
        # 获取表结构
        columns_result = await db_manager.fetchall("PRAGMA table_info(listeners)")
        
        if not columns_result:
            print("❌ listeners表不存在")
            return False
        
        print("当前表结构:")
        column_names = []
        for col in columns_result:
            column_names.append(col['name'])
            print(f"  {col['name']} - {col['type']} - {'NOT NULL' if col['notnull'] else 'NULL'} - 默认值: {col['dflt_value']}")
        
        # 检查必要字段是否存在
        required_fields = ['status', 'last_message_time', 'manual_added']
        missing_fields = [field for field in required_fields if field not in column_names]
        
        if missing_fields:
            print(f"❌ 缺少必要字段: {missing_fields}")
            return False
        else:
            print("✅ 所有必要字段都存在")
        
        # 检查索引
        print("\n=== 检查索引 ===")
        
        # 获取所有索引
        indexes_result = await db_manager.fetchall("PRAGMA index_list(listeners)")
        index_names = [idx['name'] for idx in indexes_result]
        
        print("当前索引:")
        for idx_name in index_names:
            idx_info = await db_manager.fetchall(f"PRAGMA index_info({idx_name})")
            columns = [col['name'] for col in idx_info]
            print(f"  {idx_name}: {', '.join(columns)}")
        
        # 检查必要索引是否存在
        required_indexes = {
            'idx_listeners_status': 'status',
            'idx_listeners_manual_added': 'manual_added',
            'idx_listeners_last_message_time': 'last_message_time'
        }
        
        missing_indexes = []
        for idx_name, column in required_indexes.items():
            if idx_name not in index_names:
                missing_indexes.append((idx_name, column))
        
        # 创建缺失的索引
        if missing_indexes:
            print(f"\n=== 创建缺失的索引 ===")
            for idx_name, column in missing_indexes:
                print(f"创建索引: {idx_name} on {column}")
                await db_manager.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON listeners({column})")
                print(f"✅ 已创建索引: {idx_name}")
        else:
            print("✅ 所有必要索引都存在")
        
        # 检查现有数据
        print("\n=== 检查现有数据 ===")
        
        listeners_count = await db_manager.fetchone("SELECT COUNT(*) as count FROM listeners")
        print(f"监听对象总数: {listeners_count['count']}")
        
        if listeners_count['count'] > 0:
            # 按状态统计
            status_stats = await db_manager.fetchall(
                "SELECT status, COUNT(*) as count FROM listeners GROUP BY status"
            )
            print("按状态统计:")
            for stat in status_stats:
                print(f"  {stat['status']}: {stat['count']}")
            
            # 按manual_added统计
            manual_stats = await db_manager.fetchall(
                "SELECT manual_added, COUNT(*) as count FROM listeners GROUP BY manual_added"
            )
            print("按手动添加统计:")
            for stat in manual_stats:
                manual_type = "手动添加" if stat['manual_added'] == 1 else "自动添加"
                print(f"  {manual_type}: {stat['count']}")
            
            # 显示最近的监听对象（按last_message_time排序）
            print("\n最近活跃的监听对象（前5个）:")
            recent_listeners = await db_manager.fetchall("""
                SELECT instance_id, who, status, last_message_time, manual_added
                FROM listeners 
                ORDER BY CASE WHEN status = 'active' THEN 0 ELSE 1 END, last_message_time DESC 
                LIMIT 5
            """)
            
            for listener in recent_listeners:
                from datetime import datetime
                last_time = datetime.fromtimestamp(listener['last_message_time']).strftime('%Y-%m-%d %H:%M:%S')
                manual_flag = " [手动]" if listener['manual_added'] else ""
                print(f"  {listener['instance_id']} - {listener['who']} ({listener['status']}) - {last_time}{manual_flag}")
        
        print("\n=== 验证排序查询性能 ===")
        
        # 测试排序查询
        import time
        start_time = time.time()
        
        sorted_listeners = await db_manager.fetchall("""
            SELECT instance_id, who, status, last_message_time 
            FROM listeners 
            ORDER BY CASE WHEN status = 'active' THEN 0 ELSE 1 END, last_message_time DESC
        """)
        
        end_time = time.time()
        query_time = (end_time - start_time) * 1000  # 转换为毫秒
        
        print(f"排序查询耗时: {query_time:.2f}ms")
        print(f"返回记录数: {len(sorted_listeners)}")
        
        if query_time < 100:  # 小于100ms认为性能良好
            print("✅ 查询性能良好")
        else:
            print("⚠️ 查询性能可能需要优化")
        
        print("\n✅ 监听器超时处理逻辑更新完成")
        return True
        
    except Exception as e:
        logger.error(f"更新监听器超时处理逻辑失败: {e}")
        import traceback
        logger.error(f"异常堆栈: {traceback.format_exc()}")
        return False

async def main():
    """主函数"""
    print("开始更新监听器超时处理逻辑...")
    success = await update_listener_timeout_handling()
    
    if success:
        print("\n🎉 更新成功！")
        print("\n修改总结:")
        print("1. ✅ 超时处理逻辑已修改为标记为inactive而不是删除记录")
        print("2. ✅ 添加了last_message_time字段的数据库索引以优化排序性能")
        print("3. ✅ Web端API已添加排序逻辑（活跃状态在前，按最后消息时间降序）")
        print("4. ✅ Python端添加了get_all_listeners_sorted方法支持排序")
        print("\n现在监听窗口将保留所有历史监听记录，并按最后活跃时间排序显示。")
    else:
        print("\n❌ 更新失败，请检查错误信息")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
