import sqlite3
import json

# 连接到数据库
conn = sqlite3.connect('/Users/jackson/Documents/VSCode/wxauto_Mgt/data/wxauto_mgt.db')
conn.row_factory = sqlite3.Row

# 获取消息表结构
cursor = conn.cursor()
cursor.execute("PRAGMA table_info(messages)")
columns = cursor.fetchall()
print("消息表结构:")
for col in columns:
    print(f"  {col['name']} ({col['type']})")

# 获取消息数据
cursor.execute("SELECT * FROM messages LIMIT 10")
messages = cursor.fetchall()
print("\n消息数据示例:")
for msg in messages:
    msg_dict = dict(msg)
    print(f"  ID: {msg_dict.get('message_id')}")
    print(f"  发送者: {msg_dict.get('sender')}")
    print(f"  类型: {msg_dict.get('message_type')}")
    print(f"  内容: {msg_dict.get('content')[:50]}...")
    print("  ---")

# 检查是否有Self发送者的消息
cursor.execute("SELECT COUNT(*) as count FROM messages WHERE LOWER(sender) = 'self'")
self_count = cursor.fetchone()['count']
print(f"\n发送者为'Self'的消息数量: {self_count}")

# 如果有Self发送者的消息，显示一些示例
if self_count > 0:
    cursor.execute("SELECT * FROM messages WHERE LOWER(sender) = 'self' LIMIT 5")
    self_messages = cursor.fetchall()
    print("\nSelf发送者的消息示例:")
    for msg in self_messages:
        msg_dict = dict(msg)
        print(f"  ID: {msg_dict.get('message_id')}")
        print(f"  发送者: {msg_dict.get('sender')} (原始大小写)")
        print(f"  类型: {msg_dict.get('message_type')}")
        print(f"  内容: {msg_dict.get('content')[:50]}...")
        print("  ---")

# 关闭连接
conn.close()
