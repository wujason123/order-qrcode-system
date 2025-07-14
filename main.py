#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Replit 部署专用启动文件
"""
import os
from app import app, init_app

if __name__ == '__main__':
    # 初始化应用
    init_app()
    
    # Replit 部署配置
    port = int(os.environ.get('PORT', 8080))  # Replit 推荐用 8080
    host = '0.0.0.0'  # Replit 必须用 0.0.0.0
    
    print("🚀 订单二维码管理系统启动中...")
    print(f"🌐 Replit 部署地址: {host}:{port}")
    print("📱 支持手机和电脑访问")
    
    # 启动 Flask 应用
    app.run(host=host, port=port, debug=False) 