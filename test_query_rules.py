#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试脚本：查询数据库中的规则
"""

import sqlite3
import os
import json

# 直接使用sqlite3查询数据库
DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'wxauto_mgt.db')
print(f"数据库路径: {DB_PATH}")
print(f"数据库文件是否存在: {os.path.exists(DB_PATH)}")

def query_rules():
    """查询数据库中的规则"""
    try:
        # 连接数据库
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 查询所有规则
        cursor.execute("SELECT * FROM delivery_rules")
        rules = cursor.fetchall()

        print(f"共找到 {len(rules)} 条规则:")
        for rule in rules:
            print(f"规则ID: {rule['rule_id']}")
            print(f"  名称: {rule['name']}")
            print(f"  实例ID: {rule['instance_id']}")
            print(f"  聊天匹配: {rule['chat_pattern']}")
            print(f"  平台ID: {rule['platform_id']}")
            print(f"  优先级: {rule['priority']}")
            print(f"  启用状态: {rule['enabled']}")
            print(f"  只响应@消息: {rule['only_at_messages']}")
            print(f"  @名称: {rule['at_name']}")
            print(f"  回复时@发送者: {rule['reply_at_sender'] if 'reply_at_sender' in rule.keys() else '字段不存在'}")
            print(f"  创建时间: {rule['create_time']}")
            print(f"  更新时间: {rule['update_time']}")
            print("---")

        # 查询表结构
        cursor.execute("PRAGMA table_info(delivery_rules)")
        columns = cursor.fetchall()

        print("\n表结构:")
        for col in columns:
            print(f"  {col['name']} ({col['type']})")

    except Exception as e:
        print(f"查询规则失败: {e}")
    finally:
        # 关闭数据库连接
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    query_rules()
