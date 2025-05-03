@echo off
echo 正在使用清华大学镜像源安装依赖...
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
echo 安装完成！
pause
