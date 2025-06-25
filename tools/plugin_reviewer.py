#!/usr/bin/env python3
"""
插件审核工具

用于项目维护者审核插件提交申请的命令行工具，包括：
- 从GitHub Issues获取插件申请
- 自动化安全检查和代码质量分析
- 生成审核报告
- 更新插件注册表
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any
import aiohttp
import subprocess
import zipfile

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from wxauto_mgt.core.plugin_system.plugin_security import plugin_security_manager
from wxauto_mgt.core.plugin_system.plugin_installer import plugin_installer

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class PluginReviewer:
    """插件审核器"""
    
    def __init__(self, github_token: str = None):
        """
        初始化审核器
        
        Args:
            github_token: GitHub访问令牌
        """
        self.github_token = github_token
        self.registry_file = Path("plugins/marketplace/registry.json")
        self.temp_dir = Path("temp_review")
        self.temp_dir.mkdir(exist_ok=True)
    
    async def get_plugin_submissions(self) -> List[Dict[str, Any]]:
        """获取插件提交申请"""
        try:
            headers = {}
            if self.github_token:
                headers['Authorization'] = f'token {self.github_token}'
            
            async with aiohttp.ClientSession() as session:
                # 获取带有plugin-submission标签的Issues
                url = "https://api.github.com/repos/zj591227045/WXAUTO-MGT/issues"
                params = {
                    'labels': 'plugin-submission,needs-review',
                    'state': 'open'
                }
                
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        issues = await response.json()
                        logger.info(f"找到 {len(issues)} 个待审核的插件申请")
                        return issues
                    else:
                        logger.error(f"获取Issues失败: {response.status}")
                        return []
        
        except Exception as e:
            logger.error(f"获取插件申请失败: {e}")
            return []
    
    def parse_issue_body(self, issue_body: str) -> Dict[str, Any]:
        """解析Issue内容"""
        try:
            # 这里需要根据实际的Issue模板格式来解析
            # 简化版本，实际应该解析YAML格式的Issue模板
            plugin_data = {
                'plugin_id': '',
                'name': '',
                'version': '',
                'description': '',
                'category': '',
                'github_repo': '',
                'gitee_repo': '',
                'author_name': '',
                'author_github': '',
                'author_email': '',
                'license': '',
                'min_wxauto_version': '',
                'python_version': '',
                'supported_os': [],
                'dependencies': [],
                'permissions': [],
                'features': []
            }
            
            # 简单的文本解析（实际应该更复杂）
            lines = issue_body.split('\n')
            current_field = None
            
            for line in lines:
                line = line.strip()
                if '插件名称' in line and ':' in line:
                    plugin_data['name'] = line.split(':', 1)[1].strip()
                elif '插件唯一标识符' in line and ':' in line:
                    plugin_data['plugin_id'] = line.split(':', 1)[1].strip()
                elif '版本号' in line and ':' in line:
                    plugin_data['version'] = line.split(':', 1)[1].strip()
                elif 'GitHub仓库地址' in line and ':' in line:
                    plugin_data['github_repo'] = line.split(':', 1)[1].strip()
                # ... 更多字段解析
            
            return plugin_data
            
        except Exception as e:
            logger.error(f"解析Issue内容失败: {e}")
            return {}
    
    async def download_plugin_from_repo(self, repo_url: str, temp_path: Path) -> bool:
        """从仓库下载插件"""
        try:
            # 转换为下载URL
            if 'github.com' in repo_url:
                # GitHub: https://github.com/user/repo -> https://github.com/user/repo/archive/main.zip
                download_url = repo_url.rstrip('/') + '/archive/main.zip'
            elif 'gitee.com' in repo_url:
                # Gitee: https://gitee.com/user/repo -> https://gitee.com/user/repo/repository/archive/master.zip
                download_url = repo_url.rstrip('/') + '/repository/archive/master.zip'
            else:
                logger.error(f"不支持的仓库类型: {repo_url}")
                return False
            
            logger.info(f"下载插件: {download_url}")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(download_url) as response:
                    if response.status == 200:
                        zip_file = temp_path / "plugin.zip"
                        with open(zip_file, 'wb') as f:
                            async for chunk in response.content.iter_chunked(8192):
                                f.write(chunk)
                        
                        # 解压文件
                        with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                            zip_ref.extractall(temp_path)
                        
                        # 删除zip文件
                        zip_file.unlink()
                        
                        logger.info("插件下载成功")
                        return True
                    else:
                        logger.error(f"下载失败: {response.status}")
                        return False
        
        except Exception as e:
            logger.error(f"下载插件失败: {e}")
            return False
    
    def find_plugin_directory(self, temp_path: Path) -> Optional[Path]:
        """查找插件目录"""
        try:
            # 查找包含plugin.json的目录
            for item in temp_path.rglob("plugin.json"):
                return item.parent
            
            # 如果没找到，查找第一个子目录
            subdirs = [item for item in temp_path.iterdir() if item.is_dir()]
            if subdirs:
                return subdirs[0]
            
            return None
            
        except Exception as e:
            logger.error(f"查找插件目录失败: {e}")
            return None
    
    async def review_plugin(self, plugin_data: Dict[str, Any], issue_number: int) -> Dict[str, Any]:
        """审核插件"""
        review_result = {
            'plugin_id': plugin_data.get('plugin_id', ''),
            'issue_number': issue_number,
            'passed': False,
            'security_score': 0,
            'quality_score': 0,
            'errors': [],
            'warnings': [],
            'recommendations': []
        }
        
        try:
            repo_url = plugin_data.get('github_repo', '')
            if not repo_url:
                review_result['errors'].append("缺少GitHub仓库地址")
                return review_result
            
            # 创建临时目录
            temp_path = self.temp_dir / f"review_{issue_number}"
            temp_path.mkdir(exist_ok=True)
            
            try:
                # 下载插件
                if not await self.download_plugin_from_repo(repo_url, temp_path):
                    review_result['errors'].append("无法下载插件代码")
                    return review_result
                
                # 查找插件目录
                plugin_dir = self.find_plugin_directory(temp_path)
                if not plugin_dir:
                    review_result['errors'].append("未找到有效的插件目录")
                    return review_result
                
                # 验证插件结构
                is_valid, structure_errors = plugin_installer.validate_plugin_structure(str(plugin_dir))
                if not is_valid:
                    review_result['errors'].extend(structure_errors)
                
                # 读取插件清单
                manifest_file = plugin_dir / "plugin.json"
                if manifest_file.exists():
                    with open(manifest_file, 'r', encoding='utf-8') as f:
                        manifest = json.load(f)
                    
                    # 验证清单
                    is_valid, error_msg = plugin_security_manager.validate_plugin_manifest(manifest)
                    if not is_valid:
                        review_result['errors'].append(f"插件清单验证失败: {error_msg}")
                    
                    # 检查插件ID是否匹配
                    if manifest.get('plugin_id') != plugin_data.get('plugin_id'):
                        review_result['errors'].append("插件ID与申请不匹配")
                
                # 安全检查
                is_safe, security_warnings = plugin_security_manager.scan_plugin_code(str(plugin_dir))
                if not is_safe:
                    review_result['warnings'].extend(security_warnings)
                    review_result['security_score'] = max(0, 100 - len(security_warnings) * 10)
                else:
                    review_result['security_score'] = 100
                
                # 代码质量检查
                quality_score = await self._check_code_quality(plugin_dir)
                review_result['quality_score'] = quality_score
                
                # 文档检查
                doc_score = self._check_documentation(plugin_dir)
                if doc_score < 80:
                    review_result['recommendations'].append("建议完善文档")
                
                # 综合评分
                if (len(review_result['errors']) == 0 and 
                    review_result['security_score'] >= 80 and 
                    review_result['quality_score'] >= 70):
                    review_result['passed'] = True
                
            finally:
                # 清理临时文件
                if temp_path.exists():
                    shutil.rmtree(temp_path)
            
            return review_result
            
        except Exception as e:
            logger.error(f"审核插件失败: {e}")
            review_result['errors'].append(f"审核过程出错: {str(e)}")
            return review_result
    
    async def _check_code_quality(self, plugin_dir: Path) -> int:
        """检查代码质量"""
        try:
            score = 100
            
            # 检查Python文件
            python_files = list(plugin_dir.rglob("*.py"))
            if not python_files:
                return 0
            
            for py_file in python_files:
                try:
                    with open(py_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # 简单的质量检查
                    lines = content.split('\n')
                    
                    # 检查文档字符串
                    if not content.strip().startswith('"""') and not content.strip().startswith("'''"):
                        score -= 5
                    
                    # 检查注释比例
                    comment_lines = sum(1 for line in lines if line.strip().startswith('#'))
                    if len(lines) > 0 and comment_lines / len(lines) < 0.1:
                        score -= 10
                    
                    # 检查函数文档
                    func_count = content.count('def ')
                    doc_count = content.count('"""') + content.count("'''")
                    if func_count > 0 and doc_count / func_count < 0.5:
                        score -= 10
                
                except Exception as e:
                    logger.warning(f"检查文件质量失败: {py_file}, {e}")
                    score -= 5
            
            return max(0, score)
            
        except Exception as e:
            logger.error(f"代码质量检查失败: {e}")
            return 0
    
    def _check_documentation(self, plugin_dir: Path) -> int:
        """检查文档完整性"""
        try:
            score = 0
            
            # 检查README文件
            readme_files = list(plugin_dir.glob("README*"))
            if readme_files:
                score += 40
                
                # 检查README内容
                try:
                    with open(readme_files[0], 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    if len(content) > 500:  # 至少500字符
                        score += 20
                    if '安装' in content or 'install' in content.lower():
                        score += 10
                    if '使用' in content or 'usage' in content.lower():
                        score += 10
                    if '配置' in content or 'config' in content.lower():
                        score += 10
                
                except Exception:
                    pass
            
            # 检查许可证文件
            license_files = list(plugin_dir.glob("LICENSE*"))
            if license_files:
                score += 10
            
            return min(100, score)
            
        except Exception as e:
            logger.error(f"文档检查失败: {e}")
            return 0
    
    def generate_review_report(self, review_result: Dict[str, Any]) -> str:
        """生成审核报告"""
        report = f"""
# 插件审核报告

**插件ID**: {review_result['plugin_id']}
**Issue编号**: #{review_result['issue_number']}
**审核结果**: {'✅ 通过' if review_result['passed'] else '❌ 未通过'}

## 评分

- **安全评分**: {review_result['security_score']}/100
- **质量评分**: {review_result['quality_score']}/100

## 问题列表

### 错误 ({len(review_result['errors'])})
"""
        
        for error in review_result['errors']:
            report += f"- ❌ {error}\n"
        
        report += f"\n### 警告 ({len(review_result['warnings'])})\n"
        for warning in review_result['warnings']:
            report += f"- ⚠️ {warning}\n"
        
        report += f"\n### 建议 ({len(review_result['recommendations'])})\n"
        for rec in review_result['recommendations']:
            report += f"- 💡 {rec}\n"
        
        if review_result['passed']:
            report += "\n## 审核通过\n\n插件已通过审核，可以添加到插件市场。"
        else:
            report += "\n## 审核未通过\n\n请根据上述问题修改插件后重新提交。"
        
        return report
    
    async def add_plugin_to_registry(self, plugin_data: Dict[str, Any], 
                                   review_result: Dict[str, Any]) -> bool:
        """将插件添加到注册表"""
        try:
            # 读取现有注册表
            if self.registry_file.exists():
                with open(self.registry_file, 'r', encoding='utf-8') as f:
                    registry = json.load(f)
            else:
                registry = {
                    "version": "1.0.0",
                    "plugins": [],
                    "categories": [],
                    "metadata": {}
                }
            
            # 构建插件信息
            plugin_entry = {
                "plugin_id": plugin_data['plugin_id'],
                "name": plugin_data['name'],
                "short_description": plugin_data.get('short_description', ''),
                "description": plugin_data.get('description', ''),
                "category": plugin_data.get('category', 'utility'),
                "tags": plugin_data.get('tags', []),
                "author": {
                    "name": plugin_data.get('author_name', ''),
                    "github": plugin_data.get('author_github', ''),
                    "email": plugin_data.get('author_email', ''),
                    "website": plugin_data.get('author_website', '')
                },
                "license": plugin_data.get('license', ''),
                "homepage": plugin_data.get('github_repo', ''),
                "repository": {
                    "type": "git",
                    "primary": {
                        "url": plugin_data.get('github_repo', ''),
                        "api_url": plugin_data.get('github_repo', '').replace('github.com', 'api.github.com/repos'),
                        "releases_url": plugin_data.get('github_repo', '').replace('github.com', 'api.github.com/repos') + '/releases'
                    }
                },
                "versions": {
                    "latest": plugin_data.get('version', '1.0.0'),
                    "stable": plugin_data.get('version', '1.0.0'),
                    "minimum_supported": plugin_data.get('version', '1.0.0')
                },
                "compatibility": {
                    "min_wxauto_version": plugin_data.get('min_wxauto_version', '1.0.0'),
                    "python_version": plugin_data.get('python_version', '>=3.8'),
                    "supported_os": plugin_data.get('supported_os', ['Windows', 'Linux', 'Darwin'])
                },
                "dependencies": plugin_data.get('dependencies', []),
                "permissions": plugin_data.get('permissions', []),
                "features": plugin_data.get('features', []),
                "screenshots": plugin_data.get('screenshots', []),
                "status": "active",
                "verified": True,
                "featured": False,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "review": {
                    "reviewer": "project_maintainer",
                    "review_date": datetime.now().isoformat(),
                    "security_score": review_result['security_score'],
                    "quality_score": review_result['quality_score'],
                    "comments": "通过自动化审核"
                }
            }
            
            # 添加镜像仓库
            if plugin_data.get('gitee_repo'):
                plugin_entry["repository"]["mirror"] = {
                    "url": plugin_data['gitee_repo'],
                    "api_url": plugin_data['gitee_repo'].replace('gitee.com', 'gitee.com/api/v5/repos'),
                    "releases_url": plugin_data['gitee_repo'].replace('gitee.com', 'gitee.com/api/v5/repos') + '/releases'
                }
            
            # 添加到注册表
            registry["plugins"].append(plugin_entry)
            
            # 更新元数据
            registry["last_updated"] = datetime.now().isoformat()
            registry["metadata"]["total_plugins"] = len(registry["plugins"])
            
            # 保存注册表
            with open(self.registry_file, 'w', encoding='utf-8') as f:
                json.dump(registry, f, indent=2, ensure_ascii=False)
            
            logger.info(f"插件 {plugin_data['plugin_id']} 已添加到注册表")
            return True
            
        except Exception as e:
            logger.error(f"添加插件到注册表失败: {e}")
            return False
    
    async def post_review_comment(self, issue_number: int, comment: str) -> bool:
        """在Issue中发布审核评论"""
        try:
            if not self.github_token:
                logger.warning("未提供GitHub令牌，无法发布评论")
                return False
            
            headers = {
                'Authorization': f'token {self.github_token}',
                'Content-Type': 'application/json'
            }
            
            data = {'body': comment}
            
            async with aiohttp.ClientSession() as session:
                url = f"https://api.github.com/repos/zj591227045/WXAUTO-MGT/issues/{issue_number}/comments"
                async with session.post(url, headers=headers, json=data) as response:
                    if response.status == 201:
                        logger.info(f"审核评论已发布到Issue #{issue_number}")
                        return True
                    else:
                        logger.error(f"发布评论失败: {response.status}")
                        return False
        
        except Exception as e:
            logger.error(f"发布审核评论失败: {e}")
            return False


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="WXAUTO-MGT插件审核工具")
    parser.add_argument("--github-token", help="GitHub访问令牌")
    parser.add_argument("--issue", type=int, help="指定要审核的Issue编号")
    parser.add_argument("--auto-approve", action="store_true", help="自动批准通过审核的插件")
    
    args = parser.parse_args()
    
    # 从环境变量获取GitHub令牌
    github_token = args.github_token or os.getenv('GITHUB_TOKEN')
    
    reviewer = PluginReviewer(github_token)
    
    try:
        if args.issue:
            # 审核指定Issue
            logger.info(f"审核Issue #{args.issue}")
            # 这里需要实现单个Issue的审核逻辑
        else:
            # 审核所有待审核的插件申请
            submissions = await reviewer.get_plugin_submissions()
            
            for issue in submissions:
                issue_number = issue['number']
                issue_body = issue['body']
                
                logger.info(f"开始审核Issue #{issue_number}: {issue['title']}")
                
                # 解析Issue内容
                plugin_data = reviewer.parse_issue_body(issue_body)
                if not plugin_data.get('plugin_id'):
                    logger.warning(f"Issue #{issue_number} 解析失败，跳过")
                    continue
                
                # 执行审核
                review_result = await reviewer.review_plugin(plugin_data, issue_number)
                
                # 生成审核报告
                report = reviewer.generate_review_report(review_result)
                print(f"\n{'='*50}")
                print(f"Issue #{issue_number} 审核报告")
                print('='*50)
                print(report)
                
                # 发布审核评论
                if github_token:
                    await reviewer.post_review_comment(issue_number, report)
                
                # 如果审核通过且启用自动批准
                if review_result['passed'] and args.auto_approve:
                    success = await reviewer.add_plugin_to_registry(plugin_data, review_result)
                    if success:
                        logger.info(f"插件 {plugin_data['plugin_id']} 已自动添加到市场")
    
    except KeyboardInterrupt:
        logger.info("审核被用户中断")
    except Exception as e:
        logger.error(f"审核过程出错: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
