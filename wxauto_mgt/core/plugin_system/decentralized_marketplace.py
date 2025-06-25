"""
去中心化插件市场

基于Git仓库的去中心化插件分发系统，支持：
- 从GitHub/Gitee获取插件注册表
- 多源支持和智能源切换
- 版本管理和更新检查
- 插件下载和安装
"""

import logging
import json
import aiohttp
import asyncio
import time
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import zipfile
import tempfile
import shutil

logger = logging.getLogger(__name__)


@dataclass
class PluginSource:
    """插件源配置"""
    name: str
    type: str  # 'github' or 'gitee'
    registry_url: str
    api_base: str
    priority: int = 0
    timeout: int = 10
    enabled: bool = True


@dataclass
class PluginRepository:
    """插件仓库信息"""
    type: str
    url: str
    api_url: str
    releases_url: str


@dataclass
class PluginAuthor:
    """插件作者信息"""
    name: str
    github: str
    email: str
    website: Optional[str] = None


@dataclass
class PluginCompatibility:
    """插件兼容性信息"""
    min_wxauto_version: str
    max_wxauto_version: Optional[str] = None
    python_version: str = ">=3.8"
    supported_os: List[str] = None


@dataclass
class PluginVersions:
    """插件版本信息"""
    latest: str
    stable: str
    minimum_supported: str


@dataclass
class PluginStats:
    """插件统计信息"""
    downloads: int = 0
    stars: int = 0
    forks: int = 0
    rating: float = 0.0
    rating_count: int = 0


@dataclass
class PluginReview:
    """插件审核信息"""
    reviewer: str
    review_date: str
    security_score: int
    quality_score: int
    comments: str


@dataclass
class MarketplacePlugin:
    """市场插件信息"""
    plugin_id: str
    name: str
    short_description: str
    description: str
    category: str
    tags: List[str]
    author: PluginAuthor
    license: str
    homepage: str
    repository: Dict[str, PluginRepository]
    versions: PluginVersions
    compatibility: PluginCompatibility
    dependencies: List[str]
    permissions: List[str]
    features: List[str]
    screenshots: List[str]
    demo_video: Optional[str] = None
    documentation: Optional[str] = None
    issue_tracker: Optional[str] = None
    stats: Optional[PluginStats] = None
    status: str = "active"
    verified: bool = False
    featured: bool = False
    created_at: str = ""
    updated_at: str = ""
    review: Optional[PluginReview] = None


class DecentralizedMarketplace:
    """去中心化插件市场"""
    
    def __init__(self):
        """初始化去中心化市场"""
        self.sources = self._init_default_sources()
        self.cache_dir = Path("data/marketplace_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.registry_cache = {}
        self.cache_expiry = 3600  # 1小时缓存过期
        self.last_cache_time = 0
        
        self.current_source = None
        self.plugins: Dict[str, MarketplacePlugin] = {}
        self.categories: List[Dict[str, Any]] = []
        
        # 网络配置
        self.request_timeout = 30
        self.max_retries = 3
        self.retry_delay = 1
    
    def _init_default_sources(self) -> List[PluginSource]:
        """初始化默认插件源"""
        return [
            PluginSource(
                name="本地源",
                type="local",
                registry_url="file://plugins/marketplace/registry.json",
                api_base="",
                priority=0,
                timeout=1
            ),
            PluginSource(
                name="GitHub主源",
                type="github",
                registry_url="https://raw.githubusercontent.com/zj591227045/WXAUTO-MGT/main/plugins/marketplace/registry.json",
                api_base="https://api.github.com",
                priority=1,
                timeout=10
            ),
            PluginSource(
                name="Gitee镜像源",
                type="gitee",
                registry_url="https://gitee.com/zj591227045/WXAUTO-MGT/raw/main/plugins/marketplace/registry.json",
                api_base="https://gitee.com/api/v5",
                priority=2,
                timeout=8
            )
        ]
    
    async def refresh_registry(self, force: bool = False) -> bool:
        """
        刷新插件注册表
        
        Args:
            force: 是否强制刷新缓存
            
        Returns:
            bool: 是否刷新成功
        """
        try:
            # 检查缓存是否过期
            if not force and self._is_cache_valid():
                logger.info("使用缓存的插件注册表")
                return True
            
            logger.info("开始刷新插件注册表")
            
            # 尝试从各个源获取注册表
            for source in sorted(self.sources, key=lambda x: x.priority):
                if not source.enabled:
                    continue
                
                try:
                    registry_data = await self._fetch_registry_from_source(source)
                    if registry_data:
                        self._parse_registry_data(registry_data)
                        self.current_source = source
                        self._save_cache(registry_data)
                        self.last_cache_time = time.time()
                        
                        logger.info(f"成功从 {source.name} 获取插件注册表")
                        return True
                
                except Exception as e:
                    logger.warning(f"从 {source.name} 获取注册表失败: {e}")
                    continue
            
            # 所有源都失败，尝试使用缓存
            if self._load_cache():
                logger.warning("所有源都失败，使用缓存数据")
                return True
            
            logger.error("无法获取插件注册表")
            return False
            
        except Exception as e:
            logger.error(f"刷新插件注册表失败: {e}")
            return False
    
    async def _fetch_registry_from_source(self, source: PluginSource) -> Optional[Dict[str, Any]]:
        """从指定源获取注册表"""
        try:
            # 处理本地文件源
            if source.type == "local" and source.registry_url.startswith("file://"):
                return self._load_local_registry(source.registry_url[7:])  # 移除 "file://" 前缀

            # 处理远程源
            timeout = aiohttp.ClientTimeout(total=source.timeout)

            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(source.registry_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.debug(f"从 {source.name} 获取到 {len(data.get('plugins', []))} 个插件")
                        return data
                    else:
                        logger.warning(f"{source.name} 返回状态码: {response.status}")
                        return None

        except asyncio.TimeoutError:
            logger.warning(f"{source.name} 请求超时")
            return None
        except Exception as e:
            logger.warning(f"从 {source.name} 获取注册表失败: {e}")
            return None

    def _load_local_registry(self, file_path: str) -> Optional[Dict[str, Any]]:
        """加载本地注册表文件"""
        try:
            from pathlib import Path

            # 支持相对路径和绝对路径
            if not Path(file_path).is_absolute():
                # 相对于项目根目录
                file_path = Path.cwd() / file_path
            else:
                file_path = Path(file_path)

            if not file_path.exists():
                logger.warning(f"本地注册表文件不存在: {file_path}")
                return None

            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.info(f"成功加载本地注册表: {file_path}")
                logger.debug(f"本地注册表包含 {len(data.get('plugins', []))} 个插件")
                return data

        except Exception as e:
            logger.error(f"加载本地注册表失败: {e}")
            return None
    
    def _parse_registry_data(self, data: Dict[str, Any]):
        """解析注册表数据"""
        try:
            self.plugins.clear()
            
            # 解析插件列表
            for plugin_data in data.get('plugins', []):
                try:
                    # 解析作者信息
                    author_data = plugin_data.get('author', {})
                    author = PluginAuthor(**author_data)
                    
                    # 解析仓库信息
                    repo_data = plugin_data.get('repository', {})
                    repository = {}
                    for repo_type, repo_info in repo_data.items():
                        if repo_type != 'type' and isinstance(repo_info, dict):
                            # 添加type字段
                            repo_info_with_type = repo_info.copy()
                            repo_info_with_type['type'] = repo_type
                            repository[repo_type] = PluginRepository(**repo_info_with_type)
                    
                    # 解析版本信息
                    versions_data = plugin_data.get('versions', {})
                    versions = PluginVersions(**versions_data)
                    
                    # 解析兼容性信息
                    compat_data = plugin_data.get('compatibility', {})
                    compatibility = PluginCompatibility(**compat_data)
                    
                    # 解析统计信息
                    stats_data = plugin_data.get('stats')
                    stats = PluginStats(**stats_data) if stats_data else None
                    
                    # 解析审核信息
                    review_data = plugin_data.get('review')
                    review = PluginReview(**review_data) if review_data else None
                    
                    # 创建插件对象
                    plugin = MarketplacePlugin(
                        plugin_id=plugin_data['plugin_id'],
                        name=plugin_data['name'],
                        short_description=plugin_data.get('short_description', ''),
                        description=plugin_data.get('description', ''),
                        category=plugin_data.get('category', ''),
                        tags=plugin_data.get('tags', []),
                        author=author,
                        license=plugin_data.get('license', ''),
                        homepage=plugin_data.get('homepage', ''),
                        repository=repository,
                        versions=versions,
                        compatibility=compatibility,
                        dependencies=plugin_data.get('dependencies', []),
                        permissions=plugin_data.get('permissions', []),
                        features=plugin_data.get('features', []),
                        screenshots=plugin_data.get('screenshots', []),
                        demo_video=plugin_data.get('demo_video'),
                        documentation=plugin_data.get('documentation'),
                        issue_tracker=plugin_data.get('issue_tracker'),
                        stats=stats,
                        status=plugin_data.get('status', 'active'),
                        verified=plugin_data.get('verified', False),
                        featured=plugin_data.get('featured', False),
                        created_at=plugin_data.get('created_at', ''),
                        updated_at=plugin_data.get('updated_at', ''),
                        review=review
                    )
                    
                    self.plugins[plugin.plugin_id] = plugin
                    
                except Exception as e:
                    logger.warning(f"解析插件 {plugin_data.get('plugin_id', 'unknown')} 失败: {e}")
                    continue
            
            # 解析分类信息
            self.categories = data.get('categories', [])
            
            logger.info(f"成功解析 {len(self.plugins)} 个插件")
            
        except Exception as e:
            logger.error(f"解析注册表数据失败: {e}")
            raise
    
    def _is_cache_valid(self) -> bool:
        """检查缓存是否有效"""
        if not self.last_cache_time:
            return False
        
        return time.time() - self.last_cache_time < self.cache_expiry
    
    def _save_cache(self, data: Dict[str, Any]):
        """保存缓存"""
        try:
            cache_file = self.cache_dir / "registry_cache.json"
            cache_data = {
                'timestamp': time.time(),
                'source': self.current_source.name if self.current_source else None,
                'data': data
            }
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
            
            logger.debug("插件注册表缓存已保存")
            
        except Exception as e:
            logger.warning(f"保存缓存失败: {e}")
    
    def _load_cache(self) -> bool:
        """加载缓存"""
        try:
            cache_file = self.cache_dir / "registry_cache.json"
            if not cache_file.exists():
                return False
            
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # 检查缓存时间
            cache_time = cache_data.get('timestamp', 0)
            if time.time() - cache_time > self.cache_expiry * 24:  # 缓存超过24小时就不用了
                return False
            
            self._parse_registry_data(cache_data['data'])
            self.last_cache_time = cache_time
            
            logger.info("成功加载缓存的插件注册表")
            return True
            
        except Exception as e:
            logger.warning(f"加载缓存失败: {e}")
            return False
    
    async def search_plugins(self, query: str = "", category: str = "", 
                           tags: List[str] = None, featured_only: bool = False,
                           verified_only: bool = False) -> List[MarketplacePlugin]:
        """
        搜索插件
        
        Args:
            query: 搜索关键词
            category: 插件分类
            tags: 标签列表
            featured_only: 只显示精选插件
            verified_only: 只显示已验证插件
            
        Returns:
            List[MarketplacePlugin]: 匹配的插件列表
        """
        try:
            # 确保注册表是最新的
            await self.refresh_registry()
            
            results = []
            query_lower = query.lower() if query else ""
            tags = tags or []
            
            for plugin in self.plugins.values():
                # 状态过滤
                if plugin.status != 'active':
                    continue
                
                # 精选过滤
                if featured_only and not plugin.featured:
                    continue
                
                # 验证过滤
                if verified_only and not plugin.verified:
                    continue
                
                # 分类过滤
                if category and plugin.category != category:
                    continue
                
                # 标签过滤
                if tags and not any(tag in plugin.tags for tag in tags):
                    continue
                
                # 关键词搜索
                if query_lower:
                    searchable_text = f"{plugin.name} {plugin.short_description} {plugin.description} {' '.join(plugin.tags)}".lower()
                    if query_lower not in searchable_text:
                        continue
                
                results.append(plugin)
            
            # 按优先级排序：精选 > 已验证 > 下载量 > 评分
            results.sort(key=lambda p: (
                -int(p.featured),
                -int(p.verified),
                -(p.stats.downloads if p.stats else 0),
                -(p.stats.rating if p.stats else 0)
            ))
            
            logger.info(f"搜索到 {len(results)} 个插件")
            return results
            
        except Exception as e:
            logger.error(f"搜索插件失败: {e}")
            return []
    
    async def get_plugin_details(self, plugin_id: str) -> Optional[MarketplacePlugin]:
        """获取插件详细信息"""
        await self.refresh_registry()
        return self.plugins.get(plugin_id)
    
    async def get_plugin_releases(self, plugin_id: str, source_type: str = "primary") -> List[Dict[str, Any]]:
        """
        获取插件版本列表
        
        Args:
            plugin_id: 插件ID
            source_type: 源类型 ('primary' 或 'mirror')
            
        Returns:
            List[Dict[str, Any]]: 版本列表
        """
        try:
            plugin = await self.get_plugin_details(plugin_id)
            if not plugin:
                return []
            
            repo_info = plugin.repository.get(source_type)
            if not repo_info:
                # 如果指定源不存在，尝试其他源
                repo_info = next(iter(plugin.repository.values()), None)
                if not repo_info:
                    return []
            
            # 根据源类型调用不同的API
            if self.current_source and self.current_source.type == "github":
                return await self._get_github_releases(repo_info.releases_url)
            elif self.current_source and self.current_source.type == "gitee":
                return await self._get_gitee_releases(repo_info.releases_url)
            else:
                return []
                
        except Exception as e:
            logger.error(f"获取插件版本失败: {e}")
            return []
    
    async def _get_github_releases(self, releases_url: str) -> List[Dict[str, Any]]:
        """获取GitHub版本列表"""
        try:
            timeout = aiohttp.ClientTimeout(total=self.request_timeout)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(releases_url) as response:
                    if response.status == 200:
                        releases = await response.json()
                        return [
                            {
                                'tag_name': release['tag_name'],
                                'name': release['name'],
                                'published_at': release['published_at'],
                                'prerelease': release['prerelease'],
                                'zipball_url': release['zipball_url'],
                                'tarball_url': release['tarball_url'],
                                'assets': release.get('assets', [])
                            }
                            for release in releases
                        ]
                    else:
                        logger.warning(f"GitHub API返回状态码: {response.status}")
                        return []
        
        except Exception as e:
            logger.error(f"获取GitHub版本失败: {e}")
            return []
    
    async def _get_gitee_releases(self, releases_url: str) -> List[Dict[str, Any]]:
        """获取Gitee版本列表"""
        try:
            timeout = aiohttp.ClientTimeout(total=self.request_timeout)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(releases_url) as response:
                    if response.status == 200:
                        releases = await response.json()
                        return [
                            {
                                'tag_name': release['tag_name'],
                                'name': release['name'],
                                'created_at': release['created_at'],
                                'prerelease': release['prerelease'],
                                'zipball_url': release.get('zipball_url', ''),
                                'tarball_url': release.get('tarball_url', ''),
                                'assets': release.get('assets', [])
                            }
                            for release in releases
                        ]
                    else:
                        logger.warning(f"Gitee API返回状态码: {response.status}")
                        return []
        
        except Exception as e:
            logger.error(f"获取Gitee版本失败: {e}")
            return []
    
    def get_categories(self) -> List[Dict[str, Any]]:
        """获取插件分类列表"""
        return self.categories.copy()
    
    def get_featured_plugins(self) -> List[MarketplacePlugin]:
        """获取精选插件"""
        return [plugin for plugin in self.plugins.values() 
                if plugin.featured and plugin.status == 'active']
    
    def get_verified_plugins(self) -> List[MarketplacePlugin]:
        """获取已验证插件"""
        return [plugin for plugin in self.plugins.values() 
                if plugin.verified and plugin.status == 'active']
    
    def switch_source(self, source_name: str) -> bool:
        """
        切换插件源
        
        Args:
            source_name: 源名称
            
        Returns:
            bool: 是否切换成功
        """
        for source in self.sources:
            if source.name == source_name:
                # 将选中的源优先级设为最高
                source.priority = 0
                for other_source in self.sources:
                    if other_source != source:
                        other_source.priority += 1
                
                logger.info(f"切换到插件源: {source_name}")
                return True
        
        logger.warning(f"未找到插件源: {source_name}")
        return False
    
    def get_current_source(self) -> Optional[PluginSource]:
        """获取当前使用的源"""
        return self.current_source
    
    def get_available_sources(self) -> List[PluginSource]:
        """获取可用的源列表"""
        return self.sources.copy()


    async def download_plugin(self, plugin_id: str, version: str = None,
                             source_type: str = "primary") -> Optional[str]:
        """
        下载插件

        Args:
            plugin_id: 插件ID
            version: 版本号，None表示最新版本
            source_type: 源类型

        Returns:
            Optional[str]: 下载文件路径
        """
        try:
            plugin = await self.get_plugin_details(plugin_id)
            if not plugin:
                logger.error(f"插件 {plugin_id} 不存在")
                return None

            # 获取版本列表
            releases = await self.get_plugin_releases(plugin_id, source_type)
            if not releases:
                logger.error(f"无法获取插件 {plugin_id} 的版本信息")
                return None

            # 选择版本
            target_release = None
            if version:
                target_release = next((r for r in releases if r['tag_name'] == version), None)
            else:
                # 选择最新的非预发布版本
                target_release = next((r for r in releases if not r.get('prerelease', False)), None)
                if not target_release and releases:
                    target_release = releases[0]  # 如果没有正式版本，选择最新版本

            if not target_release:
                logger.error(f"未找到插件 {plugin_id} 的指定版本: {version}")
                return None

            # 选择下载URL
            download_url = target_release.get('zipball_url') or target_release.get('tarball_url')
            if not download_url:
                # 尝试从assets中找到插件包
                assets = target_release.get('assets', [])
                plugin_asset = next((asset for asset in assets
                                   if asset['name'].endswith('.zip')), None)
                if plugin_asset:
                    download_url = plugin_asset['browser_download_url']
                else:
                    logger.error(f"未找到插件 {plugin_id} 的下载链接")
                    return None

            # 下载文件
            cache_file = self.cache_dir / f"{plugin_id}_{target_release['tag_name']}.zip"

            if cache_file.exists():
                logger.info(f"使用缓存的插件文件: {cache_file}")
                return str(cache_file)

            logger.info(f"开始下载插件 {plugin_id} 版本 {target_release['tag_name']}")

            timeout = aiohttp.ClientTimeout(total=300)  # 5分钟下载超时

            async with aiohttp.ClientSession(timeout=timeout) as session:
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

    async def check_plugin_updates(self, installed_plugins: Dict[str, str]) -> Dict[str, str]:
        """
        检查插件更新

        Args:
            installed_plugins: {plugin_id: current_version}

        Returns:
            Dict[str, str]: {plugin_id: new_version}
        """
        updates = {}

        try:
            await self.refresh_registry()

            for plugin_id, current_version in installed_plugins.items():
                plugin = self.plugins.get(plugin_id)
                if not plugin:
                    continue

                latest_version = plugin.versions.latest
                if self._compare_versions(latest_version, current_version) > 0:
                    updates[plugin_id] = latest_version

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
            # 移除版本号前缀（如v1.0.0 -> 1.0.0）
            v1 = version1.lstrip('v')
            v2 = version2.lstrip('v')

            v1_parts = [int(x) for x in v1.split('.')]
            v2_parts = [int(x) for x in v2.split('.')]

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

    async def get_plugin_statistics(self) -> Dict[str, Any]:
        """获取插件市场统计信息"""
        await self.refresh_registry()

        total_plugins = len(self.plugins)
        featured_count = len(self.get_featured_plugins())
        verified_count = len(self.get_verified_plugins())

        category_stats = {}
        for plugin in self.plugins.values():
            category = plugin.category
            if category not in category_stats:
                category_stats[category] = 0
            category_stats[category] += 1

        total_downloads = sum(
            plugin.stats.downloads if plugin.stats else 0
            for plugin in self.plugins.values()
        )

        return {
            'total_plugins': total_plugins,
            'featured_plugins': featured_count,
            'verified_plugins': verified_count,
            'total_downloads': total_downloads,
            'category_stats': category_stats,
            'current_source': self.current_source.name if self.current_source else None,
            'last_update': datetime.fromtimestamp(self.last_cache_time).isoformat() if self.last_cache_time else None
        }


# 全局去中心化市场实例
decentralized_marketplace = DecentralizedMarketplace()
