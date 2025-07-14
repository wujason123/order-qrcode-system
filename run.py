#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
订单二维码系统一键启动脚本
"""

import os
import sys
import subprocess
import time
from excel_processor import OrderProcessor

def check_dependencies():
    """检查Python依赖"""
    print("检查依赖包...")
    try:
        import pandas
        import qrcode
        import flask
        import sqlite3
        print("✅ 所有依赖包已安装")
        return True
    except ImportError as e:
        print(f"❌ 缺少依赖包: {e}")
        print("请运行: pip install -r requirements.txt")
        return False

def setup_system():
    """设置系统"""
    import socket
    
    # 获取本机IP地址
    def get_local_ip():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except:
            return "127.0.0.1"
    
    print("\n=== 订单二维码系统初始化 ===")
    
    # 检查依赖
    if not check_dependencies():
        return False
    
    local_ip = get_local_ip()
    base_url = f"http://{local_ip}:5000"
    print(f"🌐 使用IP地址: {local_ip}")
    
    try:
        processor = OrderProcessor(base_url=base_url)
        
        # 步骤1: 初始化数据库
        print("\n步骤1: 初始化数据库...")
        processor.init_database()
        print("✅ 数据库初始化完成")
        
        # 步骤2: 检查是否有Excel文件需要处理
        excel_file = "orders.xlsx"
        if os.path.exists(excel_file):
            print(f"\n📋 发现Excel文件: {excel_file}")
            
            # 询问是否处理Excel文件
            while True:
                choice = input("是否要处理Excel销售订单数据并自动扣减库存？(y/n): ").strip().lower()
                if choice in ['y', 'yes', '是', '']:
                    print("\n步骤2: 处理Excel销售订单数据（自动扣减库存）...")
                    result = processor.process_excel_data()
                    
                    if result["success"]:
                        print(f"✅ 成功处理 {result['success_count']} 条销售订单")
                        if result.get('failed_count', 0) > 0:
                            print(f"⚠️ 失败 {result['failed_count']} 条记录")
                        
                        # 生成二维码
                        print("\n步骤3: 生成二维码...")
                        qr_result = processor.generate_qr_codes()
                        if qr_result['success']:
                            print(f"✅ 成功生成 {qr_result['count']} 个二维码")
                        else:
                            print(f"❌ 二维码生成失败: {qr_result['error']}")
                    else:
                        print(f"❌ Excel数据处理失败: {result['error']}")
                        print("💡 您可以稍后在Web界面中上传Excel文件")
                    break
                elif choice in ['n', 'no', '否']:
                    print("⏭️ 跳过Excel文件处理，您可以稍后在Web界面中上传")
                    break
                else:
                    print("请输入 y(是) 或 n(否)")
        else:
            print(f"\n💡 未发现Excel文件 {excel_file}，您可以稍后在Web界面中上传Excel文件")
        
        print("✅ 系统初始化完成")
        return True
        
    except Exception as e:
        print(f"❌ 系统初始化失败: {e}")
        return False

def process_excel_data():
    """处理Excel数据并生成二维码"""
    import socket
    
    def get_local_ip():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except:
            return "127.0.0.1"
    
    print("\n=== 处理Excel销售订单数据 ===")
    
    # 检查Excel文件是否存在
    excel_file = "orders.xlsx"
    if not os.path.exists(excel_file):
        print(f"❌ Excel文件 {excel_file} 不存在")
        print("💡 请将要处理的Excel文件重命名为 'orders.xlsx' 并放在系统目录中")
        print("📋 Excel文件必须包含以下列：订单号、客户姓名、订单日期、产品编码、产品名称、数量、销售单价")
        return False
    
    try:
        local_ip = get_local_ip()
        base_url = f"http://{local_ip}:5000"
        print(f"🌐 使用IP地址: {local_ip}")
        
        processor = OrderProcessor(base_url=base_url)
        processor.init_database()
        
        # 处理Excel数据（包含自动扣减库存功能）
        print("\n🔄 处理Excel销售订单数据（自动扣减原料库存）...")
        result = processor.process_excel_data()
        
        if result["success"]:
            print(f"✅ 成功处理 {result['success_count']} 条销售订单")
            if result.get('failed_count', 0) > 0:
                print(f"⚠️ 失败 {result['failed_count']} 条记录")
            
            # 生成二维码
            print("\n🔄 生成二维码...")
            qr_result = processor.generate_qr_codes()
            if qr_result['success']:
                print(f"✅ 成功生成 {qr_result['count']} 个二维码")
            else:
                print(f"❌ 二维码生成失败: {qr_result['error']}")
        else:
            print(f"❌ Excel数据处理失败: {result['error']}")
            return False
            
        print("✅ Excel销售订单处理完成，已自动扣减原料库存")
        return True
        
    except Exception as e:
        print(f"❌ 处理Excel数据失败: {e}")
        return False

def start_server():
    """启动Flask服务器"""
    import socket
    
    # 获取本机IP地址
    def get_local_ip():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except:
            return "127.0.0.1"
    
    local_ip = get_local_ip()
    
    print("\n步骤2: 启动Web服务器...")
    print("=" * 60)
    print("🚀 订单二维码查询系统启动中...")
    print(f"💻 电脑端访问: http://localhost:5000")
    print(f"📱 手机端访问: http://{local_ip}:5000")
    print(f"📁 二维码位置: qrcodes/ 文件夹")
    print()
    print("📱 手机使用方法:")
    print("1. 确保手机和电脑连接同一WiFi网络") 
    print(f"2. 手机浏览器输入: {local_ip}:5000")
    print("3. 或直接扫描qrcodes文件夹中的二维码")
    print("=" * 60)
    
    try:
        # 导入并启动Flask应用
        from app import app
        app.run(debug=False, host='0.0.0.0', port=5000)
    except KeyboardInterrupt:
        print("\n👋 系统已停止")
    except Exception as e:
        print(f"❌ 服务器启动失败: {e}")

def show_menu():
    """显示操作菜单"""
    print("\n" + "="*50)
    print("🎯 订单二维码查询系统")
    print("="*50)
    print("1. 启动系统（智能检测Excel文件）")
    print("2. 仅处理Excel销售订单数据")
    print("3. 仅启动Web服务器")
    print("4. 查看系统状态")
    print("5. 退出")
    print("="*50)

def show_status():
    """显示系统状态"""
    print("\n📊 系统状态检查:")
    
    # 检查文件
    files_to_check = [
        ("Excel文件", "orders.xlsx"),
        ("数据库文件", "orders.db"),
        ("HTML模板", "templates/index.html"),
        ("二维码目录", "qrcodes/")
    ]
    
    for name, path in files_to_check:
        if os.path.exists(path):
            print(f"✅ {name}: {path}")
        else:
            print(f"❌ {name}: {path} (不存在)")
    
    # 检查数据库中的订单数量
    try:
        import sqlite3
        if os.path.exists("orders.db"):
            conn = sqlite3.connect("orders.db")
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM orders")
            count = cursor.fetchone()[0]
            conn.close()
            print(f"📦 订单数量: {count} 条")
        else:
            print("📦 订单数量: 数据库未创建")
    except Exception as e:
        print(f"📦 订单数量: 无法读取 ({e})")
    
    # 检查二维码文件
    if os.path.exists("qrcodes"):
        qr_files = [f for f in os.listdir("qrcodes") if f.endswith('.png')]
        print(f"🔍 二维码文件: {len(qr_files)} 个")
    else:
        print("🔍 二维码文件: 目录不存在")

def main():
    """主函数"""
    print("🎉 欢迎使用订单二维码查询系统！")
    
    while True:
        show_menu()
        choice = input("请选择操作 (1-5): ").strip()
        
        if choice == "1":
            # 启动系统（智能检测Excel文件）
            if setup_system():
                time.sleep(2)  # 等待2秒让用户看到结果
                start_server()
            
        elif choice == "2":
            # 仅处理Excel销售订单数据
            process_excel_data()
            input("\n按回车键返回菜单...")
            
        elif choice == "3":
            # 仅启动服务器
            if not os.path.exists("orders.db"):
                print("❌ 数据库文件不存在！请先选择选项1或2处理数据")
                input("按回车键返回菜单...")
                continue
            start_server()
            
        elif choice == "4":
            # 查看状态
            show_status()
            input("\n按回车键返回菜单...")
            
        elif choice == "5":
            # 退出
            print("👋 再见！")
            break
            
        else:
            print("❌ 无效选择，请重新输入")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 程序已退出")
    except Exception as e:
        print(f"\n❌ 程序出错: {e}")
        input("按回车键退出...") 