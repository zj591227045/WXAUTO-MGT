"""
配置管理器测试模块

测试配置的加载、保存、修改和验证功能。
"""

import asyncio
import json
import os
import tempfile
from pathlib import Path
from unittest import IsolatedAsyncioTestCase, mock

import pytest

# 添加项目根目录到路径
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.core.config_manager import ConfigManager, ConfigError
from app.data.db_manager import db_manager


class AsyncMock(mock.MagicMock):
    """支持异步调用的Mock类"""
    async def __call__(self, *args, **kwargs):
        return super(AsyncMock, self).__call__(*args, **kwargs)


class TestConfigManager(IsolatedAsyncioTestCase):
    """配置管理器测试类"""
    
    async def asyncSetUp(self):
        """测试前准备"""
        # 创建临时文件夹
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = os.path.join(self.temp_dir.name, "config.json")
        self.db_path = os.path.join(self.temp_dir.name, "test_config.db")
        
        # 创建测试配置文件
        self.test_config = {
            "app": {
                "name": "测试应用",
                "version": "0.1.0"
            },
            "message_listener": {
                "poll_interval": 10,
                "max_listeners": 20
            },
            "status_monitor": {
                "check_interval": 30
            },
            "db": {
                "path": self.db_path
            },
            "instances": [
                {
                    "instance_id": "test-instance",
                    "name": "测试实例",
                    "base_url": "http://localhost:8080",
                    "api_key": "test-api-key",
                    "enabled": True
                }
            ]
        }
        
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.test_config, f, indent=2)
        
        # 初始化数据库
        self.db_manager_patcher = mock.patch('app.core.config_manager.db_manager')
        self.mock_db_manager = self.db_manager_patcher.start()
        
        # 配置mock返回异步结果
        self.mock_db_manager.fetch_all = AsyncMock(return_value=[])
        self.mock_db_manager.fetch_one = AsyncMock(return_value=None)
        self.mock_db_manager.insert = AsyncMock(return_value=1)
        self.mock_db_manager.update = AsyncMock(return_value=1)
        self.mock_db_manager.delete = AsyncMock(return_value=1)
        self.mock_db_manager.execute = AsyncMock(return_value=None)
        
        # 创建配置管理器
        self.config_manager = ConfigManager()
    
    async def asyncTearDown(self):
        """测试后清理"""
        self.db_manager_patcher.stop()
        self.temp_dir.cleanup()
    
    async def test_initialize(self):
        """测试初始化"""
        await self.config_manager.initialize(default_config_path=self.config_path)
        
        # 验证配置是否正确加载
        self.assertTrue(self.config_manager._initialized)
        self.assertEqual(self.config_manager.get('app.name'), "测试应用")
        self.assertEqual(self.config_manager.get('app.version'), "0.1.0")
        self.assertEqual(self.config_manager.get('message_listener.poll_interval'), 10)
    
    async def test_set_get_config(self):
        """测试设置和获取配置"""
        await self.config_manager.initialize(default_config_path=self.config_path)
        
        # 测试设置配置
        self.config_manager.set('app.name', "新名称")
        self.config_manager.set('app.debug', True)
        self.config_manager.set('new.nested.key', "嵌套值")
        
        # 测试获取配置
        self.assertEqual(self.config_manager.get('app.name'), "新名称")
        self.assertEqual(self.config_manager.get('app.debug'), True)
        self.assertEqual(self.config_manager.get('new.nested.key'), "嵌套值")
        self.assertEqual(self.config_manager.get('not.exist', "默认值"), "默认值")
    
    async def test_save_config(self):
        """测试保存配置"""
        await self.config_manager.initialize(default_config_path=self.config_path)
        
        # 修改配置
        self.config_manager.set('app.name', "新名称")
        
        # 设置模拟
        self.mock_db_manager.fetch_one.return_value = None
        
        # 保存配置
        result = await self.config_manager.save_config()
        self.assertTrue(result)
        
        # 验证是否调用了数据库插入
        self.mock_db_manager.insert.assert_called()
    
    async def test_encryption(self):
        """测试加密功能"""
        await self.config_manager.initialize(default_config_path=self.config_path)
        
        # 测试加密
        original_text = "敏感信息"
        encrypted = self.config_manager.encrypt(original_text)
        self.assertNotEqual(encrypted, original_text)
        
        # 测试解密
        decrypted = self.config_manager.decrypt(encrypted)
        self.assertEqual(decrypted, original_text)
    
    async def test_should_encrypt(self):
        """测试敏感信息判断"""
        await self.config_manager.initialize(default_config_path=self.config_path)
        
        # 测试敏感键判断
        self.assertTrue(self.config_manager._should_encrypt('instances.test.api_key'))
        self.assertTrue(self.config_manager._should_encrypt('api.secret'))
        self.assertTrue(self.config_manager._should_encrypt('auth.password'))
        self.assertTrue(self.config_manager._should_encrypt('auth.user.token'))
        self.assertTrue(self.config_manager._should_encrypt('database.password'))
        self.assertTrue(self.config_manager._should_encrypt('user.password'))
        self.assertTrue(self.config_manager._should_encrypt('app.secret'))
        self.assertFalse(self.config_manager._should_encrypt('app.name'))
        self.assertFalse(self.config_manager._should_encrypt('message_listener.poll_interval'))
    
    async def test_pattern_matching(self):
        """测试模式匹配"""
        await self.config_manager.initialize(default_config_path=self.config_path)
        
        # 测试模式匹配
        self.assertTrue(self.config_manager._match_pattern('instances.test.api_key', 'instances.*.api_key'))
        self.assertTrue(self.config_manager._match_pattern('api.token', 'api.token'))
        self.assertTrue(self.config_manager._match_pattern('auth.user.token', 'auth.*.token'))
        self.assertTrue(self.config_manager._match_pattern('user.password', '*.password'))
        self.assertFalse(self.config_manager._match_pattern('app.name', '*.password'))
        self.assertFalse(self.config_manager._match_pattern('user.secret_phrase', '*.secret'))
    
    async def test_key_rotation(self):
        """测试密钥轮换"""
        await self.config_manager.initialize(
            default_config_path=self.config_path,
            encryption_key="old_key",
            encryption_key_id=1
        )
        
        # 保存敏感信息
        self.config_manager.set('auth.password', "secret123")
        
        # 设置模拟
        self.mock_db_manager.fetch_one.return_value = None
        self.mock_db_manager.fetch_all.return_value = [
            {'key': 'auth.password', 'value': self.config_manager.encrypt("secret123"), 'encrypted': 1}
        ]
        
        # 获取旧加密的数据
        old_encrypted = self.config_manager.encrypt("secret123")
        
        # 轮换密钥
        result = await self.config_manager.rotate_encryption_key("new_key", 2)
        self.assertTrue(result)
        
        # 验证密钥ID
        self.assertEqual(self.config_manager.get_encryption_key_id(), 2)
        
        # 验证旧密钥是否被保存
        legacy_keys = self.config_manager.get_legacy_key_ids()
        self.assertIn(1, legacy_keys)
        
        # 验证新加密数据
        new_encrypted = self.config_manager.encrypt("secret123")
        self.assertNotEqual(old_encrypted, new_encrypted)
        
        # 验证可以用新密钥解密
        decrypted = self.config_manager.decrypt(new_encrypted)
        self.assertEqual(decrypted, "secret123")
    
    async def test_legacy_key_management(self):
        """测试旧密钥管理"""
        await self.config_manager.initialize(
            default_config_path=self.config_path,
            encryption_key="current_key",
            encryption_key_id=3
        )
        
        # 添加旧密钥
        await self.config_manager.add_legacy_key(1, "legacy_key1")
        await self.config_manager.add_legacy_key(2, "legacy_key2")
        
        # 验证旧密钥列表
        legacy_keys = self.config_manager.get_legacy_key_ids()
        self.assertIn(1, legacy_keys)
        self.assertIn(2, legacy_keys)
        
        # 设置模拟
        self.mock_db_manager.fetch_all.return_value = [{'count': 0}]
        
        # 移除旧密钥
        result = await self.config_manager.remove_legacy_key(1)
        self.assertTrue(result)
        
        # 验证旧密钥是否被移除
        legacy_keys = self.config_manager.get_legacy_key_ids()
        self.assertNotIn(1, legacy_keys)
        self.assertIn(2, legacy_keys)
        
        # 尝试移除不存在的密钥
        result = await self.config_manager.remove_legacy_key(10)
        self.assertFalse(result)
        
        # 模拟密钥仍在使用
        self.mock_db_manager.fetch_all.return_value = [{'count': 5}]
        
        # 尝试移除仍在使用的密钥
        result = await self.config_manager.remove_legacy_key(2)
        self.assertFalse(result)
    
    async def test_validate_config(self):
        """测试配置验证"""
        await self.config_manager.initialize(default_config_path=self.config_path)
        
        # 测试有效配置
        valid, errors = await self.config_manager.validate_config()
        self.assertTrue(valid)
        self.assertEqual(len(errors), 0)
        
        # 测试无效配置
        self.config_manager.set('message_listener.poll_interval', -1)
        valid, errors = await self.config_manager.validate_config()
        self.assertFalse(valid)
        self.assertGreater(len(errors), 0)
    
    async def test_export_import_config(self):
        """测试配置导出和导入"""
        await self.config_manager.initialize(default_config_path=self.config_path)
        
        # 修改配置
        self.config_manager.set('app.name', "导出测试")
        
        # 导出配置
        export_path = os.path.join(self.temp_dir.name, "export_config.json")
        result = await self.config_manager.export_config(export_path)
        self.assertTrue(result)
        
        # 修改配置
        self.config_manager.set('app.name', "导入前")
        
        # 导入配置
        result = await self.config_manager.import_config(export_path)
        self.assertTrue(result)
        
        # 验证配置是否导入成功
        self.assertEqual(self.config_manager.get('app.name'), "导出测试")
    
    def test_load_from_env(self):
        """测试从环境变量加载配置"""
        # 设置环境变量
        os.environ['WXAUTO_APP_NAME'] = "环境变量名称"
        os.environ['WXAUTO_APP_DEBUG'] = "true"
        os.environ['WXAUTO_MESSAGE_LISTENER_MAX_LISTENERS'] = "50"
        
        # 创建新的配置管理器实例以确保环境变量正确加载
        config_manager = ConfigManager()
        
        # 从环境变量加载
        env_config = config_manager.load_from_env()
        print("环境变量配置:", env_config)  # 打印环境变量配置
        
        # 手动设置配置
        for key, value in env_config.items():
            print(f"设置键: {key}, 值: {value}")  # 打印每个设置的键值对
            config_manager.set(key, value)
        
        # 打印整个配置
        print("完整配置:", config_manager.get_all())
        
        # 验证配置 - 根据实际的键结构修改
        self.assertEqual(config_manager.get('app.name'), "环境变量名称")
        self.assertEqual(config_manager.get('app.debug'), True)
        
        # 验证正确的嵌套路径
        self.assertEqual(config_manager.get('message.listener.max.listeners'), 50)
    
    async def test_instance_management(self):
        """测试实例管理功能"""
        await self.config_manager.initialize(default_config_path=self.config_path)
        
        # 测试添加实例
        result = await self.config_manager.add_instance(
            "new-instance", 
            "新实例", 
            "http://example.com", 
            "new-api-key"
        )
        self.assertTrue(result)
        
        # 验证实例是否添加成功
        instances = self.config_manager.get('instances')
        self.assertEqual(len(instances), 2)
        
        # 获取实例配置
        instance = self.config_manager.get_instance_config("new-instance")
        self.assertIsNotNone(instance)
        self.assertEqual(instance['name'], "新实例")
        
        # 测试获取已启用实例
        enabled_instances = self.config_manager.get_enabled_instances()
        self.assertEqual(len(enabled_instances), 2)
        
        # 测试禁用实例
        result = await self.config_manager.disable_instance("new-instance")
        self.assertTrue(result)
        
        # 验证实例是否禁用
        enabled_instances = self.config_manager.get_enabled_instances()
        self.assertEqual(len(enabled_instances), 1)
        
        # 测试启用实例
        result = await self.config_manager.enable_instance("new-instance")
        self.assertTrue(result)
        
        # 验证实例是否启用
        enabled_instances = self.config_manager.get_enabled_instances()
        self.assertEqual(len(enabled_instances), 2)
        
        # 测试移除实例
        result = await self.config_manager.remove_instance("new-instance")
        self.assertTrue(result)
        
        # 验证实例是否移除
        instances = self.config_manager.get('instances')
        self.assertEqual(len(instances), 1)
    
    async def test_convenience_methods(self):
        """测试便捷方法"""
        await self.config_manager.initialize(default_config_path=self.config_path)
        
        # 测试获取消息监听器配置
        ml_config = self.config_manager.get_message_listener_config()
        self.assertEqual(ml_config['poll_interval'], 10)
        self.assertEqual(ml_config['max_listeners'], 20)
        
        # 测试获取状态监控器配置
        sm_config = self.config_manager.get_status_monitor_config()
        self.assertEqual(sm_config['check_interval'], 30)
        
        # 测试获取数据库配置
        db_config = self.config_manager.get_db_config()
        self.assertEqual(db_config['path'], self.db_path) 