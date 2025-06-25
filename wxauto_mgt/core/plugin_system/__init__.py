"""
WXAUTO-MGT 插件系统

该模块提供了完整的插件系统实现，包括：
- 插件接口定义
- 插件基类实现
- 插件管理器
- 插件加载器
- 插件生命周期管理

使用示例:
    from wxauto_mgt.core.plugin_system import plugin_manager
    
    # 初始化插件管理器
    await plugin_manager.initialize()
    
    # 获取服务平台插件
    platforms = plugin_manager.get_service_platforms()
"""

from .interfaces import (
    IPlugin,
    IServicePlatform,
    IMessageProcessor,
    IConfigurable,
    IHealthCheck,
    PluginInfo,
    PluginState,
    MessageType,
    MessageContext,
    ProcessResult
)

from .base_plugin import (
    BasePlugin,
    BaseServicePlatform,
    PluginException
)

from .plugin_manager import (
    PluginManager,
    PluginRegistry,
    PluginLoader,
    PluginLifecycle,
    plugin_manager
)

from .plugin_config_manager import (
    PluginConfigManager,
    PluginConfigInfo,
    plugin_config_manager
)

from .plugin_security import (
    PluginSecurityManager,
    Permission,
    SecurityPolicy,
    PluginSignature,
    plugin_security_manager
)

from .plugin_marketplace import (
    PluginMarketplace,
    plugin_marketplace
)

from .decentralized_marketplace import (
    DecentralizedMarketplace,
    MarketplacePlugin,
    PluginSource,
    PluginRepository,
    PluginAuthor,
    PluginCompatibility,
    PluginVersions,
    PluginStats,
    PluginReview,
    decentralized_marketplace
)

from .plugin_installer import (
    PluginInstaller,
    plugin_installer
)

__all__ = [
    # 接口
    'IPlugin',
    'IServicePlatform',
    'IMessageProcessor',
    'IConfigurable',
    'IHealthCheck',

    # 数据类
    'PluginInfo',
    'PluginState',
    'MessageType',
    'MessageContext',
    'ProcessResult',

    # 基类
    'BasePlugin',
    'BaseServicePlatform',
    'PluginException',

    # 管理器
    'PluginManager',
    'PluginRegistry',
    'PluginLoader',
    'PluginLifecycle',
    'plugin_manager',

    # 配置管理
    'PluginConfigManager',
    'PluginConfigInfo',
    'plugin_config_manager',

    # 安全管理
    'PluginSecurityManager',
    'Permission',
    'SecurityPolicy',
    'PluginSignature',
    'plugin_security_manager',

    # 插件市场
    'PluginMarketplace',
    'plugin_marketplace',

    # 去中心化市场
    'DecentralizedMarketplace',
    'MarketplacePlugin',
    'PluginSource',
    'PluginRepository',
    'PluginAuthor',
    'PluginCompatibility',
    'PluginVersions',
    'PluginStats',
    'PluginReview',
    'decentralized_marketplace',

    # 插件安装器
    'PluginInstaller',
    'plugin_installer'
]
