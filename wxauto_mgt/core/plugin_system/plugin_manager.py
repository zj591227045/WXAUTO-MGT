"""
插件管理器

该模块实现了插件系统的核心管理功能，包括：
- PluginManager: 插件管理器主类
- PluginRegistry: 插件注册表
- PluginLoader: 插件加载器
- PluginLifecycle: 插件生命周期管理
"""

import logging
import os
import sys
import json
import importlib
import importlib.util
from typing import Dict, List, Optional, Any, Type
from pathlib import Path
from dataclasses import asdict

from .interfaces import IPlugin, IServicePlatform, PluginInfo, PluginState
from .base_plugin import BasePlugin, PluginException

logger = logging.getLogger(__name__)


class PluginRegistry:
    """插件注册表"""
    
    def __init__(self):
        self._plugins: Dict[str, IPlugin] = {}
        self._plugin_info: Dict[str, PluginInfo] = {}
        self._plugin_types: Dict[str, Type[IPlugin]] = {}
    
    def register_plugin_type(self, plugin_type: str, plugin_class: Type[IPlugin]):
        """
        注册插件类型
        
        Args:
            plugin_type: 插件类型标识
            plugin_class: 插件类
        """
        self._plugin_types[plugin_type] = plugin_class
        logger.debug(f"注册插件类型: {plugin_type}")
    
    def register_plugin(self, plugin: IPlugin):
        """
        注册插件实例
        
        Args:
            plugin: 插件实例
        """
        info = plugin.get_info()
        self._plugins[info.plugin_id] = plugin
        self._plugin_info[info.plugin_id] = info
        logger.info(f"注册插件: {info.name} ({info.plugin_id})")
    
    def unregister_plugin(self, plugin_id: str):
        """
        注销插件
        
        Args:
            plugin_id: 插件ID
        """
        if plugin_id in self._plugins:
            info = self._plugin_info[plugin_id]
            del self._plugins[plugin_id]
            del self._plugin_info[plugin_id]
            logger.info(f"注销插件: {info.name} ({plugin_id})")
    
    def get_plugin(self, plugin_id: str) -> Optional[IPlugin]:
        """获取插件实例"""
        return self._plugins.get(plugin_id)
    
    def get_plugin_info(self, plugin_id: str) -> Optional[PluginInfo]:
        """获取插件信息"""
        return self._plugin_info.get(plugin_id)
    
    def get_all_plugins(self) -> Dict[str, IPlugin]:
        """获取所有插件"""
        return self._plugins.copy()
    
    def get_all_plugin_info(self) -> Dict[str, PluginInfo]:
        """获取所有插件信息"""
        return self._plugin_info.copy()
    
    def get_plugins_by_type(self, plugin_type: Type[IPlugin]) -> List[IPlugin]:
        """
        根据类型获取插件
        
        Args:
            plugin_type: 插件类型
            
        Returns:
            List[IPlugin]: 插件列表
        """
        return [plugin for plugin in self._plugins.values() 
                if isinstance(plugin, plugin_type)]
    
    def get_service_platforms(self) -> List[IServicePlatform]:
        """获取所有服务平台插件"""
        return self.get_plugins_by_type(IServicePlatform)


class PluginLoader:
    """插件加载器"""
    
    def __init__(self, plugin_dirs: List[str] = None):
        """
        初始化插件加载器
        
        Args:
            plugin_dirs: 插件目录列表
        """
        self.plugin_dirs = plugin_dirs or []
        self._loaded_modules = {}
    
    def discover_plugins(self) -> List[Dict[str, Any]]:
        """
        发现插件
        
        Returns:
            List[Dict[str, Any]]: 插件清单列表
        """
        plugins = []
        
        for plugin_dir in self.plugin_dirs:
            if not os.path.exists(plugin_dir):
                logger.warning(f"插件目录不存在: {plugin_dir}")
                continue
            
            plugins.extend(self._scan_directory(plugin_dir))
        
        logger.info(f"发现 {len(plugins)} 个插件")
        return plugins
    
    def _scan_directory(self, directory: str) -> List[Dict[str, Any]]:
        """
        扫描目录中的插件
        
        Args:
            directory: 目录路径
            
        Returns:
            List[Dict[str, Any]]: 插件清单列表
        """
        plugins = []
        
        for item in os.listdir(directory):
            item_path = os.path.join(directory, item)
            
            # 检查是否为插件目录
            if os.path.isdir(item_path):
                manifest_path = os.path.join(item_path, "plugin.json")
                if os.path.exists(manifest_path):
                    try:
                        with open(manifest_path, 'r', encoding='utf-8') as f:
                            manifest = json.load(f)
                        
                        manifest['path'] = item_path
                        plugins.append(manifest)
                        
                    except Exception as e:
                        logger.error(f"读取插件清单失败: {manifest_path}, 错误: {e}")
        
        return plugins
    
    def load_plugin(self, manifest: Dict[str, Any]) -> Optional[IPlugin]:
        """
        加载插件
        
        Args:
            manifest: 插件清单
            
        Returns:
            Optional[IPlugin]: 插件实例
        """
        try:
            plugin_path = manifest['path']
            entry_point = manifest.get('entry_point', 'main.py')
            class_name = manifest.get('class_name', 'Plugin')
            
            # 构建模块路径
            module_path = os.path.join(plugin_path, entry_point)
            if not os.path.exists(module_path):
                raise PluginException(f"插件入口文件不存在: {module_path}")
            
            # 加载模块
            module_name = f"plugin_{manifest['plugin_id']}"
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            if spec is None or spec.loader is None:
                raise PluginException(f"无法创建模块规范: {module_path}")
            
            module = importlib.util.module_from_spec(spec)
            self._loaded_modules[manifest['plugin_id']] = module
            
            # 添加插件路径到sys.path
            if plugin_path not in sys.path:
                sys.path.insert(0, plugin_path)
            
            try:
                spec.loader.exec_module(module)
            finally:
                # 移除插件路径
                if plugin_path in sys.path:
                    sys.path.remove(plugin_path)
            
            # 获取插件类
            if not hasattr(module, class_name):
                raise PluginException(f"插件类不存在: {class_name}")
            
            plugin_class = getattr(module, class_name)
            
            # 创建插件信息
            plugin_info = PluginInfo(
                plugin_id=manifest['plugin_id'],
                name=manifest['name'],
                version=manifest['version'],
                description=manifest.get('description', ''),
                author=manifest.get('author', ''),
                homepage=manifest.get('homepage'),
                license=manifest.get('license'),
                dependencies=manifest.get('dependencies', []),
                min_wxauto_version=manifest.get('min_wxauto_version'),
                max_wxauto_version=manifest.get('max_wxauto_version'),
                permissions=manifest.get('permissions', []),
                tags=manifest.get('tags', [])
            )
            
            # 创建插件实例
            plugin = plugin_class(plugin_info)
            
            logger.info(f"加载插件成功: {manifest['name']} ({manifest['plugin_id']})")
            return plugin
            
        except Exception as e:
            logger.error(f"加载插件失败: {manifest.get('name', 'unknown')}, 错误: {e}")
            return None
    
    def unload_plugin(self, plugin_id: str):
        """
        卸载插件
        
        Args:
            plugin_id: 插件ID
        """
        if plugin_id in self._loaded_modules:
            del self._loaded_modules[plugin_id]
            logger.info(f"卸载插件模块: {plugin_id}")


class PluginLifecycle:
    """插件生命周期管理"""
    
    def __init__(self, registry: PluginRegistry):
        """
        初始化生命周期管理器
        
        Args:
            registry: 插件注册表
        """
        self.registry = registry
    
    async def initialize_plugin(self, plugin_id: str, config: Dict[str, Any]) -> bool:
        """
        初始化插件
        
        Args:
            plugin_id: 插件ID
            config: 插件配置
            
        Returns:
            bool: 是否成功
        """
        plugin = self.registry.get_plugin(plugin_id)
        if not plugin:
            logger.error(f"插件不存在: {plugin_id}")
            return False
        
        return await plugin.initialize(config)
    
    async def activate_plugin(self, plugin_id: str) -> bool:
        """
        激活插件
        
        Args:
            plugin_id: 插件ID
            
        Returns:
            bool: 是否成功
        """
        plugin = self.registry.get_plugin(plugin_id)
        if not plugin:
            logger.error(f"插件不存在: {plugin_id}")
            return False
        
        return await plugin.activate()
    
    async def deactivate_plugin(self, plugin_id: str) -> bool:
        """
        停用插件
        
        Args:
            plugin_id: 插件ID
            
        Returns:
            bool: 是否成功
        """
        plugin = self.registry.get_plugin(plugin_id)
        if not plugin:
            logger.error(f"插件不存在: {plugin_id}")
            return False
        
        return await plugin.deactivate()
    
    async def cleanup_plugin(self, plugin_id: str) -> bool:
        """
        清理插件
        
        Args:
            plugin_id: 插件ID
            
        Returns:
            bool: 是否成功
        """
        plugin = self.registry.get_plugin(plugin_id)
        if not plugin:
            logger.error(f"插件不存在: {plugin_id}")
            return False
        
        return await plugin.cleanup()


class PluginManager:
    """插件管理器主类"""

    def __init__(self, plugin_dirs: List[str] = None):
        """
        初始化插件管理器

        Args:
            plugin_dirs: 插件目录列表
        """
        self.registry = PluginRegistry()
        self.loader = PluginLoader(plugin_dirs)
        self.lifecycle = PluginLifecycle(self.registry)
        self._initialized = False

    async def initialize(self):
        """初始化插件管理器"""
        if self._initialized:
            return

        logger.info("初始化插件管理器")

        # 注册内置插件类型
        self._register_builtin_plugin_types()

        # 发现并加载插件
        await self._discover_and_load_plugins()

        self._initialized = True
        logger.info("插件管理器初始化完成")

    def _register_builtin_plugin_types(self):
        """注册内置插件类型"""
        # 这里可以注册内置的插件类型
        pass

    async def _discover_and_load_plugins(self):
        """发现并加载插件"""
        try:
            # 发现插件
            manifests = self.loader.discover_plugins()

            # 加载插件
            for manifest in manifests:
                plugin = self.loader.load_plugin(manifest)
                if plugin:
                    self.registry.register_plugin(plugin)

        except Exception as e:
            logger.error(f"发现和加载插件失败: {e}")

    async def install_plugin(self, manifest: Dict[str, Any], config: Dict[str, Any] = None) -> bool:
        """
        安装插件

        Args:
            manifest: 插件清单
            config: 插件配置

        Returns:
            bool: 是否成功
        """
        try:
            # 加载插件
            plugin = self.loader.load_plugin(manifest)
            if not plugin:
                return False

            # 注册插件
            self.registry.register_plugin(plugin)

            # 初始化插件
            if config:
                await self.lifecycle.initialize_plugin(manifest['plugin_id'], config)

            logger.info(f"安装插件成功: {manifest['name']}")
            return True

        except Exception as e:
            logger.error(f"安装插件失败: {manifest.get('name', 'unknown')}, 错误: {e}")
            return False

    async def uninstall_plugin(self, plugin_id: str) -> bool:
        """
        卸载插件

        Args:
            plugin_id: 插件ID

        Returns:
            bool: 是否成功
        """
        try:
            # 清理插件
            await self.lifecycle.cleanup_plugin(plugin_id)

            # 注销插件
            self.registry.unregister_plugin(plugin_id)

            # 卸载模块
            self.loader.unload_plugin(plugin_id)

            logger.info(f"卸载插件成功: {plugin_id}")
            return True

        except Exception as e:
            logger.error(f"卸载插件失败: {plugin_id}, 错误: {e}")
            return False

    async def enable_plugin(self, plugin_id: str, config: Dict[str, Any] = None) -> bool:
        """
        启用插件

        Args:
            plugin_id: 插件ID
            config: 插件配置

        Returns:
            bool: 是否成功
        """
        try:
            # 初始化插件
            if config:
                success = await self.lifecycle.initialize_plugin(plugin_id, config)
                if not success:
                    return False

            # 激活插件
            return await self.lifecycle.activate_plugin(plugin_id)

        except Exception as e:
            logger.error(f"启用插件失败: {plugin_id}, 错误: {e}")
            return False

    async def disable_plugin(self, plugin_id: str) -> bool:
        """
        禁用插件

        Args:
            plugin_id: 插件ID

        Returns:
            bool: 是否成功
        """
        try:
            return await self.lifecycle.deactivate_plugin(plugin_id)

        except Exception as e:
            logger.error(f"禁用插件失败: {plugin_id}, 错误: {e}")
            return False

    def get_plugin(self, plugin_id: str) -> Optional[IPlugin]:
        """获取插件实例"""
        return self.registry.get_plugin(plugin_id)

    def get_plugin_info(self, plugin_id: str) -> Optional[PluginInfo]:
        """获取插件信息"""
        return self.registry.get_plugin_info(plugin_id)

    def get_all_plugins(self) -> Dict[str, IPlugin]:
        """获取所有插件"""
        return self.registry.get_all_plugins()

    def get_all_plugin_info(self) -> Dict[str, PluginInfo]:
        """获取所有插件信息"""
        return self.registry.get_all_plugin_info()

    def get_service_platforms(self) -> List[IServicePlatform]:
        """获取所有服务平台插件"""
        return self.registry.get_service_platforms()

    async def health_check_all(self) -> Dict[str, Dict[str, Any]]:
        """
        对所有插件执行健康检查

        Returns:
            Dict[str, Dict[str, Any]]: 健康检查结果
        """
        results = {}

        for plugin_id, plugin in self.registry.get_all_plugins().items():
            try:
                if hasattr(plugin, 'health_check'):
                    results[plugin_id] = await plugin.health_check()
                else:
                    results[plugin_id] = {
                        'plugin_id': plugin_id,
                        'healthy': True,
                        'message': '插件不支持健康检查'
                    }
            except Exception as e:
                results[plugin_id] = {
                    'plugin_id': plugin_id,
                    'healthy': False,
                    'error': str(e)
                }

        return results


# 全局插件管理器实例
plugin_manager = PluginManager()
