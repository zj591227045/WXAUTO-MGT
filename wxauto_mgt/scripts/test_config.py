#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
配置管理器手动测试脚本

用于测试配置管理器的基本功能，包括配置加载、保存、加密和验证。
"""

import asyncio
import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
ROOT_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(str(ROOT_DIR))

from app.core.config_manager import config_manager
from app1.data.db_manager import db_manager
from app.utils.logging import log_manager

# 测试配置
TEST_CONFIG = {
    "app": {
        "name": "WxAuto管理程序测试版",
        "version": "0.1.0-test",
        "log_level": "DEBUG"
    },
    "message_listener": {
        "poll_interval": 3,
        "max_listeners": 10,
        "listener_timeout_minutes": 15
    },
    "status_monitor": {
        "check_interval": 30
    },
    "db": {
        "path": "data/test_wxauto_mgt.db"
    },
    "instances": [
        {
            "instance_id": "test-instance-1",
            "name": "测试实例1",
            "base_url": "http://localhost:8080",
            "api_key": "test-api-key-1",
            "enabled": True
        },
        {
            "instance_id": "test-instance-2",
            "name": "测试实例2",
            "base_url": "http://localhost:8081",
            "api_key": "test-api-key-2",
            "enabled": False
        }
    ]
}


async def test_init():
    """测试初始化"""
    print("测试初始化配置管理器...")
    
    # 创建临时配置文件
    config_dir = ROOT_DIR / "config"
    os.makedirs(config_dir, exist_ok=True)
    
    # 初始化数据库
    print("初始化数据库...")
    await db_manager.initialize()
    
    # 初始化配置管理器
    print("初始化配置管理器...")
    await config_manager.initialize()
    
    # 加载默认配置文件
    print(f"加载配置文件: {config_manager._default_config_path}")
    
    # 验证配置
    valid, errors = await config_manager.validate_config()
    print(f"配置验证结果: {'有效' if valid else '无效'}")
    if not valid:
        print(f"验证错误: {errors}")
    
    print("当前配置:")
    print_config(config_manager.get_all())
    
    return True


async def test_add_instances():
    """测试添加实例"""
    print("\n测试添加实例...")
    
    # 添加测试实例
    for instance in TEST_CONFIG["instances"]:
        print(f"添加实例: {instance['name']} ({instance['instance_id']})")
        await config_manager.add_instance(
            instance["instance_id"],
            instance["name"],
            instance["base_url"],
            instance["api_key"],
            instance["enabled"]
        )
    
    # 获取所有实例
    print("所有实例:")
    instances = config_manager.get('instances', [])
    for instance in instances:
        print(f"  - {instance['name']} ({instance['instance_id']}): {'启用' if instance['enabled'] else '禁用'}")
    
    # 获取已启用的实例
    print("已启用的实例:")
    enabled_instances = config_manager.get_enabled_instances()
    for instance in enabled_instances:
        print(f"  - {instance['name']} ({instance['instance_id']})")
    
    return True


async def test_encryption():
    """测试加密功能"""
    print("\n测试加密功能...")
    
    # 测试敏感信息加密
    sensitive_data = "sensitive-api-key-123456"
    print(f"原始敏感数据: {sensitive_data}")
    
    # 加密
    encrypted = config_manager.encrypt(sensitive_data)
    print(f"加密后数据: {encrypted}")
    
    # 解密
    decrypted = config_manager.decrypt(encrypted)
    print(f"解密后数据: {decrypted}")
    print(f"解密是否成功: {decrypted == sensitive_data}")
    
    return True


async def test_key_rotation():
    """测试密钥轮换"""
    print("\n测试密钥轮换...")
    
    # 获取当前密钥ID
    old_key_id = config_manager.get_encryption_key_id()
    print(f"当前密钥ID: {old_key_id}")
    
    # 添加敏感配置
    config_manager.set('auth.password', "test-password-123", save=True)
    
    # 加密数据
    original_data = "test-rotation-data"
    old_encrypted = config_manager.encrypt(original_data)
    print(f"旧密钥加密数据: {old_encrypted}")
    
    # 轮换密钥
    new_key_id = old_key_id + 1
    print(f"轮换到新密钥ID: {new_key_id}")
    result = await config_manager.rotate_encryption_key("new-encryption-key", new_key_id)
    print(f"密钥轮换{'成功' if result else '失败'}")
    
    # 验证新密钥
    print(f"当前密钥ID: {config_manager.get_encryption_key_id()}")
    
    # 获取旧密钥列表
    legacy_keys = config_manager.get_legacy_key_ids()
    print(f"旧密钥ID列表: {legacy_keys}")
    
    # 使用新密钥加密
    new_encrypted = config_manager.encrypt(original_data)
    print(f"新密钥加密数据: {new_encrypted}")
    
    # 解密旧数据
    decrypted_old = config_manager.decrypt(old_encrypted)
    print(f"解密旧数据: {decrypted_old}")
    print(f"解密旧数据成功: {decrypted_old == original_data}")
    
    return True


async def test_export_import():
    """测试导出导入配置"""
    print("\n测试配置导出导入...")
    
    # 先设置一些配置
    config_manager.set('app.name', "导出测试应用")
    config_manager.set('app.debug', True)
    config_manager.set('app.test_value', 123)
    
    # 导出配置
    export_path = ROOT_DIR / "config" / "exported_config.json"
    print(f"导出配置到: {export_path}")
    result = await config_manager.export_config(str(export_path))
    print(f"导出{'成功' if result else '失败'}")
    
    # 修改配置
    config_manager.set('app.name', "修改后的名称")
    
    # 导入配置
    print(f"从 {export_path} 导入配置")
    result = await config_manager.import_config(str(export_path))
    print(f"导入{'成功' if result else '失败'}")
    
    # 验证导入后的配置
    print(f"导入后app.name = {config_manager.get('app.name')}")
    
    # 清理导出文件
    os.remove(export_path)
    
    return True


def print_config(config, prefix=""):
    """递归打印配置"""
    for key, value in config.items():
        if isinstance(value, dict):
            print(f"{prefix}{key}:")
            print_config(value, prefix + "  ")
        else:
            print(f"{prefix}{key}: {value}")


async def main():
    """主函数"""
    # 初始化日志
    log_manager.initialize(log_level="DEBUG")
    logger = log_manager.get_logger()
    
    logger.info("开始配置管理器测试")
    
    try:
        # 运行测试
        tests = [
            ("初始化", test_init),
            ("添加实例", test_add_instances),
            ("加密功能", test_encryption),
            ("密钥轮换", test_key_rotation),
            ("导出导入", test_export_import)
        ]
        
        for name, test_func in tests:
            print(f"\n{'=' * 50}")
            print(f"开始测试: {name}")
            print(f"{'=' * 50}")
            
            try:
                if await test_func():
                    print(f"\n✅ {name}测试通过")
                else:
                    print(f"\n❌ {name}测试失败")
            except Exception as e:
                print(f"\n❌ {name}测试出错: {e}")
                logger.exception(f"{name}测试出错")
        
        print(f"\n{'=' * 50}")
        print("测试完成")
        print(f"{'=' * 50}")
        
    except Exception as e:
        logger.exception(f"测试过程出错: {e}")
        return 1
    finally:
        logger.info("测试结束")
    
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main())) 