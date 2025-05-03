#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
WxAuto管理程序打包脚本

使用PyInstaller将程序打包为单个可执行文件。
"""

import os
import sys
import shutil
import subprocess
import platform
from pathlib import Path

# 项目根目录
ROOT_DIR = Path(os.path.dirname(os.path.abspath(__file__)))

# 添加项目根目录到Python路径
sys.path.insert(0, str(ROOT_DIR))

# 打包配置
APP_NAME = "WxAuto管理工具"
APP_VERSION = "0.1.0"
MAIN_SCRIPT = Path(os.path.join(ROOT_DIR, "wxauto_mgt", "main.py"))
ICON_PATH = Path(os.path.join(ROOT_DIR, "wxauto_mgt", "resources", "icons", "app_icon.ico"))
OUTPUT_DIR = "dist"

# 需要排除的模块
EXCLUDED_MODULES = [
    "ssl",
    "_ssl",
    "pytest",
    "pytest-asyncio",
    "pytest-qt"
]

# 需要包含的隐藏导入
HIDDEN_IMPORTS = [
    "wxauto_mgt",
    "wxauto_mgt.ui",
    "wxauto_mgt.core",
    "wxauto_mgt.data",
    "wxauto_mgt.utils",
    "cryptography",
    "cryptography.hazmat",
    "cryptography.hazmat.backends",
    "cryptography.hazmat.backends.openssl",
    "cryptography.hazmat.bindings",
    "cryptography.hazmat.primitives",
    "cryptography.hazmat.primitives.asymmetric",
    "cryptography.hazmat.primitives.ciphers",
    "cryptography.hazmat.primitives.kdf",
    "cryptography.hazmat.primitives.serialization"
]

# 需要包含的数据文件
DATAS = [
    (str(ROOT_DIR / "wxauto_mgt" / "config"), os.path.join("wxauto_mgt", "config"))
]

# 创建必要的数据目录结构
def create_data_dirs():
    """创建必要的数据目录结构"""
    print("创建数据目录结构...")

    # 在dist目录中创建data目录及其子目录
    data_dirs = [
        "data",
        "data/logs",
        "data/downloads"
    ]

    # 在Windows上使用反斜杠
    if platform.system() == "Windows":
        data_dirs = [
            "data",
            "data\\logs",
            "data\\downloads"
        ]

    for dir_path in data_dirs:
        full_path = os.path.join(ROOT_DIR, OUTPUT_DIR, dir_path)
        if not os.path.exists(full_path):
            os.makedirs(full_path)
            print(f"创建目录: {full_path}")

    # 创建空的数据库文件
    db_path = os.path.join(ROOT_DIR, OUTPUT_DIR, "data", "wxauto_mgt.db")
    if not os.path.exists(db_path):
        with open(db_path, 'w') as f:
            pass
        print(f"创建空数据库文件: {db_path}")

    print("数据目录结构创建完成")

def clean_build_dirs():
    """清理构建目录"""
    print("正在清理构建目录...")

    # 清理PyInstaller生成的目录
    build_dirs = ["build", "dist"]
    for dir_name in build_dirs:
        dir_path = os.path.join(ROOT_DIR, dir_name)
        if os.path.exists(dir_path):
            print(f"删除目录: {dir_path}")
            shutil.rmtree(dir_path)

    # 清理PyInstaller生成的spec文件
    spec_file = os.path.join(ROOT_DIR, f"{APP_NAME}.spec")
    if os.path.exists(spec_file):
        print(f"删除文件: {spec_file}")
        os.remove(spec_file)

    print("构建目录清理完成")

def create_spec_file():
    """创建自定义spec文件"""
    print("创建自定义spec文件...")

    # 准备数据文件字符串
    datas_str = ", ".join([f"(r'{src}', r'{dst}')" for src, dst in DATAS])

    # 准备图标路径
    icon_path = str(ICON_PATH) if ICON_PATH.exists() else ""

    spec_content = f"""# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

# 项目根目录
ROOT_DIR = r'{str(ROOT_DIR)}'

a = Analysis(
    [r'{str(MAIN_SCRIPT)}'],
    pathex=[r'{str(ROOT_DIR)}'],
    binaries=[],
    datas=[{datas_str}],
    hiddenimports={HIDDEN_IMPORTS},
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes={EXCLUDED_MODULES},
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='{APP_NAME}',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=r'{icon_path}' if r'{icon_path}' else None,
)
"""

    spec_path = os.path.join(ROOT_DIR, f"{APP_NAME}.spec")
    with open(spec_path, 'w', encoding='utf-8') as f:
        f.write(spec_content)

    print(f"自定义spec文件已创建: {spec_path}")
    return spec_path

def build_executable():
    """构建可执行文件"""
    print(f"开始构建 {APP_NAME} v{APP_VERSION}...")

    # 创建自定义spec文件
    spec_path = create_spec_file()

    # 使用spec文件构建
    cmd = [
        "pyinstaller",
        "--clean",  # 清理临时文件
        "--noconfirm",  # 不确认覆盖
        spec_path
    ]

    # 执行PyInstaller命令
    print("执行打包命令:", " ".join(cmd))
    result = subprocess.run(cmd, cwd=ROOT_DIR)

    if result.returncode != 0:
        print(f"构建失败，返回码: {result.returncode}")
        return False

    print(f"构建成功，可执行文件位于: {os.path.join(OUTPUT_DIR, APP_NAME)}")
    return True

def main():
    """主函数"""
    print("=" * 80)
    print(f"WxAuto管理程序打包工具 v{APP_VERSION}")
    print("=" * 80)

    # 检查PyInstaller是否已安装
    try:
        import PyInstaller
        print(f"PyInstaller版本: {PyInstaller.__version__}")
    except ImportError:
        print("错误: PyInstaller未安装，请先安装: pip install pyinstaller")
        return False

    # 清理构建目录
    clean_build_dirs()

    # 构建可执行文件
    if not build_executable():
        return False

    # 创建数据目录结构
    create_data_dirs()

    print("=" * 80)
    print("打包完成！")
    print(f"可执行文件: {os.path.join(OUTPUT_DIR, APP_NAME + ('.exe' if platform.system() == 'Windows' else ''))}")
    print("数据目录已创建: {0}".format(os.path.join(OUTPUT_DIR, "data")))
    print("=" * 80)

    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
