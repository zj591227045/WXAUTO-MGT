"""
插件安装器 - 支持打包后的插件安装

该模块解决了PyInstaller打包后插件安装的问题，包括：
- 动态插件目录管理
- 运行时插件加载
- 插件依赖管理
- 兼容性检查
"""

import logging
import os
import sys
import json
import importlib
import importlib.util
import subprocess
from typing import Dict, List, Optional, Any
from pathlib import Path
import tempfile
import shutil

logger = logging.getLogger(__name__)


class PluginInstaller:
    """插件安装器"""
    
    def __init__(self):
        """初始化插件安装器"""
        self.is_frozen = getattr(sys, 'frozen', False)
        self.app_dir = self._get_app_directory()
        self.plugins_dir = self.app_dir / "plugins"
        self.temp_dir = self.app_dir / "temp"
        
        # 确保目录存在
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # 添加插件目录到Python路径
        if str(self.plugins_dir) not in sys.path:
            sys.path.insert(0, str(self.plugins_dir))
        
        logger.info(f"插件安装器初始化完成，插件目录: {self.plugins_dir}")
    
    def _get_app_directory(self) -> Path:
        """获取应用程序目录"""
        if self.is_frozen:
            # PyInstaller打包后的情况
            if hasattr(sys, '_MEIPASS'):
                # 使用可写的用户数据目录
                import os
                if os.name == 'nt':  # Windows
                    app_data = os.environ.get('APPDATA', os.path.expanduser('~'))
                    return Path(app_data) / "WXAUTO-MGT"
                else:  # Linux/Mac
                    return Path.home() / ".wxauto-mgt"
            else:
                return Path(sys.executable).parent
        else:
            # 开发环境
            return Path(__file__).parent.parent.parent.parent
    
    def get_plugin_install_path(self, plugin_id: str) -> Path:
        """
        获取插件安装路径
        
        Args:
            plugin_id: 插件ID
            
        Returns:
            Path: 安装路径
        """
        return self.plugins_dir / plugin_id
    
    def install_plugin_dependencies(self, requirements: List[str]) -> tuple[bool, str]:
        """
        安装插件依赖
        
        Args:
            requirements: 依赖列表
            
        Returns:
            tuple[bool, str]: (是否成功, 错误信息)
        """
        if not requirements:
            return True, ""
        
        try:
            # 在打包环境中，需要特殊处理依赖安装
            if self.is_frozen:
                return self._install_dependencies_frozen(requirements)
            else:
                return self._install_dependencies_dev(requirements)
        
        except Exception as e:
            logger.error(f"安装插件依赖失败: {e}")
            return False, str(e)
    
    def _install_dependencies_frozen(self, requirements: List[str]) -> tuple[bool, str]:
        """在打包环境中安装依赖"""
        try:
            # 创建临时目录用于安装依赖
            deps_dir = self.app_dir / "plugin_deps"
            deps_dir.mkdir(exist_ok=True)
            
            # 添加到Python路径
            if str(deps_dir) not in sys.path:
                sys.path.insert(0, str(deps_dir))
            
            # 使用pip安装到指定目录
            for requirement in requirements:
                try:
                    # 检查是否已安装
                    if self._is_package_available(requirement):
                        logger.info(f"依赖 {requirement} 已存在")
                        continue
                    
                    # 尝试安装
                    cmd = [
                        sys.executable, "-m", "pip", "install",
                        "--target", str(deps_dir),
                        "--no-deps",  # 不安装子依赖，避免冲突
                        requirement
                    ]
                    
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode != 0:
                        logger.warning(f"安装依赖 {requirement} 失败: {result.stderr}")
                        # 继续尝试其他依赖
                    else:
                        logger.info(f"成功安装依赖: {requirement}")
                
                except Exception as e:
                    logger.warning(f"安装依赖 {requirement} 时出错: {e}")
                    continue
            
            return True, ""
        
        except Exception as e:
            return False, str(e)
    
    def _install_dependencies_dev(self, requirements: List[str]) -> tuple[bool, str]:
        """在开发环境中安装依赖"""
        try:
            for requirement in requirements:
                if self._is_package_available(requirement):
                    logger.info(f"依赖 {requirement} 已存在")
                    continue
                
                cmd = [sys.executable, "-m", "pip", "install", requirement]
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode != 0:
                    return False, f"安装依赖 {requirement} 失败: {result.stderr}"
                
                logger.info(f"成功安装依赖: {requirement}")
            
            return True, ""
        
        except Exception as e:
            return False, str(e)
    
    def _is_package_available(self, package_name: str) -> bool:
        """检查包是否可用"""
        try:
            # 处理版本号
            if '>=' in package_name or '==' in package_name or '<=' in package_name:
                package_name = package_name.split('>=')[0].split('==')[0].split('<=')[0]
            
            importlib.import_module(package_name)
            return True
        except ImportError:
            return False
    
    def validate_plugin_compatibility(self, manifest: Dict[str, Any]) -> tuple[bool, str]:
        """
        验证插件兼容性
        
        Args:
            manifest: 插件清单
            
        Returns:
            tuple[bool, str]: (是否兼容, 错误信息)
        """
        try:
            # 检查最小版本要求
            min_version = manifest.get('min_wxauto_version')
            if min_version:
                from wxauto_mgt.config import get_version
                current_version = get_version()
                if self._compare_versions(current_version, min_version) < 0:
                    return False, f"需要WXAUTO-MGT版本 {min_version} 或更高，当前版本: {current_version}"
            
            # 检查最大版本限制
            max_version = manifest.get('max_wxauto_version')
            if max_version:
                from wxauto_mgt.config import get_version
                current_version = get_version()
                if self._compare_versions(current_version, max_version) > 0:
                    return False, f"不支持WXAUTO-MGT版本 {current_version}，最大支持版本: {max_version}"
            
            # 检查Python版本
            python_version = manifest.get('python_version')
            if python_version:
                current_python = f"{sys.version_info.major}.{sys.version_info.minor}"
                if self._compare_versions(current_python, python_version) < 0:
                    return False, f"需要Python版本 {python_version} 或更高，当前版本: {current_python}"
            
            # 检查操作系统
            supported_os = manifest.get('supported_os')
            if supported_os:
                import platform
                current_os = platform.system().lower()
                if current_os not in [os.lower() for os in supported_os]:
                    return False, f"不支持当前操作系统: {current_os}"
            
            return True, ""
        
        except Exception as e:
            return False, f"兼容性检查失败: {str(e)}"
    
    def _compare_versions(self, version1: str, version2: str) -> int:
        """比较版本号"""
        try:
            v1_parts = [int(x) for x in version1.split('.')]
            v2_parts = [int(x) for x in version2.split('.')]
            
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
    
    def create_plugin_loader(self, plugin_path: str, manifest: Dict[str, Any]):
        """
        创建插件加载器
        
        Args:
            plugin_path: 插件路径
            manifest: 插件清单
        """
        try:
            plugin_id = manifest['plugin_id']
            entry_point = manifest['entry_point']
            class_name = manifest.get('class_name', 'Plugin')
            
            # 构建模块路径
            module_path = Path(plugin_path) / entry_point
            if not module_path.exists():
                raise Exception(f"插件入口文件不存在: {module_path}")
            
            # 动态加载模块
            spec = importlib.util.spec_from_file_location(
                f"plugin_{plugin_id}", 
                str(module_path)
            )
            
            if spec is None or spec.loader is None:
                raise Exception(f"无法创建模块规范: {module_path}")
            
            module = importlib.util.module_from_spec(spec)
            
            # 添加插件路径到sys.path以支持相对导入
            plugin_dir = str(Path(plugin_path))
            if plugin_dir not in sys.path:
                sys.path.insert(0, plugin_dir)
            
            try:
                spec.loader.exec_module(module)
            finally:
                # 移除插件路径
                if plugin_dir in sys.path:
                    sys.path.remove(plugin_dir)
            
            # 获取插件类
            if not hasattr(module, class_name):
                raise Exception(f"插件类不存在: {class_name}")
            
            plugin_class = getattr(module, class_name)
            
            logger.info(f"成功加载插件模块: {plugin_id}")
            return plugin_class
        
        except Exception as e:
            logger.error(f"创建插件加载器失败: {e}")
            raise
    
    def cleanup_temp_files(self):
        """清理临时文件"""
        try:
            if self.temp_dir.exists():
                for item in self.temp_dir.iterdir():
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item)
            
            logger.info("清理临时文件完成")
        
        except Exception as e:
            logger.warning(f"清理临时文件失败: {e}")
    
    def get_system_info(self) -> Dict[str, Any]:
        """获取系统信息"""
        import platform
        
        return {
            'is_frozen': self.is_frozen,
            'app_directory': str(self.app_dir),
            'plugins_directory': str(self.plugins_dir),
            'python_version': f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            'platform': platform.platform(),
            'architecture': platform.architecture()[0],
            'system': platform.system(),
            'machine': platform.machine(),
            'processor': platform.processor()
        }
    
    def create_plugin_manifest_template(self) -> Dict[str, Any]:
        """创建插件清单模板"""
        return {
            "plugin_id": "example_plugin",
            "name": "示例插件",
            "version": "1.0.0",
            "description": "这是一个示例插件",
            "author": "插件作者",
            "homepage": "https://example.com",
            "license": "MIT",
            "entry_point": "main.py",
            "class_name": "ExamplePlugin",
            "dependencies": [
                "aiohttp>=3.8.0"
            ],
            "min_wxauto_version": "1.0.0",
            "max_wxauto_version": "2.0.0",
            "python_version": "3.8",
            "supported_os": ["Windows", "Linux", "Darwin"],
            "permissions": [
                "network.http",
                "config.read",
                "config.write",
                "message.process"
            ],
            "tags": [
                "example",
                "demo"
            ],
            "config_schema": {
                "type": "object",
                "properties": {
                    "api_key": {
                        "type": "string",
                        "title": "API密钥",
                        "description": "服务API密钥",
                        "format": "password"
                    },
                    "enabled": {
                        "type": "boolean",
                        "title": "启用插件",
                        "default": True
                    }
                },
                "required": ["api_key"]
            }
        }
    
    def validate_plugin_structure(self, plugin_path: str) -> tuple[bool, List[str]]:
        """
        验证插件目录结构
        
        Args:
            plugin_path: 插件路径
            
        Returns:
            tuple[bool, List[str]]: (是否有效, 错误列表)
        """
        errors = []
        plugin_dir = Path(plugin_path)
        
        # 检查必需文件
        required_files = ['plugin.json']
        for file_name in required_files:
            file_path = plugin_dir / file_name
            if not file_path.exists():
                errors.append(f"缺少必需文件: {file_name}")
        
        # 检查清单文件
        manifest_file = plugin_dir / 'plugin.json'
        if manifest_file.exists():
            try:
                with open(manifest_file, 'r', encoding='utf-8') as f:
                    manifest = json.load(f)
                
                # 检查入口点文件
                entry_point = manifest.get('entry_point', 'main.py')
                entry_file = plugin_dir / entry_point
                if not entry_file.exists():
                    errors.append(f"入口点文件不存在: {entry_point}")
                
            except json.JSONDecodeError as e:
                errors.append(f"plugin.json格式错误: {e}")
            except Exception as e:
                errors.append(f"读取plugin.json失败: {e}")
        
        return len(errors) == 0, errors


# 全局插件安装器实例
plugin_installer = PluginInstaller()
