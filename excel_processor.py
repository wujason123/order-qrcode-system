#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
订单Excel数据处理和二维码生成脚本
"""

import pandas as pd
import qrcode
import os
import sqlite3
from datetime import datetime

class OrderProcessor:
    def __init__(self, excel_file="orders.xlsx", db_file="orders.db", base_url=None):
        self.excel_file = excel_file
        self.db_file = db_file
        
        # 如果没有提供base_url，自动获取本机IP
        if base_url is None:
            self.base_url = self._get_base_url()
        else:
            self.base_url = base_url
            
        self.qr_output_dir = "qrcodes"
        
        # 确保输出目录存在
        if not os.path.exists(self.qr_output_dir):
            os.makedirs(self.qr_output_dir)
    
    def _get_base_url(self):
        """自动获取本机IP地址并生成base_url"""
        import socket
        try:
            # 连接到一个远程地址来获取本机IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            base_url = f"http://{local_ip}:5000"
            print(f"自动检测到本机IP地址: {local_ip}")
            print(f"二维码将使用URL: {base_url}")
            return base_url
        except Exception as e:
            print(f"获取IP地址失败，使用localhost: {e}")
            return "http://localhost:5000"
    
    def _check_duplicate_orders(self, df):
        """检查Excel中的重复订单号"""
        try:
            # 检查Excel内部重复
            order_ids = df["订单号"].astype(str).str.strip()
            duplicates_in_excel = order_ids[order_ids.duplicated()].unique()
            
            if len(duplicates_in_excel) > 0:
                error_msg = f"Excel文件中发现重复的订单号: {', '.join(duplicates_in_excel)}"
                print(f"❌ {error_msg}")
                return {"success": False, "error": error_msg, "duplicates": duplicates_in_excel.tolist()}
            
            # 检查与数据库中现有订单的重复
            if os.path.exists(self.db_file):
                conn = sqlite3.connect(self.db_file)
                cursor = conn.cursor()
                
                # 获取数据库中现有的订单号
                cursor.execute("SELECT order_id FROM orders")
                existing_orders = {row[0] for row in cursor.fetchall()}
                conn.close()
                
                # 检查新订单号是否与现有订单重复
                new_order_ids = set(order_ids.tolist())
                duplicates_with_db = new_order_ids.intersection(existing_orders)
                
                if duplicates_with_db:
                    error_msg = f"以下订单号在数据库中已存在: {', '.join(duplicates_with_db)}"
                    print(f"❌ {error_msg}")
                    return {
                        "success": False, 
                        "error": error_msg, 
                        "duplicates": list(duplicates_with_db),
                        "type": "database_duplicate"
                    }
            
            print("✅ 订单号重复检查通过")
            return {"success": True}
            
        except Exception as e:
            error_msg = f"检查订单号重复时出错: {str(e)}"
            print(error_msg)
            return {"success": False, "error": error_msg}
    
    def init_database(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # 创建订单表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                customer_name TEXT NOT NULL,
                order_date TEXT NOT NULL,
                amount REAL NOT NULL,
                product_details TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 确保订单号唯一性约束
        cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_order_id_unique 
            ON orders (order_id)
        ''')
        
        conn.commit()
        conn.close()
        print("数据库初始化完成")
    
    def process_excel(self):
        """处理Excel文件并导入数据库"""
        try:
            # 读取Excel文件
            df = pd.read_excel(self.excel_file)
            print(f"读取Excel文件: {self.excel_file}")
            print(f"共读取 {len(df)} 条订单记录")
            
            # 打印列名，便于调试
            print("Excel列名:", df.columns.tolist())
            
            # 连接数据库
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            # 清空现有数据（可选）
            cursor.execute("DELETE FROM orders")
            
            # 插入数据
            for index, row in df.iterrows():
                try:
                    order_id = str(row["订单号"])
                    customer_name = str(row["客户姓名"])
                    order_date = str(row["订单日期"])
                    amount = float(row["金额"])
                    product_details = str(row["产品详情"])
                    
                    cursor.execute('''
                        INSERT OR REPLACE INTO orders 
                        (order_id, customer_name, order_date, amount, product_details)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (order_id, customer_name, order_date, amount, product_details))
                    
                    print(f"处理订单: {order_id}")
                    
                except Exception as e:
                    print(f"处理第 {index+1} 行数据时出错: {e}")
                    continue
            
            conn.commit()
            conn.close()
            print("数据导入完成")
            return True
            
        except Exception as e:
            print(f"处理Excel文件时出错: {e}")
            return False

    def process_excel_data(self):
        """处理Excel文件并导入数据库（返回详细状态）"""
        try:
            # 读取Excel文件
            df = pd.read_excel(self.excel_file)
            total_rows = len(df)
            print(f"读取Excel文件: {self.excel_file}")
            print(f"共读取 {total_rows} 条订单记录")
            
            # 检查必需的列
            required_columns = ["订单号", "客户姓名", "订单日期", "金额", "产品详情"]
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                error_msg = f"Excel文件缺少必需的列: {', '.join(missing_columns)}"
                print(error_msg)
                return {"success": False, "error": error_msg}
            
            # 检查订单号重复
            duplicate_check = self._check_duplicate_orders(df)
            if not duplicate_check["success"]:
                return duplicate_check
            
            # 连接数据库
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            # 注意：这里不再清空现有数据，而是使用INSERT OR REPLACE
            # 这样可以保留不冲突的现有数据，只更新重复的订单
            
            # 插入数据
            success_count = 0
            for index, row in df.iterrows():
                try:
                    order_id = str(row["订单号"]).strip()
                    customer_name = str(row["客户姓名"]).strip()
                    order_date = str(row["订单日期"]).strip()
                    amount = float(row["金额"])
                    product_details = str(row["产品详情"]).strip()
                    
                    # 基本验证
                    if not order_id or order_id == 'nan':
                        print(f"第 {index+1} 行：订单号为空，跳过")
                        continue
                    
                    cursor.execute('''
                        INSERT OR REPLACE INTO orders 
                        (order_id, customer_name, order_date, amount, product_details)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (order_id, customer_name, order_date, amount, product_details))
                    
                    success_count += 1
                    print(f"处理订单: {order_id}")
                    
                except Exception as e:
                    print(f"处理第 {index+1} 行数据时出错: {e}")
                    continue
            
            conn.commit()
            conn.close()
            
            if success_count == 0:
                return {"success": False, "error": "没有成功处理任何订单数据"}
            
            print(f"数据导入完成，成功处理 {success_count} 条订单")
            return {"success": True, "count": success_count, "total": total_rows}
            
        except Exception as e:
            error_msg = f"处理Excel文件时出错: {str(e)}"
            print(error_msg)
            return {"success": False, "error": error_msg}
    
    def generate_qrcodes(self):
        """为所有订单生成二维码"""
        try:
            # 从数据库读取订单数据
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute("SELECT order_id FROM orders")
            orders = cursor.fetchall()
            conn.close()
            
            print(f"开始生成 {len(orders)} 个二维码...")
            
            for order in orders:
                order_id = order[0]
                # 生成查询URL - 指向公共查询页面
                url = f"{self.base_url}/public?order_id={order_id}"
                
                # 创建二维码
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=10,
                    border=4,
                )
                qr.add_data(url)
                qr.make(fit=True)
                
                # 生成图片
                img = qr.make_image(fill_color="black", back_color="white")
                
                # 保存图片
                img_path = f"{self.qr_output_dir}/order_{order_id}.png"
                img.save(img_path)
                print(f"生成二维码: {img_path}")
            
            print("所有二维码生成完成！")
            return True
            
        except Exception as e:
            print(f"生成二维码时出错: {e}")
            return False

    def generate_qr_codes(self):
        """为所有订单生成二维码（返回详细状态）"""
        try:
            # 从数据库读取订单数据
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute("SELECT order_id FROM orders")
            orders = cursor.fetchall()
            conn.close()
            
            total_orders = len(orders)
            if total_orders == 0:
                return {"success": False, "error": "数据库中没有找到订单数据"}
            
            print(f"开始生成 {total_orders} 个二维码...")
            
            success_count = 0
            for order in orders:
                order_id = order[0]
                try:
                    # 生成查询URL - 指向公共查询页面
                    url = f"{self.base_url}/public?order_id={order_id}"
                    
                    # 创建二维码
                    qr = qrcode.QRCode(
                        version=1,
                        error_correction=qrcode.constants.ERROR_CORRECT_L,
                        box_size=10,
                        border=4,
                    )
                    qr.add_data(url)
                    qr.make(fit=True)
                    
                    # 生成图片
                    img = qr.make_image(fill_color="black", back_color="white")
                    
                    # 保存图片
                    img_path = f"{self.qr_output_dir}/order_{order_id}.png"
                    img.save(img_path)
                    success_count += 1
                    print(f"生成二维码: {img_path}")
                    
                except Exception as e:
                    print(f"为订单 {order_id} 生成二维码时出错: {e}")
                    continue
            
            if success_count == 0:
                return {"success": False, "error": "没有成功生成任何二维码"}
            
            print(f"二维码生成完成，成功生成 {success_count} 个二维码")
            return {"success": True, "count": success_count, "total": total_orders}
            
        except Exception as e:
            error_msg = f"生成二维码时出错: {str(e)}"
            print(error_msg)
            return {"success": False, "error": error_msg}
    
    def create_sample_excel(self):
        """创建示例Excel文件"""
        sample_data = {
            "订单号": ["ORD001", "ORD002", "ORD003", "ORD004", "ORD005"],
            "客户姓名": ["张三", "李四", "王五", "赵六", "钱七"],
            "订单日期": ["2024-01-15", "2024-01-16", "2024-01-17", "2024-01-18", "2024-01-19"],
            "金额": [1500.50, 2300.00, 800.75, 5200.25, 1200.00],
            "产品详情": [
                "苹果iPhone 15 Pro - 256GB 深空黑色",
                "小米笔记本Air 13.3英寸 - 银色版",
                "华为FreeBuds Pro 3 - 陶瓷白",
                "戴尔XPS 13 - 13.4英寸触摸屏笔记本",
                "AirPods Pro 第二代 - USB-C版本"
            ]
        }
        
        df = pd.DataFrame(sample_data)
        df.to_excel(self.excel_file, index=False)
        print(f"示例Excel文件已创建: {self.excel_file}")
    
    def run_full_process(self):
        """运行完整流程"""
        print("=== 订单二维码生成系统 ===")
        
        # 检查Excel文件是否存在
        if not os.path.exists(self.excel_file):
            print(f"Excel文件 {self.excel_file} 不存在，创建示例文件...")
            self.create_sample_excel()
        
        # 初始化数据库
        self.init_database()
        
        # 处理Excel数据
        if self.process_excel():
            # 生成二维码
            self.generate_qrcodes()
            print("\n=== 处理完成 ===")
            print(f"数据库文件: {self.db_file}")
            print(f"二维码目录: {self.qr_output_dir}")
        else:
            print("处理失败！")

if __name__ == "__main__":
    processor = OrderProcessor()
    processor.run_full_process() 