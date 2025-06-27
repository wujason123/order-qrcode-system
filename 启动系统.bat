@echo off
chcp 65001 >nul
title 订单二维码查询系统

echo.
echo ======================================
echo      订单二维码查询系统
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

:: 安装依赖包
echo 正在安装依赖包...
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com

if errorlevel 1 (
    echo ❌ 依赖包安装失败
    echo 💡 建议使用专门的安装脚本：双击运行"安装依赖.bat"
    echo 或者手动执行以下命令：
    echo pip install pandas qrcode flask openpyxl flask-cors -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
    pause
    exit /b 1
)

echo ✅ 依赖包安装完成
echo.

:: 网络配置提醒
echo ========================================
echo           网络配置重要提醒
echo ========================================
echo.
echo 📱 手机需要与电脑在同一WiFi网络下才能扫码！
echo.
echo 🔧 使用步骤：
echo 1. 确保电脑和手机连接同一WiFi
echo 2. 系统启动后会显示手机访问地址
echo 3. 手机浏览器先测试能否访问该地址  
echo 4. 网络正常后再扫描二维码
echo.
echo 📋 如遇问题，请查看"网络配置指南.txt"
echo ========================================
echo.

:: 启动系统
echo 正在启动订单二维码查询系统...
python run.py

pause 