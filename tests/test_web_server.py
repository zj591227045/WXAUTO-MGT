#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
独立的Web服务器启动脚本，用于测试Web界面
"""

import asyncio
import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
ROOT_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(str(ROOT_DIR))

async def main():
    """主函数"""
    try:
        # 初始化数据库
        from wxauto_mgt.data.db_manager import db_manager
        
        # 确保data目录存在
        data_dir = os.path.join(ROOT_DIR, 'data')
        os.makedirs(data_dir, exist_ok=True)
        
        # 初始化数据库
        db_path = os.path.join(data_dir, 'wxauto_mgt.db')
        await db_manager.initialize(db_path)
        print(f"数据库已初始化: {db_path}")
        
        # 创建Web应用
        from wxauto_mgt.web.server import create_app
        app = create_app()
        
        # 启动服务器
        import uvicorn
        print("启动Web服务器...")
        print("访问地址: http://127.0.0.1:8000")
        
        config = uvicorn.Config(
            app=app,
            host="127.0.0.1",
            port=8000,
            log_level="info",
            reload=False
        )
        
        server = uvicorn.Server(config)
        await server.serve()
        
    except Exception as e:
        import traceback
        print(f"启动失败: {e}")
        print(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(main())
