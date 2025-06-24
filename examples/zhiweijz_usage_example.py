#!/usr/bin/env python3
"""
只为记账平台使用示例

该示例展示如何使用WXAUTO-MGT的只为记账平台功能，包括：
1. 通过API创建只为记账平台
2. 配置消息投递规则
3. 模拟消息处理和记账
4. 查看记账记录和统计
"""

import asyncio
import aiohttp
import json
import time

# 配置信息
API_BASE_URL = "http://localhost:8000"
DEMO_CONFIG = {
    "name": "我的记账平台",
    "server_url": "https://demo.zhiweijz.com",  # 请替换为实际的服务器地址
    "username": "demo@example.com",  # 请替换为实际的用户名
    "password": "demo_password",  # 请替换为实际的密码
    "account_book_id": "",  # 可以为空，会自动获取第一个账本
    "account_book_name": "个人账本",
    "auto_login": True,
    "enabled": True
}

async def create_zhiweijz_platform():
    """创建只为记账平台"""
    print("=== 创建只为记账平台 ===")
    
    async with aiohttp.ClientSession() as session:
        try:
            # 发送创建平台请求
            async with session.post(
                f"{API_BASE_URL}/api/platforms/zhiweijz",
                json=DEMO_CONFIG,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("code") == 0:
                        platform_id = result["data"]["platform_id"]
                        print(f"✅ 只为记账平台创建成功，ID: {platform_id}")
                        return platform_id
                    else:
                        print(f"❌ 创建失败: {result.get('message', '未知错误')}")
                        return None
                else:
                    error_text = await response.text()
                    print(f"❌ HTTP错误 {response.status}: {error_text}")
                    return None
                    
        except Exception as e:
            print(f"❌ 创建平台时出错: {e}")
            return None

async def test_zhiweijz_connection():
    """测试只为记账平台连接"""
    print("\n=== 测试只为记账平台连接 ===")
    
    async with aiohttp.ClientSession() as session:
        try:
            # 发送测试连接请求
            test_config = {
                "server_url": DEMO_CONFIG["server_url"],
                "username": DEMO_CONFIG["username"],
                "password": DEMO_CONFIG["password"],
                "account_book_id": DEMO_CONFIG["account_book_id"]
            }
            
            async with session.post(
                f"{API_BASE_URL}/api/accounting/test",
                json=test_config,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("code") == 0:
                        data = result.get("data", {})
                        print(f"✅ 连接测试成功")
                        print(f"   登录状态: {'成功' if data.get('login_success') else '失败'}")
                        print(f"   账本数量: {len(data.get('account_books', []))}")
                        return True
                    else:
                        print(f"❌ 连接测试失败: {result.get('message', '未知错误')}")
                        return False
                else:
                    error_text = await response.text()
                    print(f"❌ HTTP错误 {response.status}: {error_text}")
                    return False
                    
        except Exception as e:
            print(f"❌ 测试连接时出错: {e}")
            return False

async def create_delivery_rule(platform_id):
    """创建消息投递规则"""
    print("\n=== 创建消息投递规则 ===")
    
    async with aiohttp.ClientSession() as session:
        try:
            # 发送创建规则请求
            rule_config = {
                "name": "记账规则",
                "instance_id": "*",  # 所有实例
                "chat_pattern": "记账群|账单群|消费群",  # 匹配包含这些关键词的群聊
                "platform_id": platform_id,
                "priority": 1,
                "enabled": 1
            }
            
            async with session.post(
                f"{API_BASE_URL}/api/rules",
                json=rule_config,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("code") == 0:
                        rule_id = result["data"]["rule_id"]
                        print(f"✅ 消息投递规则创建成功，ID: {rule_id}")
                        return rule_id
                    else:
                        print(f"❌ 创建规则失败: {result.get('message', '未知错误')}")
                        return None
                else:
                    error_text = await response.text()
                    print(f"❌ HTTP错误 {response.status}: {error_text}")
                    return None
                    
        except Exception as e:
            print(f"❌ 创建规则时出错: {e}")
            return None

async def get_accounting_records():
    """获取记账记录"""
    print("\n=== 获取记账记录 ===")
    
    async with aiohttp.ClientSession() as session:
        try:
            # 发送获取记录请求
            async with session.get(
                f"{API_BASE_URL}/api/accounting/records?limit=10"
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("code") == 0:
                        data = result.get("data", {})
                        records = data.get("records", [])
                        total = data.get("total", 0)
                        
                        print(f"✅ 获取记账记录成功，共 {total} 条记录")
                        
                        if records:
                            print("最近的记账记录:")
                            for i, record in enumerate(records[:5], 1):
                                status = "✅" if record.get("success") else "❌"
                                amount = f"{record.get('amount', 0)}元" if record.get('amount') else "未知金额"
                                print(f"  {i}. {record.get('description', 'N/A')} - {amount} - {status}")
                        else:
                            print("暂无记账记录")
                        
                        return records
                    else:
                        print(f"❌ 获取记录失败: {result.get('message', '未知错误')}")
                        return []
                else:
                    error_text = await response.text()
                    print(f"❌ HTTP错误 {response.status}: {error_text}")
                    return []
                    
        except Exception as e:
            print(f"❌ 获取记录时出错: {e}")
            return []

async def get_accounting_stats():
    """获取记账统计"""
    print("\n=== 获取记账统计 ===")
    
    async with aiohttp.ClientSession() as session:
        try:
            # 发送获取统计请求
            async with session.get(
                f"{API_BASE_URL}/api/accounting/stats"
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("code") == 0:
                        stats_list = result.get("data", [])
                        
                        print(f"✅ 获取记账统计成功")
                        
                        if stats_list:
                            for stats in stats_list:
                                print(f"平台: {stats.get('platform_id', 'N/A')}")
                                print(f"  总记录数: {stats.get('total_records', 0)}")
                                print(f"  成功记录数: {stats.get('successful_records', 0)}")
                                print(f"  失败记录数: {stats.get('failed_records', 0)}")
                                total = stats.get('total_records', 0)
                                success = stats.get('successful_records', 0)
                                success_rate = (success / total * 100) if total > 0 else 0
                                print(f"  成功率: {success_rate:.1f}%")
                                print(f"  总金额: {stats.get('total_amount', 0)}元")
                        else:
                            print("暂无统计数据")
                        
                        return stats_list
                    else:
                        print(f"❌ 获取统计失败: {result.get('message', '未知错误')}")
                        return []
                else:
                    error_text = await response.text()
                    print(f"❌ HTTP错误 {response.status}: {error_text}")
                    return []
                    
        except Exception as e:
            print(f"❌ 获取统计时出错: {e}")
            return []

async def cleanup_demo_data(platform_id, rule_id):
    """清理演示数据"""
    print("\n=== 清理演示数据 ===")
    
    async with aiohttp.ClientSession() as session:
        try:
            # 删除规则
            if rule_id:
                async with session.delete(f"{API_BASE_URL}/api/rules/{rule_id}") as response:
                    if response.status == 200:
                        print("✅ 消息投递规则已删除")
                    else:
                        print(f"❌ 删除规则失败: {response.status}")
            
            # 删除平台
            if platform_id:
                async with session.delete(f"{API_BASE_URL}/api/platforms/{platform_id}") as response:
                    if response.status == 200:
                        print("✅ 只为记账平台已删除")
                    else:
                        print(f"❌ 删除平台失败: {response.status}")
                        
        except Exception as e:
            print(f"❌ 清理数据时出错: {e}")

async def main():
    """主函数"""
    print("🚀 只为记账平台使用示例")
    print("=" * 50)
    
    print("⚠️  注意：此示例需要：")
    print("1. WXAUTO-MGT Web服务器正在运行 (http://localhost:8000)")
    print("2. 有效的只为记账服务器配置")
    print("3. 请在运行前修改DEMO_CONFIG中的服务器地址、用户名和密码")
    print()
    
    # 等待用户确认
    input("按回车键继续...")
    
    platform_id = None
    rule_id = None
    
    try:
        # 1. 测试连接
        connection_ok = await test_zhiweijz_connection()
        if not connection_ok:
            print("⚠️  连接测试失败，但继续演示其他功能...")
        
        # 2. 创建平台
        platform_id = await create_zhiweijz_platform()
        if not platform_id:
            print("❌ 无法创建平台，演示终止")
            return
        
        # 3. 创建投递规则
        rule_id = await create_delivery_rule(platform_id)
        
        # 4. 获取记账记录
        await get_accounting_records()
        
        # 5. 获取统计信息
        await get_accounting_stats()
        
        print("\n🎉 演示完成！")
        print("\n📝 接下来您可以：")
        print("1. 在微信群聊中发送包含金额的消息（如'午餐 35元'）")
        print("2. 通过Web界面 http://localhost:8000 查看记账记录")
        print("3. 配置更多的消息投递规则")
        
        # 询问是否清理数据
        cleanup = input("\n是否清理演示数据？(y/N): ").lower().strip()
        if cleanup == 'y':
            await cleanup_demo_data(platform_id, rule_id)
        else:
            print("演示数据已保留，您可以通过Web界面查看")
        
    except KeyboardInterrupt:
        print("\n\n用户中断演示")
        if platform_id or rule_id:
            print("正在清理演示数据...")
            await cleanup_demo_data(platform_id, rule_id)
    except Exception as e:
        print(f"\n❌ 演示过程中出错: {e}")
        if platform_id or rule_id:
            print("正在清理演示数据...")
            await cleanup_demo_data(platform_id, rule_id)

if __name__ == "__main__":
    asyncio.run(main())
