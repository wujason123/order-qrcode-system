@echo off
chcp 65001 >nul

:: 订单二维码查询系统 - Windows一键部署脚本
echo 🚀 订单二维码查询系统 - 准备部署...
echo ==================================

:: 检查git是否初始化
if not exist ".git" (
    echo 📦 初始化Git仓库...
    git init
)

:: 添加所有文件
echo 📂 添加文件到Git...
git add .

:: 提交代码
echo 💾 提交代码...
set /p commit_message="请输入提交信息 (默认: 订单二维码查询系统部署): "
if "%commit_message%"=="" set commit_message=订单二维码查询系统部署
git commit -m "%commit_message%"

:: 检查远程仓库
git remote | findstr "origin" >nul
if %errorlevel% neq 0 (
    echo 🔗 请设置GitHub远程仓库...
    set /p repo_url="请输入GitHub仓库URL: "
    git remote add origin "%repo_url%"
)

:: 推送到GitHub
echo ⬆️ 推送到GitHub...
git branch -M main
git push -u origin main

echo.
echo ✅ 代码推送完成！
echo.
echo 🌐 下一步部署选择：
echo ==================================
echo 1. 🏆 Render (推荐)
echo    - 访问: https://render.com
echo    - 点击 'New' → 'Web Service'
echo    - 连接您的GitHub仓库
echo    - 配置参数：
echo      Build Command: pip install -r requirements.txt
echo      Start Command: gunicorn app:app --bind 0.0.0.0:$PORT
echo.
echo 2. 🐍 PythonAnywhere
echo    - 访问: https://www.pythonanywhere.com
echo    - 注册免费账号
echo    - 克隆您的仓库
echo    - 配置Flask应用
echo.
echo 3. 🚂 Railway
echo    - 访问: https://railway.app
echo    - 使用GitHub登录
echo    - 选择您的仓库
echo    - 自动部署
echo.
echo 📖 详细部署步骤请参考: 部署指南.md
echo.
echo 🎉 祝您部署成功！
echo.
pause 