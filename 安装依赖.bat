@echo off
chcp 65001 >nul
title 安装Python依赖包

echo.
echo ======================================
echo      安装订单二维码系统依赖包
echo ======================================
echo.

:: 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 未检测到Python，请先安装Python 3.7+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo ✅ Python已安装
echo.

echo 正在尝试不同的镜像源安装依赖包...
echo.

:: 方法1: 使用阿里云镜像
echo 🔄 尝试阿里云镜像...
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
if not errorlevel 1 (
    echo ✅ 依赖包安装成功！
    goto success
)

:: 方法2: 使用豆瓣镜像
echo 🔄 尝试豆瓣镜像...
pip install -r requirements.txt -i https://pypi.douban.com/simple/ --trusted-host pypi.douban.com
if not errorlevel 1 (
    echo ✅ 依赖包安装成功！
    goto success
)

:: 方法3: 使用腾讯云镜像
echo 🔄 尝试腾讯云镜像...
pip install -r requirements.txt -i https://mirrors.cloud.tencent.com/pypi/simple/ --trusted-host mirrors.cloud.tencent.com
if not errorlevel 1 (
    echo ✅ 依赖包安装成功！
    goto success
)

:: 方法4: 使用官方源
echo 🔄 尝试官方PyPI源...
pip install -r requirements.txt
if not errorlevel 1 (
    echo ✅ 依赖包安装成功！
    goto success
)

:: 方法5: 逐个安装
echo 🔄 尝试逐个安装包...
pip install pandas==1.5.3 -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
pip install qrcode[pil]==7.4.2 -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
pip install Flask==2.3.3 -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
pip install openpyxl==3.1.2 -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
pip install flask-cors==4.0.0 -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com

if not errorlevel 1 (
    echo ✅ 依赖包安装成功！
    goto success
)

:: 所有方法都失败
echo ❌ 所有镜像源都无法访问，请检查网络连接或尝试以下解决方案：
echo.
echo 💡 解决建议：
echo 1. 检查网络连接是否正常
echo 2. 关闭VPN或代理软件
echo 3. 检查防火墙设置
echo 4. 尝试手动安装：pip install pandas qrcode flask openpyxl flask-cors
echo 5. 联系网络管理员检查网络限制
echo.
pause
exit /b 1

:success
echo.
echo 🎉 所有依赖包安装完成！
echo 现在可以运行系统了。
echo.
pause 