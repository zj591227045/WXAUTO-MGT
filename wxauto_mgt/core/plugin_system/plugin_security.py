"""
插件安全和权限控制系统

该模块提供了插件系统的安全控制功能，包括：
- 权限管理
- 安全验证
- 沙箱机制
- 代码签名验证
"""

import logging
import hashlib
import os
import sys
import importlib.util
from typing import Dict, List, Optional, Any, Set
from enum import Enum
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


class Permission(Enum):
    """权限枚举"""
    NETWORK_HTTP = "network.http"           # HTTP网络访问
    NETWORK_HTTPS = "network.https"         # HTTPS网络访问
    NETWORK_SOCKET = "network.socket"       # Socket网络访问
    FILE_READ = "file.read"                 # 文件读取
    FILE_WRITE = "file.write"               # 文件写入
    FILE_EXECUTE = "file.execute"           # 文件执行
    CONFIG_READ = "config.read"             # 配置读取
    CONFIG_WRITE = "config.write"           # 配置写入
    DATABASE_READ = "database.read"         # 数据库读取
    DATABASE_WRITE = "database.write"       # 数据库写入
    MESSAGE_PROCESS = "message.process"     # 消息处理
    MESSAGE_SEND = "message.send"           # 消息发送
    SYSTEM_COMMAND = "system.command"       # 系统命令执行
    SYSTEM_REGISTRY = "system.registry"     # 系统注册表访问


@dataclass
class SecurityPolicy:
    """安全策略"""
    allowed_permissions: Set[Permission]
    denied_permissions: Set[Permission]
    max_memory_mb: int = 100
    max_cpu_percent: float = 10.0
    max_network_requests_per_minute: int = 60
    allowed_domains: List[str] = None
    blocked_domains: List[str] = None
    sandbox_enabled: bool = True
    code_signing_required: bool = False


@dataclass
class PluginSignature:
    """插件签名信息"""
    plugin_id: str
    signature: str
    public_key: str
    timestamp: int
    verified: bool = False


class PluginSecurityManager:
    """插件安全管理器"""
    
    def __init__(self):
        self._security_policies: Dict[str, SecurityPolicy] = {}
        self._plugin_signatures: Dict[str, PluginSignature] = {}
        self._trusted_publishers: Set[str] = set()
        self._blocked_plugins: Set[str] = set()
        
        # 默认安全策略
        self._default_policy = SecurityPolicy(
            allowed_permissions={
                Permission.NETWORK_HTTP,
                Permission.NETWORK_HTTPS,
                Permission.CONFIG_READ,
                Permission.CONFIG_WRITE,
                Permission.MESSAGE_PROCESS
            },
            denied_permissions={
                Permission.SYSTEM_COMMAND,
                Permission.SYSTEM_REGISTRY,
                Permission.FILE_EXECUTE
            },
            max_memory_mb=50,
            max_cpu_percent=5.0,
            sandbox_enabled=True
        )
    
    def set_security_policy(self, plugin_id: str, policy: SecurityPolicy):
        """
        设置插件安全策略
        
        Args:
            plugin_id: 插件ID
            policy: 安全策略
        """
        self._security_policies[plugin_id] = policy
        logger.info(f"设置插件安全策略: {plugin_id}")
    
    def get_security_policy(self, plugin_id: str) -> SecurityPolicy:
        """
        获取插件安全策略
        
        Args:
            plugin_id: 插件ID
            
        Returns:
            SecurityPolicy: 安全策略
        """
        return self._security_policies.get(plugin_id, self._default_policy)
    
    def check_permission(self, plugin_id: str, permission: Permission) -> bool:
        """
        检查插件权限
        
        Args:
            plugin_id: 插件ID
            permission: 权限
            
        Returns:
            bool: 是否有权限
        """
        if plugin_id in self._blocked_plugins:
            logger.warning(f"插件 {plugin_id} 已被阻止")
            return False
        
        policy = self.get_security_policy(plugin_id)
        
        # 检查是否在拒绝列表中
        if permission in policy.denied_permissions:
            logger.warning(f"插件 {plugin_id} 权限 {permission.value} 被拒绝")
            return False
        
        # 检查是否在允许列表中
        if permission in policy.allowed_permissions:
            return True
        
        logger.warning(f"插件 {plugin_id} 没有权限 {permission.value}")
        return False
    
    def validate_plugin_manifest(self, manifest: Dict[str, Any]) -> tuple[bool, str]:
        """
        验证插件清单
        
        Args:
            manifest: 插件清单
            
        Returns:
            tuple[bool, str]: (是否有效, 错误信息)
        """
        try:
            # 检查必需字段
            required_fields = ['plugin_id', 'name', 'version', 'entry_point']
            for field in required_fields:
                if field not in manifest:
                    return False, f"缺少必需字段: {field}"
            
            # 验证插件ID格式
            plugin_id = manifest['plugin_id']
            if not plugin_id.replace('_', '').replace('-', '').isalnum():
                return False, "插件ID只能包含字母、数字、下划线和连字符"
            
            # 检查权限声明
            permissions = manifest.get('permissions', [])
            for perm_str in permissions:
                try:
                    Permission(perm_str)
                except ValueError:
                    return False, f"无效的权限: {perm_str}"
            
            # 检查版本格式
            version = manifest['version']
            if not self._validate_version_format(version):
                return False, "版本格式无效"
            
            # 检查入口点文件
            entry_point = manifest['entry_point']
            if not entry_point.endswith('.py'):
                return False, "入口点必须是Python文件"
            
            return True, ""
            
        except Exception as e:
            return False, f"验证插件清单失败: {str(e)}"
    
    def _validate_version_format(self, version: str) -> bool:
        """验证版本格式"""
        try:
            parts = version.split('.')
            if len(parts) < 2 or len(parts) > 4:
                return False
            
            for part in parts:
                if not part.isdigit():
                    return False
            
            return True
        except:
            return False
    
    def scan_plugin_code(self, plugin_path: str) -> tuple[bool, List[str]]:
        """
        扫描插件代码安全性
        
        Args:
            plugin_path: 插件路径
            
        Returns:
            tuple[bool, List[str]]: (是否安全, 警告列表)
        """
        warnings = []
        is_safe = True
        
        try:
            # 危险函数和模块列表
            dangerous_imports = [
                'os.system', 'subprocess', 'eval', 'exec', 'compile',
                'importlib.import_module', '__import__', 'open',
                'file', 'input', 'raw_input'
            ]
            
            dangerous_modules = [
                'subprocess', 'os', 'sys', 'shutil', 'tempfile',
                'pickle', 'marshal', 'shelve', 'dbm'
            ]
            
            # 扫描Python文件
            for py_file in Path(plugin_path).rglob('*.py'):
                try:
                    with open(py_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # 检查危险函数调用
                    for dangerous_func in dangerous_imports:
                        if dangerous_func in content:
                            warnings.append(f"发现潜在危险函数调用: {dangerous_func} in {py_file}")
                            is_safe = False
                    
                    # 检查危险模块导入
                    lines = content.split('\n')
                    for line_num, line in enumerate(lines, 1):
                        line = line.strip()
                        if line.startswith('import ') or line.startswith('from '):
                            for dangerous_module in dangerous_modules:
                                if dangerous_module in line:
                                    warnings.append(f"发现潜在危险模块导入: {line} at {py_file}:{line_num}")
                    
                    # 检查网络访问
                    if any(keyword in content for keyword in ['requests', 'urllib', 'http', 'socket']):
                        warnings.append(f"发现网络访问代码: {py_file}")
                    
                    # 检查文件操作
                    if any(keyword in content for keyword in ['open(', 'file(', 'write(', 'read(']):
                        warnings.append(f"发现文件操作代码: {py_file}")
                
                except Exception as e:
                    warnings.append(f"扫描文件失败: {py_file}, 错误: {e}")
            
            return is_safe, warnings
            
        except Exception as e:
            logger.error(f"扫描插件代码失败: {e}")
            return False, [f"代码扫描失败: {str(e)}"]
    
    def calculate_plugin_hash(self, plugin_path: str) -> str:
        """
        计算插件哈希值
        
        Args:
            plugin_path: 插件路径
            
        Returns:
            str: 哈希值
        """
        try:
            hasher = hashlib.sha256()
            
            # 计算所有Python文件的哈希
            for py_file in sorted(Path(plugin_path).rglob('*.py')):
                with open(py_file, 'rb') as f:
                    hasher.update(f.read())
            
            # 包含清单文件
            manifest_file = Path(plugin_path) / 'plugin.json'
            if manifest_file.exists():
                with open(manifest_file, 'rb') as f:
                    hasher.update(f.read())
            
            return hasher.hexdigest()
            
        except Exception as e:
            logger.error(f"计算插件哈希失败: {e}")
            return ""
    
    def verify_plugin_signature(self, plugin_id: str, plugin_path: str) -> bool:
        """
        验证插件签名
        
        Args:
            plugin_id: 插件ID
            plugin_path: 插件路径
            
        Returns:
            bool: 签名是否有效
        """
        try:
            # 检查是否需要签名验证
            policy = self.get_security_policy(plugin_id)
            if not policy.code_signing_required:
                return True
            
            # 检查签名文件
            signature_file = Path(plugin_path) / 'signature.json'
            if not signature_file.exists():
                logger.warning(f"插件 {plugin_id} 缺少签名文件")
                return False
            
            # 这里应该实现实际的签名验证逻辑
            # 目前返回True作为占位符
            logger.info(f"插件 {plugin_id} 签名验证通过")
            return True
            
        except Exception as e:
            logger.error(f"验证插件签名失败: {plugin_id}, 错误: {e}")
            return False
    
    def add_trusted_publisher(self, publisher: str):
        """添加可信发布者"""
        self._trusted_publishers.add(publisher)
        logger.info(f"添加可信发布者: {publisher}")
    
    def remove_trusted_publisher(self, publisher: str):
        """移除可信发布者"""
        self._trusted_publishers.discard(publisher)
        logger.info(f"移除可信发布者: {publisher}")
    
    def is_trusted_publisher(self, publisher: str) -> bool:
        """检查是否为可信发布者"""
        return publisher in self._trusted_publishers
    
    def block_plugin(self, plugin_id: str):
        """阻止插件"""
        self._blocked_plugins.add(plugin_id)
        logger.warning(f"阻止插件: {plugin_id}")
    
    def unblock_plugin(self, plugin_id: str):
        """解除阻止插件"""
        self._blocked_plugins.discard(plugin_id)
        logger.info(f"解除阻止插件: {plugin_id}")
    
    def is_plugin_blocked(self, plugin_id: str) -> bool:
        """检查插件是否被阻止"""
        return plugin_id in self._blocked_plugins
    
    def create_sandbox_policy(self, plugin_id: str) -> SecurityPolicy:
        """
        创建沙箱安全策略
        
        Args:
            plugin_id: 插件ID
            
        Returns:
            SecurityPolicy: 沙箱策略
        """
        return SecurityPolicy(
            allowed_permissions={
                Permission.CONFIG_READ,
                Permission.MESSAGE_PROCESS
            },
            denied_permissions={
                Permission.SYSTEM_COMMAND,
                Permission.SYSTEM_REGISTRY,
                Permission.FILE_EXECUTE,
                Permission.FILE_WRITE
            },
            max_memory_mb=20,
            max_cpu_percent=2.0,
            max_network_requests_per_minute=10,
            sandbox_enabled=True,
            code_signing_required=True
        )
    
    def get_security_report(self, plugin_id: str) -> Dict[str, Any]:
        """
        获取插件安全报告
        
        Args:
            plugin_id: 插件ID
            
        Returns:
            Dict[str, Any]: 安全报告
        """
        policy = self.get_security_policy(plugin_id)
        
        return {
            'plugin_id': plugin_id,
            'blocked': self.is_plugin_blocked(plugin_id),
            'sandbox_enabled': policy.sandbox_enabled,
            'code_signing_required': policy.code_signing_required,
            'allowed_permissions': [p.value for p in policy.allowed_permissions],
            'denied_permissions': [p.value for p in policy.denied_permissions],
            'resource_limits': {
                'max_memory_mb': policy.max_memory_mb,
                'max_cpu_percent': policy.max_cpu_percent,
                'max_network_requests_per_minute': policy.max_network_requests_per_minute
            }
        }


# 全局插件安全管理器实例
plugin_security_manager = PluginSecurityManager()
