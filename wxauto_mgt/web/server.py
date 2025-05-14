"""
Web服务器实现

提供Flask应用创建和服务器运行功能。
"""

import os
import signal
import threading
from flask import Flask, render_template
from wxauto_mgt.utils.logging import logger

# 全局变量
_shutdown_requested = False
_server = None

def create_app():
    """
    创建Flask应用
    
    Returns:
        Flask: Flask应用实例
    """
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), 'templates'),
        static_folder=os.path.join(os.path.dirname(__file__), 'static')
    )
    
    # 配置
    app.config['SECRET_KEY'] = os.urandom(24)
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    
    # 注册路由
    from .routes import register_routes
    register_routes(app)
    
    # 错误处理
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('error.html', error="页面未找到"), 404
    
    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('error.html', error="服务器内部错误"), 500
    
    return app

def run_server(app, host, port):
    """
    在线程中运行Flask服务器
    
    Args:
        app: Flask应用实例
        host: 主机地址
        port: 端口号
    """
    global _server
    
    try:
        # 使用werkzeug的服务器，支持在线程中运行
        from werkzeug.serving import make_server
        
        _server = make_server(host, port, app)
        logger.info(f"Web服务器启动中，地址: {host}:{port}")
        _server.serve_forever()
    except Exception as e:
        logger.error(f"Web服务器运行失败: {e}")
    finally:
        logger.info("Web服务器已停止")

def stop_server():
    """停止服务器"""
    global _server
    
    if _server:
        logger.info("正在停止Web服务器...")
        _server.shutdown()
        _server = None
