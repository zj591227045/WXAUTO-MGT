#!/usr/bin/env python3
"""
清除认证Token的工具脚本

当JWT密钥发生变化导致token验证失败时，可以使用此脚本清除浏览器中的认证token。
"""

import requests
import sys

def clear_auth_token(host="localhost", port=8080):
    """
    清除认证token
    
    Args:
        host: Web服务主机地址
        port: Web服务端口
    """
    try:
        url = f"http://{host}:{port}/api/auth/logout"
        
        print(f"正在清除认证token: {url}")
        
        # 调用logout API
        response = requests.post(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0:
                print("✓ 认证token已清除")
                print("请刷新浏览器页面重新登录")
                return True
            else:
                print(f"✗ 清除失败: {data.get('message', '未知错误')}")
        else:
            print(f"✗ HTTP错误: {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print(f"✗ 无法连接到Web服务 {host}:{port}")
        print("请确保Web服务正在运行")
    except requests.exceptions.Timeout:
        print("✗ 请求超时")
    except Exception as e:
        print(f"✗ 发生错误: {e}")
    
    return False

def main():
    """主函数"""
    print("wxauto_Mgt 认证Token清除工具")
    print("=" * 40)
    
    # 解析命令行参数
    host = "localhost"
    port = 8080
    
    if len(sys.argv) >= 2:
        host = sys.argv[1]
    if len(sys.argv) >= 3:
        try:
            port = int(sys.argv[2])
        except ValueError:
            print("错误: 端口必须是数字")
            sys.exit(1)
    
    print(f"目标服务: http://{host}:{port}")
    print()
    
    success = clear_auth_token(host, port)
    
    if success:
        print("\n操作完成！")
        print("现在您可以:")
        print("1. 刷新浏览器页面")
        print("2. 重新输入密码登录")
    else:
        print("\n操作失败！")
        print("您也可以手动清除浏览器Cookie:")
        print("1. 打开浏览器开发者工具 (F12)")
        print("2. 转到 Application/Storage 标签")
        print("3. 在 Cookies 下找到您的网站")
        print("4. 删除名为 'auth_token' 的Cookie")
        print("5. 刷新页面")

if __name__ == "__main__":
    main()
