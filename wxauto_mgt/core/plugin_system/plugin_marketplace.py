"""
插件市场和分发系统

该模块提供了插件市场功能，包括：
- 插件下载和安装
- 插件市场API
- 插件包管理
- 版本更新检查
"""

import logging
import json
import os
import zipfile
import tempfile
import shutil
import aiohttp
from typing import Dict, List, Optional, Any
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime

from .plugin_security import plugin_security_manager
from .plugin_manager import plugin_manager
from .plugin_config_manager import plugin_config_manager

logger = logging.getLogger(__name__)


@dataclass
class MarketplacePlugin:
    """市场插件信息"""
    plugin_id: str
    name: str
    version: str
    description: str
    author: str
    category: str
    tags: List[str]
    download_url: str
    homepage: Optional[str] = None
    license: Optional[str] = None
    min_wxauto_version: Optional[str] = None
    max_wxauto_version: Optional[str] = None
    file_size: int = 0
    download_count: int = 0
    rating: float = 0.0
    rating_count: int = 0
    created_at: str = ""
    updated_at: str = ""
    verified: bool = False
    featured: bool = False


@dataclass
class PluginPackage:
    """插件包信息"""
    plugin_id: str
    version: str
    file_path: str
    file_hash: str
    manifest: Dict[str, Any]
    installed: bool = False
    install_path: Optional[str] = None


class PluginMarketplace:
    """插件市场"""
    
    def __init__(self, marketplace_url: str = "https://api.wxauto-mgt.com/plugins"):
        """
        初始化插件市场
        
        Args:
            marketplace_url: 市场API地址
        """
        self.marketplace_url = marketplace_url
        self.cache_dir = Path("data/plugin_cache")
        self.plugins_dir = Path("plugins")
        self.installed_plugins_file = Path("data/installed_plugins.json")
        
        # 确保目录存在
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        
        self._marketplace_plugins: Dict[str, MarketplacePlugin] = {}
        self._installed_packages: Dict[str, PluginPackage] = {}
        
        # 加载已安装插件信息
        self._load_installed_plugins()
    
    def _load_installed_plugins(self):
        """加载已安装插件信息"""
        try:
            if self.installed_plugins_file.exists():
                with open(self.installed_plugins_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                for plugin_data in data:
                    package = PluginPackage(**plugin_data)
                    self._installed_packages[package.plugin_id] = package
                
                logger.info(f"加载了 {len(self._installed_packages)} 个已安装插件信息")
        
        except Exception as e:
            logger.error(f"加载已安装插件信息失败: {e}")
    
    def _save_installed_plugins(self):
        """保存已安装插件信息"""
        try:
            data = [asdict(package) for package in self._installed_packages.values()]
            
            with open(self.installed_plugins_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info("保存已安装插件信息成功")
        
        except Exception as e:
            logger.error(f"保存已安装插件信息失败: {e}")
    
    async def fetch_marketplace_plugins(self, category: str = None, 
                                      search_query: str = None) -> List[MarketplacePlugin]:
        """
        获取市场插件列表
        
        Args:
            category: 插件分类
            search_query: 搜索关键词
            
        Returns:
            List[MarketplacePlugin]: 插件列表
        """
        try:
            params = {}
            if category:
                params['category'] = category
            if search_query:
                params['search'] = search_query
            
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.marketplace_url}/list", params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        plugins = []
                        
                        for plugin_data in data.get('plugins', []):
                            plugin = MarketplacePlugin(**plugin_data)
                            plugins.append(plugin)
                            self._marketplace_plugins[plugin.plugin_id] = plugin
                        
                        logger.info(f"获取到 {len(plugins)} 个市场插件")
                        return plugins
                    else:
                        logger.error(f"获取市场插件失败: HTTP {response.status}")
                        return []
        
        except Exception as e:
            logger.error(f"获取市场插件失败: {e}")
            return []
    
    async def get_plugin_details(self, plugin_id: str) -> Optional[MarketplacePlugin]:
        """
        获取插件详细信息
        
        Args:
            plugin_id: 插件ID
            
        Returns:
            Optional[MarketplacePlugin]: 插件信息
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.marketplace_url}/plugin/{plugin_id}") as response:
                    if response.status == 200:
                        data = await response.json()
                        plugin = MarketplacePlugin(**data)
                        self._marketplace_plugins[plugin_id] = plugin
                        return plugin
                    else:
                        logger.error(f"获取插件详情失败: HTTP {response.status}")
                        return None
        
        except Exception as e:
            logger.error(f"获取插件详情失败: {e}")
            return None
    
    async def download_plugin(self, plugin_id: str, version: str = None) -> Optional[str]:
        """
        下载插件
        
        Args:
            plugin_id: 插件ID
            version: 版本号，None表示最新版本
            
        Returns:
            Optional[str]: 下载文件路径
        """
        try:
            # 获取插件信息
            plugin_info = await self.get_plugin_details(plugin_id)
            if not plugin_info:
                logger.error(f"插件 {plugin_id} 不存在")
                return None
            
            # 构建下载URL
            download_url = plugin_info.download_url
            if version:
                download_url += f"?version={version}"
            
            # 下载文件
            cache_file = self.cache_dir / f"{plugin_id}_{plugin_info.version}.zip"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(download_url) as response:
                    if response.status == 200:
                        with open(cache_file, 'wb') as f:
                            async for chunk in response.content.iter_chunked(8192):
                                f.write(chunk)
                        
                        logger.info(f"插件 {plugin_id} 下载成功: {cache_file}")
                        return str(cache_file)
                    else:
                        logger.error(f"下载插件失败: HTTP {response.status}")
                        return None
        
        except Exception as e:
            logger.error(f"下载插件失败: {e}")
            return None
    
    async def install_plugin_from_file(self, plugin_file: str) -> tuple[bool, str]:
        """
        从文件安装插件
        
        Args:
            plugin_file: 插件文件路径
            
        Returns:
            tuple[bool, str]: (是否成功, 错误信息)
        """
        try:
            # 创建临时目录
            with tempfile.TemporaryDirectory() as temp_dir:
                # 解压插件文件
                with zipfile.ZipFile(plugin_file, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
                
                # 查找插件清单文件
                manifest_file = None
                for root, dirs, files in os.walk(temp_dir):
                    if 'plugin.json' in files:
                        manifest_file = os.path.join(root, 'plugin.json')
                        plugin_dir = root
                        break
                
                if not manifest_file:
                    return False, "插件包中未找到 plugin.json 文件"
                
                # 读取插件清单
                with open(manifest_file, 'r', encoding='utf-8') as f:
                    manifest = json.load(f)
                
                plugin_id = manifest['plugin_id']
                
                # 验证插件清单
                is_valid, error_msg = plugin_security_manager.validate_plugin_manifest(manifest)
                if not is_valid:
                    return False, f"插件清单验证失败: {error_msg}"
                
                # 扫描插件代码安全性
                is_safe, warnings = plugin_security_manager.scan_plugin_code(plugin_dir)
                if not is_safe:
                    logger.warning(f"插件 {plugin_id} 安全扫描发现问题: {warnings}")
                    # 可以选择是否继续安装
                
                # 验证插件签名
                if not plugin_security_manager.verify_plugin_signature(plugin_id, plugin_dir):
                    logger.warning(f"插件 {plugin_id} 签名验证失败")
                
                # 检查是否已安装
                target_dir = self.plugins_dir / plugin_id
                if target_dir.exists():
                    # 备份现有版本
                    backup_dir = self.plugins_dir / f"{plugin_id}_backup"
                    if backup_dir.exists():
                        shutil.rmtree(backup_dir)
                    shutil.move(str(target_dir), str(backup_dir))
                
                # 复制插件文件
                shutil.copytree(plugin_dir, str(target_dir))
                
                # 计算文件哈希
                file_hash = plugin_security_manager.calculate_plugin_hash(str(target_dir))
                
                # 创建插件包信息
                package = PluginPackage(
                    plugin_id=plugin_id,
                    version=manifest['version'],
                    file_path=plugin_file,
                    file_hash=file_hash,
                    manifest=manifest,
                    installed=True,
                    install_path=str(target_dir)
                )
                
                self._installed_packages[plugin_id] = package
                self._save_installed_plugins()
                
                # 加载插件到管理器
                success = await plugin_manager.install_plugin(manifest)
                if not success:
                    # 安装失败，回滚
                    shutil.rmtree(str(target_dir))
                    backup_dir = self.plugins_dir / f"{plugin_id}_backup"
                    if backup_dir.exists():
                        shutil.move(str(backup_dir), str(target_dir))
                    return False, "插件加载失败"
                
                # 清理备份
                backup_dir = self.plugins_dir / f"{plugin_id}_backup"
                if backup_dir.exists():
                    shutil.rmtree(backup_dir)
                
                logger.info(f"插件 {plugin_id} 安装成功")
                return True, ""
        
        except Exception as e:
            logger.error(f"安装插件失败: {e}")
            return False, str(e)
    
    async def install_plugin_from_marketplace(self, plugin_id: str, 
                                            version: str = None) -> tuple[bool, str]:
        """
        从市场安装插件
        
        Args:
            plugin_id: 插件ID
            version: 版本号
            
        Returns:
            tuple[bool, str]: (是否成功, 错误信息)
        """
        try:
            # 下载插件
            plugin_file = await self.download_plugin(plugin_id, version)
            if not plugin_file:
                return False, "下载插件失败"
            
            # 安装插件
            success, error_msg = await self.install_plugin_from_file(plugin_file)
            
            # 清理下载文件
            try:
                os.remove(plugin_file)
            except:
                pass
            
            return success, error_msg
        
        except Exception as e:
            logger.error(f"从市场安装插件失败: {e}")
            return False, str(e)
    
    async def uninstall_plugin(self, plugin_id: str) -> tuple[bool, str]:
        """
        卸载插件
        
        Args:
            plugin_id: 插件ID
            
        Returns:
            tuple[bool, str]: (是否成功, 错误信息)
        """
        try:
            # 从插件管理器卸载
            success = await plugin_manager.uninstall_plugin(plugin_id)
            if not success:
                return False, "从插件管理器卸载失败"
            
            # 删除插件文件
            plugin_dir = self.plugins_dir / plugin_id
            if plugin_dir.exists():
                shutil.rmtree(plugin_dir)
            
            # 删除配置
            await plugin_config_manager.delete_plugin_config(plugin_id)
            
            # 从已安装列表移除
            if plugin_id in self._installed_packages:
                del self._installed_packages[plugin_id]
                self._save_installed_plugins()
            
            logger.info(f"插件 {plugin_id} 卸载成功")
            return True, ""
        
        except Exception as e:
            logger.error(f"卸载插件失败: {e}")
            return False, str(e)
    
    async def check_plugin_updates(self) -> Dict[str, str]:
        """
        检查插件更新
        
        Returns:
            Dict[str, str]: {plugin_id: new_version}
        """
        updates = {}
        
        try:
            for plugin_id, package in self._installed_packages.items():
                # 获取市场最新版本
                plugin_info = await self.get_plugin_details(plugin_id)
                if plugin_info and plugin_info.version != package.version:
                    # 简单版本比较（实际应该使用语义化版本比较）
                    if self._compare_versions(plugin_info.version, package.version) > 0:
                        updates[plugin_id] = plugin_info.version
            
            logger.info(f"发现 {len(updates)} 个插件更新")
            return updates
        
        except Exception as e:
            logger.error(f"检查插件更新失败: {e}")
            return {}
    
    def _compare_versions(self, version1: str, version2: str) -> int:
        """
        比较版本号
        
        Args:
            version1: 版本1
            version2: 版本2
            
        Returns:
            int: 1表示version1更新，-1表示version2更新，0表示相同
        """
        try:
            v1_parts = [int(x) for x in version1.split('.')]
            v2_parts = [int(x) for x in version2.split('.')]
            
            # 补齐长度
            max_len = max(len(v1_parts), len(v2_parts))
            v1_parts.extend([0] * (max_len - len(v1_parts)))
            v2_parts.extend([0] * (max_len - len(v2_parts)))
            
            for v1, v2 in zip(v1_parts, v2_parts):
                if v1 > v2:
                    return 1
                elif v1 < v2:
                    return -1
            
            return 0
        
        except:
            return 0
    
    def get_installed_plugins(self) -> List[PluginPackage]:
        """获取已安装插件列表"""
        return list(self._installed_packages.values())
    
    def is_plugin_installed(self, plugin_id: str) -> bool:
        """检查插件是否已安装"""
        return plugin_id in self._installed_packages
    
    def get_plugin_categories(self) -> List[str]:
        """获取插件分类列表"""
        categories = set()
        for plugin in self._marketplace_plugins.values():
            categories.add(plugin.category)
        return sorted(list(categories))


# 全局插件市场实例
plugin_marketplace = PluginMarketplace()
