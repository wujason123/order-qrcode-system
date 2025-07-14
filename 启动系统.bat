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

:: 启动说明
echo ========================================
echo           启动说明
echo ========================================
echo.
echo 🚀 系统启动后会：
echo 1. 自动初始化数据库
echo 2. 智能检测Excel文件（如果有）
echo 3. 询问是否处理Excel并自动扣减库存
echo 4. 启动Web服务器
echo.
echo 💡 Web界面也支持：
echo • 上传销售订单Excel自动扣减库存
echo • 库存管理和BOM配置
echo • 订单查询和二维码生成
echo.
echo 📱 手机扫码需要与电脑在同一WiFi下
echo ========================================
echo.

:: 启动系统
echo 正在启动订单二维码查询系统...
python run.py

pause 