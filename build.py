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
    "pytest",
    "pytest-asyncio",
    "pytest-qt"
]

# 需要包含的隐藏导入
HIDDEN_IMPORTS = [
    # 项目模块
    "wxauto_mgt",
    "wxauto_mgt.ui",
    "wxauto_mgt.core",
    "wxauto_mgt.data",
    "wxauto_mgt.utils",
    "wxauto_mgt.web",

    # 加密相关
    "cryptography",
    "cryptography.hazmat",
    "cryptography.hazmat.backends",
    "cryptography.hazmat.backends.openssl",
    "cryptography.hazmat.bindings",
    "cryptography.hazmat.primitives",
    "cryptography.hazmat.primitives.asymmetric",
    "cryptography.hazmat.primitives.ciphers",
    "cryptography.hazmat.primitives.kdf",
    "cryptography.hazmat.primitives.serialization",

    # Web相关
    "fastapi",
    "fastapi.middleware",
    "fastapi.middleware.cors",
    "fastapi.security",
    "fastapi.responses",
    "fastapi.staticfiles",
    "fastapi.templating",
    "fastapi.encoders",
    "fastapi.exceptions",

    "uvicorn",
    "uvicorn.config",
    "uvicorn.main",
    "uvicorn.middleware",
    "uvicorn.lifespan",
    "uvicorn.protocols",

    "pydantic",
    "pydantic.fields",
    "pydantic.main",
    "pydantic.error_wrappers",
    "pydantic.validators",

    "jose",
    "jose.jwt",
    "jose.exceptions",
    "jose.constants",
    "python_jose",
    "python_jose.jwt",

    "passlib",
    "passlib.context",
    "passlib.hash",
    "passlib.ifc",
    "passlib.registry",
    "passlib.handlers",
    "passlib.handlers.bcrypt",
    "bcrypt",

    "python_multipart",
    "aiofiles",

    # 其他可能需要的依赖
    "starlette",
    "starlette.middleware",
    "starlette.responses",
    "starlette.routing",
    "starlette.staticfiles",
    "starlette.templating",
    "starlette.exceptions",
    "starlette.background",
    "starlette.concurrency",
    "starlette.config",
    "starlette.datastructures",
    "starlette.formparsers",
    "starlette.types",

    "email_validator",
    "typing_extensions",
    "httptools",
    "websockets",
    "watchgod",
    "itsdangerous",
    "jinja2"
]

# 需要包含的数据文件
DATAS = [
    (str(ROOT_DIR / "wxauto_mgt" / "config"), os.path.join("wxauto_mgt", "config")),
    (str(ROOT_DIR / "wxauto_mgt"  / "requirements.txt"), os.path.join("wxauto_mgt", "web"))
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

def check_dependencies():
    """检查并安装依赖"""
    print("检查依赖...")

    # 需要安装的Web服务器依赖
    web_deps = [
        "aiofiles",
        "fastapi",
        "uvicorn",
        "python-jose[cryptography]",
        "passlib[bcrypt]",
        "python-multipart"
    ]

    # 检查并安装每个依赖
    for dep in web_deps:
        module_name = dep.split('[')[0].replace('-', '_')
        try:
            __import__(module_name)
            print(f"{dep}已安装")
        except ImportError:
            print(f"{dep}未安装，正在安装...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", dep])
                print(f"{dep}安装成功")
            except subprocess.CalledProcessError:
                print(f"警告: {dep}安装失败，可能会影响程序运行")

    # 检查web模块依赖
    web_requirements_path = os.path.join(ROOT_DIR, "wxauto_mgt", "web", "requirements.txt")
    if os.path.exists(web_requirements_path):
        print(f"检查web模块依赖: {web_requirements_path}")
        try:
            # 读取requirements.txt文件
            with open(web_requirements_path, 'r') as f:
                requirements = f.read().splitlines()

            # 过滤掉空行和注释
            requirements = [r.split('>=')[0].strip() for r in requirements if r and not r.startswith('#')]

            # 检查每个依赖
            for req in requirements:
                try:
                    module_name = req.replace('-', '_').split('[')[0]
                    __import__(module_name)
                    print(f"{req}已安装")
                except ImportError:
                    print(f"{req}未安装，正在安装...")
                    try:
                        subprocess.check_call([sys.executable, "-m", "pip", "install", req])
                        print(f"{req}安装成功")
                    except subprocess.CalledProcessError:
                        print(f"警告: {req}安装失败，可能会影响程序运行")
        except Exception as e:
            print(f"检查web模块依赖时出错: {e}")

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

    # 检查并安装依赖
    check_dependencies()

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
